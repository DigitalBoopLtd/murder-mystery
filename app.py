"""Voice-First Murder Mystery Game - 90s Point-and-Click Adventure Style.

A reimagined interface that prioritizes voice output with streaming captions,
styled like classic adventure games (Monkey Island, Gabriel Knight, etc.)
"""

import os
import re
import logging
import tempfile
import uuid
from typing import Optional, Tuple, List, Dict
from concurrent.futures import ThreadPoolExecutor
import gradio as gr
from dotenv import load_dotenv
from openai import OpenAI

try:
    from elevenlabs import ElevenLabs

    ELEVENLABS_AVAILABLE = True
except ImportError:
    ELEVENLABS_AVAILABLE = False
    ElevenLabs = None
from image_service import generate_all_mystery_images
from game_state import GameState
from mystery_generator import generate_mystery, prepare_game_prompt
from agent import create_game_master_agent, process_message
from game_parser import parse_game_actions

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
game_states: Dict[str, GameState] = {}
mystery_images: Dict[str, Dict[str, str]] = {}  # session_id -> {name: path}

# ============================================================================
# CSS STYLING - 90s Point-and-Click Adventure Game Aesthetic
# ============================================================================

RETRO_CSS = """
/* Import Roblox-style fonts */
@import url('https://fonts.googleapis.com/css2?family=Source+Sans+Pro:wght@400;600;700&family=Inter:wght@400;500;600;700&display=swap');

/* Root variables for theming - Roblox inspired palette */
:root {
    --bg-primary: #F7F7F7; /* Roblox light gray - main background */
    --bg-secondary: #FFFFFF; /* White - secondary background */
    --bg-panel: #F2F2F2; /* Light gray - panel background */
    --bg-card: #FFFFFF; /* White - card background */
    --text-primary: #1E1E1E; /* Dark gray - primary text */
    --text-secondary: #6B6B6B; /* Medium gray - secondary text */
    --accent-blue: #00A2FF; /* Roblox blue - primary accent */
    --accent-blue-dark: #0088CC; /* Darker blue - hover states */
    --accent-green: #00C853; /* Green - positive indicators */
    --accent-red: #E53935; /* Red - warnings/accusations */
    --accent-orange: #FF6F00; /* Orange - highlights */
    --border-color: #E0E0E0; /* Light gray - borders */
    --shadow-color: rgba(0, 0, 0, 0.1);
    --shadow-hover: rgba(0, 162, 255, 0.2);
}

/* Main container */
.adventure-game {
    background: var(--bg-primary) !important;
    min-height: 100vh;
    font-family: 'Source Sans Pro', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

/* Title bar - top of screen Roblox style */
.title-bar {
    background: var(--bg-secondary);
    border-bottom: 2px solid var(--border-color);
    padding: 16px 24px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: 0 2px 4px var(--shadow-color);
}

.game-title {
    font-family: 'Source Sans Pro', sans-serif;
    font-size: 20px;
    font-weight: 700;
    color: var(--accent-blue);
    letter-spacing: -0.5px;
}

/* The Stage - main viewing area */
.stage-container {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    margin: 16px;
    padding: 24px;
    min-height: 350px;
    position: relative;
    box-shadow: 0 2px 8px var(--shadow-color);
}

/* Speaker indicator */
.speaker-name {
    font-family: 'Source Sans Pro', sans-serif;
    font-size: 24px;
    font-weight: 600;
    color: var(--accent-blue);
    text-align: center;
    margin-bottom: 16px;
}

/* Caption display area */
.caption-display {
    font-family: 'Source Sans Pro', sans-serif;
    font-size: 16px;
    line-height: 1.6;
    color: var(--text-primary);
    text-align: center;
    padding: 20px 24px;
    min-height: 120px;
    max-height: 200px;
    overflow-y: auto;
}

.caption-display em {
    color: var(--text-secondary);
}

/* Portrait display */
.portrait-container {
    text-align: center;
    margin: 10px 0;
}

.portrait-image {
    max-width: 600px;
    max-height: 600px;
    width: 100%;
    height: auto;
    border: 2px solid var(--border-color);
    border-radius: 12px;
    box-shadow: 0 4px 12px var(--shadow-color);
}

/* Waveform/speaking indicator */
.speaking-indicator {
    display: flex;
    justify-content: center;
    gap: 4px;
    margin: 15px 0;
}

.speaking-indicator .bar {
    width: 4px;
    height: 20px;
    background: var(--accent-blue);
    animation: pulse 0.5s ease-in-out infinite;
    border-radius: 2px;
}

.speaking-indicator .bar:nth-child(2) { animation-delay: 0.1s; }
.speaking-indicator .bar:nth-child(3) { animation-delay: 0.2s; }
.speaking-indicator .bar:nth-child(4) { animation-delay: 0.3s; }
.speaking-indicator .bar:nth-child(5) { animation-delay: 0.4s; }

@keyframes pulse {
    0%, 100% { transform: scaleY(0.5); opacity: 0.5; }
    50% { transform: scaleY(1); opacity: 1; }
}

/* Suspect buttons - Roblox card style */
.suspect-bar {
    display: flex;
    justify-content: center;
    gap: 12px;
    padding: 16px;
    background: var(--bg-primary);
    flex-wrap: wrap;
}

.suspect-button {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 12px 16px;
    cursor: pointer;
    transition: all 0.2s ease;
    text-align: center;
    min-width: 140px;
    color: var(--text-primary);
    box-shadow: 0 2px 4px var(--shadow-color);
}

.suspect-button:hover {
    border-color: var(--accent-blue);
    transform: translateY(-2px);
    box-shadow: 0 4px 12px var(--shadow-hover);
    background: #F8FBFF;
}

.suspect-button img {
    width: 80px;
    height: 80px;
    border-radius: 8px;
    border: 1px solid var(--border-color);
    margin-bottom: 8px;
}

.suspect-button .name {
    font-family: 'Source Sans Pro', sans-serif;
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
}

.suspect-button .role {
    font-family: 'Source Sans Pro', sans-serif;
    font-size: 12px;
    color: var(--text-secondary);
}

/* Action bar - Roblox style */
.action-bar {
    display: flex;
    justify-content: center;
    gap: 12px;
    padding: 16px;
    background: var(--bg-primary);
}

.action-button {
    font-family: 'Source Sans Pro', sans-serif !important;
    font-size: 14px !important;
    font-weight: 600 !important;
    background: var(--accent-blue) !important;
    border: none !important;
    color: #FFFFFF !important;
    padding: 10px 20px !important;
    border-radius: 6px !important;
    cursor: pointer !important;
    transition: all 0.2s ease !important;
    box-shadow: 0 2px 4px var(--shadow-color) !important;
}

.action-button:hover {
    background: var(--accent-blue-dark) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 8px var(--shadow-hover) !important;
}

/* Input area */
.input-bar {
    display: flex;
    gap: 12px;
    padding: 16px;
    background: var(--bg-primary);
    border-top: 1px solid var(--border-color);
    align-items: center;
    justify-content: center;
}

.text-input {
    font-family: 'Source Sans Pro', sans-serif !important;
    font-size: 14px !important;
    background: var(--bg-card) !important;
    border: 1px solid var(--border-color) !important;
    color: var(--text-primary) !important;
    padding: 10px 16px !important;
    border-radius: 6px !important;
    flex-grow: 1 !important;
    max-width: 500px !important;
}

.text-input:focus {
    border-color: var(--accent-blue) !important;
    outline: none !important;
    box-shadow: 0 0 0 3px rgba(0, 162, 255, 0.1) !important;
}

/* Side panel - Roblox card style */
.side-panel {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 16px;
    height: fit-content;
    box-shadow: 0 2px 4px var(--shadow-color);
    margin-bottom: 12px;
}

.panel-title {
    font-family: 'Source Sans Pro', sans-serif;
    font-size: 16px;
    font-weight: 600;
    color: var(--accent-blue);
    border-bottom: 2px solid var(--border-color);
    padding-bottom: 8px;
    margin-bottom: 12px;
}

.clue-item {
    font-family: 'Source Sans Pro', sans-serif;
    font-size: 13px;
    color: var(--text-primary);
    padding: 8px 12px;
    border-left: 3px solid var(--accent-blue);
    margin-bottom: 6px;
    background: #F8FBFF;
    border-radius: 4px;
}

.location-item {
    font-family: 'Source Sans Pro', sans-serif;
    font-size: 14px;
    padding: 6px 12px;
    color: var(--text-primary);
    border-radius: 4px;
    margin-bottom: 4px;
}

.location-item.searched {
    color: var(--text-secondary);
    text-decoration: line-through;
    background: var(--bg-panel);
}

/* Status bar - bottom of screen */
.status-bar {
    background: var(--bg-card);
    border-top: 1px solid var(--border-color);
    padding: 12px 24px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: 0 -2px 4px var(--shadow-color);
}

.accusations-display {
    font-family: 'Source Sans Pro', sans-serif;
    font-size: 14px;
    font-weight: 500;
    color: var(--text-primary);
}

.accusations-pip {
    display: inline-block;
    width: 10px;
    height: 10px;
    background: var(--accent-blue);
    border-radius: 50%;
    margin: 0 4px;
}

.accusations-pip.used {
    background: var(--accent-red);
}

/* Audio player styling */
.audio-player {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-color) !important;
    border-radius: 6px !important;
}

/* Transcript panel */
.transcript-panel {
    max-height: 300px;
    overflow-y: auto;
    font-family: 'Source Sans Pro', sans-serif;
    font-size: 13px;
    line-height: 1.5;
}

.transcript-entry {
    padding: 8px 0;
    border-bottom: 1px solid var(--border-color);
}

.transcript-speaker {
    font-family: 'Source Sans Pro', sans-serif;
    font-weight: 600;
    color: var(--accent-blue);
    font-size: 13px;
}

.transcript-text {
    color: var(--text-secondary);
    margin-top: 4px;
}

/* New game splash */
.splash-screen {
    text-align: center;
    padding: 60px 20px;
}

.splash-title {
    font-family: 'Source Sans Pro', sans-serif;
    font-size: 32px;
    font-weight: 700;
    color: var(--accent-blue);
    margin-bottom: 16px;
}

.splash-subtitle {
    font-family: 'Source Sans Pro', sans-serif;
    font-size: 16px;
    color: var(--text-secondary);
    margin-bottom: 32px;
}

.start-button {
    font-family: 'Source Sans Pro', sans-serif !important;
    font-size: 16px !important;
    font-weight: 600 !important;
    background: var(--accent-blue) !important;
    border: none !important;
    color: #FFFFFF !important;
    padding: 14px 32px !important;
    border-radius: 8px !important;
    cursor: pointer !important;
    box-shadow: 0 4px 12px var(--shadow-hover) !important;
    transition: all 0.2s ease !important;
}

.start-button:hover {
    background: var(--accent-blue-dark) !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 16px var(--shadow-hover) !important;
}

/* Theme toggle */
.theme-toggle {
    font-family: 'Source Sans Pro', sans-serif !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    background: var(--bg-card) !important;
    border: 1px solid var(--border-color) !important;
    color: var(--text-primary) !important;
    padding: 6px 12px !important;
    border-radius: 6px !important;
    cursor: pointer !important;
    transition: all 0.2s ease !important;
}

.theme-toggle:hover {
    border-color: var(--accent-blue) !important;
    color: var(--accent-blue) !important;
    background: #F8FBFF !important;
}

/* Loading state */
.loading-indicator {
    font-family: 'Source Sans Pro', sans-serif;
    font-size: 16px;
    font-weight: 500;
    color: var(--accent-blue);
    text-align: center;
    animation: blink 1s infinite;
}

@keyframes blink {
    0%, 50% { opacity: 1; }
    51%, 100% { opacity: 0; }
}

/* Gradio overrides */
.gradio-container {
    background: var(--bg-primary) !important;
    max-width: 100% !important;
}

.gr-button {
    font-family: 'Source Sans Pro', sans-serif !important;
}

.gr-box {
    background: var(--bg-card) !important;
    border-color: var(--border-color) !important;
    border-radius: 8px !important;
}

footer {
    display: none !important;
}
"""


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def get_or_create_state(session_id: str) -> GameState:
    """Get or create game state for session."""
    if session_id not in game_states:
        game_states[session_id] = GameState()
    return game_states[session_id]


