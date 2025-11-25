"""Main Gradio application."""
import os
import gradio as gr
from dotenv import load_dotenv
from mystery_generator import generate_mystery, prepare_game_prompt
from game_state import GameState
from agent import create_game_master_agent, process_message

# Load environment variables
load_dotenv()

# Global state storage (in production, use a proper database)
game_states: dict[str, GameState] = {}


def get_or_create_game_state(session_id: str) -> GameState:
    """Get or create a game state for a session."""
    if session_id not in game_states:
        game_states[session_id] = GameState()
    return game_states[session_id]


def chat_fn(message: str, history: list, session_id: str):
    """Handle chat messages.
    
    Args:
        message: User's message
        history: List of message dicts in format [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
        session_id: Session identifier
    """
    if not message.strip():
        return history
    
    state = get_or_create_game_state(session_id)
    
    # Check if this is a new game request
    if state.is_new_game(message) or state.mystery is None:
        # Generate new mystery
        try:
            mystery = generate_mystery()
            state.mystery = mystery
            state.system_prompt = prepare_game_prompt(mystery)
            state.messages = []
            state.clues_found = []
            state.suspects_talked_to = []
            state.wrong_accusations = 0
            state.game_over = False
            state.won = False
        except Exception as e:
            # Return in Gradio 6 format
            return history + [
                {"role": "user", "content": message},
                {"role": "assistant", "content": f"Error generating mystery: {str(e)}"}
            ]
    else:
        # Use continue prompt
        state.system_prompt = state.get_continue_prompt()
    
    # Create agent if not exists (shared across sessions)
    if not hasattr(chat_fn, 'agent_app'):
        chat_fn.agent_app = create_game_master_agent()
    
    agent_app = chat_fn.agent_app
    
    # Process the message
    try:
        response = process_message(
            agent_app,
            message,
            state.system_prompt,
            session_id,
            thread_id=session_id
        )
        
        # Update history in Gradio 6 format
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": response})
        
        # Update game state messages
        state.messages.append({"role": "user", "content": message})
        state.messages.append({"role": "assistant", "content": response})
        
    except Exception as e:
        error_msg = f"Error processing message: {str(e)}"
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": error_msg})
    
    return history


def create_interface():
    """Create the Gradio interface."""
    with gr.Blocks(title="Murder Mystery Game") as demo:
        gr.Markdown(
            """
            # 🕵️ Murder Mystery Game
            
            Welcome to the interactive murder mystery game! 
            
            Type **"start"**, **"new game"**, **"begin"**, or **"play"** to begin a new mystery.
            
            Investigate the crime, interrogate suspects, search locations, and solve the case!
            """
        )
        
        chatbot = gr.Chatbot(
            label="Game Chat",
            height=700,
            buttons=["copy"]
        )
        
        with gr.Row():
            msg = gr.Textbox(
                label="Your Message",
                placeholder="Type your message here...",
                scale=4,
                container=False
            )
            submit_btn = gr.Button("Send", variant="primary", scale=1)
        
        # Generate a unique session ID
        session_id = gr.State(value=lambda: f"session_{os.urandom(8).hex()}")
        
        def respond(message, history, session):
            """Handle user message and generate response.
            
            Args:
                message: User's message
                history: List of message dicts in Gradio 6 format
                session: Session ID
            """
            if not message.strip():
                return history
            
            # Convert history from Gradio 6 format if needed (for backward compatibility)
            # Gradio 6 passes history as list of dicts, but we need to ensure it's in the right format
            if history and isinstance(history[0], list):
                # Convert old format [[user, assistant], ...] to new format
                converted_history = []
                for pair in history:
                    if len(pair) == 2:
                        converted_history.append({"role": "user", "content": pair[0]})
                        converted_history.append({"role": "assistant", "content": pair[1]})
                history = converted_history
            
            # Get updated history from chat function
            updated_history = chat_fn(message, history, session)
            return updated_history
        
        msg.submit(respond, [msg, chatbot, session_id], chatbot).then(
            lambda: "", None, msg
        )
        submit_btn.click(respond, [msg, chatbot, session_id], chatbot).then(
            lambda: "", None, msg
        )
        
        gr.Markdown(
            """
            ### How to Play:
            - **Start a new game**: Type "start", "new game", "begin", or "play"
            - **Interrogate suspects**: Ask to talk to or question a suspect
            - **Search locations**: Ask to search or investigate a location
            - **Make accusations**: When you think you know who did it!
            - **Rules**: You have 3 wrong accusations before you lose. Win by correctly identifying the murderer with evidence.
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

