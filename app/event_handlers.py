"""Event handlers for the murder mystery game."""

import os
import logging
import time
from typing import Tuple
import gradio as gr
from mystery_config import get_settings_for_era, create_validated_config
from game.state_manager import get_or_create_state, mystery_images
from game.startup import start_new_game_staged, refresh_voices
from services.game_memory import reset_game_memory
from services.mystery_oracle import reset_mystery_oracle
from game.handlers import process_player_action, run_action_logic
from game.media import generate_turn_media
from services.tts_service import transcribe_audio
from services.perf_tracker import perf
from ui.formatters import (
    format_suspects_list_html,
    format_locations_html,
    format_clues_html,
    format_dashboard_html,
    format_accusations_tab_html,
    format_timeline_html,
    format_case_file_html,
)
from services.api_keys import set_session_key, get_session_keys, has_required_keys
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


def format_accusations_html(state) -> str:
    """Format accusations HTML with history, checklist, and fired state.
    
    Args:
        state: GameState object (or int for backward compatibility)
    """
    # Handle backward compatibility - if passed just an int, use simple format
    if isinstance(state, int):
        wrong = state
        pips = ""
        for i in range(3):
            cls = "accusations-pip used" if i < wrong else "accusations-pip"
            pips += f'<span class="{cls}"></span>'
        return f'<div class="accusations-display">Accusations:<span>{pips}</span></div>'
    
    # Full state - use enhanced formatter
    # Build current requirements if we have a mystery
    current_requirements = {}
    if hasattr(state, 'mystery') and state.mystery:
        # Default requirements - will be populated when player has a target suspect
        current_requirements = {
            'has_minimum_clues': len(state.clue_ids_found) >= 2,
            'alibi_disproven': False,  # Requires a target suspect
            'motive_established': False,
            'opportunity_proven': False,
        }
    
    return format_accusations_tab_html(
        wrong_accusations=state.wrong_accusations,
        accusation_history=state.accusation_history,
        current_requirements=current_requirements,
        fired=state.fired,
    )


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

    # Before doing anything expensive, make sure we have the keys we need.
    # This prevents confusing OpenAI auth errors when the user hasn't set a key.
    can_play, missing = has_required_keys(sess_id)
    if not can_play:
        # Use the status tracker overlay for a clear, in-world message.
        missing_str = ", ".join(missing)
        progress(0, desc="⚠️ Missing API keys")
        progress(
            1.0,
            desc=f"⚠️ Cannot start mystery – need: {missing_str}. "
                 "Open the 🔑 Settings tab to enter your keys.",
        )
        # Do NOT mark the game as started; leave wizard visible.
        # Return no-op updates for all outputs.
        return [
            gr.update(),  # game_started_marker
            gr.update(),  # speaker_html
            gr.update(),  # audio_output
            gr.update(),  # portrait_image
            gr.update(),  # input_row
            gr.update(),  # suspects_list_html
            gr.update(),  # locations_html
            gr.update(),  # clues_html
            gr.update(),  # accusations_html
            gr.update(),  # suspects_list_html_tab
            gr.update(),  # locations_html_tab
            gr.update(),  # clues_html_tab
            gr.update(),  # accusations_html_tab
            gr.update(),  # timeline_html_tab
            gr.update(),  # mystery_check_timer
        ]

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

    # Opening scene image: wait briefly for image, but don't block audio playback
    # Image will appear when ready via timer callback
    progress(0.9, desc="🎨 Preparing scene...")

    portrait = images.get("_opening_scene", None)
    if not portrait:
        # Wait briefly (5 seconds max) for the image, but don't delay audio
        wait_start = time.time()
        max_wait = 5.0  # Shorter wait - prioritize audio playback
        poll_interval = 0.1  # 100ms
        
        logger.info("[APP] Opening scene not ready, waiting up to %.1fs...", max_wait)
        while time.time() - wait_start < max_wait:
            # Re-check the images dict (background thread updates it)
            images = mystery_images.get(sess_id, {})
            portrait = images.get("_opening_scene", None)
            if portrait:
                wait_time = time.time() - wait_start
                logger.info("[APP] ✅ Opening scene ready after %.2fs", wait_time)
                break
            time.sleep(poll_interval)
        
        if not portrait:
            logger.info("[APP] Opening scene still loading - will appear when ready via timer")

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
    # Always enable autoplay when audio exists - image will appear when ready
    audio_update = None
    if audio_path:
        # Always autoplay if audio exists - don't block audio waiting for image
        # The image will appear when ready via the timer callback
        audio_update = gr.update(
            value=audio_path,
            subtitles=subtitles,
            autoplay=True,  # Always autoplay - image will appear when ready
        )
        logger.info("[APP] Audio autoplay enabled (image will appear when ready)")

    # Final progress
    progress(1.0, desc="🎮 Let's play!")
    
    # Check voice mode for any UI adaptation
    voice_mode = getattr(state, "voice_mode", "full")
    if voice_mode == "text_only":
        logger.info("[APP] Running in Silent Film mode (no voices)")

    yield [
        # FIRST: Populate game_started_marker with content → CSS :has() detects it
        '<div class="game-active" data-game-started="true"></div>',  # game_started_marker
        # Speaker - show when game starts
        f'<div class="speaker-name" style="padding: 16px 0 !important;">🗣️ {speaker} SPEAKING...</div>',
        # Audio with subtitles
        audio_update,
        # Portrait - set the image value (CSS handles visibility)
        display_portrait,
        # Show game UI
        gr.update(visible=True),  # input_row
        # Side panels - show "loading" state, timer will update when ready
        format_suspects_list_html(None, state.suspects_talked_to, loading=True, layout="column"),
        format_locations_html(None, state.searched_locations, loading=True),
        format_clues_html(state.clues_found),
        # Accusations
        format_accusations_html(state),
        # Tab components (suspects, locations, clues, accusations, timeline)
        format_suspects_list_html(None, state.suspects_talked_to, loading=True, layout="row"),
        format_locations_html(None, state.searched_locations, loading=True),
        format_clues_html(state.clues_found),
        format_accusations_html(state),
        format_timeline_html(state.discovered_timeline),
        # Activate timer to check when mystery is ready
        gr.update(active=True),
        # Show restart button
        gr.update(visible=True),  # restart_btn
    ]
    # NOTE: on_start_game outputs 19 items (game_started_marker + input_row + mystery_check_timer + game_outputs)
    # game_outputs now has 18 items including dashboard_html_main, but on_start_game doesn't return dashboard_html_main
    # since it's wired separately. The yield above is for start_btn.click outputs, not game_outputs.


