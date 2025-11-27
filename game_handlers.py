"""Game logic handlers for starting games and processing player actions."""

import os
import re
import logging
import time
from typing import Optional, Tuple, List, Dict

from game_state import GameState
from image_service import (
    generate_portrait_on_demand,
    get_image_service,
)
from mystery_generator import generate_mystery, prepare_game_prompt, assign_voice_to_suspect
from agent import create_game_master_agent, process_message
from game_parser import parse_game_actions
from tts_service import text_to_speech

logger = logging.getLogger(__name__)

# These will be set by app.py
game_states = {}
mystery_images = {}
GAME_MASTER_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"


def init_game_handlers(states_dict, images_dict, game_master_voice_id: str):
    """Initialize game handlers with shared state."""
    global game_states, mystery_images, GAME_MASTER_VOICE_ID
    game_states = states_dict
    mystery_images = images_dict
    GAME_MASTER_VOICE_ID = game_master_voice_id


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


def start_new_game(session_id: str):
    """Start a new mystery game with parallelized image generation."""
    state = get_or_create_state(session_id)
    state.reset_game()

    # Generate mystery
    logger.info("Generating new mystery...")
    t0 = time.perf_counter()
    mystery = generate_mystery()
    t1 = time.perf_counter()
    logger.info(f"[PERF] Mystery generation took {t1 - t0:.2f}s")
    state.mystery = mystery
    state.system_prompt = prepare_game_prompt(mystery)

    # Initialize with agent and narration (images generated on-demand)
    logger.info("Starting game initialization (images will be generated on-demand)...")

    # Create or reuse shared agent and get narration immediately (no waiting for images)
    if not hasattr(start_new_game, "agent"):
        start_new_game.agent = create_game_master_agent()

    t2 = time.perf_counter()
    response, speaker = process_message(
        start_new_game.agent,
        "The player has just arrived. Welcome them to the mystery with atmosphere.",
        state.system_prompt,
        session_id,
        thread_id=session_id,
    )
    t3 = time.perf_counter()
    logger.info(f"[PERF] First Game Master response took {t3 - t2:.2f}s")

    # Initialize empty images dict - images will be generated on-demand
    mystery_images[session_id] = {}
    
    # Optionally generate title card in background (non-blocking)
    # For now, we'll generate it on-demand when first needed

    # Generate audio (needs the response text)
    logger.info(f"[GAME] Calling TTS for welcome message ({len(response)} chars)")
    t4 = time.perf_counter()
    audio_path, alignment_data = text_to_speech(
        response, GAME_MASTER_VOICE_ID, speaker_name="Game Master"
    )
    t5 = time.perf_counter()
    logger.info(f"[PERF] Welcome TTS (with timestamps) took {t5 - t4:.2f}s")

    # Verify audio was generated
    if audio_path:
        if os.path.exists(audio_path):
            file_size = os.path.getsize(audio_path)
            logger.info(
                f"[GAME] ✅ Audio generated: {audio_path} ({file_size} bytes)"
            )
        else:
            logger.error(
                f"[GAME] ❌ Audio path returned but file doesn't exist: {audio_path}"
            )
    else:
        logger.error("[GAME] ❌ No audio path returned from TTS!")

    if alignment_data:
        logger.info(f"[GAME] ✅ Got {len(alignment_data)} word timestamps")
    else:
        logger.warning("[GAME] ⚠️ No alignment data (captions will use estimation)")

    # Store in messages
    state.messages.append(
        {"role": "assistant", "content": response, "speaker": "Game Master"}
    )

    return state, response, audio_path, "Game Master", alignment_data


