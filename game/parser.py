"""Parse game actions from AI responses using structured markers.

The Game Master agent includes markers in its responses to indicate game events:
- [SEARCHED:location name] - when a location is searched
- [ACCUSATION:suspect name] - when an accusation is made
- [CLUE_FOUND:clue_id] - when a clue is revealed

For suspect interrogations, we detect tool calls to `interrogate_suspect`.
"""

import logging
import re
from typing import Optional, List, Tuple

from game.state import GameState

logger = logging.getLogger(__name__)


def parse_game_actions(user_message: str, response: str, state: GameState) -> dict:
    """Parse AI response markers to update game state.

    The agent intelligently handles routing and includes markers in responses.
    This parser extracts those markers to update game state.

    Args:
        user_message: The player's message (used for context)
        response: The AI's response with markers
        state: Current game state

    Returns:
        Dict with actions detected: {
            'suspect_talked_to': str or None,
            'location_searched': str or None,
            'clues_found': list of clue descriptions,
            'accusation_made': str or None,
            'accusation_correct': bool or None
        }
    """
    if not state.mystery:
        return {}

    actions = {
        "suspect_talked_to": None,
        "location_searched": None,
        "clues_found": [],
        "accusation_made": None,
        "accusation_correct": None,
    }

    # === DETECT SUSPECT INTERROGATION ===
    # This is handled by detecting tool calls to interrogate_suspect
    # The agent extracts suspect name from tool calls in services/agent.py
    # We also check for [AUDIO:path] prefix which indicates suspect response
    audio_match = re.search(r'\[AUDIO:[^\]]+\]', response)
    if audio_match:
        # Suspect interrogation happened - name extraction happens in agent.py
        # Just detect that it occurred for logging
        logger.info("🎭 Detected interrogation response (has audio marker)")

    # === DETECT LOCATION SEARCH (via AI marker) ===
    searched_match = re.search(r'\[SEARCHED:([^\]]+)\]', response)
    if searched_match:
        location = searched_match.group(1).strip()
        # Normalize to exact clue location if possible
        normalized = _normalize_location(location, state)
        state.add_searched_location(normalized)
        actions["location_searched"] = normalized
        logger.info(f"📍 AI searched location: {normalized}")

    # === DETECT CLUE DISCOVERIES (via AI marker) ===
    clue_matches = re.findall(r'\[CLUE_FOUND:([^\]]+)\]', response)
    for clue_id in clue_matches:
        clue_id = clue_id.strip()
        # Find the clue description
        for clue in state.mystery.clues:
            if clue.id.lower() == clue_id.lower():
                state.add_clue(clue.id, clue.description)
                actions["clues_found"].append(clue.description)
                logger.info(f"🔍 AI revealed clue: {clue.id}")
                break

    # === DETECT ACCUSATIONS (via AI marker) ===
    accusation_match = re.search(r'\[ACCUSATION:([^\]]+)\]', response)
    if accusation_match:
        accused_name = accusation_match.group(1).strip()
        actions["accusation_made"] = accused_name
        
        # Check if accusation is correct
        if state.mystery.murderer.lower() in accused_name.lower() or \
           accused_name.lower() in state.mystery.murderer.lower():
            actions["accusation_correct"] = True
            state.won = True
            state.game_over = True
            logger.info(f"✅ Correct accusation: {accused_name}")
        else:
            actions["accusation_correct"] = False
            state.wrong_accusations += 1
            if state.wrong_accusations >= 3:
                state.game_over = True
            logger.info(f"❌ Wrong accusation: {accused_name} (attempt {state.wrong_accusations}/3)")

    # === FALLBACK: Detect from context if no markers ===
    # Only if AI forgot to include markers, try basic detection
    if not actions["location_searched"] and not audio_match:
        location = _detect_location_from_context(user_message, response, state)
        if location:
            state.add_searched_location(location)
            actions["location_searched"] = location
            logger.info(f"📍 Detected search from context: {location}")
            
            # Also try to detect clues mentioned in response
            found_clues = _find_clues_in_response(response, state, location)
            for clue_id, clue_desc in found_clues:
                state.add_clue(clue_id, clue_desc)
                actions["clues_found"].append(clue_desc)
                logger.info(f"🔍 Detected clue from context: {clue_id}")

    return actions


def _normalize_location(location: str, state: GameState) -> str:
    """Normalize location name to match exact clue location."""
    if not state.mystery:
        return location
    
    location_lower = location.lower()
    for clue in state.mystery.clues:
        clue_loc_lower = clue.location.lower()
        if (clue_loc_lower == location_lower or 
            location_lower in clue_loc_lower or 
            clue_loc_lower in location_lower):
            return clue.location
    return location


def _detect_location_from_context(user_message: str, response: str, state: GameState) -> Optional[str]:
    """Fallback: detect location search from context when AI forgets markers."""
    msg_lower = user_message.lower()
    resp_lower = response.lower()
    
    # Quick check for search-related words in user message
    search_words = ["search", "examine", "investigate", "check", "look", "inspect", "explore"]
    if not any(word in msg_lower for word in search_words):
        return None
    
    # Check if any clue location is mentioned in user message or response
    for clue in state.mystery.clues:
        loc_lower = clue.location.lower()
        # Check user message
        if loc_lower in msg_lower:
            return clue.location
        # Check key words from location
        loc_words = [w for w in loc_lower.split() if len(w) > 3 and w not in ["the", "and"]]
        for word in loc_words:
            if word in msg_lower:
                return clue.location
    
    return None


def _find_clues_in_response(response: str, state: GameState, location: str) -> List[Tuple[str, str]]:
    """Find clues mentioned in response for a searched location."""
    found = []
    resp_lower = response.lower()
    loc_lower = location.lower()
    
    for clue in state.mystery.clues:
        if clue.id in state.clue_ids_found:
            continue
        if clue.location.lower() != loc_lower:
            continue
        # Check if clue description words appear in response
        desc_words = [w.lower() for w in clue.description.split() if len(w) > 4]
        matches = sum(1 for w in desc_words if w in resp_lower)
        if matches >= 2:  # At least 2 significant words match
            found.append((clue.id, clue.description))
    
    return found


def clean_response_markers(response: str) -> str:
    """Remove game markers from response for display to player.
    
    Removes: [SEARCHED:...], [ACCUSATION:...], [CLUE_FOUND:...]
    Keeps: [AUDIO:...] (needed for audio playback)
    """
    cleaned = response
    cleaned = re.sub(r'\[SEARCHED:[^\]]+\]', '', cleaned)
    cleaned = re.sub(r'\[ACCUSATION:[^\]]+\]', '', cleaned)
    cleaned = re.sub(r'\[CLUE_FOUND:[^\]]+\]', '', cleaned)
    # Clean up any double spaces or leading/trailing whitespace
    cleaned = re.sub(r'  +', ' ', cleaned)
    return cleaned.strip()


def find_suspect_in_message(message_lower: str, state: GameState) -> Optional[str]:
    """Find a suspect name in the message (simple version).
    
    Used for detecting suspect mentions in user messages.
    The agent handles complex disambiguation.
    """
    if not state.mystery:
        return None

    for suspect in state.mystery.suspects:
        name_lower = suspect.name.lower()
        # Check full name
        if name_lower in message_lower:
            return suspect.name
        # Check first/last name parts
        name_parts = name_lower.split()
        for part in name_parts:
            if len(part) > 2 and part in message_lower:
                return suspect.name
        # Check role (butler, heiress, etc.)
        role_lower = suspect.role.lower()
        if role_lower in message_lower:
            return suspect.name

    return None
