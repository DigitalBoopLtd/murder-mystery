"""Media generation helpers (audio + images) for the murder mystery game."""

from __future__ import annotations

import logging
import os
import threading
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple

from game.state import GameState
from services.image_service import smart_generate_portrait, smart_generate_scene
from services.tts_service import text_to_speech
from game.state_manager import (
    mystery_images,
    get_or_create_state,
    _get_scene_mood_for_state,
    GAME_MASTER_VOICE_ID,
    get_suspect_voice_id,
    normalize_location_name,
)
from services.perf_tracker import perf

logger = logging.getLogger(__name__)


def _generate_portrait_background(
    suspect_name: str,
    suspect,
    mystery_setting: str,
    session_id: str,
):
    """Generate portrait in background thread."""
    try:
        logger.info("[BG] Generating portrait for %s...", suspect_name)
        perf.start(f"portrait_{suspect_name}", is_parallel=True, parallel_count=1, details="background")
        portrait_path = smart_generate_portrait(suspect, mystery_setting)
        if portrait_path:
            if session_id not in mystery_images:
                mystery_images[session_id] = {}
            mystery_images[session_id][suspect_name] = portrait_path
            perf.end(f"portrait_{suspect_name}", details=f"success")
            logger.info("[BG] ✅ Portrait ready for %s: %s", suspect_name, portrait_path)
        else:
            perf.end(f"portrait_{suspect_name}", status="error", details="no path")
            logger.warning("[BG] ❌ Failed to generate portrait for %s", suspect_name)
    except Exception as e:
        perf.end(f"portrait_{suspect_name}", status="error", details=str(e))
        logger.error("[BG] Error generating portrait for %s: %s", suspect_name, e)


def _generate_scene_background(
    location: str,
    mystery_setting: str,
    context_text: str,
    session_id: str,
):
    """Generate scene image in background thread."""
    # Sanitize location for perf key (remove spaces/special chars)
    safe_loc = location.replace(" ", "_").replace("'", "")[:20]
    try:
        logger.info("[BG] Generating scene for %s...", location)
        perf.start(f"scene_{safe_loc}", is_parallel=True, parallel_count=1, details="background")
        bg_state = get_or_create_state(session_id)
        mood = _get_scene_mood_for_state(bg_state)
        scene_path = smart_generate_scene(
            location=location,
            setting=mystery_setting,
            mood=mood,
            context=context_text,
        )
        if scene_path:
            if session_id not in mystery_images:
                mystery_images[session_id] = {}
            mystery_images[session_id][location] = scene_path
            perf.end(f"scene_{safe_loc}", details="success")
            logger.info("[BG] ✅ Scene ready for %s: %s", location, scene_path)
        else:
            perf.end(f"scene_{safe_loc}", status="error", details="no path")
            logger.warning("[BG] ❌ Failed to generate scene for %s", location)
    except Exception as e:
        perf.end(f"scene_{safe_loc}", status="error", details=str(e))
        logger.error("[BG] Error generating scene for %s: %s", location, e)


