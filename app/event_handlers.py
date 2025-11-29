"""Event handlers for the murder mystery game."""

import os
import logging
import time
from typing import Tuple
import gradio as gr
from mystery_config import get_settings_for_era, create_validated_config
from game.state_manager import get_or_create_state, mystery_images
from game.startup import start_new_game_staged, prepare_game_resources, refresh_voices
from game.handlers import process_player_action, run_action_logic
from game.media import generate_turn_media
from services.tts_service import transcribe_audio
from ui.formatters import (
    format_victim_scene_html,
    format_suspects_list_html,
    format_locations_html,
    format_clues_html,
    format_detective_notebook_html,
    format_dashboard_html,
)
from app.utils import convert_alignment_to_subtitles

logger = logging.getLogger(__name__)


def normalize_session_id(sess_id) -> str:
    """Ensure we always use a *stable* string session id.

    Important: do NOT *call* callables here (e.g. ``lambda: uuid4()``),
    because that would generate a new id on every callback and break
    the link between background tasks, the timer, and voice turns.
    Instead, we treat the callable object itself as an opaque, stable
    identifier and use its ``repr`` as the session key.
    """
    if callable(sess_id):
        # Use a stable string representation of the callable object itself
        return repr(sess_id)
    if not isinstance(sess_id, str):
        return str(sess_id)
    return sess_id


def ensure_config(sess_id):
    """Get or initialize the per-session mystery configuration."""
    sess_id = normalize_session_id(sess_id)
    state = get_or_create_state(sess_id)
    if not hasattr(state, "config") or state.config is None:
        state.config = create_validated_config()
    return state


def format_accusations_html(wrong: int) -> str:
    """Format accusations HTML with pips."""
    pips = ""
    for i in range(3):
        cls = "accusations-pip used" if i < wrong else "accusations-pip"
        pips += f'<span class="{cls}"></span>'
    return f'<div class="accusations-display">Accusations:<span>{pips}</span></div>'


def on_config_generic_change(setting, era, difficulty, tone, sess_id):
    """Update config for non-era fields (setting/difficulty/tone)."""
    state = ensure_config(sess_id)
    try:
        state.config = create_validated_config(
            setting=setting,
            era=era,
            difficulty=difficulty,
            tone=tone,
        )
    except ValueError as e:
        logger.warning(
            "Invalid mystery config for session %s: %s",
            sess_id,
            e,
        )
        state.config = create_validated_config()


def on_refresh_voices(sess_id, progress=gr.Progress()):
    """Manually refresh available voices for the current session."""
    sess_id = normalize_session_id(sess_id)
    logger.info("[APP] Manual voice refresh requested for session %s", sess_id)
    progress(0, desc="🎭 Refreshing voices...")
    try:
        # Trigger a fresh voice fetch; return value is not used by UI directly.
        refresh_voices(sess_id)
        progress(1.0, desc="✅ Voices refreshed")
    except Exception as e:  # noqa: BLE001
        logger.warning("[APP] Voice refresh failed for session %s: %s", sess_id, e)
        progress(1.0, desc="⚠️ Voice refresh failed")


def on_wizard_config_change(era, setting, difficulty, tone, sess_id):
    """Update config from wizard controls and refresh setting options if era changed."""
    state = ensure_config(sess_id)
    
    available_settings = get_settings_for_era(era)
    # If current setting is not valid for the new era, reset to Random
    if setting not in available_settings and setting != "Random":
        setting = "Random"
    
    try:
        state.config = create_validated_config(
            setting=setting,
            era=era,
            difficulty=difficulty,
            tone=tone,
        )
    except ValueError as e:
        logger.warning(
            "Invalid mystery config from wizard for session %s: %s",
            sess_id,
            e,
        )
        state.config = create_validated_config()
        era = state.config.era
        available_settings = get_settings_for_era(era)
        setting = "Random"
    
    return gr.update(
        choices=["Random"] + available_settings,
        value=setting,
    )

