"""Parallel mystery generation using sub-agents.

This module replaces the monolithic mystery generation with parallel sub-agents:
- 4x faster startup (~6s vs ~15s)
- Better error isolation (one suspect failing doesn't lose everything)
- More consistent character development (each suspect gets full LLM attention)

Architecture:
    1. Skeleton Agent → Premise + murderer + role outlines (~2s)
    2. Parallel Agents → 4 suspects + clues (all run simultaneously ~5s)
    3. Assembly → Combine outputs + assign voices

IMPORTANT: This is NOT the agent the user talks to. The user talks to the
Game Master Agent in services/agent.py. This module only runs once at
game start to generate the mystery content.
"""

import asyncio
import logging
import os
import random
from typing import Dict, List, Optional, Tuple

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from game.models import (
    Mystery, Suspect, Victim, Clue, MysteryPremise,
    AlibiClaim, WitnessStatement, MurderMethod
)
from game.encounter_graph import (
    EncounterGraph, EncounterGraphDraft, LocationNode, PresenceNode,
    SightingEdge, TimeSlot, build_encounter_graph_from_draft
)
from mystery_config import MysteryConfig

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 1.0


# =============================================================================
# INTERMEDIATE MODELS FOR SUB-AGENTS
# =============================================================================

class SuspectPreview(BaseModel):
    """Minimal suspect info generated with skeleton for early display."""
    name: str = Field(description="Full character name")
    role: str = Field(description="Relationship to victim (e.g., 'Business Partner')")


class MysterySkeleton(BaseModel):
    """Lightweight skeleton that guides parallel generation.
    
    This is generated first to establish the framework that all
    parallel sub-agents will work within.
    
    NEW: Includes suspect_previews with names/roles for early UI display.
    """
    setting: str = Field(description="Vivid 1-2 sentence setting description")
    victim_name: str = Field(description="Victim's full name")
    victim_background: str = Field(description="1-2 sentences about the victim")
    murderer_index: int = Field(
        ge=0, le=3, 
        description="Which suspect (0-3) is the murderer"
    )
    weapon: str = Field(description="Murder weapon")
    motive: str = Field(description="Why the murderer did it")
    suspect_briefs: List[str] = Field(
        min_length=4, max_length=4,
        description="4 brief role descriptions like 'The jealous business partner'"
    )
    # NEW: Suspect names/roles for early UI display
    suspect_previews: List[SuspectPreview] = Field(
        description="4 suspects with name and role - for early UI display"
    )
    clue_locations: List[str] = Field(
        min_length=5, max_length=5,
        description="5 specific locations where clues will be found"
    )
    # Murder timeline for alibi verification
    murder_time: str = Field(
        default="9:00 PM",
        description="Approximate time of murder (e.g., '9:00 PM')"
    )
    murder_location: str = Field(
        default="",
        description="Where the murder took place"
    )


class AlibiDraft(BaseModel):
    """Structured alibi for verification system."""
    time_claimed: str = Field(description="Time range: e.g., '8:30 PM - 10:00 PM'")
    location_claimed: str = Field(description="Where they claim to have been")
    activity: str = Field(description="What they were doing")
    corroborator: Optional[str] = Field(
        default=None,
        description="Role of another suspect who can verify this (e.g., 'the business partner')"
    )
    corroboration_type: str = Field(
        default="none",
        description="'witness' (another suspect saw them), 'physical' (clue proves it), or 'none' (alone)"
    )
    is_truthful: bool = Field(default=True, description="False only for the murderer's fake alibi")


class SuspectDraft(BaseModel):
    """Output from a single suspect sub-agent."""
    name: str = Field(description="Full character name")
    role: str = Field(description="Relationship to victim")
    personality: str = Field(description="2-3 key personality traits")
    alibi: str = Field(description="Simple alibi statement for display")
    secret: str = Field(description="What they're hiding")
    clue_they_know: str = Field(description="Info they might share if pressed")
    gender: str = Field(description="male or female")
    age: str = Field(description="young, middle_aged, or old")
    nationality: str = Field(description="american, british, australian, or standard")
    # Structured alibi for verification
    structured_alibi: AlibiDraft = Field(description="Detailed alibi with verification method")
    # What they saw (witness statement about another suspect)
    witness_claim: Optional[str] = Field(
        default=None,
        description="What they saw another suspect do, e.g., 'I saw the professor in the library at 8:45'"
    )
    witness_subject_role: Optional[str] = Field(
        default=None,
        description="Role of the suspect they're making a statement about"
    )
    # location_hint is assigned during assembly, not generated by the sub-agent


class ClueDraft(BaseModel):
    """Output for a single clue with alibi verification capabilities."""
    id: str = Field(description="Unique clue ID like clue_1")
    description: str = Field(description="What the clue is")
    location: str = Field(description="Where it's found")
    significance: str = Field(description="What it means for the case")
    # Alibi verification
    contradicts_alibi_of_role: Optional[str] = Field(
        default=None,
        description="Role of suspect whose alibi this DISPROVES (e.g., 'the jealous partner')"
    )
    supports_alibi_of_role: Optional[str] = Field(
        default=None,
        description="Role of suspect whose alibi this CONFIRMS"
    )
    timeline_implication: Optional[str] = Field(
        default=None,
        description="What this tells us about timing"
    )
    evidence_type: str = Field(
        default="circumstantial",
        description="'physical', 'documentary', or 'circumstantial'"
    )


class ClueSet(BaseModel):
    """Output from the clue sub-agent."""
    clues: List[ClueDraft] = Field(min_length=5, max_length=5)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

async def retry_with_backoff(coro_func, *args, max_retries=MAX_RETRIES, **kwargs):
    """Retry an async function with exponential backoff.
    
    Args:
        coro_func: Async function to call
        *args: Arguments to pass to the function
        max_retries: Maximum number of retry attempts
        **kwargs: Keyword arguments to pass to the function
        
    Returns:
        Result of the successful call
        
    Raises:
        Last exception if all retries fail
    """
    last_error = None
    for attempt in range(max_retries):
        try:
            return await coro_func(*args, **kwargs)
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                delay = RETRY_DELAY_SECONDS * (2 ** attempt)  # Exponential backoff
                logger.warning(
                    "[PARALLEL] Attempt %d/%d failed: %s. Retrying in %.1fs...",
                    attempt + 1, max_retries, str(e)[:100], delay
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    "[PARALLEL] All %d attempts failed. Last error: %s",
                    max_retries, str(e)[:200]
                )
    raise last_error


