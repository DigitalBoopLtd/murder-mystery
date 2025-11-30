"""Game startup logic for the murder mystery game.

This module handles:
- Voice-first character generation (fetch voices BEFORE generating characters)
- Fast premise generation
- Initial Game Master welcome
- Background full-case generation
- Background prewarming of portraits and scene images
- Graceful fallback to "Silent Film" mode if voices unavailable
"""

from __future__ import annotations

import logging
import os
import random
import threading
import time
from typing import Optional, Tuple, List, Dict

from game.mystery_generator import (
    generate_mystery,
    generate_mystery_premise,
    prepare_game_prompt,
    generate_location_descriptions,
)
from game.media import _prewarm_suspect_portraits, _prewarm_scene_images
from mystery_config import create_validated_config
from services.agent import create_game_master_agent, process_message
from services.tts_service import text_to_speech
from game.state_manager import (
    mystery_images,
    GAME_MASTER_VOICE_ID,
    get_or_create_state,
)
from services.game_memory import initialize_game_memory, reset_game_memory
from services.voice_service import get_voice_service, Voice

logger = logging.getLogger(__name__)


def pick_expressive_narrator_voice(voices: List[Voice]) -> str:
    """Pick an expressive, English-friendly voice for the Game Master.

    Falls back to the default GAME_MASTER_VOICE_ID if anything goes wrong.
    """
    if not voices:
        return GAME_MASTER_VOICE_ID

    expressive_keywords = [
        "dramatic",
        "theatrical",
        "expressive",
        "bold",
        "edgy",
        "mysterious",
        "intense",
        "energetic",
        "brooding",
        "suspense",
    ]
    expressive_use_cases = {
        "characters_animation",
        "narrative_story",
        "entertainment_tv",
        "video_games",
    }

    def is_expressive(v: Voice) -> bool:
        text_parts: List[str] = []
        if getattr(v, "descriptive", None):
            text_parts.append(str(v.descriptive))
        if getattr(v, "description", None):
            text_parts.append(str(v.description))
        text = " ".join(text_parts).lower()
        use_case = str(getattr(v, "use_case", "") or "").lower()
        return any(kw in text for kw in expressive_keywords) or use_case in expressive_use_cases

    # Prefer English voices
    english_voices = [
        v
        for v in voices
        if str(getattr(v, "language", "") or "").lower() in ("", "en", "english")
    ]

    # Then prefer expressive ones within that set
    pool = [v for v in english_voices if is_expressive(v)] or english_voices or voices
    chosen = random.choice(pool)

    logger.info(
        "[VOICE] Selected Game Master voice: %s (id=%s, gender=%s, accent=%s, use_case=%s)",
        getattr(chosen, "name", "Unknown"),
        getattr(chosen, "voice_id", ""),
        getattr(chosen, "gender", ""),
        getattr(chosen, "accent", ""),
        getattr(chosen, "use_case", ""),
    )
    return chosen.voice_id


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
        from services.image_service import generate_title_card_on_demand

        victim_stub = SimpleNamespace(name=victim_name)
        mystery_like = SimpleNamespace(victim=victim_stub, setting=setting)

        logger.info(
            "[BG] Generating opening scene image from premise for session %s (fast mode)",
            session_id,
        )
        # Use fast_mode=True to skip LLM prompt enhancement (~6s faster)
        # This ensures the image is ready before/with the welcome speech
        portrait = generate_title_card_on_demand(mystery_like, fast_mode=True)
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


