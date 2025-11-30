"""Voice-First Murder Mystery Game - 90s Point-and-Click Adventure Style.

A reimagined interface that prioritizes voice output with streaming captions,
styled like classic adventure games (Monkey Island, Day of the Tentacles, Gabriel Knight, etc.)
"""

# IMPORTANT: Load environment variables FIRST, before any other imports
# This ensures USE_MCP and other env vars are available when modules load
from dotenv import load_dotenv
load_dotenv()

import os
import threading
from typing import Dict, List
import gradio as gr
from openai import OpenAI

try:
    from elevenlabs import ElevenLabs

    ELEVENLABS_AVAILABLE = True
except ImportError:
    ELEVENLABS_AVAILABLE = False
    ElevenLabs = None

# Import modular components (AFTER load_dotenv so env vars are available)
from services.tts_service import init_tts_service
from services.perf_tracker import perf, get_perf_summary
from game.state_manager import init_game_handlers, mystery_images
from app.utils import setup_ui_logging, get_ui_logs, get_reveal_status
from app.ui_components import create_ui_components
from app.event_handlers import (
    on_config_generic_change,
    on_wizard_config_change,
    on_refresh_voices,
    on_start_game,
    check_mystery_ready,
    on_voice_input,
    reset_voice_input,
    on_audio_stop,
    on_suspects_tab_select,
    on_refresh_suspects_click,
    on_save_api_keys,
    check_api_keys_status,
)

# Logging - set up early
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
setup_ui_logging()

# =============================================================================
# APP STARTUP - Pre-fetch voices directly (no MCP overhead)
# =============================================================================

logger.info("🚀 Starting Murder Mystery App...")
perf.reset("app_startup")

# Initialize OpenAI client
perf.start("init_openai")
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
perf.end("init_openai")

# Initialize ElevenLabs client
perf.start("init_elevenlabs")
elevenlabs_client = None
if os.getenv("ELEVENLABS_API_KEY") and ELEVENLABS_AVAILABLE:
    try:
        elevenlabs_client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
        logger.info("✅ ElevenLabs client initialized")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"⚠️ Failed to initialize ElevenLabs: {e}")
perf.end("init_elevenlabs")

# Game Master voice
GAME_MASTER_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"

# =============================================================================
# PRE-FETCH VOICES DIRECTLY (bypasses MCP for speed)
# =============================================================================

# Global voice cache - populated on app load for instant access
PREFETCHED_VOICES: List = []
VOICE_SUMMARY: str = ""
VOICES_READY = threading.Event()


def _prefetch_voices():
    """Pre-fetch voices directly from ElevenLabs API on app startup."""
    global PREFETCHED_VOICES, VOICE_SUMMARY
    
    from services.voice_service import get_voice_service
    
    perf.start("prefetch_voices", details="Direct API call")
    
    try:
        voice_service = get_voice_service()
        if voice_service.is_available:
            voices = voice_service.get_available_voices(force_refresh=True)
            if voices:
                # Update globals BEFORE signaling ready
                PREFETCHED_VOICES = voices
                VOICE_SUMMARY = voice_service.summarize_voices_for_llm(voices)
                VOICES_READY.set()  # Signal ready AFTER globals are set
                logger.info(f"✅ Pre-fetched {len(voices)} voices on app load")
                perf.end("prefetch_voices", details=f"{len(voices)} voices")
                return
            else:
                logger.warning("⚠️ No voices returned from ElevenLabs")
                perf.end("prefetch_voices", status="warning", details="No voices")
        else:
            logger.info("ℹ️ ElevenLabs not configured, skipping voice prefetch")
            perf.end("prefetch_voices", status="skipped", details="No API key")
    except Exception as e:
        logger.error(f"❌ Voice prefetch failed: {e}")
        perf.end("prefetch_voices", status="error", details=str(e))
    
    # If we get here, no voices were fetched
    VOICES_READY.set()


# Start voice prefetch in background thread (non-blocking)
logger.info("🎤 Pre-fetching voices in background...")
voice_thread = threading.Thread(target=_prefetch_voices, daemon=True)
voice_thread.start()

# Global state
game_states: Dict[str, object] = {}
# mystery_images is imported from game.state_manager to ensure all modules share the same dict

# Initialize services
perf.start("init_services")
init_tts_service(elevenlabs_client, openai_client, GAME_MASTER_VOICE_ID)
init_game_handlers(game_states, mystery_images, GAME_MASTER_VOICE_ID)
perf.end("init_services")


# ============================================================================
# GRADIO UI
# ============================================================================


