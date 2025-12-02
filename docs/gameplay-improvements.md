# 🎮 Gameplay Improvement Ideas

This document tracks potential enhancements to the murder mystery game. Items are prioritized with mobile-responsive design in mind.

---

## ✅ Completed

### Core Architecture
- ✅ **MCP-first design** — All game logic runs through Murder Mystery MCP Server
- ✅ **Mystery Oracle** — Isolated truth authority prevents agent from knowing the answer
- ✅ **Encounter Graph** — Explicit "who saw whom, where, when" for consistent alibis
- ✅ **Partitioned RAG** — Per-suspect vector stores prevent information bleeding
- ✅ **Emotional Tracker** — Trust/nervousness with RAG embedding

### Interrogation Depth & Memory (AI Enhancements)
- ✅ **Trust/nervousness meters** per suspect
- ✅ **Contradictions tracking** — caught lies are recorded and displayed
- ✅ **Emotional states** — suspects become defensive, nervous, or cooperative
- ✅ **Cross-reference questioning** — RAG tools enable "But X said..."
- ✅ **Conversation history** — per-suspect tracking in GameState
- ✅ **LLM contradiction detection** — Natural language comparison vs heuristics

### RAG-Powered Gameplay Features
- ✅ **Hint system** — `get_investigation_hint` tool suggests next steps based on what's unexplored
- ✅ **Suspect relationship labels** — Shows who accused/alibi'd whom (🎯 accused, 🛡️ alibi, 💬 mentioned)
- ✅ **Difficulty modifiers for RAG** — Easy/Normal/Hard affects search results and hint detail
- ✅ **Multiple endings** — Investigation scoring determines ending type:
  - 🏆 Perfect Detective (score ≥80%, correct accusation)
  - ✅ Solid Case (score ≥50%, correct accusation)
  - 🎲 Lucky Guess (score <50%, correct accusation)
  - ⚠️ Frame Job (wrong person convicted)
  - 💀 Murderer Escapes (3 wrong accusations)

### UI Improvements
- ✅ **Timeline view** — Visual investigation timeline in main tab
- ✅ **Case File** — Vintage police folder aesthetic document
- ✅ **Dashboard** — Performance and game stats in main tab
- ✅ **Settings tab** — API key management moved to dedicated tab
- ✅ **Sticky record button** — Always visible microphone control
- ✅ **Mobile-responsive tabs** — Icon-only on smallest screens

---

## 🎯 Prioritized Backlog

### High Priority (Low effort, high impact)

| Feature | Mobile Notes |
|---------|--------------|
| **Save/Resume games** — localStorage | Essential for mobile sessions that get interrupted |
| **Quick accusation shortcut** — "I accuse X" parsing | Reduces friction on mobile |

### Medium Priority (Medium effort)

| Feature | Mobile Notes |
|---------|--------------|
| **Ambient audio per location** | Zero UI footprint; enhances atmosphere |
| **Time pressure mode** — optional turn limits | Could show turn counter in header |
| **Voice selection per suspect** — let user pick voices | Settings tab integration |

### Lower Priority (Higher effort or desktop-oriented)

| Feature | Mobile Notes |
|---------|--------------|
| **Evidence Board (drag-drop)** | ⚠️ Desktop-only or needs swipe-based mobile alternative |
| **Animated character portraits** | Performance concerns on older mobile devices |
| **Searchable transcript with filters** | Text-heavy; current timeline may suffice |

### Future Vision (Post-MVP)

- **Cooperative mode** — two players share a mystery
- **Competitive mode** — race to solve
- **Community mysteries** — share seeds/configs
- **Detective customization** — name, backstory, specialty
- **Multiplayer via MCP** — multiple agents playing same mystery

---

## 📱 Mobile-Responsive Guidelines

The current UI uses a 3-column layout (left sidebar, center stage, right sidebar). For mobile:

- **Breakpoint ~768px**: Sidebars collapse; content stacks vertically
- **Breakpoint ~480px**: Icon-only tabs to save horizontal space
- **Accordions**: Already mobile-friendly (collapse to save space)
- **Voice input**: Primary interaction; works great on mobile
- **Touch targets**: Buttons/accordions need adequate tap size (44px minimum)
- **Portrait orientation**: Center stage (speaker + portrait) should remain visible; panels scroll below
- **Sticky record bar**: Always visible at bottom with safe area padding for iOS

---

## 🎨 Aesthetic Polish (When time permits)

- Ambient audio (location-specific soundscapes)
- Tension music that escalates near solution
- Cinematic "case solved" sequence
- Opening noir narration with title card

---

## 🔧 Technical Debt

- [ ] Remove legacy direct API calls (now all MCP)
- [ ] Add UI toggle for MCP vs direct mode (for debugging)
- [ ] Improve error handling when MCP server unavailable
- [ ] Add retry logic for flaky image generation

---

*Last updated: Nov 2025*