def check_mystery_ready(sess_id: str):
    """Timer callback to check if full mystery is ready and update UI.
    
    Also updates the opening scene image when it becomes available.
    """
    import sys
    sess_id = normalize_session_id(sess_id)
    state = get_or_create_state(sess_id)
    ready = getattr(state, "mystery_ready", False)
    images = mystery_images.get(sess_id, {})
    opening_scene = images.get("_opening_scene", None)
    suspect_previews = getattr(state, "suspect_previews", [])
    
    # Force print to see timer is running
    print(f"[TIMER] tick - sess={sess_id[:8] if sess_id else 'None'}, ready={ready}, previews={len(suspect_previews)}, opening={bool(opening_scene)}", flush=True)
    sys.stdout.flush()
    
    logger.info(
        "[APP] Timer tick - session: %s, mystery_ready: %s, opening_scene: %s",
        sess_id[:8] if sess_id else "None",
        ready,
        bool(opening_scene),
    )

    if ready and state.mystery is not None:
        # Mystery is ready - update UI and stop timer
        # Note: Portraits may still be loading - they'll appear when user clicks Suspects tab
        logger.info("[APP] Timer: Full mystery ready, updating UI panels")
        # Side panel: column layout (portrait on top)
        suspects_html_panel = format_suspects_list_html(
            state.mystery,
            state.suspects_talked_to,
            loading=False,
            suspect_states=state.suspect_states,
            portrait_images=images,
            layout="column",
        )
        # Tabs: row layout (portrait on left)
        suspects_html_tab = format_suspects_list_html(
            state.mystery,
            state.suspects_talked_to,
            loading=False,
            suspect_states=state.suspect_states,
            portrait_images=images,
            layout="row",
        )
        locations_html = format_locations_html(
            state.mystery,
            state.searched_locations,
            loading=False,
            location_images=images,
            unlocked_locations=state.unlocked_locations,
        )
        # Update portrait if opening scene is available
        portrait_update = gr.update(value=opening_scene) if opening_scene else gr.update()
        
        case_file_html = format_case_file_html(
            state.mystery,
            suspects_talked_to=state.suspects_talked_to,
            suspect_states=state.suspect_states,
            clues_found=state.clues_found,
            wrong_accusations=state.wrong_accusations,
            game_over=state.game_over,
            won=state.won,
        )
        return [
            portrait_update,  # Opening scene image
            suspects_html_panel,  # Side panel (column layout)
            locations_html,
            # Tab components (replicated from accordions)
            suspects_html_tab,  # Tabs (row layout)
            locations_html,
            case_file_html,    # Case File (main tab)
            gr.update(active=False),  # Stop the timer
        ]
    else:
        # Mystery still loading - but check if opening scene or suspect previews are ready
        portrait_update = gr.update(value=opening_scene) if opening_scene else gr.update()
        
        # Check for early suspect previews (available ~2s before full mystery)
        # Note: suspect_previews already loaded at line 369
        print(f"[TIMER] Checking previews: count={len(suspect_previews)}, data={suspect_previews[:2] if suspect_previews else 'empty'}", flush=True)
        if suspect_previews and len(suspect_previews) > 0:
            try:
                print(f"[TIMER] ✅ Showing previews: {[sp.get('name', '?') for sp in suspect_previews]}", flush=True)
                from ui.formatters import format_suspect_previews_html
                suspects_preview_panel = format_suspect_previews_html(suspect_previews, layout="column")
                suspects_preview_tab = format_suspect_previews_html(suspect_previews, layout="row")
                # Update case file with suspect previews so names appear early
                case_file_preview = format_case_file_html(
                    mystery=None,
                    suspects_talked_to=state.suspects_talked_to,
                    suspect_states=state.suspect_states,
                    clues_found=state.clues_found,
                    wrong_accusations=state.wrong_accusations,
                    game_over=state.game_over,
                    won=state.won,
                    suspect_previews=suspect_previews,
                )
                print("[TIMER] Preview HTML generated, returning to UI", flush=True)
                return [
                    portrait_update,  # Update opening scene if available
                    suspects_preview_panel,  # suspects_list_html - show previews early!
                    gr.update(),  # locations_html - no change
                    # Tab components
                    suspects_preview_tab,  # suspects tab - show previews early!
                    gr.update(),  # locations_html_tab
                    case_file_preview,  # case_file_html_main - show suspect names from previews!
                    gr.update(active=True),  # Keep timer running
                ]
            except Exception as e:
                print(f"[TIMER] ❌ Error showing previews: {e}", flush=True)
                import traceback
                traceback.print_exc()
        
        return [
            portrait_update,  # Update opening scene if available
            gr.update(),  # suspects_list_html - no change
            gr.update(),  # locations_html - no change
            # Tab components - no change
            gr.update(),  # suspects_list_html_tab
            gr.update(),  # locations_html_tab
            gr.update(),  # case_file_html_main - no change
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
        format_suspects_list_html(
            state.mystery,
            state.suspects_talked_to,
            suspect_states=state.suspect_states,
            portrait_images=mystery_images.get(sess_id, {}),
            layout="column",  # Side panel: vertical layout
        ),
        format_locations_html(
            state.mystery,
            state.searched_locations,
            location_images=mystery_images.get(sess_id, {}),
            unlocked_locations=state.unlocked_locations,
        ),
        format_clues_html(state.clues_found),
        format_accusations_html(state),
        format_timeline_html(state.discovered_timeline),
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
        yield [gr.update()] * 15  # Must match game_outputs count
        return

    # Normalize session id so it matches what on_start_game used
    sess_id = normalize_session_id(sess_id)

    # Check if game has been started
    state_before = get_or_create_state(sess_id)
    if not state_before.mystery and not getattr(
        state_before, "premise_setting", None
    ):
        logger.warning("[APP] Voice input received but no game started yet")
        yield [gr.update()] * 15  # Must match game_outputs count
        return

    # Show progress indicator while processing
    progress(0, desc="🗣️ Transcribing...")
    yield [gr.update()] * 15  # Must match game_outputs count

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

    # Transcribe - TRACKED
    perf.start("transcription", details="Whisper API")
    t0 = time.perf_counter()
    text = transcribe_audio(audio_path)
    t1 = time.perf_counter()
    perf.end("transcription", details=f"{len(text)} chars")
    logger.info("[PERF] Transcription took %.2fs", t1 - t0)

    if not text.strip():
        yield [gr.update()] * 15  # Must match game_outputs count
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
    
    # Get alignment data from ToolOutputStore (stored alongside audio by tool)
    from game.state_manager import get_tool_output_store
    tool_store = get_tool_output_store(sess_id)
    alignment_data_from_tool = tool_store.audio_alignment_data
    
    # Debug: Log accusation state after processing
    if tool_store.accusation:
        logger.info(
            "[APP] Accusation detected - wrong_accusations: %d, is_correct: %s, has_evidence: %s, accusation_history length: %d",
            state.wrong_accusations,
            tool_store.accusation.is_correct,
            tool_store.accusation.has_sufficient_evidence,
            len(state.accusation_history) if hasattr(state, 'accusation_history') else 0
        )
    
    # Check if a secret was revealed this turn (for UI notification)
    secret_reveal_notification = ""
    if tool_store.secret_revealed and tool_store.secret_revealed_by:
        secret_reveal_notification = f'''
        <div class="secret-revealed-notification" style="
            background: linear-gradient(135deg, #2d1b4e 0%, #1a1a2e 100%);
            border: 2px solid #9b59b6;
            border-radius: 8px;
            padding: 12px 16px;
            margin: 8px 0;
            animation: pulse-glow 2s ease-in-out infinite;
        ">
            <span style="font-size: 1.2em;">🔓</span>
            <strong style="color: #bb86fc;">{tool_store.secret_revealed_by}</strong>
            <span style="color: #e0e0e0;"> revealed their secret!</span>
            <div style="color: #aaa; font-size: 0.9em; margin-top: 4px;">Check the Suspects panel to see what they confessed.</div>
        </div>'''
        logger.info("🔓 [UI] Secret reveal notification for %s", tool_store.secret_revealed_by)

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

    # Build speaker HTML with optional secret notification
    speaker_html = f'<div class="speaker-name" style="padding: 16px 0 !important;">🗣️ {speaker} SPEAKING...</div>{secret_reveal_notification}'
    
    yield [
        speaker_html,
        gr.update(),  # Audio placeholder - will be filled in stage 2
        portrait_update,
        format_suspects_list_html(
            state.mystery,
            state.suspects_talked_to,
            suspect_states=state.suspect_states,
            portrait_images=mystery_images.get(sess_id, {}),
            layout="column",  # Side panel: vertical layout
        ),
        format_locations_html(
            state.mystery,
            state.searched_locations,
            location_images=mystery_images.get(sess_id, {}),
            unlocked_locations=state.unlocked_locations,
        ),
        format_clues_html(state.clues_found),
        format_accusations_html(state),
        format_timeline_html(state.discovered_timeline),  # Main tab version
        # Tab components (replicated from accordions)
        format_suspects_list_html(
            state.mystery,
            state.suspects_talked_to,
            suspect_states=state.suspect_states,
            portrait_images=mystery_images.get(sess_id, {}),
            layout="row",  # Tabs: horizontal layout
        ),
        format_locations_html(
            state.mystery,
            state.searched_locations,
            location_images=mystery_images.get(sess_id, {}),
            unlocked_locations=state.unlocked_locations,
        ),
        format_clues_html(state.clues_found),
        format_accusations_html(state),
        format_timeline_html(state.discovered_timeline),  # Tab (mobile)
        format_case_file_html(
            state.mystery,
            suspects_talked_to=state.suspects_talked_to,
            suspect_states=state.suspect_states,
            clues_found=state.clues_found,
            wrong_accusations=state.wrong_accusations,
            game_over=state.game_over,
            won=state.won,
        ),
        # Dashboard (main tab)
        format_dashboard_html(
            state.mystery,
            state.clues_found,
            state.suspects_talked_to,
            state.searched_locations,
            state.suspect_states,
            state.wrong_accusations
        ),
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
        alignment_data_from_tool=alignment_data_from_tool,
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
    # DEBUG: Log what we're using for audio vs subtitles
    logger.info("[AUDIO/SUBTITLE DEBUG] audio_resp=%s", audio_resp[:50] if audio_resp else "None")
    logger.info("[AUDIO/SUBTITLE DEBUG] alignment_data has %d words", len(alignment_data) if alignment_data else 0)
    if alignment_data and len(alignment_data) > 0:
        first_words = [w.get("word", "?") for w in alignment_data[:5]]
        last_words = [w.get("word", "?") for w in alignment_data[-3:]]
        logger.info("[AUDIO/SUBTITLE DEBUG] First 5 words: %s", first_words)
        logger.info("[AUDIO/SUBTITLE DEBUG] Last 3 words: %s", last_words)
    logger.info("[AUDIO/SUBTITLE DEBUG] clean_response first 100 chars: %s", clean_response[:100] if clean_response else "None")
    
    subtitles = convert_alignment_to_subtitles(alignment_data)
    logger.info("[AUDIO/SUBTITLE DEBUG] Generated %d subtitle entries", len(subtitles) if subtitles else 0)

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
        speaker_html,  # Includes secret reveal notification if applicable
        (
            gr.update(value=audio_resp, subtitles=subtitles, autoplay=True)
            if audio_resp
            else gr.update()
        ),
        portrait_update,
        format_suspects_list_html(
            state.mystery,
            state.suspects_talked_to,
            suspect_states=state.suspect_states,
            portrait_images=mystery_images.get(sess_id, {}),
            layout="column",  # Side panel: vertical layout
        ),
        format_locations_html(
            state.mystery,
            state.searched_locations,
            location_images=mystery_images.get(sess_id, {}),
            unlocked_locations=state.unlocked_locations,
        ),
        format_clues_html(state.clues_found),
        format_accusations_html(state),
        format_timeline_html(state.discovered_timeline),  # Main tab version
        # Tab components (replicated from accordions)
        format_suspects_list_html(
            state.mystery,
            state.suspects_talked_to,
            suspect_states=state.suspect_states,
            portrait_images=mystery_images.get(sess_id, {}),
            layout="row",  # Tabs: horizontal layout
        ),
        format_locations_html(
            state.mystery,
            state.searched_locations,
            unlocked_locations=state.unlocked_locations,
        ),
        format_clues_html(state.clues_found),
        format_accusations_html(state),
        format_timeline_html(state.discovered_timeline),  # Tab (mobile)
        format_case_file_html(
            state.mystery,
            suspects_talked_to=state.suspects_talked_to,
            suspect_states=state.suspect_states,
            clues_found=state.clues_found,
            wrong_accusations=state.wrong_accusations,
            game_over=state.game_over,
            won=state.won,
        ),
        # Dashboard (main tab)
        format_dashboard_html(
            state.mystery,
            state.clues_found,
            state.suspects_talked_to,
            state.searched_locations,
            state.suspect_states,
            state.wrong_accusations
        ),
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
        portrait_images=session_images,
        layout="row",  # Tabs: horizontal layout
    )


# =============================================================================
# API KEY HANDLERS
# =============================================================================

def on_save_api_keys(
    openai_key: str,
    elevenlabs_key: str,
    huggingface_key: str,
    sess_id: str,
):
    """Save API keys to session (not persisted to disk).
    
    Returns updates for:
    - openai_key_status
    - elevenlabs_key_status
    - huggingface_key_status
    - keys_status_html
    """
    sess_id = normalize_session_id(sess_id)
    
    results = []
    overall_status = []
    
    # Save OpenAI key
    if openai_key and openai_key.strip():
        success, msg = set_session_key(sess_id, "openai", openai_key)
        if success:
            results.append('<span class="key-status key-ok">✅ Saved</span>')
            overall_status.append("OpenAI ✓")
        else:
            results.append(f'<span class="key-status key-error">❌ {msg}</span>')
            overall_status.append("OpenAI ✗")
    else:
        # Check if env has it
        keys = get_session_keys(sess_id)
        if keys.openai_key:
            results.append('<span class="key-status key-env">✅ From environment</span>')
            overall_status.append("OpenAI (env)")
        else:
            results.append('<span class="key-status key-missing">❌ Required</span>')
            overall_status.append("OpenAI missing!")
    
    # Save ElevenLabs key
    if elevenlabs_key and elevenlabs_key.strip():
        success, msg = set_session_key(sess_id, "elevenlabs", elevenlabs_key)
        if success:
            results.append('<span class="key-status key-ok">✅ Saved</span>')
            overall_status.append("Voice ✓")
            
            # Fetch voices now that API key is set
            try:
                import app.main as main_module
                from services.voice_service import get_voice_service
                import threading
                
                def _fetch_voices_async():
                    """Fetch voices in background thread after API key is set."""
                    try:
                        logger.info("🎤 Fetching voices after API key was set...")
                        voice_service = get_voice_service()
                        if voice_service.is_available:
                            voices = voice_service.get_available_voices(force_refresh=True)
                            if voices:
                                # Update module-level globals
                                main_module.PREFETCHED_VOICES = voices
                                main_module.VOICE_SUMMARY = voice_service.summarize_voices_for_llm(voices)
                                main_module.VOICES_READY.set()
                                logger.info(f"✅ Fetched {len(voices)} voices after API key was set")
                            else:
                                logger.warning("⚠️ No voices returned from ElevenLabs")
                                main_module.VOICES_READY.set()
                        else:
                            logger.warning("⚠️ Voice service not available after setting key")
                            main_module.VOICES_READY.set()
                    except Exception as e:
                        logger.error(f"❌ Voice fetch failed after setting key: {e}")
                        main_module.VOICES_READY.set()
                
                # Fetch voices in background thread
                voice_thread = threading.Thread(target=_fetch_voices_async, daemon=True)
                voice_thread.start()
            except Exception as e:
                logger.error(f"Failed to start voice fetch thread: {e}")
        else:
            results.append(f'<span class="key-status key-error">❌ {msg}</span>')
            overall_status.append("Voice ✗")
    else:
        keys = get_session_keys(sess_id)
        if keys.elevenlabs_key:
            results.append('<span class="key-status key-env">✅ From environment</span>')
            overall_status.append("Voice (env)")
            
            # If key exists in env but voices haven't been fetched, fetch them now
            try:
                import app.main as main_module
                if not main_module.PREFETCHED_VOICES and main_module.VOICES_READY.is_set():
                    # Reset the event and fetch voices
                    main_module.VOICES_READY.clear()
                    from services.voice_service import get_voice_service
                    import threading
                    
                    def _fetch_voices_async():
                        """Fetch voices in background thread when env key exists."""
                        try:
                            logger.info("🎤 Fetching voices (env key detected)...")
                            voice_service = get_voice_service()
                            if voice_service.is_available:
                                voices = voice_service.get_available_voices(force_refresh=True)
                                if voices:
                                    main_module.PREFETCHED_VOICES = voices
                                    main_module.VOICE_SUMMARY = voice_service.summarize_voices_for_llm(voices)
                                    main_module.VOICES_READY.set()
                                    logger.info(f"✅ Fetched {len(voices)} voices from env key")
                                else:
                                    main_module.VOICES_READY.set()
                        except Exception as e:
                            logger.error(f"❌ Voice fetch failed: {e}")
                            main_module.VOICES_READY.set()
                    
                    voice_thread = threading.Thread(target=_fetch_voices_async, daemon=True)
                    voice_thread.start()
            except Exception as e:
                logger.error(f"Failed to fetch voices from env: {e}")
        else:
            results.append('<span class="key-status key-missing">❌ Required</span>')
            overall_status.append("Voice missing!")
    
    # Save HuggingFace key
    if huggingface_key and huggingface_key.strip():
        success, msg = set_session_key(sess_id, "huggingface", huggingface_key)
        if success:
            results.append('<span class="key-status key-ok">✅ Saved</span>')
            overall_status.append("HF ✓")
        else:
            results.append(f'<span class="key-status key-error">❌ {msg}</span>')
            overall_status.append("HF ✗")
    else:
        keys = get_session_keys(sess_id)
        if keys.huggingface_key:
            results.append('<span class="key-status key-env">✅ From environment</span>')
            overall_status.append("HF (env)")
        else:
            results.append('<span class="key-status key-missing">❌ Required</span>')
            overall_status.append("HF missing!")
    
    # Check if we can play
    can_play, missing = has_required_keys(sess_id)
    if can_play:
        status_html = f'<span class="keys-ready">✅ Ready to play! ({", ".join(overall_status)})</span>'
    else:
        status_html = f'<span class="keys-not-ready">⚠️ Missing: {", ".join(missing)}</span>'
    
    return results[0], results[1], results[2], status_html


def check_api_keys_status(sess_id: str):
    """Check current API key status (called on page load)."""
    sess_id = normalize_session_id(sess_id)
    keys = get_session_keys(sess_id)
    status = keys.get_status()
    
    openai_html = _format_key_status(status["openai"])
    elevenlabs_html = _format_key_status(status["elevenlabs"])
    huggingface_html = _format_key_status(status["huggingface"])
    
    can_play, missing = has_required_keys(sess_id)
    if can_play:
        overall = '<span class="keys-ready">✅ Ready to play</span>'
    else:
        overall = f'<span class="keys-not-ready">⚠️ Need: {", ".join(missing)}</span>'
    
    return openai_html, elevenlabs_html, huggingface_html, overall


def _format_key_status(status: str) -> str:
    """Format a key status string to HTML."""
    if "Not set" in status:
        return f'<span class="key-status key-missing">{status}</span>'
    elif "User" in status:
        return f'<span class="key-status key-ok">{status}</span>'
    else:  # Environment
        return f'<span class="key-status key-env">{status}</span>'


def choose_initial_tab(sess_id: str):
    """On page load, pick which main tab should be active.

    If required keys are missing, send player to the 🔑 Settings tab first.
    Otherwise, land on the Game tab.
    """
    sess_id = normalize_session_id(sess_id)
    can_play, _missing = has_required_keys(sess_id)
    # These values must match the tab labels defined in ui_components.py
    target = "Game" if can_play else "🔑 Settings"
    return gr.update(value=target)


def on_restart_game(sess_id: str):
    """Restart the game - reset all state and show the setup wizard again."""
    sess_id = normalize_session_id(sess_id)
    logger.info("[APP] Restarting game for session %s", sess_id[:8])
    
    # Get and reset game state
    state = get_or_create_state(sess_id)
    state.reset_game()
    
    # Clear game memory and oracle
    reset_game_memory()
    reset_mystery_oracle()
    
    # Clear images for this session
    if sess_id in mystery_images:
        mystery_images[sess_id] = {}
        logger.info("[APP] Cleared images for session %s", sess_id[:8])
    
    # Reset performance tracker
    perf.reset(sess_id)
    
    # Return updates to reset UI to initial state
    return [
        '',  # game_started_marker - clear it so wizard shows again
        '<div class="speaker-name" style="display: none;"></div>',  # speaker_html - hide
        gr.update(value=None),  # audio_output - clear audio
        gr.update(value=None),  # portrait_image - clear portrait
        gr.update(visible=False),  # input_row - hide input
        format_suspects_list_html(None, [], loading=False, layout="column"),  # suspects_list_html
        format_locations_html(None, [], loading=False),  # locations_html
        format_clues_html([]),  # clues_html
        format_accusations_html(state),  # accusations_html
        format_suspects_list_html(None, [], loading=False, layout="row"),  # suspects_list_html_tab
        format_locations_html(None, [], loading=False),  # locations_html_tab
        format_clues_html([]),  # clues_html_tab
        format_accusations_html(state),  # accusations_html_tab
        format_timeline_html([]),  # timeline_html_tab
        gr.update(active=False),  # mystery_check_timer - stop timer
        gr.update(visible=False),  # restart_btn - hide restart button
    ]

