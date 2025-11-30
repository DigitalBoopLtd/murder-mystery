"""Game logic handlers for starting games and processing player actions."""

import os
import json
import logging
import time
import threading
from typing import Optional, Tuple, List, Dict

from game.state import GameState
from services.image_service import (
    smart_generate_portrait,
    smart_generate_scene,
)
from game.mystery_generator import (
    assign_voice_to_suspect,
)
from services.agent import create_game_master_agent, process_message
from game.parser import parse_game_actions, clean_response_markers
from services.tts_service import text_to_speech
from game.state_manager import (
    mystery_images,
    GAME_MASTER_VOICE_ID,
    _is_invalid_voice_id,
    _get_scene_mood_for_state,
    get_or_create_state,
    get_suspect_voice_id,
    normalize_location_name,
    set_current_session,
    get_tool_output_store,
    clear_tool_outputs,
)
from game.media import _generate_portrait_background
from services.game_memory import get_game_memory
from services.perf_tracker import perf

logger = logging.getLogger(__name__)


# ============================================================================
# Accusation Detection Helper
# ============================================================================


def _detect_accusation_intent(message: str, state: GameState) -> Optional[str]:
    """Detect if the player is making an accusation and extract the suspect name.
    
    Returns the suspect name if an accusation is detected, None otherwise.
    """
    if not state.mystery:
        return None
    
    message_lower = message.lower()
    
    # Keywords that indicate accusation intent
    accusation_keywords = [
        "i accuse",
        "you are the murderer",
        "you are the killer", 
        "you killed",
        "you did it",
        "you're the murderer",
        "you're the killer",
        "it was you",
        "you committed the murder",
        "you are guilty",
        "i think you murdered",
        "i think you killed",
        "the murderer is",
        "the killer is",
        "guilty of murder",
        "committed this murder",
    ]
    
    has_accusation_keyword = any(kw in message_lower for kw in accusation_keywords)
    
    if not has_accusation_keyword:
        return None
    
    # Check if a suspect name is mentioned or if we're talking to someone
    for suspect in state.mystery.suspects:
        suspect_lower = suspect.name.lower()
        name_parts = suspect_lower.split()
        
        # Check full name
        if suspect_lower in message_lower:
            logger.info("[ACCUSE] Detected accusation against: %s (full name match)", suspect.name)
            return suspect.name
        
        # Check any significant name part (2+ chars)
        for part in name_parts:
            if len(part) >= 3 and part in message_lower:
                logger.info("[ACCUSE] Detected accusation against: %s (name part '%s')", suspect.name, part)
                return suspect.name
    
    # If message uses "you" (second person), try to find the last suspect talked to
    second_person_words = ["you", "you're", "your"]
    if any(word in message_lower.split() for word in second_person_words):
        last_speaker = _get_last_suspect_speaker(state)
        if last_speaker:
            logger.info("[ACCUSE] Detected accusation using 'you' - inferring target: %s", last_speaker)
            return last_speaker
    
    return None


# ============================================================================
# Scene Brief Processing Helper
# ============================================================================