def transcribe_audio(audio_path: str) -> str:
    """Transcribe audio using OpenAI Whisper."""
    try:
        with open(audio_path, "rb") as audio_file:
            transcript = openai_client.audio.transcriptions.create(
                model="whisper-1", file=audio_file
            )
        return transcript.text
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        return ""


def enhance_text_for_speech(text: str, speaker_type: str = "game_master") -> str:
    """Enhance text with emotional tags and emphasis for more engaging speech.
    
    Adds emotional tags and uses capitalization for emphasis to make TTS more engaging.
    
    Args:
        text: Original text
        speaker_type: "game_master" or "suspect" to adjust enhancement style
    """
    enhanced = text
    
    # Add emotional context based on content
    text_lower = text.lower()
    
    # Detect excitement/exclamation
    if any(word in text_lower for word in ['amazing', 'incredible', 'wow', 'fantastic', 'unbelievable', 'remarkable']):
        enhanced = f"[excited] {enhanced}"
    elif '?' in text:
        # Questions can be more curious
        enhanced = f"[curiously] {enhanced}"
    elif any(word in text_lower for word in ['suspicious', 'strange', 'odd', 'mysterious', 'enigmatic']):
        enhanced = f"[mysteriously] {enhanced}"
    elif any(word in text_lower for word in ['important', 'crucial', 'key', 'vital', 'critical']):
        enhanced = f"[emphatically] {enhanced}"
    elif any(word in text_lower for word in ['terrible', 'horrible', 'shocking', 'disturbing']):
        enhanced = f"[dramatically] {enhanced}"
    elif speaker_type == "game_master" and any(word in text_lower for word in ['welcome', 'arrive', 'begin', 'start']):
        enhanced = f"[warmly] {enhanced}"
    
    # Enhance exclamation marks - capitalize words before them for emphasis
    # Find sentences ending with ! and capitalize key words
    sentences = enhanced.split('. ')
    enhanced_sentences = []
    for sentence in sentences:
        if '!' in sentence:
            # Capitalize important words before exclamation
            words = sentence.split()
            for i, word in enumerate(words):
                if word.endswith('!') and i > 0:
                    # Capitalize the word before the exclamation
                    words[i-1] = words[i-1].upper()
            sentence = ' '.join(words)
        enhanced_sentences.append(sentence)
    enhanced = '. '.join(enhanced_sentences)
    
    # Capitalize key dramatic words for emphasis
    dramatic_words = ['suddenly', 'immediately', 'finally', 'quickly', 'carefully', 'silently', 'slowly', 'quietly']
    for word in dramatic_words:
        pattern = r'\b' + re.escape(word) + r'\b'
        enhanced = re.sub(pattern, word.upper(), enhanced, flags=re.IGNORECASE)
    
    return enhanced