def on_start_game(sess_id, progress=gr.Progress()):
    """Handle game start with staged progress updates.

    Flow:
    1. Hide wizard, show casting progress
    2. Voice-first: Use pre-fetched voices for character generation
    3. Generate premise → welcome → TTS → image
    4. Background: full mystery generation with voice assignments
    """
    sess_id = normalize_session_id(sess_id)
    state = get_or_create_state(sess_id)


    # Stage descriptions for progress bar
    stage_descriptions = {
        "voices": "🎭 Preparing voice actors...",
        "premise": "📜 Creating murder scenario...",
        "welcome": "🎙️ Preparing Game Master...",
        "tts": "🔊 Generating voice narration...",
        "complete": "✅ Ready to play!",
    }

    # Run the staged generator (fast path only, mystery generates in background)
    state = None
    response = None
    audio_path = None
    speaker = None
    alignment_data = None

    for stage_name, stage_progress, stage_data in start_new_game_staged(sess_id):
        desc = stage_descriptions.get(stage_name, f"Processing {stage_name}...")
        progress(stage_progress, desc=desc)
        logger.info(
            "[APP] Game start stage: %s (%.0f%%)",
            stage_name,
            stage_progress * 100,
        )

        if stage_name == "complete" and stage_data:
            state = stage_data["state"]
            response = stage_data["response"]
            audio_path = stage_data["audio_path"]
            speaker = stage_data["speaker"]
            alignment_data = stage_data["alignment_data"]

    # Log what we got back
    logger.info("[APP] on_start_game received:")
    logger.info("[APP]   response: %d chars", len(response) if response else 0)
    logger.info("[APP]   audio_path: %s", audio_path)
    logger.info("[APP]   speaker: %s", speaker)
    logger.info(
        "[APP]   alignment_data: %s items",
        len(alignment_data) if alignment_data else "None",
    )

    # Verify audio file exists
    if audio_path:
        if os.path.exists(audio_path):
            logger.info(
                "[APP] ✅ Audio file exists: %d bytes",
                os.path.getsize(audio_path),
            )
        else:
            logger.error("[APP] ❌ Audio file NOT FOUND: %s", audio_path)
    else:
        logger.error("[APP] ❌ No audio_path received!")

    # Get images - retrieve after start_new_game has stored them
    images = mystery_images.get(sess_id, {})

    # Debug logging
    logger.info("Retrieving images for session %s", sess_id)
    logger.info("Available image keys: %s", list(images.keys()))

    # Opening scene image: we REQUIRE this before "starting" the game.
    # First, try to use any prewarmed image generated in the background
    # right after the premise was created. If it's not available yet,
    # fall back to generating it synchronously here.
    progress(0.9, desc="🎨 Creating scene image...")

    portrait = images.get("_opening_scene", None)
    if not portrait:
        from services.image_service import generate_title_card_on_demand
        from types import SimpleNamespace

        if getattr(state, "premise_setting", None) and getattr(
            state, "premise_victim_name", None
        ):
            victim_stub = SimpleNamespace(name=state.premise_victim_name)
            mystery_like = SimpleNamespace(
                victim=victim_stub,
                setting=state.premise_setting,
            )
            logger.info(
                "Generating opening scene image for new mystery (fallback)..."
            )
            portrait = generate_title_card_on_demand(mystery_like)
            if portrait:
                # Merge into existing images dict without clobbering
                images = mystery_images.get(sess_id, {}) or {}
                images["_opening_scene"] = portrait
                mystery_images[sess_id] = images
                logger.info("Generated opening scene image: %s", portrait)

    if portrait:
        # Ensure path is absolute and file exists
        if not os.path.isabs(portrait):
            portrait = os.path.abspath(portrait)

        if not os.path.exists(portrait):
            logger.warning(
                "Opening scene image file does not exist: %s", portrait
            )
            portrait = None
        else:
            logger.info("Opening scene image file exists: %s", portrait)

    # Only show a portrait if we have an opening scene image
    display_portrait = portrait
    logger.info(
        "[APP] Portrait to display: %s (visible=%s)",
        display_portrait,
        bool(display_portrait),
    )

    # Convert alignment_data to Gradio subtitles format
    subtitles = convert_alignment_to_subtitles(alignment_data)

    # Update audio component with game audio and subtitles
    audio_update = None
    if audio_path:
        audio_update = gr.update(
            value=audio_path,
            subtitles=subtitles,
            autoplay=True,
        )

    # Build victim/case HTML from premise (full mystery still loading)
    victim_html = f"""
    <div style="margin-bottom: 12px;">
        <div style="font-weight: 700; margin-bottom: 8px; font-size: 1.2em; padding-bottom: 8px;">
            The Murder of {state.premise_victim_name}
        </div>
        <div style="font-weight: 600; color: var(--accent-blue); margin-bottom: 8px;">Victim:</div>
        <div style="color: var(--text-primary); margin-bottom: 12px;">{state.premise_victim_name}</div>
        <div style="font-weight: 600; color: var(--accent-blue); margin-bottom: 8px;">Scene:</div>
        <div style="color: var(--text-primary);">{state.premise_setting}</div>
    </div>
    """

    # Final progress
    progress(1.0, desc="🎮 Let's play!")
    
    # Check voice mode for any UI adaptation
    voice_mode = getattr(state, "voice_mode", "full")
    if voice_mode == "text_only":
        logger.info("[APP] Running in Silent Film mode (no voices)")

    yield [
        # Speaker - show when game starts
        f'<div class="speaker-name" style="padding: 16px 0 !important;">🗣️ {speaker} SPEAKING...</div>',
        # Audio with subtitles
        audio_update,
        # Portrait - set the image value (CSS handles visibility)
        display_portrait,
        # Show game UI
        gr.update(visible=True),  # input_row
        gr.update(visible=False),  # setup_wizard - hide wizard
        # Side panels - show "loading" state, timer will update when ready
        victim_html,
        format_suspects_list_html(None, state.suspects_talked_to, loading=True),
        format_locations_html(None, state.searched_locations, loading=True),
        format_clues_html(state.clues_found),
        # Accusations
        format_accusations_html(state.wrong_accusations),
        # Tab components (replicated from accordions)
        format_dashboard_html(
            None,
            state.clues_found,
            state.suspects_talked_to,
            state.searched_locations,
            state.suspect_states,
            state.wrong_accusations
        ),
        victim_html,
        format_suspects_list_html(None, state.suspects_talked_to, loading=True),
        format_locations_html(None, state.searched_locations, loading=True),
        format_clues_html(state.clues_found),
        format_accusations_html(state.wrong_accusations),
        format_detective_notebook_html(state.suspect_states),
        # Activate timer to check when mystery is ready
        gr.update(active=True),
    ]