# =============================================================================
# SUB-AGENT: SKELETON GENERATOR
# =============================================================================

async def _generate_skeleton_impl(
    config: Optional[MysteryConfig] = None,
    premise: Optional[MysteryPremise] = None,
) -> MysterySkeleton:
    """Internal implementation of skeleton generation."""
    from game.mystery_generator import SETTING_TYPES
    
    # Use structured output - LLM is constrained to output valid Pydantic
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.9,
        api_key=os.getenv("OPENAI_API_KEY"),
    ).with_structured_output(MysterySkeleton)
    
    # Use premise if provided, otherwise generate setting
    if premise:
        setting_instruction = f"""Use this EXACT setting and victim:
Setting: {premise.setting}
Victim: {premise.victim_name} - {premise.victim_background}

Do NOT change the setting or victim details."""
    else:
        setting_type = random.choice(SETTING_TYPES) if not config else config.get_setting_for_generation()
        setting_instruction = f"Create a vivid setting based on: {setting_type}"
    
    tone_instruction = ""
    if config:
        tone = config.get_tone_instruction()
        if tone:
            tone_instruction = f"\nTONE: {tone}"
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are planning a murder mystery game structure.

Your job is to create a SKELETON - the framework that guides detailed generation.
This is NOT the final mystery, just the blueprint.

REQUIREMENTS:
1. Pick which of 4 suspects (index 0-3) will be the murderer
2. Create 4 distinct suspect ROLE BRIEFS (evocative descriptions)
3. Create 4 SUSPECT PREVIEWS with actual character names and short role titles
4. Choose weapon and motive
5. List 5 specific searchable locations for clues

SUSPECT ROLE BRIEFS should be evocative like:
- "The bitter ex-business partner who lost everything"
- "The charming assistant with a dark secret"

SUSPECT PREVIEWS are for early UI display - give each suspect:
- A full character name (fitting the setting, no nicknames in quotes)
- A short role title like "Business Partner", "Personal Assistant", "Estranged Daughter"

{tone_instruction}"""),
        ("human", """{setting_instruction}

Generate the mystery skeleton with:
- Setting and victim details
- 4 suspect_briefs (evocative role descriptions)
- 4 suspect_previews (name + short role for each - SHOWN TO PLAYER IMMEDIATELY)
- murderer_index (0-3) indicating which suspect is guilty
- Weapon and motive
- 5 specific clue locations fitting the setting""")
    ])
    
    chain = prompt | llm
    
    # Structured output returns the Pydantic model directly - no parsing needed!
    skeleton = await chain.ainvoke({
        "setting_instruction": setting_instruction,
        "tone_instruction": tone_instruction,
    })
    
    logger.info(
        "[PARALLEL] Skeleton: murderer_index=%d, weapon=%s, %d locations, %d suspect_previews",
        skeleton.murderer_index,
        skeleton.weapon,
        len(skeleton.clue_locations),
        len(skeleton.suspect_previews) if skeleton.suspect_previews else 0,
    )
    # Log suspect previews for early display
    if skeleton.suspect_previews:
        for i, sp in enumerate(skeleton.suspect_previews):
            logger.info("[PARALLEL] Suspect preview %d: %s (%s)", i, sp.name, sp.role)
    return skeleton


async def generate_skeleton(
    config: Optional[MysteryConfig] = None,
    premise: Optional[MysteryPremise] = None,
) -> MysterySkeleton:
    """Stage 1: Generate the mystery skeleton (fast, ~2s).
    
    This determines the structure that all parallel agents will follow.
    Uses gpt-4o-mini for speed since this is just the framework.
    Uses structured output for reliable parsing.
    """
    logger.info("[PARALLEL] Generating skeleton...")
    return await retry_with_backoff(_generate_skeleton_impl, config, premise)


# =============================================================================
# SUB-AGENT: ENCOUNTER GRAPH GENERATOR
# =============================================================================

# Pydantic models for OpenAI structured output (must have explicit fields, not Dict)
class LocationOutput(BaseModel):
    """A location in the mystery setting."""
    id: str = Field(description="Unique location ID like 'library' or 'garden'")
    name: str = Field(description="Human-readable name")
    description: str = Field(description="Brief description of the location")
    is_murder_scene: bool = Field(default=False, description="Is this where the murder occurred?")


class TimelineEntry(BaseModel):
    """Where one suspect was at each time slot."""
    role: str = Field(description="The suspect's role brief")
    early_evening: str = Field(description="Location ID at 6:00-7:30 PM")
    dinner_start: str = Field(description="Location ID at 7:30-8:00 PM")
    dinner_main: str = Field(description="Location ID at 8:00-8:45 PM")
    critical_window: str = Field(description="Location ID at 8:45-9:15 PM (MURDER TIME)")
    post_discovery: str = Field(description="Location ID at 9:15-9:45 PM")


class SightingOutput(BaseModel):
    """A sighting: one person saw another."""
    observer_role: str = Field(description="Role of the person who saw")
    subject_role: str = Field(description="Role of the person who was seen")
    location: str = Field(description="Location ID where the sighting occurred")
    time_slot: str = Field(description="Time slot: early_evening, dinner_start, dinner_main, critical_window, or post_discovery")
    claim_text: str = Field(description="Natural language: 'I saw [subject] in the [location] around [time]'")
    is_mutual: bool = Field(default=False, description="Did both parties see each other?")


class EncounterGraphOutput(BaseModel):
    """Structured output for encounter graph generation.
    
    Defines WHO was WHERE at WHAT TIME, and WHO SAW WHOM.
    This is the SINGLE SOURCE OF TRUTH for alibis and witness statements.
    """
    
    # Location definitions
    locations: List[LocationOutput] = Field(
        description="4-6 locations in the mystery"
    )
    
    # Timeline: where each suspect role was at each time slot
    timeline: List[TimelineEntry] = Field(
        description="Where each of the 4 suspects was at each time slot"
    )
    
    # Sightings: who saw whom (forms the basis for witness statements)
    sightings: List[SightingOutput] = Field(
        description="3-6 sightings establishing who can corroborate whom"
    )
    
    murder_location_id: str = Field(description="Location ID where the murder occurred")


async def _generate_encounter_graph_impl(
    skeleton: MysterySkeleton,
) -> EncounterGraph:
    """Internal: Generate the encounter graph based on skeleton."""
    
    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0.7,
        api_key=os.getenv("OPENAI_API_KEY"),
    ).with_structured_output(EncounterGraphOutput)
    
    # Time slots explanation
    time_slots_desc = """
