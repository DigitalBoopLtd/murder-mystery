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
    secret_revealed: bool = Field(default=False, description="True when they've revealed their secret/motive")


# =============================================================================
# ACCUSATION TRACKING
# =============================================================================

class AccusationRequirements(BaseModel):
    """Checklist of requirements for an iron-cast accusation.
    
    All of these should be True for a successful accusation.
    """
    
    # Core requirements
    has_minimum_clues: bool = Field(default=False, description="Found at least 2 clues")
    alibi_disproven: bool = Field(default=False, description="Found evidence that contradicts their alibi")
    motive_established: bool = Field(default=False, description="Discovered a motive for the accused")
    opportunity_proven: bool = Field(default=False, description="Proved they had opportunity (time/place)")
    
    # Evidence details
    contradicting_clue_ids: List[str] = Field(default_factory=list, description="Clues that disprove alibi")
    witness_contradictions: List[str] = Field(default_factory=list, description="Witnesses who contradict alibi")
    motive_evidence: Optional[str] = Field(default=None, description="What established the motive")
    
    def get_missing_requirements(self) -> List[str]:
        """Get list of requirements not yet met."""
        missing = []
        if not self.has_minimum_clues:
            missing.append("Need to find at least 2 clues")
        if not self.alibi_disproven:
            missing.append("Need to disprove the suspect's alibi (find contradicting evidence or witnesses)")
        if not self.motive_established:
            missing.append("Need to establish a motive")
        if not self.opportunity_proven:
            missing.append("Need to prove they had the opportunity")
        return missing
    
    def is_iron_cast(self) -> bool:
        """Check if all requirements are met for an iron-cast accusation."""
        return self.has_minimum_clues and self.alibi_disproven
    
    def get_strength_score(self) -> int:
        """Calculate case strength as percentage (0-100)."""
        score = 0
        if self.has_minimum_clues:
            score += 25
        if self.alibi_disproven:
            score += 40  # Most important!
        if self.motive_established:
            score += 20
        if self.opportunity_proven:
            score += 15
        return score


class AccusationAttempt(BaseModel):
    """Record of a single accusation attempt."""
    
    turn: int = Field(description="Game turn when accusation was made")
    accused_name: str = Field(description="Name of the suspect accused")
    evidence_cited: str = Field(default="", description="What evidence the player cited")
    was_correct_suspect: bool = Field(default=False, description="Was this actually the murderer?")
    had_sufficient_evidence: bool = Field(default=False, description="Did they have enough evidence?")
    requirements_met: AccusationRequirements = Field(
        default_factory=AccusationRequirements,
        description="Which requirements were met at time of accusation"
    )
    failure_reason: Optional[str] = Field(
        default=None,
        description="Why the accusation failed (if it failed)"
    )
    outcome: str = Field(
        default="pending",
        description="'success', 'wrong_suspect', 'insufficient_evidence', or 'pending'"
    )


class Victim(BaseModel):
    """Victim information."""

    name: str
    background: str = Field(
        description="Who they were, why someone might want them dead"
    )


# =============================================================================
# ALIBI VERIFICATION SYSTEM
# =============================================================================

class AlibiClaim(BaseModel):
    """A structured alibi that can be verified or disproven.
    
    Every suspect has an alibi. Innocent suspects have TRUE alibis.
    The murderer has a FALSE alibi with specific holes that can be discovered.
    """
    
    time_claimed: str = Field(
        description="Time range claimed: e.g., '8:00 PM - 9:30 PM'"
    )
    location_claimed: str = Field(
        description="Where they claim to have been"
    )
    activity: str = Field(
        description="What they claim to have been doing"
    )
    corroborator: Optional[str] = Field(
        default=None,
        description="Name of another suspect who can verify (or contradict) this alibi"
    )
    corroboration_type: str = Field(
        default="none",
        description="How alibi can be verified: 'witness' (another suspect), 'physical' (clue), 'none' (alone)"
    )
    is_truthful: bool = Field(
        default=True,
        description="True if this alibi is real, False if fabricated (murderer only)"
    )
    # For false alibis only - how to catch the lie
    contradiction_clue_id: Optional[str] = Field(
        default=None,
        description="ID of clue that disproves this alibi (for false alibis)"
    )
    actual_whereabouts: Optional[str] = Field(
        default=None,
        description="Where they ACTUALLY were (for false alibis - committing the murder)"
    )


