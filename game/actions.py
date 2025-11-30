"""Per-turn action logic for the murder mystery game.

This module contains the core logic for:
- Processing structured player actions from the UI (`process_player_action`)
- Running fast action logic for the voice UI without media (`run_action_logic`)
"""

from __future__ import annotations

import logging
import os
import re
import json
from typing import Optional, Tuple, List, Dict

from services.agent import create_game_master_agent, process_message
from game.parser import parse_game_actions, clean_response_markers
from game.state import GameState
from game.state_manager import (
    mystery_images,
    GAME_MASTER_VOICE_ID,
    _is_invalid_voice_id,
    _get_scene_mood_for_state,
    get_or_create_state,
    get_suspect_voice_id,
    normalize_location_name,
)
from services.image_service import smart_generate_portrait, smart_generate_scene
from game.mystery_generator import (
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

    # Extract optional scene brief marker (from describe_scene_for_image tool)
    # Format: [SCENE_BRIEF{...json...}]
    scene_brief = None
    scene_pattern = r"\[SCENE_BRIEF(?P<json>\{.*?\})\]"
    scene_match = re.search(scene_pattern, clean_response)
    if scene_match:
        scene_json = scene_match.group("json")
        try:
            scene_brief = json.loads(scene_json)
            logger.info(
                "[GAME] Parsed SCENE_BRIEF for location: %s",
                scene_brief.get("location_name"),
            )
        except Exception as e:  # noqa: BLE001
            logger.exception("[GAME] Failed to parse SCENE_BRIEF JSON: %s", e)
            scene_brief = None

        # Remove the scene brief marker from the text seen by the player
        clean_response = re.sub(scene_pattern, "", clean_response).strip()

        # If we successfully parsed, cache a rich description on state
        if scene_brief:
            loc_name = scene_brief.get("location_name")
            env = scene_brief.get("environment_description") or ""
            camera = scene_brief.get("camera_position") or ""
            focal = scene_brief.get("focal_objects") or ""

            parts = [env]
            if camera:
                parts.append(f"Camera: {camera}")
            if focal:
                parts.append(f"Focal objects: {focal}")
            full_desc = " ".join(p for p in parts if p)

            if loc_name and full_desc:
                try:
                    normalized_loc = normalize_location_name(loc_name, state)
                except Exception:
                    normalized_loc = loc_name
                try:
                    state.location_descriptions[normalized_loc] = full_desc
                    logger.info(
                        "[GAME] Stored scene brief for %s", normalized_loc
                    )
                except Exception:  # noqa: BLE001
                    logger.exception(
                        "[GAME] Failed to store scene brief for %s", normalized_loc
                    )

    # Remove game state markers from response (SEARCHED, ACCUSATION, CLUE_FOUND)
    clean_response = clean_response_markers(clean_response)

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
                portrait_path = smart_generate_portrait(
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
    # ALWAYS regenerate if we have clue context (even if prewarmed image exists)
    if actions.get("location_searched"):
        location = actions["location_searched"]
        normalized_location = normalize_location_name(location, state)
        session_images = mystery_images.get(session_id, {})
        
        # Build rich scene context: stored location description + latest narrative
        loc_desc = getattr(state, "location_descriptions", {}).get(
            normalized_location, ""
        )
        
        # Check if we have clue context from the describe_scene_for_image tool
        has_clue_context = bool(loc_desc and "Focus:" in loc_desc)
        image_exists = normalized_location in session_images or location in session_images
        
        # Generate if: no image exists OR we have clue context (override prewarmed)
        if has_clue_context or not image_exists:
            parts = []
            if loc_desc:
                parts.append(f"CLUE-FOCUSED IMAGE: {loc_desc}")
            if clean_response:
                parts.append(clean_response[:300])
            context_text = " ".join(parts)
            mood = _get_scene_mood_for_state(state)
            
            if has_clue_context and image_exists:
                logger.info("🎯 Regenerating scene with CLUE FOCUS (overriding prewarmed): %s", normalized_location)
            else:
                logger.info("Generating scene image for location: %s (normalized: %s)", location, normalized_location)
            
            # Use smart_generate_scene (MCP if available, otherwise direct)
            scene_path = smart_generate_scene(
                location=normalized_location,
                setting=state.mystery.setting if state.mystery else "",
                mood=mood,
                context=context_text,
            )
            if scene_path:
                # Store in mystery_images dict for this session with normalized name
                # Also store with original name as fallback
                if session_id not in mystery_images:
                    mystery_images[session_id] = {}
                mystery_images[session_id][normalized_location] = scene_path
                if normalized_location != location:
                    mystery_images[session_id][location] = scene_path  # Also store with original
                logger.info(
                    "Generated and stored scene for %s (normalized: %s): %s",
                    location,
                    normalized_location,
                    scene_path,
                )
            else:
                logger.warning("Failed to generate scene for %s", normalized_location)
        else:
            logger.info("Using existing image for %s (no clue context)", normalized_location)

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
    else:
        # Narrator: prefer the per-game Game Master voice picked at startup
        gm_voice = getattr(state, "game_master_voice_id", None)
        if gm_voice:
            voice_id = gm_voice

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

    # Remove game state markers from response (SEARCHED, ACCUSATION, CLUE_FOUND)
    clean_response = clean_response_markers(clean_response)

    # Store assistant message (text only)
    state.messages.append(
        {
            "role": "assistant",
            "content": clean_response,
            "speaker": speaker or "Game Master",
        }
    )

    return clean_response, speaker or "Game Master", state, actions, audio_path_from_tool