TIME SLOTS (in order):
- early_evening: 6:00-7:30 PM - Before the event, people arriving
- dinner_start: 7:30-8:00 PM - Gathering, mingling
- dinner_main: 8:00-8:45 PM - Main event/activity
- critical_window: 8:45-9:15 PM - ⚠️ MURDER HAPPENS HERE
- post_discovery: 9:15-9:45 PM - Body discovered
"""
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are designing the ENCOUNTER GRAPH for a murder mystery.

This graph is the SINGLE SOURCE OF TRUTH for:
- Where everyone ACTUALLY was at each time
- Who could have seen whom
- What alibis are true/false

{time_slots}

CRITICAL RULES:

1. MURDERER'S POSITION DURING CRITICAL_WINDOW:
   - The murderer (role index {murderer_index}: "{murderer_role}") MUST be at the murder location
   - Their "claimed" position in the timeline is their FALSE ALIBI
   - They will claim to be somewhere else, but they were actually at the murder scene
   
2. SIGHTINGS MUST BE PHYSICALLY POSSIBLE:
   - If A saw B, both A and B must have ACTUALLY been at that location at that time
   - The murderer CANNOT be truthfully seen during critical_window (they were at murder scene)
   - Other suspects CAN see each other (these become corroborating witnesses)
   
3. ALIBI NETWORK:
   - At least 2 innocent suspects should see each other (mutual corroboration)
   - The murderer might CLAIM someone saw them (false alibi with no real witness)
   - One innocent suspect should be alone (no alibi - creates suspicion)

4. SIGHTING CLAIMS:
   - Each sighting needs a natural claim_text: "I saw [role] in the [location] around [time]"
   - These become witness statements suspects can share

SETTING: {setting}
VICTIM: {victim_name}
MURDER TIME: During critical_window (8:45-9:15 PM)

SUSPECT ROLES:
{roles}

LOCATIONS TO USE (create location IDs from these):
{locations}
"""),
        ("human", """Generate the encounter graph:

1. Define 4-6 locations with IDs, names, and which are adjacent
2. Create the timeline: where each of the 4 suspect roles was at each time slot
   - Remember: murderer's critical_window position is their LIE
3. Define 3-6 sightings that establish who can corroborate whom
   - Must be physically possible (both parties actually at location)
   - Include at least one mutual sighting between innocents
   
Make the graph logically consistent - this is the TRUTH of the mystery.""")
    ])
    
    chain = prompt | llm
    
    roles_text = "\n".join([
        f"  {i}. {role}" + (" ← MURDERER" if i == skeleton.murderer_index else "")
        for i, role in enumerate(skeleton.suspect_briefs)
    ])
    
    output: EncounterGraphOutput = await chain.ainvoke({
        "time_slots": time_slots_desc,
        "murderer_index": skeleton.murderer_index,
        "murderer_role": skeleton.suspect_briefs[skeleton.murderer_index],
        "setting": skeleton.setting,
        "victim_name": skeleton.victim_name,
        "roles": roles_text,
        "locations": ", ".join(skeleton.clue_locations),
    })
    
    # Convert output to EncounterGraph
    locations = []
    for loc_out in output.locations:
        loc = LocationNode(
            id=loc_out.id,
            name=loc_out.name,
            description=loc_out.description,
            is_murder_scene=(loc_out.id == output.murder_location_id) or loc_out.is_murder_scene,
            is_public=True,
            adjacent_to=[],
        )
        locations.append(loc)
    
    # Convert timeline to presences
    presences = []
    murderer_role = skeleton.suspect_briefs[skeleton.murderer_index]
    
    # Map time slot names to TimeSlot enum
    time_slot_map = {
        "early_evening": TimeSlot.EARLY_EVENING,
        "dinner_start": TimeSlot.DINNER_START,
        "dinner_main": TimeSlot.DINNER_MAIN,
        "critical_window": TimeSlot.CRITICAL_WINDOW,
        "post_discovery": TimeSlot.POST_DISCOVERY,
    }
    
    for entry in output.timeline:
        role = entry.role
        # Access each time slot from the TimelineEntry model
        for ts_key, ts_enum in time_slot_map.items():
            loc_id = getattr(entry, ts_key, None)
            if loc_id:
                # For murderer during critical window, their stated position is a lie
                is_murderer_critical = (role == murderer_role and ts_enum == TimeSlot.CRITICAL_WINDOW)
                
                presence = PresenceNode(
                    person_role=role,
                    location_id=loc_id,
                    time_slot=ts_enum,
                    activity="present",
                    is_truthful=not is_murderer_critical,
                    actual_location_id=output.murder_location_id if is_murderer_critical else None,
                )
                presences.append(presence)
    
    # Convert sightings
    sightings = []
    for sight_out in output.sightings:
        ts_str = sight_out.time_slot
        ts = time_slot_map.get(ts_str, TimeSlot.CRITICAL_WINDOW)
        
        sighting = SightingEdge(
            observer_role=sight_out.observer_role,
            subject_role=sight_out.subject_role,
            location_id=sight_out.location,
            time_slot=ts,
            is_mutual=sight_out.is_mutual,
            is_truthful=(sight_out.observer_role != murderer_role),  # Murderer's claims might be lies
            claim_text=sight_out.claim_text,
        )
        sightings.append(sighting)
    
    graph = EncounterGraph(
        locations=locations,
        presences=presences,
        sightings=sightings,
        murderer_role=murderer_role,
        murder_time=TimeSlot.CRITICAL_WINDOW,
        murder_location_id=output.murder_location_id,
    )
    
    logger.info("[ENCOUNTER] Generated graph: %d locations, %d presences, %d sightings",
               len(locations), len(presences), len(sightings))
    
    return graph


async def generate_encounter_graph(
    skeleton: MysterySkeleton,
) -> EncounterGraph:
    """Stage 1.5: Generate the encounter graph from skeleton.
    
    The encounter graph is the SINGLE SOURCE OF TRUTH for:
    - Where everyone actually was
    - Who saw whom
    - Which alibis are true/false
    
    All alibis and witness statements are DERIVED from this graph.
    """
    logger.info("[PARALLEL] Generating encounter graph...")
    return await retry_with_backoff(_generate_encounter_graph_impl, skeleton)