def _process_scene_brief(scene_brief: dict, state: GameState) -> str:
    """Process a scene brief and cache the description on state.
    
    Handles both new clue-focused format and legacy format.
    Returns the full description string for logging.
    """
    logger.info("[SCENE_BRIEF] Processing: %s", scene_brief)
    
    loc_name = scene_brief.get("location_name")
    
    # New clue-focused format
    clue_focus = scene_brief.get("clue_focus") or ""
    camera_angle = scene_brief.get("camera_angle") or ""
    lighting = scene_brief.get("lighting_mood") or ""
    background = scene_brief.get("background_hint") or ""
    prompt_hint = scene_brief.get("prompt_hint") or ""
    
    logger.info("[SCENE_BRIEF] Extracted: location=%s, clue_focus=%s, camera=%s", 
                loc_name, clue_focus[:50] if clue_focus else "none", camera_angle)
    
    # Legacy format support
    env = scene_brief.get("environment_description") or ""
    camera = scene_brief.get("camera_position") or camera_angle
    focal = scene_brief.get("focal_objects") or clue_focus

    # Build description prioritizing clue-focused format
    parts = []
    if clue_focus:
        parts.append(f"Focus: {clue_focus}")
    if camera_angle:
        parts.append(f"Shot: {camera_angle}")
    if lighting:
        parts.append(f"Lighting: {lighting}")
    if background:
        parts.append(f"Background: {background}")
    # Fallback to legacy fields
    if not parts and env:
        parts.append(env)
        if camera:
            parts.append(f"Camera: {camera}")
        if focal:
            parts.append(f"Focal: {focal}")
    if prompt_hint:
        parts.append(prompt_hint)
    full_desc = " | ".join(p for p in parts if p)

    if loc_name and full_desc:
        try:
            normalized_loc = normalize_location_name(loc_name, state)
        except Exception:
            normalized_loc = loc_name
        try:
            state.location_descriptions[normalized_loc] = full_desc
            logger.info("[GAME] Stored scene brief for %s: %s", normalized_loc, full_desc[:100])
        except Exception:  # noqa: BLE001
            logger.exception("[GAME] Failed to store scene brief for %s", normalized_loc)
    
    return full_desc


# ============================================================================
# AI Enhancement Helpers
# ============================================================================


def _analyze_question_style(question: str) -> Tuple[int, int]:
    """Analyze the player's question to determine emotional impact on suspect.
    
    Returns:
        Tuple of (trust_delta, nervousness_delta) to apply to the suspect.
    """
    question_lower = question.lower()
    trust_delta = 0
    nervousness_delta = 0
    
    # Aggressive/accusatory language decreases trust, increases nervousness
    aggressive_words = [
        "liar", "lying", "killed", "murder", "guilty", "confess",
        "admit", "truth", "suspicious", "caught", "evidence against",
        "you did it", "accuse", "blame"
    ]
    for word in aggressive_words:
        if word in question_lower:
            trust_delta -= 5
            nervousness_delta += 10
            break  # Only apply once
    
    # Friendly/empathetic language increases trust, decreases nervousness
    friendly_words = [
        "help", "understand", "sorry", "difficult", "must be hard",
        "appreciate", "thank", "please", "kind", "trust you"
    ]
    for word in friendly_words:
        if word in question_lower:
            trust_delta += 5
            nervousness_delta -= 5
            break  # Only apply once
    
    # Direct confrontation with evidence increases nervousness
    confrontation_phrases = [
        "but you said", "you told me", "earlier you", "contradict",
        "that doesn't match", "someone saw you", "witness"
    ]
    for phrase in confrontation_phrases:
        if phrase in question_lower:
            nervousness_delta += 15
            break
    
    return trust_delta, nervousness_delta


def _get_last_suspect_speaker(state: GameState) -> Optional[str]:
    """Return the last non-Game-Master speaker from state.messages, if any.

    Used as a fallback to interpret follow-up custom messages as being
    directed to the last suspect the player was talking to (e.g. when the
    player says "Why did you lie about the time?" right after Father Fiber
    spoke, without repeating his name).
    """
    # Walk messages in reverse and find the most recent assistant message
    # from a suspect (speaker != "Game Master").
    for msg in reversed(getattr(state, "messages", [])):
        try:
            if msg.get("role") == "assistant":
                speaker = msg.get("speaker")
                if speaker and speaker != "Game Master":
                    return speaker
        except AttributeError:
            # If messages are not dict-like for some reason, skip gracefully
            continue
    return None