def check_mystery_ready(sess_id: str):
    """Timer callback to check if full mystery is ready and update UI."""
    sess_id = normalize_session_id(sess_id)
    state = get_or_create_state(sess_id)
    ready = getattr(state, "mystery_ready", False)
    logger.info(
        "[APP] Timer tick - session: %s, mystery_ready: %s",
        sess_id[:8] if sess_id else "None",
        ready,
    )

    if ready and state.mystery is not None:
        # Mystery is ready - update UI and stop timer
        # Note: Portraits may still be loading - they'll appear when user clicks Suspects tab
        logger.info("[APP] Timer: Full mystery ready, updating UI panels")
        victim_html = format_victim_scene_html(state.mystery)
        suspects_html = format_suspects_list_html(
            state.mystery,
            state.suspects_talked_to,
            loading=False,
            suspect_states=state.suspect_states,
            portrait_images=mystery_images.get(sess_id, {})
        )
        locations_html = format_locations_html(
            state.mystery,
            state.searched_locations,
            loading=False,
            location_images=mystery_images.get(sess_id, {}),
        )
        dashboard_html = format_dashboard_html(
            state.mystery,
            state.clues_found,
            state.suspects_talked_to,
            state.searched_locations,
            state.suspect_states,
            state.wrong_accusations
        )
        return [
            victim_html,
            suspects_html,
            locations_html,
            # Tab components (replicated from accordions)
            dashboard_html,
            victim_html,
            suspects_html,
            locations_html,
            gr.update(active=False),  # Stop the timer
        ]
    else:
        # Mystery still loading - keep timer active, no UI changes
        return [
            gr.update(),  # victim_scene_html - no change
            gr.update(),  # suspects_list_html - no change
            gr.update(),  # locations_html - no change
            # Tab components - no change
            gr.update(),  # dashboard_html_tab
            gr.update(),
            gr.update(),
            gr.update(),
            gr.update(active=True),  # Keep timer running
        ]


