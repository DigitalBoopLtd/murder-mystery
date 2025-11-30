"""Voice-First Murder Mystery Game - 90s Point-and-Click Adventure Style.

A reimagined interface that prioritizes voice output with streaming captions,
styled like classic adventure games (Monkey Island, Day of the Tentacles, Gabriel Knight, etc.)
"""

import os
from typing import Dict
import gradio as gr
from dotenv import load_dotenv
from openai import OpenAI

try:
    from elevenlabs import ElevenLabs

    ELEVENLABS_AVAILABLE = True
except ImportError:
    ELEVENLABS_AVAILABLE = False
    ElevenLabs = None

# Import modular components
from services.tts_service import init_tts_service
from game.state_manager import init_game_handlers, mystery_images
from app.utils import setup_ui_logging, get_ui_logs
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
)

# Load environment variables
load_dotenv()

# Initialize clients
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

elevenlabs_client = None
if os.getenv("ELEVENLABS_API_KEY") and ELEVENLABS_AVAILABLE:
    try:
        elevenlabs_client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
    except Exception as e:  # noqa: BLE001
        print(f"Warning: Failed to initialize ElevenLabs: {e}")

# Game Master voice
GAME_MASTER_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"

# Logging
import logging

logging.basicConfig(level=logging.INFO)
setup_ui_logging()

# Global state
game_states: Dict[str, object] = {}
# mystery_images is imported from game.state_manager to ensure all modules share the same dict

# Initialize services
init_tts_service(elevenlabs_client, openai_client, GAME_MASTER_VOICE_ID)
init_game_handlers(game_states, mystery_images, GAME_MASTER_VOICE_ID)


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
        notebook_html = components["notebook_html"]
        dashboard_html_tab = components["dashboard_html_tab"]
        victim_scene_html_tab = components["victim_scene_html_tab"]
        suspects_list_html_tab = components["suspects_list_html_tab"]
        locations_html_tab = components["locations_html_tab"]
        clues_html_tab = components["clues_html_tab"]
        accusations_html_tab = components["accusations_html_tab"]
        notebook_html_tab = components["notebook_html_tab"]
        debug_logs_textbox = components["debug_logs_textbox"]
        refresh_logs_btn = components["refresh_logs_btn"]
        mystery_check_timer = components["mystery_check_timer"]
        voice_input = components["voice_input"]
        # Setup wizard components
        game_started_marker = components["game_started_marker"]
        setup_wizard = components["setup_wizard"]
        wizard_era_dropdown = components["wizard_era_dropdown"]
        wizard_setting_dropdown = components["wizard_setting_dropdown"]
        wizard_difficulty_radio = components["wizard_difficulty_radio"]
        wizard_tone_radio = components["wizard_tone_radio"]
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
            notebook_html,
            # Tab components (replicated from accordions)
            dashboard_html_tab,
            victim_scene_html_tab,
            suspects_list_html_tab,
            locations_html_tab,
            clues_html_tab,
            accusations_html_tab,
            notebook_html_tab,
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
                notebook_html_tab,
                mystery_check_timer,  # Timer activation
            ],
        )

        # Timer to check for mystery completion and update UI
        getattr(mystery_check_timer, "tick")(
            fn=check_mystery_ready,
            inputs=[session_id],
            outputs=[
                victim_scene_html,
                suspects_list_html,
                locations_html,
                dashboard_html_tab,
                victim_scene_html_tab,
                suspects_list_html_tab,
                locations_html_tab,
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

        # Debug tab - refresh logs
        getattr(refresh_logs_btn, "click")(
            fn=get_ui_logs,
            inputs=None,
            outputs=[debug_logs_textbox],
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