def text_to_speech(text: str, voice_id: str = None, speaker_name: str = None) -> Optional[str]:
    """Generate speech from text with enhanced settings for more engaging delivery.
    
    Args:
        text: Text to convert to speech
        voice_id: ElevenLabs voice ID (defaults to Game Master voice)
        speaker_name: Name of speaker (for determining enhancement style)
    """
    if not elevenlabs_client or not text.strip():
        return None

    try:
        voice_id = voice_id or GAME_MASTER_VOICE_ID
        
        # Enhance text with emotional tags and emphasis
        speaker_type = "suspect" if speaker_name and speaker_name != "Game Master" else "game_master"
        enhanced_text = enhance_text_for_speech(text, speaker_type=speaker_type)
        
        # Use voice_settings for more engaging speech
        # Stability: 0.45-0.50 for more emotional range (lower = more variation)
        # Style: 0.3-0.5 for more expressive delivery (higher = more exaggerated)
        # Note: Speed is not directly available in the SDK, but style and stability help with energy
        
        # Try with voice_settings first (if SDK supports it)
        try:
            audio_stream = elevenlabs_client.text_to_speech.convert(
                voice_id=voice_id,
                text=enhanced_text,
                model_id="eleven_multilingual_v2",
                output_format="mp3_44100_128",
                voice_settings={
                    "stability": 0.48,  # Lower for more emotional range
                    "similarity_boost": 0.75,
                    "style": 0.4,  # Style exaggeration for more expressive delivery
                    "use_speaker_boost": True,
                },
            )
        except TypeError:
            # SDK might not support voice_settings parameter, try without it
            # The enhanced text with emotional tags should still help
            audio_stream = elevenlabs_client.text_to_speech.convert(
                voice_id=voice_id,
                text=enhanced_text,
                model_id="eleven_multilingual_v2",
                output_format="mp3_44100_128",
            )

        audio_bytes = b"".join(chunk for chunk in audio_stream if chunk)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
            f.write(audio_bytes)
            return f.name
    except Exception as e:
        logger.error(f"TTS error: {e}")
        # Fallback: try without voice_settings if the API doesn't support it
        try:
            audio_stream = elevenlabs_client.text_to_speech.convert(
                voice_id=voice_id,
                text=enhanced_text,
                model_id="eleven_multilingual_v2",
                output_format="mp3_44100_128",
            )
            audio_bytes = b"".join(chunk for chunk in audio_stream if chunk)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
                f.write(audio_bytes)
                return f.name
        except Exception as e2:
            logger.error(f"TTS fallback error: {e2}")
            return None


