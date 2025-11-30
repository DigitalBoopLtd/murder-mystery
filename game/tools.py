"""Tools for the game master agent."""

import json
import logging
import os
import re
import tempfile
from typing import Annotated, Optional, List
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from services.tts_service import text_to_speech
from services.game_memory import get_game_memory

logger = logging.getLogger(__name__)

# Directory for storing generated audio files
AUDIO_DIR = os.path.join(tempfile.gettempdir(), "murder_mystery_audio")
os.makedirs(AUDIO_DIR, exist_ok=True)


# =============================================================================
# TOOL PREREQUISITE VALIDATION
# =============================================================================
# Pattern for handling tools that need data which may not be ready yet.
# Returns helpful messages or waits for data to become available.

import time as _time

class ToolPrerequisiteError(Exception):
    """Raised when a tool's prerequisites are not met."""
    def __init__(self, message: str, can_retry: bool = True, wait_hint: str = None):
        self.message = message
        self.can_retry = can_retry
        self.wait_hint = wait_hint
        super().__init__(message)


def wait_for_mystery_ready(timeout_seconds: float = 10.0, poll_interval: float = 0.5) -> bool:
    """Wait for the mystery to be fully generated.
    
    Args:
        timeout_seconds: Maximum time to wait
        poll_interval: How often to check
        
    Returns:
        True if mystery became ready, False if timeout
    """
    from game.state_manager import get_game_state
    
    elapsed = 0.0
    while elapsed < timeout_seconds:
        state = get_game_state()
        if state and state.mystery and state.mystery_ready:
            return True
        _time.sleep(poll_interval)
        elapsed += poll_interval
        logger.info("[TOOL] Waiting for mystery to be ready... (%.1fs)", elapsed)
    
    return False


def validate_tool_prerequisites(
    tool_name: str,
    requires_mystery: bool = True,
    requires_suspect: str = None,
    auto_wait: bool = True,
    wait_timeout: float = 10.0,
) -> tuple[bool, Optional[str]]:
    """Validate that prerequisites for a tool are met.
    
    Args:
        tool_name: Name of the tool (for logging)
        requires_mystery: Whether the tool needs the mystery to be ready
        requires_suspect: If set, validates this suspect exists
        auto_wait: If True, wait for missing prerequisites
        wait_timeout: How long to wait for prerequisites
        
    Returns:
        (success, error_message) - if success is False, error_message explains why
    """
    from game.state_manager import get_game_state
    
    state = get_game_state()
    
    # Check 1: Do we have a game state at all?
    if not state:
        return False, (
            "🎮 No game in progress. Please start a new game first by saying "
            "'Start a new game' or clicking the Start button."
        )
    
    # Check 2: Is the mystery ready?
    if requires_mystery:
        if not state.mystery:
            if auto_wait:
                logger.info("[TOOL] %s: Mystery not ready, waiting...", tool_name)
                if wait_for_mystery_ready(timeout_seconds=wait_timeout):
                    # Refresh state after waiting
                    state = get_game_state()
                else:
                    return False, (
                        "⏳ The case details are still being prepared. "
                        "Please wait a moment and try again. "
                        "The suspects and clues are being finalized..."
                    )
            else:
                return False, (
                    "⏳ The investigation hasn't fully begun yet. "
                    "The case file is still being assembled. Please wait a moment."
                )
        
        if not getattr(state, 'mystery_ready', False):
            if auto_wait:
                logger.info("[TOOL] %s: Mystery exists but not marked ready, waiting...", tool_name)
                if wait_for_mystery_ready(timeout_seconds=wait_timeout):
                    state = get_game_state()
                else:
                    return False, (
                        "⏳ Almost ready! The final details of the case are being prepared. "
                        "Try again in a few seconds."
                    )
            else:
                return False, (
                    "⏳ The investigation is almost ready. Please wait a moment."
                )
    
    # Check 3: Does the specified suspect exist?
    if requires_suspect and state.mystery:
        suspect_found = False
        for s in state.mystery.suspects:
            if s.name.lower() == requires_suspect.lower() or requires_suspect.lower() in s.name.lower():
                suspect_found = True
                break
        
        if not suspect_found:
            suspect_names = [s.name for s in state.mystery.suspects]
            return False, (
                f"🔍 I couldn't find a suspect named '{requires_suspect}'. "
                f"The suspects in this case are: {', '.join(suspect_names)}. "
                f"Please specify one of these names."
            )
    
    return True, None

# Global dict to store alignment data for tool-generated audio
# Key: audio_path, Value: alignment_data list
_audio_alignment_cache = {}


# =============================================================================
# LOCATION & SECRET REVEAL CRITERIA
# =============================================================================
# Different unlock conditions for locations vs secrets:
# - LOCATIONS: Trust or nervousness based (no brute force)
# - SECRETS: Relevant questions, emotional states, or random chance
# - MURDERER: Harder to crack, lies more, deflects

import random

def should_reveal_location(suspect_state, is_guilty: bool = False) -> tuple[bool, str]:
    """Check if suspect should reveal their location hint.
    
    SIMPLIFIED RULES (single criterion):
    - Innocent: reveal ONLY when TRUST is high enough
    - Murderer: reveal ONLY when TRUST is VERY high
    
    This makes testing and reasoning about reveals much easier.
    """
    if suspect_state is None:
        return False, "no_state"
    
    trust = suspect_state.trust
    
    # Murderer is harder to crack - requires very high trust
    if is_guilty:
        threshold = 85
        if trust >= threshold:
            return True, f"MURDERER_TRUST (trust={trust}% >= {threshold}%)"
        return False, f"murderer_not_ready (trust={trust}%/{threshold}%)"
    
    # Innocent suspects: single path - high trust only
    threshold = 70
    if trust >= threshold:
        return True, f"TRUST (trust={trust}% >= {threshold}%)"
    
    return False, f"not_ready (trust={trust}%/{threshold}%)"


def should_reveal_secret(suspect_state, player_question: str, is_guilty: bool = False) -> tuple[bool, str]:
    """Check if suspect should reveal their secret/motive.
    
    SIMPLIFIED RULES (single criterion):
    - Innocent: reveal ONLY when TRUST is high *and* the player asks a PROBING question
    - Murderer: reveal ONLY when NERVOUSNESS is very high *and* they've been caught in CONTRADICTIONS
    
    No random chance, no multiple OR paths.
    """
    if suspect_state is None:
        return False, "no_state"
    
    question_lower = player_question.lower()
    trust = suspect_state.trust
    nervousness = suspect_state.nervousness
    contradictions = suspect_state.contradictions_caught
    
    # Check if question is probing for motive/secrets
    motive_keywords = ["why", "motive", "reason", "relationship", "feel about", 
                       "hate", "love", "angry", "jealous", "money", "inherit",
                       "affair", "secret", "hiding", "truth", "really"]
    matched_keywords = [kw for kw in motive_keywords if kw in question_lower]
    is_probing_question = len(matched_keywords) > 0
    
    # Murderer: single strict path
    if is_guilty:
        nerv_threshold = 90
        needed_contradictions = 2
        if nervousness >= nerv_threshold and contradictions >= needed_contradictions:
            return True, (
                f"MURDERER_CRACKED (nervousness={nervousness}% >= {nerv_threshold}% "
                f"AND contradictions={contradictions} >= {needed_contradictions})"
            )
        return False, (
            f"murderer_not_ready (nervousness={nervousness}%/{nerv_threshold}%, "
            f"contradictions={contradictions}/{needed_contradictions})"
        )
    
    # Innocent suspects: single path - high trust + probing question
    trust_threshold = 60
    if trust >= trust_threshold and is_probing_question:
        return True, (
            f"TRUST+PROBING (trust={trust}% >= {trust_threshold}%, "
            f"keywords={matched_keywords})"
        )
    
    return False, (
        f"not_ready (trust={trust}%/{trust_threshold}%, probing={is_probing_question}, "
        f"keywords={matched_keywords})"
    )


