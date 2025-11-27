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
from mystery_generator import (
    generate_mystery,
    generate_mystery_premise,
    prepare_game_prompt,
    assign_voice_to_suspect,
)
import threading
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


def start_new_game_staged(session_id: str):
    """Generator that yields progress stages during game initialization.
    
    Fast path: premise → welcome → TTS (~6s total)
    Background: full mystery generation (~15s, non-blocking)
    
    Yields tuples of (stage_name, stage_progress, stage_data) where:
    - stage_name: str describing current stage
    - stage_progress: float 0.0-1.0
    - stage_data: dict with any data from that stage (or None)
    
    Final yield has stage_name="complete" with all game data.
    """
    state = get_or_create_state(session_id)
    state.reset_game()

    # ========== STAGE 1: PREMISE (20%) ==========
    yield ("premise", 0.2, None)
    
    logger.info("Generating mystery premise...")
    t0 = time.perf_counter()
    premise = generate_mystery_premise()
    t1 = time.perf_counter()
    logger.info("[PERF] Mystery premise generation took %.2fs", t1 - t0)

    # Store premise on state
    state.premise_setting = premise.setting
    state.premise_victim_name = premise.victim_name
    state.premise_victim_background = premise.victim_background

    # Build a lightweight system prompt for the intro, based only on the premise.
    state.system_prompt = f"""You are the Game Master for a murder mystery game.

## THE CASE (PREMISE ONLY)
{premise.setting}

## VICTIM
{premise.victim_name}: {premise.victim_background}

The full case file with suspects and clues is still being compiled off-screen.

## RESPONSE LENGTH
Keep ALL responses SHORT for voice narration (10-20 seconds of speech).
- Welcome: 2-3 atmospheric sentences (max 40-50 words total)
- Then ask what the player would like to do first.
- NEVER write more than 50 words in a single response.

Do NOT mention that the case file is still generating or anything about the
system or background tasks. Stay purely in-world."""

    # ========== START BACKGROUND MYSTERY GENERATION ==========
    def _background_generate_full_case(sess_id: str, premise_obj):
        bg_state = get_or_create_state(sess_id)
        try:
            logger.info("[BG] Starting full mystery generation in background...")
            t_full_0 = time.perf_counter()
            full_mystery = generate_mystery(premise=premise_obj)
            t_full_1 = time.perf_counter()
            logger.info(
                "[PERF] Full mystery generation (background) took %.2fs",
                t_full_1 - t_full_0,
            )
            bg_state.mystery = full_mystery
            bg_state.system_prompt = prepare_game_prompt(full_mystery)
            bg_state.mystery_ready = True
            logger.info("[BG] Full mystery is ready for session %s", sess_id)
        except Exception as e:
            logger.error("[BG] Error generating full mystery in background: %s", e)

    threading.Thread(
        target=_background_generate_full_case,
        args=(session_id, premise),
        daemon=True,
    ).start()

    # ========== STAGE 2: WELCOME MESSAGE (50%) ==========
    yield ("welcome", 0.5, {"premise": premise})
    
    logger.info("Generating welcome message...")
    
    # Create or reuse shared agent
    if not hasattr(start_new_game_staged, "agent"):
        start_new_game_staged.agent = create_game_master_agent()

    t2 = time.perf_counter()
    response, _speaker = process_message(
        start_new_game_staged.agent,
        (
            "The player has just arrived. Welcome them briefly "
            "(2-3 sentences, max 50 words) with atmosphere, "
            "then ask what they'd like to do."
        ),
        state.system_prompt,
        session_id,
        thread_id=session_id,
    )
    t3 = time.perf_counter()
    logger.info("[PERF] First Game Master response took %.2fs", t3 - t2)

    # Initialize empty images dict
    mystery_images[session_id] = {}

    # Store in messages
    state.messages.append(
        {"role": "assistant", "content": response, "speaker": "Game Master"}
    )

    # ========== STAGE 3: TTS (80%) ==========
    yield ("tts", 0.8, {"response": response})
    
    logger.info("[GAME] Calling TTS for welcome message (%d chars)", len(response))
    t4 = time.perf_counter()
    audio_path, alignment_data = text_to_speech(
        response, GAME_MASTER_VOICE_ID, speaker_name="Game Master"
    )
    t5 = time.perf_counter()
    logger.info("[PERF] Welcome TTS (with timestamps) took %.2fs", t5 - t4)

    # Verify audio was generated
    if audio_path:
        if os.path.exists(audio_path):
            file_size = os.path.getsize(audio_path)
            logger.info(
                "[GAME] ✅ Audio generated: %s (%d bytes)", audio_path, file_size
            )
        else:
            logger.error(
                "[GAME] ❌ Audio path returned but file doesn't exist: %s", audio_path
            )
    else:
        logger.error("[GAME] ❌ No audio path returned from TTS!")

    if alignment_data:
        logger.info("[GAME] ✅ Got %d word timestamps", len(alignment_data))
    else:
        logger.warning("[GAME] ⚠️ No alignment data (captions will use estimation)")

    # ========== STAGE 4: COMPLETE (100%) ==========
    yield ("complete", 1.0, {
        "state": state,
        "response": response,
        "audio_path": audio_path,
        "speaker": "Game Master",
        "alignment_data": alignment_data,
    })


