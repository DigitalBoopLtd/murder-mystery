"""Main Gradio application with info cards."""

import os
import logging
import re
import tempfile
import wave
from typing import Optional
import gradio as gr
from dotenv import load_dotenv
from openai import OpenAI
try:
    from elevenlabs import ElevenLabs
    ELEVENLABS_AVAILABLE = True
except ImportError:
    # Fallback if elevenlabs not installed yet
    ELEVENLABS_AVAILABLE = False
    ElevenLabs = None
from game_parser import parse_game_actions
from mystery_generator import generate_mystery, prepare_game_prompt
from game_state import GameState
from agent import create_game_master_agent, process_message
from ui_components import get_all_card_content


# Load environment variables
load_dotenv()

# Initialize OpenAI client
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Initialize ElevenLabs client
elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY")
elevenlabs_client = None
if elevenlabs_api_key and ELEVENLABS_AVAILABLE:
    try:
        elevenlabs_client = ElevenLabs(api_key=elevenlabs_api_key)
    except Exception as e:
        # Logger not yet initialized, use print for early errors
        print(f"Warning: Failed to initialize ElevenLabs client: {e}")

# Voice mapping for different characters
# You can customize these voice IDs based on your ElevenLabs account
VOICE_MAP = {
    "game_master": "JBFqnCBsd6RMkjVDRZzb",  # Default voice, replace with your preferred Game Master voice ID
    "default": "JBFqnCBsd6RMkjVDRZzb",  # Default for unknown speakers
    # Add suspect-specific voices here if desired
    # "Zara Orion": "voice_id_here",
    # "Max Stellar": "voice_id_here",
}

# Set up logging
logger = logging.getLogger(__name__)

# Global state storage (in production, use a proper database)
game_states: dict[str, GameState] = {}

# Global log storage for UI display
ui_logs: dict[str, list] = {}


class UILogHandler(logging.Handler):
    """Custom logging handler that stores logs for UI display."""

    def __init__(self, session_id: str):
        super().__init__()
        self.session_id = session_id
        self.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%H:%M:%S",
            )
        )

    def emit(self, record):
        """Store log record for UI display."""
        if self.session_id not in ui_logs:
            ui_logs[self.session_id] = []

        log_entry = self.format(record)
        ui_logs[self.session_id].append(log_entry)

        # Keep only last 100 log entries per session
        if len(ui_logs[self.session_id]) > 100:
            ui_logs[self.session_id] = ui_logs[self.session_id][-100:]


def get_ui_logs(session_id: str) -> str:
    """Get formatted logs for a session."""
    if session_id not in ui_logs:
        return "No logs yet..."
    return "\n".join(ui_logs.get(session_id, []))


def transcribe_audio(audio_file_path: str) -> str:
    """Transcribe audio to text using OpenAI Whisper.
    
    Args:
        audio_file_path: Path to the audio file
        
    Returns:
        Transcribed text
    """
    try:
        with open(audio_file_path, "rb") as audio_file:
            transcript = openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
            return transcript.text
    except Exception as e:
        logger.error(f"Error transcribing audio: {str(e)}", exc_info=True)
        return ""


def validate_audio_file(audio_path: Optional[str]) -> Optional[str]:
    """Validate that an audio file exists and is readable.
    
    Args:
        audio_path: Path to audio file
        
    Returns:
        Valid audio path or None if invalid
    """
    if not audio_path:
        return None
    
    if not os.path.exists(audio_path):
        logger.warning(f"Audio file does not exist: {audio_path}")
        return None
    
    try:
        # Try to read the file to ensure it's valid
        with open(audio_path, 'rb') as f:
            header = f.read(4)
            if len(header) < 4:
                logger.warning(f"Audio file is too small or empty: {audio_path}")
                return None
        return audio_path
    except (IOError, OSError) as e:
        logger.warning(f"Audio file is not readable: {audio_path}, error: {e}")
        return None


