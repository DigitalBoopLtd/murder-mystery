"""Shared game state and helper utilities for the murder mystery game."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from game.state import GameState

logger = logging.getLogger(__name__)


# ============================================================================
# Structured Tool Output Store
# ============================================================================
# Tools store their structured outputs here instead of embedding markers in text.
# Handlers read from here instead of regex parsing.


@dataclass
class SceneBriefOutput:
    """Structured output from describe_scene_for_image tool."""
    location_name: str
    clue_id: Optional[str] = None
    clue_focus: str = ""
    camera_angle: str = "medium shot"
    lighting_mood: str = "dramatic"
    background_hint: str = ""
    prompt_hint: str = ""


@dataclass 
class InterrogationOutput:
    """Structured output from interrogate_suspect tool."""
    suspect_name: str
    response_text: str
    emotional_state: Optional[str] = None


@dataclass
class AccusationOutput:
    """Structured output from make_accusation tool."""
    suspect_name: str
    is_correct: bool
    narrative: str
    has_sufficient_evidence: bool = False  # True if player found enough clues
    clues_found_count: int = 0  # Number of clues found when accusation was made


@dataclass
class ToolOutputStore:
    """Store for structured tool outputs. Replaces regex marker parsing."""
    
    # Most recent outputs from each tool type
    scene_brief: Optional[SceneBriefOutput] = None
    interrogation: Optional[InterrogationOutput] = None
    accusation: Optional[AccusationOutput] = None
    
    # Action flags (replaces [SEARCHED:], [CLUE_FOUND:], etc.)
    location_searched: Optional[str] = None
    clue_found: Optional[str] = None
    audio_path: Optional[str] = None
    audio_alignment_data: Optional[List[Dict]] = None  # Word timestamps for subtitles
    
    def clear(self):
        """Clear all stored outputs for next turn."""
        self.scene_brief = None
        self.interrogation = None
        self.accusation = None
        self.location_searched = None
        self.clue_found = None
        self.audio_path = None
        self.audio_alignment_data = None
    
    def to_actions_dict(self) -> Dict[str, Any]:
        """Convert to actions dict for backward compatibility."""
        actions = {}
        if self.location_searched:
            actions["location_searched"] = self.location_searched
        if self.clue_found:
            actions["clue_found"] = self.clue_found
        if self.accusation:
            actions["accusation"] = self.accusation.suspect_name
            actions["accusation_correct"] = self.accusation.is_correct
        return actions


# Per-session tool output stores
_tool_outputs: Dict[str, ToolOutputStore] = {}


def get_tool_output_store(session_id: Optional[str] = None) -> ToolOutputStore:
    """Get the tool output store for a session."""
    sid = session_id or _current_session_id or "_default"
    if sid not in _tool_outputs:
        _tool_outputs[sid] = ToolOutputStore()
    return _tool_outputs[sid]


def clear_tool_outputs(session_id: Optional[str] = None):
    """Clear tool outputs for a new turn."""
    store = get_tool_output_store(session_id)
    store.clear()

# These will be set by app.py via init_game_handlers()
game_states: Dict[str, GameState] = {}
mystery_images: Dict[str, Dict[str, str]] = {}
GAME_MASTER_VOICE_ID: str = "JBFqnCBsd6RMkjVDRZzb"


def init_game_handlers(states_dict, images_dict, game_master_voice_id: str):
    """Initialize game handlers with shared state.

    This mirrors the previous behavior in game_handlers.py so that app.py
    can continue to call init_game_handlers(game_states, mystery_images, GAME_MASTER_VOICE_ID)
    without any changes.

    Note: We update dicts in-place rather than reassigning so that other modules
    that imported the module-level dicts will see the changes.
    """
    global GAME_MASTER_VOICE_ID

    # Update dicts in-place so all importers see the same data
    game_states.clear()
    game_states.update(states_dict)

    mystery_images.clear()
    mystery_images.update(images_dict)

    GAME_MASTER_VOICE_ID = game_master_voice_id


def _is_invalid_voice_id(voice_id: Optional[str]) -> bool:
    """Heuristic check for placeholder/invalid voice IDs.

    Some generated mysteries may include fake ElevenLabs IDs like
    'elevenlabs-voice-id-john'. Treat these as invalid so we can
    assign a real voice instead of triggering API errors.
    """
    if not voice_id:
        return True
    if isinstance(voice_id, str) and voice_id.startswith("elevenlabs-voice-id-"):
        return True
    return False


def _get_scene_mood_for_state(state: GameState) -> str:
    """Derive a scene mood string from the current config tone.

    This is used to lightly steer scene images (e.g. more playful vs. brooding)
    without changing the underlying mystery content.
    """
    tone = getattr(getattr(state, "config", None), "tone", None)
    if tone == "Cheeky Adult Comedy":
        return "playful, slightly silly, light-hearted"
    if tone == "Flirty Noir":
        return "moody, romantic, sultry but non-explicit"
    if tone == "Gothic Romance":
        return "brooding, romantic, gothic"
    return "mysterious"


# Thread-local storage for current session context
_current_session_id: Optional[str] = None


def set_current_session(session_id: str):
    """Set the current session ID for tool context."""
    global _current_session_id
    _current_session_id = session_id


def get_game_state() -> Optional[GameState]:
    """Get the current game state for tool access.
    
    Returns the state for the current session, or the most recent state if none set.
    Tools use this to securely access game data without exposing it in prompts.
    """
    # First try the explicitly set current session
    if _current_session_id and _current_session_id in game_states:
        return game_states[_current_session_id]
    
    # Fall back to most recent state (usually just one active game)
    if game_states:
        # Return the most recently accessed state
        return list(game_states.values())[-1]
    
    return None


def get_or_create_state(session_id: str) -> GameState:
    """Get or create game state for session."""
    if session_id not in game_states:
        game_states[session_id] = GameState()
    return game_states[session_id]


def get_suspect_voice_id(suspect_name: str, state: GameState) -> Optional[str]:
    """Get voice ID for a suspect."""
    if not state.mystery:
        return None
    for suspect in state.mystery.suspects:
        if suspect.name == suspect_name:
            return getattr(suspect, "voice_id", None)
    return None


def normalize_location_name(location: str, state: GameState) -> str:
    """Normalize location name to match exact clue location name.
    
    This ensures consistent storage/retrieval of location images even if
    the parser returns a slightly different variation of the location name.
    
    Args:
        location: Location name from parser/player message
        state: Game state with mystery data
        
    Returns:
        Normalized location name (exact match from clue if found, otherwise original)
    """
    if not state.mystery:
        return location
    
    location_lower = location.lower()
    for clue in state.mystery.clues:
        clue_location_lower = clue.location.lower()
        # Exact match or location is contained in clue location (or vice versa)
        if (clue_location_lower == location_lower or 
            location_lower in clue_location_lower or 
            clue_location_lower in location_lower):
            # Return exact clue location name for consistency
            if clue.location != location:
                logger.info(
                    "Normalizing location name: '%s' -> '%s'",
                    location,
                    clue.location,
                )
            return clue.location
    
    # No match found, return original
    return location


