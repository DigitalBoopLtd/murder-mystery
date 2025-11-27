"""Game state management."""

from typing import Dict, Optional, List
from models import Mystery


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

    def get_continue_prompt(self) -> str:
        """Get the system prompt for continuing an existing game."""
        # If we have a mystery, include suspect profiles so they're always accessible
        if self.mystery:
            suspect_profiles = "\n".join(
                [
                    f"""
### {s.name}
Role: {s.role}
Personality: {s.personality}
Alibi: "{s.alibi}"
Secret: {s.secret}
Will share if asked: {s.clue_they_know}
Guilty: {s.isGuilty}
Voice ID: {s.voice_id or 'None'}{f'''
Murder details: Used {self.mystery.weapon} because {self.mystery.motive}''' if s.isGuilty else ''}"""
                    for s in self.mystery.suspects
                ]
            )

            suspect_list = "\n".join(
                [f"- {s.name} ({s.role})" for s in self.mystery.suspects]
            )
            clue_list = "\n".join(
                [
                    f'- "{c.id}": {c.description} [Location: {c.location}]'
                    for c in self.mystery.clues
                ]
            )

            return f"""You are the Game Master for an ongoing murder mystery game.

## THE CASE
{self.mystery.setting}

## VICTIM
{self.mystery.victim.name}: {self.mystery.victim.background}

## SUSPECTS
{suspect_list}

## CLUES (reveal when player searches correct location)
{clue_list}

## SUSPECT PROFILES (use when calling Interrogate Suspect tool)
{suspect_profiles}

## YOUR ROLE
1. When player wants to TALK/SPEAK/INTERROGATE a suspect → You MUST call the "interrogate_suspect" tool. Pass the suspect's name, their FULL PROFILE from above, the player's question, and their voice_id.
2. When player wants to SEARCH a location → Describe findings. If they search the right location, reveal the clue with atmosphere!
3. When player makes ACCUSATION → Check against the murderer

CRITICAL: For ANY request involving talking to a suspect, you MUST use the interrogate_suspect tool. Do NOT respond directly as the suspect yourself.

## GAME RULES  
- 3 wrong accusations = lose
- Win = name murderer + provide evidence
- Never reveal murderer until correct accusation

## SECRET (NEVER REVEAL)
Murderer: {self.mystery.murderer}
Weapon: {self.mystery.weapon}
Motive: {self.mystery.motive}

## RESPONSE STYLE - VERY IMPORTANT
The player can already see suspects, locations, objectives, and found clues in sidebar cards on their screen.
- Do NOT list out suspects, locations, or clues - they're visible in the UI
- Keep responses focused, atmospheric, and conversational
- When searching: Describe what they find narratively, don't just state "you found clue X"
- When interrogating: Let the suspect's response speak for itself
- Be concise - 2-4 paragraphs max

Continue the investigation based on the player's message."""
        else:
            # Fallback if no mystery (shouldn't happen in normal flow)
            return """You are the Game Master for an ongoing murder mystery game.

The game is already in progress. All story details (victim, suspects, clues, and the secret murderer) are in your conversation memory from earlier in this session.

## YOUR ROLE
1. When player wants to TALK to a suspect → Use "Interrogate Suspect" tool. Pass the suspect's full profile from memory.
2. When player wants to SEARCH a location → Describe findings based on clues in memory
3. When player makes ACCUSATION → Check against the murderer from memory
4. Track game state

## GAME RULES  
- 3 wrong accusations = lose
- Win = name murderer + provide evidence
- Never reveal murderer until correct accusation

Continue the investigation based on the player's message."""