def text_to_speech(text: str, speaker_name: str = None, voice_id: str = None) -> str:
    """Convert text to speech using ElevenLabs client API.
    
    Args:
        text: Text to convert to speech
        speaker_name: Name of the speaker (Game Master, suspect name, etc.)
                     Used to select appropriate voice if voice_id not provided
        voice_id: Optional specific voice ID to use (from suspect assignment)
        
    Returns:
        Path to the generated audio file
    """
    if not elevenlabs_client:
        logger.warning("ElevenLabs client not available, skipping TTS")
        return None
    
    if not text or not text.strip():
        return None
        
    try:
        # Use provided voice_id, or fall back to VOICE_MAP
        if not voice_id:
            voice_id = VOICE_MAP.get("default")
            if speaker_name:
                # Check if there's a specific voice for this speaker
                voice_id = VOICE_MAP.get(speaker_name, VOICE_MAP.get("game_master", VOICE_MAP.get("default")))
            else:
                # Default to game master voice
                voice_id = VOICE_MAP.get("game_master", VOICE_MAP.get("default"))
        
        logger.info(f"Generating TTS for '{speaker_name or 'Game Master'}' using voice: {voice_id}")
        
        # Generate audio using ElevenLabs client
        audio_stream = elevenlabs_client.text_to_speech.convert(
            voice_id=voice_id,
            text=text,
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128"
        )
        
        # Collect all audio chunks
        audio_bytes = b""
        for chunk in audio_stream:
            if chunk:
                audio_bytes += chunk
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
            tmp_file.write(audio_bytes)
            return tmp_file.name
    except Exception as e:
        logger.error(f"Error generating speech: {str(e)}", exc_info=True)
        return None


def format_friendly_error(error: Exception) -> str:
    """Convert technical error messages to user-friendly ones.

    Returns a tuple of (friendly_message, raw_error_string)
    """
    error_str = str(error)
    error_type = type(error).__name__

    # Friendly error messages based on error type and content
    friendly_messages = {
        "OUTPUT_PARSING_FAILURE": "I'm having trouble generating a new mystery. The AI returned an unexpected format. Please try starting a new game again.",
        "Invalid json output": "I'm having trouble generating a new mystery. The AI returned an unexpected format. Please try starting a new game again.",
        "Error generating mystery": "I'm having trouble generating a new mystery. Please try starting a new game again.",
        "Error processing message": "I'm having trouble processing your message. Please try rephrasing your question or try again.",
        "ConnectionError": "I'm having trouble connecting to the AI service. Please check your internet connection and try again.",
        "TimeoutError": "The request took too long to process. Please try again.",
        "APIError": "There was an issue with the AI service. Please try again in a moment.",
    }

    # Check for specific error patterns
    friendly_msg = None
    for pattern, message in friendly_messages.items():
        if (
            pattern.lower() in error_str.lower()
            or pattern.lower() in error_type.lower()
        ):
            friendly_msg = message
            break

    # Default friendly message if no pattern matches
    if not friendly_msg:
        if "mystery" in error_str.lower() or "generate" in error_str.lower():
            friendly_msg = "I'm having trouble generating a new mystery. Please try starting a new game again."
        elif "process" in error_str.lower() or "message" in error_str.lower():
            friendly_msg = "I'm having trouble processing your message. Please try rephrasing your question or try again."
        else:
            friendly_msg = "Something went wrong. Please try again. If the problem persists, check the debug logs for details."

    # Format the response with both friendly message and raw error
    # Use markdown format that works well in Gradio
    return f"""{friendly_msg}

---

**Technical Details:**

*Error Type:* `{error_type}`

*Error Message:*
```
{error_str[:500]}{'...' if len(error_str) > 500 else ''}
```

*Full error details are available in the Debug Logs section below.*"""


def get_or_create_game_state(session_id: str) -> GameState:
    """Get or create a game state for a session."""
    if session_id not in game_states:
        game_states[session_id] = GameState()
    return game_states[session_id]


def get_card_updates(state: GameState) -> tuple:
    """Get all card content updates from game state.

    Returns:
        Tuple of (status, suspects, objective, locations, clues) markdown strings
    """
    cards = get_all_card_content(
        mystery=state.mystery,
        wrong_accusations=state.wrong_accusations,
        clues_found=state.clues_found,
        searched_locations=state.searched_locations,
        game_over=state.game_over,
        won=state.won,
    )
    return (
        cards["status"],
        cards["suspects"],
        cards["objective"],
        cards["locations"],
        cards["clues"],
    )


