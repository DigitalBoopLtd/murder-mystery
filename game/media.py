"""Media generation helpers (audio + images) for the murder mystery game."""

from __future__ import annotations

import logging
import os
import threading
import queue
from typing import Dict, List, Optional, Tuple

from game.state import GameState
from services.image_service import generate_portrait_on_demand, get_image_service
from services.tts_service import text_to_speech
from game.state_manager import (
    mystery_images,
    get_or_create_state,
    _get_scene_mood_for_state,
    GAME_MASTER_VOICE_ID,
    get_suspect_voice_id,
    normalize_location_name,
)

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

    max_workers = 3
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

    Runs concurrently with portrait prewarming. Uses a bounded number of
    workers to generate scene images for each unique location mentioned
    in the clues.
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

    max_workers = 3
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
                    portrait_path = generate_portrait_on_demand(
                        suspect, mystery_setting
                    )
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
        normalized_location = normalize_location_name(location, state)
        session_images = mystery_images.get(session_id, {})
        
        # Only generate if we don't already have this scene (check both original and normalized)
        if normalized_location not in session_images and location not in session_images:
            mystery_setting = state.mystery.setting if state.mystery else ""
            # Build rich scene context: stored location description + latest narrative
            parts = []
            loc_desc = getattr(state, "location_descriptions", {}).get(
                normalized_location, ""
            )
            if loc_desc:
                parts.append(f"Location visual description: {loc_desc}")
            if clean_response:
                parts.append(clean_response[:300])
            context_text = " ".join(parts)
            
            if background_images:
                logger.info(
                    "[GAME] Starting background scene generation for: %s (normalized: %s)",
                    location,
                    normalized_location,
                )
                threading.Thread(
                    target=_generate_scene_background,
                    args=(normalized_location, mystery_setting, context_text, session_id),
                    daemon=True,
                ).start()
            else:
                # Foreground (blocking)
                logger.info("Generating scene image for location: %s (normalized: %s)", location, normalized_location)
                service = get_image_service()
                if service and service.is_available:
                    scene_path = service.generate_scene(
                        location_name=normalized_location,  # Use normalized name for generation
                        setting_description=mystery_setting,
                        mood="mysterious",
                        context=context_text,
                    )
                    if scene_path:
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
                    logger.warning("Image service not available for scene generation")

    # Determine voice
    voice_id = None
    if speaker and speaker != "Game Master":
        voice_id = get_suspect_voice_id(speaker, state)
    else:
        # Narrator: prefer the per-game Game Master voice picked at startup
        gm_voice = getattr(state, "game_master_voice_id", None)
        if gm_voice:
            voice_id = gm_voice

    voice_id = voice_id or GAME_MASTER_VOICE_ID

    # Generate audio (always foreground - needed for immediate playback)
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

    return audio_path, alignment_data