def get_reveal_reason(suspect_state, is_guilty: bool = False) -> str:
    """Get the reason why a location was revealed (for logging/debugging)."""
    if suspect_state is None:
        return "unknown"
    
    reasons = []
    
    if is_guilty:
        if suspect_state.nervousness >= 85:
            reasons.append(f"murderer_cracked({suspect_state.nervousness}%)")
        if suspect_state.contradictions_caught >= 2:
            reasons.append(f"murderer_caught({suspect_state.contradictions_caught})")
    else:
        if suspect_state.trust >= 65:
            reasons.append(f"high_trust({suspect_state.trust}%)")
        if suspect_state.nervousness >= 75:
            reasons.append(f"high_nervousness({suspect_state.nervousness}%)")
        if suspect_state.contradictions_caught >= 1:
            reasons.append(f"caught_contradiction({suspect_state.contradictions_caught})")
    
    return " + ".join(reasons) if reasons else "conditions_not_met"


@tool
def interrogate_suspect(
    suspect_name: Annotated[str, "The full name of the suspect to interrogate"],
    player_question: Annotated[str, "The player's question or statement to the suspect"],
    emotional_context: Annotated[
        str,
        "Current emotional state and conversation history: trust %, nervousness %, past exchanges"
    ] = "",
) -> str:
    """Interrogate Suspect - Use when player wants to talk to a suspect.
    
    Just provide:
    1) suspect_name - full name (the tool looks up their secrets internally)
    2) player_question - what the player said
    3) emotional_context - current trust/nervousness and conversation history
    
    Returns only the narrative. Structured data (audio path, speaker) stored in ToolOutputStore.
    
    This tool uses RAG memory to maintain consistency - suspects remember past conversations."""

    import time
    t_start = time.perf_counter()
    
    logger.info("\n%s", "=" * 60)
    logger.info("INTERROGATE_SUSPECT TOOL CALLED")
    logger.info("Suspect: %s", suspect_name)
    logger.info("Player question: %s", player_question)
    logger.info("Emotional context: %s", emotional_context[:200] if emotional_context else "None")
    logger.info("%s\n", "=" * 60)
    
    # =========================================================================
    # PREREQUISITE VALIDATION - Ensure we have the data we need
    # Will wait up to 10s for mystery to be ready, then fail gracefully
    # =========================================================================
    prereq_ok, prereq_error = validate_tool_prerequisites(
        tool_name="interrogate_suspect",
        requires_mystery=True,
        requires_suspect=suspect_name,
        auto_wait=True,
        wait_timeout=10.0,
    )
    if not prereq_ok:
        logger.warning("[TOOL] Prerequisite check failed: %s", prereq_error)
        return prereq_error
    
    # Import here to avoid circular imports
    from game.state_manager import get_game_state, get_tool_output_store, InterrogationOutput
    
    state = get_game_state()
    store = get_tool_output_store()
    
    # =========================================================================
    # STAGE 1: LOOKUP SUSPECT (~0ms)
    # =========================================================================
    t1 = time.perf_counter()
    suspect = None
    voice_id = None
    if state and state.mystery:
        for s in state.mystery.suspects:
            if s.name.lower() == suspect_name.lower() or suspect_name.lower() in s.name.lower():
                suspect = s
                voice_id = s.voice_id
                break
    t1_end = time.perf_counter()
    logger.info("⏱️ [PERF] Stage 1 - Lookup suspect: %.0fms", (t1_end - t1) * 1000)
    
    # This should never happen now due to prerequisite check, but keep as safety
    if not suspect:
        logger.warning("Suspect not found: %s", suspect_name)
        return f"I'm sorry, I couldn't find a suspect named {suspect_name}."
    
    # =========================================================================
    # STAGE 2: RAG MEMORY LOOKUP (~50-200ms)
    # This gives the suspect "memory" of past conversations for consistency
    # =========================================================================
    t2 = time.perf_counter()
    memory = get_game_memory()
    past_conversations = ""
    relevant_statements = ""
    
    if memory.is_available:
        # Get ALL past conversations with this suspect (chronological)
        history = memory.get_suspect_history(suspect.name)
        if history:
            past_convos = []
            for conv in history[-5:]:  # Last 5 exchanges max
                q = conv.get("question", "")[:100]
                a = conv.get("answer", "")[:150]
                turn = conv.get("turn", "?")
                past_convos.append(f"Turn {turn}: Player asked: \"{q}\" → You said: \"{a}\"")
            past_conversations = "\n".join(past_convos)
            logger.info("[RAG] Found %d past conversations with %s", len(history), suspect.name)
        
        # Search for statements RELATED to current question (semantic search)
        related = memory.search_by_suspect(suspect.name, player_question, k=3)
        if related:
            statements = []
            for text, meta in related:
                answer = meta.get("answer", "")
                if answer:
                    statements.append(f"- \"{answer[:150]}\"")
            if statements:
                relevant_statements = "\n".join(statements)
                logger.info("[RAG] Found %d relevant past statements", len(statements))
    
    # Build memory context for prompt
    memory_context = ""
    if past_conversations:
        memory_context += f"""
## YOUR PAST STATEMENTS TO THIS DETECTIVE
(Maintain consistency! Reference these naturally.)
{past_conversations}
"""
    if relevant_statements:
        memory_context += f"""
## YOUR STATEMENTS RELATED TO THIS TOPIC
You may have said something about this before - stay consistent:
{relevant_statements}
"""
    t2_end = time.perf_counter()
    logger.info("⏱️ [PERF] Stage 2 - RAG memory lookup: %.0fms", (t2_end - t2) * 1000)
    
    # =========================================================================
    # STAGE 3: EMOTIONAL STATE UPDATE (~0ms)
    # This ensures the current question's impact is considered for reveals
    # =========================================================================
    t3 = time.perf_counter()
    suspect_state = state.get_suspect_state(suspect.name) if state else None
    
    if suspect_state and state:
        # Analyze question style to determine emotional impact
        question_lower = player_question.lower()
        trust_delta = 0
        nervousness_delta = 0
        
        # Aggressive/accusatory language decreases trust, increases nervousness
        aggressive_words = ["liar", "lying", "killed", "murder", "guilty", "confess",
                          "admit", "truth", "suspicious", "caught", "evidence against",
                          "you did it", "accuse", "blame"]
        for word in aggressive_words:
            if word in question_lower:
                trust_delta -= 5
                nervousness_delta += 10
                break
        
        # Friendly/empathetic language increases trust, decreases nervousness
        friendly_words = ["help", "understand", "sorry", "difficult", "must be hard",
                        "appreciate", "thank", "please", "kind", "trust you"]
        for word in friendly_words:
            if word in question_lower:
                trust_delta += 5
                nervousness_delta -= 5
                break
        
        # Direct confrontation with evidence increases nervousness
        confrontation_phrases = ["but you said", "you told me", "earlier you", "contradict",
                                "that doesn't match", "someone saw you", "witness"]
        for phrase in confrontation_phrases:
            if phrase in question_lower:
                nervousness_delta += 15
                break
        
        # Apply emotional changes BEFORE unlock check
        if trust_delta != 0 or nervousness_delta != 0:
            state.update_suspect_emotion(
                suspect.name,
                trust_delta=trust_delta,
                nervousness_delta=nervousness_delta
            )
            logger.info(
                "[EMOTION] Updated %s: trust=%d%% (%+d), nervousness=%d%% (%+d) (before unlock check)",
                suspect.name, suspect_state.trust, trust_delta, suspect_state.nervousness, nervousness_delta
            )
        
        # Record this conversation BEFORE unlock check (so conversation count is current)
        suspect_state.conversations.append({
            "question": player_question,
            "answer": "[pending]",  # Will be updated after LLM response
            "turn": state.current_turn
        })
    
    # SECURE: Location and secret reveals are decided by the Oracle
    # The Oracle has access to suspect.isGuilty internally - we don't access it here
    # This prevents the GM agent from ever knowing who is guilty
    will_reveal_location = False
    location_reveal_reason = "pending_oracle"
    will_reveal_secret = False
    secret_reveal_reason = "pending_oracle"
    
    # Log current state for debugging (without revealing guilt status)
    if suspect_state:
        logger.info("📊 [STATE] %s - trust: %d%%, nervousness: %d%%, conversations: %d",
                   suspect.name, suspect_state.trust, suspect_state.nervousness, 
                   len(suspect_state.conversations))
        if suspect_state.secret_revealed:
            logger.info("✓ [SECRET] %s already revealed their secret previously", suspect.name)
    t3_end = time.perf_counter()
    logger.info("⏱️ [PERF] Stage 3 - Emotional state update: %.0fms", (t3_end - t3) * 1000)
    
    # =========================================================================
    # STAGE 4: ORACLE RESPONSE GENERATION (~2-4s - main bottleneck)
    # The Oracle has full truth but only returns the roleplay response
    # This ensures the GM agent NEVER sees secrets, guilt status, etc.
    # =========================================================================
    t4 = time.perf_counter()
    from services.mystery_oracle import get_mystery_oracle, SuspectResponseRequest
    
    oracle = get_mystery_oracle()
    
    if oracle.is_initialized:
        # Use the Oracle for response generation - it knows the truth internally
        # but only returns the narrative response
        logger.info("[ORACLE] Delegating response generation to MysteryOracle")
        
        # Build conversation history from memory
        conversation_history = []
        if memory.is_available:
            history = memory.get_suspect_history(suspect.name)
            for conv in history[-5:]:
                conversation_history.append({
                    "question": conv.get("question", ""),
                    "answer": conv.get("answer", ""),
                })
        
        # Create request with ONLY what the GM agent should know
        request = SuspectResponseRequest(
            suspect_name=suspect.name,
            player_question=player_question,
            conversation_history=conversation_history,
            trust_level=suspect_state.trust if suspect_state else 50,
            nervousness_level=suspect_state.nervousness if suspect_state else 30,
            contradictions_caught=suspect_state.contradictions_caught if suspect_state else 0,
        )
        
        # Oracle generates response internally using full truth
        # Returns ONLY the response text + game state deltas
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        oracle.generate_suspect_response(request)
                    )
                    oracle_result = future.result()
            else:
                oracle_result = loop.run_until_complete(
                    oracle.generate_suspect_response(request)
                )
        except RuntimeError:
            oracle_result = asyncio.run(oracle.generate_suspect_response(request))
        
        text_response = oracle_result.response_text
        
        # Update will_reveal flags based on Oracle's decision
        if oracle_result.revealed_location_hint:
            will_reveal_location = True
            location_reveal_reason = "oracle_decided"
        if oracle_result.revealed_secret:
            will_reveal_secret = True
            secret_reveal_reason = "oracle_decided"
        
        t4_oracle_end = time.perf_counter()
        logger.info("⏱️ [PERF] Stage 4a - Oracle LLM call: %.0fms", (t4_oracle_end - t4) * 1000)
        logger.info("[ORACLE] Response generated (trust_delta=%d, nervousness_delta=%d, location=%s, secret=%s)",
                   oracle_result.trust_delta, oracle_result.nervousness_delta,
                   oracle_result.revealed_location_hint, oracle_result.revealed_secret)
    else:
        # SECURE: Oracle not initialized - this should NOT happen in normal gameplay
        # Return an error rather than falling back to insecure legacy code
        logger.error("[ORACLE] MysteryOracle not initialized - cannot generate secure response")
        return "I'm sorry, I'm having trouble thinking right now. Please try again in a moment."
    
    # REMOVED: Legacy fallback that exposed suspect.isGuilty
    # The Oracle is now REQUIRED for all suspect interactions
    # This block is kept as a comment to show what was removed for security:
    #
    # SECURITY ISSUE: The legacy code included:
    # - full_profile with "Guilty: {suspect.isGuilty}"
    # - Murder details if suspect.isGuilty
    # This leaked truth to the GM agent's context
    
    # Placeholder to maintain code structure
    if False:  # Never executed - keeping for reference only
        llm = ChatOpenAI(
            model="gpt-4o", temperature=0.8, api_key=os.getenv("OPENAI_API_KEY")
        )

        # Legacy code removed for security - see comment above
        pass
    
    t4_end = time.perf_counter()
    logger.info("⏱️ [PERF] Stage 4 - Response generation total: %.0fms", (t4_end - t4) * 1000)
    
    # Update the "[pending]" answer we recorded earlier with the actual response
    if suspect_state and suspect_state.conversations:
        suspect_state.conversations[-1]["answer"] = text_response[:200]  # Truncate for storage
        state.current_turn += 1  # Increment turn counter

    # =========================================================================
    # STAGE 5: TTS AUDIO GENERATION (~1-3s)
    # =========================================================================
    t5 = time.perf_counter()
    audio_path = None
    alignment_data = None
    if voice_id:
        logger.info("[INTERROGATE DEBUG] Generating audio for text: %s...", text_response[:100])
        audio_path, alignment_data = generate_suspect_audio(text_response, voice_id, suspect.name)
        if alignment_data:
            first_words = [w.get("word", "?") for w in alignment_data[:5]]
            logger.info("[INTERROGATE DEBUG] Alignment first 5 words: %s", first_words)
    t5_end = time.perf_counter()
    logger.info("⏱️ [PERF] Stage 5 - TTS generation: %.0fms%s", 
               (t5_end - t5) * 1000,
               "" if voice_id else " (skipped - no voice)")

    # Store structured data in ToolOutputStore (no markers!)
    store.interrogation = InterrogationOutput(
        suspect_name=suspect.name,
        response_text=text_response,
        emotional_state=emotional_context[:100] if emotional_context else None,
    )
    if audio_path:
        store.audio_path = audio_path
        # Store alignment data directly in ToolOutputStore for reliable retrieval
        store.audio_alignment_data = alignment_data
    
    # Unlock the location this suspect knows about (if criteria were met earlier)
    # We already checked will_reveal_location before generating the response
    location_unlocked = None
    if suspect.location_hint and suspect_state and will_reveal_location:
        newly_unlocked = state.unlock_location(suspect.location_hint)
        if newly_unlocked:
            location_unlocked = suspect.location_hint
            store.location_unlocked = location_unlocked
            logger.info(
                "🔓 [LOCATION UNLOCKED] %s revealed: %s (reason: %s)",
                suspect.name, location_unlocked, location_reveal_reason
            )
    
    # Mark secret as revealed if it was included in this response
    # (we already checked will_reveal_secret before generating the response)
    if will_reveal_secret and suspect_state:
        suspect_state.secret_revealed = True
        store.secret_revealed = suspect.secret
        store.secret_revealed_by = suspect.name
        logger.info(
            "🔓 [SECRET UNLOCKED] %s revealed: '%s...' (reason: %s)",
            suspect.name, suspect.secret[:50], secret_reveal_reason
        )
    
    logger.info("Interrogation stored: suspect=%s, audio=%s, alignment=%d words, memory_used=%s, location_unlocked=%s, secret_revealed=%s", 
                suspect.name, bool(audio_path), len(alignment_data) if alignment_data else 0,
                bool(past_conversations or relevant_statements), location_unlocked,
                suspect_state.secret_revealed if suspect_state else False)

    # =========================================================================
    # STAGE 6: ADD TO INVESTIGATION TIMELINE
    # Extract alibi/witness info for the player's timeline visualization
    # =========================================================================
    if state and suspect:
        # Add alibi claim to timeline if suspect has structured alibi
        if suspect.structured_alibi and suspect_state and len(suspect_state.conversations) == 1:
            # First conversation - add their alibi claim
            alibi = suspect.structured_alibi
            time_slot = alibi.time_claimed.split("-")[0].strip() if "-" in alibi.time_claimed else alibi.time_claimed
            state.add_timeline_event(
                time_slot=time_slot,
                event_type="alibi_claim",
                description=f"Claims: \"{suspect.alibi}\" at {alibi.location_claimed}",
                suspect_name=suspect.name,
                source=f"Interview with {suspect.name}",
                is_verified=False,  # Not verified until corroborated
            )
            logger.info("📅 [TIMELINE] Added alibi claim for %s: %s", suspect.name, alibi.location_claimed)
        
        # Add witness statements to timeline
        if suspect.witness_statements:
            for ws in suspect.witness_statements:
                if ws.claim and suspect_state and len(suspect_state.conversations) <= 2:
                    # Add witness sighting on early conversations
                    state.add_timeline_event(
                        time_slot=ws.time_of_sighting or "Around 9 PM",
                        event_type="witness_sighting",
                        description=f"{suspect.name} says: \"{ws.claim}\"",
                        suspect_name=ws.subject,
                        source=f"Witness: {suspect.name}",
                        is_verified=ws.is_truthful,
                    )
                    logger.info("📅 [TIMELINE] Added witness sighting by %s about %s", suspect.name, ws.subject)

    # =========================================================================
    # PERFORMANCE SUMMARY
    # =========================================================================
    t_end = time.perf_counter()
    total_ms = (t_end - t_start) * 1000
    logger.info("=" * 60)
    logger.info("⏱️ [PERF] INTERROGATION COMPLETE - Total: %.0fms", total_ms)
    logger.info("⏱️ [PERF] Breakdown:")
    logger.info("⏱️ [PERF]   Stage 1 (Lookup):     %.0fms", (t1_end - t1) * 1000)
    logger.info("⏱️ [PERF]   Stage 2 (RAG):        %.0fms", (t2_end - t2) * 1000)
    logger.info("⏱️ [PERF]   Stage 3 (Emotional):  %.0fms", (t3_end - t3) * 1000)
    logger.info("⏱️ [PERF]   Stage 4 (LLM):        %.0fms", (t4_end - t4) * 1000)
    logger.info("⏱️ [PERF]   Stage 5 (TTS):        %.0fms", (t5_end - t5) * 1000)
    logger.info("=" * 60)

    # Return ONLY the narrative - no markers needed!
    return text_response