def process_player_action(
    action_type: str, target: str, custom_message: str, session_id: str
) -> Tuple[str, Optional[str], str, GameState, Optional[List[Dict]]]:
    """Process a player action and return response.

    Args:
        action_type: "talk", "search", "accuse", or "custom"
        target: Suspect name, location, or None
        custom_message: Free-form message if action_type is "custom"
        session_id: Session identifier

    Returns:
        Tuple of (response_text, audio_path, speaker_name, state)
    """
    state = get_or_create_state(session_id)

    if not state.mystery:
        return "Please start a new game first.", None, "Game Master", state

    # Build the message based on action type
    if action_type == "talk" and target:
        message = f"I want to talk to {target}. Hello, {target}."
    elif action_type == "search" and target:
        message = f"I want to search {target}."
    elif action_type == "accuse" and target:
        message = f"I accuse {target} of the murder!"
    elif action_type == "custom" and custom_message:
        message = custom_message
    else:
        return "I didn't understand that action.", None, "Game Master", state

    # Store player message
    state.messages.append({"role": "user", "content": message, "speaker": "You"})

    # If talking to a suspect, assign voice on-demand before processing
    # This ensures the system prompt includes the voice_id for the tool
    if action_type == "talk" and target:
        suspect = None
        for s in state.mystery.suspects:
            if s.name == target:
                suspect = s
                break
        
        if suspect and not suspect.voice_id:
            logger.info(f"Assigning voice on-demand for suspect: {target}")
            # Get list of already-used voice IDs to avoid duplicates
            used_voice_ids = [
                s.voice_id for s in state.mystery.suspects 
                if s.voice_id and s.name != target
            ]
            assign_voice_to_suspect(suspect, used_voice_ids)

    # Get or create agent
    if not hasattr(process_player_action, "agent"):
        process_player_action.agent = create_game_master_agent()

    # Update system prompt (will include newly assigned voice_id if any)
    state.system_prompt = state.get_continue_prompt()

    # Process with agent
    response, speaker = process_message(
        process_player_action.agent,
        message,
        state.system_prompt,
        session_id,
        thread_id=session_id,
    )

    # Parse game actions to detect location searches, etc.
    actions = parse_game_actions(message, response, state)

    # Extract audio path marker if present (from interrogate_suspect tool)
    # Format: [AUDIO:/path/to/file.mp3]text response
    audio_path_from_tool = None
    clean_response = response
    audio_marker_pattern = r"\[AUDIO:([^\]]+)\]"
    match = re.search(audio_marker_pattern, response)
    if match:
        audio_path_from_tool = match.group(1)
        # Remove the audio marker from the text
        clean_response = re.sub(audio_marker_pattern, "", response).strip()
        logger.info(f"Extracted audio path from tool: {audio_path_from_tool}")

    # Generate portrait and assign voice on-demand if a suspect was talked to
    # (This handles cases where speaker is detected from custom messages)
    if speaker and speaker != "Game Master":
        session_images = mystery_images.get(session_id, {})
        
        # Find the suspect in the mystery
        suspect = None
        for s in state.mystery.suspects:
            if s.name == speaker:
                suspect = s
                break
        
        if suspect:
            # Assign voice on-demand if not already assigned
            # (May have been assigned earlier for "talk" action, but check here too for custom messages)
            if not suspect.voice_id:
                logger.info(f"Assigning voice on-demand for suspect: {speaker}")
                # Get list of already-used voice IDs to avoid duplicates
                used_voice_ids = [
                    s.voice_id for s in state.mystery.suspects 
                    if s.voice_id and s.name != speaker
                ]
                assign_voice_to_suspect(suspect, used_voice_ids)
                # Note: System prompt was already generated, but voice_id will be available for next interaction
            
            # Check if we need to generate this suspect's portrait
            if speaker not in session_images:
                logger.info(f"Generating portrait on-demand for suspect: {speaker}")
                portrait_path = generate_portrait_on_demand(
                    suspect, 
                    state.mystery.setting if state.mystery else ""
                )
                if portrait_path:
                    # Store in mystery_images dict for this session
                    if session_id not in mystery_images:
                        mystery_images[session_id] = {}
                    mystery_images[session_id][speaker] = portrait_path
                    logger.info(f"Generated and stored portrait for {speaker}: {portrait_path}")
                else:
                    logger.warning(f"Failed to generate portrait for {speaker}")
        else:
            logger.warning(f"Suspect {speaker} not found in mystery for portrait/voice generation")

    # Generate scene image on-demand if a location was searched
    if actions.get("location_searched"):
        location = actions["location_searched"]
        session_images = mystery_images.get(session_id, {})
        
        # Only generate if we don't already have this scene
        if location not in session_images:
            logger.info(f"Generating scene image for location: {location}")
            service = get_image_service()
            if service and service.is_available:
                # Use the response text as context for scene generation
                # Clean the response to extract relevant descriptive content
                context_text = clean_response[:500]  # Use first 500 chars as context
                scene_path = service.generate_scene(
                    location_name=location,
                    setting_description=state.mystery.setting if state.mystery else "",
                    mood="mysterious",
                    context=context_text,
                )
                if scene_path:
                    # Store in mystery_images dict for this session
                    if session_id not in mystery_images:
                        mystery_images[session_id] = {}
                    mystery_images[session_id][location] = scene_path
                    logger.info(
                        f"Generated and stored scene for {location}: {scene_path}"
                    )
                else:
                    logger.warning(f"Failed to generate scene for {location}")
            else:
                logger.warning("Image service not available for scene generation")

    # Determine voice
    voice_id = None
    if speaker and speaker != "Game Master":
        voice_id = get_suspect_voice_id(speaker, state)
    voice_id = voice_id or GAME_MASTER_VOICE_ID

    # Generate audio
    tts_text = clean_response.replace("**", "").replace("*", "")
    speaker = speaker or "Game Master"

    alignment_data = None
    if audio_path_from_tool:
        # Try to get alignment data from tool-generated audio
        audio_path = audio_path_from_tool
        from game_tools import get_audio_alignment_data
        alignment_data = get_audio_alignment_data(audio_path)
        if alignment_data:
            logger.info(f"[GAME] Using audio from tool with {len(alignment_data)} word timestamps: {audio_path}")
        else:
            logger.info(f"[GAME] Using audio from tool (no alignment data): {audio_path}")
    else:
        logger.info(f"[GAME] Calling TTS for response ({len(tts_text)} chars)")
        audio_path, alignment_data = text_to_speech(
            tts_text, voice_id, speaker_name=speaker
        )

        # Verify audio was generated
        if audio_path:

            if os.path.exists(audio_path):
                file_size = os.path.getsize(audio_path)
                logger.info(
                    f"[GAME] ✅ Audio generated: {audio_path} ({file_size} bytes)"
                )
            else:
                logger.error(
                    f"[GAME] ❌ Audio path returned but file doesn't exist: {audio_path}"
                )
        else:
            logger.error("[GAME] ❌ No audio path returned from TTS!")

        if alignment_data:
            logger.info(f"[GAME] ✅ Got {len(alignment_data)} word timestamps")
        else:
            logger.warning("[GAME] ⚠️ No alignment data")

    # Store response (without audio marker)
    state.messages.append(
        {
            "role": "assistant",
            "content": clean_response,
            "speaker": speaker or "Game Master",
        }
    )

    return clean_response, audio_path, speaker or "Game Master", state, alignment_data
