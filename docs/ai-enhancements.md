# 🧠 AI Architecture Enhancements

This document outlines planned improvements to the murder mystery game's AI system, following a "smart orchestrator, dumb workers" multi-agent pattern.

---

## 📊 Current Architecture

### What We Have

```
┌─────────────────────────────────────────────────────────┐
│              GAME MASTER AGENT (LangGraph)              │
│                                                         │
│  • Model: GPT-5.1 (600 max tokens)                     │
│  • Memory: MemorySaver (conversation history only)      │
│  • Tools: interrogate_suspect                           │
│  • State: Basic game state in GameState class           │
└─────────────────────────────────────────────────────────┘
                          │
                          │ Tool call with profile injection
                          ▼
┌─────────────────────────────────────────────────────────┐
│              SUSPECT "AGENT" (Stateless LLM Call)       │
│                                                         │
│  • Model: GPT-4o (temp 0.8)                            │
│  • Memory: NONE - each call is independent              │
│  • Receives: static profile + question                  │
│  • Returns: in-character response                       │
└─────────────────────────────────────────────────────────┘
```

### Current Limitations

1. **No suspect memory**: Suspects don't remember past conversations. Ask the same question twice, get different answers.

2. **No emotional state tracking**: Suspects respond the same regardless of how the player treats them.

3. **No cross-referencing**: Can't say "But Eleanor said she saw you at 9pm!" and have it mean anything.

4. **No contradiction detection**: The system doesn't flag when suspects contradict themselves or each other.

5. **Context bloat**: As games progress, the system prompt grows large with no retrieval optimization.

---

## 🎯 Target Architecture

### Design Principle: Smart Orchestrator, Dumb Workers

The Game Master owns ALL memory and state. Suspect agents remain stateless—they receive curated context and respond based solely on that.

```
┌─────────────────────────────────────────────────────────────────────┐
│                      GAME MASTER (Orchestrator)                     │
│                                                                     │
│   ┌──────────────────────────────────────────────────────────────┐ │
│   │                     MEMORY LAYER                              │ │
│   │                                                               │ │
│   │   ┌───────────────────┐    ┌────────────────────────────┐    │ │
│   │   │  Conversation     │    │      Game State Memory     │    │ │
│   │   │  Memory           │    │                            │    │ │
│   │   │  (LangGraph)      │    │  ┌──────────────────────┐  │    │ │
│   │   │                   │    │  │  Structured State    │  │    │ │
│   │   │  • Chat history   │    │  │  • suspect_states    │  │    │ │
│   │   │  • Tool calls     │    │  │  • suspect_convos    │  │    │ │
│   │   │  • AI responses   │    │  │  • contradictions    │  │    │ │
│   │   │                   │    │  └──────────────────────┘  │    │ │
│   │   │  ✅ EXISTS        │    │                            │    │ │
│   │   └───────────────────┘    │  ┌──────────────────────┐  │    │ │
│   │                            │  │  Vector Store (RAG)  │  │    │ │
│   │                            │  │  • Embedded convos   │  │    │ │
│   │                            │  │  • Semantic search   │  │    │ │
│   │                            │  └──────────────────────┘  │    │ │
│   │                            │                            │    │ │
│   │                            │  ❌ TO BUILD               │    │ │
│   │                            └────────────────────────────┘    │ │
│   └──────────────────────────────────────────────────────────────┘ │
│                                                                     │
│   Game Master curates context for each suspect interaction          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                                   │
            ┌──────────────────────┼──────────────────────┐
            ▼                      ▼                      ▼
      ┌───────────┐          ┌───────────┐          ┌───────────┐
      │  Suspect  │          │  Suspect  │          │  Suspect  │
      │  (Dumb)   │          │  (Dumb)   │          │  (Dumb)   │
      │           │          │           │          │           │
      │ Stateless │          │ Stateless │          │ Stateless │
      │ LLM call  │          │ LLM call  │          │ LLM call  │
      └───────────┘          └───────────┘          └───────────┘
```

---

## 🛠️ Implementation Plan

### Phase 1: Structured Game State Memory

**Goal**: Track per-suspect conversation history and emotional state.

#### 1.1 Extend GameState

Add to `game/state.py`:

```python
class SuspectState(BaseModel):
    """Tracked state for each suspect."""
    trust: int = Field(default=50, ge=0, le=100)
    nervousness: int = Field(default=30, ge=0, le=100)
    conversations: List[Dict[str, str]] = []  # [{q, a, turn}, ...]
    contradictions_caught: int = 0

class GameState:
    def __init__(self):
        # ... existing fields ...
        
        # NEW: Per-suspect tracking
        self.suspect_states: Dict[str, SuspectState] = {}
        self.detected_contradictions: List[Dict] = []
        self.current_turn: int = 0
```

