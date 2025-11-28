"""Per-turn action logic for the murder mystery game.

This module contains the core logic for:
- Processing structured player actions from the UI (`process_player_action`)
- Running fast action logic for the voice UI without media (`run_action_logic`)
"""

from __future__ import annotations

import logging
import os
import re
from typing import Optional, Tuple, List, Dict

from services.agent import create_game_master_agent, process_message
from game.parser import parse_game_actions
from game.state import GameState
from game.state_manager import (
    game_states,
    mystery_images,
    GAME_MASTER_VOICE_ID,
    _is_invalid_voice_id,
    _get_scene_mood_for_state,
    get_or_create_state,
    get_suspect_voice_id,
)
from services.image_service import generate_portrait_on_demand, get_image_service
from mystery_config import create_validated_config
from game.mystery_generator import (
    generate_mystery,
    prepare_game_prompt,
    assign_voice_to_suspect,
)
from services.tts_service import text_to_speech

logger = logging.getLogger(__name__)


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
        Tuple of (response_text, audio_path, speaker_name, state, alignment_data)
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
        return "I didn't understand that action.", None, "Game Master", state, None

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

    if suspect_to_assign and _is_invalid_voice_id(
        getattr(suspect_to_assign, "voice_id", None)
    ):
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

    # Parse game actions to detect interrogations, searches, clues, accusations.
    actions = parse_game_actions(message, response, state)

    # Robustly mark suspects as "talked to" based on the detected speaker as well.
    # This complements the text-based parser and ensures the sidebar ticks a suspect
    # whenever their voice is actually used in the conversation.
    if speaker and speaker != "Game Master":
        try:
            state.add_suspect_talked_to(speaker)
        except Exception:
            logger.exception(
                "[GAME] Failed to mark suspect %s as talked to on state", speaker
            )

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

    alignment_data: Optional[List[Dict]] = None
    if audio_path_from_tool:
        # Try to get alignment data from tool-generated audio
        audio_path = audio_path_from_tool
        from game.tools import get_audio_alignment_data

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

    # Also mark suspects as "talked to" based on the speaker, so even if the
    # player's wording doesn't match our text heuristics, the suspect sidebar
    # stays in sync with who has actually spoken.
    if speaker and speaker != "Game Master":
        try:
            state.add_suspect_talked_to(speaker)
        except Exception:
            logger.exception(
                "[GAME] Failed to mark suspect %s as talked to on state", speaker
            )

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