def process_voice_input(audio, history: list, session_id: str):
    """Process voice input: transcribe, get response, convert to speech.
    
    Args:
        audio: Audio input from Gradio (can be tuple or file path)
        history: Chat history
        session_id: Session identifier
        
    Returns:
        Tuple of (updated_history, audio_response_path, status_card, suspects_card, objective_card, locations_card, clues_card, logs)
    """
    if audio is None:
        state = get_or_create_game_state(session_id)
        logs = get_ui_logs(session_id)
        return history, None, *get_card_updates(state), logs
    
    # Extract audio file path from Gradio audio input
    # In Gradio 5+, audio can be a tuple (sample_rate, audio_data) or a file path string
    audio_path = None
    if isinstance(audio, tuple):
        # Convert numpy array to WAV file
        import numpy as np
        sample_rate, audio_data = audio
        tmp_file_path = tempfile.mktemp(suffix=".wav")
        # Note: 'wb' mode returns Wave_write which has setnchannels/setsampwidth/setframerate
        # The linter incorrectly infers Wave_read, but the code is correct
        wav_file = wave.open(tmp_file_path, 'wb')  # type: ignore[assignment]
        try:
            wav_file.setnchannels(1)  # type: ignore[attr-defined]  # Mono
            wav_file.setsampwidth(2)  # type: ignore[attr-defined]  # 16-bit
            wav_file.setframerate(sample_rate)  # type: ignore[attr-defined]
            # Convert float array to int16
            audio_int16 = (audio_data * 32767).astype(np.int16)
            wav_file.writeframes(audio_int16.tobytes())  # type: ignore[attr-defined]
        finally:
            wav_file.close()
        audio_path = tmp_file_path
    elif isinstance(audio, str):
        # It's already a file path
        audio_path = audio
    else:
        logger.error(f"Unexpected audio format: {type(audio)}")
        state = get_or_create_game_state(session_id)
        logs = get_ui_logs(session_id)
        return history, None, *get_card_updates(state), logs
    
    # Transcribe audio
    transcription = transcribe_audio(audio_path)
    
    if not transcription.strip():
        logger.warning("Empty transcription from audio")
        state = get_or_create_game_state(session_id)
        logs = get_ui_logs(session_id)
        return history, None, *get_card_updates(state), logs
    
    logger.info(f"Transcribed voice input: {transcription}")
    
    # Process the transcribed message through the chat function
    # chat_fn now returns: (history, audio_response_path, status_card, suspects_card, objective_card, locations_card, clues_card, logs)
    result = chat_fn(transcription, history, session_id)
    
    # Return all results (audio is already included from chat_fn)
    return result


