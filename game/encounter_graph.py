"""Encounter Graph - The authoritative truth of who saw whom, where, and when.

This module implements a graph-based approach to mystery consistency:

1. **Nodes** represent person-location-time tuples
2. **Edges** represent sightings (who saw whom)
3. **Alibis** are derived FROM the graph (not generated independently)
4. **Clues** reference the graph (proving or disproving positions)

This ensures logical consistency - if A says "I saw B at the library",
B's alibi MUST place them at the library at that time.

The graph is the SINGLE SOURCE OF TRUTH. Everything else derives from it.

Architecture:
- EncounterGraph is generated FIRST (during skeleton generation)
- Suspects, alibis, and clues are then derived from the graph
- The MysteryOracle (separate service) holds this truth
- The Game Master agent NEVER sees the full graph - only player-discovered info
"""

from typing import Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, Field
from enum import Enum


class TimeSlot(str, Enum):
    """Discrete time slots for the mystery timeline.
    
    Using discrete slots instead of exact times makes
    verification simpler and more robust.
    """
    EARLY_EVENING = "early_evening"      # 6:00-7:30 PM - Pre-event
    DINNER_START = "dinner_start"        # 7:30-8:00 PM - Gathering
    DINNER_MAIN = "dinner_main"          # 8:00-8:45 PM - Main course
    CRITICAL_WINDOW = "critical_window"  # 8:45-9:15 PM - MURDER HAPPENS HERE
    POST_DISCOVERY = "post_discovery"    # 9:15-9:45 PM - Body found
    LATE_EVENING = "late_evening"        # 9:45 PM+ - Police arrive


class LocationNode(BaseModel):
    """A physical location in the mystery setting."""
    id: str = Field(description="Unique location ID like 'library' or 'garden'")
    name: str = Field(description="Human-readable name")
    description: str = Field(description="Brief description of the location")
    is_public: bool = Field(default=True, description="Can multiple people be here?")
    is_murder_scene: bool = Field(default=False, description="Where the murder occurred")
    adjacent_to: List[str] = Field(default_factory=list, description="IDs of adjacent locations")


class PresenceNode(BaseModel):
    """A person's presence at a location during a time slot.
    
    This is the fundamental unit of the encounter graph.
    """
    person_role: str = Field(description="Role of the person (e.g., 'the jealous partner')")
    location_id: str = Field(description="Where they were")
    time_slot: TimeSlot = Field(description="When they were there")
    activity: str = Field(description="What they were doing")
    is_truthful: bool = Field(
        default=True, 
        description="True if this is where they actually were. False for the murderer's fake position."
    )
    # For the murderer only - their ACTUAL position during the critical window
    actual_location_id: Optional[str] = Field(
        default=None,
        description="If is_truthful=False, where they ACTUALLY were (murder scene)"
    )


class SightingEdge(BaseModel):
    """A directed sighting: one person saw another.
    
    If Alice saw Bob, there's an edge from Alice -> Bob.
    Sightings can be:
    - Mutual (both saw each other)
    - One-way (Alice saw Bob, but Bob didn't notice Alice)
    """
    observer_role: str = Field(description="Who did the seeing")
    subject_role: str = Field(description="Who was seen")
    location_id: str = Field(description="Where the sighting occurred")
    time_slot: TimeSlot = Field(description="When the sighting occurred")
    is_mutual: bool = Field(default=False, description="Did both parties see each other?")
    is_truthful: bool = Field(
        default=True,
        description="Is this sighting accurate? Murderer might falsely claim sightings."
    )
    claim_text: str = Field(
        default="",
        description="Natural language claim: 'I saw [subject] in the [location] around [time]'"
    )