def get_suspect_voice_id(suspect_name: str, state: GameState) -> Optional[str]:
    """Get voice ID for a suspect."""
    if not state.mystery:
        return None
    for suspect in state.mystery.suspects:
        if suspect.name == suspect_name:
            return suspect.voice_id
    return None


def format_victim_scene_html(mystery) -> str:
    """Format victim and scene information as HTML."""
    if not mystery:
        return "<em>Start a game to see case details...</em>"
    
    return f"""
    <div style="margin-bottom: 12px;">
        <div style="font-weight: 600; color: var(--accent-blue); margin-bottom: 8px;">Victim:</div>
        <div style="color: var(--text-primary); margin-bottom: 12px;">{mystery.victim.name}</div>
        <div style="font-weight: 600; color: var(--accent-blue); margin-bottom: 8px;">Scene:</div>
        <div style="color: var(--text-primary);">{mystery.setting}</div>
    </div>
    """


def format_clues_html(clues: List[str]) -> str:
    """Format found clues as HTML."""
    if not clues:
        return "<em>No clues discovered yet...</em>"

    return "".join(f'<div class="clue-item">• {clue}</div>' for clue in clues)


def format_suspects_list_html(mystery, talked_to: List[str] = None) -> str:
    """Format suspects list as HTML for quick reference."""
    if not mystery:
        return "<em>Start a game to see suspects</em>"
    
    talked_to = talked_to or []
    html_parts = []
    
    for suspect in mystery.suspects:
        talked_class = "location-item searched" if suspect.name in talked_to else "location-item"
        check = " ✓" if suspect.name in talked_to else ""
        html_parts.append(
            f'<div class="{talked_class}">'
            f'<strong>{suspect.name}</strong> - {suspect.role}{check}<br>'
            f'<em style="font-size: 0.9em; color: var(--text-secondary);">Motive: {suspect.secret}</em>'
            f'</div>'
        )
    
    return "".join(html_parts)


