"""Main Gradio application with info cards."""

import os
import logging
import gradio as gr
from dotenv import load_dotenv
from mystery_generator import generate_mystery, prepare_game_prompt
from game_state import GameState
from agent import create_game_master_agent, process_message
from ui_components import get_all_card_content

# Load environment variables
load_dotenv()

# Global state storage (in production, use a proper database)
game_states: dict[str, GameState] = {}

# Global log storage for UI display
ui_logs: dict[str, list] = {}


class UILogHandler(logging.Handler):
    """Custom logging handler that stores logs for UI display."""
    
    def __init__(self, session_id: str):
        super().__init__()
        self.session_id = session_id
        self.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
                                           datefmt='%H:%M:%S'))
    
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
            except Exception as e:
                # Return error with card updates
                error_history = history + [
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": f"Error generating mystery: {str(e)}"},
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
            response = process_message(
                agent_app, message, state.system_prompt, session_id, thread_id=session_id
            )

            # Update history in Gradio 6 format
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": response})

            # Update game state messages
            state.messages.append({"role": "user", "content": message})
            state.messages.append({"role": "assistant", "content": response})

            # TODO: Parse response to auto-update clues_found, searched_locations, suspects_talked_to
            # This would require response parsing or tool callbacks

        except Exception as e:
            error_msg = f"Error processing message: {str(e)}"
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": error_msg})
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
            
            Type **"start"**, **"new game"**, **"begin"**, or **"play"** to begin a new mystery.
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

                with gr.Row():
                    msg = gr.Textbox(
                        label="Your Action",
                        placeholder="What do you want to do? (talk to suspect, search location, make accusation...)",
                        scale=4,
                        container=False,
                    )
                    submit_btn = gr.Button("Send", variant="primary", scale=1)

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

        def respond(message, history, session):
            """Handle user message and generate response."""
            if not message.strip():
                state = get_or_create_game_state(session)
                logs = get_ui_logs(session)
                return history, *get_card_updates(state), logs

            # Get updated history and cards from chat function
            result = chat_fn(message, history, session)
            return result

        # Wire up the interface
        getattr(msg, "submit")(
            respond,
            [msg, chatbot, session_id],
            [
                chatbot,
                status_card,
                suspects_card,
                objective_card,
                locations_card,
                clues_card,
                logs_display,
            ],
        ).then(lambda: "", None, msg)

        getattr(submit_btn, "click")(
            respond,
            [msg, chatbot, session_id],
            [
                chatbot,
                status_card,
                suspects_card,
                objective_card,
                locations_card,
                clues_card,
                logs_display,
            ],
        ).then(lambda: "", None, msg)

        # Instructions accordion
        with gr.Accordion("How to Play", open=False):
            gr.Markdown(
                """
                ### Commands:
                - **Start a new game**: Type "start", "new game", "begin", or "play"
                - **Talk to suspect**: "talk to [name]" or "question [name]"
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