def fetch_voices_for_session(session_id: str) -> Tuple[List, str, str]:
    """Fetch voices for a session using pre-fetched voices from app startup.
    
    This should be called BEFORE generating characters so the LLM can
    create characters that match available voices.
    
    OPTIMIZATION: Voices are pre-fetched on app load via direct API call,
    bypassing MCP for speed. This function uses the cached voices.
    
    Returns:
        Tuple of (voices list, voice_summary string, status string)
        Status is one of: 'prefetched', 'api_success', 'cached', 'failed', etc.
    """
    from services.perf_tracker import perf
    
    state = get_or_create_state(session_id)
    
    # Check session cache first
    if state.voices_fetched and state.available_voices:
        logger.info("[VOICE] Using session-cached voices for %s (%d voices)", 
                    session_id[:8], len(state.available_voices))
        return state.available_voices, state.voice_summary, "cached"
    
    perf.start("fetch_voices_session")
    
    # Try to use pre-fetched voices from app startup
    try:
        from app.main import PREFETCHED_VOICES, VOICE_SUMMARY, VOICES_READY
        
        # Wait for prefetch to complete (with timeout)
        if VOICES_READY.wait(timeout=5.0) and PREFETCHED_VOICES:
            logger.info("[VOICE] Using pre-fetched voices (%d voices)", len(PREFETCHED_VOICES))
            
            # Cache in session state
            state.available_voices = PREFETCHED_VOICES
            state.voice_summary = VOICE_SUMMARY
            state.voices_fetched = True
            state.voice_mode = "full"
            
            perf.end("fetch_voices_session", details=f"prefetched {len(PREFETCHED_VOICES)} voices")
            return PREFETCHED_VOICES, VOICE_SUMMARY, "prefetched"
    except ImportError:
        logger.debug("[VOICE] Pre-fetched voices not available, using direct fetch")
    
    # Fallback to direct API fetch (no MCP)
    voice_service = get_voice_service()
    
    t0 = time.perf_counter()
    voices = voice_service.get_available_voices(force_refresh=True)
    t1 = time.perf_counter()
    status = "api_success" if voices else "failed"
    logger.info("[PERF] Voice fetch took %.2fs (status=%s)", t1 - t0, status)
    
    if status in ["prefetched", "mcp_success", "api_success", "success"] and voices:
        # Generate summary for LLM
        voice_summary = voice_service.summarize_voices_for_llm(voices)
        voice_stats = voice_service.get_voice_diversity_stats(voices)
        
        # Cache in session state
        state.available_voices = voices
        state.voice_summary = voice_summary
        state.voices_fetched = True
        state.voice_mode = "full"
        state.voice_diversity_stats = voice_stats
        state.voice_fetch_error = None
        
        # Log with source info
        source = "MCP" if status == "mcp_success" else "Direct API"
        logger.info("[VOICE] Fetched %d voices via %s for session %s", len(voices), source, session_id[:8])
        logger.info("[VOICE] Diversity: %s", voice_stats)
        
        return voices, voice_summary, status
    else:
        # Failed to fetch - enable silent film mode
        state.available_voices = []
        state.voice_summary = ""
        state.voices_fetched = True  # Mark as fetched (even if failed) to avoid retrying
        state.voice_mode = "text_only"  # Silent film mode
        state.voice_fetch_error = status
        
        logger.warning("[VOICE] Failed to fetch voices (status=%s), running in silent film mode", status)
        
        return [], "", status