def on_custom_message(message: str, sess_id: str):
    """Handle free-form text input (currently unused - voice only)."""
    sess_id = normalize_session_id(sess_id)
    if not message.strip():
        return [gr.update()] * 9

    # Store previous state to detect what changed
    state_before = get_or_create_state(sess_id)
    previous_locations = (
        set(state_before.searched_locations)
        if state_before.searched_locations
        else set()
    )
    previous_suspects = (
        set(state_before.suspects_talked_to)
        if state_before.suspects_talked_to
        else set()
    )

    _response, audio_path, speaker, state, alignment_data = (
        process_player_action("custom", "", message, sess_id)
    )

    # Refresh images dict after processing (in case new images were generated)
    images = mystery_images.get(sess_id, {})
    logger.info(
        "Available images for session %s: %s", sess_id, list(images.keys())
    )

    # Determine image to display based on action type
    display_portrait = None

    # Check what changed in this turn
    current_locations = (
        set(state.searched_locations) if state.searched_locations else set()
    )
    current_suspects = (
        set(state.suspects_talked_to) if state.suspects_talked_to else set()
    )

    newly_searched_location = current_locations - previous_locations
    newly_talked_suspect = current_suspects - previous_suspects

    # Priority 0: If speaker is a suspect name, show their portrait directly
    # This is the most reliable method since state comparison can fail
    if speaker and speaker != "Game Master":
        suspect_portrait = images.get(speaker, None)
        if suspect_portrait:
            logger.info(
                "✓ Found portrait for speaker %s: %s", speaker, suspect_portrait
            )
            display_portrait = suspect_portrait

    # Priority 1: Check if a suspect was just talked to
    if not display_portrait and newly_talked_suspect:
        suspect_name = list(newly_talked_suspect)[0]
        logger.info("Looking for portrait for suspect: %s", suspect_name)
        portrait = images.get(suspect_name, None)
        if portrait:
            logger.info(
                "✓ Found portrait for suspect %s: %s", suspect_name, portrait
            )
            display_portrait = portrait
        else:
            logger.warning(
                "✗ No portrait found for suspect %s in images dict",
                suspect_name,
            )
            # Try to get it directly from mystery_images in case of timing issue
            session_images = mystery_images.get(sess_id, {})
            portrait = session_images.get(suspect_name, None)
            if portrait:
                logger.info("✓ Found portrait in direct lookup: %s", portrait)
                display_portrait = portrait
                # Update images dict for next time
                images[suspect_name] = portrait

    # Priority 2: Check if a location was just searched
    if not display_portrait and newly_searched_location:
        location = list(newly_searched_location)[0]
        scene_image = images.get(location, None)
        
        # Fallback: try case-insensitive match if exact match fails
        if not scene_image:
            location_lower = location.lower()
            for key, value in images.items():
                if key.lower() == location_lower:
                    scene_image = value
                    logger.info(
                        "Found scene image via case-insensitive match: %s -> %s",
                        location,
                        key,
                    )
                    break
        
        # Fallback: try partial match via clue locations
        if not scene_image and state.mystery:
            location_lower = location.lower()
            for clue in state.mystery.clues:
                clue_location = clue.location
                if clue_location.lower() == location_lower or location_lower in clue_location.lower():
                    scene_image = images.get(clue_location, None)
                    if scene_image:
                        logger.info(
                            "Found scene image via clue location match: %s -> %s",
                            location,
                            clue_location,
                        )
                        break
        
        if scene_image:
            logger.info("Displaying scene image for location: %s", location)
            display_portrait = scene_image
        else:
            logger.warning(
                "Location %s searched but no scene image found. Available keys: %s",
                location,
                list(images.keys()),
            )

    # Priority 3: Fall back to opening scene image (Game Master)
    if not display_portrait:
        display_portrait = images.get("_opening_scene", None)
        if display_portrait:
            logger.info("Displaying opening scene image (Game Master)")

    # Priority 4: If nothing available, leave the current portrait unchanged
    if not display_portrait:
        logger.info("No portrait available; leaving current image unchanged")

    # Convert alignment_data to Gradio subtitles format
    # Use alignment data directly - it represents what was actually spoken
    subtitles = convert_alignment_to_subtitles(alignment_data)

    portrait_update = (
        gr.update(value=display_portrait, visible=True)
        if display_portrait
        else gr.update()
    )

    return [
        f'<div class="speaker-name" style="padding: 16px 0 !important;">🗣️ {speaker} SPEAKING...</div>',
        (
            gr.update(value=audio_path, subtitles=subtitles)
            if audio_path
            else None
        ),
        portrait_update,
        format_victim_scene_html(state.mystery),
        format_suspects_list_html(
            state.mystery,
            state.suspects_talked_to,
            suspect_states=state.suspect_states,
            portrait_images=mystery_images.get(sess_id, {})
        ),
        format_locations_html(
            state.mystery,
            state.searched_locations,
            location_images=mystery_images.get(sess_id, {}),
        ),
        format_clues_html(state.clues_found),
        format_accusations_html(state.wrong_accusations),
        format_detective_notebook_html(state.suspect_states),
        "",  # Clear text input
    ]