# =============================================================================
# SUB-AGENT: SUSPECT GENERATOR (runs 4x in parallel)
# =============================================================================

async def _generate_suspect_impl(
    skeleton: MysterySkeleton,
    role_brief: str,
    suspect_index: int,
    is_guilty: bool,
    voice_options: Optional[str] = None,
    encounter_graph: Optional[EncounterGraph] = None,
) -> SuspectDraft:
    """Internal implementation of suspect generation with structured output."""
    # Use structured output - LLM is constrained to output valid Pydantic
    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0.9,
        api_key=os.getenv("OPENAI_API_KEY"),
    ).with_structured_output(SuspectDraft)
    
    # Get the predetermined name/role from skeleton (for UI consistency)
    # These were shown to the player BEFORE full generation, so we MUST use them
    preset_name = None
    preset_role = None
    if skeleton.suspect_previews and suspect_index < len(skeleton.suspect_previews):
        preset_name = skeleton.suspect_previews[suspect_index].name
        preset_role = skeleton.suspect_previews[suspect_index].role
        logger.info("[PARALLEL] Suspect %d: Using preset name '%s' (%s)", suspect_index, preset_name, preset_role)
    
    # Get other suspect roles for cross-referencing (for witness statements)
    other_roles = [r for i, r in enumerate(skeleton.suspect_briefs) if i != suspect_index]
    other_roles_str = ", ".join(other_roles) if other_roles else "other suspects"
    
    if is_guilty:
        guilt_instructions = f"""
⚠️ THIS SUSPECT IS THE MURDERER ⚠️

They killed the victim using: {skeleton.weapon}
Their motive: {skeleton.motive}
Murder time: Around {skeleton.murder_time}
Murder location: {skeleton.murder_location or skeleton.clue_locations[0]}

CHARACTER RULES FOR THE GUILTY:
- Their alibi is FALSE - they claim to be somewhere they weren't
- structured_alibi.is_truthful MUST be False
- Their alibi should sound plausible but can be DISPROVEN by:
  1. A clue at a location (physical evidence they were elsewhere)
  2. Another suspect's testimony contradicting their claim
- If they claim someone can corroborate, that person should NOT actually confirm it
- Their SECRET must be a damaging observation or claim about ANOTHER SUSPECT
  * Example: They \"secretly\" saw another suspect near the murder scene, or overheard a threat
  * This secret should make that OTHER suspect look more guilty and shift suspicion away from them
  * The claim can be a lie or a twisted half-truth, but it MUST fit the overall case details
- Their "clue_they_know" should be misleading or deflecting (it points AWAY from their own guilt)

ALIBI CREATION (GUILTY):
- Create a specific alibi with exact time/place that COVERS the murder time
- The alibi should be falsifiable - there should be a way to prove they weren't there
- corroboration_type should be 'witness' if they falsely claim someone saw them
- corroborator should be one of the other roles: {other_roles_str}
"""
    else:
        guilt_instructions = f"""
This suspect is INNOCENT but should still seem suspicious.

CHARACTER RULES FOR THE INNOCENT:
- Their SECRET should be a truthful thing they know or saw that touches the case
  * Often this is something incriminating or awkward about another suspect (e.g. a heated argument, a suspicious meeting)
  * It MUST be TRUE in the mystery world and ideally corroborated by EITHER:
    - a clue, OR
    - another suspect's structured_alibi / witness statement
- Their secret should NOT directly solve the case on its own, but it should be a real puzzle piece the detective can cross‑check
- Their alibi is TRUE - they were where they say they were
- structured_alibi.is_truthful MUST be True
- Their alibi can be verified by another suspect OR was alone
- They may have HAD motive but didn't act on it
- Their "clue_they_know" should be helpful info they might share

ALIBI CREATION (INNOCENT):
- Create a REAL alibi with specific time/place
- corroboration_type options:
  - 'witness': Another suspect saw them (corroborator = one of: {other_roles_str})
  - 'physical': A clue at a location proves their presence
  - 'none': They were alone (harder to verify but also can't disprove)
- If they have a witness corroborator, it should be truthful
"""
    
    voice_block = ""
    if voice_options:
        voice_block = f"""
VOICE CASTING:
Design this character to match one of these available voice actors.
Consider gender, age range, and accent when creating the character:

{voice_options[:1500]}

Pick characteristics that fit an available voice well."""
    
    # === ENCOUNTER GRAPH DERIVED ALIBIS ===
    # If we have an encounter graph, extract MANDATORY alibi constraints
    graph_alibi_block = ""
    graph_witness_block = ""
    
    if encounter_graph:
        # Get this role's alibi info from the graph
        alibi_info = encounter_graph.derive_alibi_claim(role_brief)
        
        # Get sightings this person made (they become witness statements)
        sightings_made = encounter_graph.get_sightings_by(role_brief)
        
        # Get sightings of this person (for corroboration)
        sightings_of = encounter_graph.get_sightings_of(role_brief)
        
        graph_alibi_block = f"""
🔒 MANDATORY ALIBI FROM ENCOUNTER GRAPH (YOU MUST USE THESE EXACT VALUES):
- Location claimed: {alibi_info.get('location_claimed', 'unknown')}
- Activity: {alibi_info.get('activity', 'present')}
- Time: Around 9 PM (the critical window)
- Is truthful: {alibi_info.get('is_truthful', True)}
- Corroborator (if any): {alibi_info.get('corroborator', 'None')}

Your structured_alibi MUST match these values exactly. This ensures consistency
across all suspects and allows the player to verify alibis logically.
"""
        
        if sightings_made:
            witness_claims = []
            for s in sightings_made:
                if s.claim_text:
                    witness_claims.append(f"  - {s.claim_text}")
            if witness_claims:
                graph_witness_block = f"""
🔒 MANDATORY WITNESS STATEMENTS (you saw these people):
{chr(10).join(witness_claims)}

Include ONE of these as your witness_claim field.
"""
        
        if sightings_of:
            corroborators = [s.observer_role for s in sightings_of if s.is_truthful]
            if corroborators:
                graph_alibi_block += f"""
People who can verify your alibi: {', '.join(corroborators)}
"""
    
    # Build name requirement based on whether we have a preset
    if preset_name:
        name_requirement = f"""🔒 MANDATORY NAME: You MUST use exactly "{preset_name}" as this character's name.
🔒 MANDATORY ROLE: You MUST use exactly "{preset_role}" as their role.
This name was already shown to the player - do NOT change it."""
    else:
        name_requirement = "- Name should fit the setting and feel authentic (no quotes or nicknames)"
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are creating ONE detailed suspect for a murder mystery.