def start_new_game(session_id: str):
    """Start a new mystery game with voice-first character generation.
    
    Flow:
    1. Fetch voices (with session caching and fallback)
    2. Generate premise
    3. Generate Game Master welcome
    4. Background: Generate full mystery WITH voice assignments
    """
    from services.perf_tracker import perf
    
    # Reset perf tracker for this game session
    perf.reset(session_id)
    
    state = get_or_create_state(session_id)
    state.reset_game()

    # Initialize RAG memory for semantic search (Phase 2 AI Enhancement)
    perf.start("init_rag_memory")
    reset_game_memory()
    if initialize_game_memory():
        logger.info("[RAG] Game memory initialized successfully")
        perf.end("init_rag_memory", details="success")
    else:
        logger.warning("[RAG] Game memory not available (FAISS may not be installed)")
        perf.end("init_rag_memory", status="skipped", details="FAISS not available")

    # Ensure we have a configuration object for this session
    if not hasattr(state, "config") or state.config is None:
        state.config = create_validated_config()
    config = state.config
    # Cache tone instruction on state so it can be used in continue prompts
    try:
        state.tone_instruction = config.get_tone_instruction()
    except Exception:  # noqa: BLE001
        state.tone_instruction = None

    # ========== STAGE 0: FETCH VOICES (Voice-First) ==========
    # This MUST happen before mystery generation so LLM can create
    # characters that match available voices
    logger.info("Fetching voices for session %s...", session_id[:8])
    voices, voice_summary, voice_status = fetch_voices_for_session(session_id)
    
    if voice_status in ["prefetched", "mcp_success", "api_success", "success", "cached"]:
        logger.info(
            "[VOICE] %d voices available for character generation (via %s)",
            len(voices),
            voice_status,
        )
    else:
        logger.warning("[VOICE] No voices available - running in Silent Film mode")

    # Choose a Game Master voice for this game from the available voices (if any)
    narrator_voice_id = GAME_MASTER_VOICE_ID
    if voices:
        try:
            narrator_voice_id = pick_expressive_narrator_voice(voices)
        except Exception:
            logger.exception(
                "[VOICE] Failed to pick expressive narrator voice; using default"
            )
    state.game_master_voice_id = narrator_voice_id

    # ========== STAGE 1: FAST PREMISE ==========
    logger.info("Generating mystery premise...")
    perf.start("generate_premise", details="GPT-4o call")
    premise = generate_mystery_premise(config=config)
    perf.end("generate_premise", details=f"victim: {premise.victim_name}")

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
    perf.start("bg_title_card", is_parallel=True, parallel_count=1, details="Background thread")
    try:
        threading.Thread(
            target=_background_generate_title_card_from_premise,
            args=(session_id,),
            daemon=True,
        ).start()
        # Note: We mark this as "started" - completion is tracked separately
    except Exception as e:  # noqa: BLE001
        logger.error(
            "[BG] Error starting title-card prewarm thread for %s: %s",
            session_id,
            e,
        )
        perf.end("bg_title_card", status="error", details=str(e))

    # Create or reuse shared agent and get narration immediately (no waiting for images)
    if not hasattr(start_new_game, "agent"):
        start_new_game.agent = create_game_master_agent()

    perf.start("welcome_llm", details="Game Master greeting")
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
    perf.end("welcome_llm", details=f"{len(response)} chars")

    # Ensure images dict exists for this session (do not clobber prewarmed images)
    if session_id not in mystery_images:
        mystery_images[session_id] = {}

    # Generate audio (needs the response text)
    logger.info("[GAME] Calling TTS for welcome message (%d chars)", len(response))
    gm_voice = getattr(state, "game_master_voice_id", None) or GAME_MASTER_VOICE_ID
    logger.info(
        "[GAME] Using Game Master voice_id=%s for welcome message",
        gm_voice,
    )
    perf.start("welcome_tts", details="ElevenLabs TTS")
    audio_path, alignment_data = text_to_speech(
        response, gm_voice, speaker_name="Game Master"
    )
    perf.end("welcome_tts", details=f"audio: {bool(audio_path)}, alignment: {len(alignment_data) if alignment_data else 0} words")

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
    # Pass voice_summary so LLM can assign voices during generation

    def _background_generate_full_case(sess_id: str, premise_obj, bg_voice_summary: str):
        from services.perf_tracker import perf
        
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
            logger.info("[BG] Voice mode: %s (summary length: %d chars)", 
                        bg_state.voice_mode, len(bg_voice_summary) if bg_voice_summary else 0)
            
            perf.start("bg_full_mystery", is_parallel=True, parallel_count=1, details="Background thread")
            # Pass voice_summary so LLM assigns voices during character generation
            full_mystery = generate_mystery(
                premise=premise_obj, 
                config=bg_config,
                voice_summary=bg_voice_summary if bg_voice_summary else None
            )
            
            # Log voice assignments
            assigned_count = sum(1 for s in full_mystery.suspects if s.voice_id)
            logger.info("[BG] Voice assignments: %d/%d suspects have voices",
                        assigned_count, len(full_mystery.suspects))
            
            bg_state.mystery = full_mystery
            
            # Generate rich per-location visual descriptions for scene images
            perf.start("bg_location_descriptions", details="LLM visual descriptions")
            try:
                bg_state.location_descriptions = generate_location_descriptions(
                    full_mystery
                )
                perf.end("bg_location_descriptions", details=f"{len(bg_state.location_descriptions)} locations")
            except Exception as e:  # noqa: BLE001
                logger.error(
                    "[BG] Error generating location descriptions for session %s: %s",
                    sess_id,
                    e,
                )
                perf.end("bg_location_descriptions", status="error", details=str(e))
            
            bg_state.system_prompt = prepare_game_prompt(
                full_mystery, bg_state.tone_instruction
            )
            bg_state.mystery_ready = True
            perf.end("bg_full_mystery", details=f"{len(full_mystery.suspects)} suspects, {len(full_mystery.clues)} clues")
            logger.info("[BG] Full mystery is ready for session %s", sess_id)
            
            # ========== PREWARM ALL IMAGES IN BACKGROUND ==========
            # This runs AFTER mystery is ready, generating all portraits and scenes
            # in parallel so they're ready before the player needs them
            logger.info("[BG] Starting image prewarming for session %s...", sess_id)
            perf.start("bg_prewarm_images", is_parallel=True, parallel_count=1, details="portraits + scenes")
            try:
                # Prewarm all suspect portraits (runs 3 workers in parallel)
                _prewarm_suspect_portraits(sess_id, full_mystery)
                # Prewarm all scene images (runs 3 workers in parallel)
                _prewarm_scene_images(sess_id, full_mystery)
                perf.end("bg_prewarm_images", details=f"{len(full_mystery.suspects)} portraits, {len(full_mystery.clues)} scenes")
            except Exception as prewarm_err:  # noqa: BLE001
                logger.error("[BG] Error prewarming images: %s", prewarm_err)
                perf.end("bg_prewarm_images", status="error", details=str(prewarm_err))
        except Exception as e:
            logger.error("[BG] Error generating full mystery in background: %s", e)
            perf.end("bg_full_mystery", status="error", details=str(e))

    # Mark title card prewarm as started (it's running in parallel)
    perf.end("bg_title_card", status="started", details="Running in parallel")
    
    perf.start("bg_mystery_thread", details="Starting background thread")
    threading.Thread(
        target=_background_generate_full_case,
        args=(session_id, premise, voice_summary),  # Pass voice_summary!
        daemon=True,
    ).start()
    perf.end("bg_mystery_thread", details="Thread launched")

    return state, response, audio_path, "Game Master", alignment_data


