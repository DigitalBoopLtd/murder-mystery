"""Voice-First Murder Mystery Game - 90s Point-and-Click Adventure Style.

A reimagined interface that prioritizes voice output with streaming captions,
styled like classic adventure games (Monkey Island, Gabriel Knight, etc.)
"""

import os
import uuid
import base64
import logging
import tempfile
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
    start_new_game,
    process_player_action,
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
    except Exception as e:
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
    draw.ellipse([2, 2, size-2, size-2], fill="#34495E", outline="#1A252F", width=1)
    
    # Head (circle)
    head_size = 14
    head_x = (size - head_size) // 2
    head_y = 6
    draw.ellipse([head_x, head_y, head_x + head_size, head_y + head_size], 
                 fill="#FDB9B9", outline="#E8A5A5", width=1)
    
    # Detective hat (fedora)
    hat_width = 18
    hat_x = (size - hat_width) // 2
    hat_y = 4
    # Hat brim
    draw.ellipse([hat_x - 2, hat_y + 2, hat_x + hat_width + 2, hat_y + 6], 
                 fill="#1A1A1A", outline="#000000", width=1)
    # Hat crown
    draw.ellipse([hat_x + 2, hat_y, hat_x + hat_width - 2, hat_y + 8], 
                 fill="#2C2C2C", outline="#1A1A1A", width=1)
    
    # Eyes (two small dots)
    eye_size = 2
    left_eye_x = head_x + 3
    right_eye_x = head_x + head_size - 5
    eye_y = head_y + 5
    draw.ellipse([left_eye_x, eye_y, left_eye_x + eye_size, eye_y + eye_size], fill="#000000")
    draw.ellipse([right_eye_x, eye_y, right_eye_x + eye_size, eye_y + eye_size], fill="#000000")
    
    # Magnifying glass (detective tool)
    glass_x = size - 10
    glass_y = size - 10
    glass_size = 6
    # Glass circle
    draw.ellipse([glass_x, glass_y, glass_x + glass_size, glass_y + glass_size], 
                 fill=None, outline="#E8A5A5", width=2)
    # Handle
    draw.line([glass_x + glass_size, glass_y + glass_size, glass_x + glass_size + 3, glass_y + glass_size + 3],
              fill="#E8A5A5", width=2)
    
    # Save as PNG (Gradio can use PNG as favicon)
    favicon_path = os.path.join(tempfile.gettempdir(), "murder_mystery_favicon.png")
    img.save(favicon_path)
    return favicon_path


def create_placeholder_image() -> str:
    """Create a placeholder image with an emoji/icon for the portrait display.

    Returns:
        Path to the placeholder image file
    """
    # Create a 500x500 image with a light gray background
    img = Image.new("RGB", (500, 500), color="#F2F2F2")
    draw = ImageDraw.Draw(img)

    # Draw a simple icon/emoji representation
    # Using a large question mark or mystery icon
    try:
        # Try to use a system font
        font_size = 200
        try:
            font = ImageFont.truetype(
                "/System/Library/Fonts/Supplemental/Arial.ttf", font_size
            )
        except:
            try:
                font = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size
                )
            except:
                font = ImageFont.load_default()
    except:
        font = ImageFont.load_default()

    # Draw a large question mark in the center
    text = "?"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    x = (500 - text_width) // 2
    y = (500 - text_height) // 2 - 20  # Slight offset for visual balance

    # Draw with a subtle color
    draw.text((x, y), text, fill="#6B6B6B", font=font)

    # Save to a temporary file
    placeholder_path = os.path.join(
        tempfile.gettempdir(), "murder_mystery_placeholder.png"
    )
    img.save(placeholder_path)
    return placeholder_path


