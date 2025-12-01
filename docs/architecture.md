# 🏗️ Architecture Overview

This document describes the MCP-first architecture of the Murder Mystery Detective Game.

---

## Design Philosophy

### MCP-First

The game engine is implemented as an **MCP (Model Context Protocol) server**. This means:

1. **Any MCP-compatible client can play** — Claude Desktop, Cursor, custom agents, or the Gradio UI
2. **Clean separation of concerns** — UI is decoupled from game logic
3. **Composable tools** — Each game action is a discrete, well-defined tool
4. **Stateless protocol** — Session state is managed server-side, keyed by session ID

### Oracle Pattern

The "truth" of the mystery (who is guilty, secrets, motives) is encapsulated in a **MysteryOracle**. The player-facing agent:

- ❌ Cannot directly access `suspect.isGuilty` or `suspect.secret`
- ✅ Must call `oracle.interrogate()` which returns only what the suspect would reveal
- ✅ Must call `oracle.check_accusation()` to verify guesses

This prevents the Game Master agent from accidentally spoiling the mystery.

### Partitioned RAG

Each suspect has their own vector store partition:

```
memory/
├── suspect_alice/     # Alice's conversation history
├── suspect_bob/       # Bob's conversation history
├── suspect_charlie/   # Charlie's conversation history
└── clues/             # Discovered clues (shared)
```

This ensures:
- Searching "what did Alice say" only returns Alice's statements
- No information bleeding between suspects
- Clues are searchable across the entire investigation

---

## Component Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENTS                                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────┐    ┌─────────────────────┐                │
│  │   Gradio UI         │    │   Claude Desktop    │                │
│  │   (murder-mystery/) │    │   (or any MCP       │                │
│  │                     │    │    client)          │                │
│  └──────────┬──────────┘    └──────────┬──────────┘                │
│             │                          │                            │
│             └──────────┬───────────────┘                            │
│                        │                                            │
│                        ▼ MCP Protocol (stdio)                       │
│                                                                      │
├─────────────────────────────────────────────────────────────────────┤
│                    MURDER MYSTERY MCP SERVER                         │
│                    (murder-mystery-mcp/)                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                        server.py                             │   │
│  │  - @server.list_tools() → 11 tools                          │   │
│  │  - @server.call_tool() → handler dispatch                   │   │
│  │  - @server.list_resources() → 3 resource types              │   │
│  │  - @server.read_resource() → JSON data                      │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐     │
│  │  GameSession    │  │  MysteryOracle  │  │  GameMemory     │     │
│  │  (game/state)   │  │  (truth keeper) │  │  (RAG)          │     │
│  │                 │  │                 │  │                 │     │
│  │  • suspects     │  │  • full mystery │  │  • per-suspect  │     │
│  │  • clues        │  │  • interrogate()│  │    partitions   │     │
│  │  • locations    │  │  • check_accuse │  │  • search()     │     │
│  │  • emotions     │  │  • reveal logic │  │  • add_convo()  │     │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘     │
│                                                                      │
│  ┌─────────────────┐  ┌─────────────────┐                          │
│  │ EmotionalTracker│  │ Contradiction   │                          │
│  │                 │  │ Detector        │                          │
│  │ • trust         │  │                 │                          │
│  │ • nervousness   │  │ • LLM-based     │                          │
│  │ • triggers      │  │ • natural lang  │                          │
│  └─────────────────┘  └─────────────────┘                          │
│                                                                      │
├─────────────────────────────────────────────────────────────────────┤
│                    EXTERNAL SERVICES                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐     │
│  │  OpenAI API     │  │  HuggingFace    │  │  ElevenLabs     │     │
│  │                 │  │  Inference API  │  │  MCP            │     │
│  │  • GPT-4o       │  │                 │  │                 │     │
│  │  • Whisper      │  │  • FLUX.1       │  │  • get_voices   │     │
│  │  • Embeddings   │  │  • Portraits    │  │  • text_to_     │     │
│  │                 │  │  • Scenes       │  │    speech       │     │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘     │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### Starting a Game