class EncounterGraph(BaseModel):
    """The complete graph of all encounters during the mystery.
    
    This is the SINGLE SOURCE OF TRUTH for:
    - Where everyone was at each time
    - Who saw whom
    - What alibis are valid/false
    - What clues can prove/disprove
    """
    
    # The locations in the mystery
    locations: List[LocationNode] = Field(default_factory=list)
    
    # All person-location-time positions
    presences: List[PresenceNode] = Field(default_factory=list)
    
    # All sightings (who saw whom)
    sightings: List[SightingEdge] = Field(default_factory=list)
    
    # Quick lookups
    murderer_role: str = Field(default="", description="Role of the murderer")
    murder_time: TimeSlot = Field(default=TimeSlot.CRITICAL_WINDOW)
    murder_location_id: str = Field(default="")
    
    def get_presence(self, role: str, time_slot: TimeSlot) -> Optional[PresenceNode]:
        """Get where a person claims to be at a given time."""
        for p in self.presences:
            if p.person_role == role and p.time_slot == time_slot:
                return p
        return None
    
    def get_actual_presence(self, role: str, time_slot: TimeSlot) -> Optional[PresenceNode]:
        """Get where a person ACTUALLY was (resolves lies)."""
        presence = self.get_presence(role, time_slot)
        if presence and not presence.is_truthful and presence.actual_location_id:
            # Return a synthetic presence with actual location
            return PresenceNode(
                person_role=role,
                location_id=presence.actual_location_id,
                time_slot=time_slot,
                activity="committing the murder",
                is_truthful=True,
            )
        return presence
    
    def get_sightings_by(self, observer_role: str) -> List[SightingEdge]:
        """Get all sightings made by a person."""
        return [s for s in self.sightings if s.observer_role == observer_role]
    
    def get_sightings_of(self, subject_role: str) -> List[SightingEdge]:
        """Get all sightings of a person (by others)."""
        return [s for s in self.sightings if s.subject_role == subject_role]
    
    def get_people_at_location(self, location_id: str, time_slot: TimeSlot) -> List[str]:
        """Get all people (actually) at a location during a time slot."""
        people = []
        for p in self.presences:
            if p.time_slot == time_slot:
                actual_loc = p.actual_location_id if not p.is_truthful else p.location_id
                if actual_loc == location_id:
                    people.append(p.person_role)
        return people
    
    def can_person_see_person(
        self, 
        observer_role: str, 
        subject_role: str, 
        time_slot: TimeSlot
    ) -> Tuple[bool, str]:
        """Check if one person COULD have seen another (based on actual positions).
        
        Returns (possible, reason).
        """
        observer_pos = self.get_actual_presence(observer_role, time_slot)
        subject_pos = self.get_actual_presence(subject_role, time_slot)
        
        if not observer_pos or not subject_pos:
            return False, "One or both people have no recorded position"
        
        if observer_pos.location_id == subject_pos.location_id:
            return True, f"Both at {observer_pos.location_id}"
        
        # Check if locations are adjacent
        observer_loc = next((l for l in self.locations if l.id == observer_pos.location_id), None)
        if observer_loc and subject_pos.location_id in observer_loc.adjacent_to:
            return True, f"Adjacent locations ({observer_pos.location_id} -> {subject_pos.location_id})"
        
        return False, f"Different locations: {observer_pos.location_id} vs {subject_pos.location_id}"
    
    def validate_sighting(self, sighting: SightingEdge) -> Tuple[bool, str]:
        """Validate that a sighting is physically possible.
        
        A sighting is valid if:
        1. The observer was ACTUALLY at the claimed location
        2. The subject was ACTUALLY at the claimed location
        3. Both were there at the same time
        """
        observer_actual = self.get_actual_presence(sighting.observer_role, sighting.time_slot)
        subject_actual = self.get_actual_presence(sighting.subject_role, sighting.time_slot)
        
        if not observer_actual:
            return False, f"Observer {sighting.observer_role} has no position at {sighting.time_slot}"
        if not subject_actual:
            return False, f"Subject {sighting.subject_role} has no position at {sighting.time_slot}"
        
        if observer_actual.location_id != sighting.location_id:
            return False, f"Observer was actually at {observer_actual.location_id}, not {sighting.location_id}"
        if subject_actual.location_id != sighting.location_id:
            return False, f"Subject was actually at {subject_actual.location_id}, not {sighting.location_id}"
        
        return True, "Sighting is physically possible"
    
    def get_alibi_verification_status(self, role: str) -> Dict[str, any]:
        """Check how a person's alibi can be verified or disproven.
        
        Returns info about:
        - Is their alibi truthful?
        - Who (if anyone) can corroborate it?
        - What evidence could prove/disprove it?
        """
        critical_presence = self.get_presence(role, TimeSlot.CRITICAL_WINDOW)
        if not critical_presence:
            return {"status": "unknown", "reason": "No alibi for critical time"}
        
        # Find sightings that could verify this alibi
        corroborating_sightings = []
        contradicting_sightings = []
        
        for s in self.sightings:
            if s.time_slot == TimeSlot.CRITICAL_WINDOW and s.subject_role == role:
                if s.is_truthful:
                    if s.location_id == critical_presence.location_id:
                        corroborating_sightings.append(s)
                    else:
                        contradicting_sightings.append(s)
        
        return {
            "is_truthful": critical_presence.is_truthful,
            "claimed_location": critical_presence.location_id,
            "claimed_activity": critical_presence.activity,
            "actual_location": critical_presence.actual_location_id if not critical_presence.is_truthful else critical_presence.location_id,
            "corroborators": [s.observer_role for s in corroborating_sightings],
            "contradictors": [s.observer_role for s in contradicting_sightings],
        }
    
    def derive_alibi_claim(self, role: str) -> Dict[str, str]:
        """Derive an alibi claim from the graph.
        
        This ensures alibis are CONSISTENT with the graph.
        """
        presence = self.get_presence(role, TimeSlot.CRITICAL_WINDOW)
        if not presence:
            return {
                "time_claimed": "around 9 PM",
                "location_claimed": "unknown",
                "activity": "I don't remember exactly",
                "corroborator": None,
                "is_truthful": True,
            }
        
        # Find anyone who saw this person (and whose sighting is truthful)
        corroborator = None
        for s in self.sightings:
            if (s.subject_role == role and 
                s.time_slot == TimeSlot.CRITICAL_WINDOW and 
                s.is_truthful and
                s.location_id == presence.location_id):
                corroborator = s.observer_role
                break
        
        return {
            "time_claimed": "around 9 PM",  # Covers CRITICAL_WINDOW
            "location_claimed": presence.location_id,
            "activity": presence.activity,
            "corroborator": corroborator,
            "is_truthful": presence.is_truthful,
        }
    
    def get_clue_opportunities(self) -> List[Dict[str, any]]:
        """Identify opportunities for clues based on the graph.
        
        Clues can:
        1. Prove someone WAS at a location (supports alibi)
        2. Prove someone WAS NOT at a location (contradicts alibi)
        3. Show timeline evidence (when things happened)
        """
        opportunities = []
        
        # For the murderer - their false alibi creates clue opportunities
        murderer_presence = self.get_presence(self.murderer_role, TimeSlot.CRITICAL_WINDOW)
        if murderer_presence and not murderer_presence.is_truthful:
            # Clue opportunity 1: Evidence at claimed location showing they WEREN'T there
            opportunities.append({
                "type": "absence_evidence",
                "location": murderer_presence.location_id,
                "target_role": self.murderer_role,
                "description": f"Evidence showing {self.murderer_role} was NOT at {murderer_presence.location_id}",
                "proves": "alibi_false",
            })
            
            # Clue opportunity 2: Evidence at murder scene showing they WERE there
            if murderer_presence.actual_location_id:
                opportunities.append({
                    "type": "presence_evidence",
                    "location": murderer_presence.actual_location_id,
                    "target_role": self.murderer_role,
                    "description": f"Evidence placing {self.murderer_role} at {murderer_presence.actual_location_id}",
                    "proves": "at_murder_scene",
                })
        
        # For innocent suspects - evidence supporting their alibis
        for presence in self.presences:
            if presence.person_role != self.murderer_role and presence.time_slot == TimeSlot.CRITICAL_WINDOW:
                if presence.is_truthful:
                    opportunities.append({
                        "type": "alibi_support",
                        "location": presence.location_id,
                        "target_role": presence.person_role,
                        "description": f"Evidence confirming {presence.person_role} was at {presence.location_id}",
                        "proves": "alibi_true",
                    })
        
        return opportunities