def _prewarm_suspect_portraits(session_id: str, mystery):
    """Pre-generate portraits for all suspects in the background.

    Uses a small bounded worker pool (max 3 concurrent workers) so we don't
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

    perf.start("prewarm_portraits", is_parallel=True, parallel_count=len(tasks), 
               details=f"{len(tasks)} suspects")
    
    task_queue: "queue.Queue[Tuple[str, object]]" = queue.Queue()
    completed_count = [0]  # Use list for mutable closure
    
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
                    completed_count[0] += 1
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

    max_workers = 3
    num_workers = min(max_workers, len(tasks))
    threads = []
    for _ in range(num_workers):
        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        threads.append(t)

    logger.info(
        "[BG] Launched %d prewarm portrait workers for session %s (tasks=%d)",
        num_workers,
        session_id,
        len(tasks),
    )
    
    # Wait for all tasks to complete, then end perf tracking
    def _track_completion():
        task_queue.join()  # Wait for all tasks
        perf.end("prewarm_portraits", details=f"{completed_count[0]}/{len(tasks)} completed")
        logger.info("[BG] Portrait prewarm complete: %d/%d", completed_count[0], len(tasks))
    
    threading.Thread(target=_track_completion, daemon=True).start()


def _prewarm_scene_images(session_id: str, mystery):
    """Pre-generate scene images for all clue locations in the background.

    Runs concurrently with portrait prewarming. Uses clue info to generate
    focused scene images that are ready when the player searches.
    
    This eliminates the ~4-5s wait during gameplay when searching locations.
    """
    if not mystery or not getattr(mystery, "clues", None):
        logger.info(
            "[BG] No clues available for scene prewarm in session %s", session_id
        )
        return

    setting = getattr(mystery, "setting", "") or ""
    session_images = mystery_images.get(session_id, {})

    # Build location -> clue info mapping for context
    location_clues: Dict[str, object] = {}
    for clue in mystery.clues:
        location = getattr(clue, "location", None)
        if location and location not in session_images:
            # Keep first clue per location (most important)
            if location not in location_clues:
                location_clues[location] = clue

    if not location_clues:
        logger.info(
            "[BG] No new scene images to prewarm for session %s", session_id
        )
        return

    perf.start("prewarm_scenes", is_parallel=True, parallel_count=len(location_clues),
               details=f"{len(location_clues)} locations")
    
    # Queue contains (location, clue) tuples for context
    task_queue: "queue.Queue[Tuple[str, object]]" = queue.Queue()
    completed_count = [0]  # Use list for mutable closure
    
    for location, clue in location_clues.items():
        task_queue.put((location, clue))

    def _worker():
        while True:
            try:
                location, clue = task_queue.get_nowait()
                try:
                    logger.info(
                        "[BG] Worker generating prewarm scene for %s in session %s",
                        location,
                        session_id,
                    )
                    # Build clue-focused context for better image quality
                    clue_desc = getattr(clue, "description", "") or ""
                    clue_type = getattr(clue, "type", "") or ""
                    context = f"Focus: {clue_desc}. Type: {clue_type}." if clue_desc else ""
                    
                    _generate_scene_background(
                        location=location,
                        mystery_setting=setting,
                        context_text=context,
                        session_id=session_id,
                    )
                    completed_count[0] += 1
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

    max_workers = 3
    num_workers = min(max_workers, len(locations))
    threads = []
    for _ in range(num_workers):
        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        threads.append(t)

    logger.info(
        "[BG] Launched %d prewarm scene workers for session %s (locations=%d)",
        num_workers,
        session_id,
        len(locations),
    )
    
    # Wait for all tasks to complete, then end perf tracking
    def _track_completion():
        task_queue.join()  # Wait for all tasks
        perf.end("prewarm_scenes", details=f"{completed_count[0]}/{len(locations)} completed")
        logger.info("[BG] Scene prewarm complete: %d/%d", completed_count[0], len(locations))
    
    threading.Thread(target=_track_completion, daemon=True).start()


def generate_turn_media(
    clean_response: str,
    speaker: str,
    state: GameState,
    actions: Dict,
    audio_path_from_tool: Optional[str],
    session_id: str,
    background_images: bool = True,
    alignment_data_from_tool: Optional[List[Dict]] = None,
) -> Tuple[Optional[str], Optional[List[Dict]]]:
    """Generate audio and images for a turn (slow path).

    This handles TTS generation and portrait/scene image generation.
    Called after run_action_logic to generate media assets.
    
    OPTIMIZATION: When background_images=False, TTS and image generation
    run in PARALLEL using ThreadPoolExecutor, saving 3-5s per turn.

    Args:
        clean_response: The text response to convert to speech
        speaker: Speaker name (suspect name or "Game Master")
        state: Game state
        actions: Parsed actions dict from run_action_logic
        audio_path_from_tool: Pre-generated audio path if tool created it
        session_id: Session identifier
        background_images: If True, generate images in background threads (default)
        alignment_data_from_tool: Pre-generated alignment data if tool created it

    Returns:
        Tuple of (audio_path, alignment_data)
    """
    # Determine voice early (needed for TTS)
    voice_id = None
    if speaker and speaker != "Game Master":
        voice_id = get_suspect_voice_id(speaker, state)
    else:
        gm_voice = getattr(state, "game_master_voice_id", None)
        if gm_voice:
            voice_id = gm_voice
    voice_id = voice_id or GAME_MASTER_VOICE_ID
    
    tts_text = clean_response.replace("**", "").replace("*", "")
    speaker_name = speaker or "Game Master"
    
    # Collect image generation tasks
    image_tasks = []
    
    # Check if portrait needed
    portrait_suspect = None
    if speaker and speaker != "Game Master":
        session_images = mystery_images.get(session_id, {})
        if speaker not in session_images:
            for s in state.mystery.suspects:
                if s.name == speaker:
                    portrait_suspect = s
                    break
    
    # Check if scene needed
    # Use prewarmed image if exists - prewarming now includes clue focus
    scene_info = None
    if actions.get("location_searched"):
        location = actions["location_searched"]
        normalized_location = normalize_location_name(location, state)
        session_images = mystery_images.get(session_id, {})
        mystery_setting = state.mystery.setting if state.mystery else ""
        
        # Check if image already exists (from prewarming or previous search)
        image_exists = normalized_location in session_images or location in session_images
        
        if image_exists:
            # Use prewarmed/cached image - no regeneration needed
            # Prewarmed images already have clue focus from _prewarm_scene_images
            logger.info("[GAME] ✅ Using prewarmed scene for %s (instant)", normalized_location)
        else:
            # No prewarmed image - generate on-demand with clue context
            loc_desc = getattr(state, "location_descriptions", {}).get(normalized_location, "")
            parts = []
            if loc_desc:
                parts.append(f"CLUE-FOCUSED IMAGE: {loc_desc}")
            if clean_response:
                parts.append(clean_response[:300])
            context_text = " ".join(parts)
            
            logger.info("[GAME] Generating scene on-demand for: %s", normalized_location)
            logger.info("[GAME] Scene context: %d chars", len(context_text))
            scene_info = (location, normalized_location, mystery_setting, context_text)
    
    # If background_images=True, fire and forget
    if background_images:
        if portrait_suspect:
            mystery_setting = state.mystery.setting if state.mystery else ""
            logger.info("[GAME] Starting background portrait generation for: %s", speaker)
            threading.Thread(
                target=_generate_portrait_background,
                args=(speaker, portrait_suspect, mystery_setting, session_id),
                daemon=True,
            ).start()
        
        if scene_info:
            location, normalized_location, mystery_setting, context_text = scene_info
            logger.info("[GAME] Starting background scene generation for: %s", normalized_location)
            threading.Thread(
                target=_generate_scene_background,
                args=(normalized_location, mystery_setting, context_text, session_id),
                daemon=True,
            ).start()
        
        # TTS runs in foreground
        audio_path, alignment_data = _generate_tts(
            tts_text, voice_id, speaker_name, audio_path_from_tool, alignment_data_from_tool
        )
        return audio_path, alignment_data
    
    # ========== PARALLEL MODE (background_images=False) ==========
    # Run TTS and image generation in parallel for maximum speed
    
    logger.info("[GAME] Running TTS + images in PARALLEL mode")
    perf.start("parallel_media", details="TTS + portrait/scene")
    
    audio_path = None
    alignment_data = None
    
    def _tts_task():
        return _generate_tts(tts_text, voice_id, speaker_name, audio_path_from_tool, alignment_data_from_tool)
    
    def _portrait_task():
        if not portrait_suspect:
            return None
        mystery_setting = state.mystery.setting if state.mystery else ""
        logger.info("[GAME] Parallel: generating portrait for %s", speaker)
        perf.start(f"parallel_portrait_{speaker}", details="foreground parallel")
        portrait_path = smart_generate_portrait(portrait_suspect, mystery_setting)
        if portrait_path:
            if session_id not in mystery_images:
                mystery_images[session_id] = {}
            mystery_images[session_id][speaker] = portrait_path
            perf.end(f"parallel_portrait_{speaker}", details="success")
            logger.info("[GAME] Parallel: portrait ready for %s", speaker)
        else:
            perf.end(f"parallel_portrait_{speaker}", status="error", details="no path")
        return portrait_path
    
    def _scene_task():
        if not scene_info:
            return None
        location, normalized_location, mystery_setting, context_text = scene_info
        logger.info("[GAME] Parallel: generating scene for %s", normalized_location)
        perf.start(f"parallel_scene_{normalized_location[:15]}", details="foreground parallel")
        scene_path = smart_generate_scene(
            location=normalized_location,
            setting=mystery_setting,
            mood="mysterious",
            context=context_text,
        )
        if scene_path:
            if session_id not in mystery_images:
                mystery_images[session_id] = {}
            mystery_images[session_id][normalized_location] = scene_path
            if normalized_location != location:
                mystery_images[session_id][location] = scene_path
            perf.end(f"parallel_scene_{normalized_location[:15]}", details="success")
            logger.info("[GAME] Parallel: scene ready for %s", normalized_location)
            return scene_path
        perf.end(f"parallel_scene_{normalized_location[:15]}", status="error", details="failed")
        return None
    
    # Run all tasks in parallel
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {}
        futures["tts"] = executor.submit(_tts_task)
        if portrait_suspect:
            futures["portrait"] = executor.submit(_portrait_task)
        if scene_info:
            futures["scene"] = executor.submit(_scene_task)
        
        # Wait for all to complete
        for name, future in futures.items():
            try:
                result = future.result()
                if name == "tts":
                    audio_path, alignment_data = result
            except Exception as e:
                logger.error("[GAME] Parallel task '%s' failed: %s", name, e)
    
    perf.end("parallel_media", details=f"tts={bool(audio_path)}, portrait={bool(portrait_suspect)}, scene={bool(scene_info)}")
    
    return audio_path, alignment_data


def _generate_tts(
    tts_text: str,
    voice_id: str,
    speaker_name: str,
    audio_path_from_tool: Optional[str],
    alignment_data_from_tool: Optional[List[Dict]] = None,
) -> Tuple[Optional[str], Optional[List[Dict]]]:
    """Generate TTS audio (extracted for parallel execution)."""
    if audio_path_from_tool:
        # Prefer alignment data passed directly from ToolOutputStore
        alignment_data = alignment_data_from_tool
        
        # Fall back to legacy cache lookup if not provided
        if not alignment_data:
            from game.tools import get_audio_alignment_data
            alignment_data = get_audio_alignment_data(audio_path_from_tool)
        
        if alignment_data:
            logger.info(
                "[GAME] Using audio from tool with %d word timestamps: %s",
                len(alignment_data), audio_path_from_tool
            )
        else:
            logger.info("[GAME] Using audio from tool (no alignment): %s", audio_path_from_tool)
        return audio_path_from_tool, alignment_data
    
    logger.info("[GAME] Calling TTS for response (%d chars)", len(tts_text))
    perf.start("gameplay_tts", details=f"{len(tts_text)} chars, speaker={speaker_name}")
    audio_path, alignment_data = text_to_speech(tts_text, voice_id, speaker_name=speaker_name)
    perf.end("gameplay_tts", details=f"audio={bool(audio_path)}, words={len(alignment_data) if alignment_data else 0}")
    
    if audio_path:
        if os.path.exists(audio_path):
            file_size = os.path.getsize(audio_path)
            logger.info("[GAME] ✅ Audio generated: %s (%d bytes)", audio_path, file_size)
        else:
            logger.error("[GAME] ❌ Audio file doesn't exist: %s", audio_path)
    else:
        logger.error("[GAME] ❌ No audio path from TTS!")
    
    if alignment_data:
        logger.info("[GAME] ✅ Got %d word timestamps", len(alignment_data))
    else:
        logger.warning("[GAME] ⚠️ No alignment data")
    
    return audio_path, alignment_data


