"""Structured output parsing for Game Master responses.

This module provides structured parsing of GM responses using Pydantic models
instead of fragile regex matching. It works alongside the existing parser.py
to provide a migration path.

Usage:
    from game.structured_parser import parse_structured_response, extract_tool_output
    
    # Option 1: Parse JSON tool outputs directly
    if response.startswith('{'):
        result = extract_tool_output(response)
    
    # Option 2: Use LLM with structured output
    from game.structured_parser import get_structured_llm
    llm = get_structured_llm()
    response = llm.invoke(messages)  # Returns GameMasterResponse

The structured approach replaces these regex markers:
- [SEARCHED:location] -> action.action_type = "search_location"
- [ACCUSATION:suspect] -> action.action_type = "make_accusation"
- [CLUE_FOUND:id] -> action.clue_ids_revealed = [id]
- [SCENE_BRIEF{...}] -> scene_brief = SceneBrief(...)
- [AUDIO:path] -> (handled separately in TTS)
"""

import os
import json
import logging
import re
from typing import Optional, Tuple, Dict, Any

from pydantic import ValidationError

from game.models import (
    GameMasterResponse,
    GameAction,
    SceneBrief,
    StructuredToolOutput,
)
from game.state import GameState

logger = logging.getLogger(__name__)


# =============================================================================
# TOOL OUTPUT PARSING (Structured JSON from tools)
# =============================================================================