class SceneToolOutput(BaseModel):
    """Structured output from describe_scene_for_image tool.
    
    Using Pydantic model with LangChain's with_structured_output() 
    instead of regex parsing of markers.
    """
    spoken_narration: str = Field(description="2-3 sentences about finding the clue")
    clue_focus: str = Field(description="What the image should focus on - the clue itself")
    camera_angle: str = Field(description="Shot type: extreme close-up, close-up, medium, wide")
    lighting_mood: str = Field(description="Lighting style: dramatic, forensic, atmospheric, moody")
    background_hint: str = Field(default="", description="Location details visible in blurred background")
    prompt_hint: str = Field(default="", description="Additional image generation hints")


@tool
def describe_scene_for_image(
    location_name: Annotated[str, "Name of the location being searched (matches a SEARCHABLE LOCATION)"],
) -> str:
    """Search a location and reveal what the detective finds there.

    Just provide the location_name - the tool looks up clue details internally.
    
    The image will focus on the CLUE ITSELF (not just the location):
    - Close-up for documents, objects, and traces
    - Wide shot only for environment/scene clues
    
    Returns only the narrative text. Structured data is stored in ToolOutputStore.
    """
    logger.info("\n%s", "=" * 60)
    logger.info("DESCRIBE_SCENE_FOR_IMAGE TOOL CALLED")
    logger.info("Location: %s", location_name)
    logger.info("%s\n", "=" * 60)
    
    # =========================================================================
    # PREREQUISITE VALIDATION - Ensure we have the data we need
    # =========================================================================
    prereq_ok, prereq_error = validate_tool_prerequisites(
        tool_name="describe_scene_for_image",
        requires_mystery=True,
        auto_wait=True,
        wait_timeout=10.0,
    )
    if not prereq_ok:
        logger.warning("[TOOL] Prerequisite check failed: %s", prereq_error)
        return prereq_error
    
    # Import here to avoid circular imports
    from game.state_manager import get_game_state, get_tool_output_store, SceneBriefOutput
    
    state = get_game_state()
    store = get_tool_output_store()
    
    # Check if location is unlocked before allowing search
    if state and state.unlocked_locations:
        # Check if requested location matches any unlocked location (fuzzy match)
        location_lower = location_name.lower()
        is_unlocked = any(
            ul.lower() in location_lower or location_lower in ul.lower()
            for ul in state.unlocked_locations
        )
        if not is_unlocked:
            logger.warning("Location '%s' is not unlocked yet. Unlocked: %s", location_name, state.unlocked_locations)
            return f"You haven't learned about this location yet. Talk to suspects to discover searchable areas. Currently unlocked locations: {', '.join(state.unlocked_locations) if state.unlocked_locations else 'None'}"
    elif state and not state.unlocked_locations:
        # No locations unlocked yet
        logger.warning("No locations unlocked yet. Cannot search '%s'", location_name)
        return "You haven't discovered any searchable locations yet. Talk to the suspects - they may reveal places worth investigating."
    
    clue = None
    clue_description = "an empty area"
    clue_id = None
    clue_type = "environment"
    exact_location = location_name
    
    if state and state.mystery:
        # Find matching clue by location (fuzzy match)
        location_lower = location_name.lower()
        for c in state.mystery.clues:
            if c.location.lower() in location_lower or location_lower in c.location.lower():
                clue = c
                clue_description = c.description
                clue_id = c.id
                exact_location = c.location
                # Infer clue type from description
                desc_lower = c.description.lower()
                if any(w in desc_lower for w in ["letter", "note", "document", "paper", "file", "email", "message"]):
                    clue_type = "document"
                elif any(w in desc_lower for w in ["blood", "stain", "fingerprint", "footprint", "residue", "mark"]):
                    clue_type = "trace"
                elif any(w in desc_lower for w in ["room", "scene", "area", "space", "position"]):
                    clue_type = "environment"
                else:
                    clue_type = "object"
                logger.info("Matched location '%s' -> exact clue location '%s'", location_name, exact_location)
                break
    
    logger.info("Found clue: %s (type: %s) at '%s'", clue_id or "none", clue_type, exact_location)
    
    # Camera angle guidance based on clue type
    camera_guidance = {
        "document": "extreme close-up, document filling frame, dramatic lighting from above",
        "object": "close-up on the object, shallow depth of field, mysterious lighting",
        "trace": "macro close-up, forensic detail visible, stark lighting",
        "environment": "wide establishing shot, atmospheric, the scene tells a story"
    }
    suggested_camera = camera_guidance.get(clue_type, camera_guidance["object"])

    # Use LangChain's structured output - no regex needed!
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.7,
        api_key=os.getenv("OPENAI_API_KEY"),
    )
    
    # with_structured_output ensures we get a Pydantic model back
    structured_llm = llm.with_structured_output(SceneToolOutput)

    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a Game Master narrator + concept artist for a murder mystery game.