def _record_interrogation(
    state: GameState,
    suspect_name: str,
    question: str,
    answer: str
) -> None:
    """Index interrogation in RAG memory for semantic search.
    
    NOTE: Conversation recording and emotional state updates now happen
    INSIDE the interrogate_suspect tool (before the unlock check) so that
    trust/nervousness changes from the current question affect location reveals.
    
    This function now ONLY handles RAG indexing for semantic search.
    
    Args:
        state: Current game state
        suspect_name: Name of the suspect who responded
        question: The player's question/message
        answer: The suspect's response
    """
    try:
        # Index in vector store for RAG search
        # (Conversation is already recorded in the tool, we just need to index it)
        memory = get_game_memory()
        if memory.is_available:
            memory.add_conversation(
                suspect=suspect_name,
                question=question,
                answer=answer,
                turn=state.current_turn
            )
            logger.info(
                "[AI] Indexed interrogation with %s in RAG memory (turn %d)",
                suspect_name,
                state.current_turn
            )
    except Exception:
        logger.exception("[AI] Failed to index interrogation with %s", suspect_name)

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
    # Set current session for tool context and clear previous outputs
    set_current_session(session_id)
    clear_tool_outputs(session_id)
    
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
    # Perf: measure time spent resolving which suspect (if any) this message targets
    t_resolve_start = time.perf_counter()

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
    
    # ========== ACCUSATION DETECTION ==========
    # Detect accusations and rewrite message to be explicit so LLM routes to make_accusation tool
    # This prevents "I accuse you" from being routed to interrogate_suspect
    accused_suspect = None
    if state.mystery:  # Only check for accusations if mystery is loaded
        if action_type == "accuse" and target:
            # Explicit accuse action - find the suspect name
            for s in state.mystery.suspects:
                if s.name.lower() == target.lower() or target.lower() in s.name.lower():
                    accused_suspect = s.name
                    break
            if not accused_suspect:
                accused_suspect = target  # Use the target as-is if not found
        elif action_type == "custom" and custom_message:
            # Check custom messages for accusation intent
            accused_suspect = _detect_accusation_intent(message, state)
    
    if accused_suspect:
        # Rewrite message to be explicit about accusation intent for the LLM
        original_message = message
        message = f"[FORMAL ACCUSATION] I formally accuse {accused_suspect} of the murder! Use the make_accusation tool. Original statement: {original_message}"
        logger.info("[GAME] Detected accusation against %s - rewrote message for agent", accused_suspect)
        # Update the stored player message
        if state.messages:
            state.messages[-1]["content"] = original_message  # Keep original for display

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

        # Final fallback: treat as follow-up to the last suspect who spoke,
        # as long as the message doesn't clearly mention a different suspect.
        if not suspect_to_assign and state.mystery:
            last_speaker = _get_last_suspect_speaker(state)
            if last_speaker:
                # Avoid overriding when the message explicitly names someone else
                explicit_other = False
                for s in state.mystery.suspects:
                    if s.name == last_speaker:
                        continue
                    if s.name.lower() in message_lower:
                        explicit_other = True
                        break
                if not explicit_other:
                    for s in state.mystery.suspects:
                        if s.name == last_speaker:
                            suspect_to_assign = s
                            logger.info(
                                "Assuming follow-up question to last suspect speaker: %s",
                                last_speaker,
                            )
                            break
    
    if suspect_to_assign and _is_invalid_voice_id(getattr(suspect_to_assign, "voice_id", None)):
        logger.info("Assigning voice on-demand for suspect: %s", suspect_to_assign.name)
        # Get list of already-used voice IDs to avoid duplicates
        used_voice_ids = [
            s.voice_id
            for s in state.mystery.suspects
            if s.voice_id and s.name != suspect_to_assign.name
        ]
        assign_voice_to_suspect(suspect_to_assign, used_voice_ids)

    # If this was a custom message and we resolved a suspect, gently steer the
    # Game Master to treat it as talking to that suspect. This helps for follow-up
    # lines like "I know you're lying, give it up" where the player doesn't repeat
    # the suspect's name but clearly intends to confront the last speaker.
    if action_type == "custom" and custom_message and suspect_to_assign:
        message = (
            f"I want to talk to {suspect_to_assign.name}. "
            f"Here's what I say to them: {custom_message}"
        )
        # Update the stored player message so state/messages stay in sync
        try:
            if state.messages:
                state.messages[-1]["content"] = message
        except Exception:
            # If messages aren't dict-like for some reason, fail gracefully
            logger.exception(
                "[GAME] Failed to update stored custom message content on state"
            )

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

    # ========== Structured Tool Outputs (No Regex!) ==========
    # Tools store their outputs in ToolOutputStore, we just read from it
    tool_store = get_tool_output_store(session_id)
    
    # Get audio path from tool store (no regex parsing needed!)
    audio_path_from_tool = tool_store.audio_path
    if audio_path_from_tool:
        logger.info("[GAME] Audio path from ToolOutputStore: %s", audio_path_from_tool)
    
    # Get scene brief from tool store (no regex parsing needed!)
    clean_response = response
    if tool_store.scene_brief:
        sb = tool_store.scene_brief
        logger.info("[GAME] Scene brief from ToolOutputStore: location=%s, clue_focus=%s", 
                    sb.location_name, sb.clue_focus[:50] if sb.clue_focus else "none")
        
        # Convert to dict format and process (stores in state.location_descriptions)
        scene_brief_dict = {
            "location_name": sb.location_name,
            "clue_focus": sb.clue_focus,
            "camera_angle": sb.camera_angle,
            "lighting_mood": sb.lighting_mood,
            "background_hint": sb.background_hint,
            "prompt_hint": sb.prompt_hint,
        }
        _process_scene_brief(scene_brief_dict, state)
    
    # Merge tool store actions into parsed actions
    # Tool store values take precedence over parser-detected values
    if tool_store.location_searched:
        tool_location = tool_store.location_searched
        parser_location = actions.get("location_searched")
        
        # If parser detected a different location, replace it in state.searched_locations
        if parser_location and parser_location != tool_location:
            if parser_location in state.searched_locations:
                state.searched_locations.remove(parser_location)
                logger.info("[GAME] Replaced parser location '%s' with tool location '%s'", 
                           parser_location, tool_location)
        
        # Ensure the tool store location is in searched_locations
        if tool_location not in state.searched_locations:
            state.searched_locations.append(tool_location)
        
        actions["location_searched"] = tool_location
    
    if tool_store.clue_found:
        actions["clue_found"] = tool_store.clue_found
        clue_id = tool_store.clue_found
        
        # Add clue to game state and RAG memory
        if state and state.mystery:
            for clue in state.mystery.clues:
                if clue.id == clue_id:
                    # Add to game state (tracks discovered clues for investigation log)
                    state.add_clue(clue.id, clue.description)
                    logger.info("[CLUE] ✅ Added to investigation log: %s at %s", 
                                clue.id, clue.location)
                    
                    # Add to RAG memory for semantic search
                    from services.game_memory import get_game_memory
                    memory = get_game_memory()
                    if memory.is_available:
                        memory.add_clue(
                            clue_id=clue.id,
                            description=clue.description,
                            location=clue.location,
                            significance=clue.significance,
                            turn=state.current_turn
                        )
                        logger.info("[RAG] Indexed clue %s for semantic search", clue.id)
                    break
    
    if tool_store.accusation:
        actions["accusation"] = tool_store.accusation.suspect_name
        actions["accusation_correct"] = tool_store.accusation.is_correct
        actions["accusation_has_evidence"] = tool_store.accusation.has_sufficient_evidence
        
        # Apply accusation result to game state
        # Only count accusations that had sufficient evidence
        if tool_store.accusation.has_sufficient_evidence:
            if tool_store.accusation.is_correct:
                state.won = True
                state.game_over = True
                logger.info("✅ CORRECT ACCUSATION with evidence! Player wins!")
            else:
                state.wrong_accusations += 1
                logger.info(
                    "❌ Wrong accusation: %s (attempt %d/3)",
                    tool_store.accusation.suspect_name,
                    state.wrong_accusations
                )
                if state.wrong_accusations >= 3:
                    state.game_over = True
                    logger.info("💀 3 wrong accusations - GAME OVER!")
        else:
            logger.info(
                "⚠️ Accusation rejected - insufficient evidence (%d clues found)",
                tool_store.accusation.clues_found_count
            )
    
    # Clean up any leftover markers from response (legacy support)
    clean_response = clean_response_markers(clean_response)

    # AI Enhancement Phase 1: Record interrogation and update emotional state
    # This must happen after we have clean_response but before storing the message
    if speaker and speaker != "Game Master":
        _record_interrogation(state, speaker, message, clean_response)

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

    alignment_data = None
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


