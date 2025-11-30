"""Game state management."""

from typing import Dict, Optional, List, Any
from game.models import Mystery, SuspectState
from mystery_config import MysteryConfig, create_validated_config


class GameState:
    """Manages the state of a game session."""

    def __init__(self):
        self.mystery: Optional[Mystery] = None
        self.system_prompt: Optional[str] = None
        self.messages: List[Dict[str, str]] = []
        self.clues_found: List[str] = []  # Clue descriptions that have been found
        self.clue_ids_found: List[str] = []  # Clue IDs for tracking
        self.suspects_talked_to: List[str] = []
        self.searched_locations: List[str] = []  # Locations that have been searched
        self.wrong_accusations: int = 0
        self.game_over: bool = False
        self.won: bool = False
        # Fast-start fields
        self.mystery_ready: bool = False
        self.premise_setting: Optional[str] = None
        self.premise_victim_name: Optional[str] = None
        self.premise_victim_background: Optional[str] = None
        # Per-session configuration for mystery generation (era, setting, difficulty, tone)
        self.config: MysteryConfig = create_validated_config()
        # Optional tone instruction string injected into system prompts
        self.tone_instruction: Optional[str] = None
        # AI Enhancement Phase 1: Per-suspect state tracking
        # The Game Master (orchestrator) owns this state and passes it to stateless suspects
        self.suspect_states: Dict[str, SuspectState] = {}
        self.current_turn: int = 0
        # Per-location visual descriptions for scene generation (name -> rich description)
        self.location_descriptions: Dict[str, str] = {}
        
        # Voice-First Character Generation (Session Cache)
        # Voices are fetched BEFORE character generation so LLM can create 
        # characters that match available voices
        self.available_voices: List[Any] = []  # List of Voice objects
        self.voice_summary: str = ""  # Formatted summary for LLM
        self.voices_fetched: bool = False
        self.voice_mode: str = "pending"  # pending, full, text_only (silent film mode)
        self.voice_fetch_error: Optional[str] = None
        self.voice_diversity_stats: Dict = {}  # Stats for UI display
        # Per-game Game Master voice (picked from available ElevenLabs voices)
        self.game_master_voice_id: Optional[str] = None
        
        # Setup wizard state
        self.setup_step: int = 1  # 1 = configure, 2 = casting
        self.setup_ready: bool = False  # True when voices fetched and ready to proceed

    def is_new_game(self, message: str) -> bool:
        """Check if the message indicates a new game."""
        message_lower = message.lower()
        keywords = ["start", "new game", "begin", "play"]
        return any(keyword in message_lower for keyword in keywords)

    def reset_game(self):
        """Reset the game state for a new game."""
        self.mystery = None
        self.system_prompt = None
        self.messages = []
        self.clues_found = []
        self.clue_ids_found = []
        self.suspects_talked_to = []
        self.searched_locations = []
        self.wrong_accusations = 0
        self.game_over = False
        self.won = False
        self.mystery_ready = False
        self.premise_setting = None
        self.premise_victim_name = None
        self.premise_victim_background = None
        self.tone_instruction = None
        # AI Enhancement Phase 1: Reset suspect state tracking
        self.suspect_states = {}
        self.current_turn = 0
        # Reset location descriptions for new mystery
        self.location_descriptions = {}
        # Note: We do NOT reset voice fields here - voices are session-cached
        # and should persist across multiple games in the same session
        # Reset setup state for new game
        self.setup_step = 1
        self.setup_ready = False

    def add_clue(self, clue_id: str, clue_description: str):
        """Add a discovered clue."""
        if clue_id not in self.clue_ids_found:
            self.clue_ids_found.append(clue_id)
            self.clues_found.append(clue_description)

    def add_searched_location(self, location: str):
        """Mark a location as searched."""
        if location not in self.searched_locations:
            self.searched_locations.append(location)

    def add_suspect_talked_to(self, suspect_name: str):
        """Mark a suspect as talked to."""
        if suspect_name not in self.suspects_talked_to:
            self.suspects_talked_to.append(suspect_name)

    def make_accusation(self, accused_name: str) -> bool:
        """Make an accusation. Returns True if correct."""
        if not self.mystery:
            return False

        if accused_name.lower() == self.mystery.murderer.lower():
            self.won = True
            self.game_over = True
            return True
        else:
            self.wrong_accusations += 1
            if self.wrong_accusations >= 3:
                self.game_over = True
            return False

    # =========================================================================
    # Investigation Scoring & Multiple Endings
    # =========================================================================

    def calculate_investigation_score(self) -> dict:
        """Calculate how thorough the investigation was.
        
        Returns a dict with:
        - clues_found: fraction of clues discovered
        - suspects_interviewed: fraction of suspects talked to
        - contradictions_caught: total contradictions caught
        - locations_searched: fraction of locations searched
        - total_score: 0-100 overall investigation quality
        """
        if not self.mystery:
            return {"total_score": 0}
        
        # Clue coverage
        total_clues = len(self.mystery.clues)
        found_clues = len(self.clue_ids_found)
        clue_score = found_clues / total_clues if total_clues > 0 else 0
        
        # Suspect coverage
        total_suspects = len(self.mystery.suspects)
        talked_suspects = len(self.suspects_talked_to)
        suspect_score = talked_suspects / total_suspects if total_suspects > 0 else 0
        
        # Location coverage
        total_locations = len(self.get_available_locations())
        searched_locs = len(self.searched_locations)
        location_score = searched_locs / total_locations if total_locations > 0 else 0
        
        # Contradictions caught (bonus points)
        total_contradictions = sum(
            state.contradictions_caught 
            for state in self.suspect_states.values()
        )
        
        # Weighted total score
        total_score = int(
            (clue_score * 35) +  # Clues worth 35%
            (suspect_score * 30) +  # Interviews worth 30%
            (location_score * 20) +  # Locations worth 20%
            min(total_contradictions * 5, 15)  # Up to 15% bonus for catching lies
        )
        
        return {
            "clues_found": f"{found_clues}/{total_clues}",
            "clues_percent": int(clue_score * 100),
            "suspects_interviewed": f"{talked_suspects}/{total_suspects}",
            "suspects_percent": int(suspect_score * 100),
            "locations_searched": f"{searched_locs}/{total_locations}",
            "locations_percent": int(location_score * 100),
            "contradictions_caught": total_contradictions,
            "total_score": min(total_score, 100),
        }

    def get_ending_type(self) -> str:
        """Determine the ending type based on game outcome and investigation quality.
        
        Returns one of:
        - "perfect_detective": Won with excellent investigation (score >= 80)
        - "solid_case": Won with good investigation (score >= 50)
        - "lucky_guess": Won but with poor investigation (score < 50)
        - "frame_job": Lost but built a case (had evidence against wrong person)
        - "murderer_escapes": Lost with 3 wrong accusations
        """
        score = self.calculate_investigation_score()["total_score"]
        
        if self.won:
            if score >= 80:
                return "perfect_detective"
            elif score >= 50:
                return "solid_case"
            else:
                return "lucky_guess"
        else:
            # Lost the game
            if self.wrong_accusations >= 3:
                return "murderer_escapes"
            else:
                return "gave_up"

    def get_ending_narrative(self) -> str:
        """Get the narrative text for the current ending type."""
        ending = self.get_ending_type()
        score = self.calculate_investigation_score()
        
        narratives = {
            "perfect_detective": (
                "🏆 **PERFECT DETECTIVE**\n\n"
                "Your investigation was masterful. Every clue examined, every witness questioned, "
                "every contradiction exposed. The prosecution has an airtight case, and justice "
                "will be served. The department is already talking about your promotion.\n\n"
                f"Investigation Score: {score['total_score']}%"
            ),
            "solid_case": (
                "✅ **CASE CLOSED**\n\n"
                "You got your killer. The evidence is solid, and the case will hold up in court. "
                "There might be a few loose ends, but the important thing is that the murderer "
                "is behind bars. Well done, detective.\n\n"
                f"Investigation Score: {score['total_score']}%"
            ),
            "lucky_guess": (
                "🎲 **LUCKY BREAK**\n\n"
                "Right person, wrong reasons. You accused the correct killer, but your case "
                "is built on intuition more than evidence. The defense attorney is already "
                "planning appeals. Let's hope your luck holds in court.\n\n"
                f"Investigation Score: {score['total_score']}%"
            ),
            "frame_job": (
                "⚠️ **WRONG PERSON**\n\n"
                "An innocent person sits in a cell tonight. You built a convincing case against "
                "the wrong suspect. Somewhere out there, the real killer is smiling. "
                "This one will haunt you.\n\n"
                f"Investigation Score: {score['total_score']}%"
            ),
            "murderer_escapes": (
                "💀 **THE ONE THAT GOT AWAY**\n\n"
                "Three strikes. The case goes cold. The killer watches from the crowd as you "
                "pack up your notes, knowing they've won. This murder will remain unsolved, "
                "and they'll always know they beat you.\n\n"
                f"Investigation Score: {score['total_score']}%"
            ),
            "gave_up": (
                "📁 **CASE ABANDONED**\n\n"
                "The investigation ends without resolution. The file goes into a drawer, "
                "the victim's family never gets closure, and the killer walks free.\n\n"
                f"Investigation Score: {score['total_score']}%"
            ),
        }
        
        return narratives.get(ending, "The case has concluded.")

    def get_available_locations(self) -> List[str]:
        """Get list of locations from clues."""
        if not self.mystery:
            return []
        return list(set(clue.location for clue in self.mystery.clues))

    def get_suspect_names(self) -> List[str]:
        """Get list of suspect names."""
        if not self.mystery:
            return []
        return [s.name for s in self.mystery.suspects]

    # =========================================================================
    # AI Enhancement Phase 1: Suspect State Management
    # =========================================================================

    def get_suspect_state(self, suspect_name: str) -> SuspectState:
        """Get or create the emotional state for a suspect.
        
        The Game Master owns this state and passes it to stateless suspect agents.
        """
        if suspect_name not in self.suspect_states:
            self.suspect_states[suspect_name] = SuspectState()
        return self.suspect_states[suspect_name]

    def record_interrogation(
        self, suspect_name: str, question: str, answer: str
    ) -> None:
        """Record a conversation exchange with a suspect.
        
        Called after each interrogation to track what was said.
        """
        state = self.get_suspect_state(suspect_name)
        state.conversations.append({
            "question": question,
            "answer": answer,
            "turn": self.current_turn
        })
        self.current_turn += 1

    def update_suspect_emotion(
        self,
        suspect_name: str,
        trust_delta: int = 0,
        nervousness_delta: int = 0,
        caught_contradiction: bool = False
    ) -> None:
        """Update a suspect's emotional state based on the interaction.
        
        Args:
            suspect_name: Name of the suspect
            trust_delta: Change to trust (-/+), clamped to 0-100
            nervousness_delta: Change to nervousness (-/+), clamped to 0-100
            caught_contradiction: If True, increment contradictions_caught
        """
        state = self.get_suspect_state(suspect_name)
        state.trust = max(0, min(100, state.trust + trust_delta))
        state.nervousness = max(0, min(100, state.nervousness + nervousness_delta))
        if caught_contradiction:
            state.contradictions_caught += 1
            # Getting caught in a lie increases nervousness
            state.nervousness = min(100, state.nervousness + 15)

    def get_emotional_instructions(self, suspect_name: str) -> str:
        """Generate behavior instructions based on emotional state.
        
        These instructions are passed to the stateless suspect agent to
        influence how they respond.
        """
        state = self.get_suspect_state(suspect_name)
        instructions = []
        
        # Trust-based behavior
        if state.trust < 30:
            instructions.append(
                "Be defensive and give short, guarded answers. "
                "You don't trust this detective."
            )
        elif state.trust > 70:
            instructions.append(
                "Be more open and forthcoming. You're starting to trust this detective. "
                "Consider sharing your secret if pressed."
            )
        
        # Nervousness-based behavior
        if state.nervousness > 70:
            instructions.append(
                "Show clear signs of stress - speak faster, fidget, avoid eye contact. "
                "You might slip up or contradict yourself slightly."
            )
        elif state.nervousness > 50:
            instructions.append(
                "Be slightly on edge. Pause before answering difficult questions."
            )
        
        # Contradiction history
        if state.contradictions_caught > 0:
            instructions.append(
                f"You've been caught in {state.contradictions_caught} contradiction(s). "
                "Be more careful with your answers, or double down on your story."
            )
        
        return "\n".join(instructions) if instructions else ""

    def format_conversation_history(self, suspect_name: str) -> str:
        """Format a suspect's conversation history for inclusion in prompts.
        
        Returns a formatted string of past exchanges with this suspect.
        """
        state = self.get_suspect_state(suspect_name)
        if not state.conversations:
            return "No previous conversations."
        
        history_lines = []
        for conv in state.conversations:
            history_lines.append(
                f"Turn {conv['turn']}: Detective asked: \"{conv['question']}\"\n"
                f"         You replied: \"{conv['answer']}\""
            )
        return "\n".join(history_lines)

    def get_continue_prompt(self) -> str:
        """Get the system prompt for continuing an existing game.
        
        IMPORTANT: This prompt is carefully structured to HIDE information
        the player hasn't discovered yet. The GM only sees:
        - Undiscovered clue LOCATIONS (not descriptions)
        - Discovered clue FULL details
        - Suspect public info (role, personality, alibi)
        - Suspect secrets are passed to the interrogate tool, NOT shown here
        """
        # If we have a mystery, include suspect profiles so they're always accessible
        if self.mystery:
            # Build enhanced suspect profiles with conversation history and emotional state
            # NOTE: We do NOT include secrets or clue_they_know in the visible prompt
            # Those are passed directly to the interrogate_suspect tool to guide roleplay
            suspect_profiles_list = []
            for s in self.mystery.suspects:
                # Get emotional state and history from Game Master's memory
                suspect_state = self.get_suspect_state(s.name)
                conversation_history = self.format_conversation_history(s.name)
                emotional_instructions = self.get_emotional_instructions(s.name)
                
                # Only include guilt flag for tool usage (not displayed to player)
                profile = f"""
### {s.name}
Role: {s.role}
Personality: {s.personality}
Alibi: "{s.alibi}"
Voice ID: {s.voice_id or 'None'}

EMOTIONAL STATE (pass to tool):
- Trust: {suspect_state.trust}%
- Nervousness: {suspect_state.nervousness}%
- Contradictions caught: {suspect_state.contradictions_caught}

CONVERSATION HISTORY (pass to tool):
{conversation_history}
{f'''
BEHAVIORAL INSTRUCTIONS (pass to tool):
{emotional_instructions}''' if emotional_instructions else ''}"""
                suspect_profiles_list.append(profile)
            
            suspect_profiles = "\n".join(suspect_profiles_list)

            suspect_list = "\n".join(
                [f"- {s.name} ({s.role})" for s in self.mystery.suspects]
            )
            
            # CRITICAL: Split clues into discovered vs undiscovered
            # - Discovered: show full details (player earned this info)
            # - Undiscovered: show ONLY location name (so GM knows where to send player)
            discovered_clues = []
            undiscovered_locations = []
            for c in self.mystery.clues:
                if c.id in self.clue_ids_found:
                    discovered_clues.append(f'- ✓ "{c.id}": {c.description} [Found at: {c.location}]')
                else:
                    # Only show location, not what's there
                    undiscovered_locations.append(f'- "{c.location}" (searchable)')
            
            clue_section = ""
            if discovered_clues:
                clue_section += "## DISCOVERED EVIDENCE\n" + "\n".join(discovered_clues) + "\n\n"
            if undiscovered_locations:
                clue_section += "## SEARCHABLE LOCATIONS (clue details hidden until searched)\n" + "\n".join(undiscovered_locations)

            tone_block = ""
            if self.tone_instruction:
                tone_block = f"""

## TONE
{self.tone_instruction}
"""
            
            # Build progress summary
            progress_summary = f"""
## INVESTIGATION PROGRESS
- Clues found: {len(self.clue_ids_found)}/{len(self.mystery.clues)}
- Suspects interviewed: {len(self.suspects_talked_to)}/{len(self.mystery.suspects)}
- Wrong accusations: {self.wrong_accusations}/3
"""

            return f"""You are the Game Master for an ongoing murder mystery game.

## THE CASE
{self.mystery.setting}

## VICTIM
{self.mystery.victim.name}: {self.mystery.victim.background}

## SUSPECTS (public info only)
{suspect_list}

{clue_section}

{progress_summary}

## SUSPECT PROFILES (for interrogate_suspect tool)
{suspect_profiles}

## YOUR ROLE AS GAME MASTER

CRITICAL RULE: You can ONLY reveal information the player has EARNED through investigation!
- Clues are only revealed when the player SEARCHES the correct location
- Suspect secrets emerge through INTERROGATION, not narration
- Do NOT summarize case details the player hasn't discovered

Handle these actions:

### 1. TALKING TO SUSPECTS
When a player wants to talk to someone:
- Call "interrogate_suspect" tool with suspect name and profile
- The tool handles what the suspect reveals based on trust/nervousness
- Do NOT reveal suspect secrets in your narration - let them emerge through dialogue

### 2. SEARCHING LOCATIONS  
When a player searches somewhere:
- Find the matching location from SEARCHABLE LOCATIONS
- Call "describe_scene_for_image" with just the location_name
- The tool automatically looks up clues and generates the correct response
- Use the tool's output VERBATIM (it includes all necessary markers)

### 3. ACCUSATIONS
When player formally accuses someone:
- Call "make_accusation" tool with suspect name
- Only for FINAL accusations, not theorizing

### IMPORTANT MARKERS:
- [SEARCHED:exact location name] - when player searches
- [CLUE_FOUND:clue_id] - when revealing a clue

## GAME RULES  
- 3 wrong accusations = lose
- Win = name murderer + provide evidence
- NEVER reveal murderer, weapon, or motive until correct accusation
- NEVER reveal clue details until player searches that location
- NEVER reveal suspect secrets - let them emerge through interrogation

{tone_block}

## RESPONSE STYLE
- Keep responses atmospheric and conversational
- Be concise - 2-4 paragraphs max
- ASK for clarification rather than guessing wrong
- Build suspense, don't spoil the mystery!

Continue the investigation based on the player's message."""
        else:
            # Fallback if no mystery (shouldn't happen in normal flow)
            return """You are the Game Master for an ongoing murder mystery game.

The game is in progress. Story details are in your conversation memory.

## YOUR ROLE
1. TALK to suspect → Use "Interrogate Suspect" tool with full profile
2. SEARCH location → Describe findings based on clues in memory
3. ACCUSATION → Check against the murderer from memory

## GAME RULES  
- 3 wrong accusations = lose
- Win = name murderer + provide evidence
- Never reveal murderer until correct accusation

Continue the investigation based on the player's message."""