#### 1.2 Update interrogate_suspect Tool

Modify `game/tools.py` to accept richer context:

```python
@tool
def interrogate_suspect(
    suspect_name: str,
    suspect_profile: str,  # Now includes conversation history + state
    player_question: str,
    voice_id: Optional[str] = None,
) -> str:
    """Interrogate a suspect with full context."""
    # Tool remains stateless - all context is in suspect_profile
```

#### 1.3 Enhance Game Master Prompt

Update `game/mystery_generator.py` `prepare_game_prompt()` to instruct the Game Master to:

1. Include conversation history when calling the tool
2. Pass emotional state (trust/nervousness)
3. Include relevant cross-references from other suspects

#### 1.4 Post-Response Processing

After each interrogation:

1. Log the exchange to `suspect_states[name].conversations`
2. Update trust/nervousness based on question style
3. Check for contradictions against past statements

---

### Phase 2: RAG Integration

**Goal**: Enable semantic search across all game knowledge for efficient retrieval.

#### 2.1 Create GameMemory Service

New file `services/game_memory.py`:

```python
from langchain.vectorstores import FAISS
from langchain.embeddings import OpenAIEmbeddings
from typing import Dict, List, Optional

class GameMemory:
    """Centralized memory with structured state and vector search."""
    
    def __init__(self):
        self.embeddings = OpenAIEmbeddings()
        self.vectorstore = None
        self.documents = []
        
    def initialize(self):
        """Initialize empty vectorstore."""
        self.vectorstore = FAISS.from_texts(
            ["Game initialized"], 
            self.embeddings,
            metadatas=[{"type": "system"}]
        )
        
    def add_conversation(
        self, 
        suspect: str, 
        question: str, 
        answer: str, 
        turn: int
    ):
        """Index a conversation exchange."""
        doc = f"Turn {turn}: {suspect} was asked '{question}' and said: '{answer}'"
        self.vectorstore.add_texts(
            [doc],
            metadatas=[{
                "type": "conversation",
                "suspect": suspect,
                "turn": turn
            }]
        )
        
    def search(self, query: str, k: int = 5) -> List[str]:
        """Semantic search across all indexed content."""
        results = self.vectorstore.similarity_search(query, k=k)
        return [r.page_content for r in results]
        
    def search_by_suspect(self, suspect: str, query: str, k: int = 3) -> List[str]:
        """Search statements from a specific suspect."""
        results = self.vectorstore.similarity_search(
            query, 
            k=k,
            filter={"suspect": suspect}
        )
        return [r.page_content for r in results]
```

#### 2.2 RAG-Powered Tools

Add optional tools for the Game Master:

```python
@tool
def search_past_statements(query: str) -> str:
    """Search all past conversations for relevant statements.
    
    Use when:
    - Player references something a suspect said
    - Need to check for contradictions
    - Reconstructing timeline of events
    """
    results = game_memory.search(query, k=5)
    return "\n".join(results) if results else "No relevant statements found."

@tool
def find_contradictions(suspect: str, new_statement: str) -> str:
    """Check if a suspect's new statement contradicts their past statements."""
    past = game_memory.search_by_suspect(suspect, new_statement, k=3)
    # LLM analysis of potential contradictions
    # ...
```

#### 2.3 Context Assembly

Before each suspect interaction, the Game Master assembles context using both memory systems:

```python
def assemble_interrogation_context(suspect_name: str, question: str) -> str:
    """Build rich context for suspect interaction."""
    
    # 1. Structured: Get suspect's current state
    state = game_state.suspect_states.get(suspect_name)
    
    # 2. Structured: Get conversation history with this suspect
    history = state.conversations if state else []
    
    # 3. RAG: Find what others said about this suspect
    cross_refs = game_memory.search(f"statements about {suspect_name}", k=3)
    
    # 4. RAG: Find statements related to the question topic
    related = game_memory.search(question, k=3)
    
    return f"""
PREVIOUS CONVERSATIONS WITH THIS SUSPECT:
{format_history(history)}

WHAT OTHERS HAVE SAID ABOUT THEM:
{format_cross_refs(cross_refs)}

CURRENT EMOTIONAL STATE:
- Trust: {state.trust}%
- Nervousness: {state.nervousness}%
- Times caught in contradictions: {state.contradictions_caught}
"""
```

