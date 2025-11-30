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
import json
import logging
import os
import random
import re
from typing import List, Optional, Tuple

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from game.models import Mystery, Suspect, Victim, Clue, MysteryPremise
from mystery_config import MysteryConfig

logger = logging.getLogger(__name__)


# =============================================================================
# INTERMEDIATE MODELS FOR SUB-AGENTS
# =============================================================================

class MysterySkeleton(BaseModel):
    """Lightweight skeleton that guides parallel generation.
    
    This is generated first to establish the framework that all
    parallel sub-agents will work within.
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
    clue_locations: List[str] = Field(
        min_length=5, max_length=5,
        description="5 specific locations where clues will be found"
    )


class SuspectDraft(BaseModel):
    """Output from a single suspect sub-agent."""
    name: str = Field(description="Full character name")
    role: str = Field(description="Relationship to victim")
    personality: str = Field(description="2-3 key personality traits")
    alibi: str = Field(description="Their claimed alibi")
    secret: str = Field(description="What they're hiding")
    clue_they_know: str = Field(description="Info they might share if pressed")
    gender: str = Field(description="male or female")
    age: str = Field(description="young, middle_aged, or old")
    nationality: str = Field(description="american, british, australian, or standard")


class ClueDraft(BaseModel):
    """Output for a single clue."""
    id: str = Field(description="Unique clue ID like clue_1")
    description: str = Field(description="What the clue is")
    location: str = Field(description="Where it's found")
    significance: str = Field(description="What it means for the case")


class ClueSet(BaseModel):
    """Output from the clue sub-agent."""
    clues: List[ClueDraft] = Field(min_length=5, max_length=5)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def strip_markdown_json(text: str) -> str:
    """Strip markdown code blocks from JSON output."""
    if hasattr(text, "content"):
        text = text.content
    elif not isinstance(text, str):
        text = str(text)
    
    # Remove markdown code blocks
    text = re.sub(r"^```(?:json)?\s*\n?", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n?```\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"```", "", text)
    text = text.strip()
    
    # Extract JSON if not starting with {
    if not text.startswith("{") and not text.startswith("["):
        start_idx = text.find("{")
        if start_idx == -1:
            start_idx = text.find("[")
        end_idx = max(text.rfind("}"), text.rfind("]"))
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            text = text[start_idx:end_idx + 1]
    
    return text.strip()


# =============================================================================
# SUB-AGENT: SKELETON GENERATOR
# =============================================================================

async def generate_skeleton(
    config: Optional[MysteryConfig] = None,
    premise: Optional[MysteryPremise] = None,
) -> MysterySkeleton:
    """Stage 1: Generate the mystery skeleton (fast, ~2s).
    
    This determines the structure that all parallel agents will follow.
    Uses gpt-4o-mini for speed since this is just the framework.
    """
    from game.mystery_generator import SETTING_TYPES
    
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.9,
        api_key=os.getenv("OPENAI_API_KEY"),
    )
    
    parser = PydanticOutputParser(pydantic_object=MysterySkeleton)
    
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
2. Create 4 distinct suspect ROLE BRIEFS (not full characters yet)
3. Choose weapon and motive
4. List 5 specific searchable locations for clues

SUSPECT ROLE BRIEFS should be evocative like:
- "The bitter ex-business partner who lost everything"
- "The charming assistant with a dark secret"
- "The victim's estranged child seeking inheritance"
- "The rival who was publicly humiliated"

{tone_instruction}

CRITICAL: Output ONLY valid JSON. No markdown, no explanation.

{format_instructions}"""),
        ("human", """{setting_instruction}

Generate the mystery skeleton with:
- Setting and victim details
- 4 suspect role briefs (one will be the murderer)
- murderer_index (0-3) indicating which suspect is guilty
- Weapon and motive
- 5 specific clue locations fitting the setting

Output ONLY JSON.""")
    ])
    
    chain = prompt | llm
    
    logger.info("[PARALLEL] Generating skeleton...")
    result = await chain.ainvoke({
        "format_instructions": parser.get_format_instructions(),
        "setting_instruction": setting_instruction,
        "tone_instruction": tone_instruction,
    })
    
    text = strip_markdown_json(result.content)
    skeleton = parser.parse(text)
    
    logger.info(
        "[PARALLEL] Skeleton: murderer_index=%d, weapon=%s, %d locations",
        skeleton.murderer_index,
        skeleton.weapon,
        len(skeleton.clue_locations),
    )
    return skeleton


# =============================================================================
# SUB-AGENT: SUSPECT GENERATOR (runs 4x in parallel)
# =============================================================================