def infer_voice_action_type(message: str, state) -> Tuple[str, str]:
    """Infer action_type and target from a transcribed voice command.

    Returns:
        (action_type, target)
        where action_type is one of: "talk", "search", "accuse", "custom"
    """
    text = (message or "").strip()
    text_lower = text.lower()

    # Default: treat as free-form custom message
    action_type = "custom"
    target = ""

    # Simple search intent detection
    search_prefixes = [
        "search ",
        "search the ",
        "search in ",
        "look in ",
        "look around ",
        "look at ",
        "check ",
        "investigate ",
    ]
    if any(text_lower.startswith(p) for p in search_prefixes):
        action_type = "search"

        # Try to map to a known location using available locations from state
        target = text
        try:
            available_locations = (
                state.get_available_locations()
                if hasattr(state, "get_available_locations")
                else []
            )
        except Exception:  # noqa: BLE001
            available_locations = []

        best_match = None
        best_score = 0
        for loc in available_locations:
            loc_lower = loc.lower()
            # Score simple substring overlap
            if loc_lower in text_lower or text_lower in loc_lower:
                score = len(loc_lower)
                if score > best_score:
                    best_score = score
                    best_match = loc

        if best_match:
            target = best_match
        return action_type, target

    # Could extend later for explicit "talk to X" or "accuse X" patterns
    return action_type, target