Your job is to:
1. Write SHORT spoken narration (2-3 sentences, ~50 words) about finding the CLUE
2. Design an image brief that FOCUSES ON THE CLUE, not the location

IMAGE RULES:
- The CLUE is the HERO of the image - it should be the visual focus
- Use the suggested camera angle for this clue type
- DOCUMENT clues: Extreme close-up, text partially visible, dramatic top lighting
- OBJECT clues: Close-up with shallow depth of field, isolated, moody lighting
- TRACE clues: Macro/forensic style, details crisp, clinical lighting
- ENVIRONMENT clues: Wide shot, room tells a story, atmospheric

NARRATION RULES:
- Write in ENGLISH, second person ("You notice...", "Something catches your eye...")
- Focus on the DISCOVERY moment
- Be atmospheric but brief"""),
        ("human", """LOCATION: {location_name}
CLUE FOUND: {clue_description}
CLUE TYPE: {clue_type}
SUGGESTED CAMERA: {suggested_camera}

Design an image that dramatically reveals this CLUE."""),
    ])

    chain = prompt | structured_llm
    
    try:
        # Structured output - no JSON parsing needed!
        result: SceneToolOutput = chain.invoke({
            "location_name": exact_location,
            "clue_description": clue_description,
            "clue_type": clue_type,
            "suggested_camera": suggested_camera,
        })
        
        logger.info("Structured output: clue_focus=%s, camera=%s", 
                    result.clue_focus[:50], result.camera_angle)
        
        # Store structured data in ToolOutputStore (no regex markers!)
        store.scene_brief = SceneBriefOutput(
            location_name=exact_location,
            clue_id=clue_id,
            clue_focus=result.clue_focus,
            camera_angle=result.camera_angle,
            lighting_mood=result.lighting_mood,
            background_hint=result.background_hint,
            prompt_hint=result.prompt_hint,
        )
        store.location_searched = exact_location
        if clue_id:
            store.clue_found = clue_id
        
        logger.info("Scene tool: stored in ToolOutputStore (location=%s, clue=%s)", 
                    exact_location, clue_id or "none")
        
        # Add clue to investigation timeline if it has timeline implications
        if state and clue and clue_id:
            # Check if clue has timeline implication
            if clue.timeline_implication:
                state.add_timeline_event(
                    time_slot="Evidence",  # Clues are evidence, not time-specific
                    event_type="clue_implication",
                    description=clue.timeline_implication,
                    suspect_name=clue.contradicts_alibi_of or clue.supports_alibi_of or "Unknown",
                    source=f"Found at {exact_location}",
                    is_verified=True,  # Physical evidence is verified
                )
                logger.info("📅 [TIMELINE] Added clue timeline implication: %s", clue.timeline_implication)
            
            # Check if clue contradicts an alibi
            if clue.contradicts_alibi_of:
                state.add_timeline_event(
                    time_slot="9:00 PM",  # Murder time
                    event_type="contradiction",
                    description=f"This clue contradicts {clue.contradicts_alibi_of}'s alibi!",
                    suspect_name=clue.contradicts_alibi_of,
                    source=f"Clue: {clue.description[:50]}...",
                    is_verified=True,
                )
                logger.info("📅 [TIMELINE] Added alibi contradiction for %s", clue.contradicts_alibi_of)
        
        # Return ONLY the narrative - no markers needed!
        return result.spoken_narration
        
    except Exception as e:
        logger.error("Structured output failed: %s", e)
        # Fallback - still store basic info
        store.location_searched = exact_location
        if clue_id:
            store.clue_found = clue_id
        return f"You search {exact_location} carefully."


def enhance_text_for_speech(text: str) -> str:
    """Enhance text with capitalization for emphasis for more engaging speech.

    Uses capitalization and punctuation cues instead of emotional tags
    (which would be spoken). Voice settings handle emotional delivery.
    """
    enhanced = text

    # Don't add emotional tags - they get spoken! Instead, use:
    # - Capitalization for emphasis
    # - Voice settings for emotional delivery
    # - Natural text cues (exclamation marks, question marks)

    # Capitalize key dramatic words for emphasis
    dramatic_words = [
        "suddenly",
        "immediately",
        "finally",
        "quickly",
        "carefully",
        "silently",
        "slowly",
        "quietly",
    ]
    for word in dramatic_words:
        pattern = r"\b" + re.escape(word) + r"\b"
        enhanced = re.sub(pattern, word.upper(), enhanced, flags=re.IGNORECASE)

    return enhanced


def generate_suspect_audio(
    text: str, voice_id: str, suspect_name: str
) -> tuple:
    """Generate audio for suspect response with alignment data.

    Args:
        text: The text to convert to speech
        voice_id: ElevenLabs voice ID
        suspect_name: Name of the suspect (for logging)

    Returns:
        Tuple of (audio_path, alignment_data) or (None, None) on error
    """
    try:
        # Enhance text with capitalization for emphasis
        enhanced_text = enhance_text_for_speech(text)

        # Use services.tts_service to get audio with alignment data
        audio_path, alignment_data = text_to_speech(
            enhanced_text, voice_id=voice_id, speaker_name=suspect_name
        )

        if audio_path:
            # Also store in legacy cache for backward compatibility
            _audio_alignment_cache[audio_path] = alignment_data
            if alignment_data:
                logger.info(
                    "Generated audio with %d word timestamps for %s: %s",
                    len(alignment_data),
                    suspect_name,
                    audio_path,
                )
            else:
                logger.info(
                    "Generated audio (no alignment data) for %s: %s",
                    suspect_name,
                    audio_path,
                )
            return audio_path, alignment_data
        else:
            logger.warning("Failed to generate audio for %s", suspect_name)
            return None, None

    except Exception as e:
        logger.error("Error generating audio: %s", e)
        return None, None


def get_audio_alignment_data(audio_path: str) -> Optional[list]:
    """Get alignment data for a tool-generated audio file.

    Args:
        audio_path: Path to audio file

    Returns:
        Alignment data list or None if not found
    """
    return _audio_alignment_cache.get(audio_path)


# ============================================================================
# RAG-Powered Tools (Phase 2 AI Enhancements)
# ============================================================================


@tool
def search_past_statements(
    query: Annotated[str, "What to search for in past conversations"],
    suspect_name: Annotated[
        Optional[str],
        "Optional: filter to statements from a specific suspect"
    ] = None,
) -> str:
    """Search all past conversations for relevant statements.
    
    Use this tool when:
    - Player references something a suspect said earlier
    - You need to check what was discussed about a topic
    - Reconstructing a timeline of events based on testimony
    - Player asks "didn't [suspect] say something about...?"
    
    Returns relevant past statements from the game's memory.
    """
    logger.info("\n%s", "=" * 60)
    logger.info("SEARCH_PAST_STATEMENTS TOOL CALLED")
    logger.info("Query: %s", query)
    logger.info("Suspect filter: %s", suspect_name or "None (all suspects)")
    logger.info("%s\n", "=" * 60)
    
    memory = get_game_memory()
    
    if not memory.is_available:
        return "No past conversations indexed yet. This is the first interrogation."
    
    try:
        if suspect_name:
            results = memory.search_by_suspect(suspect_name, query, k=5)
        else:
            results = memory.search(query, k=5, filter_type="conversation")
        
        if not results:
            if suspect_name:
                return f"No relevant statements found from {suspect_name}."
            return "No relevant statements found in past conversations."
        
        # Format results for the Game Master
        formatted = []
        for text, metadata in results:
            turn = metadata.get("turn", "?")
            speaker = metadata.get("suspect", "Unknown")
            formatted.append(f"[Turn {turn}] {speaker}: {text}")
        
        response = "Found the following relevant statements:\n\n" + "\n\n".join(formatted)
        logger.info("[RAG] search_past_statements returned %d results", len(results))
        return response
        
    except Exception as e:
        logger.error("[RAG] search_past_statements failed: %s", e)
        return "Error searching past statements. Please try again."


@tool
def find_contradictions(
    suspect_name: Annotated[str, "Name of the suspect to check"],
    new_statement: Annotated[str, "The suspect's new statement to check for contradictions"],
) -> str:
    """Check if a suspect's new statement contradicts their past statements.
    
    Use this tool when:
    - A suspect says something that might conflict with earlier testimony
    - Player accuses a suspect of lying
    - You want to verify consistency before proceeding
    
    Returns analysis of potential contradictions.
    """
    logger.info("\n%s", "=" * 60)
    logger.info("FIND_CONTRADICTIONS TOOL CALLED")
    logger.info("Suspect: %s", suspect_name)
    logger.info("New statement: %s", new_statement[:100] + "..." if len(new_statement) > 100 else new_statement)
    logger.info("%s\n", "=" * 60)
    
    memory = get_game_memory()
    
    if not memory.is_available:
        return "No past statements to compare against. This appears to be the suspect's first interrogation."
    
    try:
        # Find semantically similar past statements
        past_statements = memory.find_related_statements(suspect_name, new_statement, k=3)
        
        if not past_statements:
            return f"No previous statements from {suspect_name} found to compare against."
        
        # Use LLM to analyze for contradictions
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            api_key=os.getenv("OPENAI_API_KEY")
        )
        
        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                """You are analyzing testimony for contradictions in a murder mystery.
                