def run_action_logic(
    action_type: str, target: str, custom_message: str, session_id: str
) -> Tuple[str, str, GameState, Dict, Optional[str]]:
    """Process player action logic WITHOUT generating audio/images (fast path).

    This is the core logic that runs the LLM agent and parses actions,
    but does NOT block on TTS or image generation.

    Args:
        action_type: "talk", "search", "accuse", or "custom"
        target: Suspect name, location, or None
        custom_message: Free-form message if action_type is "custom"
        session_id: Session identifier

    Returns:
        Tuple of (clean_response, speaker, state, actions_dict, audio_path_from_tool)
        - clean_response: The text response (with audio markers stripped)
        - speaker: Speaker name (suspect name or "Game Master")
        - state: Updated game state
        - actions_dict: Parsed actions (location_searched, etc.)
        - audio_path_from_tool: Pre-generated audio path if tool created it, else None
    """
    state = get_or_create_state(session_id)

    # If the full mystery is not ready yet, keep the player in the intro
    # phase. This prevents interrogations/searches before the case file
    # has been fully generated.
    if not getattr(state, "mystery_ready", False):
        return (
            "Your full case file is still being prepared. "
            "Give me just a moment, then try again.",
            "Game Master",
            state,
            {},
            None,
        )

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
        return "I didn't understand that action.", "Game Master", state, {}, None

    # Store player message
    state.messages.append({"role": "user", "content": message, "speaker": "You"})

    # Assign voice on-demand before processing if talking to a suspect
    # This ensures the system prompt includes the voice_id for the tool
    suspect_to_assign = None
    
    if action_type == "talk" and target:
        # Direct talk action - target is the suspect name
        for s in state.mystery.suspects:
            if s.name == target:
                suspect_to_assign = s
                break
    elif action_type == "custom" and custom_message:
        # Custom message - first try heuristic suspect matching (fast, offline)
        message_lower = custom_message.lower()
        message_words = set(message_lower.split())

        for s in state.mystery.suspects:
            name_parts = s.name.lower().split()

            # Check if full name is in message
            if s.name.lower() in message_lower:
                suspect_to_assign = s
                logger.info("Detected suspect mention (full name): %s", s.name)
                break

            # Check if 2+ consecutive name parts appear
            for i in range(len(name_parts) - 1):
                partial_name = f"{name_parts[i]} {name_parts[i+1]}"
                if partial_name in message_lower:
                    suspect_to_assign = s
                    logger.info("Detected suspect mention (partial name): %s", s.name)
                    break
            if suspect_to_assign:
                break

            # Check if any significant name part (3+ chars) matches a word in the message
            # This handles cases like "Ada" matching "Ada Syntax"
            for part in name_parts:
                if len(part) >= 3:  # Only match meaningful name parts
                    # Check exact word match
                    if part in message_words:
                        suspect_to_assign = s
                        logger.info(
                            "Detected suspect mention (name part '%s'): %s",
                            part,
                            s.name,
                        )
                        break
            if suspect_to_assign:
                break

        # Hybrid fallback: if heuristics failed, ask a small LLM to resolve
        if not suspect_to_assign and state.mystery:
            try:
                from langchain_openai import ChatOpenAI
                from langchain_core.prompts import ChatPromptTemplate

                suspects = state.mystery.suspects
                suspects_summary = "\n".join(
                    f"- {s.name} ({s.role})" for s in suspects
                )

                llm = ChatOpenAI(
                    model=os.getenv("SUSPECT_RESOLVER_MODEL", "gpt-4o-mini"),
                    temperature=0,
                    api_key=os.getenv("OPENAI_API_KEY"),
                )

                prompt = ChatPromptTemplate.from_messages(
                    [
                        (
                            "system",
                            (
                                "You map a player's message to ONE suspect from a list.\n"
                                "You MUST answer with exactly one suspect name from the list, "
                                "or the word NONE if no suspect clearly matches.\n"
                                "Do not add any explanation."
                            ),
                        ),
                        (
                            "human",
                            (
                                "Suspects:\n"
                                "{suspect_list}\n\n"
                                "Player message:\n"
                                "{player_message}\n\n"
                                "Answer with exactly one suspect name from the list above, "
                                "or NONE if you are not sure."
                            ),
                        ),
                    ]
                )

                chain = prompt | llm
                result = chain.invoke(
                    {
                        "suspect_list": suspects_summary,
                        "player_message": custom_message,
                    }
                )
                choice = (result.content or "").strip()
                first_line = choice.splitlines()[0].strip()
                # Strip bullets or quotes if present
                first_line = first_line.lstrip("-• ").strip().strip('"').strip("'")

                if first_line and first_line.upper() != "NONE":
                    for s in suspects:
                        if s.name.lower() == first_line.lower():
                            suspect_to_assign = s
                            logger.info(
                                "AI-resolved suspect mention: %s (from '%s')",
                                s.name,
                                custom_message,
                            )
                            break
                    else:
                        logger.info(
                            "AI suspect resolver returned '%s', which did not match any known suspect",
                            first_line,
                        )
                else:
                    logger.info(
                        "AI suspect resolver chose NONE for message: %s", custom_message
                    )
            except Exception:
                logger.exception(
                    "Error resolving suspect name via AI; falling back to heuristics only"
                )
    
    if suspect_to_assign and not suspect_to_assign.voice_id:
        logger.info("Assigning voice on-demand for suspect: %s", suspect_to_assign.name)
        # Get list of already-used voice IDs to avoid duplicates
        used_voice_ids = [
            s.voice_id
            for s in state.mystery.suspects
            if s.voice_id and s.name != suspect_to_assign.name
        ]
        assign_voice_to_suspect(suspect_to_assign, used_voice_ids)

    # Get or create agent
    if not hasattr(run_action_logic, "agent"):
        run_action_logic.agent = create_game_master_agent()

    # Update system prompt (will include newly assigned voice_id if any)
    state.system_prompt = state.get_continue_prompt()

    # Process with agent
    response, speaker = process_message(
        run_action_logic.agent,
        message,
        state.system_prompt,
        session_id,
        thread_id=session_id,
    )

    # Handle empty or placeholder responses from the LLM
    empty_responses = ["", "Empty", "I'm processing your request", "No content"]
    if not response or response.strip() in empty_responses:
        logger.warning(
            "[GAME] LLM returned empty/placeholder response, generating fallback"
        )
        # Generate a contextual fallback based on what the player asked
        message_lower = message.lower()
        if "search" in message_lower:
            response = (
                "You carefully examine the area, taking in every detail. "
                "The atmosphere is thick with tension as you search for clues."
            )
        elif "talk" in message_lower or "speak" in message_lower:
            response = "You approach to have a conversation."
        else:
            response = "You consider your next move carefully."

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
        logger.info("Extracted audio path from tool: %s", audio_path_from_tool)

    # Assign voice on-demand if a suspect was talked to
    # (This handles cases where speaker is detected from custom messages)
    if speaker and speaker != "Game Master":
        # Find the suspect in the mystery
        suspect = None
        for s in state.mystery.suspects:
            if s.name == speaker:
                suspect = s
                break

        if suspect:
            # Assign voice on-demand if not already assigned
            # (May have been assigned earlier for "talk" action)
            if not suspect.voice_id:
                logger.info("Assigning voice on-demand for suspect: %s", speaker)
                # Get list of already-used voice IDs to avoid duplicates
                used_voice_ids = [
                    s.voice_id
                    for s in state.mystery.suspects
                    if s.voice_id and s.name != speaker
                ]
                assign_voice_to_suspect(suspect, used_voice_ids)
        else:
            logger.warning(
                "Suspect %s not found in mystery for voice assignment", speaker
            )

    # Store response (without audio marker)
    state.messages.append(
        {
            "role": "assistant",
            "content": clean_response,
            "speaker": speaker or "Game Master",
        }
    )

    return clean_response, speaker or "Game Master", state, actions, audio_path_from_tool