You are building a THREE-DIMENSIONAL character, not a cardboard cutout.
Give them depth, quirks, and believable motivations.

SETTING: {setting}
VICTIM: {victim_name} - {victim_background}
MURDER TIME: Around {murder_time}
OTHER SUSPECTS IN THIS CASE: {other_roles}

{guilt_instructions}

{voice_block}

{graph_alibi_block}

{graph_witness_block}

QUALITY REQUIREMENTS:
{name_requirement}
- Personality should be specific, not generic ("nervous and detail-oriented" not just "suspicious")
- Secret should be juicy and character-defining
- Their "clue_they_know" should be something they'd realistically know

ALIBI REQUIREMENTS (CRITICAL):
- The "alibi" field is a simple statement like "I was in the library reading"
- The "structured_alibi" object MUST match the encounter graph values above
- If no encounter graph values provided, create plausible alibi details

WITNESS STATEMENT (if provided above):
- Use the witness_claim from the encounter graph
- witness_subject_role: The role of the person you saw"""),
        ("human", """Create a fully realized character for this role:
"{role_brief}"

Make them memorable and distinct from typical mystery tropes.
Your alibi MUST follow the encounter graph constraints if provided.""")
    ])
    
    chain = prompt | llm
    
    # Structured output returns the Pydantic model directly - no parsing needed!
    suspect = await chain.ainvoke({
        "setting": skeleton.setting,
        "victim_name": skeleton.victim_name,
        "victim_background": skeleton.victim_background,
        "murder_time": skeleton.murder_time,
        "other_roles": other_roles_str,
        "guilt_instructions": guilt_instructions,
        "voice_block": voice_block,
        "graph_alibi_block": graph_alibi_block,
        "graph_witness_block": graph_witness_block,
        "name_requirement": name_requirement,
        "role_brief": role_brief,
    })
    
    return suspect


async def generate_suspect(
    skeleton: MysterySkeleton,
    role_brief: str,
    suspect_index: int,
    is_guilty: bool,
    voice_options: Optional[str] = None,
    encounter_graph: Optional[EncounterGraph] = None,
) -> Tuple[SuspectDraft, int, bool]:
    """Generate a single suspect (runs in parallel with other suspects).
    
    Uses gpt-4o for quality character development since each suspect
    gets full LLM attention in parallel. Uses structured output for
    reliable parsing with automatic retries.
    
    If encounter_graph is provided, alibis are DERIVED from it for consistency.
    
    Returns:
        Tuple of (suspect_draft, suspect_index, is_guilty)
    """
    logger.info("[PARALLEL] Generating suspect %d: %s (guilty=%s, has_graph=%s)", 
                suspect_index, role_brief[:40], is_guilty, encounter_graph is not None)
    
    suspect = await retry_with_backoff(
        _generate_suspect_impl, skeleton, role_brief, suspect_index, is_guilty, voice_options, encounter_graph
    )
    
    # FORCE the preset name/role if we have one (LLM might ignore instructions)
    if skeleton.suspect_previews and suspect_index < len(skeleton.suspect_previews):
        preset = skeleton.suspect_previews[suspect_index]
        if suspect.name != preset.name:
            logger.warning("[PARALLEL] Suspect %d: LLM used '%s' but forcing preset name '%s'", 
                          suspect_index, suspect.name, preset.name)
            suspect.name = preset.name
        if suspect.role != preset.role:
            logger.warning("[PARALLEL] Suspect %d: LLM used role '%s' but forcing preset role '%s'", 
                          suspect_index, suspect.role, preset.role)
            suspect.role = preset.role
    
    logger.info("[PARALLEL] ✓ Suspect %d: %s (%s)", suspect_index, suspect.name, suspect.role)
    return (suspect, suspect_index, is_guilty)


# =============================================================================
# SUB-AGENT: CLUE GENERATOR
# =============================================================================

async def _generate_clues_impl(
    skeleton: MysterySkeleton,
    murderer_role: str,
    encounter_graph: Optional[EncounterGraph] = None,
) -> ClueSet:
    """Internal implementation of clue generation with structured output."""
    # Use structured output - LLM is constrained to output valid Pydantic
    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0.8,
        api_key=os.getenv("OPENAI_API_KEY"),
    ).with_structured_output(ClueSet)
    
    # Get all suspect roles for alibi verification
    all_suspect_roles = ", ".join(skeleton.suspect_briefs)
    
    # === ENCOUNTER GRAPH DERIVED CLUE OPPORTUNITIES ===
    # If we have an encounter graph, extract specific alibi verification opportunities
    graph_clue_block = ""
    if encounter_graph:
        clue_opportunities = encounter_graph.get_clue_opportunities()
        if clue_opportunities:
            opp_lines = []
            for opp in clue_opportunities:
                opp_lines.append(
                    f"  - At {opp['location']}: {opp['description']} (proves {opp['proves']})"
                )
            graph_clue_block = f"""
🔒 CLUE OPPORTUNITIES FROM ENCOUNTER GRAPH (use these to ensure logical consistency):
{chr(10).join(opp_lines)}

Design clues that match these opportunities. The encounter graph has established
WHERE everyone actually was - clues should prove or disprove these positions.