Compare the NEW STATEMENT against PAST STATEMENTS from the same suspect.
Identify any contradictions, inconsistencies, or suspicious changes in story.

Be specific about what contradicts what. Consider:
- Timeline inconsistencies
- Changed details (locations, times, people present)
- Contradictory claims about knowledge or actions
- Suspicious omissions or additions

If there's no contradiction, say so clearly."""
            ),
            (
                "human",
                """SUSPECT: {suspect_name}

NEW STATEMENT:
{new_statement}

PAST STATEMENTS:
{past_statements}

Analyze for contradictions:"""
            )
        ])
        
        chain = prompt | llm
        result = chain.invoke({
            "suspect_name": suspect_name,
            "new_statement": new_statement,
            "past_statements": "\n\n".join(past_statements)
        })
        
        analysis = result.content
        logger.info("[RAG] Contradiction analysis complete for %s", suspect_name)
        return analysis
        
    except Exception as e:
        logger.error("[RAG] find_contradictions failed: %s", e)
        return "Error analyzing contradictions. Please try again."


@tool
def get_cross_references(
    about_suspect: Annotated[str, "Name of the suspect you want to know about"],
) -> str:
    """Find what OTHER suspects have said about a specific suspect.
    
    Use this tool when:
    - Player wants to confront a suspect with what others said about them
    - You need to find alibis or accusations from other suspects
    - Building a case by cross-referencing testimony
    
    Returns statements from other suspects mentioning this person.
    """
    logger.info("\n%s", "=" * 60)
    logger.info("GET_CROSS_REFERENCES TOOL CALLED")
    logger.info("About suspect: %s", about_suspect)
    logger.info("%s\n", "=" * 60)
    
    memory = get_game_memory()
    
    if not memory.is_available:
        return "No cross-references available yet. Need more conversations first."
    
    try:
        cross_refs = memory.search_cross_references(about_suspect, k=5)
        
        if not cross_refs:
            return f"No other suspects have mentioned {about_suspect} yet."
        
        # Format for Game Master
        formatted = []
        for speaker, statement in cross_refs:
            formatted.append(f"• {speaker} said: {statement}")
        
        response = f"What others have said about {about_suspect}:\n\n" + "\n\n".join(formatted)
        logger.info("[RAG] Found %d cross-references about %s", len(cross_refs), about_suspect)
        return response
        
    except Exception as e:
        logger.error("[RAG] get_cross_references failed: %s", e)
        return "Error finding cross-references. Please try again."