# ============================================================================
# FAST ACTION LOGIC + MEDIA GENERATION (for voice UI)
# ============================================================================


def run_action_logic(
    action_type: str, target: str, custom_message: str, session_id: str
) -> Tuple[str, str, GameState, Dict, Optional[str]]:
    """Process player action logic WITHOUT generating audio/images (fast path).

    This is used by the voice UI to:
      - Run transcription + LLM agent + tools
      - Read structured outputs from ToolOutputStore (no regex parsing!)
    and then hand off to generate_turn_media() for the slow TTS/image work.
    
    Tool outputs (audio paths, scene briefs, actions) are stored in ToolOutputStore
    by the tools themselves, and read here without any regex parsing.

    Returns:
        Tuple of (clean_response, speaker_name, state, actions_dict, audio_path_from_tool)
    """
    t_start = time.perf_counter()
    
    # Set current session for tool context (tools can access state securely)
    set_current_session(session_id)
    
    # Clear tool outputs from previous turn (fresh slate)
    clear_tool_outputs(session_id)
    
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
    
    # ========== ACCUSATION DETECTION ==========
    # Detect accusations and rewrite message to be explicit so LLM routes to make_accusation tool
    accused_suspect = None
    if state.mystery:  # Only check for accusations if mystery is loaded
        if action_type == "accuse" and target:
            # Explicit accuse action - find the suspect name
            for s in state.mystery.suspects:
                if s.name.lower() == target.lower() or target.lower() in s.name.lower():
                    accused_suspect = s.name
                    break
            if not accused_suspect:
                accused_suspect = target
        elif action_type == "custom" and custom_message:
            # Check custom messages for accusation intent
            accused_suspect = _detect_accusation_intent(message, state)
    
    if accused_suspect:
        # Rewrite message to be explicit about accusation intent for the LLM
        original_message = message
        message = f"[FORMAL ACCUSATION] I formally accuse {accused_suspect} of the murder! Use the make_accusation tool. Original statement: {original_message}"
        logger.info("[GAME] Detected accusation against %s - rewrote message for agent", accused_suspect)
        # Update the stored player message
        if state.messages:
            state.messages[-1]["content"] = original_message  # Keep original for display

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
                perf.start("suspect_resolver", details="gpt-4o-mini")
                result = chain.invoke(
                    {
                        "suspect_list": suspects_summary,
                        "player_message": custom_message,
                    }
                )
                perf.end("suspect_resolver", details="resolved")
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
                perf.end("suspect_resolver", status="error", details="exception")
                logger.exception(
                    "Error resolving suspect name via AI; falling back to heuristics only"
                )

        # Final fallback: treat as follow-up to the last suspect who spoke,
        # as long as the message doesn't clearly mention a different suspect.
        if not suspect_to_assign and state.mystery:
            last_speaker = _get_last_suspect_speaker(state)
            if last_speaker:
                explicit_other = False
                for s in state.mystery.suspects:
                    if s.name == last_speaker:
                        continue
                    if s.name.lower() in message_lower:
                        explicit_other = True
                        break
                if not explicit_other:
                    for s in state.mystery.suspects:
                        if s.name == last_speaker:
                            suspect_to_assign = s
                            logger.info(
                                "Assuming follow-up question to last suspect speaker: %s",
                                last_speaker,
                            )
                            break

    # Perf: measure how long suspect resolution (heuristics + resolver) took
    # (t_resolve_start is captured just before heuristics; if we didn't set it, this is a no-op)
    try:
        t_resolve_end = time.perf_counter()
        if "t_resolve_start" in locals():
            logger.info(
                "[PERF] run_action_logic: suspect resolution took %.2fs",
                t_resolve_end - t_resolve_start,
            )
    except Exception:
        logger.exception("[PERF] Failed to log suspect resolution timing")

    if suspect_to_assign and not suspect_to_assign.voice_id:
        logger.info("Assigning voice on-demand for suspect: %s", suspect_to_assign.name)
        used_voice_ids = [
            s.voice_id
            for s in state.mystery.suspects
            if s.voice_id and s.name != suspect_to_assign.name
        ]
        assign_voice_to_suspect(suspect_to_assign, used_voice_ids)

    # As in process_player_action, if this is a custom message and we resolved
    # a suspect, rewrite the message to make that intent explicit so the agent
    # reliably calls the interrogate_suspect tool for follow-ups.
    if action_type == "custom" and custom_message and suspect_to_assign:
        message = (
            f"I want to talk to {suspect_to_assign.name}. "
            f"Here's what I say to them: {custom_message}"
        )
        try:
            if state.messages:
                state.messages[-1]["content"] = message
        except Exception:
            logger.exception(
                "[GAME] Failed to update stored custom message content on state (fast path)"
            )

    # Kick off background portrait generation for this suspect so it can
    # complete while the agent + tools are running. This reduces the time
    # we wait in Stage 2 media generation before the portrait is available.
    if suspect_to_assign and state.mystery:
        try:
            session_images = mystery_images.get(session_id, {})
            if suspect_to_assign.name not in session_images:
                mystery_setting = state.mystery.setting if state.mystery else ""
                logger.info(
                    "[GAME] Pre-warming portrait in background for suspect: %s",
                    suspect_to_assign.name,
                )
                threading.Thread(
                    target=_generate_portrait_background,
                    args=(
                        suspect_to_assign.name,
                        suspect_to_assign,
                        mystery_setting,
                        session_id,
                    ),
                    daemon=True,
                ).start()
        except Exception:
            logger.exception(
                "[GAME] Failed to start background portrait generation for %s",
                getattr(suspect_to_assign, "name", "unknown"),
            )

    # Get or create agent
    if not hasattr(run_action_logic, "agent"):
        run_action_logic.agent = create_game_master_agent()

    # Update system prompt (will include newly assigned voice_id if any)
    state.system_prompt = state.get_continue_prompt()

    # Process with agent (Game Master + tools) - TRACKED
    perf.start("gameplay_agent", details=f"action={action_type}")
    t_agent_start = time.perf_counter()
    response, speaker = process_message(
        run_action_logic.agent,
        message,
        state.system_prompt,
        session_id,
        thread_id=session_id,
    )
    t_agent_end = time.perf_counter()
    perf.end("gameplay_agent", details=f"{len(response)} chars, speaker={speaker}")
    logger.info(
        "[PERF] run_action_logic: agent + tools took %.2fs",
        t_agent_end - t_agent_start,
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
    t_parse_start = time.perf_counter()
    actions = parse_game_actions(message, response, state)
    t_parse_end = time.perf_counter()
    logger.info(
        "[PERF] run_action_logic: parse_game_actions took %.2fs",
        t_parse_end - t_parse_start,
    )

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

    # ========== Structured Tool Outputs (No Regex!) ==========
    # Tools store their outputs in ToolOutputStore, we just read from it
    tool_store = get_tool_output_store(session_id)
    
    # Get audio path from tool store (no regex parsing needed!)
    audio_path_from_tool = tool_store.audio_path
    if audio_path_from_tool:
        logger.info("[GAME] Audio path from ToolOutputStore: %s", audio_path_from_tool)
    
    # Get scene brief from tool store (no regex parsing needed!)
    clean_response = response
    if tool_store.scene_brief:
        sb = tool_store.scene_brief
        logger.info("[GAME] Scene brief from ToolOutputStore: location=%s, clue_focus=%s", 
                    sb.location_name, sb.clue_focus[:50] if sb.clue_focus else "none")
        
        # Convert to dict format and process (stores in state.location_descriptions)
        scene_brief_dict = {
            "location_name": sb.location_name,
            "clue_focus": sb.clue_focus,
            "camera_angle": sb.camera_angle,
            "lighting_mood": sb.lighting_mood,
            "background_hint": sb.background_hint,
            "prompt_hint": sb.prompt_hint,
        }
        _process_scene_brief(scene_brief_dict, state)
    
    # Merge tool store actions into parsed actions
    # Tool store values take precedence over parser-detected values
    if tool_store.location_searched:
        tool_location = tool_store.location_searched
        parser_location = actions.get("location_searched")
        
        # If parser detected a different location, replace it in state.searched_locations
        if parser_location and parser_location != tool_location:
            if parser_location in state.searched_locations:
                state.searched_locations.remove(parser_location)
                logger.info("[GAME] Replaced parser location '%s' with tool location '%s'", 
                           parser_location, tool_location)
        
        # Ensure the tool store location is in searched_locations
        if tool_location not in state.searched_locations:
            state.searched_locations.append(tool_location)
        
        actions["location_searched"] = tool_location
    
    if tool_store.clue_found:
        actions["clue_found"] = tool_store.clue_found
        clue_id = tool_store.clue_found
        
        # Add clue to game state and RAG memory
        if state and state.mystery:
            for clue in state.mystery.clues:
                if clue.id == clue_id:
                    # Add to game state (tracks discovered clues for investigation log)
                    state.add_clue(clue.id, clue.description)
                    logger.info("[CLUE] ✅ Added to investigation log: %s at %s", 
                                clue.id, clue.location)
                    
                    # Add to RAG memory for semantic search
                    from services.game_memory import get_game_memory
                    memory = get_game_memory()
                    if memory.is_available:
                        memory.add_clue(
                            clue_id=clue.id,
                            description=clue.description,
                            location=clue.location,
                            significance=clue.significance,
                            turn=state.current_turn
                        )
                        logger.info("[RAG] Indexed clue %s for semantic search", clue.id)
                    break
    
    if tool_store.accusation:
        actions["accusation"] = tool_store.accusation.suspect_name
        actions["accusation_correct"] = tool_store.accusation.is_correct
        actions["accusation_has_evidence"] = tool_store.accusation.has_sufficient_evidence
        
        # Apply accusation result to game state
        # Only count accusations that had sufficient evidence
        if tool_store.accusation.has_sufficient_evidence:
            if tool_store.accusation.is_correct:
                state.won = True
                state.game_over = True
                logger.info("✅ CORRECT ACCUSATION with evidence! Player wins!")
            else:
                state.wrong_accusations += 1
                logger.info(
                    "❌ Wrong accusation: %s (attempt %d/3)",
                    tool_store.accusation.suspect_name,
                    state.wrong_accusations
                )
                if state.wrong_accusations >= 3:
                    state.game_over = True
                    logger.info("💀 3 wrong accusations - GAME OVER!")
        else:
            logger.info(
                "⚠️ Accusation rejected - insufficient evidence (%d clues found)",
                tool_store.accusation.clues_found_count
            )

    # Remove game state markers from response (SEARCHED, ACCUSATION, CLUE_FOUND)
    t_clean_start = time.perf_counter()
    clean_response = clean_response_markers(clean_response)

    # AI Enhancement Phase 1: Record interrogation and update emotional state
    # This must happen after we have clean_response but before storing the message
    if speaker and speaker != "Game Master":
        t_record_start = time.perf_counter()
        _record_interrogation(state, speaker, message, clean_response)
        t_record_end = time.perf_counter()
        logger.info(
            "[PERF] run_action_logic: _record_interrogation took %.2fs",
            t_record_end - t_record_start,
        )

    t_clean_end = time.perf_counter()
    logger.info(
        "[PERF] run_action_logic: clean/markers + scene-brief handling took %.2fs",
        t_clean_end - t_clean_start,
    )

    # Store assistant message (text only)
    state.messages.append(
        {
            "role": "assistant",
            "content": clean_response,
            "speaker": speaker or "Game Master",
        }
    )

    t_end = time.perf_counter()
    logger.info(
        "[PERF] run_action_logic: total internal time %.2fs",
        t_end - t_start,
    )

    return clean_response, speaker or "Game Master", state, actions, audio_path_from_tool


# def generate_turn_media(
#     clean_response: str,
#     speaker: str,
#     state: GameState,
#     actions: Dict,
#     audio_path_from_tool: Optional[str],
#     session_id: str,
#     background_images: bool = True,
# ) -> Tuple[Optional[str], Optional[List[Dict]]]:
#     """Re-exported from game_media for backwards compatibility."""
#     from game_media import generate_turn_media as _impl

#     return _impl(
#         clean_response,
#         speaker,
#         state,
#         actions,
#         audio_path_from_tool,
#         session_id,
#         background_images,
#     )
