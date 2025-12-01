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
    # Also include a script to ensure sticky bar works in Hugging Face Spaces
    sticky_bar_script = """
    <script>
    (function() {
        let stickyBarMoved = false;
        
        // Check if a parent element has transform/perspective/filter that breaks fixed positioning
        function hasTransformParent(element) {
            let parent = element.parentElement;
            while (parent && parent !== document.body) {
                const style = window.getComputedStyle(parent);
                const transform = style.transform;
                const perspective = style.perspective;
                const filter = style.filter;
                const willChange = style.willChange;
                
                if (transform && transform !== 'none') return true;
                if (perspective && perspective !== 'none') return true;
                if (filter && filter !== 'none') return true;
                if (willChange && willChange !== 'auto') return true;
                
                parent = parent.parentElement;
            }
            return false;
        }
        
        // Ensure sticky bar is always fixed to viewport
        function enforceStickyBar() {
            const stickyBar = document.getElementById('sticky-record-bar');
            if (!stickyBar) return;
            
            // Always move to body if not already there (simplified - just always move it)
            if (stickyBar.parentElement !== document.body) {
                // Move directly to body (preserves event listeners)
                document.body.appendChild(stickyBar);
                stickyBarMoved = true;
                console.log('[Sticky Bar] Moved to body. Was in:', stickyBar.parentElement?.tagName, stickyBar.parentElement?.className);
            }
            
            // Apply all styles with !important via setProperty
            stickyBar.style.setProperty('position', 'fixed', 'important');
            stickyBar.style.setProperty('bottom', '0', 'important');
            stickyBar.style.setProperty('left', '0', 'important');
            stickyBar.style.setProperty('right', '0', 'important');
            stickyBar.style.setProperty('width', '100%', 'important');
            stickyBar.style.setProperty('z-index', '99999', 'important');
            stickyBar.style.setProperty('margin', '0', 'important');
            stickyBar.style.setProperty('flex-grow', '0', 'important');
            stickyBar.style.setProperty('min-width', 'auto', 'important');
            stickyBar.style.setProperty('max-width', 'none', 'important');
            stickyBar.style.setProperty('display', 'block', 'important');
            stickyBar.style.setProperty('flex-direction', 'unset', 'important');
            
            // Verify it's actually fixed and positioned correctly
            const computed = window.getComputedStyle(stickyBar);
            const rect = stickyBar.getBoundingClientRect();
            const viewportHeight = window.innerHeight;
            const distanceFromBottom = viewportHeight - rect.bottom;
            const isInBody = stickyBar.parentElement === document.body;
            
            // Log detailed info for debugging
            if (!isInBody || computed.position !== 'fixed' || Math.abs(distanceFromBottom) > 5) {
                console.warn('[Sticky Bar] Issue detected!', {
                    inBody: isInBody,
                    position: computed.position,
                    parent: stickyBar.parentElement?.tagName + '.' + stickyBar.parentElement?.className,
                    distanceFromBottom: distanceFromBottom + 'px',
                    rect: { top: rect.top, bottom: rect.bottom, left: rect.left, right: rect.right },
                    viewportHeight: viewportHeight
                });
            }
        }
        
        // Run on load and after delays to catch late-rendered elements
        function initStickyBar() {
            console.log('[Sticky Bar] Initializing...');
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', enforceStickyBar);
            } else {
                enforceStickyBar();
            }
            setTimeout(enforceStickyBar, 100);
            setTimeout(enforceStickyBar, 500);
            setTimeout(enforceStickyBar, 1000);
            setTimeout(enforceStickyBar, 2000);
            setTimeout(enforceStickyBar, 3000);
        }
        
        initStickyBar();
        
        // Watch for DOM changes (Gradio may re-render or move the element back)
        const observer = new MutationObserver(function(mutations) {
            const stickyBar = document.getElementById('sticky-record-bar');
            if (stickyBar) {
                const parent = stickyBar.parentElement;
                if (parent !== document.body) {
                    console.log('[Sticky Bar] Detected in container, moving to body. Parent:', parent.tagName, parent.className);
                    // Immediately move it back to body
                    document.body.appendChild(stickyBar);
                    stickyBarMoved = true;
                    // Re-apply all styles
                    enforceStickyBar();
                } else {
                    // Still enforce styles even if already moved (in case styles get overridden)
                    enforceStickyBar();
                }
            }
        });
        
        // Watch the entire document for when the element gets moved
        observer.observe(document.documentElement, { 
            childList: true, 
            subtree: true,
            attributes: false  // Don't watch attributes to reduce noise
        });
        
        // Also watch body specifically for when element is added/removed
        observer.observe(document.body, { 
            childList: true,
            subtree: false  // Only direct children of body
        });
        
        // Also run on window load to ensure it stays fixed
        window.addEventListener('load', enforceStickyBar);
        // Removed scroll listener to reduce console spam - fixed positioning should handle scrolling automatically
    })();
    </script>
    """
    gr.HTML(f"<style>{RETRO_CSS}</style>{favicon_html}{sticky_bar_script}")

    # Session state - stable UUID string per browser session
    session_id = gr.State(str(uuid.uuid4()))

    # ====== TITLE BAR ======
    with gr.Row(elem_classes="title-bar"):
        gr.HTML(
            '<div class="game-title"><span class="detective-avatar">🕵️‍♀️</span> MURDER MYSTERY</div>'
        )

    # ====== MAIN LAYOUT AND DEBUG ======
    with gr.Tabs(elem_classes="main-tabs") as main_tabs:
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

                    # Suspects list - expanded by default
                    with gr.Accordion(
                        "🎭 SUSPECTS",
                        open=True,
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

                    # ====== GAME STARTED MARKER (must be first for CSS sibling selectors) ======
                    # Empty initially - when game starts, content is added that CSS detects via :has()
                    game_started_marker = gr.HTML(
                        '',  # Empty initially - will be populated when game starts
                        elem_classes="game-started-container",
                    )

                    # Stage container (styled via .center-column > .gr-group in CSS)
                    with gr.Group(elem_classes="crt-stage"):

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
                        
                    # Input bar - sticky bottom record button (always visible)
                    with gr.Column(
                        elem_classes="input-bar",
                        elem_id="sticky-record-bar",
                        visible=True,
                    ) as input_row:
                        # Voice input - minimal, just the mic button
                        voice_input = gr.Audio(
                            sources=["microphone"],
                            type="filepath",
                            label=None,
                            show_label=False,
                            elem_classes="record-audio-minimal",
                        )

                    # ====== SETUP WIZARD ======
                    # Step 1: Configure + Voice Loading
                    with gr.Column(elem_classes="setup-wizard") as setup_wizard:
                        
                        # Settings (inline in wizard for Step 1)
                        with gr.Group(elem_classes="wizard-settings"):
                            gr.HTML('<div class="wizard-section-title">🔍 Murder Mystery Detective</div>')
                            gr.HTML('''
                                <div class="wizard-instructions">
                                    <p><strong>How to Play:</strong></p>
                                    <ul>
                                        <li>🎤 <strong>Speak</strong> to investigate — use the microphone to ask questions</li>
                                        <li>🗣️ <strong>Interrogate</strong> suspects — ask about their alibis and secrets</li>
                                        <li>🔎 <strong>Search</strong> locations — look for clues at the crime scene</li>
                                        <li>⚖️ <strong>Accuse</strong> the murderer — but be careful, 3 wrong guesses and you lose!</li>
                                    </ul>
                                </div>
                            ''')
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
                            
                            # Start button inside the config panel
                            with gr.Row(elem_classes="wizard-buttons"):
                                start_btn = gr.Button(
                                    "🚀 START MYSTERY",
                                    elem_classes="start-button wizard-primary-btn",
                                    size="lg",
                                )
                    
                    # Tab group with accordion content (always visible)
                    with gr.Tabs(elem_classes="info-tabs") as info_tabs:
                        # Dashboard tab - first for quick overview
                        with gr.Tab("📊 DASHBOARD", id="dashboard"):
                            dashboard_html_tab = gr.HTML(
                                '''<div class="dashboard-empty">
                                    <div class="dashboard-icon">📊</div>
                                    <div>Start a mystery to track your investigation.</div>
                                </div>'''
                            )
                        
                        # Case Details tab
                        with gr.Tab("🧳 CASE DETAILS", id="case_details"):
                            victim_scene_html_tab = gr.HTML(
                                "<em>Start a game to see case details...</em>",
                                elem_classes="transcript-panel",
                            )
                        
                        # Suspects tab
                        with gr.Tab("🎭 SUSPECTS", id="suspects") as suspects_tab:
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
                        
                        # Investigation Timeline tab
                        with gr.Tab("🕐 TIMELINE"):
                            timeline_html_tab = gr.HTML(
                                '''<div class="timeline-empty">
                                    <div class="timeline-empty-icon">🕐</div>
                                    <div class="timeline-empty-text">Timeline Empty</div>
                                    <div class="timeline-empty-hint">
                                        Interrogate suspects and search for clues to piece together what happened.
                                    </div>
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


        # ----- DASHBOARD TAB -----
        with gr.Tab("📊 Dashboard", elem_classes="dashboard-tab"):
            with gr.Column(elem_classes="dashboard-column"):
                dashboard_html_main = gr.HTML(
                    '''<div class="dashboard-empty">
                        <div class="dashboard-icon">📊</div>
                        <div>Start a mystery to track your investigation.</div>
                    </div>''',
                    elem_classes="dashboard-main",
                )

        # ----- CASE FILE TAB -----
        with gr.Tab("📋 Case File", elem_classes="case-file-tab"):
            with gr.Column(elem_classes="case-file-column"):
                gr.Markdown("### 📋 Official Case File")
                gr.Markdown(
                    "Police-style case summary showing victim information and current persons of interest.\n"
                    "**Updates automatically as you discover clues and interrogate suspects.**"
                )
                case_file_html_main = gr.HTML(
                    '<div class="case-file-empty">'
                    '<div class="case-file-empty-icon">📁</div>'
                    '<div class="case-file-empty-text">Start a mystery to generate the official case file.</div>'
                    "</div>",
                    elem_classes="case-file-main",
                )

        # ----- TIMELINE TAB -----
        with gr.Tab("🕐 Timeline", elem_classes="timeline-tab"):
            with gr.Column(elem_classes="timeline-column"):
                gr.Markdown("### 🕐 Investigation Timeline")
                gr.Markdown(
                    "Track alibis, witness sightings, and contradictions as you uncover them.\n"
                    "**Events are logged chronologically as you interrogate suspects and find clues.**"
                )
                timeline_html_main = gr.HTML(
                    '''<div class="timeline-empty">
                        <div class="timeline-empty-icon">🕐</div>
                        <div class="timeline-empty-text">Timeline Empty</div>
                        <div class="timeline-empty-hint">
                            Interrogate suspects and search for clues to piece together what happened.
                        </div>
                    </div>''',
                    elem_classes="timeline-main",
                )

        # ----- API KEYS TAB -----
        with gr.Tab("🔑 Settings", elem_classes="settings-tab"):
            with gr.Column(elem_classes="settings-column"):
                gr.Markdown("### 🔑 API Keys")
                gr.Markdown(
                    "Enter your own API keys to play. Keys are stored in memory only (session) and **never saved to disk**.\n"
                    "For local development, you can also set keys in your `.env` file."
                )
                
                with gr.Group(elem_classes="api-keys-group"):
                    with gr.Row():
                        openai_key_input = gr.Textbox(
                            label="OpenAI API Key (required)",
                            placeholder="sk-...",
                            type="password",
                            scale=3,
                        )
                        openai_key_status = gr.HTML(
                            '<span class="key-status">❓ Not set</span>',
                            elem_classes="key-status-container",
                        )
                    
                    with gr.Row():
                        elevenlabs_key_input = gr.Textbox(
                            label="ElevenLabs API Key (required)",
                            placeholder="Your ElevenLabs key...",
                            type="password",
                            scale=3,
                        )
                        elevenlabs_key_status = gr.HTML(
                            '<span class="key-status">❓ Not set</span>',
                            elem_classes="key-status-container",
                        )
                    
                    with gr.Row():
                        huggingface_key_input = gr.Textbox(
                            label="HuggingFace Token (required)",
                            placeholder="hf_...",
                            type="password",
                            scale=3,
                        )
                        huggingface_key_status = gr.HTML(
                            '<span class="key-status">❓ Not set</span>',
                            elem_classes="key-status-container",
                        )
                    
                    with gr.Row():
                        save_keys_btn = gr.Button(
                            "💾 Save Keys to Session",
                            elem_classes="save-keys-btn",
                            variant="primary",
                        )
                        keys_status_html = gr.HTML(
                            '<span class="keys-overall-status"></span>'
                        )
                
                gr.Markdown("---")
                gr.Markdown(
                    "### ℹ️ About API Keys\n\n"
                    "- **OpenAI** (required): Powers the game master AI and mystery generation\n"
                    "- **ElevenLabs** (required): Voice acting for characters\n"
                    "- **HuggingFace** (required): Portrait and scene art generation\n\n"
                    "All three keys are required to play the game."
                )

    # Hidden timer for checking mystery completion (inactive by default)
    mystery_check_timer = gr.Timer(value=1.0, active=False)

    # Return all components as a dictionary
    return {
        "session_id": session_id,
        "main_tabs": main_tabs,
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
        "dashboard_html_tab": dashboard_html_tab,
        "victim_scene_html_tab": victim_scene_html_tab,
        "suspects_list_html_tab": suspects_list_html_tab,
        "locations_html_tab": locations_html_tab,
        "clues_html_tab": clues_html_tab,
        "accusations_html_tab": accusations_html_tab,
        "timeline_html_tab": timeline_html_tab,
        "timeline_html_main": timeline_html_main,  # Main tab version
        "case_file_html_main": case_file_html_main,  # Case File (main tab)
        "dashboard_html_main": dashboard_html_main,  # Dashboard (main tab)
        "mystery_check_timer": mystery_check_timer,
        "voice_input": voice_input,
        # Setup wizard components
        "game_started_marker": game_started_marker,
        "setup_wizard": setup_wizard,
        "wizard_era_dropdown": wizard_era_dropdown,
        "wizard_setting_dropdown": wizard_setting_dropdown,
        "wizard_difficulty_radio": wizard_difficulty_radio,
        "wizard_tone_radio": wizard_tone_radio,
        # API Key inputs
        "openai_key_input": openai_key_input,
        "openai_key_status": openai_key_status,
        "elevenlabs_key_input": elevenlabs_key_input,
        "elevenlabs_key_status": elevenlabs_key_status,
        "huggingface_key_input": huggingface_key_input,
        "huggingface_key_status": huggingface_key_status,
        "save_keys_btn": save_keys_btn,
        "keys_status_html": keys_status_html,
        # Tabs for select events (lazy portrait loading)
        "info_tabs": info_tabs,
        "suspects_tab": suspects_tab,
    }