@tool
def get_investigation_hint(
    current_situation: Annotated[str, "Brief description of where the player is stuck or what they're trying to figure out"],
) -> str:
    """Provide a hint to help the player progress in their investigation.
    
    Use this tool when:
    - Player explicitly asks for a hint or help
    - Player seems stuck and doesn't know what to do next
    - Player asks "what should I do?" or similar
    
    The hint will be based on what hasn't been explored yet and what
    evidence might be relevant.
    """
    logger.info("\n%s", "=" * 60)
    logger.info("GET_INVESTIGATION_HINT TOOL CALLED")
    logger.info("Situation: %s", current_situation)
    logger.info("%s\n", "=" * 60)
    
    memory = get_game_memory()
    
    # Gather investigation status from memory
    hints = []
    
    # Check what's been covered
    total_docs = len(memory.documents) if memory.is_available else 0
    conversations = [d for d in memory.documents if d.get("metadata", {}).get("type") == "conversation"] if memory.is_available else []
    
    suspects_talked = set()
    for doc in conversations:
        suspect = doc.get("metadata", {}).get("suspect")
        if suspect:
            suspects_talked.add(suspect)
    
    # Generate contextual hints
    if total_docs == 0:
        hints.append("The detective hasn't gathered any testimony yet. Consider talking to the suspects to learn about the victim and their relationships.")
    elif len(suspects_talked) < 2:
        hints.append(f"Only {len(suspects_talked)} suspect(s) have been interviewed. Talking to more suspects might reveal conflicting stories or new leads.")
    
    # If RAG is available, search for unresolved threads
    if memory.is_available and total_docs > 0:
        try:
            # Look for mentions of unverified claims
            unverified = memory.search("alibi claimed said they were", k=3, filter_type="conversation")
            if unverified:
                hints.append("Some alibis mentioned in testimony could be verified by questioning other suspects or searching locations.")
            
            # Look for relationship hints
            relationships = memory.search("relationship secret affair argument fight", k=2, filter_type="conversation")
            if relationships:
                hints.append("There are hints about relationships between suspects that might be worth exploring further.")
        except Exception as e:
            logger.warning("[HINT] RAG search failed: %s", e)
    
    if not hints:
        hints.append("Consider searching locations you haven't explored yet, or pressing suspects on inconsistencies in their stories.")
    
    return "INVESTIGATION HINTS:\n\n• " + "\n• ".join(hints)