---

### Phase 3: Enhanced Gameplay Features

**Goal**: Use the new memory system to enable advanced gameplay.

#### 3.1 Automatic Contradiction Detection

After each response, check for contradictions:

```python
def check_for_contradictions(suspect: str, new_statement: str):
    """Detect if new statement contradicts past statements."""
    similar_past = game_memory.search_by_suspect(suspect, new_statement, k=3)
    
    if similar_past:
        # Use LLM to analyze for contradictions
        analysis = analyze_contradiction(new_statement, similar_past)
        if analysis.is_contradiction:
            game_state.detected_contradictions.append({
                "suspect": suspect,
                "old_statement": analysis.old_statement,
                "new_statement": new_statement,
                "issue": analysis.explanation
            })
            # Update suspect nervousness
            state = game_state.suspect_states[suspect]
            state.nervousness = min(100, state.nervousness + 15)
            state.contradictions_caught += 1
```

#### 3.2 Trust/Nervousness Effects

Modify suspect prompts based on emotional state:

```python
def get_emotional_instructions(state: SuspectState) -> str:
    """Generate behavior instructions based on emotional state."""
    instructions = []
    
    if state.trust < 30:
        instructions.append("Be defensive and give short, guarded answers.")
    elif state.trust > 70:
        instructions.append("Be more open, consider sharing your secret.")
        
    if state.nervousness > 70:
        instructions.append("Show signs of stress - speak faster, contradict yourself slightly.")
    elif state.nervousness > 50:
        instructions.append("Be slightly on edge, avoid eye contact in your descriptions.")
        
    if state.contradictions_caught > 0:
        instructions.append(f"You've been caught in {state.contradictions_caught} contradiction(s). Be more careful.")
        
    return "\n".join(instructions)
```

#### 3.3 Cross-Reference Confrontations

When player explicitly references another suspect's statement:

```python
# Game Master detects cross-reference in player input
if "but [suspect] said" in player_message.lower():
    # RAG retrieves the actual statement
    referenced_statement = game_memory.search(player_message, k=1)
    
    # Include in context so suspect can react authentically
    context += f"""
THE DETECTIVE IS CONFRONTING YOU WITH THIS:
{referenced_statement}

React appropriately - if this contradicts what you said, either:
- Nervously try to explain the discrepancy
- Double down on your story
- If innocent, express genuine confusion
- If guilty, deflect or get defensive
"""
```

---

## 📁 File Changes Summary

| File | Changes |
|------|---------|
| `game/state.py` | Add `SuspectState`, expand `GameState` |
| `game/tools.py` | Enhanced `interrogate_suspect`, new RAG tools |
| `game/mystery_generator.py` | Update `prepare_game_prompt()` with new instructions |
| `services/game_memory.py` | **NEW** - GameMemory class with RAG |
| `game/handlers.py` | Post-response processing for state updates |
| `requirements.txt` | Add `faiss-cpu`, `langchain` (if not present) |

---

## 🎯 Priority Order

### Must Have (Phase 1) ✅ COMPLETE
1. ✅ Per-suspect conversation tracking in GameState
2. ✅ Trust/nervousness state per suspect
3. ✅ Include conversation history in tool calls
4. ✅ Emotional state affects suspect behavior

### Should Have (Phase 2) ✅ COMPLETE
1. ✅ RAG vector store for conversations (`services/game_memory.py`)
2. ✅ Semantic search across game knowledge (`search_past_statements` tool)
3. ✅ Automatic contradiction detection (`find_contradictions` tool)
4. ✅ Cross-reference retrieval (`get_cross_references` tool)

### Nice to Have (Phase 3)
1. ⬜ Visual contradiction indicators in UI
2. ⬜ Trust meter display per suspect
3. ⬜ Timeline reconstruction tool
4. ⬜ Detective notebook with pinned statements

---

## 🧪 Testing Strategy

1. **Unit tests** for GameMemory service
2. **Integration tests** for context assembly
3. **Gameplay tests**:
   - Ask same question twice → consistent answer
   - Build trust → suspect becomes more open
   - Catch in contradiction → nervousness increases
   - Cross-reference works → suspect reacts appropriately

---

## 📈 Success Metrics

- Suspects give consistent answers to repeated questions
- Trust/nervousness visibly affects gameplay
- Cross-references actually retrieve correct past statements
- Contradictions are detected and flagged
- Context size stays manageable even in long games