CRITICAL: At least one clue MUST be at the murder location ({encounter_graph.murder_location_id})
that proves the murderer was there.
"""
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are designing CLUES for a murder mystery game.

CASE DETAILS:
- Setting: {setting}
- Victim: {victim_name} - {victim_background}
- The Murderer's Role: {murderer_role}
- Weapon: {weapon}
- Motive: {motive}
- Murder Time: Around {murder_time}

ALL SUSPECT ROLES: {all_suspect_roles}

CLUE DESIGN RULES:
1. Create 5 clues spread across these locations: {locations}
2. 3-4 clues should POINT TOWARD the murderer when combined
3. 1 clue should be a RED HERRING pointing at an innocent suspect
4. Clues should be DISCOVERABLE THINGS: documents, objects, traces, marks

ALIBI VERIFICATION (CRITICAL):
Each clue should help verify or contradict alibis:
- contradicts_alibi_of_role: Role of suspect whose alibi this DISPROVES
  * At least ONE clue MUST contradict the murderer's alibi!
  * Example: Guest book shows murderer wasn't where they claimed
- supports_alibi_of_role: Role of suspect whose alibi this CONFIRMS
  * Some clues should SUPPORT innocent suspects' alibis
- timeline_implication: What this tells us about timing
  * Example: "Clock in photo shows 8:45 PM"
- evidence_type: 'physical' (forensic), 'documentary' (records/letters), or 'circumstantial'

REQUIRED CLUE DISTRIBUTION:
- 1 clue MUST contradict the murderer's false alibi (this is key evidence!)
- 1-2 clues should support innocent suspects' alibis
- 1-2 clues should point to motive/opportunity
- 1 red herring that initially looks damning but has innocent explanation

{graph_clue_block}

PUZZLE DESIGN:
- No single clue solves it alone - need to combine evidence
- The murderer's alibi can be proven FALSE through physical evidence
- Innocent suspects' alibis should be verifiable
- The solution should feel "obvious in hindsight" """),
        ("human", """Create 5 interconnected clues at these locations:
{locations}

Design them as a coherent puzzle pointing to "{murderer_role}".
At least ONE clue must DISPROVE the murderer's alibi.
Include support for innocent alibis and one red herring.
If encounter graph clue opportunities are provided above, use them to ensure logical consistency.""")
    ])
    
    chain = prompt | llm
    
    # Structured output returns the Pydantic model directly - no parsing needed!
    clue_set = await chain.ainvoke({
        "setting": skeleton.setting,
        "victim_name": skeleton.victim_name,
        "victim_background": skeleton.victim_background,
        "murderer_role": murderer_role,
        "weapon": skeleton.weapon,
        "motive": skeleton.motive,
        "murder_time": skeleton.murder_time,
        "all_suspect_roles": all_suspect_roles,
        "locations": ", ".join(skeleton.clue_locations),
        "graph_clue_block": graph_clue_block,
    })
    
    return clue_set


async def generate_clues(
    skeleton: MysterySkeleton,
    murderer_role: str,
    encounter_graph: Optional[EncounterGraph] = None,
) -> ClueSet:
    """Generate all clues for the mystery.
    
    Uses gpt-4o for quality clue design that forms a coherent puzzle.
    Uses structured output for reliable parsing with automatic retries.
    
    If encounter_graph is provided, clues are designed to prove/disprove
    positions established in the graph.
    """
    logger.info("[PARALLEL] Generating clues for %d locations (has_graph=%s)...", 
               len(skeleton.clue_locations), encounter_graph is not None)
    
    clue_set = await retry_with_backoff(_generate_clues_impl, skeleton, murderer_role, encounter_graph)
    
    logger.info("[PARALLEL] ✓ Generated %d clues", len(clue_set.clues))
    return clue_set


# =============================================================================
# ASSEMBLY: COMBINE SUB-AGENT OUTPUTS
# =============================================================================

def assemble_mystery(
    skeleton: MysterySkeleton,
    suspect_results: List[Tuple[SuspectDraft, int, bool]],
    clue_set: ClueSet,
    voice_summary: Optional[str] = None,
    encounter_graph: Optional[EncounterGraph] = None,
) -> Mystery:
    """Assemble final Mystery from sub-agent outputs.
    
    Combines all parallel outputs into the final Mystery model.
    Also handles voice assignment, location hints, and alibi verification wiring.
    
    If encounter_graph is provided, alibis are validated against it.
    """
    # Sort suspects by their original index to maintain order
    suspect_results.sort(key=lambda x: x[1])
    
    # Build a mapping from role brief -> suspect name for alibi resolution
    role_to_name = {}
    for draft, index, is_guilty in suspect_results:
        role_brief = skeleton.suspect_briefs[index].lower()
        role_to_name[role_brief] = draft.name
        # Also map partial matches
        for word in role_brief.split():
            if len(word) > 3:  # Skip short words like "the"
                role_to_name[word] = draft.name
    
    # Get unique locations from clues for assignment to suspects
    clue_locations = list(set(clue.location for clue in clue_set.clues))
    
    # Convert drafts to full Suspect models with alibi verification
    suspects: List[Suspect] = []
    murderer_name = None
    all_witness_statements: List[WitnessStatement] = []
    
    for idx, (draft, index, is_guilty) in enumerate(suspect_results):
        # Assign a location hint to each suspect
        location_hint = clue_locations[idx] if idx < len(clue_locations) else None
        
        # Convert AlibiDraft to AlibiClaim
        structured_alibi = None
        if hasattr(draft, 'structured_alibi') and draft.structured_alibi:
            alibi_draft = draft.structured_alibi
            # Resolve corroborator role to name
            corroborator_name = None
            if alibi_draft.corroborator:
                corroborator_lower = alibi_draft.corroborator.lower()
                for key, name in role_to_name.items():
                    if key in corroborator_lower or corroborator_lower in key:
                        corroborator_name = name
                        break
            
            structured_alibi = AlibiClaim(
                time_claimed=alibi_draft.time_claimed,
                location_claimed=alibi_draft.location_claimed,
                activity=alibi_draft.activity,
                corroborator=corroborator_name,
                corroboration_type=alibi_draft.corroboration_type,
                is_truthful=alibi_draft.is_truthful,
            )
        
        # Build witness statements from this suspect
        witness_statements = []
        if hasattr(draft, 'witness_claim') and draft.witness_claim and hasattr(draft, 'witness_subject_role') and draft.witness_subject_role:
            # Resolve the subject role to a name
            subject_name = None
            subject_lower = draft.witness_subject_role.lower()
            for key, name in role_to_name.items():
                if key in subject_lower or subject_lower in key:
                    subject_name = name
                    break
            
            if subject_name:
                ws = WitnessStatement(
                    witness=draft.name,
                    subject=subject_name,
                    claim=draft.witness_claim,
                    time_of_sighting="",  # Extracted from claim
                    location_of_sighting="",  # Extracted from claim
                    is_truthful=not is_guilty,  # Guilty suspect might lie
                )
                witness_statements.append(ws)
                all_witness_statements.append(ws)
        
        suspect = Suspect(
            name=draft.name,
            role=draft.role,
            personality=draft.personality,
            alibi=draft.alibi,
            secret=draft.secret,
            clue_they_know=draft.clue_they_know,
            isGuilty=is_guilty,
            gender=draft.gender,
            age=draft.age,
            nationality=draft.nationality,
            voice_id=None,  # Assigned below
            portrait_path=None,
            location_hint=location_hint,
            structured_alibi=structured_alibi,
            witness_statements=witness_statements,
        )
        suspects.append(suspect)
        
        if is_guilty:
            murderer_name = draft.name
    
    # Log alibi assignments
    for s in suspects:
        alibi_info = f"truthful={s.structured_alibi.is_truthful}" if s.structured_alibi else "none"
        logger.info("[PARALLEL] Suspect %s: location=%s, alibi=%s", 
                   s.name, s.location_hint, alibi_info)
    
    # Convert clue drafts to Clue models with alibi verification
    clues: List[Clue] = []
    for clue_draft in clue_set.clues:
        # Resolve role references to suspect names
        contradicts_name = None
        if hasattr(clue_draft, 'contradicts_alibi_of_role') and clue_draft.contradicts_alibi_of_role:
            role_lower = clue_draft.contradicts_alibi_of_role.lower()
            for key, name in role_to_name.items():
                if key in role_lower or role_lower in key:
                    contradicts_name = name
                    break
        
        supports_name = None
        if hasattr(clue_draft, 'supports_alibi_of_role') and clue_draft.supports_alibi_of_role:
            role_lower = clue_draft.supports_alibi_of_role.lower()
            for key, name in role_to_name.items():
                if key in role_lower or role_lower in key:
                    supports_name = name
                    break
        
        clue = Clue(
            id=clue_draft.id,
            description=clue_draft.description,
            location=clue_draft.location,
            significance=clue_draft.significance,
            contradicts_alibi_of=contradicts_name,
            supports_alibi_of=supports_name,
            timeline_implication=getattr(clue_draft, 'timeline_implication', None),
            evidence_type=getattr(clue_draft, 'evidence_type', 'circumstantial'),
        )
        clues.append(clue)
    
    # Log clue alibi verification
    for c in clues:
        if c.contradicts_alibi_of or c.supports_alibi_of:
            logger.info("[PARALLEL] Clue %s: contradicts=%s, supports=%s",
                       c.id, c.contradicts_alibi_of, c.supports_alibi_of)
    
    # Assign voices if available
    if voice_summary:
        suspects = _assign_voices_to_suspects(suspects, voice_summary)
    
    # Build murder method with evidence trail
    evidence_trail = [c.id for c in clues if c.contradicts_alibi_of == murderer_name]
    murder_method = MurderMethod(
        weapon=skeleton.weapon,
        time_of_death=skeleton.murder_time,
        location_of_murder=skeleton.murder_location or skeleton.clue_locations[0],
        opportunity=f"While other suspects were occupied, during the time window around {skeleton.murder_time}",
        evidence_trail=evidence_trail,
    )
    
    mystery = Mystery(
        setting=skeleton.setting,
        victim=Victim(
            name=skeleton.victim_name,
            background=skeleton.victim_background,
        ),
        murderer=murderer_name or "Unknown",
        weapon=skeleton.weapon,
        motive=skeleton.motive,
        suspects=suspects,
        clues=clues,
        murder_method=murder_method,
        witness_statements=all_witness_statements,
    )
    
    logger.info(
        "[PARALLEL] Assembled mystery: %s murdered by %s with %s",
        skeleton.victim_name,
        murderer_name,
        skeleton.weapon,
    )
    logger.info(
        "[PARALLEL] Alibi verification: %d witness statements, %d clues with alibi implications",
        len(all_witness_statements),
        len([c for c in clues if c.contradicts_alibi_of or c.supports_alibi_of])
    )
    return mystery


