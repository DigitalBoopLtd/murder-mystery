"""Voice-First Murder Mystery Game - 90s Point-and-Click Adventure Style.

A reimagined interface that prioritizes voice output with streaming captions,
styled like classic adventure games (Monkey Island, Gabriel Knight, etc.)
"""

import os
import uuid
import base64
import logging
import tempfile
import time
from typing import Dict, Optional, List
from PIL import Image, ImageDraw, ImageFont
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
from ui_styles import RETRO_CSS
from tts_service import (
    init_tts_service,
    transcribe_audio,
)
from ui_formatters import (
    format_victim_scene_html,
    format_suspects_list_html,
    format_locations_html,
    format_clues_html,
)
from game_handlers import (
    init_game_handlers,
    start_new_game_staged,
    process_player_action,
    run_action_logic,
    generate_turn_media,
    get_or_create_state,
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
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global state
game_states: Dict[str, object] = {}
mystery_images: Dict[str, Dict[str, str]] = {}  # session_id -> {name: path}

# Initialize services
init_tts_service(elevenlabs_client, openai_client, GAME_MASTER_VOICE_ID)
init_game_handlers(game_states, mystery_images, GAME_MASTER_VOICE_ID)


def create_favicon() -> str:
    """Create a female detective favicon for the browser tab.

    Returns:
        Path to the favicon file
    """
    # Create a 32x32 favicon (standard size)
    size = 32
    img = Image.new("RGB", (size, size), color="#2C3E50")
    draw = ImageDraw.Draw(img)

    # Draw a simple female detective icon
    # Background circle
    draw.ellipse([2, 2, size - 2, size - 2], fill="#34495E", outline="#1A252F", width=1)

    # Head (circle)
    head_size = 14
    head_x = (size - head_size) // 2
    head_y = 6
    draw.ellipse(
        [head_x, head_y, head_x + head_size, head_y + head_size],
        fill="#FDB9B9",
        outline="#E8A5A5",
        width=1,
    )

    # Detective hat (fedora)
    hat_width = 18
    hat_x = (size - hat_width) // 2
    hat_y = 4
    # Hat brim
    draw.ellipse(
        [hat_x - 2, hat_y + 2, hat_x + hat_width + 2, hat_y + 6],
        fill="#1A1A1A",
        outline="#000000",
        width=1,
    )
    # Hat crown
    draw.ellipse(
        [hat_x + 2, hat_y, hat_x + hat_width - 2, hat_y + 8],
        fill="#2C2C2C",
        outline="#1A1A1A",
        width=1,
    )

    # Eyes (two small dots)
    eye_size = 2
    left_eye_x = head_x + 3
    right_eye_x = head_x + head_size - 5
    eye_y = head_y + 5
    draw.ellipse(
        [left_eye_x, eye_y, left_eye_x + eye_size, eye_y + eye_size], fill="#000000"
    )
    draw.ellipse(
        [right_eye_x, eye_y, right_eye_x + eye_size, eye_y + eye_size], fill="#000000"
    )

    # Magnifying glass (detective tool)
    glass_x = size - 10
    glass_y = size - 10
    glass_size = 6
    # Glass circle
    draw.ellipse(
        [glass_x, glass_y, glass_x + glass_size, glass_y + glass_size],
        fill=None,
        outline="#E8A5A5",
        width=2,
    )
    # Handle
    draw.line(
        [
            glass_x + glass_size,
            glass_y + glass_size,
            glass_x + glass_size + 3,
            glass_y + glass_size + 3,
        ],
        fill="#E8A5A5",
        width=2,
    )

    # Save as PNG (Gradio can use PNG as favicon)
    favicon_path = os.path.join(tempfile.gettempdir(), "murder_mystery_favicon.png")
    img.save(favicon_path)
    return favicon_path


def create_placeholder_image() -> str:
    """Create an engaging splash screen for the murder mystery game.

    Returns:
        Path to the placeholder image file
    """
    # Create a 500x500 image with dark theme background
    img = Image.new("RGB", (500, 500), color="#0d0d26")
    draw = ImageDraw.Draw(img)

    # Colors matching the retro theme
    cyan = "#00FFFF"
    dark_cyan = "#006666"
    gold = "#D4AF37"
    white = "#FFFFFF"
    muted = "#888888"
    red = "#CC3333"

    # Load fonts with fallbacks
    def load_font(size, bold=False):
        font_paths = [
            f"/System/Library/Fonts/Supplemental/Arial{'Bold' if bold else ''}.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            (
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
                if bold
                else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            ),
        ]
        for path in font_paths:
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
        return ImageFont.load_default()

    title_font = load_font(22, bold=True)
    feature_font = load_font(16)
    small_font = load_font(14)
    cta_font = load_font(18, bold=True)

    # Draw decorative corner brackets (top-left)
    draw.line([(30, 25), (30, 50)], fill=cyan, width=2)
    draw.line([(30, 25), (55, 25)], fill=cyan, width=2)
    # Top-right
    draw.line([(470, 25), (470, 50)], fill=cyan, width=2)
    draw.line([(445, 25), (470, 25)], fill=cyan, width=2)

    # Main tagline - Voice-Powered AI Mystery
    tagline = "~ VOICE-POWERED AI MYSTERY ~"
    tagline_bbox = draw.textbbox((0, 0), tagline, font=title_font)
    tagline_width = tagline_bbox[2] - tagline_bbox[0]
    draw.text(((500 - tagline_width) // 2, 45), tagline, fill=cyan, font=title_font)

    # Decorative line under title
    draw.line([(100, 80), (400, 80)], fill=dark_cyan, width=1)

    # Atmospheric intro with symbols
    intro_lines = [
        ("*", "A body has been discovered...", red),
        ("?", "Four suspects. One killer.", white),
    ]

    intro_y = 100
    for i, (symbol, text, color) in enumerate(intro_lines):
        full_text = f"[ {symbol} ]  {text}"
        bbox = draw.textbbox((0, 0), full_text, font=feature_font)
        width = bbox[2] - bbox[0]
        draw.text(
            ((500 - width) // 2, intro_y + (i * 32)),
            full_text,
            fill=color,
            font=feature_font,
        )

    # Decorative divider with diamond
    draw.line([(60, 175), (220, 175)], fill=dark_cyan, width=1)
    diamond = "<>"
    d_bbox = draw.textbbox((0, 0), diamond, font=small_font)
    d_width = d_bbox[2] - d_bbox[0]
    draw.text(((500 - d_width) // 2, 168), diamond, fill=cyan, font=small_font)
    draw.line([(280, 175), (440, 175)], fill=dark_cyan, width=1)

    # Feature list - what makes this game special (using ASCII symbols)
    features = [
        (">", "Speak to interrogate suspects"),
        (">", "Search locations for clues"),
        (">", "Hear AI-voiced suspect responses"),
        (">", "Every mystery is unique"),
        (">", "Make your accusation!"),
    ]

    features_y = 195
    line_height = 34

    for i, (bullet, text) in enumerate(features):
        full_line = f"  {bullet}  {text}"
        bbox = draw.textbbox((0, 0), full_line, font=feature_font)
        width = bbox[2] - bbox[0]
        x = (500 - width) // 2
        # Draw bullet in cyan, text in white
        draw.text(
            (x, features_y + (i * line_height)),
            f"  {bullet}",
            fill=cyan,
            font=feature_font,
        )
        text_x = x + draw.textbbox((0, 0), f"  {bullet}  ", font=feature_font)[2]
        draw.text(
            (text_x, features_y + (i * line_height)),
            text,
            fill=white,
            font=feature_font,
        )

    # Decorative divider
    draw.line([(60, 375), (220, 375)], fill=dark_cyan, width=1)
    draw.text(((500 - d_width) // 2, 368), diamond, fill=cyan, font=small_font)
    draw.line([(280, 375), (440, 375)], fill=dark_cyan, width=1)

    # Pro tip
    tip = "[ TIP: Use your microphone to play! ]"
    tip_bbox = draw.textbbox((0, 0), tip, font=small_font)
    tip_width = tip_bbox[2] - tip_bbox[0]
    draw.text(((500 - tip_width) // 2, 395), tip, fill=muted, font=small_font)

    # Call to action with arrows
    cta = ">>> START NEW MYSTERY <<<"
    cta_bbox = draw.textbbox((0, 0), cta, font=cta_font)
    cta_width = cta_bbox[2] - cta_bbox[0]
    draw.text(((500 - cta_width) // 2, 430), cta, fill=gold, font=cta_font)

    # Draw decorative corner brackets (bottom-left)
    draw.line([(30, 450), (30, 475)], fill=cyan, width=2)
    draw.line([(30, 475), (55, 475)], fill=cyan, width=2)
    # Bottom-right
    draw.line([(470, 450), (470, 475)], fill=cyan, width=2)
    draw.line([(445, 475), (470, 475)], fill=cyan, width=2)

    # Save to a temporary file
    placeholder_path = os.path.join(
        tempfile.gettempdir(), "murder_mystery_placeholder.png"
    )
    img.save(placeholder_path)
    return placeholder_path


def convert_alignment_to_subtitles(
    alignment_data: Optional[List[Dict]],
) -> Optional[List[Dict]]:
    """Convert alignment_data format to Gradio subtitles format.

    Args:
        alignment_data: List of dicts with 'word', 'start', 'end' keys from TTS alignment

    Returns:
        List of dicts in format Gradio expects: [{"timestamp": [start, end], "text": str}, ...]
        or None if no alignment data

    Note:
        Gradio expects 'timestamp' field as a list/tuple [start, end] and 'text' field for each subtitle.
        Uses alignment data words directly - they represent what was actually spoken in the audio.
        Preserves ALL words from alignment data to ensure perfect sync with audio.
    """
    if not alignment_data:
        logger.warning("[Subtitles] No alignment data provided")
        return None

    # Gradio subtitles format: list of dicts with 'timestamp' (as [start, end]) and 'text' keys
    # Use alignment data words exactly as they are - they match what's spoken in the audio
    subtitles = []
    for word_data in alignment_data:
        word = word_data.get("word", "")
        start = word_data.get("start", 0.0)
        end = word_data.get("end", 0.0)

        # Preserve the word as-is (don't strip - might remove important characters)
        # Only skip if completely empty
        if (
            word or word == ""
        ):  # Include even empty strings if they're in alignment (spaces/punctuation)
            # But actually, skip truly empty strings to avoid issues
            if word.strip():  # Only add if word has content after stripping whitespace
                subtitles.append(
                    {
                        "timestamp": [float(start), float(end)],
                        "text": word,  # Use word exactly as it appears in alignment data
                    }
                )

    logger.info(
        "[Subtitles] Converted %d alignment words to %d subtitles",
        len(alignment_data),
        len(subtitles),
    )
    return subtitles if subtitles else None


# ============================================================================
# GRADIO UI
# ============================================================================


def create_app():
    """Create the Gradio application."""

    with gr.Blocks(title="Murder Mystery") as app:

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

        # ====== MAIN LAYOUT ======
        with gr.Row(elem_classes="main-layout-row"):

            # === LEFT: SIDE PANEL ===
            with gr.Column(
                scale=1, min_width=200, elem_classes="side-column side-column-left"
            ):
                # Victim and Scene - first card (open by default)
                with gr.Accordion(
                    "🧳 CASE DETAILS", open=True, elem_classes="side-panel"
                ):
                    victim_scene_html = gr.HTML(
                        "<em>Start a game to see case details...</em>",
                        elem_classes="transcript-panel",
                    )

                # Suspects list - show who can be questioned (open by default)
                with gr.Accordion(
                    "🎭 SUSPECTS", open=True, elem_classes="side-panel suspects-panel"
                ):
                    suspects_list_html = gr.HTML(
                        "<em>Start a game to see suspects...</em>",
                        elem_classes="transcript-panel suspects-list",
                    )

            # === CENTER: MAIN STAGE ===
            with gr.Column(scale=3, elem_classes="center-column"):

                # Stage container (styled via .center-column > .gr-group in CSS)
                with gr.Group():

                    # Speaker name - hidden initially, will show when game starts
                    speaker_html = gr.HTML(
                        '<div class="speaker-name" style="display: none;"></div>'
                    )

                    # Portrait display - larger size for better visibility
                    # Start with placeholder image
                    placeholder_img = create_placeholder_image()
                    portrait_image = gr.Image(
                        value=placeholder_img,
                        show_label=False,
                        elem_classes="portrait-image",
                        visible=True,  # Visible by default, will show image when set
                    )

                    # Audio player with built-in subtitles support (Gradio handles word highlighting)
                    audio_output = gr.Audio(
                        label=None,
                        show_label=False,
                        autoplay=False,  # Don't autoplay initially - no audio to play yet
                        elem_classes="audio-player",
                    )

                # Start game button (shown initially)
                with gr.Column(elem_classes="start-button-container"):
                    start_btn = gr.Button(
                        "🚀 START NEW MYSTERY", elem_classes="start-button", size="lg"
                    )

                # Input bar - voice only
                with gr.Column(elem_classes="input-bar", visible=False) as input_row:
                    # Voice input - only input method
                    voice_input = gr.Audio(
                        sources=["microphone"],
                        type="filepath",
                        label=None,
                        show_label=False,
                    )

            # === RIGHT: SIDE PANEL ===
            with gr.Column(
                scale=1, min_width=200, elem_classes="side-column side-column-right"
            ):
                # Locations card (open by default)
                with gr.Accordion("📍 LOCATIONS", open=True, elem_classes="side-panel"):
                    locations_html = gr.HTML("<em>Start a game...</em>")

                # Clues card (open by default)
                with gr.Accordion(
                    "🔎 CLUES FOUND", open=True, elem_classes="side-panel"
                ):
                    clues_html = gr.HTML("<em>No clues yet...</em>")

                # Accusations card (open by default)
                with gr.Accordion(
                    "⚖️ ACCUSATIONS", open=True, elem_classes="side-panel"
                ):
                    accusations_html = gr.HTML(
                        '<div class="accusations-display">Accusations: '
                        "<span>"
                        '<span class="accusations-pip"></span>'
                        '<span class="accusations-pip"></span>'
                        '<span class="accusations-pip"></span>'
                        "</span></div>"
                    )

        # Hidden timer for checking mystery completion (inactive by default)
        mystery_check_timer = gr.Timer(value=1.0, active=False)

        # ====== EVENT HANDLERS ======

        def _normalize_session_id(sess_id) -> str:
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

        def on_start_game(sess_id, progress=gr.Progress()):
            """Handle game start with staged progress updates.

            Fast path (~6s): premise → welcome → TTS → image
            Background: full mystery generation (~15s, timer updates panels when ready)
            """
            sess_id = _normalize_session_id(sess_id)

            # Initial yield to hide start button immediately
            progress(0, desc="🔍 Starting mystery generation...")
            yield [
                gr.update(),  # speaker_html
                gr.update(),  # audio_output
                gr.update(),  # portrait_image
                gr.update(),  # input_row
                gr.update(visible=False),  # start_btn - hide button
                gr.update(),  # victim_scene_html
                gr.update(),  # suspects_list_html
                gr.update(),  # locations_html
                gr.update(),  # clues_html
                gr.update(),  # accusations_html
                gr.update(),  # mystery_check_timer
            ]

            # Stage descriptions for progress bar
            stage_descriptions = {
                "premise": "🎭 Creating murder scenario...",
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

            for stage_name, stage_progress, stage_data in start_new_game_staged(
                sess_id
            ):
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

            # Get placeholder image path
            placeholder_img = create_placeholder_image()

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
                from image_service import generate_title_card_on_demand
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

            # Use placeholder if no opening scene is available
            display_portrait = portrait if portrait else placeholder_img

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
                <div style="font-weight: 700; margin-bottom: 8px; font-size: 1.1em; padding-bottom: 8px;">
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

            yield [
                # Speaker - show when game starts
                f'<div class="speaker-name" style="padding: 16px 0 !important;">🗣️ {speaker} SPEAKING...</div>',
                # Audio with subtitles
                audio_update,
                # Portrait
                display_portrait,
                # Show game UI
                gr.update(visible=True),  # input_row
                gr.update(visible=False),  # start_btn
                # Side panels - show "loading" state, timer will update when ready
                victim_html,
                format_suspects_list_html(None, state.suspects_talked_to, loading=True),
                format_locations_html(None, state.searched_locations, loading=True),
                format_clues_html(state.clues_found),
                # Accusations
                _format_accusations_html(state.wrong_accusations),
                # Activate timer to check when mystery is ready
                gr.update(active=True),
            ]

        def _format_accusations_html(wrong: int):
            pips = ""
            for i in range(3):
                cls = "accusations-pip used" if i < wrong else "accusations-pip"
                pips += f'<span class="{cls}"></span>'
            return f'<div class="accusations-display">Accusations:<span>{pips}</span></div>'

        def check_mystery_ready(sess_id: str):
            """Timer callback to check if full mystery is ready and update UI."""
            sess_id = _normalize_session_id(sess_id)
            state = get_or_create_state(sess_id)
            ready = getattr(state, "mystery_ready", False)
            logger.info(
                "[APP] Timer tick - session: %s, mystery_ready: %s",
                sess_id[:8] if sess_id else "None",
                ready,
            )

            if ready and state.mystery is not None:
                # Mystery is ready - update UI and stop timer
                logger.info("[APP] Timer: Full mystery ready, updating UI panels")
                return [
                    format_victim_scene_html(state.mystery),
                    format_suspects_list_html(
                        state.mystery, state.suspects_talked_to, loading=False
                    ),
                    format_locations_html(
                        state.mystery, state.searched_locations, loading=False
                    ),
                    gr.update(active=False),  # Stop the timer
                ]
            else:
                # Mystery still loading - keep timer active, no UI changes
                return [
                    gr.update(),  # victim_scene_html - no change
                    gr.update(),  # suspects_list_html - no change
                    gr.update(),  # locations_html - no change
                    gr.update(active=True),  # Keep timer running
                ]

        def _on_custom_message(message: str, sess_id: str):
            """Handle free-form text input (currently unused - voice only)."""
            sess_id = _normalize_session_id(sess_id)
            if not message.strip():
                return [gr.update()] * 8

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
            placeholder_img = create_placeholder_image()

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
                if scene_image:
                    logger.info("Displaying scene image for location: %s", location)
                    display_portrait = scene_image

            # Priority 3: Fall back to opening scene image (Game Master)
            if not display_portrait:
                display_portrait = images.get("_opening_scene", None)
                if display_portrait:
                    logger.info("Displaying opening scene image (Game Master)")

            # Priority 4: Use placeholder if nothing available
            if not display_portrait:
                display_portrait = placeholder_img
                logger.info("Using placeholder image")

            # Convert alignment_data to Gradio subtitles format
            # Use alignment data directly - it represents what was actually spoken
            subtitles = convert_alignment_to_subtitles(alignment_data)

            return [
                f'<div class="speaker-name" style="padding: 16px 0 !important;">🗣️ {speaker} SPEAKING...</div>',
                (
                    gr.update(value=audio_path, subtitles=subtitles)
                    if audio_path
                    else None
                ),
                gr.update(value=display_portrait, visible=True),
                format_victim_scene_html(state.mystery),
                format_suspects_list_html(state.mystery, state.suspects_talked_to),
                format_locations_html(state.mystery, state.searched_locations),
                format_clues_html(state.clues_found),
                _format_accusations_html(state.wrong_accusations),
                "",  # Clear text input
            ]

        def on_voice_input(audio_path: str, sess_id, progress=gr.Progress()):
            """Handle voice input with two-stage yield for faster perceived response.

            Stage 1 (fast): Transcribe + run LLM logic, yield text/panels immediately
            Stage 2 (slow): Generate TTS audio + images, yield final update with audio
            """
            if not audio_path:
                yield [gr.update()] * 8
                return

            # Normalize session id so it matches what on_start_game used
            sess_id = _normalize_session_id(sess_id)

            # Check if game has been started
            state_before = get_or_create_state(sess_id)
            if not state_before.mystery and not getattr(
                state_before, "premise_setting", None
            ):
                logger.warning("[APP] Voice input received but no game started yet")
                yield [gr.update()] * 8
                return

            # Show progress indicator while processing
            progress(0, desc="🗣️ Transcribing...")
            yield [gr.update()] * 8

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
                yield [gr.update()] * 8
                return

            # ========== STAGE 1: FAST - Run LLM logic only ==========
            # Use the full 0→100 range for the "thinking" phase
            progress(0.5, desc="🧠 Figuring out what happens...")

            t2 = time.perf_counter()
            clean_response, speaker, state, actions, audio_path_from_tool = (
                run_action_logic("custom", "", text, sess_id)
            )
            t3 = time.perf_counter()
            logger.info("[PERF] Action logic took %.2fs", t3 - t2)
            progress(1.0, desc="🧠 Figuring out what happens...")

            # Get images dict (may not have new portrait yet)
            images = mystery_images.get(sess_id, {})
            placeholder_img = create_placeholder_image()

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
                    display_portrait = portrait

            # Priority 2: Check if a location was just searched
            if not display_portrait and newly_searched_location:
                location = list(newly_searched_location)[0]
                scene_image = images.get(location, None)
                if scene_image:
                    display_portrait = scene_image

            # Priority 3: Fall back to opening scene image (Game Master)
            if not display_portrait:
                display_portrait = images.get("_opening_scene", None)

            # Priority 4: Use placeholder if nothing available
            if not display_portrait:
                display_portrait = placeholder_img

            # YIELD STAGE 1: Show text response + updated panels immediately (no audio yet)
            logger.info("[APP] Stage 1 complete - yielding fast UI update")

            yield [
                f'<div class="speaker-name" style="padding: 16px 0 !important;">🗣️ {speaker} SPEAKING...</div>',
                gr.update(),  # Audio placeholder - will be filled in stage 2
                gr.update(value=display_portrait, visible=True),
                format_victim_scene_html(state.mystery),
                format_suspects_list_html(state.mystery, state.suspects_talked_to),
                format_locations_html(state.mystery, state.searched_locations),
                format_clues_html(state.clues_found),
                _format_accusations_html(state.wrong_accusations),
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
                if scene_image:
                    display_portrait = scene_image

            # Priority 3: Fall back to opening scene image (Game Master)
            if not display_portrait:
                display_portrait = images.get("_opening_scene", None)

            # Priority 4: Use placeholder if nothing available
            if not display_portrait:
                display_portrait = placeholder_img

            # Convert alignment_data to Gradio subtitles format
            subtitles = convert_alignment_to_subtitles(alignment_data)

            # YIELD STAGE 2: Final update with audio + updated portrait
            progress(1.0, desc="Done!")
            logger.info("[APP] Stage 2 complete - yielding final UI with audio")

            yield [
                f'<div class="speaker-name" style="padding: 16px 0 !important;">🗣️ {speaker} SPEAKING...</div>',
                (
                    gr.update(value=audio_resp, subtitles=subtitles, autoplay=True)
                    if audio_resp
                    else gr.update()
                ),
                gr.update(value=display_portrait, visible=True),
                format_victim_scene_html(state.mystery),
                format_suspects_list_html(state.mystery, state.suspects_talked_to),
                format_locations_html(state.mystery, state.searched_locations),
                format_clues_html(state.clues_found),
                _format_accusations_html(state.wrong_accusations),
            ]

        def reset_voice_input():
            """Clear the voice input so it's ready for the next recording."""
            return gr.update(value=None)

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
        ]

        # Start game
        getattr(start_btn, "click")(
            on_start_game,
            inputs=[session_id],
            outputs=[
                speaker_html,
                audio_output,
                portrait_image,
                input_row,
                start_btn,
                victim_scene_html,
                suspects_list_html,
                locations_html,
                clues_html,
                accusations_html,
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

        # Hide speaker name when audio finishes playing
        def on_audio_stop():
            """Clear speaker name when audio playback ends."""
            return '<div class="speaker-name" style="display: none;"></div>'

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