def prepare_game_resources(session_id: str) -> Dict:
    """Pre-fetch voices and prepare game resources.
    
    This should be called when the settings screen opens to:
    1. Fetch voices in the background
    2. Cache them for use when game starts
    3. Return status for UI to show progress
    
    Returns:
        Dict with status info:
        - voices_ready: bool
        - voice_count: int
        - voice_mode: str (full/text_only)
        - diversity_stats: dict
        - error: str or None
    """
    state = get_or_create_state(session_id)
    
    # Fetch voices (uses session cache)
    voices, voice_summary, status = fetch_voices_for_session(session_id)
    
    return {
        "voices_ready": len(voices) > 0,
        "voice_count": len(voices),
        "voice_mode": state.voice_mode,
        "diversity_stats": state.voice_diversity_stats,
        "error": state.voice_fetch_error,
        "status": status,
    }


def refresh_voices(session_id: str) -> Dict:
    """Force refresh voices from ElevenLabs.
    
    Called when user clicks the refresh button.
    """
    state = get_or_create_state(session_id)
    
    # Clear cache to force refresh
    state.voices_fetched = False
    state.available_voices = []
    state.voice_summary = ""
    
    # Re-fetch
    return prepare_game_resources(session_id)


def start_new_game_staged(session_id: str):
    """Staged version of start_new_game used by the UI to show progress.

    This wraps the existing start_new_game() function and exposes coarse
    progress stages as a generator:
      - ("voices", 0.1, voice_status)
      - ("premise", 0.3, None)
      - ("welcome", 0.6, None)
      - ("tts", 0.9, None)
      - ("complete", 1.0, {...})
    """
    state = get_or_create_state(session_id)
    
    # Stage 0: Voice status (may already be cached)
    voice_status = {
        "mode": state.voice_mode,
        "count": len(state.available_voices) if state.available_voices else 0,
    }
    yield ("voices", 0.1, voice_status)

    # Run the actual startup logic (voices + premise + welcome + TTS + BG full mystery)
    state, response, audio_path, speaker, alignment_data = start_new_game(session_id)

    # Expose additional coarse stages so the UI can animate the progress bar
    yield ("premise", 0.3, None)
    yield ("welcome", 0.6, None)
    yield ("tts", 0.9, None)

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
            "voice_mode": state.voice_mode,
        },
    )


