"""UI component creation for the murder mystery game."""

import uuid
import base64
import gradio as gr
from mystery_config import (
    ERA_OPTIONS,
    DIFFICULTY_LEVELS,
    TONE_OPTIONS,
    get_settings_for_era,
)
from ui.styles import RETRO_CSS
from app.utils import create_favicon


def create_ui_components() -> dict:
    """Create all Gradio UI components and return them as a dictionary.

    Returns:
        Dictionary containing all UI components with descriptive keys.
    """
    # Create and inject favicon
    favicon_path = create_favicon()
    # Convert favicon to base64 data URI for embedding
    with open(favicon_path, "rb") as f:
        favicon_data = base64.b64encode(f.read()).decode("utf-8")
    favicon_html = f"""
    <link rel="icon" type="image/png" href="data:image/png;base64,{favicon_data}">
    <link rel="shortcut icon" type="image/png" href="data:image/png;base64,{favicon_data}">
    """

    # Inject CSS and favicon
    gr.HTML(f"<style>{RETRO_CSS}</style>{favicon_html}")

    # Session state
    session_id = gr.State(lambda: str(uuid.uuid4()))

    # ====== TITLE BAR ======
    with gr.Row(elem_classes="title-bar"):
        gr.HTML(
            '<div class="game-title"><span class="detective-avatar">🕵️‍♀️</span> MURDER MYSTERY</div>'
        )

    # ====== MAIN LAYOUT, SETTINGS, AND DEBUG ======
    with gr.Tabs(elem_classes="main-tabs"):
        # ----- GAME TAB (DEFAULT) -----
        with gr.Tab("Game"):
            # ====== MAIN LAYOUT ======
            with gr.Row(elem_classes="main-layout-row"):

                # === LEFT: SIDE PANEL ===
                with gr.Column(
                    scale=1,
                    min_width=200,
                    elem_classes="side-column side-column-left",
                ):
                    # Case Details
                    with gr.Accordion(
                        "🧳 CASE DETAILS",
                        open=False,
                        elem_classes="side-panel",
                    ):
                        victim_scene_html = gr.HTML(
                            "<em>Start a game to see case details...</em>",
                            elem_classes="transcript-panel",
                        )

                    # Suspects list
                    with gr.Accordion(
                        "🎭 SUSPECTS",
                        open=False,
                        elem_classes="side-panel suspects-panel",
                    ):
                        suspects_list_html = gr.HTML(
                            "<em>Start a game to see suspects...</em>",
                            elem_classes="transcript-panel suspects-list",
                        )

                    # Accusations card
                    with gr.Accordion(
                        "⚖️ ACCUSATIONS",
                        open=False,
                        elem_classes="side-panel",
                    ):
                        accusations_html = gr.HTML(
                            '<div class="accusations-display">Accusations: '
                            "<span>"
                            '<span class="accusations-pip"></span>'
                            '<span class="accusations-pip"></span>'
                            '<span class="accusations-pip"></span>'
                            "</span></div>"
                        )

                # === CENTER: MAIN STAGE ===
                with gr.Column(scale=3, elem_classes="center-column"):

                    # Stage container (styled via .center-column > .gr-group in CSS)
                    with gr.Group():

                        # Speaker name - hidden until the mystery starts
                        # (placeholder text is only shown after the first turn)
                        speaker_html = gr.HTML(
                            '<div class="speaker-name" style="display: none;"></div>'
                        )

                        # Portrait display - larger size for better visibility
                        # Start visible but empty; CSS will handle hiding when no image
                        portrait_image = gr.Image(
                            value=None,
                            type="filepath",  # We pass file paths from the backend
                            show_label=False,
                            elem_classes="portrait-image",
                            visible=True,  # Always visible; CSS hides when empty
                        )

                        # Audio player with built-in subtitles support (Gradio handles word highlighting)
                        audio_output = gr.Audio(
                            label=None,
                            show_label=False,
                            autoplay=False,  # Don't autoplay initially - no audio to play yet
                            elem_id="mm-audio-player",
                            elem_classes="audio-player",
                        )

                    # ====== SETUP WIZARD ======
                    # Step 1: Configure + Voice Loading
                    with gr.Column(elem_classes="setup-wizard", visible=True) as setup_wizard:
                        
                        # Settings (inline in wizard for Step 1)
                        with gr.Group(elem_classes="wizard-settings"):
                            gr.HTML('<div class="wizard-section-title">Configure Your Mystery</div>')
                            with gr.Row():
                                wizard_era_dropdown = gr.Dropdown(
                                    label="Era",
                                    choices=ERA_OPTIONS,
                                    value="Any",
                                    interactive=True,
                                    scale=1,
                                )
                                wizard_setting_dropdown = gr.Dropdown(
                                    label="Setting",
                                    choices=["Random"] + get_settings_for_era("Any"),
                                    value="Random",
                                    interactive=True,
                                    scale=1,
                                )
                            with gr.Row():
                                wizard_difficulty_radio = gr.Radio(
                                    label="Difficulty",
                                    choices=DIFFICULTY_LEVELS,
                                    value="Normal",
                                    interactive=True,
                                )
                            with gr.Row():
                                wizard_tone_radio = gr.Radio(
                                    label="Tone",
                                    choices=TONE_OPTIONS,
                                    value="Random",
                                    interactive=True,
                                )
                        
                        # Buttons row
                        with gr.Row(elem_classes="wizard-buttons"):
                            refresh_voices_btn = gr.Button(
                                "↻ Refresh Voices",
                                elem_classes="wizard-secondary-btn",
                                size="sm",
                            )
                            start_btn = gr.Button(
                                "🚀 START MYSTERY",
                                elem_classes="start-button wizard-primary-btn",
                                size="lg",
                            )

                    # Input bar - voice only
                    with gr.Column(
                        elem_classes="input-bar", visible=False
                    ) as input_row:
                        # Voice input - only input method
                        voice_input = gr.Audio(
                            sources=["microphone"],
                            type="filepath",
                            label=None,
                            show_label=False,
                        )
                    
                    # Tab group with accordion content (always visible)
                    with gr.Tabs(elem_classes="info-tabs"):
                        # Dashboard tab - first for quick overview
                        with gr.Tab("📊 DASHBOARD"):
                            dashboard_html_tab = gr.HTML(
                                '''<div class="dashboard-empty">
                                    <div class="dashboard-icon">📊</div>
                                    <div>Start a mystery to track your investigation.</div>
                                </div>'''
                            )
                        
                        # Case Details tab
                        with gr.Tab("🧳 CASE DETAILS"):
                            victim_scene_html_tab = gr.HTML(
                                "<em>Start a game to see case details...</em>",
                                elem_classes="transcript-panel",
                            )
                        
                        # Suspects tab
                        with gr.Tab("🎭 SUSPECTS"):
                            suspects_list_html_tab = gr.HTML(
                                "<em>Start a game to see suspects...</em>",
                                elem_classes="transcript-panel suspects-list",
                            )
                        
                        # Locations tab
                        with gr.Tab("📍 LOCATIONS"):
                            locations_html_tab = gr.HTML("<em>Start a game...</em>")
                        
                        # Clues Found tab
                        with gr.Tab("🔎 CLUES FOUND"):
                            clues_html_tab = gr.HTML("<em>No clues yet...</em>")
                        
                        # Accusations tab
                        with gr.Tab("⚖️ ACCUSATIONS"):
                            accusations_html_tab = gr.HTML(
                                '<div class="accusations-display">Accusations: '
                                "<span>"
                                '<span class="accusations-pip"></span>'
                                '<span class="accusations-pip"></span>'
                                '<span class="accusations-pip"></span>'
                                "</span></div>"
                            )
                        
                        # Detective Notebook tab
                        with gr.Tab("📓 DETECTIVE NOTEBOOK"):
                            notebook_html_tab = gr.HTML(
                                '''<div class="notebook-empty">
                                    <div class="notebook-icon">📓</div>
                                    <div>No interrogations recorded yet.</div>
                                    <div class="notebook-hint">Talk to suspects to fill your notebook.</div>
                                </div>'''
                            )

                # === RIGHT: SIDE PANEL ===
                with gr.Column(
                    scale=1,
                    min_width=200,
                    elem_classes="side-column side-column-right",
                ):
                    # Locations card
                    with gr.Accordion(
                        "📍 LOCATIONS",
                        open=False,
                        elem_classes="side-panel",
                    ):
                        locations_html = gr.HTML("<em>Start a game...</em>")

                    # Clues card
                    with gr.Accordion(
                        "🔎 CLUES FOUND",
                        open=False,
                        elem_classes="side-panel",
                    ):
                        clues_html = gr.HTML("<em>No clues yet...</em>")

                    # Detective Notebook - conversation timeline & contradictions
                    with gr.Accordion(
                        "📓 DETECTIVE NOTEBOOK",
                        open=False,
                        elem_classes="side-panel",
                    ):
                        notebook_html = gr.HTML(
                            '''<div class="notebook-empty">
                                <div class="notebook-icon">📓</div>
                                <div>No interrogations recorded yet.</div>
                                <div class="notebook-hint">Talk to suspects to fill your notebook.</div>
                            </div>'''
                        )

        # ----- SETTINGS TAB -----
        with gr.Tab("Settings"):
            with gr.Column(elem_classes="settings-column"):
                gr.Markdown(
                    "### Mystery settings\n\n"
                    "Adjust these before starting a new game. "
                    "Changes apply to the **next** mystery you start in this browser session."
                )
                era_dropdown = gr.Dropdown(
                    label="Era / category",
                    choices=ERA_OPTIONS,
                    value="Any",
                    interactive=True,
                )
                setting_dropdown = gr.Dropdown(
                    label="Setting",
                    choices=["Random"] + get_settings_for_era("Any"),
                    value="Random",
                    interactive=True,
                )
                difficulty_radio = gr.Radio(
                    label="Difficulty",
                    choices=DIFFICULTY_LEVELS,
                    value="Normal",
                    interactive=True,
                )
                tone_radio = gr.Radio(
                    label="Tone",
                    choices=TONE_OPTIONS,
                    value="Random",
                    interactive=True,
                )

        # ----- DEBUG TAB -----
        with gr.Tab("Debug"):
            with gr.Column(elem_classes="settings-column"):
                gr.Markdown(
                    "### Debug logs\n\n"
                    "These are the most recent server logs captured during gameplay.\n\n"
                    "- Use the **Refresh logs** button to update.\n"
                    "- Then copy/paste any relevant lines when sharing details with the AI assistant."
                )
                debug_logs_textbox = gr.Textbox(
                    label="Recent logs",
                    lines=20,
                    value="No logs captured yet. Interact with the game to generate logs.",
                    interactive=False,
                )
                refresh_logs_btn = gr.Button("🔄 Refresh logs")

    # Hidden timer for checking mystery completion (inactive by default)
    mystery_check_timer = gr.Timer(value=1.0, active=False)

    # Return all components as a dictionary
    return {
        "session_id": session_id,
        "speaker_html": speaker_html,
        "audio_output": audio_output,
        "portrait_image": portrait_image,
        "input_row": input_row,
        "start_btn": start_btn,
        "victim_scene_html": victim_scene_html,
        "suspects_list_html": suspects_list_html,
        "locations_html": locations_html,
        "clues_html": clues_html,
        "accusations_html": accusations_html,
        "notebook_html": notebook_html,
        "dashboard_html_tab": dashboard_html_tab,
        "victim_scene_html_tab": victim_scene_html_tab,
        "suspects_list_html_tab": suspects_list_html_tab,
        "locations_html_tab": locations_html_tab,
        "clues_html_tab": clues_html_tab,
        "accusations_html_tab": accusations_html_tab,
        "notebook_html_tab": notebook_html_tab,
        "era_dropdown": era_dropdown,
        "setting_dropdown": setting_dropdown,
        "difficulty_radio": difficulty_radio,
        "tone_radio": tone_radio,
        "debug_logs_textbox": debug_logs_textbox,
        "refresh_logs_btn": refresh_logs_btn,
        "mystery_check_timer": mystery_check_timer,
        "voice_input": voice_input,
        # Setup wizard components
        "setup_wizard": setup_wizard,
        "wizard_era_dropdown": wizard_era_dropdown,
        "wizard_setting_dropdown": wizard_setting_dropdown,
        "wizard_difficulty_radio": wizard_difficulty_radio,
        "wizard_tone_radio": wizard_tone_radio,
        "refresh_voices_btn": refresh_voices_btn
    }