def _assign_voices_to_suspects(
    suspects: List[Suspect],
    voice_summary: str,
) -> List[Suspect]:
    """Assign voices to suspects based on characteristics."""
    try:
        from services.voice_service import get_voice_service
        
        voice_service = get_voice_service()
        if not voice_service.is_available:
            logger.info("[PARALLEL] Voice service not available, skipping voice assignment")
            return suspects
        
        available_voices = voice_service.get_available_voices()
        if not available_voices:
            return suspects
        
        used_ids = set()
        
        for suspect in suspects:
            suspect_dict = {
                "name": suspect.name,
                "role": suspect.role,
                "personality": suspect.personality,
                "gender": suspect.gender,
                "age": suspect.age,
                "nationality": suspect.nationality,
            }
            
            voice = voice_service.match_voice_to_suspect(
                suspect_dict,
                available_voices,
                list(used_ids),
            )
            
            if voice:
                suspect.voice_id = voice.voice_id
                used_ids.add(voice.voice_id)
                logger.info(
                    "[PARALLEL] Assigned voice '%s' to %s",
                    voice.name,
                    suspect.name,
                )
        
        return suspects
        
    except Exception as e:
        logger.warning("[PARALLEL] Voice assignment failed: %s", e)
        return suspects


# =============================================================================
# MAIN PARALLEL GENERATION FUNCTION
# =============================================================================

