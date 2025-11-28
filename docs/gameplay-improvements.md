# 🎮 Gameplay Improvement Ideas

This document tracks potential enhancements to the murder mystery game. Items are prioritized with mobile-responsive design in mind.

---

## ✅ Completed

### Interrogation Depth & Memory (AI Enhancements)
- ✅ **Trust/nervousness meters** per suspect
- ✅ **Contradictions tracking** – caught lies are recorded and displayed
- ✅ **Emotional states** – suspects become defensive, nervous, or cooperative
- ✅ **Cross-reference questioning** – RAG tools enable "But X said..."
- ✅ **Conversation history** – per-suspect tracking in GameState
- ✅ **Detective Notebook** – interrogation timeline with contradiction highlights

### RAG-Powered Gameplay Features
- ✅ **Hint system** – `get_investigation_hint` tool suggests next steps based on what's unexplored
- ✅ **Suspect relationship labels** – Shows who accused/alibi'd whom (🎯 accused, 🛡️ alibi, 💬 mentioned)
- ✅ **Difficulty modifiers for RAG** – Easy/Normal/Hard affects search results and hint detail
- ✅ **Multiple endings** – Investigation scoring determines ending type:
  - 🏆 Perfect Detective (score ≥80%, correct accusation)
  - ✅ Solid Case (score ≥50%, correct accusation)
  - 🎲 Lucky Guess (score <50%, correct accusation)
  - ⚠️ Frame Job (wrong person convicted)
  - 💀 Murderer Escapes (3 wrong accusations)

---

## 🎯 Prioritized Backlog

### High Priority (Low effort, high impact)

| Feature | Mobile Notes |
|---------|--------------|
| **Save/Resume games** – localStorage | Essential for mobile sessions that get interrupted |

### Medium Priority (Medium effort)

| Feature | Mobile Notes |
|---------|--------------|
| **Ambient audio per location** | Zero UI footprint; enhances atmosphere |
| **Time pressure mode** – optional turn limits | Could show turn counter in header |

### Lower Priority (Higher effort or desktop-oriented)

| Feature | Mobile Notes |
|---------|--------------|
| **Evidence Board (drag-drop)** | ⚠️ Desktop-only or needs swipe-based mobile alternative |
| **Suspect Relationship Map (diagram)** | ⚠️ Complex; relationship labels now show this data in simpler form |
| **Animated character portraits** | Performance concerns on older mobile devices |
| **Searchable transcript with filters** | Text-heavy; current notebook may suffice |

### Future Vision (Post-MVP)

- **Cooperative mode** – two players share a mystery
- **Competitive mode** – race to solve
- **Community mysteries** – share seeds/configs
- **Detective customization** – name, backstory, specialty

---

## 📱 Mobile-Responsive Guidelines

The current UI uses a 3-column layout (left sidebar, center stage, right sidebar). For mobile:

- **Breakpoint ~768px**: Sidebars should stack below center stage or become slide-out drawers
- **Accordions**: Already mobile-friendly (collapse to save space)
- **Voice input**: Primary interaction; works great on mobile
- **Touch targets**: Buttons/accordions need adequate tap size (44px minimum)
- **Portrait orientation**: Center stage (speaker + portrait) should remain visible; panels scroll below

---

## 🎨 Aesthetic Polish (When time permits)

- Ambient audio (location-specific soundscapes)
- Tension music that escalates near solution
- Cinematic "case solved" sequence
- Opening noir narration

---

*Last updated after completing AI Enhancement Phases 1-3*