@tool
class AccusationToolOutput(BaseModel):
    """Structured output from make_accusation tool."""
    dramatic_response: str = Field(description="Dramatic 2-3 sentence Game Master response")


# Minimum clues required before an accusation is considered valid
MIN_CLUES_FOR_VALID_ACCUSATION = 2


def evaluate_case_strength(state, accused_name: str) -> dict:
    """Evaluate the strength of the case against a suspect.
    
    Checks:
    - Clues that contradict their alibi (strong evidence)
    - Witness statements that contradict their claims
    - General clue count
    
    Returns dict with case_strength, alibi_disproven, evidence_summary
    """
    if not state or not state.mystery:
        return {"case_strength": "weak", "alibi_disproven": False, "evidence_summary": "No evidence"}
    
    # Find clues that contradict accused's alibi
    alibi_contradictions = state.mystery.get_alibi_contradictions(accused_name)
    found_contradictions = [cid for cid in alibi_contradictions if cid in state.clue_ids_found]
    
    # Check witness statements that contradict accused's alibi
    witness_contradictions = []
    accused_suspect = None
    for s in state.mystery.suspects:
        if s.name.lower() == accused_name.lower() or accused_name.lower() in s.name.lower():
            accused_suspect = s
            break
    
    if accused_suspect and accused_suspect.structured_alibi:
        alibi = accused_suspect.structured_alibi
        if alibi.corroborator:
            # Check if we've talked to the corroborator
            if alibi.corroborator in state.suspects_talked_to:
                # If the alibi is false, the corroborator won't confirm it
                if not alibi.is_truthful:
                    witness_contradictions.append(alibi.corroborator)
    
    # Calculate case strength
    total_clues = len(state.clue_ids_found)
    alibi_disproven = len(found_contradictions) > 0 or len(witness_contradictions) > 0
    
    evidence_parts = []
    if found_contradictions:
        evidence_parts.append(f"Physical evidence contradicts alibi ({len(found_contradictions)} clues)")
    if witness_contradictions:
        evidence_parts.append(f"Witness testimony contradicts alibi")
    if total_clues > 0:
        evidence_parts.append(f"{total_clues} clues gathered")
    
    if alibi_disproven and total_clues >= 2:
        case_strength = "strong"
    elif alibi_disproven or total_clues >= 3:
        case_strength = "moderate"
    elif total_clues >= MIN_CLUES_FOR_VALID_ACCUSATION:
        case_strength = "weak"
    else:
        case_strength = "insufficient"
    
    return {
        "case_strength": case_strength,
        "alibi_disproven": alibi_disproven,
        "alibi_contradiction_clues": found_contradictions,
        "witness_contradictions": witness_contradictions,
        "evidence_summary": "; ".join(evidence_parts) if evidence_parts else "No substantial evidence",
    }