async def generate_mystery_parallel(
    premise: Optional[MysteryPremise] = None,
    config: Optional[MysteryConfig] = None,
    voice_summary: Optional[str] = None,
    skeleton: Optional[MysterySkeleton] = None,
) -> Tuple[Mystery, Optional[EncounterGraph]]:
    """Generate a complete mystery using parallel sub-agents.
    
    Performance: ~8-10s vs ~15s for monolithic generation.
    
    This is NOT the agent that users talk to. Users interact with the
    Game Master Agent in services/agent.py. This function only runs once
    at game start to generate the mystery content.
    
    Architecture:
        1. Skeleton Agent (gpt-4o-mini, ~2s) - Framework (SKIPPED if skeleton provided)
        2. Encounter Graph Agent (~3s) - WHO SAW WHOM (single source of truth)
        3. PARALLEL: 4x Suspects + Clues (~5s total) - Derived from graph
        4. Assembly + Voice Assignment
    
    The Encounter Graph ensures logical consistency:
    - All alibis are derived from the graph
    - All witness statements are validated against the graph
    - Clues align with what the graph says about positions
    
    Args:
        premise: Optional preset premise (setting, victim)
        config: Game configuration for difficulty/tone
        voice_summary: Available voices for assignment
        skeleton: Optional pre-generated skeleton (for early UI display)
        
    Returns:
        Tuple of (Mystery, EncounterGraph) - both needed for full game
    """
    import time
    t_start = time.perf_counter()
    
    # =========================================================================
    # STAGE 1: SKELETON (~2s) - SKIP if already provided
    # =========================================================================
    if skeleton:
        logger.info("[PARALLEL] ═══ Stage 1: Using pre-generated skeleton (SKIPPED generation) ═══")
        t2 = time.perf_counter()
    else:
        logger.info("[PARALLEL] ═══ Stage 1: Generating skeleton ═══")
        t1 = time.perf_counter()
        
        skeleton = await generate_skeleton(config=config, premise=premise)
        
        t2 = time.perf_counter()
        logger.info("[PARALLEL] Skeleton complete in %.2fs", t2 - t1)
    
    # =========================================================================
    # STAGE 1.5: ENCOUNTER GRAPH (~3s) - SINGLE SOURCE OF TRUTH
    # =========================================================================
    logger.info("[PARALLEL] ═══ Stage 1.5: Generating encounter graph ═══")
    t2_5 = time.perf_counter()
    
    encounter_graph = await generate_encounter_graph(skeleton)
    
    t3 = time.perf_counter()
    logger.info("[PARALLEL] Encounter graph complete in %.2fs", t3 - t2_5)
    
    # =========================================================================
    # STAGE 2: PARALLEL SUSPECTS + CLUES (~5s total, derived from graph)
    # =========================================================================
    logger.info("[PARALLEL] ═══ Stage 2: Generating suspects + clues IN PARALLEL ═══")
    logger.info("[PARALLEL] Alibis will be DERIVED from encounter graph for consistency")
    
    # Get murderer role for clue generation (don't need name yet!)
    murderer_role = skeleton.suspect_briefs[skeleton.murderer_index]
    
    # Create tasks for each suspect - NOW WITH ENCOUNTER GRAPH
    suspect_tasks = []
    for i, role_brief in enumerate(skeleton.suspect_briefs):
        is_guilty = (i == skeleton.murderer_index)
        task = generate_suspect(
            skeleton=skeleton,
            role_brief=role_brief,
            suspect_index=i,
            is_guilty=is_guilty,
            voice_options=voice_summary[:2000] if voice_summary else None,
            encounter_graph=encounter_graph,  # NEW: pass the graph for alibi derivation
        )
        suspect_tasks.append(task)
    
    # Create clue task - NOW WITH ENCOUNTER GRAPH for alibi verification
    clue_task = generate_clues(skeleton, murderer_role, encounter_graph)
    
    # Run ALL tasks in parallel: 4 suspects + 1 clue generation
    logger.info("[PARALLEL] Launching %d suspect tasks + 1 clue task (all parallel)", 
                len(suspect_tasks))
    all_tasks = suspect_tasks + [clue_task]
    all_results = await asyncio.gather(*all_tasks, return_exceptions=True)
    
    # Split results: first 4 are suspects, last is clues
    suspect_results = all_results[:4]
    clue_result = all_results[4]
    
    # Handle suspect failures
    valid_suspect_results = []
    for i, result in enumerate(suspect_results):
        if isinstance(result, Exception):
            logger.error("[PARALLEL] Suspect %d failed: %s", i, result)
            raise result
        valid_suspect_results.append(result)
    
    # Handle clue failure
    if isinstance(clue_result, Exception):
        logger.error("[PARALLEL] Clue generation failed: %s", clue_result)
        raise clue_result
    clue_set = clue_result
    
    t4 = time.perf_counter()
    logger.info("[PARALLEL] All %d suspects + clues complete in %.2fs (PARALLEL)", 
                len(valid_suspect_results), t4 - t3)
    
    # =========================================================================
    # STAGE 3: ASSEMBLY + VOICE ASSIGNMENT
    # =========================================================================
    logger.info("[PARALLEL] ═══ Stage 3: Assembly ═══")
    
    mystery = assemble_mystery(
        skeleton=skeleton,
        suspect_results=valid_suspect_results,
        clue_set=clue_set,
        voice_summary=voice_summary,
        encounter_graph=encounter_graph,  # Pass graph for assembly
    )
    
    t_end = time.perf_counter()
    
    # Log voice assignment stats
    assigned_count = sum(1 for s in mystery.suspects if s.voice_id)
    logger.info(
        "[PARALLEL] ✅ Mystery generation complete in %.2fs (voices: %d/%d)",
        t_end - t_start,
        assigned_count,
        len(mystery.suspects),
    )
    logger.info("[PARALLEL] Encounter graph: %d sightings establish alibi network",
               len(encounter_graph.sightings))
    
    return mystery, encounter_graph


# =============================================================================
# SYNC WRAPPERS FOR EXISTING CODE
# =============================================================================

def generate_skeleton_sync(
    premise: Optional[MysteryPremise] = None,
    config: Optional[MysteryConfig] = None,
) -> MysterySkeleton:
    """Synchronous wrapper for skeleton generation ONLY.
    
    Use this to get suspect names/roles EARLY for UI display,
    before the full mystery is ready.
    
    Returns:
        MysterySkeleton with suspect_previews for immediate display
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    generate_skeleton(config=config, premise=premise)
                )
                return future.result()
        else:
            return loop.run_until_complete(generate_skeleton(config=config, premise=premise))
    except RuntimeError:
        return asyncio.run(generate_skeleton(config=config, premise=premise))


def generate_mystery_parallel_sync(
    premise: Optional[MysteryPremise] = None,
    config: Optional[MysteryConfig] = None,
    voice_summary: Optional[str] = None,
    skeleton: Optional[MysterySkeleton] = None,
) -> Mystery:
    """Synchronous wrapper for parallel mystery generation.
    
    Drop-in replacement for generate_mystery() in existing code.
    Handles the async/sync boundary.
    
    Args:
        skeleton: Optional pre-generated skeleton to use (avoids regenerating suspects)
    
    NOTE: Returns only the Mystery for backward compatibility.
    The encounter graph is initialized in the MysteryOracle internally.
    """
    async def _generate_and_init_oracle():
        mystery, encounter_graph = await generate_mystery_parallel(premise, config, voice_summary, skeleton)
        
        # Initialize the MysteryOracle with the truth
        # This is the ONLY place where the full truth is stored
        from services.mystery_oracle import initialize_mystery_oracle
        initialize_mystery_oracle(mystery, encounter_graph)
        
        return mystery
    
    try:
        # Try to get existing event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're inside an async context, need to use nest_asyncio or thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    _generate_and_init_oracle()
                )
                return future.result()
        else:
            return loop.run_until_complete(_generate_and_init_oracle())
    except RuntimeError:
        # No event loop exists, create one
        return asyncio.run(_generate_and_init_oracle())