async def generate_suspect(
    skeleton: MysterySkeleton,
    role_brief: str,
    suspect_index: int,
    is_guilty: bool,
    voice_options: Optional[str] = None,
) -> Tuple[SuspectDraft, int, bool]:
    """Generate a single suspect (runs in parallel with other suspects).
    
    Uses gpt-4o for quality character development since each suspect
    gets full LLM attention in parallel.
    
    Returns:
        Tuple of (suspect_draft, suspect_index, is_guilty)
    """
    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0.9,
        api_key=os.getenv("OPENAI_API_KEY"),
    )
    
    parser = PydanticOutputParser(pydantic_object=SuspectDraft)
    
    if is_guilty:
        guilt_instructions = f"""
⚠️ THIS SUSPECT IS THE MURDERER ⚠️

They killed the victim using: {skeleton.weapon}
Their motive: {skeleton.motive}

CHARACTER RULES FOR THE GUILTY:
- Their alibi should sound plausible but have SUBTLE holes
- Their secret relates to their guilt but doesn't directly confess
- They should seem suspicious if pressed but not obviously guilty
- Design personality that could believably commit this crime
- Their "clue_they_know" should be misleading or deflecting
"""
    else:
        guilt_instructions = """
This suspect is INNOCENT but should still seem suspicious.

CHARACTER RULES FOR THE INNOCENT:
- Give them their OWN secret unrelated to the murder
- Their alibi should be real but potentially questionable
- They may have HAD motive but didn't act on it
- Their "clue_they_know" should be helpful info they might share
"""
    
    voice_block = ""
    if voice_options:
        voice_block = f"""
VOICE CASTING:
Design this character to match one of these available voice actors.
Consider gender, age range, and accent when creating the character:

{voice_options[:1500]}

Pick characteristics that fit an available voice well."""
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are creating ONE detailed suspect for a murder mystery.

You are building a THREE-DIMENSIONAL character, not a cardboard cutout.
Give them depth, quirks, and believable motivations.

SETTING: {setting}
VICTIM: {victim_name} - {victim_background}

{guilt_instructions}

{voice_block}

QUALITY REQUIREMENTS:
- Name should fit the setting and feel authentic
- Personality should be specific, not generic ("nervous and detail-oriented" not just "suspicious")
- Alibi should be specific with times/places
- Secret should be juicy and character-defining
- Their "clue_they_know" should be something they'd realistically know

CRITICAL: Output ONLY valid JSON. No markdown.

{format_instructions}"""),
        ("human", """Create a fully realized character for this role:
"{role_brief}"

Make them memorable and distinct from typical mystery tropes.