def format_locations_html(mystery, searched: List[str]) -> str:
    """Format locations as HTML."""
    if not mystery:
        return "<em>Start a game to see locations</em>"

    locations = list(set(clue.location for clue in mystery.clues))
    html_parts = []

    for loc in locations:
        cls = "location-item searched" if loc in searched else "location-item"
        check = " ✓" if loc in searched else ""
        html_parts.append(f'<div class="{cls}">{loc}{check}</div>')

    return "".join(html_parts)


# ============================================================================
# GAME LOGIC
# ============================================================================


def start_new_game(session_id: str):
    """Start a new mystery game with parallelized image generation."""
    state = get_or_create_state(session_id)
    state.reset_game()

    # Generate mystery
    logger.info("Generating new mystery...")
    mystery = generate_mystery()
    state.mystery = mystery
    state.system_prompt = prepare_game_prompt(mystery)

    # Start image generation and agent/narration in parallel
    logger.info("Starting parallel initialization...")
    
    with ThreadPoolExecutor(max_workers=3) as executor:
        # Submit image generation (takes longest)
        images_future = executor.submit(generate_all_mystery_images, mystery)
        
        # While images generate, create agent and get narration
        agent = create_game_master_agent()
        response, speaker = process_message(
            agent,
            "The player has just arrived. Welcome them to the mystery with atmosphere.",
            state.system_prompt,
            session_id,
            thread_id=session_id,
        )
        
        # Wait for images to complete
        images = images_future.result()
        mystery_images[session_id] = images
        
        # Store portrait paths on suspects
        for suspect in mystery.suspects:
            if suspect.name in images:
                suspect.portrait_path = images[suspect.name]
        
        # Generate audio (needs the response text)
        audio_path = text_to_speech(response, GAME_MASTER_VOICE_ID, speaker_name="Game Master")

    # Store in messages
    state.messages.append(
        {"role": "assistant", "content": response, "speaker": "Game Master"}
    )

    return state, response, audio_path, "Game Master"


