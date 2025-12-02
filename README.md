---
title: Murder Mystery Detective Game
emoji: 🔍
colorFrom: purple
colorTo: red
sdk: gradio
sdk_version: "5.29.1"
app_file: app.py
pinned: false
tags:
  - mcp-in-action-track-creative
  - agents
  - game
  - elevenlabs
  - tts
  - mcp
  - voice
  - detective
  - agentic
---

# 🔍 Murder Mystery Detective Game

> 🎉 **MCP 1st Birthday Hackathon Submission** — Track 2: MCP in Action (`mcp-in-action-track-creative`)
> 
> 🔗 **See also**: [Murder Mystery MCP Server](https://huggingface.co/spaces/MCP-1st-Birthday/murder-mystery-mcp) — Track 1: Building MCP

A voice-first murder mystery game powered by **Model Context Protocol (MCP)**. Investigate crimes, interrogate AI suspects, and solve procedurally generated mysteries in a 90s point-and-click adventure style.

---

## 📺 Demo Video

> **[👉 Watch the Demo Video](YOUR_VIDEO_LINK_HERE)** *(Required for submission)*
>
> The video shows: starting a new mystery, interrogating suspects with voice, searching locations, and making an accusation.

---

## 🐦 Social Media

> **[🐦 See the announcement on X/Twitter](YOUR_SOCIAL_POST_LINK_HERE)** *(Required for submission)*

---

## 👥 Team

| HuggingFace Username |
|---------------------|
| @YOUR_HF_USERNAME |

*(Add all team member HuggingFace usernames)*

---

## 🔌 What is the MCP Server?

This project is built around a **Murder Mystery MCP Server** — a standalone game engine that exposes the entire murder mystery experience as composable tools via the [Model Context Protocol](https://modelcontextprotocol.io/).

### Why MCP?

**MCP (Model Context Protocol)** is an open standard that lets AI agents use tools and access resources in a consistent way. By building the game as an MCP server:

1. **Play anywhere** — The same game works in Claude Desktop, Cursor, custom agents, or this Gradio UI
2. **Agent-agnostic** — Any LLM that supports MCP can be the "detective" playing the game
3. **Composable** — Tools like `interrogate_suspect` and `search_location` can be mixed with other MCP servers
4. **Separation of concerns** — The game logic is completely decoupled from the UI

### What the MCP Server Does

The MCP server (`murder-mystery-mcp/`) handles **all game logic**:

| Responsibility | How It Works |
|----------------|--------------|
| **Mystery Generation** | Creates unique victims, suspects, motives, and an encounter graph |
| **Suspect Interrogation** | Manages emotional states, conversation memory, and in-character responses |
| **Clue Discovery** | Tracks which locations have been searched and what was found |
| **RAG Memory** | Semantic search across all conversations to find contradictions |
| **Accusation Validation** | Checks if the player correctly identified the murderer |
| **Image Generation** | Creates 1990s adventure game-style portraits and scenes |

### How It's Used

**Option 1: Gradio UI (this project)**
- The UI calls MCP tools to start games, interrogate suspects, etc.
- Voice input is transcribed and sent as questions
- Responses are spoken back with ElevenLabs TTS

**Option 2: Claude Desktop**
- Add the MCP server to your Claude Desktop config
- Chat naturally: *"Start a mystery game"*, *"Talk to the butler"*
- Claude uses the MCP tools to play the game

**Option 3: Any MCP Client**
- Build your own client in any language
- Connect via stdio and call the tools programmatically

---

## 🏆 Hackathon Tracks

This is part of a **two-project submission**:

| Track | Project | Description |
|-------|---------|-------------|
| **Track 1: Building MCP** | [murder-mystery-mcp](https://huggingface.co/spaces/MCP-1st-Birthday/murder-mystery-mcp) | Standalone MCP server with all game tools |
| **Track 2: MCP in Action** | **This project** | Gradio UI that uses the MCP server |

### Track 1: Building MCP → [Separate Repository](../murder-mystery-mcp/)

The **Murder Mystery MCP Server** is a complete game engine as MCP tools:

| Category | Tools/Resources |
|----------|-----------------|
| **Game Flow** | `start_game`, `get_game_state`, `interrogate_suspect`, `search_location`, `make_accusation` |
| **Investigation** | `search_memory`, `find_contradictions`, `get_cross_references`, `get_timeline` |
| **Images** | `generate_portrait`, `generate_scene`, `generate_title_card` |
| **Resources** | `mystery://state`, `mystery://suspects`, `mystery://clues`, `mystery://timeline` |

**Use it in Claude Desktop** to play the game entirely through chat!

### Track 2: MCP in Action — This Project

**The Gradio Murder Mystery App** is a complete AI agent application that:

- 🎙️ **Voice-first gameplay** with ElevenLabs TTS for all characters
- 🕵️ **Autonomous agent** that orchestrates interrogation, clue discovery, and accusation
- 🧠 **RAG-powered memory** for finding contradictions in suspect statements
- 🎨 **MCP-powered image generation** via the Image Generator MCP server
- 📊 **Visual case file** with timeline, clues, and suspect profiles

---

## ✨ Features

- **Voice-first gameplay** — Talk to the Game Master using your microphone; responses are spoken back with ElevenLabs TTS
- **Procedural mystery generation** — Each game creates a unique victim, suspects, locations, clues, and an encounter graph
- **MCP-powered game engine** — All game logic exposed as composable MCP tools that any agent can use
- **Suspect interrogation** — Suspects have personalities, emotional states (trust/nervousness), and memory of past conversations
- **RAG memory search** — Semantic search across all conversations and clues to find contradictions
- **1990s adventure game art** — Portraits and scenes generated via HuggingFace in vintage LucasArts style
- **Timeline & case file** — Visual investigation timeline and case file that updates as you discover clues

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        MURDER MYSTERY SYSTEM                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────┐         ┌─────────────────────────────┐   │
│  │   Gradio UI         │         │  Claude Desktop / Cursor    │   │
│  │   (this project)    │         │  or any MCP-compatible      │   │
│  │                     │         │  agent                      │   │
│  └──────────┬──────────┘         └──────────────┬──────────────┘   │
│             │                                   │                   │
│             │  MCP Protocol                     │  MCP Protocol     │
│             │  (tools + resources)              │  (tools + resources)
│             ▼                                   ▼                   │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │            MURDER MYSTERY MCP SERVER                          │  │
│  │            (murder-mystery-mcp/)                              │  │
│  ├──────────────────────────────────────────────────────────────┤  │
│  │                                                               │  │
│  │  TOOLS:                         RESOURCES:                    │  │
│  │  • start_game                   • mystery://{id}/state        │  │
│  │  • interrogate_suspect          • mystery://{id}/suspects     │  │
│  │  • search_location              • mystery://{id}/clues        │  │
│  │  • make_accusation                                            │  │
│  │  • search_memory (RAG)                                        │  │
│  │  • find_contradictions                                        │  │
│  │  • get_timeline                                               │  │
│  │  • generate_portrait                                          │  │
│  │  • generate_scene_image                                       │  │
│  │  • generate_title_card                                        │  │
│  │                                                               │  │
│  │  INTERNALS:                                                   │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐             │  │
│  │  │ Mystery     │ │ RAG Memory  │ │ Emotional   │             │  │
│  │  │ Oracle      │ │ (per-suspect│ │ Tracker     │             │  │
│  │  │ (truth)     │ │  partitions)│ │             │             │  │
│  │  └─────────────┘ └─────────────┘ └─────────────┘             │  │
│  │                                                               │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  IMAGE GENERATOR MCP (mcp_servers/image_generator.py)         │  │
│  │  • generate_character_portrait                                │  │
│  │  • generate_scene                                             │  │
│  │  • generate_title_card                                        │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  ELEVENLABS MCP (external: mcp-elevenlabs)                    │  │
│  │  • get_voices                                                 │  │
│  │  • text_to_speech                                             │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Design Principles

1. **MCP-First** — The game engine is an MCP server. The UI is just one possible client.
2. **Oracle Pattern** — The "truth" of the mystery (who is guilty, secrets) lives in a `MysteryOracle` that the player-facing agent cannot directly access.
3. **Partitioned RAG** — Each suspect has their own vector store partition to prevent information bleeding.
4. **Emotional State** — Suspects track trust and nervousness, affecting their responses.

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- API Keys (all required):
  - **OpenAI** — Mystery generation and LLM responses
  - **ElevenLabs** — Voice synthesis for characters
  - **HuggingFace** — Portrait and scene art generation

### Installation

**Quick Start (Recommended):**

```bash
# Clone the repository
git clone https://github.com/your-username/murder-mystery.git
cd murder-mystery

# One command to set up everything!
make setup

# Create your .env file with API keys
cp env.example .env
# Edit .env with your API keys (OPENAI_API_KEY, ELEVENLABS_API_KEY, HF_TOKEN)
```

The `make setup` command will:
- Create a Python virtual environment
- Install all dependencies
- Set up everything you need to get started

**Manual Installation (Alternative):**

If you prefer to set up manually:

```bash
# Clone both repositories
git clone https://github.com/your-username/murder-mystery.git
git clone https://github.com/your-username/murder-mystery-mcp.git

# Set up the MCP server first
cd murder-mystery-mcp
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp env.example .env
# Edit .env with your OPENAI_API_KEY

# Set up the UI
cd ../murder-mystery
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp env.example .env
# Edit .env with all API keys
```

### Running

**Option 1: Gradio UI (recommended for playing)**

```bash
cd murder-mystery

# With hot reloading (auto-restarts on file changes)
make dev

# Or run normally
make run

# Or manually
source venv/bin/activate
python app.py

# Open http://localhost:7860 in your browser
```

**Available Make Commands:**

- `make setup` - Set up virtual environment and install dependencies
- `make dev` - Run with hot reloading (watches for file changes)
- `make run` - Run the app normally
- `make install` - Install/update dependencies (assumes venv exists)
- `make clean` - Remove virtual environment and cache files
- `make check-env` - Verify .env file has required API keys

**Option 2: Claude Desktop (play via chat)**

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "murder-mystery": {
      "command": "python",
      "args": ["/path/to/murder-mystery-mcp/server.py"],
      "env": {
        "OPENAI_API_KEY": "your-key-here",
        "HF_TOKEN": "your-token-here"
      }
    }
  }
}
```

Then in Claude Desktop, say: *"Start a new murder mystery game"*

---

## 🎮 How to Play

1. **Enter API Keys** — On first load, go to the 🔑 Settings tab and enter your API keys (or set them in `.env`)
2. **Start a new game** — Click **"START NEW MYSTERY"** to generate a fresh case
3. **Listen to the intro** — The Game Master introduces the victim and suspects
4. **Investigate by speaking** — Use the microphone to ask questions:
   - *"Tell me about the suspects"*
   - *"Let me talk to the butler"*
   - *"Search the library for clues"*
   - *"What did Marcus say about his alibi?"*
5. **Find contradictions** — Use the RAG memory to catch suspects in lies
6. **Make an accusation** — When confident, accuse the murderer with evidence

### Win/Lose Conditions

- **Win**: Correctly identify the murderer with supporting evidence
- **Lose**: 3 wrong accusations and you're removed from the case

---

## 🔧 MCP Tools Reference

### Gameplay Tools

| Tool | Description |
|------|-------------|
| `start_game` | Start a new murder mystery (optional: era, tone) |
| `get_game_state` | Get suspects, clues, locations, progress |
| `interrogate_suspect` | Ask a suspect a question |
| `search_location` | Search a location for clues |
| `make_accusation` | Formally accuse a suspect |
| `search_memory` | RAG search past statements |
| `find_contradictions` | Detect inconsistencies in statements |
| `get_timeline` | Get investigation timeline |

### Image Generation Tools

| Tool | Description |
|------|-------------|
| `generate_scene_image` | Generate location artwork |
| `generate_portrait` | Generate suspect portrait |
| `generate_title_card` | Generate mystery title card |

### MCP Resources

| URI Pattern | Description |
|-------------|-------------|
| `mystery://{session_id}/state` | Current game state (JSON) |
| `mystery://{session_id}/suspects` | Suspect list with public info |
| `mystery://{session_id}/clues` | Discovered clues |

---

## 📁 Project Structure

```
murder-mystery/                    # Gradio UI (this repo)
├── app.py                         # Main entry point
├── app/
│   ├── main.py                    # App wiring
│   ├── ui_components.py           # Gradio components
│   └── event_handlers.py          # UI event handlers
├── services/
│   ├── mcp_client.py              # MCP client for game server
│   ├── game_router.py             # Routes calls to MCP
│   ├── tts_service.py             # ElevenLabs TTS
│   ├── voice_service.py           # Voice matching
│   └── image_agent.py             # Image MCP client
├── ui/
│   ├── formatters.py              # HTML formatting
│   └── styles/                    # CSS styling
├── mcp_servers/
│   └── image_generator.py         # Standalone image MCP server
└── config/
    └── settings.py                # Environment config

murder-mystery-mcp/                # Game Engine MCP Server
├── server.py                      # MCP server with tools
├── game/
│   ├── state.py                   # Game session state
│   ├── memory.py                  # Partitioned RAG
│   ├── emotional_tracker.py       # Trust/nervousness
│   └── contradiction_detector.py  # LLM contradiction detection
├── image_generator.py             # Image generation
└── requirements.txt
```

---

## 🔐 API Keys

All three keys are **required** to play:

| Key | Environment Variable | Purpose |
|-----|---------------------|---------|
| OpenAI | `OPENAI_API_KEY` | Mystery generation, LLM responses |
| ElevenLabs | `ELEVENLABS_API_KEY` | Voice synthesis for characters |
| HuggingFace | `HF_TOKEN` | Portrait and scene art generation |

Set in `.env` file or enter via the 🔑 Settings tab in the UI.

---

## 🎨 Customization

### Mystery Settings

When starting a game, you can customize:

- **Era**: Victorian, 1920s, Cyberpunk, Modern, etc.
- **Tone**: Noir, Cozy, Gothic Horror, Comedy, etc.
- **Difficulty**: Easy, Normal, Hard (affects RAG hints)

### Art Style

All generated images use a **1990s LucasArts point-and-click adventure game** aesthetic (think *The Secret of Monkey Island*, *Gabriel Knight*).

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

## 📜 License

MIT

---

## 🙏 Acknowledgments

- **LangChain/LangGraph** — Agent orchestration
- **Gradio** — Web UI framework
- **ElevenLabs** — Voice synthesis
- **HuggingFace** — Image generation
- **MCP** — Model Context Protocol for tool composition