Output ONLY JSON.""")
    ])
    
    chain = prompt | llm
    
    logger.info("[PARALLEL] Generating suspect %d: %s (guilty=%s)", 
                suspect_index, role_brief[:40], is_guilty)
    
    result = await chain.ainvoke({
        "format_instructions": parser.get_format_instructions(),
        "setting": skeleton.setting,
        "victim_name": skeleton.victim_name,
        "victim_background": skeleton.victim_background,
        "guilt_instructions": guilt_instructions,
        "voice_block": voice_block,
        "role_brief": role_brief,
    })
    
    text = strip_markdown_json(result.content)
    suspect = parser.parse(text)
    
    logger.info("[PARALLEL] ✓ Suspect %d: %s (%s)", suspect_index, suspect.name, suspect.role)
    return (suspect, suspect_index, is_guilty)


# =============================================================================
# SUB-AGENT: CLUE GENERATOR
# =============================================================================

async def generate_clues(
    skeleton: MysterySkeleton,
    murderer_role: str,
) -> ClueSet:
    """Generate all clues for the mystery.
    
    Uses gpt-4o for quality clue design that forms a coherent puzzle.
    
    Note: Takes murderer_role (not name) so this can run in PARALLEL
    with suspect generation. The role is enough to design clues.
    """
    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0.8,
        api_key=os.getenv("OPENAI_API_KEY"),
    )
    
    parser = PydanticOutputParser(pydantic_object=ClueSet)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are designing CLUES for a murder mystery game.

CASE DETAILS:
- Setting: {setting}
- Victim: {victim_name} - {victim_background}
- The Murderer's Role: {murderer_role}
- Weapon: {weapon}
- Motive: {motive}

CLUE DESIGN RULES:
1. Create 5 clues spread across these locations: {locations}
2. 3-4 clues should POINT TOWARD the murderer (described above) when combined
3. 1 clue should be a RED HERRING pointing at an innocent suspect
4. Clues should be DISCOVERABLE THINGS: documents, objects, traces, marks
5. Each clue needs: id (clue_1 through clue_5), description, location, significance

PUZZLE DESIGN:
- No single clue should solve the mystery alone
- The clues should interconnect logically
- The solution should feel "obvious in hindsight"
- Red herring should be plausible but have an innocent explanation
- Clues should relate to the murderer's ROLE/MOTIVE, not specific names

CRITICAL: Output ONLY valid JSON.

{format_instructions}"""),
        ("human", """Create 5 interconnected clues at these locations:
{locations}

Design them as a coherent puzzle pointing to "{murderer_role}".
Include one convincing red herring.

Output ONLY JSON.""")
    ])
    
    chain = prompt | llm
    
    logger.info("[PARALLEL] Generating clues for %d locations...", len(skeleton.clue_locations))
    
    result = await chain.ainvoke({
        "format_instructions": parser.get_format_instructions(),
        "setting": skeleton.setting,
        "victim_name": skeleton.victim_name,
        "victim_background": skeleton.victim_background,
        "murderer_role": murderer_role,
        "weapon": skeleton.weapon,
        "motive": skeleton.motive,
        "locations": ", ".join(skeleton.clue_locations),
    })
    
    text = strip_markdown_json(result.content)
    clue_set = parser.parse(text)
    
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
) -> Mystery:
    """Assemble final Mystery from sub-agent outputs.
    
    Combines all parallel outputs into the final Mystery model.
    Also handles voice assignment post-assembly.
    """
    # Sort suspects by their original index to maintain order
    suspect_results.sort(key=lambda x: x[1])
    
    # Convert drafts to full Suspect models
    suspects: List[Suspect] = []
    murderer_name = None
    
    for draft, index, is_guilty in suspect_results:
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
        )
        suspects.append(suspect)
        
        if is_guilty:
            murderer_name = draft.name
    
    # Convert clue drafts to Clue models
    clues: List[Clue] = []
    for clue_draft in clue_set.clues:
        clue = Clue(
            id=clue_draft.id,
            description=clue_draft.description,
            location=clue_draft.location,
            significance=clue_draft.significance,
        )
        clues.append(clue)
    
    # Assign voices if available
    if voice_summary:
        suspects = _assign_voices_to_suspects(suspects, voice_summary)
    
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
    )
    
    logger.info(
        "[PARALLEL] Assembled mystery: %s murdered by %s with %s",
        skeleton.victim_name,
        murderer_name,
        skeleton.weapon,
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
) -> Mystery:
    """Generate a complete mystery using parallel sub-agents.
    
    Performance: ~8-10s vs ~15s for monolithic generation.
    
    This is NOT the agent that users talk to. Users interact with the
    Game Master Agent in services/agent.py. This function only runs once
    at game start to generate the mystery content.
    
    Architecture:
        1. Skeleton Agent (gpt-4o-mini, ~6s) - Framework
        2. PARALLEL: 4x Suspects + Clues (~5s total, not sequential!)
        3. Assembly + Voice Assignment
    
    Key optimization: Suspects and clues run IN PARALLEL because clues
    only need the murderer's ROLE (from skeleton), not their NAME.
    
    Args:
        premise: Optional preset premise (setting, victim)
        config: Game configuration for difficulty/tone
        voice_summary: Available voices for assignment
        
    Returns:
        Complete Mystery object ready for gameplay
    """
    import time
    t_start = time.perf_counter()
    
    # =========================================================================
    # STAGE 1: SKELETON (~6s)
    # =========================================================================
    logger.info("[PARALLEL] ═══ Stage 1: Generating skeleton ═══")
    t1 = time.perf_counter()
    
    skeleton = await generate_skeleton(config=config, premise=premise)
    
    t2 = time.perf_counter()
    logger.info("[PARALLEL] Skeleton complete in %.2fs", t2 - t1)
    
    # =========================================================================
    # STAGE 2: PARALLEL SUSPECTS + CLUES (~5s total, not 8s sequential!)
    # =========================================================================
    logger.info("[PARALLEL] ═══ Stage 2: Generating suspects + clues IN PARALLEL ═══")
    t3 = time.perf_counter()
    
    # Get murderer role for clue generation (don't need name yet!)
    murderer_role = skeleton.suspect_briefs[skeleton.murderer_index]
    
    # Create tasks for each suspect
    suspect_tasks = []
    for i, role_brief in enumerate(skeleton.suspect_briefs):
        is_guilty = (i == skeleton.murderer_index)
        task = generate_suspect(
            skeleton=skeleton,
            role_brief=role_brief,
            suspect_index=i,
            is_guilty=is_guilty,
            voice_options=voice_summary[:2000] if voice_summary else None,
        )
        suspect_tasks.append(task)
    
    # Create clue task - runs IN PARALLEL with suspects!
    clue_task = generate_clues(skeleton, murderer_role)
    
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
    
    return mystery


# =============================================================================
# SYNC WRAPPER FOR EXISTING CODE
# =============================================================================

def generate_mystery_parallel_sync(
    premise: Optional[MysteryPremise] = None,
    config: Optional[MysteryConfig] = None,
    voice_summary: Optional[str] = None,
) -> Mystery:
    """Synchronous wrapper for parallel mystery generation.
    
    Drop-in replacement for generate_mystery() in existing code.
    Handles the async/sync boundary.
    """
    try:
        # Try to get existing event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're inside an async context, need to use nest_asyncio or thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    generate_mystery_parallel(premise, config, voice_summary)
                )
                return future.result()
        else:
            return loop.run_until_complete(
                generate_mystery_parallel(premise, config, voice_summary)
            )
    except RuntimeError:
        # No event loop exists, create one
        return asyncio.run(
            generate_mystery_parallel(premise, config, voice_summary)
        )