def process_player_action(
    action_type: str, target: str, custom_message: str, session_id: str
) -> Tuple[str, Optional[str], str, GameState]:
    """Process a player action and return response.

    Args:
        action_type: "talk", "search", "accuse", or "custom"
        target: Suspect name, location, or None
        custom_message: Free-form message if action_type is "custom"
        session_id: Session identifier

    Returns:
        Tuple of (response_text, audio_path, speaker_name, state)
    """
    state = get_or_create_state(session_id)

    if not state.mystery:
        return "Please start a new game first.", None, "Game Master", state

    # Build the message based on action type
    if action_type == "talk" and target:
        message = f"I want to talk to {target}. Hello, {target}."
    elif action_type == "search" and target:
        message = f"I want to search {target}."
    elif action_type == "accuse" and target:
        message = f"I accuse {target} of the murder!"
    elif action_type == "custom" and custom_message:
        message = custom_message
    else:
        return "I didn't understand that action.", None, "Game Master", state

    # Store player message
    state.messages.append({"role": "user", "content": message, "speaker": "You"})

    # Get or create agent
    if not hasattr(process_player_action, "agent"):
        process_player_action.agent = create_game_master_agent()

    # Update system prompt
    state.system_prompt = state.get_continue_prompt()

    # Process with agent
    response, speaker = process_message(
        process_player_action.agent,
        message,
        state.system_prompt,
        session_id,
        thread_id=session_id,
    )

    # Parse game actions
    actions = parse_game_actions(message, response, state)

    # Determine voice
    voice_id = None
    if speaker and speaker != "Game Master":
        voice_id = get_suspect_voice_id(speaker, state)
    voice_id = voice_id or GAME_MASTER_VOICE_ID

    # Extract audio path marker if present (from interrogate_suspect tool)
    # Format: [AUDIO:/path/to/file.mp3]text response
    audio_path_from_tool = None
    clean_response = response
    audio_marker_pattern = r'\[AUDIO:([^\]]+)\]'
    match = re.search(audio_marker_pattern, response)
    if match:
        audio_path_from_tool = match.group(1)
        # Remove the audio marker from the text
        clean_response = re.sub(audio_marker_pattern, '', response).strip()
        logger.info(f"Extracted audio path from tool: {audio_path_from_tool}")

    # Generate audio
    tts_text = clean_response.replace("**", "").replace("*", "")
    speaker = speaker or "Game Master"
    audio_path = audio_path_from_tool or text_to_speech(tts_text, voice_id, speaker_name=speaker)

    # Store response (without audio marker)
    state.messages.append(
        {"role": "assistant", "content": clean_response, "speaker": speaker or "Game Master"}
    )

    return clean_response, audio_path, speaker or "Game Master", state


# ============================================================================
# GRADIO UI
# ============================================================================


