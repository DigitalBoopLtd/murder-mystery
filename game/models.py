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
