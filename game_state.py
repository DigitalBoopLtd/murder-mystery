"""Game state management."""
from typing import Dict, Optional, List
from models import Mystery


class GameState:
    """Manages the state of a game session."""
    
    def __init__(self):
        self.mystery: Optional[Mystery] = None
        self.system_prompt: Optional[str] = None
        self.messages: List[Dict[str, str]] = []
        self.clues_found: List[str] = []
        self.suspects_talked_to: List[str] = []
        self.wrong_accusations: int = 0
        self.game_over: bool = False
        self.won: bool = False
    
    def is_new_game(self, message: str) -> bool:
        """Check if the message indicates a new game."""
        message_lower = message.lower()
        keywords = ['start', 'new game', 'begin', 'play']
        return any(keyword in message_lower for keyword in keywords)
    
    def get_continue_prompt(self) -> str:
        """Get the system prompt for continuing an existing game."""
        # If we have a mystery, include suspect profiles so they're always accessible
        if self.mystery:
            suspect_profiles = "\n".join([
                f"""
### {s.name}
Role: {s.role}
Personality: {s.personality}
Alibi: "{s.alibi}"
Secret: {s.secret}
Will share if asked: {s.clue_they_know}
Guilty: {s.isGuilty}{f'''
Murder details: Used {self.mystery.weapon} because {self.mystery.motive}''' if s.isGuilty else ''}"""
                for s in self.mystery.suspects
            ])
            
            suspect_list = "\n".join([f"- {s.name} ({s.role})" for s in self.mystery.suspects])
            clue_list = "\n".join([f"- \"{c.id}\": {c.description} [Location: {c.location}]" for c in self.mystery.clues])
            
            return f"""You are the Game Master for an ongoing murder mystery game.

The game is already in progress. All story details (victim, suspects, clues, and the secret murderer) are in your conversation memory from earlier in this session.

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
1. When player wants to TALK to a suspect → Use "Interrogate Suspect" tool. IMPORTANT: Pass the suspect's FULL PROFILE from above.
2. When player wants to SEARCH a location → Describe findings based on clues in memory
3. When player makes ACCUSATION → Check against the murderer from memory
4. Track game state (clues found, suspects talked to)

## GAME RULES  
- 3 wrong accusations = lose
- Win = name murderer + provide evidence
- Never reveal murderer until correct accusation

## SECRET (NEVER REVEAL)
Murderer: {self.mystery.murderer}
Weapon: {self.mystery.weapon}
Motive: {self.mystery.motive}

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

