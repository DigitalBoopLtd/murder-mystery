# Murder Mystery Game

An interactive murder mystery game built with Gradio, LangChain, and LangGraph. This application recreates the n8n workflow as a Python-based chat interface where players can investigate crimes, interrogate suspects, and solve mysteries.

## Features

- **Dynamic Mystery Generation**: Each game generates a unique murder mystery scenario with victims, suspects, clues, and motives
- **Interactive Gameplay**: Chat with an AI Game Master to investigate the crime
- **Suspect Interrogation**: Use the "Interrogate Suspect" tool to question suspects who respond in character
- **Memory Management**: Game state and conversation history are maintained across the session
- **Gradio Interface**: Beautiful, user-friendly web interface

## Setup

1. **Install dependencies**:
```bash
pip install -r requirements.txt
```

2. **Set up environment variables**:
   - Copy `.env.example` to `.env`
   - Add your OpenAI API key:
   ```
   OPENAI_API_KEY=your_api_key_here
   ```

3. **Run the application**:
```bash
python app.py
```

4. **Access the interface**:
   - Open your browser to `http://localhost:7860`
   - The interface will be available locally

## How to Play

1. **Start a new game**: Type "start", "new game", "begin", or "play" to generate a new mystery
2. **Investigate**: Ask the Game Master questions about the crime scene, suspects, or locations
3. **Interrogate suspects**: Ask to talk to or question a suspect (the Game Master will use the interrogation tool)
4. **Search locations**: Ask to search or investigate specific locations to find clues
5. **Make accusations**: When you think you know who did it, make an accusation!
6. **Win conditions**: 
   - Win by correctly identifying the murderer with evidence
   - Lose after 3 wrong accusations

## Project Structure

- `app.py`: Main Gradio application and entry point
- `agent.py`: LangGraph agent implementation for the Game Master
- `models.py`: Pydantic models for structured mystery data
- `mystery_generator.py`: Mystery generation logic with structured output
- `game_tools.py`: Tools available to the Game Master agent (e.g., Interrogate Suspect)
- `game_state.py`: Game state management and session handling

## Architecture

The application uses:
- **LangGraph**: For the agent workflow with tool calling and memory
- **LangChain**: For LLM integration and structured output parsing
- **Gradio**: For the web interface
- **Pydantic**: For structured data validation

The flow mirrors the original n8n workflow:
1. User message triggers check for new game
2. If new game: Generate mystery → Parse structured output → Prepare game prompt
3. If continuing: Use continue prompt
4. Game Master agent processes message with tools and memory
5. Response is returned to the user

## Requirements

- Python 3.8+
- OpenAI API key
- See `requirements.txt` for Python dependencies