@tool
def make_accusation(
    suspect_name: Annotated[str, "The full name of the suspect being accused of the murder"],
    evidence_summary: Annotated[str, "Brief summary of evidence or reasoning the player cited"] = "",
) -> str:
    """Make Accusation - Use when the player accuses a suspect of being the murderer.
    
    Call this tool when the player says things like:
    - "I accuse X of the murder"
    - "X is the killer" / "X did it"
    - "I think X is the murderer"
    - "It was X all along"
    - "X must be guilty"
    
    This tool:
    1. Checks if the player has gathered enough evidence (minimum clues found)
    2. Evaluates case strength - did they disprove the alibi?
    3. If evidence is INSUFFICIENT, the accusation still counts as a failed attempt
       (you lose one of your 3 allowed accusations), but the GM will scold you for
       jumping the gun and tell you to gather more proof.
    4. If there is enough evidence, checks if the accusation is correct. A wrong,
       fully-backed accusation also costs a strike.
    5. Returns a dramatic response for the Game Master to deliver
    
    Returns only the narrative. Structured data is stored in ToolOutputStore.
    """
    logger.info("\n" + "=" * 60)
    logger.info("🎯 MAKE_ACCUSATION TOOL CALLED")
    logger.info("Accused: %s", suspect_name)
    logger.info("Evidence: %s", evidence_summary[:200] if evidence_summary else "None cited")
    logger.info("=" * 60 + "\n")
    
    # =========================================================================
    # PREREQUISITE VALIDATION - Ensure we have the data we need
    # =========================================================================
    prereq_ok, prereq_error = validate_tool_prerequisites(
        tool_name="make_accusation",
        requires_mystery=True,
        requires_suspect=suspect_name,
        auto_wait=True,
        wait_timeout=10.0,
    )
    if not prereq_ok:
        logger.warning("[TOOL] Prerequisite check failed: %s", prereq_error)
        return prereq_error
    
    # Import here to avoid circular imports
    from game.state_manager import get_game_state, get_tool_output_store, AccusationOutput
    
    state = get_game_state()
    store = get_tool_output_store()
    
    # Evaluate case strength with alibi verification
    case_eval = evaluate_case_strength(state, suspect_name)
    
    # Check evidence: how many clues has the player found?
    clues_found_count = len(state.clue_ids_found) if state else 0
    has_sufficient_evidence = clues_found_count >= MIN_CLUES_FOR_VALID_ACCUSATION
    
    logger.info("Evidence check: %d clues found (need %d)", clues_found_count, MIN_CLUES_FOR_VALID_ACCUSATION)
    logger.info("Case evaluation: strength=%s, alibi_disproven=%s", 
                case_eval["case_strength"], case_eval["alibi_disproven"])
    
    # Check if accusation is correct - MUST GO THROUGH ORACLE
    # The Oracle is the only component that knows who the murderer is
    is_correct = False
    from services.mystery_oracle import get_mystery_oracle
    oracle = get_mystery_oracle()
    if oracle.is_initialized:
        # Ask the Oracle if this suspect is the murderer
        is_correct = oracle.check_accusation(suspect_name)
        logger.info("[ORACLE] Accusation check for '%s': %s", suspect_name, is_correct)
    else:
        logger.error("[ORACLE] Not initialized - cannot validate accusation")
    
    # Use LangChain's structured output
    llm = ChatOpenAI(
        model="gpt-4o-mini", 
        temperature=0.8, 
        api_key=os.getenv("OPENAI_API_KEY")
    )
    
    structured_llm = llm.with_structured_output(AccusationToolOutput)
    
    # Generate different response based on evidence status and case strength
    if has_sufficient_evidence:
        # Include case strength in the prompt for better responses
        case_context = f"Case strength: {case_eval['case_strength'].upper()}"
        if case_eval['alibi_disproven']:
            case_context += " - Alibi has been DISPROVEN through evidence"
        else:
            case_context += " - Alibi NOT yet disproven (weaker case)"
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are the Game Master for a murder mystery game. The player has made a FORMAL ACCUSATION with evidence to back it up.

Generate a DRAMATIC response that:
1. Acknowledges their accusation with gravitas
2. References their evidence gathering (especially if they disproved an alibi!)
3. Builds tension before the reveal
4. Ends on a cliffhanger (the actual result will be shown by the game)

Keep it SHORT (2-3 sentences) for voice narration. Be theatrical!"""),
            ("human", """Player formally accuses: {suspect_name}
Their reasoning: {evidence}
Clues they've gathered: {clue_count}
{case_context}

Generate the dramatic Game Master response.""")
        ])
    else:
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are the Game Master for a murder mystery game. The player has made an accusation BUT HASN'T GATHERED ENOUGH EVIDENCE YET.

Generate a response that:
1. Acknowledges their suspicion
2. Makes it clear this STILL COUNTS as one of their limited accusation attempts (a strike)
3. Explains that they need more evidence before trying again
4. Hint that they should verify alibis - search locations for physical evidence, talk to witnesses
5. The suspect is released without further questioning until more evidence is found

Keep it SHORT (2-3 sentences) for voice narration. Be firm but encouraging."""),
            ("human", """Player tried to accuse: {suspect_name}
Their reasoning: {evidence}
Clues found so far: {clue_count} (need at least {min_clues})
Evidence evaluation: {evidence_eval}

Generate the Game Master response rejecting this premature accusation.""")
        ])
    
    chain = prompt | structured_llm
    
    try:
        invoke_params = {
            "suspect_name": suspect_name,
            "evidence": evidence_summary or "Gut instinct - no specific evidence cited",
            "clue_count": clues_found_count,
            "min_clues": MIN_CLUES_FOR_VALID_ACCUSATION,
        }
        if has_sufficient_evidence:
            case_context = f"Case strength: {case_eval['case_strength'].upper()}"
            if case_eval['alibi_disproven']:
                case_context += " - Alibi has been DISPROVEN through evidence"
            else:
                case_context += " - Alibi NOT yet disproven (weaker case)"
            invoke_params["case_context"] = case_context
        else:
            invoke_params["evidence_eval"] = case_eval["evidence_summary"]
        
        result: AccusationToolOutput = chain.invoke(invoke_params)
        
        # Store structured data in ToolOutputStore (no regex markers!)
        store.accusation = AccusationOutput(
            suspect_name=suspect_name,
            is_correct=is_correct,
            narrative=result.dramatic_response,
            has_sufficient_evidence=has_sufficient_evidence,
            clues_found_count=clues_found_count,
        )
        
        # Record accusation attempt in state history (for UI display)
        if state:
            requirements = state.evaluate_accusation_requirements(suspect_name)
            state.record_accusation(
                accused_name=suspect_name,
                evidence_cited=evidence_summary or "",
                was_correct=is_correct,
                had_evidence=has_sufficient_evidence,
                requirements=requirements,
            )
        
        logger.info(
            "Accusation stored: suspect=%s, correct=%s, has_evidence=%s, clues=%d",
            suspect_name, is_correct, has_sufficient_evidence, clues_found_count
        )
        
        # Return ONLY the narrative - no markers needed!
        return result.dramatic_response
        
    except Exception as e:
        logger.error("Structured output failed: %s", e)
        # Fallback - still store basic info
        if has_sufficient_evidence:
            narrative = f"You accuse {suspect_name} of the murder."
        else:
            narrative = (
                f"You point the finger at {suspect_name}, but you haven't gathered enough concrete evidence. "
                "It still counts as a misstep, and the Chief warns you to build a stronger case before trying again."
            )
        
        store.accusation = AccusationOutput(
            suspect_name=suspect_name,
            is_correct=is_correct,
            narrative=narrative,
            has_sufficient_evidence=has_sufficient_evidence,
            clues_found_count=clues_found_count,
        )
        
        # Record accusation attempt even in fallback
        if state:
            from game.models import AccusationRequirements
            requirements = AccusationRequirements(
                has_minimum_clues=clues_found_count >= MIN_CLUES_FOR_VALID_ACCUSATION
            )
            state.record_accusation(
                accused_name=suspect_name,
                evidence_cited=evidence_summary or "",
                was_correct=is_correct,
                had_evidence=has_sufficient_evidence,
                requirements=requirements,
            )
        
        return narrative


def get_all_tools() -> List:
    """Get all tools for the game master agent.
    
    Returns a list of all available tools, including RAG tools if available.
    """
    tools = [interrogate_suspect, describe_scene_for_image, make_accusation]
    
    # Add RAG tools if memory is available
    memory = get_game_memory()
    if memory.is_available:
        tools.extend([
            search_past_statements,
            find_contradictions,
            get_cross_references,
            get_investigation_hint,
        ])
        logger.info("[TOOLS] RAG tools enabled (including hint system)")
    else:
        # Still add hint tool even without RAG - it provides basic guidance
        tools.append(get_investigation_hint)
        logger.info("[TOOLS] RAG tools disabled, basic hint system enabled")
    
    return tools
