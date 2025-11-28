"""Game logic handlers for starting games and processing player actions."""

import os
import re
import logging
import time
import threading
import queue
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
from mystery_config import create_validated_config
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


def _background_generate_title_card_from_premise(session_id: str):
    """Generate opening scene image in the background using premise-only data.

    This can run before the full mystery is ready. It uses the stored
    ``premise_setting`` and ``premise_victim_name`` on the GameState to
    build a lightweight mystery-like object for the image service.
    """
    try:
        # If another process (e.g. the foreground fallback) has already
        # generated the opening scene, don't do duplicate work.
        existing = mystery_images.get(session_id, {})
        if existing.get("_opening_scene"):
            logger.info(
                "[BG] Title-card prewarm: opening scene already exists for %s, skipping",
                session_id,
            )
            return

        bg_state = get_or_create_state(session_id)
        setting = getattr(bg_state, "premise_setting", None)
        victim_name = getattr(bg_state, "premise_victim_name", None)
        if not setting or not victim_name:
            logger.info(
                "[BG] Title-card prewarm: missing premise data for session %s, skipping",
                session_id,
            )
            return

        from types import SimpleNamespace
        from image_service import generate_title_card_on_demand

        victim_stub = SimpleNamespace(name=victim_name)
        mystery_like = SimpleNamespace(victim=victim_stub, setting=setting)

        logger.info(
            "[BG] Generating opening scene image from premise for session %s",
            session_id,
        )
        portrait = generate_title_card_on_demand(mystery_like)
        if not portrait:
            logger.warning(
                "[BG] Failed to generate opening scene image for session %s",
                session_id,
            )
            return

        # Ensure session image dict exists without clobbering any existing images
        if session_id not in mystery_images:
            mystery_images[session_id] = {}
        mystery_images[session_id]["_opening_scene"] = portrait
        logger.info(
            "[BG] Prewarmed opening scene image for session %s: %s",
            session_id,
            portrait,
        )
    except Exception:
        logger.exception(
            "[BG] Error prewarming opening scene image for session %s", session_id
        )


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
    """Start a new mystery game with fast premise + background case generation."""
    state = get_or_create_state(session_id)
    state.reset_game()

    # Ensure we have a configuration object for this session
    if not hasattr(state, "config") or state.config is None:
        state.config = create_validated_config()
    config = state.config
    # Cache tone instruction on state so it can be used in continue prompts
    try:
        state.tone_instruction = config.get_tone_instruction()
    except Exception:  # noqa: BLE001
        state.tone_instruction = None

    # ========== STAGE 1: FAST PREMISE ==========
    logger.info("Generating mystery premise...")
    t0 = time.perf_counter()
    premise = generate_mystery_premise(config=config)
    t1 = time.perf_counter()
    logger.info("[PERF] Mystery premise generation took %.2fs", t1 - t0)

    # Store premise on state for later use
    state.premise_setting = premise.setting
    state.premise_victim_name = premise.victim_name
    state.premise_victim_background = premise.victim_background

    # Build a lightweight system prompt for the intro, based only on the premise.
    state.system_prompt = f"""You are the Game Master for a murder mystery game.

## THE CASE (PREMISE ONLY)
{premise.setting}

## VICTIM
{premise.victim_name}: {premise.premise_victim_background if hasattr(premise, 'premise_victim_background') else premise.victim_background}

The full case file with suspects and clues is still being compiled off-screen.

## RESPONSE LENGTH
Keep ALL responses SHORT for voice narration (10-20 seconds of speech).
- Welcome: 2-3 atmospheric sentences (max 40-50 words total)
- Then ask what the player would like to do first.
- NEVER write more than 50 words in a single response.

Do NOT mention that the case file is still generating or anything about the
system or background tasks. Stay purely in-world."""

    # Initialize with agent and narration (images generated on-demand)
    logger.info("Starting game initialization (images will be generated on-demand)...")

    # Kick off background generation of the opening scene image as soon as
    # we have the premise (victim + setting). This runs concurrently with
    # the welcome LLM + TTS so the image is often ready by the time we show
    # the first screen, without blocking startup.
    try:
        threading.Thread(
            target=_background_generate_title_card_from_premise,
            args=(session_id,),
            daemon=True,
        ).start()
    except Exception as e:  # noqa: BLE001
        logger.error(
            "[BG] Error starting title-card prewarm thread for %s: %s",
            session_id,
            e,
        )

    # Create or reuse shared agent and get narration immediately (no waiting for images)
    if not hasattr(start_new_game, "agent"):
        start_new_game.agent = create_game_master_agent()

    t2 = time.perf_counter()
    response, _speaker = process_message(
        start_new_game.agent,
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

    # Ensure images dict exists for this session (do not clobber prewarmed images)
    if session_id not in mystery_images:
        mystery_images[session_id] = {}

    # Generate audio (needs the response text)
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

    # Store in messages
    state.messages.append(
        {"role": "assistant", "content": response, "speaker": "Game Master"}
    )

    # ========== STAGE 2: FULL CASE IN BACKGROUND ==========

    def _background_generate_full_case(sess_id: str, premise_obj):
        bg_state = get_or_create_state(sess_id)
        try:
            # Use the latest config for this session when generating the full case
            if not hasattr(bg_state, "config") or bg_state.config is None:
                bg_state.config = create_validated_config()
            bg_config = bg_state.config
            # Keep tone_instruction on state in sync with config
            try:
                bg_state.tone_instruction = bg_config.get_tone_instruction()
            except Exception:  # noqa: BLE001
                bg_state.tone_instruction = None

            logger.info("[BG] Starting full mystery generation in background...")
            t_full_0 = time.perf_counter()
            full_mystery = generate_mystery(premise=premise_obj, config=bg_config)
            t_full_1 = time.perf_counter()
            logger.info(
                "[PERF] Full mystery generation (background) took %.2fs",
                t_full_1 - t_full_0,
            )
            bg_state.mystery = full_mystery
            bg_state.system_prompt = prepare_game_prompt(
                full_mystery, bg_state.tone_instruction
            )
            bg_state.mystery_ready = True
            logger.info("[BG] Full mystery is ready for session %s", sess_id)

            # Kick off background prewarming of suspect portraits AND scene images
            # Both run in parallel using separate worker pools (2 workers each)
            try:
                threading.Thread(
                    target=_prewarm_suspect_portraits,
                    args=(sess_id, full_mystery),
                    daemon=True,
                ).start()
            except Exception as e2:  # noqa: BLE001
                logger.error(
                    "[BG] Error starting suspect portrait prewarm thread for %s: %s",
                    sess_id,
                    e2,
                )

            try:
                threading.Thread(
                    target=_prewarm_scene_images,
                    args=(sess_id, full_mystery),
                    daemon=True,
                ).start()
            except Exception as e3:  # noqa: BLE001
                logger.error(
                    "[BG] Error starting scene image prewarm thread for %s: %s",
                    sess_id,
                    e3,
                )
        except Exception as e:
            logger.error("[BG] Error generating full mystery in background: %s", e)

    threading.Thread(
        target=_background_generate_full_case,
        args=(session_id, premise),
        daemon=True,
    ).start()

    return state, response, audio_path, "Game Master", alignment_data


def start_new_game_staged(session_id: str):
    """Staged version of start_new_game used by the UI to show progress.

    This wraps the existing start_new_game() function and exposes coarse
    progress stages as a generator:
      - ("premise", 0.2, None)
      - ("welcome", 0.5, None)
      - ("tts", 0.8, None)
      - ("complete", 1.0, {...})
    """
    # Initial stage - premise (we don't re-run premise here, just expose stage)
    yield ("premise", 0.2, None)

    # Run the actual startup logic (premise + welcome + TTS + BG full mystery)
    state, response, audio_path, speaker, alignment_data = start_new_game(session_id)

    # Expose additional coarse stages so the UI can animate the progress bar
    yield ("welcome", 0.5, None)
    yield ("tts", 0.8, None)

    # Final stage with full data
    yield (
        "complete",
        1.0,
        {
            "state": state,
            "response": response,
            "audio_path": audio_path,
            "speaker": speaker,
            "alignment_data": alignment_data,
        },
    )


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

    # If the full mystery is not ready yet, keep the player in the intro
    # phase. This prevents interrogations/searches before the case file
    # has been fully generated.
    if not getattr(state, "mystery_ready", False):
        return (
            "Your full case file is still being prepared. "
            "Give me just a moment, then try again.",
            None,
            "Game Master",
            state,
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
        return "I didn't understand that action.", None, "Game Master", state

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
    
    if suspect_to_assign and _is_invalid_voice_id(getattr(suspect_to_assign, "voice_id", None)):
        logger.info("Assigning voice on-demand for suspect: %s", suspect_to_assign.name)
        # Get list of already-used voice IDs to avoid duplicates
        used_voice_ids = [
            s.voice_id
            for s in state.mystery.suspects
            if s.voice_id and s.name != suspect_to_assign.name
        ]
        assign_voice_to_suspect(suspect_to_assign, used_voice_ids)

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
            # (May have been assigned earlier for "talk" action)
            if _is_invalid_voice_id(getattr(suspect, "voice_id", None)):
                logger.info("Assigning voice on-demand for suspect: %s", speaker)
                # Get list of already-used voice IDs to avoid duplicates
                used_voice_ids = [
                    s.voice_id
                    for s in state.mystery.suspects
                    if s.voice_id and s.name != speaker
                ]
                assign_voice_to_suspect(suspect, used_voice_ids)
                # voice_id will be available for next interaction

            # Check if we need to generate this suspect's portrait
            if speaker not in session_images:
                logger.info("Generating portrait on-demand for suspect: %s", speaker)
                portrait_path = generate_portrait_on_demand(
                    suspect, state.mystery.setting if state.mystery else ""
                )
                if portrait_path:
                    # Store in mystery_images dict for this session
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
        else:
            logger.warning(
                "Suspect %s not found in mystery for portrait/voice generation", speaker
            )

    # Generate scene image on-demand if a location was searched
    if actions.get("location_searched"):
        location = actions["location_searched"]
        session_images = mystery_images.get(session_id, {})

        # Only generate if we don't already have this scene
        if location not in session_images:
            logger.info("Generating scene image for location: %s", location)
            service = get_image_service()
            if service and service.is_available:
                # Use the response text as context for scene generation
                # Clean the response to extract relevant descriptive content
                context_text = clean_response[:500]  # Use first 500 chars as context
                mood = _get_scene_mood_for_state(state)
                scene_path = service.generate_scene(
                    location_name=location,
                    setting_description=state.mystery.setting if state.mystery else "",
                    mood=mood,
                    context=context_text,
                )
                if scene_path:
                    # Store in mystery_images dict for this session
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
        if _is_invalid_voice_id(voice_id):
            logger.warning(
                "[GAME] Ignoring invalid/placeholder voice_id '%s' for %s, "
                "falling back to default assignment",
                voice_id,
                speaker,
            )
            voice_id = None
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

    # Store response (without audio marker)
    state.messages.append(
        {
            "role": "assistant",
            "content": clean_response,
            "speaker": speaker or "Game Master",
        }
    )

    return clean_response, audio_path, speaker or "Game Master", state, alignment_data


# ============================================================================
# FAST ACTION LOGIC + MEDIA GENERATION (for voice UI)
# ============================================================================


def run_action_logic(
    action_type: str, target: str, custom_message: str, session_id: str
) -> Tuple[str, str, GameState, Dict, Optional[str]]:
    """Process player action logic WITHOUT generating audio/images (fast path).

    This is used by the voice UI to:
      - Run transcription + LLM agent + tools
      - Parse actions
      - Extract any tool-generated audio path (from [AUDIO:...] markers)
    and then hand off to generate_turn_media() for the slow TTS/image work.

    Returns:
        Tuple of (clean_response, speaker_name, state, actions_dict, audio_path_from_tool)
    """
    state = get_or_create_state(session_id)

    # If the full mystery is not ready yet, keep the player in the intro phase.
    if not getattr(state, "mystery_ready", False):
        clean = (
            "Your full case file is still being prepared. "
            "Give me just a moment, then try again."
        )
        return clean, "Game Master", state, {}, None

    # Build the message based on action type (same as process_player_action)
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
    suspect_to_assign = None
    if action_type == "talk" and target:
        for s in state.mystery.suspects:
            if s.name == target:
                suspect_to_assign = s
                break
    elif action_type == "custom" and custom_message:
        # Reuse the same heuristic + AI resolver logic as process_player_action
        message_lower = custom_message.lower()
        message_words = set(message_lower.split())

        for s in state.mystery.suspects:
            name_parts = s.name.lower().split()

            if s.name.lower() in message_lower:
                suspect_to_assign = s
                logger.info("Detected suspect mention (full name): %s", s.name)
                break

            for i in range(len(name_parts) - 1):
                partial_name = f"{name_parts[i]} {name_parts[i+1]}"
                if partial_name in message_lower:
                    suspect_to_assign = s
                    logger.info("Detected suspect mention (partial name): %s", s.name)
                    break
            if suspect_to_assign:
                break

            for part in name_parts:
                if len(part) >= 3 and part in message_words:
                    suspect_to_assign = s
                    logger.info(
                        "Detected suspect mention (name part '%s'): %s",
                        part,
                        s.name,
                    )
                    break
            if suspect_to_assign:
                break

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

    # Handle empty or placeholder responses
    empty_responses = ["", "Empty", "I'm processing your request", "No content"]
    if not response or response.strip() in empty_responses:
        logger.warning(
            "[GAME] LLM returned empty/placeholder response, generating fallback"
        )
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

    # Parse actions
    actions = parse_game_actions(message, response, state)

    # Extract audio path marker if present (from interrogate_suspect tool)
    audio_path_from_tool = None
    clean_response = response
    audio_marker_pattern = r"\[AUDIO:([^\]]+)\]"
    match = re.search(audio_marker_pattern, response)
    if match:
        audio_path_from_tool = match.group(1)
        clean_response = re.sub(audio_marker_pattern, "", response).strip()
        logger.info("Extracted audio path from tool: %s", audio_path_from_tool)

    # Store assistant message (text only)
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
            bg_state = get_or_create_state(session_id)
            mood = _get_scene_mood_for_state(bg_state)
            scene_path = service.generate_scene(
                location_name=location,
                setting_description=mystery_setting,
                mood=mood,
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


def _prewarm_suspect_portraits(session_id: str, mystery):
    """Pre-generate portraits for all suspects in the background.

    Uses a small bounded worker pool (max 2 concurrent workers) so we don't
    overwhelm the image API but still parallelize enough to be snappy.
    """
    if not mystery or not getattr(mystery, "suspects", None):
        logger.info(
            "[BG] No suspects available for portrait prewarm in session %s", session_id
        )
        return

    setting = getattr(mystery, "setting", "") or ""
    session_images = mystery_images.get(session_id, {})

    tasks: List[Tuple[str, object]] = []
    for suspect in mystery.suspects:
        name = getattr(suspect, "name", None)
        if not name:
            continue
        if name in session_images:
            # Already have a portrait for this suspect
            continue
        tasks.append((name, suspect))

    if not tasks:
        logger.info(
            "[BG] No new suspect portraits to prewarm for session %s", session_id
        )
        return

    task_queue: "queue.Queue[Tuple[str, object]]" = queue.Queue()
    for task in tasks:
        task_queue.put(task)

    def _worker():
        while True:
            try:
                name, suspect = task_queue.get_nowait()
                try:
                    logger.info(
                        "[BG] Worker generating prewarm portrait for %s in session %s",
                        name,
                        session_id,
                    )
                    _generate_portrait_background(name, suspect, setting, session_id)
                finally:
                    # Ensure task is marked done even if generation fails
                    task_queue.task_done()
            except queue.Empty:
                break
            except Exception as e:  # noqa: BLE001
                logger.error(
                    "[BG] Worker error generating portrait for %s in session %s: %s",
                    name if "name" in locals() else "<unknown>",
                    session_id,
                    e,
                )

    max_workers = 3  # Limit to 2 concurrent image generations
    num_workers = min(max_workers, len(tasks))
    for _ in range(num_workers):
        t = threading.Thread(target=_worker, daemon=True)
        t.start()

    logger.info(
        "[BG] Launched %d prewarm portrait workers for session %s (tasks=%d)",
        num_workers,
        session_id,
        len(tasks),
    )
    # No need to join here, as these are daemon threads and we don't block on them.


def _prewarm_scene_images(session_id: str, mystery):
    """Pre-generate scene images for all locations in the background.

    Runs concurrently with portrait prewarming. Uses 2 workers to generate
    scene images for each unique location mentioned in the clues.
    """
    if not mystery or not getattr(mystery, "clues", None):
        logger.info(
            "[BG] No clues available for scene prewarm in session %s", session_id
        )
        return

    setting = getattr(mystery, "setting", "") or ""
    session_images = mystery_images.get(session_id, {})

    # Extract unique locations from clues
    locations = set()
    for clue in mystery.clues:
        location = getattr(clue, "location", None)
        if location and location not in session_images:
            locations.add(location)

    if not locations:
        logger.info(
            "[BG] No new scene images to prewarm for session %s", session_id
        )
        return

    task_queue: "queue.Queue[str]" = queue.Queue()
    for location in locations:
        task_queue.put(location)

    def _worker():
        while True:
            try:
                location = task_queue.get_nowait()
                try:
                    logger.info(
                        "[BG] Worker generating prewarm scene for %s in session %s",
                        location,
                        session_id,
                    )
                    # Generate scene without specific context (since player hasn't searched yet)
                    _generate_scene_background(
                        location=location,
                        mystery_setting=setting,
                        context_text="",  # No context yet - player hasn't searched
                        session_id=session_id,
                    )
                finally:
                    task_queue.task_done()
            except queue.Empty:
                break
            except Exception as e:  # noqa: BLE001
                logger.error(
                    "[BG] Worker error generating scene for %s in session %s: %s",
                    location if "location" in locals() else "<unknown>",
                    session_id,
                    e,
                )

    max_workers = 3  # Limit to 2 concurrent scene generations
    num_workers = min(max_workers, len(locations))
    for _ in range(num_workers):
        t = threading.Thread(target=_worker, daemon=True)
        t.start()

    logger.info(
        "[BG] Launched %d prewarm scene workers for session %s (locations=%d)",
        num_workers,
        session_id,
        len(locations),
    )


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
                    logger.info(
                        "[GAME] Starting background portrait generation for: %s", speaker
                    )
                    threading.Thread(
                        target=_generate_portrait_background,
                        args=(speaker, suspect, mystery_setting, session_id),
                        daemon=True,
                    ).start()
                else:
                    # Foreground (blocking)
                    logger.info(
                        "Generating portrait on-demand for suspect: %s", speaker
                    )
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
                logger.info(
                    "[GAME] Starting background scene generation for: %s", location
                )
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
    speaker = speaker or "Game Master"

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