def chat_fn(message: str, history: list, session_id: str):
    """Handle chat messages.

    Args:
        message: User's message
        history: List of message dicts in format [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
        session_id: Session identifier

    Returns:
        Tuple of (updated_history, audio_response_path, status_card, suspects_card, objective_card, locations_card, clues_card, logs)
    """
    audio_response_path = None
    # Set up UI logging handler for this session
    ui_handler = UILogHandler(session_id)
    ui_handler.setLevel(logging.INFO)

    # Get root logger and add handler
    root_logger = logging.getLogger()
    root_logger.addHandler(ui_handler)
    root_logger.setLevel(logging.INFO)

    try:
        if not message.strip():
            state = get_or_create_game_state(session_id)
            logs = get_ui_logs(session_id)
            return history, audio_response_path, *get_card_updates(state), logs

        state = get_or_create_game_state(session_id)

        # Check if this is a new game request
        if state.is_new_game(message) or state.mystery is None:
            # Generate new mystery
            try:
                mystery = generate_mystery()
                state.reset_game()  # Reset all state
                state.mystery = mystery
                state.system_prompt = prepare_game_prompt(mystery)
                # Cards will be updated after agent processes the message
            except Exception as e:
                # Log the raw error
                logger.error(f"Error generating mystery: {str(e)}", exc_info=True)
                # Return friendly error with card updates
                friendly_error = format_friendly_error(e)
                formatted_error = f"**Game Master:** {friendly_error}"
                error_history = history + [
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": formatted_error},
                ]
                logs = get_ui_logs(session_id)
                return error_history, audio_response_path, *get_card_updates(state), logs
        else:
            # Use continue prompt
            state.system_prompt = state.get_continue_prompt()

        # Create agent if not exists (shared across sessions)
        if not hasattr(chat_fn, "agent_app"):
            chat_fn.agent_app = create_game_master_agent()

        agent_app = chat_fn.agent_app

        # Process the message
        try:
            response, speaker_name = process_message(
                agent_app,
                message,
                state.system_prompt,
                session_id,
                thread_id=session_id,
            )

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
            
            # Format response with speaker name (using cleaned response)
            if speaker_name:
                formatted_response = f"**{speaker_name}:** {clean_response}"
            else:
                formatted_response = f"**Game Master:** {clean_response}"

            # Update history in Gradio 6 format
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": formatted_response})

            # Update game state messages (store cleaned response without formatting)
            state.messages.append({"role": "user", "content": message})
            state.messages.append({"role": "assistant", "content": clean_response})
            
            # Generate audio for the response
            # Use audio from tool if available, otherwise generate new audio
            audio_response_path = None
            if audio_path_from_tool:
                audio_response_path = validate_audio_file(audio_path_from_tool)
                if audio_response_path:
                    logger.info(f"Using validated audio from tool: {audio_response_path}")
                else:
                    logger.warning("Audio file from tool failed validation, generating new audio")
            
            if not audio_response_path:
                # Generate new audio
                # Clean the response text for TTS (remove markdown formatting)
                tts_text = clean_response.replace("**", "").replace("*", "")
                
                # Remove speaker name prefix if present at the START of the text
                if speaker_name:
                    prefix = f"{speaker_name}:"
                    if tts_text.startswith(prefix):
                        tts_text = tts_text[len(prefix):].strip()
                elif tts_text.startswith("Game Master:"):
                    tts_text = tts_text[len("Game Master:"):].strip()
                
                # Look up voice_id from suspect if this is a suspect speaking
                voice_id = None
                if speaker_name and state.mystery:
                    for suspect in state.mystery.suspects:
                        if suspect.name == speaker_name and suspect.voice_id:
                            voice_id = suspect.voice_id
                            logger.info(f"Using assigned voice {voice_id} for suspect {speaker_name}")
                            break
                
                audio_response_path = text_to_speech(tts_text, speaker_name or "Game Master", voice_id)
                # Validate the generated audio file
                audio_response_path = validate_audio_file(audio_response_path)

            # Parse response to auto-update game state
            # This detects: suspects talked to, locations searched, clues found, accusations
            # Use clean_response (without audio markers) for parsing
            actions = parse_game_actions(message, clean_response, state)

            if actions:
                if actions.get("suspect_talked_to"):
                    logger.info(
                        f"Updated suspects_talked_to: {state.suspects_talked_to}"
                    )
                if actions.get("location_searched"):
                    logger.info(
                        f"Updated searched_locations: {state.searched_locations}"
                    )
                if actions.get("clues_found"):
                    logger.info(f"Updated clues_found: {state.clues_found}")
                if actions.get("accusation_made"):
                    logger.info(
                        f"Accusation made against: {actions['accusation_made']}, correct: {actions.get('accusation_correct')}"
                    )

        except Exception as e:
            # Log the raw error
            logger.error(f"Error processing message: {str(e)}", exc_info=True)
            # Show friendly error to user
            friendly_error = format_friendly_error(e)
            formatted_error = f"**Game Master:** {friendly_error}"
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": formatted_error})
            # Generate audio for error message too
            clean_error = friendly_error.split("---")[0].strip()  # Just the friendly message
            audio_response_path = text_to_speech(clean_error, "Game Master")
            # Validate the generated audio file
            audio_response_path = validate_audio_file(audio_response_path)
    finally:
        # Remove handler after processing
        root_logger.removeHandler(ui_handler)

    logs = get_ui_logs(session_id)
    # Return history, audio_response, and card updates
    return history, audio_response_path, *get_card_updates(state), logs


