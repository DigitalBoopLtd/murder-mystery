"""Game startup logic for the murder mystery game.

This module handles:
- Fast premise generation
- Initial Game Master welcome
- Background full-case generation
- Background prewarming of portraits and scene images
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Optional, Tuple, List, Dict

from game.mystery_generator import (
    generate_mystery,
    generate_mystery_premise,
    prepare_game_prompt,
)
from mystery_config import create_validated_config
from services.agent import create_game_master_agent, process_message
from services.tts_service import text_to_speech
from game.state_manager import (
    mystery_images,
    GAME_MASTER_VOICE_ID,
    get_or_create_state,
)
from game.media import _prewarm_suspect_portraits, _prewarm_scene_images

logger = logging.getLogger(__name__)


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
            # Both run in parallel using separate worker pools
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


