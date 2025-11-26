"""Data models for the murder mystery game."""

from typing import List, Optional
from pydantic import BaseModel, Field


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
        description="Age category for voice matching (young/middle_aged/old). Not displayed to players.",
    )
    nationality: Optional[str] = Field(
        default=None,
        description="Nationality/accent for voice matching (american/british/australian/etc). Not displayed to players.",
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