def _generate_portrait_background(
    suspect_name: str,
    suspect,
    mystery_setting: str,
    session_id: str,
):
    """Generate portrait in background thread."""
    try:
        logger.info("[BG] Generating portrait for %s...", suspect_name)
        portrait_path = generate_portrait_on_demand(suspect, mystery_setting)
        if portrait_path:
            if session_id not in mystery_images:
                mystery_images[session_id] = {}
            mystery_images[session_id][suspect_name] = portrait_path
            logger.info("[BG] ✅ Portrait ready for %s: %s", suspect_name, portrait_path)
        else:
            logger.warning("[BG] ❌ Failed to generate portrait for %s", suspect_name)
    except Exception as e:
        logger.error("[BG] Error generating portrait for %s: %s", suspect_name, e)


def _generate_scene_background(
    location: str,
    mystery_setting: str,
    context_text: str,
    session_id: str,
):
    """Generate scene image in background thread."""
    try:
        logger.info("[BG] Generating scene for %s...", location)
        service = get_image_service()
        if service and service.is_available:
            scene_path = service.generate_scene(
                location_name=location,
                setting_description=mystery_setting,
                mood="mysterious",
                context=context_text,
            )
            if scene_path:
                if session_id not in mystery_images:
                    mystery_images[session_id] = {}
                mystery_images[session_id][location] = scene_path
                logger.info("[BG] ✅ Scene ready for %s: %s", location, scene_path)
            else:
                logger.warning("[BG] ❌ Failed to generate scene for %s", location)
        else:
            logger.warning("[BG] Image service not available for scene generation")
    except Exception as e:
        logger.error("[BG] Error generating scene for %s: %s", location, e)