def create_app():
    """Create the Gradio application."""

    with gr.Blocks(title="Murder Mystery") as app:

        # Inject CSS via HTML component (works across Gradio versions)
        gr.HTML(f"<style>{RETRO_CSS}</style>")

        # Session state
        session_id = gr.State(lambda: str(uuid.uuid4()))

        # ====== TITLE BAR ======
        with gr.Row(elem_classes="title-bar"):
            gr.HTML('<div class="game-title">🔍 MURDER MYSTERY</div>')

        # ====== MAIN LAYOUT ======
        with gr.Row():

            # === LEFT: SIDE PANEL ===
            with gr.Column(scale=1, min_width=200):
                # Victim and Scene - first card
                with gr.Group(elem_classes="side-panel"):
                    gr.HTML('<div class="panel-title">🔍 Case Details</div>')
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

                # Accusations remaining
                accusations_html = gr.HTML(
                    '<div class="accusations-display">Accusations: <span class="accusations-pip"></span><span class="accusations-pip"></span><span class="accusations-pip"></span></div>'
                )

            # === CENTER: MAIN STAGE ===
            with gr.Column(scale=3):

                # Stage container
                with gr.Group(elem_classes="stage-container"):

                    # Portrait display - larger size for better visibility
                    portrait_image = gr.Image(
                        value=None,
                        show_label=False,
                        elem_classes="portrait-image",
                        height=500,
                        width=500,
                        visible=True,  # Visible by default, will show image when set
                    )

                    # Speaker name
                    speaker_html = gr.HTML(
                        '<div class="speaker-name">Game Master</div>'
                    )

                    # Caption display
                    caption_html = gr.HTML(
                        '<div class="caption-display"><div class="splash-screen"><div class="splash-title">MURDER MYSTERY</div><div class="splash-subtitle">A Voice-First Adventure</div></div></div>'
                    )

                    # Audio player (hidden controls, auto-play)
                    audio_output = gr.Audio(
                        label=None,
                        show_label=False,
                        autoplay=True,
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
                        label="🎤 Voice",
                        scale=1,
                    )
                    text_input = gr.Textbox(
                        placeholder="Type your question or action...",
                        show_label=False,
                        elem_classes="text-input",
                        scale=3,
                    )
                    send_btn = gr.Button("📤", elem_classes="action-button", scale=0)

        # ====== STATUS BAR ======
        with gr.Row(elem_classes="status-bar"):
            status_text = gr.HTML(
                '<span style="color: var(--text-secondary);">Press START to begin your investigation...</span>'
            )

        # ====== EVENT HANDLERS ======

        def on_start_game(sess_id):
            """Handle game start."""
            state, response, audio_path, speaker = start_new_game(sess_id)

            # Get images - retrieve after start_new_game has stored them
            images = mystery_images.get(sess_id, {})
            
            # Debug logging
            logger.info(f"Retrieving images for session {sess_id}")
            logger.info(f"Available image keys: {list(images.keys())}")
            logger.info(f"All mystery_images keys: {list(mystery_images.keys())}")
            
            # Build portrait for game master (use title image if available)
            portrait = images.get("_title", None)
            logger.info(f"Portrait path: {portrait}")
            
            if portrait:
                # Ensure path is absolute and file exists
                if not os.path.isabs(portrait):
                    # If relative, make it absolute
                    portrait = os.path.abspath(portrait)
                
                if not os.path.exists(portrait):
                    logger.warning(f"Portrait image file does not exist: {portrait}")
                    portrait = None
                else:
                    logger.info(f"Portrait image file exists: {portrait}")
            else:
                logger.warning("No _title image found in images dict")

            return [
                # Caption
                f'<div class="caption-display">{response}</div>',
                # Speaker
                f'<div class="speaker-name">{speaker}</div>',
                # Audio
                audio_path,
                # Portrait - return path directly
                portrait,
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
                # Status
                f'<span style="color: var(--accent-blue);">Case: The Murder of {state.mystery.victim.name}</span>',
            ]

        def _format_accusations_html(wrong: int):
            pips = ""
            for i in range(3):
                cls = "accusations-pip used" if i < wrong else "accusations-pip"
                pips += f'<span class="{cls}"></span>'
            return f'<div class="accusations-display">Accusations: {pips}</div>'

        def on_talk_to_suspect(suspect_idx: int, sess_id: str):
            """Handle clicking on a suspect."""
            state = get_or_create_state(sess_id)
            if not state.mystery or suspect_idx >= len(state.mystery.suspects):
                return [gr.update()] * 8

            suspect = state.mystery.suspects[suspect_idx]
            response, audio_path, speaker, state = process_player_action(
                "talk", suspect.name, "", sess_id
            )

            # Get portrait
            images = mystery_images.get(sess_id, {})
            portrait = images.get(suspect.name, images.get("_title", None))

            return [
                f'<div class="caption-display">{response}</div>',
                f'<div class="speaker-name">{speaker}</div>',
                audio_path,
                gr.update(value=portrait, visible=bool(portrait)),
                format_victim_scene_html(state.mystery),
                format_suspects_list_html(state.mystery, state.suspects_talked_to),
                format_locations_html(state.mystery, state.searched_locations),
                format_clues_html(state.clues_found),
                _format_accusations_html(state.wrong_accusations),
            ]

        def on_search(location: str, sess_id: str):
            """Handle location search."""
            if not location:
                return [gr.update()] * 9

            response, audio_path, speaker, state = process_player_action(
                "search", location, "", sess_id
            )

            images = mystery_images.get(sess_id, {})
            portrait = images.get(location, images.get("_title", None))

            return [
                f'<div class="caption-display">{response}</div>',
                f'<div class="speaker-name">{speaker}</div>',
                audio_path,
                gr.update(value=portrait, visible=bool(portrait)),
                format_victim_scene_html(state.mystery),
                format_suspects_list_html(state.mystery, state.suspects_talked_to),
                format_locations_html(state.mystery, state.searched_locations),
                format_clues_html(state.clues_found),
                _format_accusations_html(state.wrong_accusations),
            ]

        def on_accuse(suspect_name: str, sess_id: str):
            """Handle accusation."""
            if not suspect_name:
                return [gr.update()] * 9

            response, audio_path, speaker, state = process_player_action(
                "accuse", suspect_name, "", sess_id
            )

            images = mystery_images.get(sess_id, {})
            portrait = images.get("_title", None)

            return [
                f'<div class="caption-display">{response}</div>',
                f'<div class="speaker-name">{speaker}</div>',
                audio_path,
                gr.update(value=portrait, visible=bool(portrait)),
                format_victim_scene_html(state.mystery),
                format_suspects_list_html(state.mystery, state.suspects_talked_to),
                format_locations_html(state.mystery, state.searched_locations),
                format_clues_html(state.clues_found),
                _format_accusations_html(state.wrong_accusations),
            ]

        def on_custom_message(message: str, sess_id: str):
            """Handle free-form text input."""
            if not message.strip():
                return [gr.update()] * 9

            response, audio_path, speaker, state = process_player_action(
                "custom", "", message, sess_id
            )

            images = mystery_images.get(sess_id, {})

            # Determine portrait based on speaker
            portrait = None
            if speaker and speaker != "Game Master":
                portrait = images.get(speaker, None)
            if not portrait:
                portrait = images.get("_title", None)

            return [
                f'<div class="caption-display">{response}</div>',
                f'<div class="speaker-name">{speaker}</div>',
                audio_path,
                gr.update(value=portrait, visible=bool(portrait)),
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
                return [gr.update()] * 9

            # Transcribe
            text = transcribe_audio(audio_path)
            if not text.strip():
                return [gr.update()] * 9

            response, audio_resp, speaker, state = process_player_action(
                "custom", "", text, sess_id
            )

            images = mystery_images.get(sess_id, {})
            portrait = None
            if speaker and speaker != "Game Master":
                portrait = images.get(speaker, None)
            if not portrait:
                portrait = images.get("_title", None)

            return [
                f'<div class="caption-display">{response}</div>',
                f'<div class="speaker-name">{speaker}</div>',
                audio_resp,
                gr.update(value=portrait, visible=bool(portrait)),
                format_victim_scene_html(state.mystery),
                format_suspects_list_html(state.mystery, state.suspects_talked_to),
                format_locations_html(state.mystery, state.searched_locations),
                format_clues_html(state.clues_found),
                _format_accusations_html(state.wrong_accusations),
            ]

        # ====== WIRE UP EVENTS ======

        # Common outputs for game actions
        game_outputs = [
            caption_html,
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
                caption_html,
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
                status_text,
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