```
Client                    MCP Server                    Services
  │                           │                            │
  │  start_game(era, tone)    │                            │
  │ ─────────────────────────>│                            │
  │                           │  generate_mystery_async()  │
  │                           │ ──────────────────────────>│ OpenAI
  │                           │<───────────────────────────│
  │                           │                            │
  │                           │  oracle.initialize(mystery)│
  │                           │  session.initialize()      │
  │                           │                            │
  │  {premise, suspects...}   │                            │
  │<──────────────────────────│                            │
```

### Interrogating a Suspect

```
Client                    MCP Server                    Oracle
  │                           │                            │
  │  interrogate_suspect      │                            │
  │  (name, question)         │                            │
  │ ─────────────────────────>│                            │
  │                           │  oracle.interrogate(       │
  │                           │    name, question,         │
  │                           │    trust, nervousness,     │
  │                           │    history                 │
  │                           │  )                         │
  │                           │ ──────────────────────────>│
  │                           │                            │ LLM call
  │                           │<───────────────────────────│
  │                           │                            │
  │                           │  session.record_convo()    │
  │                           │  memory.add_conversation() │
  │                           │  emotional.update()        │
  │                           │                            │
  │  {response, emotions...}  │                            │
  │<──────────────────────────│                            │
```

### Making an Accusation

```
Client                    MCP Server                    Oracle
  │                           │                            │
  │  make_accusation          │                            │
  │  (suspect, evidence)      │                            │
  │ ─────────────────────────>│                            │
  │                           │  oracle.check_accusation() │
  │                           │ ──────────────────────────>│
  │                           │                            │ (checks isGuilty)
  │                           │  true/false                │
  │                           │<───────────────────────────│
  │                           │                            │
  │                           │  if correct:               │
  │                           │    session.game_over=True  │
  │                           │    session.won=True        │
  │                           │  else:                     │
  │                           │    wrong_accusations++     │
  │                           │                            │
  │  {result, game_state}     │                            │
  │<──────────────────────────│                            │
```

---

## MCP Tools

### Gameplay Tools

| Tool | Inputs | Returns |
|------|--------|---------|
| `start_game` | `session_id?`, `era?`, `tone?` | Premise, victim, suspects |
| `get_game_state` | `session_id` | Full game state JSON |
| `interrogate_suspect` | `session_id`, `suspect_name`, `question` | Response, emotions, reveals |
| `search_location` | `session_id`, `location` | Scene description, clue found |
| `make_accusation` | `session_id`, `suspect_name`, `evidence` | Win/lose result |
| `search_memory` | `session_id`, `query`, `suspect_filter?` | RAG results |
| `find_contradictions` | `session_id`, `suspect_name` | Contradiction list |
| `get_timeline` | `session_id` | Timeline events |

### Image Tools

| Tool | Inputs | Returns |
|------|--------|---------|
| `generate_scene_image` | `session_id`, `location`, `include_clue?` | Image URL |
| `generate_portrait` | `session_id`, `suspect_name` | Image URL |
| `generate_title_card` | `session_id` | Image URL |

---

## Security Considerations

### API Key Handling

1. **Environment variables** — Primary method for local development
2. **Session-scoped storage** — UI-provided keys stored in memory only
3. **Never persisted** — Keys are not written to disk or logs
4. **Never exposed** — Keys not sent to client or included in responses

### Oracle Isolation

The `MysteryOracle` is the only component that knows:
- Who the murderer is (`isGuilty`)
- Suspect secrets
- Full encounter graph

The player-facing agent only receives:
- Public suspect info (name, role, personality, alibi)
- What suspects choose to reveal during interrogation
- Clues found at searched locations

---

## Future Considerations

### Scaling

- **Multiple concurrent games** — Already supported via session IDs
- **Persistent sessions** — Could add Redis/database for session storage
- **Horizontal scaling** — Stateless MCP protocol enables load balancing

### Additional MCP Servers

The architecture supports adding more MCP servers:
- **Audio MCP** — Ambient sounds, music
- **Analytics MCP** — Game metrics, player behavior
- **Community MCP** — Shared mysteries, leaderboards

---

*Last updated: Nov 2025*