def create_app():
    """Create the Gradio application."""

    with gr.Blocks(title="Murder Mystery") as app:
        # Create all UI components
        components = create_ui_components()

        # Extract components for easier access
        session_id = components["session_id"]
        speaker_html = components["speaker_html"]
        audio_output = components["audio_output"]
        portrait_image = components["portrait_image"]
        input_row = components["input_row"]
        start_btn = components["start_btn"]
        victim_scene_html = components["victim_scene_html"]
        suspects_list_html = components["suspects_list_html"]
        locations_html = components["locations_html"]
        clues_html = components["clues_html"]
        accusations_html = components["accusations_html"]
        dashboard_html_tab = components["dashboard_html_tab"]
        victim_scene_html_tab = components["victim_scene_html_tab"]
        suspects_list_html_tab = components["suspects_list_html_tab"]
        locations_html_tab = components["locations_html_tab"]
        clues_html_tab = components["clues_html_tab"]
        accusations_html_tab = components["accusations_html_tab"]
        timeline_html_tab = components["timeline_html_tab"]
        timeline_html_main = components["timeline_html_main"]  # Main tab version
        case_board_plot = components["case_board_plot"]  # Visual conspiracy board (info tabs/mobile)
        case_board_plot_main = components["case_board_plot_main"]  # Visual conspiracy board (main tab)
        reveal_status_textbox = components["reveal_status_textbox"]
        refresh_reveal_btn = components["refresh_reveal_btn"]
        debug_logs_textbox = components["debug_logs_textbox"]
        refresh_logs_btn = components["refresh_logs_btn"]
        perf_summary_textbox = components["perf_summary_textbox"]
        refresh_perf_btn = components["refresh_perf_btn"]
        mystery_check_timer = components["mystery_check_timer"]
        voice_input = components["voice_input"]
        # Setup wizard components
        game_started_marker = components["game_started_marker"]
        setup_wizard = components["setup_wizard"]
        wizard_era_dropdown = components["wizard_era_dropdown"]
        wizard_setting_dropdown = components["wizard_setting_dropdown"]
        wizard_difficulty_radio = components["wizard_difficulty_radio"]
        wizard_tone_radio = components["wizard_tone_radio"]
        # API Key inputs
        openai_key_input = components["openai_key_input"]
        openai_key_status = components["openai_key_status"]
        elevenlabs_key_input = components["elevenlabs_key_input"]
        elevenlabs_key_status = components["elevenlabs_key_status"]
        save_keys_btn = components["save_keys_btn"]
        keys_status_html = components["keys_status_html"]
        refresh_voices_btn = components["refresh_voices_btn"]
        # Tabs and buttons for lazy portrait loading
        info_tabs = components["info_tabs"]
        refresh_suspects_btn = components["refresh_suspects_btn"]

        # ====== WIRE UP EVENTS ======

        # Common outputs for game actions
        game_outputs = [
            speaker_html,
            audio_output,
            portrait_image,
            victim_scene_html,
            suspects_list_html,
            locations_html,
            clues_html,
            accusations_html,
            timeline_html_main,  # Main tab version
            # Tab components (replicated from accordions)
            dashboard_html_tab,
            victim_scene_html_tab,
            suspects_list_html_tab,
            locations_html_tab,
            clues_html_tab,
            accusations_html_tab,
            timeline_html_tab,
            case_board_plot,  # Visual conspiracy board (info tabs/mobile)
            case_board_plot_main,  # Visual conspiracy board (main tab)
        ]

        # ====== WIZARD EVENT HANDLERS ======
        
        # Wizard era dropdown - updates settings and syncs config
        getattr(wizard_era_dropdown, "change")(
            fn=on_wizard_config_change,
            inputs=[
                wizard_era_dropdown,
                wizard_setting_dropdown,
                wizard_difficulty_radio,
                wizard_tone_radio,
                session_id,
            ],
            outputs=[wizard_setting_dropdown],
        )
        
        # Wizard setting changes - sync config
        getattr(wizard_setting_dropdown, "change")(
            fn=on_config_generic_change,
            inputs=[
                wizard_setting_dropdown,
                wizard_era_dropdown,
                wizard_difficulty_radio,
                wizard_tone_radio,
                session_id,
            ],
            outputs=None,
        )
        
        # Wizard difficulty changes - sync config
        getattr(wizard_difficulty_radio, "change")(
            fn=on_config_generic_change,
            inputs=[
                wizard_setting_dropdown,
                wizard_era_dropdown,
                wizard_difficulty_radio,
                wizard_tone_radio,
                session_id,
            ],
            outputs=None,
        )
        
        # Wizard tone changes - sync config
        getattr(wizard_tone_radio, "change")(
            fn=on_config_generic_change,
            inputs=[
                wizard_setting_dropdown,
                wizard_era_dropdown,
                wizard_difficulty_radio,
                wizard_tone_radio,
                session_id,
            ],
            outputs=None,
        )
        
        # Save API keys button
        getattr(save_keys_btn, "click")(
            fn=on_save_api_keys,
            inputs=[openai_key_input, elevenlabs_key_input, session_id],
            outputs=[openai_key_status, elevenlabs_key_status, keys_status_html],
        )
        
        # Check API keys status on page load
        getattr(app, "load")(
            fn=check_api_keys_status,
            inputs=[session_id],
            outputs=[openai_key_status, elevenlabs_key_status, keys_status_html],
        )
        
        # Note: Voices are fetched on-demand when START is clicked.
        # The refresh button allows manual refresh before starting.
        getattr(refresh_voices_btn, "click")(
            fn=on_refresh_voices,
            inputs=[session_id],
            outputs=None,
        )

        # Start game - show game_started_marker (CSS sibling selector hides wizard)
        getattr(start_btn, "click")(
            fn=on_start_game,
            inputs=[session_id],
            outputs=[
                game_started_marker,  # Show marker → CSS hides wizard via sibling selector
                speaker_html,
                audio_output,
                portrait_image,
                input_row,
                victim_scene_html,
                suspects_list_html,
                locations_html,
                clues_html,
                accusations_html,
                dashboard_html_tab,
                victim_scene_html_tab,
                suspects_list_html_tab,
                locations_html_tab,
                clues_html_tab,
                accusations_html_tab,
                timeline_html_tab,
                case_board_plot,  # Visual conspiracy board (info tabs/mobile)
                case_board_plot_main,  # Visual conspiracy board (main tab)
                mystery_check_timer,  # Timer activation
            ],
        )

        # Timer to check for mystery completion and update UI
        # Also updates opening scene image when it becomes available
        getattr(mystery_check_timer, "tick")(
            fn=check_mystery_ready,
            inputs=[session_id],
            outputs=[
                portrait_image,  # Opening scene image (appears when ready)
                victim_scene_html,
                suspects_list_html,
                locations_html,
                dashboard_html_tab,
                victim_scene_html_tab,
                suspects_list_html_tab,
                locations_html_tab,
                case_board_plot,  # Update case board as mystery loads (info tabs/mobile)
                case_board_plot_main,  # Update case board (main tab)
                mystery_check_timer,
            ],
        )

        # Voice input - only input method
        getattr(voice_input, "stop_recording")(
            on_voice_input, inputs=[voice_input, session_id], outputs=game_outputs
        ).then(
            reset_voice_input,
            inputs=None,
            outputs=[voice_input],
        )

        # Debug tab - refresh reveal status
        getattr(refresh_reveal_btn, "click")(
            fn=get_reveal_status,
            inputs=[session_id],
            outputs=[reveal_status_textbox],
        )
        
        # Debug tab - refresh logs
        getattr(refresh_logs_btn, "click")(
            fn=get_ui_logs,
            inputs=None,
            outputs=[debug_logs_textbox],
        )
        
        # Debug tab - refresh performance summary
        getattr(refresh_perf_btn, "click")(
            fn=get_perf_summary,
            inputs=None,
            outputs=[perf_summary_textbox],
        )

        # Hide speaker name when audio finishes playing
        # Use getattr to access the stop event (works across Gradio versions)
        if hasattr(audio_output, "stop"):
            getattr(audio_output, "stop")(
                fn=on_audio_stop,
                inputs=[session_id],
                outputs=[speaker_html],
            )
        elif hasattr(audio_output, "pause"):
            getattr(audio_output, "pause")(
                fn=on_audio_stop,
                inputs=[session_id],
                outputs=[speaker_html],
            )

        # Info tabs select - refresh suspects portraits on tab click (lazy loading)
        getattr(info_tabs, "select")(
            fn=on_suspects_tab_select,
            inputs=[session_id],
            outputs=[suspects_list_html_tab],
        )
        
        # Manual refresh button for suspects portraits
        getattr(refresh_suspects_btn, "click")(
            fn=on_refresh_suspects_click,
            inputs=[session_id],
            outputs=[suspects_list_html_tab],
        )

    return app


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    app = create_app()
    # Use Gradio's queue so the global progress/status tracker is visible
    app.queue().launch(server_name="0.0.0.0", server_port=7860, share=False)