def convert_alignment_to_subtitles(alignment_data: Optional[List[Dict]]) -> Optional[List[Dict]]:
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
        if word or word == "":  # Include even empty strings if they're in alignment (spaces/punctuation)
            # But actually, skip truly empty strings to avoid issues
            if word.strip():  # Only add if word has content after stripping whitespace
                subtitles.append({
                    "timestamp": [float(start), float(end)],
                    "text": word  # Use word exactly as it appears in alignment data
                })
    
    logger.info(f"[Subtitles] Converted {len(alignment_data)} alignment words to {len(subtitles)} subtitles")
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
            favicon_data = base64.b64encode(f.read()).decode('utf-8')
        favicon_html = f'''
        <link rel="icon" type="image/png" href="data:image/png;base64,{favicon_data}">
        <link rel="shortcut icon" type="image/png" href="data:image/png;base64,{favicon_data}">
        '''
        
        # Inject CSS and favicon
        gr.HTML(f"<style>{RETRO_CSS}</style>{favicon_html}")

        # Session state
        session_id = gr.State(lambda: str(uuid.uuid4()))

        # ====== TITLE BAR ======
        with gr.Row(elem_classes="title-bar"):
            gr.HTML('<div class="game-title">🕵️‍♀️ MURDER MYSTERY</div>')
            # Accusations counter - top right
            accusations_html = gr.HTML(
                '<div class="accusations-display accusations-title-bar">Accusations: <span class="accusations-pip"></span><span class="accusations-pip"></span><span class="accusations-pip"></span></div>'
            )

        # ====== MAIN LAYOUT ======
        with gr.Row():

            # === LEFT: SIDE PANEL ===
            with gr.Column(scale=1, min_width=200):
                # Victim and Scene - first card
                with gr.Group(elem_classes="side-panel"):
                    gr.HTML('<div class="panel-title">🧳 Case Details</div>')
                    victim_scene_html = gr.HTML(
                        "<em>Start a game to see case details...</em>",
                        elem_classes="transcript-panel",
                    )

                # Suspects list - show who can be questioned
                with gr.Group(elem_classes="side-panel"):
                    gr.HTML('<div class="panel-title">🎭 Suspects</div>')
                    suspects_list_html = gr.HTML(
                        "<em>Start a game to see suspects...</em>",
                        elem_classes="transcript-panel",
                    )

                # Locations card - above clues
                with gr.Group(elem_classes="side-panel"):
                    gr.HTML('<div class="panel-title">📍 Locations</div>')
                    locations_html = gr.HTML("<em>Start a game...</em>")

                # Clues card - below locations
                with gr.Group(elem_classes="side-panel"):
                    gr.HTML('<div class="panel-title">🔎 Clues Found</div>')
                    clues_html = gr.HTML("<em>No clues yet...</em>")

            # === CENTER: MAIN STAGE ===
            with gr.Column(scale=3):

                # Stage container
                with gr.Group(elem_classes="stage-container"):
                    
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
                start_btn = gr.Button(
                    "▶ START NEW MYSTERY", elem_classes="start-button", size="lg"
                )

                # Input bar
                with gr.Row(elem_classes="input-bar", visible=False) as input_row:
                    voice_input = gr.Audio(
                        sources=["microphone"],
                        type="filepath",
                        label=None,
                        show_label=False,
                        scale=1,
                    )
                    text_input = gr.Textbox(
                        placeholder="Type your question or action...",
                        show_label=False,
                        elem_classes="text-input",
                        scale=3,
                    )
                    send_btn = gr.Button("📤", elem_classes="action-button", scale=0)

        # ====== EVENT HANDLERS ======

        def on_start_game(sess_id):
            """Handle game start."""
            state, response, audio_path, speaker, alignment_data = start_new_game(
                sess_id
            )

            # Log what we got back
            logger.info(f"[APP] on_start_game received:")
            logger.info(f"[APP]   response: {len(response) if response else 0} chars")
            logger.info(f"[APP]   audio_path: {audio_path}")
            logger.info(f"[APP]   speaker: {speaker}")
            logger.info(
                f"[APP]   alignment_data: {len(alignment_data) if alignment_data else 'None'} items"
            )

            # Verify audio file exists
            if audio_path:
                if os.path.exists(audio_path):
                    logger.info(
                        f"[APP] ✅ Audio file exists: {os.path.getsize(audio_path)} bytes"
                    )
                else:
                    logger.error(f"[APP] ❌ Audio file NOT FOUND: {audio_path}")
            else:
                logger.error("[APP] ❌ No audio_path received!")

            # Get placeholder image path
            placeholder_img = create_placeholder_image()

            # Get images - retrieve after start_new_game has stored them
            images = mystery_images.get(sess_id, {})

            # Debug logging
            logger.info(f"Retrieving images for session {sess_id}")
            logger.info(f"Available image keys: {list(images.keys())}")

            # Try to get title image, generate on-demand if needed
            portrait = images.get("_title", None)
            
            # Generate title card on-demand if not available
            if not portrait:
                from image_service import generate_title_card_on_demand
                state = get_or_create_state(sess_id)
                if state.mystery:
                    logger.info("Generating title card on-demand...")
                    portrait = generate_title_card_on_demand(state.mystery)
                    if portrait:
                        images["_title"] = portrait
                        mystery_images[sess_id] = images
                        logger.info(f"Generated title card: {portrait}")

            if portrait:
                # Ensure path is absolute and file exists
                if not os.path.isabs(portrait):
                    portrait = os.path.abspath(portrait)

                if not os.path.exists(portrait):
                    logger.warning(f"Portrait image file does not exist: {portrait}")
                    portrait = None
                else:
                    logger.info(f"Portrait image file exists: {portrait}")

            # Use placeholder if no portrait available
            display_portrait = portrait if portrait else placeholder_img

            # Convert alignment_data to Gradio subtitles format
            # Use alignment data directly - it represents what was actually spoken
            subtitles = convert_alignment_to_subtitles(alignment_data)

            # Update audio component with game audio and subtitles
            # Autoplay is allowed after user interaction (Start button click)
            audio_update = None
            if audio_path:
                audio_update = gr.update(
                    value=audio_path,
                    subtitles=subtitles,
                    autoplay=True  # Autoplay after user interaction
                )

            return [
                # Speaker - show when game starts
                f'<div class="speaker-name" style="padding: 16px 0 !important;">🗣️ {speaker}</div>',
                # Audio with subtitles - will autoplay after user interaction (Start button click)
                audio_update,
                # Portrait - return path directly, or placeholder if not available
                display_portrait,
                # Show game UI
                gr.update(visible=True),  # input_row
                gr.update(visible=False),  # start_btn
                # Side panels
                format_victim_scene_html(state.mystery),
                format_suspects_list_html(state.mystery, state.suspects_talked_to),
                format_locations_html(state.mystery, state.searched_locations),
                format_clues_html(state.clues_found),
                # Accusations
                _format_accusations_html(state.wrong_accusations),
            ]

        def _format_accusations_html(wrong: int):
            pips = ""
            for i in range(3):
                cls = "accusations-pip used" if i < wrong else "accusations-pip"
                pips += f'<span class="{cls}"></span>'
            return f'<div class="accusations-display accusations-title-bar">Accusations: {pips}</div>'

        def on_custom_message(message: str, sess_id: str):
            """Handle free-form text input."""
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

            response, audio_path, speaker, state, alignment_data = (
                process_player_action("custom", "", message, sess_id)
            )

            # Refresh images dict after processing (in case new images were generated)
            images = mystery_images.get(sess_id, {})
            logger.info(f"Available images for session {sess_id}: {list(images.keys())}")
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

            # Priority 1: Check if a suspect was just talked to (highest priority)
            if newly_talked_suspect:
                suspect_name = list(newly_talked_suspect)[0]
                logger.info(f"Looking for portrait for suspect: {suspect_name}")
                portrait = images.get(suspect_name, None)
                if portrait:
                    logger.info(f"✓ Found portrait for suspect {suspect_name}: {portrait}")
                    display_portrait = portrait
                else:
                    logger.warning(f"✗ No portrait found for suspect {suspect_name} in images dict")
                    # Try to get it directly from mystery_images in case of timing issue
                    session_images = mystery_images.get(sess_id, {})
                    portrait = session_images.get(suspect_name, None)
                    if portrait:
                        logger.info(f"✓ Found portrait in direct lookup: {portrait}")
                        display_portrait = portrait
                        # Update images dict for next time
                        images[suspect_name] = portrait

            # Priority 2: Check if a location was just searched
            if not display_portrait and newly_searched_location:
                location = list(newly_searched_location)[0]
                scene_image = images.get(location, None)
                if scene_image:
                    logger.info(f"Displaying scene image for location: {location}")
                    display_portrait = scene_image

            # Priority 3: Fall back to title image (Game Master)
            if not display_portrait:
                display_portrait = images.get("_title", None)
                if display_portrait:
                    logger.info("Displaying title image (Game Master)")

            # Priority 4: Use placeholder if nothing available
            if not display_portrait:
                display_portrait = placeholder_img
                logger.info("Using placeholder image")

            # Convert alignment_data to Gradio subtitles format
            # Use alignment data directly - it represents what was actually spoken
            subtitles = convert_alignment_to_subtitles(alignment_data)

            return [
                f'<div class="speaker-name" style="padding: 16px 0 !important;">🗣️ {speaker}</div>',
                gr.update(value=audio_path, subtitles=subtitles) if audio_path else None,
                gr.update(value=display_portrait, visible=True),
                format_victim_scene_html(state.mystery),
                format_suspects_list_html(state.mystery, state.suspects_talked_to),
                format_locations_html(state.mystery, state.searched_locations),
                format_clues_html(state.clues_found),
                _format_accusations_html(state.wrong_accusations),
                "",  # Clear text input
            ]

        def on_voice_input(audio_path: str, sess_id: str):
            """Handle voice input."""
            if not audio_path:
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

            # Transcribe
            text = transcribe_audio(audio_path)
            if not text.strip():
                return [gr.update()] * 8

            response, audio_resp, speaker, state, alignment_data = (
                process_player_action("custom", "", text, sess_id)
            )

            # Refresh images dict after processing (in case new images were generated)
            images = mystery_images.get(sess_id, {})
            logger.info(f"Available images for session {sess_id}: {list(images.keys())}")
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

            # Priority 1: Check if a suspect was just talked to (highest priority)
            if newly_talked_suspect:
                suspect_name = list(newly_talked_suspect)[0]
                logger.info(f"Looking for portrait for suspect: {suspect_name}")
                portrait = images.get(suspect_name, None)
                if portrait:
                    logger.info(f"✓ Found portrait for suspect {suspect_name}: {portrait}")
                    display_portrait = portrait
                else:
                    logger.warning(f"✗ No portrait found for suspect {suspect_name} in images dict")
                    # Try to get it directly from mystery_images in case of timing issue
                    session_images = mystery_images.get(sess_id, {})
                    portrait = session_images.get(suspect_name, None)
                    if portrait:
                        logger.info(f"✓ Found portrait in direct lookup: {portrait}")
                        display_portrait = portrait
                        # Update images dict for next time
                        images[suspect_name] = portrait

            # Priority 2: Check if a location was just searched
            if not display_portrait and newly_searched_location:
                location = list(newly_searched_location)[0]
                scene_image = images.get(location, None)
                if scene_image:
                    logger.info(f"Displaying scene image for location: {location}")
                    display_portrait = scene_image

            # Priority 3: Fall back to title image (Game Master)
            if not display_portrait:
                display_portrait = images.get("_title", None)
                if display_portrait:
                    logger.info("Displaying title image (Game Master)")

            # Priority 4: Use placeholder if nothing available
            if not display_portrait:
                display_portrait = placeholder_img
                logger.info("Using placeholder image")

            # Convert alignment_data to Gradio subtitles format
            # Use alignment data directly - it represents what was actually spoken
            subtitles = convert_alignment_to_subtitles(alignment_data)

            return [
                f'<div class="speaker-name" style="padding: 16px 0 !important;">🗣️ {speaker}</div>',
                gr.update(value=audio_resp, subtitles=subtitles) if audio_resp else None,
                gr.update(value=display_portrait, visible=True),
                format_victim_scene_html(state.mystery),
                format_suspects_list_html(state.mystery, state.suspects_talked_to),
                format_locations_html(state.mystery, state.searched_locations),
                format_clues_html(state.clues_found),
                _format_accusations_html(state.wrong_accusations),
            ]

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
            ],
        )

        # Text input
        getattr(text_input, "submit")(
            on_custom_message,
            inputs=[text_input, session_id],
            outputs=game_outputs + [text_input],
        )
        getattr(send_btn, "click")(
            on_custom_message,
            inputs=[text_input, session_id],
            outputs=game_outputs + [text_input],
        )

        # Voice input
        getattr(voice_input, "stop_recording")(
            on_voice_input, inputs=[voice_input, session_id], outputs=game_outputs
        )

    return app


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    app = create_app()
    app.launch(server_name="0.0.0.0", server_port=7860, share=False)
