"""Voice-First Murder Mystery Game - 90s Point-and-Click Adventure Style.

A reimagined interface that prioritizes voice output with streaming captions,
styled like classic adventure games (Monkey Island, Gabriel Knight, etc.)
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
    on_config_era_change,
    on_config_generic_change,
    on_wizard_config_change,
    on_start_game,
    check_mystery_ready,
    on_voice_input,
    reset_voice_input,
    on_audio_stop,
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
        era_dropdown = components["era_dropdown"]
        setting_dropdown = components["setting_dropdown"]
        difficulty_radio = components["difficulty_radio"]
        tone_radio = components["tone_radio"]
        debug_logs_textbox = components["debug_logs_textbox"]
        refresh_logs_btn = components["refresh_logs_btn"]
        mystery_check_timer = components["mystery_check_timer"]
        voice_input = components["voice_input"]
        # Setup wizard components
        setup_wizard = components["setup_wizard"]
        wizard_era_dropdown = components["wizard_era_dropdown"]
        wizard_setting_dropdown = components["wizard_setting_dropdown"]
        wizard_difficulty_radio = components["wizard_difficulty_radio"]
        wizard_tone_radio = components["wizard_tone_radio"]
        refresh_voices_btn = components["refresh_voices_btn"]

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

        # Settings tab - keep per-session config in GameState
        getattr(era_dropdown, "change")(
            fn=on_config_era_change,
            inputs=[
                era_dropdown,
                setting_dropdown,
                difficulty_radio,
                tone_radio,
                session_id,
            ],
            outputs=[setting_dropdown],
        )

        getattr(setting_dropdown, "change")(
            fn=on_config_generic_change,
            inputs=[
                setting_dropdown,
                era_dropdown,
                difficulty_radio,
                tone_radio,
                session_id,
            ],
            outputs=None,
        )
        getattr(difficulty_radio, "change")(
            fn=on_config_generic_change,
            inputs=[
                setting_dropdown,
                era_dropdown,
                difficulty_radio,
                tone_radio,
                session_id,
            ],
            outputs=None,
        )
        getattr(tone_radio, "change")(
            fn=on_config_generic_change,
            inputs=[
                setting_dropdown,
                era_dropdown,
                difficulty_radio,
                tone_radio,
                session_id,
            ],
            outputs=None,
        )

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
        
        # Note: Voices are fetched on-demand when START is clicked
        # The refresh button allows manual refresh before starting

        # Start game - now with wizard outputs
        getattr(start_btn, "click")(
            on_start_game,
            inputs=[session_id],
            outputs=[
                speaker_html,
                audio_output,
                portrait_image,
                input_row,
                setup_wizard,  # Hide wizard
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
                inputs=None,
                outputs=[speaker_html],
            )
        elif hasattr(audio_output, "pause"):
            getattr(audio_output, "pause")(
                fn=on_audio_stop,
                inputs=None,
                outputs=[speaker_html],
            )

    return app


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    app = create_app()
    # Use Gradio's queue so the global progress/status tracker is visible
    app.queue().launch(server_name="0.0.0.0", server_port=7860, share=False)