class WitnessStatement(BaseModel):
    """What one suspect claims to have seen about another.
    
    Used for corroboration - if A says they saw B, B's alibi should match.
    If the murderer claims they were with someone, that person's statement
    should contradict them.
    """
    
    witness: str = Field(description="Name of the suspect making the statement")
    subject: str = Field(description="Name of the suspect they're talking about")
    claim: str = Field(
        description="What they claim to have seen: 'I saw Eleanor in the library at 8:30'"
    )
    time_of_sighting: str = Field(description="When they claim to have seen them")
    location_of_sighting: str = Field(description="Where they claim to have seen them")
    is_truthful: bool = Field(
        default=True,
        description="True if this witness statement is accurate"
    )


class Suspect(BaseModel):
    """Suspect information."""

    name: str
    role: str = Field(description="Relationship to victim")
    personality: str = Field(description="2-3 key traits")
    alibi: str = Field(description="Simple alibi statement for backward compatibility")
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
    location_hint: Optional[str] = Field(
        default=None,
        description="A location this suspect reveals when interrogated. Unlocks that location for searching.",
    )
    # Enhanced alibi verification system
    structured_alibi: Optional[AlibiClaim] = Field(
        default=None,
        description="Detailed alibi with verification method"
    )
    witness_statements: List[WitnessStatement] = Field(
        default_factory=list,
        description="What this suspect claims to have seen about others"
    )


class Clue(BaseModel):
    """Clue information with alibi verification capabilities."""

    id: str
    description: str
    location: str
    significance: str
    # Alibi verification fields
    contradicts_alibi_of: Optional[str] = Field(
        default=None,
        description="Name of suspect whose alibi this clue DISPROVES"
    )
    supports_alibi_of: Optional[str] = Field(
        default=None,
        description="Name of suspect whose alibi this clue CONFIRMS"
    )
    timeline_implication: Optional[str] = Field(
        default=None,
        description="What this clue tells us about timing: e.g., 'Victim was alive at 8:15 PM'"
    )
    evidence_type: str = Field(
        default="circumstantial",
        description="Type: 'physical' (forensic), 'documentary' (letters/records), 'circumstantial'"
    )


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


class MurderMethod(BaseModel):
    """Details of how the murder was committed - required for valid accusation."""
    
    weapon: str = Field(description="The murder weapon")
    time_of_death: str = Field(description="Approximate time: e.g., '8:30 PM'")
    location_of_murder: str = Field(description="Where it happened")
    opportunity: str = Field(
        description="How the murderer had the opportunity (e.g., 'while others were at dinner')"
    )
    evidence_trail: List[str] = Field(
        default_factory=list,
        description="Clue IDs that prove this method"
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
    # Enhanced verification system
    murder_method: Optional[MurderMethod] = Field(
        default=None,
        description="Detailed method for evidence-based accusation"
    )
    witness_statements: List[WitnessStatement] = Field(
        default_factory=list,
        description="All witness statements across suspects for easy corroboration lookup"
    )
    
    def get_alibi_contradictions(self, suspect_name: str) -> List[str]:
        """Get clue IDs that contradict a suspect's alibi."""
        return [c.id for c in self.clues if c.contradicts_alibi_of == suspect_name]
    
    def get_alibi_support(self, suspect_name: str) -> List[str]:
        """Get clue IDs that support a suspect's alibi."""
        return [c.id for c in self.clues if c.supports_alibi_of == suspect_name]
    
    def get_witness_statements_about(self, suspect_name: str) -> List[WitnessStatement]:
        """Get all witness statements about a specific suspect."""
        return [ws for ws in self.witness_statements if ws.subject == suspect_name]
    
    def get_witness_statements_by(self, suspect_name: str) -> List[WitnessStatement]:
        """Get all witness statements made by a specific suspect."""
        return [ws for ws in self.witness_statements if ws.witness == suspect_name]


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