def extract_tool_output(response: str) -> Optional[StructuredToolOutput]:
    """Extract structured tool output from a response.
    
    Tools like interrogate_suspect and describe_scene_for_image can return
    JSON that we parse directly instead of using regex markers.
    
    Args:
        response: Raw response string (may be JSON or text with JSON)
    
    Returns:
        StructuredToolOutput if JSON found, None otherwise
    """
    # Try direct JSON parse first
    try:
        data = json.loads(response.strip())
        if isinstance(data, dict):
            return _parse_tool_dict(data)
    except json.JSONDecodeError:
        pass
    
    # Look for embedded JSON in the response
    json_patterns = [
        r'\[SCENE_BRIEF(\{[^}]+\})\]',  # Scene brief marker
        r'```json\s*(\{[^`]+\})\s*```',  # Code block JSON
        r'(\{[^{}]*"tool_name"[^{}]*\})',  # Tool output with tool_name
        r'(\{[^{}]*"narrative"[^{}]*\})',  # Output with narrative field
    ]
    
    for pattern in json_patterns:
        match = re.search(pattern, response, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                if isinstance(data, dict):
                    result = _parse_tool_dict(data)
                    if result:
                        return result
            except json.JSONDecodeError:
                continue
    
    return None


def _parse_tool_dict(data: Dict[str, Any]) -> Optional[StructuredToolOutput]:
    """Parse a dictionary into StructuredToolOutput."""
    try:
        # Check if it's a scene brief
        if "location" in data and "visual_description" in data:
            scene_brief = SceneBrief(
                location=data.get("location", ""),
                visual_description=data.get("visual_description", ""),
                camera_angle=data.get("camera_angle", "medium shot"),
                mood=data.get("mood", "mysterious"),
                focus_element=data.get("focus_element")
            )
            return StructuredToolOutput(
                tool_name="describe_scene_for_image",
                narrative=data.get("narrative", data.get("visual_description", "")),
                scene_brief=scene_brief
            )
        
        # Check if it's already a StructuredToolOutput format
        if "tool_name" in data:
            return StructuredToolOutput(**data)
        
        # Check if it has narrative (generic tool output)
        if "narrative" in data:
            action = None
            if "action" in data:
                action = GameAction(**data["action"])
            
            return StructuredToolOutput(
                tool_name=data.get("tool_name", "unknown"),
                narrative=data["narrative"],
                speaker=data.get("speaker"),
                action=action,
                raw_data=data
            )
        
        return None
        
    except (ValidationError, TypeError) as e:
        logger.warning(f"Failed to parse tool output: {e}")
        return None


# =============================================================================
# RESPONSE PARSING (Convert legacy markers to structured)
# =============================================================================

def parse_response_to_structured(
    response: str,
    state: Optional[GameState] = None
) -> GameMasterResponse:
    """Parse a GM response (with legacy markers) into structured format.
    
    This provides backward compatibility while moving toward structured outputs.
    It converts regex-matched markers into GameMasterResponse fields.
    
    Args:
        response: Raw GM response with [SEARCHED:], [ACCUSATION:], etc. markers
        state: Optional game state for clue validation
    
    Returns:
        GameMasterResponse with extracted data
    """
    narrative = response
    action = None
    scene_brief = None
    speaker = None
    accusation_result = None
    
    # Extract SEARCHED marker
    searched_match = re.search(r'\[SEARCHED:([^\]]+)\]', response)
    if searched_match:
        location = searched_match.group(1).strip()
        action = GameAction(
            action_type="search_location",
            target=location
        )
        narrative = re.sub(r'\[SEARCHED:[^\]]+\]', '', narrative)
    
    # Extract ACCUSATION marker
    accusation_match = re.search(r'\[ACCUSATION:([^\]]+)\]', response)
    if accusation_match:
        suspect = accusation_match.group(1).strip()
        action = GameAction(
            action_type="make_accusation",
            target=suspect
        )
        narrative = re.sub(r'\[ACCUSATION:[^\]]+\]', '', narrative)
        
        # Check if accusation was correct
        if state and state.mystery:
            murderer = state.mystery.murderer.lower()
            accusation_result = (murderer in suspect.lower() or suspect.lower() in murderer)
    
    # Extract CLUE_FOUND markers
    clue_matches = re.findall(r'\[CLUE_FOUND:([^\]]+)\]', response)
    if clue_matches:
        if not action:
            action = GameAction(action_type="reveal_clue", clue_ids_revealed=clue_matches)
        else:
            action.clue_ids_revealed = clue_matches
        narrative = re.sub(r'\[CLUE_FOUND:[^\]]+\]', '', narrative)
    
    # Extract SCENE_BRIEF marker
    scene_match = re.search(r'\[SCENE_BRIEF(\{[^}]+\})\]', response, re.DOTALL)
    if scene_match:
        try:
            scene_data = json.loads(scene_match.group(1))
            scene_brief = SceneBrief(
                location=scene_data.get("location", ""),
                visual_description=scene_data.get("visual_description", ""),
                camera_angle=scene_data.get("camera_angle", "medium shot"),
                mood=scene_data.get("mood", "mysterious"),
                focus_element=scene_data.get("focus_element")
            )
        except (json.JSONDecodeError, ValidationError) as e:
            logger.warning(f"Failed to parse SCENE_BRIEF: {e}")
        narrative = re.sub(r'\[SCENE_BRIEF\{[^}]+\}\]', '', narrative, flags=re.DOTALL)
    
    # Extract AUDIO marker (for speaker detection)
    audio_match = re.search(r'\[AUDIO:([^\]]+)\]', response)
    if audio_match:
        # Audio path doesn't tell us the speaker directly
        # but indicates this is likely a suspect response
        # Keep the marker in narrative for audio processing
        pass
    
    # Clean up narrative
    narrative = re.sub(r'  +', ' ', narrative)
    narrative = narrative.strip()
    
    return GameMasterResponse(
        narrative=narrative,
        speaker=speaker,
        action=action,
        scene_brief=scene_brief,
        accusation_result=accusation_result
    )


# =============================================================================
# STRUCTURED LLM (For direct structured responses)
# =============================================================================

def get_structured_llm(model: str = None):
    """Get an LLM configured for structured GameMasterResponse output.
    
    This uses LangChain's with_structured_output() to get responses
    that match the GameMasterResponse schema directly, eliminating
    the need for regex parsing entirely.
    
    Usage:
        llm = get_structured_llm()
        response: GameMasterResponse = llm.invoke(messages)
    """
    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        raise ImportError("langchain-openai required. Run: pip install langchain-openai")
    
    model_name = model or os.getenv("GAME_MASTER_MODEL", "gpt-4o-mini")
    
    llm = ChatOpenAI(
        model=model_name,
        max_tokens=800,
        api_key=os.getenv("OPENAI_API_KEY")
    )
    
    return llm.with_structured_output(GameMasterResponse)


# =============================================================================
# MIGRATION UTILITIES
# =============================================================================

def convert_legacy_to_structured(
    response: str,
    speaker: Optional[str] = None,
    state: Optional[GameState] = None
) -> Tuple[GameMasterResponse, str]:
    """Convert a legacy marker-based response to structured format.
    
    Returns both the structured response and the cleaned narrative.
    This is useful during the migration period.
    
    Args:
        response: Raw response with markers
        speaker: Known speaker (from tool call detection)
        state: Game state for validation
    
    Returns:
        Tuple of (GameMasterResponse, cleaned_narrative)
    """
    structured = parse_response_to_structured(response, state)
    
    # Override speaker if known from tool calls
    if speaker:
        structured.speaker = speaker
    
    return structured, structured.narrative


def is_structured_response(response: str) -> bool:
    """Check if a response is already in structured JSON format.
    
    Useful for detecting tool outputs that are already structured.
    """
    if not response.strip().startswith('{'):
        return False
    
    try:
        data = json.loads(response.strip())
        # Check for structured output indicators
        return (
            isinstance(data, dict) and
            ("narrative" in data or "tool_name" in data or "visual_description" in data)
        )
    except json.JSONDecodeError:
        return False