# =============================================================================
# GRAPH GENERATION OUTPUT MODEL
# =============================================================================

class EncounterGraphDraft(BaseModel):
    """Output from the encounter graph generator.
    
    This is what the LLM generates. It gets validated and converted
    to a full EncounterGraph.
    """
    
    locations: List[Dict[str, str]] = Field(
        description="List of locations with id, name, description, is_murder_scene flag"
    )
    
    timeline: List[Dict[str, str]] = Field(
        description="For each suspect role: where they were at each time slot"
    )
    
    sightings: List[Dict[str, str]] = Field(
        description="List of sightings: observer_role, subject_role, location, time_slot, claim_text"
    )
    
    murderer_role: str = Field(description="Which role is the murderer")
    murder_location: str = Field(description="Location ID where murder occurred")


def build_encounter_graph_from_draft(
    draft: EncounterGraphDraft,
    suspect_roles: List[str],
) -> EncounterGraph:
    """Convert an LLM-generated draft into a validated EncounterGraph.
    
    This ensures all the logical constraints are satisfied.
    """
    # Build locations
    locations = []
    for loc_data in draft.locations:
        loc = LocationNode(
            id=loc_data.get("id", loc_data.get("name", "").lower().replace(" ", "_")),
            name=loc_data.get("name", "Unknown"),
            description=loc_data.get("description", ""),
            is_murder_scene=loc_data.get("is_murder_scene", False),
            is_public=loc_data.get("is_public", True),
            adjacent_to=loc_data.get("adjacent_to", []),
        )
        locations.append(loc)
    
    # Build presences from timeline
    presences = []
    for entry in draft.timeline:
        role = entry.get("role", "")
        for time_slot in TimeSlot:
            location_key = time_slot.value
            if location_key in entry:
                loc_id = entry[location_key]
                activity = entry.get(f"{location_key}_activity", "present")
                is_truthful = role != draft.murderer_role or time_slot != TimeSlot.CRITICAL_WINDOW
                
                presence = PresenceNode(
                    person_role=role,
                    location_id=loc_id,
                    time_slot=time_slot,
                    activity=activity,
                    is_truthful=is_truthful,
                    actual_location_id=draft.murder_location if not is_truthful else None,
                )
                presences.append(presence)
    
    # Build sightings
    sightings = []
    for sight_data in draft.sightings:
        time_slot_str = sight_data.get("time_slot", "critical_window")
        try:
            time_slot = TimeSlot(time_slot_str)
        except ValueError:
            time_slot = TimeSlot.CRITICAL_WINDOW
        
        sighting = SightingEdge(
            observer_role=sight_data.get("observer_role", ""),
            subject_role=sight_data.get("subject_role", ""),
            location_id=sight_data.get("location", ""),
            time_slot=time_slot,
            is_mutual=sight_data.get("is_mutual", False),
            is_truthful=sight_data.get("observer_role") != draft.murderer_role,
            claim_text=sight_data.get("claim_text", ""),
        )
        sightings.append(sighting)
    
    # Find murder location
    murder_loc_id = draft.murder_location
    for loc in locations:
        if loc.is_murder_scene:
            murder_loc_id = loc.id
            break
    
    return EncounterGraph(
        locations=locations,
        presences=presences,
        sightings=sightings,
        murderer_role=draft.murderer_role,
        murder_time=TimeSlot.CRITICAL_WINDOW,
        murder_location_id=murder_loc_id,
    )

