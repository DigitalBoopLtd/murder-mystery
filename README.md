# Murder Mystery Game

Voice‑first murder mystery game built with Gradio, LangChain, and LangGraph. Players investigate crimes, interrogate suspects, and solve fully generated mysteries in a 90s point‑and‑click adventure style, with optional AI voices and retro portraits/scenes.

## Features

- **Voice‑first gameplay**: Talk to the Game Master using your microphone; responses are spoken back with optional subtitles.
- **Dynamic mystery generation**: Each game builds a fresh victim, suspects, locations, clues, and motives.
- **Suspect interrogation tools**: The Game Master can call tools (e.g. interrogate a suspect) that respond in‑character.
- **On‑demand 90s adventure art**: Optional portraits and scene art generated via HuggingFace in a vintage point‑and‑click style.
- **Per‑session settings**: Choose era, setting, difficulty, and narrative tone before starting a new mystery.
- **Stateful gameplay**: Game state, searched locations, suspects talked to, and clues are tracked across the session.

## Setup

You can use the helper script or do things manually.

1. **(Recommended) Run the setup script**:

```bash
./setup.sh
```

This will:
- Check for Python 3.8+  
- Create a `venv` virtual environment (if needed)  
- Install dependencies from `requirements.txt`  
- Create a `.env` file from `env.example` if you don't already have one  

2. **(Manual) Install dependencies**:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. **Configure environment variables**:

- Copy `env.example` to `.env`:

```bash
cp env.example .env
```

- Edit `.env` and set at least:

```bash
OPENAI_API_KEY=your_openai_api_key_here
```

- Optionally enable extra features:

```bash
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here  # Voice acting + TTS
HF_TOKEN=your_huggingface_token_here             # Portraits and scene art

# Advanced (optional) model overrides
SUSPECT_RESOLVER_MODEL=gpt-4o-mini
LOCATION_RESOLVER_MODEL=gpt-4o-mini
```

## Running the application

```bash
source venv/bin/activate
python app.py
```

Then open your browser to `http://localhost:7860`.

## How to Play

1. **Start a new game**: Click the **“START NEW MYSTERY”** button in the UI.
2. **Listen to the intro**: The Game Master will introduce the case via voice (and subtitles if available).
3. **Investigate by speaking**: Use the microphone input and ask things like:
   - “Describe the crime scene”
   - “Tell me about the suspects”
   - “Search the study for clues”
   - “Let me talk to the heiress again”
4. **Interrogate suspects**: Ask to speak with a specific suspect; they will answer in character and may have their own voice.
5. **Make accusations**: When you’re ready, accuse someone of the murder. You win by correctly identifying the murderer with evidence; you lose after too many wrong accusations.

## Project Structure

- `app.py`: Voice‑first Gradio application and main entry point.
- `app/`: Application wiring; exposes `create_app` for embedding the UI elsewhere.
- `mystery_config.py`: Options, validation, and helper functions for era/setting/difficulty/tone.
- `game/`:
  - `actions.py`, `handlers.py`, `startup.py`: Core game loop, player actions, and startup wiring.
  - `mystery_generator.py`, `parser.py`, `models.py`: Mystery generation, parsing, and structured data models.
  - `state.py`, `state_manager.py`: Game state and per‑session management.
  - `tools.py`: Tools available to the Game Master (e.g. interrogate suspect).
- `services/`:
  - `agent.py`: LangGraph/LangChain agent that runs the Game Master.
  - `tts_service.py`, `voice_service.py`: ElevenLabs/OpenAI TTS and voice‑matching helpers.
  - `image_service.py`: HuggingFace‑based portrait and scene generation.
- `ui/`:
  - `styles.py`: Retro 90s adventure‑style CSS.
  - `formatters.py`: HTML formatting for victims, suspects, locations, and clues.
- `config/settings.py`: Centralized environment/config dataclass for deployment‑level settings.

## Architecture

The application uses:
- **LangGraph**: To orchestrate the Game Master agent, tools, and conversational memory.
- **LangChain**: For OpenAI model integration and structured outputs.
- **Gradio**: For the web UI, voice input, and audio/subtitle playback.
- **Pydantic / dataclasses**: For structured models and configuration.

High‑level flow:
1. Player starts a new game, which generates a fresh mystery and optional art.
2. Player actions (spoken input) are transcribed with Whisper via OpenAI.
3. The LangGraph agent and game handlers decide what happens next (search, interrogate, reveal clues, etc.).
4. A response is generated, voiced with ElevenLabs (if configured), and the UI is updated with state panels and art.

## Requirements

- Python 3.8+
- OpenAI API key (`OPENAI_API_KEY`)
- Optional: ElevenLabs API key (`ELEVENLABS_API_KEY`) for voices
- Optional: HuggingFace token (`HF_TOKEN`) for images
- See `requirements.txt` for Python dependencies


