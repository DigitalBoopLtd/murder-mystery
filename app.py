"""Main Gradio application with info cards."""

import os
import logging
import gradio as gr
from dotenv import load_dotenv
from game_parser import parse_game_actions
from mystery_generator import generate_mystery, prepare_game_prompt
from game_state import GameState
from agent import create_game_master_agent, process_message
from ui_components import get_all_card_content


# Load environment variables
load_dotenv()

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


def chat_fn(message: str, history: list, session_id: str):
    """Handle chat messages.

    Args:
        message: User's message
        history: List of message dicts in format [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
        session_id: Session identifier

    Returns:
        Tuple of (updated_history, status_card, suspects_card, objective_card, locations_card, clues_card, logs)
    """
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
            return history, *get_card_updates(state), logs

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
                return error_history, *get_card_updates(state), logs
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

            # Format response with speaker name
            if speaker_name:
                formatted_response = f"**{speaker_name}:** {response}"
            else:
                formatted_response = f"**Game Master:** {response}"

            # Update history in Gradio 6 format
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": formatted_response})

            # Update game state messages (store original response without formatting)
            state.messages.append({"role": "user", "content": message})
            state.messages.append({"role": "assistant", "content": response})

            # Parse response to auto-update game state
            # This detects: suspects talked to, locations searched, clues found, accusations
            actions = parse_game_actions(message, response, state)

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
    finally:
        # Remove handler after processing
        root_logger.removeHandler(ui_handler)

    logs = get_ui_logs(session_id)
    return history, *get_card_updates(state), logs


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
                    *get_card_updates(state),
                    logs,
                    True,  # game_started
                    gr.update(visible=False),  # start_btn
                    gr.update(visible=True),  # msg
                    gr.update(visible=True),  # submit_btn
                )

            # Start a new game
            result = chat_fn("start", history, session)
            # Return result + visibility updates (hide start button, show input)
            return (
                *result,
                True,  # game_started
                gr.update(visible=False),  # start_btn
                gr.update(visible=True),  # msg
                gr.update(visible=True),  # submit_btn
            )

        def respond(message, history, session, started):
            """Handle user message and generate response."""
            if not message.strip():
                state = get_or_create_game_state(session)
                logs = get_ui_logs(session)
                return (
                    history,
                    *get_card_updates(state),
                    logs,
                    started,  # game_started
                    gr.update(visible=False),  # start_btn
                    gr.update(visible=True),  # msg
                    gr.update(visible=True),  # submit_btn
                )

            # Get updated history and cards from chat function
            result = chat_fn(message, history, session)
            # Check if this was a new game request
            state = get_or_create_game_state(session)
            is_new_game = state.mystery is not None and started == False
            new_started = started or is_new_game

            return (
                *result,
                new_started,  # game_started
                gr.update(visible=False),  # start_btn
                gr.update(visible=True),  # msg
                gr.update(visible=True),  # submit_btn
            )

        # Wire up the start button
        getattr(start_btn, "click")(
            start_game,
            [chatbot, session_id, game_started],
            [
                chatbot,
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
            ],
        )

        # Wire up the message input and send button
        getattr(msg, "submit")(
            respond,
            [msg, chatbot, session_id, game_started],
            [
                chatbot,
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
            ],
        ).then(lambda: "", None, msg)

        getattr(submit_btn, "click")(
            respond,
            [msg, chatbot, session_id, game_started],
            [
                chatbot,
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
            ],
        ).then(lambda: "", None, msg)

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
