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
- **Model Context Protocol (MCP)**: For exposing game state and services as composable tools.
- **Pydantic / dataclasses**: For structured models and configuration.

High‑level flow:
1. Player starts a new game, which generates a fresh mystery and optional art.
2. Player actions (spoken input) are transcribed with Whisper via OpenAI.
3. The LangGraph agent and game handlers decide what happens next (search, interrogate, reveal clues, etc.).
4. A response is generated, voiced with ElevenLabs (if configured), and the UI is updated with state panels and art.

---

## 🔌 MCP Architecture (Model Context Protocol)

This project demonstrates **MCP in Action** through MCP servers that expose game functionality as composable tools and resources.

### MCP Servers

```
┌─────────────────────────────────────────────────────────────────────┐
│                     MURDER MYSTERY MCP ECOSYSTEM                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Image Generator MCP (mcp_servers/image_generator.py)       │   │
│  ├─────────────────────────────────────────────────────────────┤   │
│  │                                                             │   │
│  │  RESOURCES:                    TOOLS:                       │   │
│  │  • images://cache              • generate_character_portrait│   │
│  │  • images://cache/{key}        • generate_scene             │   │
│  │  • images://styles             • generate_title_card        │   │
│  │  • images://stats              • list_cached_images         │   │
│  │                                • get_image_by_key           │   │
│  │                                                             │   │
│  │  Purpose: 1990s adventure game art generation with caching  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  ElevenLabs MCP (external: mcp-elevenlabs)                  │   │
│  ├─────────────────────────────────────────────────────────────┤   │
│  │  TOOLS:                                                     │   │
│  │  • get_voices - Fetch available voice catalog               │   │
│  │  • text_to_speech - Generate speech from text               │   │
│  │                                                             │   │
│  │  Purpose: Voice synthesis for characters and Game Master    │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Image Agent (services/image_agent.py)                      │   │
│  ├─────────────────────────────────────────────────────────────┤   │
│  │  Demonstrates MCP tool composition:                         │   │
│  │  • Connects to Image MCP server                             │   │
│  │  • Calls tools to generate images                           │   │
│  │  • Reads resources to check cache status                    │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Image Generator MCP Server (`mcp_servers/image_generator.py`)

Generates 1990s point-and-click adventure game style artwork via HuggingFace.

**Resources (MCP Resources):**

| URI | Description |
|-----|-------------|
| `images://cache` | List all cached images with metadata |
| `images://cache/{key}` | Get details of a specific cached image |
| `images://styles` | Available art styles and presets |
| `images://stats` | Cache statistics (total images, size, etc.) |

**Tools:**

| Tool | Description |
|------|-------------|
| `generate_character_portrait` | Create suspect/victim portraits |
| `generate_scene` | Generate location backgrounds |
| `generate_title_card` | Create atmospheric opening scenes |
| `list_cached_images` | Query the image cache |
| `get_image_by_key` | Retrieve a specific cached image |

**Run standalone:**
```bash
python -m mcp_servers.image_generator
```

### ElevenLabs MCP Client (`services/mcp_elevenlabs.py`)

Connects to the official ElevenLabs MCP server for voice synthesis.

**Usage:**
```python
from services.mcp_elevenlabs import fetch_voices_via_mcp

voices, status = await fetch_voices_via_mcp()
```

### Image Agent (`services/image_agent.py`)

Demonstrates calling the Image MCP server from an agent:

```python
from services.image_agent import ImageAgent

agent = ImageAgent()

# Generate a portrait via MCP
path = await agent.generate_portrait("Inspector Holmes", "Detective", "Analytical, observant")

# Check cache stats via MCP Resource
stats = await agent.get_cache_stats()
```

### Claude Desktop Configuration

To use the Image MCP server with Claude Desktop:

```json
{
  "mcpServers": {
    "murder-mystery-images": {
      "command": "python",
      "args": ["-m", "mcp_servers.image_generator"],
      "cwd": "/path/to/murder-mystery",
      "env": {
        "OPENAI_API_KEY": "your-key",
        "HF_TOKEN": "your-token"
      }
    }
  }
}
```

### MCP Integration Points

The main application integrates MCP at several points:

1. **Voice Fetching**: Uses ElevenLabs MCP to get available voices for character casting
2. **Image Generation**: Parallel image requests via `ImageAgent` (`services/image_agent.py`)
3. **Image Resources**: Cache status and generated images queryable via MCP Resources

### Demo: MCP Tool Composition

Run the Image Agent demo:
```bash
python -m services.image_agent
```

This demonstrates:
- Connecting to the Image MCP server
- Reading resources (`images://cache`, `images://styles`, `images://stats`)
- Calling tools to generate images
- Composing multiple MCP operations

---

## 🤖 Agentic Architecture

### Game Master Agent (`services/agent.py`)

The Game Master is a **LangGraph agent** with tools, not just an LLM. It:
- Decides when to call tools (interrogate suspect, search location, make accusation)
- Maintains conversation state via LangGraph checkpoints
- Uses tools to access game information securely

**Tools Available:**

| Tool | Purpose |
|------|---------|
| `interrogate_suspect` | Talk to a suspect in-character |
| `describe_scene_for_image` | Generate scene descriptions for image generation |
| `make_accusation` | Formally accuse a suspect of murder |
| `search_past_statements` | RAG search over conversation history |
| `find_contradictions` | Detect inconsistencies in statements |
| `get_investigation_hint` | Get contextual hints for the player |

### Investigation Assistant (`services/investigation_agent.py`)

A **separate assistant agent** demonstrating MCP composition:
- Analyzes case evidence and suggests next steps
- Uses structured outputs (Pydantic models)
- Non-blocking - doesn't affect gameplay latency

```python
from services.investigation_agent import InvestigationAssistant

assistant = InvestigationAssistant()
report = await assistant.analyze_case()
suggestions = await assistant.suggest_next_steps()
```

### Structured Outputs (vs Regex Markers)

The game uses **structured Pydantic outputs** for reliable parsing:

```python
# Old approach (fragile regex):
# "[SEARCHED:library] You find a torn letter..."

# New approach (structured output):
from game.models import GameMasterResponse, GameAction

response = GameMasterResponse(
    narrative="You carefully search the library...",
    action=GameAction(
        action_type="search_location",
        target="library",
        clue_ids_revealed=["clue_torn_letter"]
    ),
    scene_brief=SceneBrief(
        location="Victorian Library",
        visual_description="Dusty shelves, scattered papers...",
        camera_angle="medium shot"
    )
)
```

See `game/models.py` for structured output schemas and `game/structured_parser.py` for the parser.

---

## Requirements

- Python 3.8+
- OpenAI API key (`OPENAI_API_KEY`)
- Optional: ElevenLabs API key (`ELEVENLABS_API_KEY`) for voices
- Optional: HuggingFace token (`HF_TOKEN`) for images
- See `requirements.txt` for Python dependencies


