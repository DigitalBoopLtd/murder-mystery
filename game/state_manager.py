"""Shared game state and helper utilities for the murder mystery game."""

from __future__ import annotations

import logging
from typing import Dict, Optional

from game.state import GameState

logger = logging.getLogger(__name__)

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