def generate_turn_media(
    clean_response: str,
    speaker: str,
    state: GameState,
    actions: Dict,
    audio_path_from_tool: Optional[str],
    session_id: str,
    background_images: bool = True,
) -> Tuple[Optional[str], Optional[List[Dict]]]:
    """Generate audio and images for a turn (slow path).

    This handles TTS generation and portrait/scene image generation.
    Called after run_action_logic to generate media assets.

    Args:
        clean_response: The text response to convert to speech
        speaker: Speaker name (suspect name or "Game Master")
        state: Game state
        actions: Parsed actions dict from run_action_logic
        audio_path_from_tool: Pre-generated audio path if tool created it
        session_id: Session identifier
        background_images: If True, generate images in background threads (default)

    Returns:
        Tuple of (audio_path, alignment_data)
    """
    # Start portrait generation (background or foreground)
    if speaker and speaker != "Game Master":
        session_images = mystery_images.get(session_id, {})

        # Find the suspect in the mystery
        suspect = None
        for s in state.mystery.suspects:
            if s.name == speaker:
                suspect = s
                break

        if suspect:
            # Check if we need to generate this suspect's portrait
            if speaker not in session_images:
                mystery_setting = state.mystery.setting if state.mystery else ""
                if background_images:
                    logger.info("[GAME] Starting background portrait generation for: %s", speaker)
                    threading.Thread(
                        target=_generate_portrait_background,
                        args=(speaker, suspect, mystery_setting, session_id),
                        daemon=True,
                    ).start()
                else:
                    # Foreground (blocking)
                    logger.info("Generating portrait on-demand for suspect: %s", speaker)
                    portrait_path = generate_portrait_on_demand(suspect, mystery_setting)
                    if portrait_path:
                        if session_id not in mystery_images:
                            mystery_images[session_id] = {}
                        mystery_images[session_id][speaker] = portrait_path
                        logger.info(
                            "Generated and stored portrait for %s: %s",
                            speaker,
                            portrait_path,
                        )
                    else:
                        logger.warning("Failed to generate portrait for %s", speaker)

    # Start scene image generation (background or foreground)
    if actions.get("location_searched"):
        location = actions["location_searched"]
        session_images = mystery_images.get(session_id, {})

        # Only generate if we don't already have this scene
        if location not in session_images:
            mystery_setting = state.mystery.setting if state.mystery else ""
            context_text = clean_response[:500]  # Use first 500 chars as context
            
            if background_images:
                logger.info("[GAME] Starting background scene generation for: %s", location)
                threading.Thread(
                    target=_generate_scene_background,
                    args=(location, mystery_setting, context_text, session_id),
                    daemon=True,
                ).start()
            else:
                # Foreground (blocking)
                logger.info("Generating scene image for location: %s", location)
                service = get_image_service()
                if service and service.is_available:
                    scene_path = service.generate_scene(
                        location_name=location,
                        setting_description=mystery_setting,
                        mood="mysterious",
                        context=context_text,
                    )
                    if scene_path:
                        if session_id not in mystery_images:
                            mystery_images[session_id] = {}
                        mystery_images[session_id][location] = scene_path
                        logger.info(
                            "Generated and stored scene for %s: %s", location, scene_path
                        )
                    else:
                        logger.warning("Failed to generate scene for %s", location)
                else:
                    logger.warning("Image service not available for scene generation")

    # Determine voice
    voice_id = None
    if speaker and speaker != "Game Master":
        voice_id = get_suspect_voice_id(speaker, state)
    voice_id = voice_id or GAME_MASTER_VOICE_ID

    # Generate audio (always foreground - needed for immediate playback)
    tts_text = clean_response.replace("**", "").replace("*", "")

    alignment_data = None
    if audio_path_from_tool:
        # Try to get alignment data from tool-generated audio
        audio_path = audio_path_from_tool
        from game_tools import get_audio_alignment_data

        alignment_data = get_audio_alignment_data(audio_path)
        if alignment_data:
            logger.info(
                "[GAME] Using audio from tool with %d word timestamps: %s",
                len(alignment_data),
                audio_path,
            )
        else:
            logger.info(
                "[GAME] Using audio from tool (no alignment data): %s", audio_path
            )
    else:
        logger.info("[GAME] Calling TTS for response (%d chars)", len(tts_text))
        audio_path, alignment_data = text_to_speech(
            tts_text, voice_id, speaker_name=speaker
        )

        # Verify audio was generated
        if audio_path:
            if os.path.exists(audio_path):
                file_size = os.path.getsize(audio_path)
                logger.info(
                    "[GAME] ✅ Audio generated: %s (%d bytes)", audio_path, file_size
                )
            else:
                logger.error(
                    "[GAME] ❌ Audio path returned but file doesn't exist: %s",
                    audio_path,
                )
        else:
            logger.error("[GAME] ❌ No audio path returned from TTS!")

        if alignment_data:
            logger.info("[GAME] ✅ Got %d word timestamps", len(alignment_data))
        else:
            logger.warning("[GAME] ⚠️ No alignment data")

    return audio_path, alignment_data


def process_player_action(
    action_type: str, target: str, custom_message: str, session_id: str
) -> Tuple[str, Optional[str], str, GameState, Optional[List[Dict]]]:
    """Process a player action and return response (legacy interface).

    This is a convenience wrapper that calls run_action_logic + generate_turn_media
    synchronously. For better UX, use run_action_logic first, update UI, then
    call generate_turn_media separately.

    Args:
        action_type: "talk", "search", "accuse", or "custom"
        target: Suspect name, location, or None
        custom_message: Free-form message if action_type is "custom"
        session_id: Session identifier

    Returns:
        Tuple of (response_text, audio_path, speaker_name, state, alignment_data)
    """
    # Run core logic (fast)
    clean_response, speaker, state, actions, audio_path_from_tool = run_action_logic(
        action_type, target, custom_message, session_id
    )

    # Generate media (slow)
    audio_path, alignment_data = generate_turn_media(
        clean_response, speaker, state, actions, audio_path_from_tool, session_id
    )

    return clean_response, audio_path, speaker, state, alignment_data
