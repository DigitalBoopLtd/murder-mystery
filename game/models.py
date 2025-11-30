"""Data models for the murder mystery game."""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class SuspectState(BaseModel):
    """Tracked emotional state and conversation history for a suspect.
    
    This is owned by the Game Master (orchestrator) and passed to stateless
    suspect agents as context. Suspects don't store their own state.
    """
    
    trust: int = Field(default=50, ge=0, le=100, description="0=hostile, 100=confiding")
    nervousness: int = Field(default=30, ge=0, le=100, description="Increases when pressed")
    conversations: List[Dict[str, str]] = Field(
        default_factory=list,
        description="List of {question, answer, turn} exchanges"
    )
    contradictions_caught: int = Field(default=0, description="Times caught in a lie")


class Victim(BaseModel):
    """Victim information."""

    name: str
    background: str = Field(
        description="Who they were, why someone might want them dead"
    )


class Suspect(BaseModel):
    """Suspect information."""

    name: str
    role: str = Field(description="Relationship to victim")
    personality: str = Field(description="2-3 key traits")
    alibi: str
    secret: str = Field(description="What they are hiding")
    clue_they_know: str = Field(description="Info they share if asked right questions")
    isGuilty: bool
    gender: Optional[str] = Field(
        default=None,
        description="Gender for voice matching (male/female). Not displayed to players.",
    )
    age: Optional[str] = Field(
        default=None,
        description="Age for voice matching (young/middle_aged/old). Hidden.",
    )
    nationality: Optional[str] = Field(
        default=None,
        description="Nationality/accent for voice matching. Hidden.",
    )
    voice_id: Optional[str] = Field(
        default=None, description="ElevenLabs voice ID for TTS"
    )
    portrait_path: Optional[str] = Field(
        default=None, description="Path to generated portrait image"
    )


class Clue(BaseModel):
    """Clue information."""

    id: str
    description: str
    location: str
    significance: str


class MysteryPremise(BaseModel):
    """Lightweight premise used for fast startup."""

    setting: str = Field(
        description="Brief evocative description of the location and occasion"
    )
    victim_name: str = Field(description="Victim's full name")
    victim_background: str = Field(
        description=(
            "1-2 sentence background about who they are and why someone "
            "might want them dead"
        )
    )


class Mystery(BaseModel):
    """Complete murder mystery scenario."""

    setting: str = Field(
        description="Brief evocative description of location and occasion"
    )
    victim: Victim
    murderer: str = Field(description="Full name of the guilty suspect")
    weapon: str
    motive: str
    suspects: List[Suspect] = Field(min_length=4, max_length=4)
    clues: List[Clue] = Field(min_length=5, max_length=5)


# =============================================================================
# STRUCTURED OUTPUT MODELS FOR GAME MASTER RESPONSES
# =============================================================================

class GameAction(BaseModel):
    """A game action detected in the GM's response.
    
    These replace the fragile regex markers like [SEARCHED:], [ACCUSATION:], etc.
    """
    
    action_type: str = Field(
        description="Type of action: 'search_location', 'interrogate_suspect', 'reveal_clue', 'make_accusation', 'general_narration'"
    )
    target: Optional[str] = Field(
        default=None,
        description="Target of action (location name, suspect name, or clue ID)"
    )
    clue_ids_revealed: List[str] = Field(
        default_factory=list,
        description="List of clue IDs revealed during this action (if any)"
    )


class SceneBrief(BaseModel):
    """Scene description for image generation."""
    
    location: str = Field(description="The exact location name")
    visual_description: str = Field(description="Rich visual description for image generation")
    camera_angle: str = Field(
        default="medium shot",
        description="Camera angle: 'extreme close-up', 'close-up', 'medium shot', 'wide shot', 'establishing shot'"
    )
    mood: str = Field(default="mysterious", description="Atmosphere/mood of the scene")
    focus_element: Optional[str] = Field(
        default=None,
        description="Primary element to focus on (e.g., 'torn letter', 'bloody knife')"
    )


class GameMasterResponse(BaseModel):
    """Structured response from the Game Master.
    
    This replaces the fragile regex parsing of markers like [SEARCHED:], [ACCUSATION:], etc.
    The LLM returns structured data that we can process directly.
    """
    
    narrative: str = Field(
        description="The spoken narrative for the player. This is what gets TTS'd and displayed."
    )
    
    speaker: Optional[str] = Field(
        default=None,
        description="Who is speaking: None for Game Master, or suspect name if a suspect is responding"
    )
    
    action: Optional[GameAction] = Field(
        default=None,
        description="Game action performed (search, interrogation, accusation, etc.)"
    )
    
    scene_brief: Optional[SceneBrief] = Field(
        default=None,
        description="Scene details for image generation (only when searching a location)"
    )
    
    accusation_result: Optional[bool] = Field(
        default=None,
        description="True if accusation was correct, False if wrong, None if no accusation"
    )


class StructuredToolOutput(BaseModel):
    """Wrapper for tool outputs that need structured parsing.
    
    Tools can return this to provide structured data back to the parser
    instead of relying on regex markers in text.
    """
    
    tool_name: str
    narrative: str = Field(description="The narrative text to speak/display")
    speaker: Optional[str] = Field(default=None, description="Who is speaking")
    action: Optional[GameAction] = Field(default=None)
    scene_brief: Optional[SceneBrief] = Field(default=None)
    raw_data: Optional[Dict] = Field(default=None, description="Additional tool-specific data")