def on_voice_input(audio_path: str, sess_id, progress=gr.Progress()):
    """Handle voice input with two-stage yield for faster perceived response.

    Stage 1 (fast): Transcribe + run LLM logic, yield text/panels immediately
    Stage 2 (slow): Generate TTS audio + images, yield final update with audio
    """
    if not audio_path:
        yield [gr.update()] * 16
        return

    # Normalize session id so it matches what on_start_game used
    sess_id = normalize_session_id(sess_id)

    # Check if game has been started
    state_before = get_or_create_state(sess_id)
    if not state_before.mystery and not getattr(
        state_before, "premise_setting", None
    ):
        logger.warning("[APP] Voice input received but no game started yet")
        yield [gr.update()] * 16
        return

    # Show progress indicator while processing
    progress(0, desc="🗣️ Transcribing...")
    yield [gr.update()] * 16

    # Store previous state to detect what changed
    # IMPORTANT: Make copies of the lists since state is mutated in place
    previous_locations = (
        set(list(state_before.searched_locations))
        if state_before.searched_locations
        else set()
    )
    previous_suspects = (
        set(list(state_before.suspects_talked_to))
        if state_before.suspects_talked_to
        else set()
    )
    logger.info(
        "[APP] Before processing - suspects talked to: %s", previous_suspects
    )

    # Transcribe
    t0 = time.perf_counter()
    text = transcribe_audio(audio_path)
    t1 = time.perf_counter()
    logger.info("[PERF] Transcription took %.2fs", t1 - t0)

    if not text.strip():
        yield [gr.update()] * 16
        return

    # Infer high-level action type from the transcribed text
    action_type, target = infer_voice_action_type(text, state_before)

    # ========== STAGE 1: FAST - Run LLM logic only ==========
    # Use the full 0→100 range for the "thinking" phase
    progress(0.5, desc="🧠 Figuring out what happens...")

    t2 = time.perf_counter()
    clean_response, speaker, state, actions, audio_path_from_tool = (
        run_action_logic(
            action_type,
            target,
            text if action_type == "custom" else "",
            sess_id,
        )
    )
    t3 = time.perf_counter()
    logger.info("[PERF] Action logic took %.2fs", t3 - t2)
    progress(1.0, desc="🧠 Figuring out what happens...")

    # Get images dict (may not have new portrait yet)
    images = mystery_images.get(sess_id, {})

    # Determine image to display based on action type
    display_portrait = None

    # Check what changed in this turn
    current_locations = (
        set(state.searched_locations) if state.searched_locations else set()
    )
    current_suspects = (
        set(state.suspects_talked_to) if state.suspects_talked_to else set()
    )

    newly_searched_location = current_locations - previous_locations
    newly_talked_suspect = current_suspects - previous_suspects

    # Priority 0: If speaker is a suspect name, show their portrait directly
    # (may not exist yet on first talk - will be generated in stage 2)
    if speaker and speaker != "Game Master":
        suspect_portrait = images.get(speaker, None)
        if suspect_portrait:
            logger.info(
                "✓ Found portrait for speaker %s: %s", speaker, suspect_portrait
            )
            display_portrait = suspect_portrait

    # Priority 1: Check if a suspect was just talked to
    if not display_portrait and newly_talked_suspect:
        suspect_name = list(newly_talked_suspect)[0]
        portrait = images.get(suspect_name, None)
        if portrait:
            logger.info(
                "Stage 2: Using portrait for newly talked suspect %s: %s",
                suspect_name,
                portrait,
            )
            display_portrait = portrait

    # Priority 2: Check if a location was just searched
    if not display_portrait and newly_searched_location:
        location = list(newly_searched_location)[0]
        scene_image = images.get(location, None)
        if scene_image:
            logger.info(
                "Stage 2: Using scene image for newly searched location %s: %s",
                location,
                scene_image,
            )
            display_portrait = scene_image

    # Priority 3: Fall back to opening scene image (Game Master)
    if not display_portrait:
        opening_scene = images.get("_opening_scene", None)
        if opening_scene:
            logger.info(
                "Stage 2: Falling back to opening scene image: %s", opening_scene
            )
        display_portrait = opening_scene

    # Priority 4: If nothing available, keep whatever image is already showing
    if not display_portrait:
        logger.info("No portrait available in Stage 1; keeping existing image")

    # YIELD STAGE 1: Show text response + updated panels immediately (no audio yet)
    logger.info("[APP] Stage 1 complete - yielding fast UI update")

    portrait_update = (
        gr.update(value=display_portrait, visible=True)
        if display_portrait
        else gr.update()
    )

    yield [
        f'<div class="speaker-name" style="padding: 16px 0 !important;">🗣️ {speaker} SPEAKING...</div>',
        gr.update(),  # Audio placeholder - will be filled in stage 2
        portrait_update,
        format_victim_scene_html(state.mystery),
        format_suspects_list_html(
            state.mystery,
            state.suspects_talked_to,
            suspect_states=state.suspect_states,
            portrait_images=mystery_images.get(sess_id, {})
        ),
        format_locations_html(
            state.mystery,
            state.searched_locations,
            location_images=mystery_images.get(sess_id, {}),
        ),
        format_clues_html(state.clues_found),
        format_accusations_html(state.wrong_accusations),
        format_detective_notebook_html(state.suspect_states),
        # Tab components (replicated from accordions)
        format_dashboard_html(
            state.mystery,
            state.clues_found,
            state.suspects_talked_to,
            state.searched_locations,
            state.suspect_states,
            state.wrong_accusations
        ),
        format_victim_scene_html(state.mystery),
        format_suspects_list_html(
            state.mystery,
            state.suspects_talked_to,
            suspect_states=state.suspect_states,
            portrait_images=mystery_images.get(sess_id, {})
        ),
        format_locations_html(
            state.mystery,
            state.searched_locations,
            location_images=mystery_images.get(sess_id, {}),
        ),
        format_clues_html(state.clues_found),
        format_accusations_html(state.wrong_accusations),
        format_detective_notebook_html(state.suspect_states),
    ]

    # ========== STAGE 2: SLOW - Generate audio + images ==========
    # Restart the progress counter for the voice generation phase
    progress(0, desc="🔊 Generating voice...")
    # Use background_images=False so portrait is ready before we yield
    t4 = time.perf_counter()
    audio_resp, alignment_data = generate_turn_media(
        clean_response,
        speaker,
        state,
        actions,
        audio_path_from_tool,
        sess_id,
        background_images=False,  # Wait for portrait so it's ready in Stage 2
    )
    t5 = time.perf_counter()
    logger.info("[PERF] Media generation took %.2fs", t5 - t4)

    # Refresh images dict after media generation (portraits/scenes may be new)
    images = mystery_images.get(sess_id, {})
    logger.info(
        "Available images for session %s: %s", sess_id, list(images.keys())
    )

    # Re-determine portrait (may have been generated in stage 2)
    display_portrait = None

    # Priority 0: If speaker is a suspect name, show their portrait directly
    if speaker and speaker != "Game Master":
        suspect_portrait = images.get(speaker, None)
        if suspect_portrait:
            logger.info(
                "✓ Found portrait for speaker %s: %s", speaker, suspect_portrait
            )
            display_portrait = suspect_portrait

    # Priority 1: Check if a suspect was just talked to
    if not display_portrait and newly_talked_suspect:
        suspect_name = list(newly_talked_suspect)[0]
        portrait = images.get(suspect_name, None)
        if portrait:
            display_portrait = portrait

    # Priority 2: Check if a location was just searched
    if not display_portrait and newly_searched_location:
        location = list(newly_searched_location)[0]
        scene_image = images.get(location, None)
        
        # Fallback: try case-insensitive match if exact match fails
        if not scene_image:
            location_lower = location.lower()
            for key, value in images.items():
                if key.lower() == location_lower:
                    scene_image = value
                    logger.info(
                        "Stage 2: Found scene image via case-insensitive match: %s -> %s",
                        location,
                        key,
                    )
                    break
        
        # Fallback: try partial match (location name contains searched location or vice versa)
        if not scene_image and state.mystery:
            location_lower = location.lower()
            for clue in state.mystery.clues:
                clue_location = clue.location
                if clue_location.lower() == location_lower or location_lower in clue_location.lower():
                    scene_image = images.get(clue_location, None)
                    if scene_image:
                        logger.info(
                            "Stage 2: Found scene image via clue location match: %s -> %s",
                            location,
                            clue_location,
                        )
                        break
        
        if scene_image:
            logger.info(
                "Stage 2: Using scene image for location %s: %s",
                location,
                scene_image,
            )
            display_portrait = scene_image
        else:
            logger.warning(
                "Stage 2: Location %s searched but no scene image found in images dict. Available keys: %s",
                location,
                list(images.keys()),
            )

    # Priority 3: Fall back to opening scene image (Game Master)
    if not display_portrait:
        opening = images.get("_opening_scene", None)
        if opening:
            logger.info("Stage 2: Falling back to opening scene: %s", opening)
        display_portrait = opening

    # Priority 4: If nothing available, keep whatever image is already showing
    if not display_portrait:
        logger.info("No portrait available in Stage 2; keeping existing image")

    # Convert alignment_data to Gradio subtitles format
    subtitles = convert_alignment_to_subtitles(alignment_data)

    # YIELD STAGE 2: Final update with audio + updated portrait
    progress(1.0, desc="Done!")
    logger.info(
        "[APP] Stage 2 complete - yielding final UI with audio, portrait=%s",
        display_portrait,
    )

    portrait_update = (
        gr.update(value=display_portrait, visible=True)
        if display_portrait
        else gr.update()
    )

    yield [
        f'<div class="speaker-name" style="padding: 16px 0 !important;">🗣️ {speaker} SPEAKING...</div>',
        (
            gr.update(value=audio_resp, subtitles=subtitles, autoplay=True)
            if audio_resp
            else gr.update()
        ),
        portrait_update,
        format_victim_scene_html(state.mystery),
        format_suspects_list_html(
            state.mystery,
            state.suspects_talked_to,
            suspect_states=state.suspect_states,
            portrait_images=mystery_images.get(sess_id, {})
        ),
        format_locations_html(
            state.mystery,
            state.searched_locations,
            location_images=mystery_images.get(sess_id, {}),
        ),
        format_clues_html(state.clues_found),
        format_accusations_html(state.wrong_accusations),
        format_detective_notebook_html(state.suspect_states),
        # Tab components (replicated from accordions)
        format_dashboard_html(
            state.mystery,
            state.clues_found,
            state.suspects_talked_to,
            state.searched_locations,
            state.suspect_states,
            state.wrong_accusations
        ),
        format_victim_scene_html(state.mystery),
        format_suspects_list_html(
            state.mystery,
            state.suspects_talked_to,
            suspect_states=state.suspect_states,
            portrait_images=mystery_images.get(sess_id, {})
        ),
        format_locations_html(state.mystery, state.searched_locations),
        format_clues_html(state.clues_found),
        format_accusations_html(state.wrong_accusations),
        format_detective_notebook_html(state.suspect_states),
    ]


