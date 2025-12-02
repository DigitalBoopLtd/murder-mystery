"""Public Mystery View - Safe information the Game Master can access.

This module provides a "sanitized" view of the mystery that:
1. Hides suspect secrets and guilt status
2. Only exposes what the player could reasonably know
3. Gets updated as the player discovers information

The full truth remains ONLY in the MysteryOracle.
"""

from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field
from pydantic import BaseModel


@dataclass
class PublicSuspect:
    """What the GM can know about a suspect (no secrets!)."""
    name: str
    role: str
    personality: str
    alibi: str  # What they CLAIM (may be false)
    voice_id: Optional[str] = None
    
    # Discovered through gameplay (starts empty)
    has_been_interrogated: bool = False
    revealed_locations: List[str] = field(default_factory=list)
    known_contradictions: List[str] = field(default_factory=list)
    
    # NOTE: No isGuilty, no secret, no structured_alibi.is_truthful


@dataclass  
class PublicClue:
    """A clue that has been discovered."""
    id: str
    description: str
    location: str
    discovery_context: str = ""  # How it was found
    
    # NOTE: No alibi_implications (that would leak truth)


@dataclass
class PublicMystery:
    """The safe view of the mystery for the Game Master agent.
    
    This is what the GM can access. It contains:
    - Basic setting and victim info
    - Public suspect info (name, role, alibi claim)
    - Discovered clues and searched locations
    - Player progress
    
    It does NOT contain:
    - Who the murderer is
    - Suspect secrets  
    - Whether alibis are true or false
    - Encounter graph truth
    """
    setting: str
    victim_name: str
    victim_background: str
    
    suspects: List[PublicSuspect] = field(default_factory=list)
    
    # Searchable locations (revealed progressively)
    available_locations: List[str] = field(default_factory=list)
    searched_locations: Set[str] = field(default_factory=set)
    
    # Discovered information (grows as player investigates)
    discovered_clues: List[PublicClue] = field(default_factory=list)
    
    # Player progress
    suspects_interrogated: Set[str] = field(default_factory=set)
    wrong_accusations: int = 0


def create_public_mystery(mystery) -> PublicMystery:
    """Create a sanitized public view from the full mystery.
    
    Called ONCE when mystery is generated. Updates happen through
    update methods that add discovered information.
    """
    # Create public suspects (no secrets!)
    public_suspects = []
    for s in mystery.suspects:
        public_suspects.append(PublicSuspect(
            name=s.name,
            role=s.role,
            personality=s.personality,
            alibi=s.alibi,  # What they claim, not whether it's true
            voice_id=s.voice_id,
        ))
    
    # Get searchable locations from clues
    locations = list(set(c.location for c in mystery.clues))
    
    return PublicMystery(
        setting=mystery.setting,
        victim_name=mystery.victim.name if mystery.victim else "Unknown",
        victim_background=mystery.victim.background if mystery.victim else "",
        suspects=public_suspects,
        available_locations=locations,
    )


def update_after_interrogation(
    public: PublicMystery,
    suspect_name: str,
    revealed_locations: List[str] = None,
    contradictions_found: List[str] = None,
):
    """Update public mystery after interrogating a suspect."""
    public.suspects_interrogated.add(suspect_name)
    
    for ps in public.suspects:
        if ps.name == suspect_name:
            ps.has_been_interrogated = True
            if revealed_locations:
                ps.revealed_locations.extend(revealed_locations)
                # Add to available locations
                for loc in revealed_locations:
                    if loc not in public.available_locations:
                        public.available_locations.append(loc)
            if contradictions_found:
                ps.known_contradictions.extend(contradictions_found)
            break


def update_after_search(
    public: PublicMystery,
    location: str,
    clue_found: Optional[PublicClue] = None,
):
    """Update public mystery after searching a location."""
    public.searched_locations.add(location)
    if clue_found:
        public.discovered_clues.append(clue_found)


def build_gm_context(public: PublicMystery) -> str:
    """Build the context string for the GM's system prompt.
    
    This is what the GM agent can see - ONLY discovered information.
    """
    suspect_list = "\n".join(
        f"- {s.name} ({s.role})" + 
        (" [INTERROGATED]" if s.has_been_interrogated else "")
        for s in public.suspects
    )
    
    location_list = "\n".join(
        f'- "{loc}"' + (" [SEARCHED]" if loc in public.searched_locations else "")
        for loc in public.available_locations
    )
    
    clue_list = "\n".join(
        f"- {c.description} (found at {c.location})"
        for c in public.discovered_clues
    ) or "None yet"
    
    return f"""## THE CASE
{public.setting}

## VICTIM  
{public.victim_name}: {public.victim_background}

## SUSPECTS
{suspect_list}

## KNOWN LOCATIONS
{location_list}

## DISCOVERED CLUES
{clue_list}

## PROGRESS
- Suspects interviewed: {len(public.suspects_interrogated)}/{len(public.suspects)}
- Locations searched: {len(public.searched_locations)}/{len(public.available_locations)}
- Clues found: {len(public.discovered_clues)}
- Wrong accusations: {public.wrong_accusations}/3"""