def create_interface():
    """Create the Gradio interface with info cards."""

    # Custom CSS for better card styling
    custom_css = """
    .info-card {
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 12px;
        background: #fafafa;
        height: 100%;
    }
    .info-card h3 {
        margin-top: 0;
        color: #333;
    }
    .game-chat {
        min-height: 500px;
    }
    .logs-display {
        font-family: monospace;
        font-size: 11px;
    }
    """

    with gr.Blocks(title="Murder Mystery Game") as demo:
        # Inject CSS using gr.HTML
        gr.HTML(f"<style>{custom_css}</style>")

        gr.Markdown(
            """
            # 🕵️ Murder Mystery Game
            
            Click **"Start New Game"** to begin a new mystery investigation!
            """
        )

        with gr.Row():
            # Left column - Game info cards
            with gr.Column(scale=1):
                status_card = gr.Markdown(
                    value='### 🕵️ Murder Mystery\n\nType **"start"** to begin!',
                    elem_classes=["info-card"],
                )

                suspects_card = gr.Markdown(
                    value="### 🎭 Suspects\n\n*Start a new game to see suspects*",
                    elem_classes=["info-card"],
                )

                objective_card = gr.Markdown(
                    value="### 🎯 Objective\n\n*Start a new game to begin*",
                    elem_classes=["info-card"],
                )

            # Center column - Chat
            with gr.Column(scale=2):
                chatbot = gr.Chatbot(
                    label="Investigation", height=600, elem_classes=["game-chat"]
                )

                # Start button (visible initially)
                start_btn = gr.Button(
                    "🎮 Start New Game",
                    variant="primary",
                    size="lg",
                    visible=True,
                )

                # Message input and send button (hidden initially)
                with gr.Row():
                    msg = gr.Textbox(
                        label="Your Action",
                        placeholder="What do you want to do? (talk to suspect, search location, make accusation...)",
                        scale=4,
                        container=False,
                        visible=False,
                    )
                    submit_btn = gr.Button(
                        "Send", variant="primary", scale=1, visible=False
                    )
                
                # Voice input and output (hidden initially)
                with gr.Row(visible=False) as voice_row:
                    voice_input = gr.Audio(
                        label="🎤 Speak Your Action",
                        sources=["microphone"],
                        type="filepath",
                        format="wav",
                        scale=1,
                    )
                    voice_output = gr.Audio(
                        label="🔊 Response",
                        type="filepath",
                        scale=1,
                        autoplay=True,  # Auto-play audio when generated
                    )
                    voice_submit_btn = gr.Button(
                        "🎤 Process Voice", variant="secondary", scale=1
                    )

            # Right column - Locations and Clues
            with gr.Column(scale=1):
                locations_card = gr.Markdown(
                    value="### 📍 Locations\n\n*Start a new game to explore*",
                    elem_classes=["info-card"],
                )

                clues_card = gr.Markdown(
                    value="### 🔍 Clues Found\n\n*No clues discovered yet*",
                    elem_classes=["info-card"],
                )

        # Logs section (collapsible)
        with gr.Accordion("🔍 Debug Logs", open=False):
            logs_display = gr.Textbox(
                label="Agent Logs",
                value="No logs yet...",
                lines=15,
                max_lines=20,
                interactive=False,
                elem_classes=["logs-display"],
            )

        # Generate a unique session ID
        session_id = gr.State(value=lambda: f"session_{os.urandom(8).hex()}")
        # Track if game has started
        game_started = gr.State(value=False)

        def start_game(history, session, started):
            """Handle start game button click."""
            if started:
                # Game already started, just return current state
                state = get_or_create_game_state(session)
                logs = get_ui_logs(session)
                return (
                    history,
                    None,  # voice_output
                    *get_card_updates(state),
                    logs,
                    True,  # game_started
                    gr.update(visible=False),  # start_btn
                    gr.update(visible=True),  # msg
                    gr.update(visible=True),  # submit_btn
                    gr.update(visible=True),  # voice_row
                )

            # Start a new game
            result = chat_fn("start", history, session)
            # Return result + visibility updates (hide start button, show input)
            return (
                *result,
                None,  # voice_output
                True,  # game_started
                gr.update(visible=False),  # start_btn
                gr.update(visible=True),  # msg
                gr.update(visible=True),  # submit_btn
                gr.update(visible=True),  # voice_row
            )

        def respond(message, history, session, started):
            """Handle user message and generate response."""
            if not message.strip():
                state = get_or_create_game_state(session)
                logs = get_ui_logs(session)
                return (
                    history,
                    None,  # voice_output
                    *get_card_updates(state),
                    logs,
                    started,  # game_started
                    gr.update(visible=False),  # start_btn
                    gr.update(visible=True),  # msg
                    gr.update(visible=True),  # submit_btn
                    gr.update(visible=True),  # voice_row
                )

            # Get updated history and cards from chat function
            # chat_fn returns: (history, audio_response_path, status_card, suspects_card, objective_card, locations_card, clues_card, logs)
            result = chat_fn(message, history, session)
            # Check if this was a new game request
            state = get_or_create_game_state(session)
            is_new_game = state.mystery is not None and started == False
            new_started = started or is_new_game

            return (
                *result,  # Includes history, audio_response_path, and all cards
                new_started,  # game_started
                gr.update(visible=False),  # start_btn
                gr.update(visible=True),  # msg
                gr.update(visible=True),  # submit_btn
                gr.update(visible=True),  # voice_row
            )
        
        def respond_voice(audio, history, session, started):
            """Handle voice input and generate audio response."""
            if audio is None:
                state = get_or_create_game_state(session)
                logs = get_ui_logs(session)
                return (
                    history,
                    None,  # voice_output
                    *get_card_updates(state),
                    logs,
                    started,  # game_started
                    gr.update(visible=False),  # start_btn
                    gr.update(visible=True),  # msg
                    gr.update(visible=True),  # submit_btn
                    gr.update(visible=True),  # voice_row
                )
            
            # Process voice input
            # process_voice_input returns: (history, audio_response_path, status_card, suspects_card, objective_card, locations_card, clues_card, logs)
            result = process_voice_input(audio, history, session)
            
            state = get_or_create_game_state(session)
            is_new_game = state.mystery is not None and started == False
            new_started = started or is_new_game
            
            return (
                *result,  # Includes history, audio_response_path, and all cards
                new_started,  # game_started
                gr.update(visible=False),  # start_btn
                gr.update(visible=True),  # msg
                gr.update(visible=True),  # submit_btn
                gr.update(visible=True),  # voice_row
            )

        # Wire up the start button
        getattr(start_btn, "click")(
            start_game,
            [chatbot, session_id, game_started],
            [
                chatbot,
                voice_output,
                status_card,
                suspects_card,
                objective_card,
                locations_card,
                clues_card,
                logs_display,
                game_started,
                start_btn,
                msg,
                submit_btn,
                voice_row,
            ],
        )

        # Wire up the message input and send button
        getattr(msg, "submit")(
            respond,
            [msg, chatbot, session_id, game_started],
            [
                chatbot,
                voice_output,
                status_card,
                suspects_card,
                objective_card,
                locations_card,
                clues_card,
                logs_display,
                game_started,
                start_btn,
                msg,
                submit_btn,
                voice_row,
            ],
        ).then(lambda: "", None, msg)

        getattr(submit_btn, "click")(
            respond,
            [msg, chatbot, session_id, game_started],
            [
                chatbot,
                voice_output,
                status_card,
                suspects_card,
                objective_card,
                locations_card,
                clues_card,
                logs_display,
                game_started,
                start_btn,
                msg,
                submit_btn,
                voice_row,
            ],
        ).then(lambda: "", None, msg)
        
        # Wire up the voice input button
        getattr(voice_submit_btn, "click")(
            respond_voice,
            [voice_input, chatbot, session_id, game_started],
            [
                chatbot,
                voice_output,
                status_card,
                suspects_card,
                objective_card,
                locations_card,
                clues_card,
                logs_display,
                game_started,
                start_btn,
                msg,
                submit_btn,
                voice_row,
            ],
        )

        # Instructions accordion
        with gr.Accordion("How to Play", open=False):
            gr.Markdown(
                """
                ### Commands:
                - **Start a new game**: Click the "Start New Game" button
                - **Talk to suspect**: "talk to [name]" or "question [name]" or "ask [name] about..."
                - **Search location**: "search [location]" or "investigate [location]"
                - **Make accusation**: "I accuse [name]" or "The murderer is [name]"
                
                ### Rules:
                - You have **3 wrong accusations** before you lose
                - Win by correctly identifying the murderer **with evidence**
                - Search locations to find clues
                - Interview suspects to gather information
                """
            )

    return demo


if __name__ == "__main__":
    # Verify API key is set
    if not os.getenv("OPENAI_API_KEY"):
        print("Warning: OPENAI_API_KEY not found in environment variables.")
        print("Please create a .env file with your OpenAI API key.")

    demo = create_interface()
    demo.launch(share=False, server_name="0.0.0.0", server_port=7860)