def reset_voice_input():
    """Clear the voice input so it's ready for the next recording."""
    return gr.update(value=None)


def on_audio_stop(sess_id):
    """Reset speaker name to placeholder when audio playback ends."""
    sess_id = normalize_session_id(sess_id)
    state = get_or_create_state(sess_id)
    """Reset speaker name to placeholder when audio playback ends."""
    return f'<div class="speaker-name">The Murder of {state.premise_victim_name if state.premise_victim_name else "..."}</div>'


def on_suspects_tab_select(sess_id, evt: gr.SelectData):
    """Refresh suspects list when Suspects tab is selected - loads latest portraits.
    
    Uses gr.SelectData to detect which tab was clicked. Only refreshes for suspects tab.
    """
    # Check if the suspects tab was selected (by checking tab value/index)
    # evt.value contains the tab label, evt.index contains the tab index
    tab_value = getattr(evt, 'value', None)
    
    # Only refresh if Suspects tab is selected (check for the emoji label)
    if tab_value != "🎭 SUSPECTS":
        return gr.update()  # No update for other tabs
    
    return _refresh_suspects_list(sess_id, "tab select")


def on_refresh_suspects_click(sess_id):
    """Manual refresh button click - loads latest portraits."""
    return _refresh_suspects_list(sess_id, "button click")


def _refresh_suspects_list(sess_id, trigger: str):
    """Shared logic to refresh suspects list with latest portraits."""
    sess_id = normalize_session_id(sess_id)
    state = get_or_create_state(sess_id)
    
    if not state.mystery:
        return gr.update()
    
    # Get latest portraits from mystery_images
    session_images = mystery_images.get(sess_id, {})
    suspect_names = [s.name for s in state.mystery.suspects]
    portraits_ready = sum(1 for name in suspect_names if name in session_images)
    
    logger.info(
        "[APP] Suspects refresh (%s) - %d/%d portraits ready",
        trigger,
        portraits_ready,
        len(suspect_names)
    )
    
    return format_suspects_list_html(
        state.mystery,
        state.suspects_talked_to,
        loading=False,
        suspect_states=state.suspect_states,
        portrait_images=session_images
    )

