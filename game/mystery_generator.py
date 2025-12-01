"""Mystery generation logic.

Uses PARALLEL generation with structured outputs:
- Skeleton → 4 suspects + clues generated concurrently (~6-8s total)
- LangChain's with_structured_output() for reliable Pydantic parsing
- Automatic retries with exponential backoff on failures

IMPORTANT: This does NOT create an agent that users interact with.
The user-facing agent is the Game Master in services/agent.py.
This generator only runs once at game start to create the mystery content.
"""

import os
import re
import json
import random
import logging
from typing import Optional, TYPE_CHECKING
from langchain_openai import ChatOpenAI

if TYPE_CHECKING:
    from game.public_mystery import PublicMystery
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import RunnableLambda
from game.models import Mystery, MysteryPremise
from services.voice_service import get_voice_service
from mystery_config import MysteryConfig

logger = logging.getLogger(__name__)


# Diverse, tech/geek-friendly mystery settings
SETTING_TYPES = [
    "A luxury cruise ship in the middle of the ocean",
    "A 1920s speakeasy during Prohibition",
    "A remote ski lodge during a blizzard",
    "A Hollywood movie studio in the 1950s",
    "A space station orbiting Mars",
    "A Las Vegas casino on New Year's Eve",
    "A traveling circus in the 1930s",
    "A prestigious university during finals week",
    "A fashion week event in Paris",
    "A tech billionaire's private island",
    "An overnight train through Europe",
    "A haunted theater on opening night",
    "A submarine research vessel",
    "A royal palace during a state dinner",
    "An archaeological dig in Egypt",
    "A jazz club in 1960s New Orleans",
    "A mountain monastery",
    "A luxury safari lodge in Africa",
    "A vintage airplane during a transatlantic flight",
    # Tech/geek-friendly additions
    "A high-tech research lab during a power outage",
    "A gaming convention during a major tournament",
    "A Silicon Valley startup's launch party",
    "A hacker conference in Las Vegas",
    "A retro computing museum during a special exhibit",
    "A space mission control center during a critical launch",
    "A VR gaming arcade in Tokyo",
    "A quantum computing facility during an experiment",
    "A cyberpunk-themed nightclub in Neo-Tokyo",
    "A robotics competition at MIT",
    "A blockchain conference in Singapore",
    "An AI research facility during a breakthrough announcement",
    "A retro arcade bar during a high-score tournament",
    "A sci-fi convention during a costume contest",
    "A secret underground data center",
    "A futuristic smart home during a system malfunction",
    "A cyber security summit in Geneva",
    "A game development studio during crunch time",
    "A tech incubator during demo day",
    "A virtual reality theme park",
]


def strip_markdown_json(message) -> str:
    """Strip markdown code blocks from JSON output."""
    # Extract content if it's an AIMessage object
    if hasattr(message, "content"):
        text = message.content
    elif isinstance(message, str):
        text = message
    else:
        text = str(message)

    # More aggressive markdown removal - handle various formats
    # Remove ```json at start
    text = re.sub(r"^```(?:json)?\s*\n?", "", text, flags=re.MULTILINE)
    # Remove ``` at end
    text = re.sub(r"\n?```\s*$", "", text, flags=re.MULTILINE)
    # Remove any remaining ``` markers
    text = re.sub(r"```", "", text)
    # Clean up any leading/trailing whitespace
    text = text.strip()

    # If text doesn't start with {, try to find the JSON object
    if not text.startswith("{"):
        # Try to find the first { and last }
        start_idx = text.find("{")
        end_idx = text.rfind("}")
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            text = text[start_idx : end_idx + 1]

    return text.strip()


def generate_mystery_premise(config: Optional[MysteryConfig] = None) -> MysteryPremise:
    """Generate a lightweight premise for fast startup.

    If a config is provided, use its setting/era preferences to choose the
    setting type; otherwise, pick a random setting type to force variety.
    """

    tone_line = ""
    if config:
        setting_type = config.get_setting_for_generation()
        tone_instruction = config.get_tone_instruction()
        if tone_instruction:
            tone_line = f"""

TONE: {tone_instruction}
"""
    else:
        # Pick a random setting type to force variety
        setting_type = random.choice(SETTING_TYPES)

    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0.8,
        api_key=os.getenv("OPENAI_API_KEY"),
    )

    parser = PydanticOutputParser(pydantic_object=MysteryPremise)

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a creative murder mystery writer with a geeky sense of humor, writing for tech professionals who love AI, computer games, and clever puzzles.

Generate a short premise for a murder mystery game as STRICT JSON only
matching this schema:
{format_instructions}

IMPORTANT: The setting MUST be: {setting_type}
Build the victim and scenario around this specific setting. Make it vivid, atmospheric, and engaging.

Constraints:
{tone_line}
- setting: 1-2 sentences describing {setting_type}, vivid but concise. Include specific details that make it feel real.
- victim_name: single full name appropriate for this setting
- victim_background: 1-2 sentences about who they are and why someone
  might want them dead. Make it interesting and fitting for the tech/geek audience.

CRITICAL: Return ONLY valid JSON. Do NOT wrap it in markdown code blocks.
Do NOT include any text before or after the JSON. Start with {{ and end with }}.""",
            ),
            ("human", "Generate a concise murder mystery premise."),
        ]
    )

    strip_markdown = RunnableLambda(strip_markdown_json)

    def validate_and_parse_premise(text: str):
        """Validate JSON for the premise and parse it."""
        try:
            json.loads(text)
            return text
        except json.JSONDecodeError as e:
            start_idx = text.find("{")
            end_idx = text.rfind("}")
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                json_text = text[start_idx : end_idx + 1]
                try:
                    json.loads(json_text)
                    return json_text
                except json.JSONDecodeError:
                    pass
            raise ValueError(
                f"Invalid JSON for premise from LLM: {e!s}\n\nReceived text:\n{text[:500]}"
            ) from e

    validate_json = RunnableLambda(validate_and_parse_premise)
    chain = prompt | llm | strip_markdown | validate_json | parser

    logger.info("Generating mystery premise...")
    premise = chain.invoke(
        {
            "format_instructions": parser.get_format_instructions(),
            "setting_type": setting_type,
            "tone_line": tone_line,
        }
    )
    logger.info(
        "Generated mystery premise: setting=%s, victim=%s",
        premise.setting,
        premise.victim_name,
    )
    return premise


def generate_location_descriptions(mystery: Mystery) -> dict:
    """Generate rich visual descriptions for each unique location in the mystery.

    Returns a dict: {location_name: visual_description}.
    """
    try:
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.8,
            api_key=os.getenv("OPENAI_API_KEY"),
        )

        # Collect unique locations from the clues
        locations = sorted({clue.location for clue in mystery.clues})
        if not locations:
            return {}

        # Build a block that includes clues per location so the LLM can anchor visuals
        location_blocks = []
        for loc in locations:
            loc_clues = [
                clue
                for clue in mystery.clues
                if clue.location == loc
            ]
            block_lines = [f"- {loc}:"]
            if loc_clues:
                for c in loc_clues:
                    block_lines.append(
                        f"  - Clue '{c.id}': {c.description} (significance: {c.significance})"
                    )
            location_blocks.append("\n".join(block_lines))
        locations_with_clues = "\n".join(location_blocks)

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are a background concept artist for a 1990s point-and-click adventure game.

Your job is to write short VISUAL DESCRIPTIONS for game locations that a painter can use
to design unique scene art. Focus ONLY on the environment — no characters, no plot spoilers.

For EACH location, write 1–2 sentences that describe:
- Layout and geometry of the space
- Key props, furniture, machines, or landmarks
- Colors and lighting
- Interior vs exterior feel
- Whether the \"camera\" should be outside looking at an object/room, or inside a confined space
  (e.g., \"inside an open briefcase looking out over the desk\" vs \"a briefcase sitting on the desk\").

Use the CLUES for each location to decide what should be visually emphasized and whether
the primary viewpoint is outside or inside any container (briefcase, safe, locker, car trunk, etc.).

Tone: vivid but concise. Imagine you are briefing an artist.

Return STRICT JSON mapping location name to description, for example:
{{
  "Lab 1": "A narrow lab lined with humming consoles and glass sample cases, neon indicator lights reflecting off polished floors.",
  "Security Mainframe": "A cramped control room packed with server racks and glowing monitors, cables snaking across industrial flooring."
}}

Do NOT include characters or actions. Do NOT mention the murder directly.
""",
                ),
                (
                    "human",
                    """MYSTERY SETTING:
{setting}

LOCATIONS AND THEIR CLUES:
{locations}

Return ONLY the JSON object mapping each location name to its visual description.""",
                ),
            ]
        )

        chain = prompt | llm
        raw = chain.invoke(
            {
                "setting": mystery.setting,
                "locations": locations_with_clues,
            }
        )

        # Reuse markdown/JSON stripping helper
        text = strip_markdown_json(raw)
        data = json.loads(text)

        # Ensure we only keep strings for known locations
        # Normalize both keys for comparison (strip trailing punctuation)
        def normalize_loc(s: str) -> str:
            return s.rstrip(".,;:!? ").lower()
        
        # Build lookup from normalized LLM keys to original descriptions
        normalized_data = {normalize_loc(k): v for k, v in data.items()}
        
        result: dict = {}
        for loc in locations:
            # Try exact match first, then normalized match
            desc = data.get(loc)
            if not desc:
                desc = normalized_data.get(normalize_loc(loc))
            if isinstance(desc, str) and desc.strip():
                result[loc] = desc.strip()

        logger.info(
            "Generated location descriptions for %d/%d locations",
            len(result),
            len(locations),
        )
        return result
    except Exception as e:  # noqa: BLE001
        logger.error("Error generating location descriptions: %s", e)
        return {}


def generate_mystery(
    premise: Optional[MysteryPremise] = None,
    config: Optional[MysteryConfig] = None,
    voice_summary: Optional[str] = None,
    skeleton=None,  # Optional MysterySkeleton - avoids circular import
) -> Mystery:
    """Generate a complete murder mystery scenario.
    
    Uses parallel generation with structured outputs and automatic retries.
    No fallback to monolithic - parallel is now the only path.
    
    IMPORTANT: This is NOT the agent users interact with. Users talk to
    the Game Master Agent in services/agent.py. This function only runs
    once at game start to create the mystery content.

    Args:
        premise: Optional preset premise (setting, victim)
        config: Game configuration for difficulty/tone
        voice_summary: Available voices for character casting
        skeleton: Optional pre-generated skeleton (for early UI display consistency)
        
    Returns:
        Complete Mystery object ready for gameplay
        
    Raises:
        Exception: If mystery generation fails after all retries
    """
    from game.parallel_mystery import generate_mystery_parallel_sync
    logger.info("[MYSTERY] Using PARALLEL generation (structured output + retries)")
    return generate_mystery_parallel_sync(
        premise=premise,
        config=config,
        voice_summary=voice_summary,
        skeleton=skeleton,
    )


def _generate_mystery_monolithic(
    premise: Optional[MysteryPremise] = None,
    config: Optional[MysteryConfig] = None,
    voice_summary: Optional[str] = None,
) -> Mystery:
    """Generate a complete murder mystery in a single LLM call (legacy mode).

    This is the original monolithic generator. It's slower (~15s) but serves
    as a fallback if parallel generation fails.
    
    If a premise is provided, the model MUST keep the setting and victim
    consistent with that premise.
    
    If voice_summary is provided, the model will create characters that match
    the available voices and assign voice_id directly to each suspect.
    """

    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0.9,
        api_key=os.getenv("OPENAI_API_KEY"),
    )

    parser = PydanticOutputParser(pydantic_object=Mystery)

    # Premise block used to anchor the full mystery to a previously
    # generated setting and victim, while still using the same Pydantic
    # schema for the final output.
    premise_block = ""
    if premise:
        premise_block = f"""
Use this fixed setting and victim (do NOT change names or key details):

Setting: {premise.setting}

Victim name: {premise.victim_name}
Victim background: {premise.victim_background}
"""

    # Optional difficulty/tone guidance derived from configuration
    difficulty_block = ""
    tone_block = ""
    if config is not None:
        try:
            difficulty = config.get_difficulty_modifier()
        except Exception:
            difficulty = None

        if difficulty:
            difficulty_block = f"""

DIFFICULTY SETTINGS:
- Clue clarity: {difficulty.get('clue_clarity')}
- Red herrings: {difficulty.get('red_herrings')}
- Alibi complexity: {difficulty.get('alibi_complexity')}
- Hint level: {difficulty.get('hint_level')}"""

        tone_instruction = config.get_tone_instruction()
        if tone_instruction:
            tone_block = f"""

TONE OVERRIDE:
{tone_instruction}"""

    # Voice assignment block - if voices are available, LLM assigns them during generation
    voice_block = ""
    if voice_summary:
        voice_block = f"""

VOICE ASSIGNMENT REQUIREMENT:
You have access to a library of voice actors. For each suspect, you MUST:
1. Design their character to match one of the available voices
2. Set their "voice_id" field to the exact ID (the alphanumeric string after "ID:") from the list below
3. CRITICAL: Use the VOICE ID (the alphanumeric string), NOT the voice name!
4. Use DIFFERENT voices for each suspect (no duplicates!)
5. Match voice characteristics: gender MUST match, age should match, accent is a bonus

{voice_summary}

VOICE MATCHING RULES:
- Gender must match exactly (male character → male voice)
- Age should match (young character → young voice, etc.)
- Accent can inform character nationality/background
- Prioritize diverse casting - use different voice types for variety
- If limited voices, prioritize gender match over age/accent

CRITICAL REMINDER: The "voice_id" field must be the alphanumeric ID (like "JBFqnCBsd6RMkjVDRZzb"), NOT the voice name (like "Laura" or "George")!
"""
    else:
        # No voices available - generate without voice_id assignments
        voice_block = """

NOTE: No voice actors are available for this session. 
Generate characters normally but leave "voice_id" as null.
The game will run in "Silent Film" mode with text-only dialogue.
"""

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a creative murder mystery writer with a geeky sense of humor, writing for tech professionals who love AI, computer games, and clever puzzles. Generate a UNIQUE murder mystery scenario.

{premise_block}
{format_instructions}

DIVERSITY REQUIREMENT: If no premise is provided, AVOID common tropes like Victorian mansions, country estates, or generic dinner parties. Instead, choose something unexpected and creative from these categories:
- Transportation (trains, ships, planes, submarines, space stations)
- Entertainment (theaters, circuses, film sets, casinos, gaming conventions)
- Historical periods (1920s speakeasy, Wild West, Ancient Rome)
- Exotic locations (safari lodge, archaeological dig, monastery)
- Modern tech settings (research labs, hacker conferences, VR arcades, startup offices)
- Sci-fi/futuristic (space stations, cyberpunk clubs, smart homes, quantum labs)

TONE: Your audience appreciates clever references, subtle tech humor, and well-crafted puzzles. Make the mystery engaging and intellectually satisfying.
{tone_block}
{difficulty_block}
{voice_block}

Create an interesting victim with enemies, 4 distinct suspects with secrets and motives, and 5 clues that lead to solving the case. One suspect is the murderer. Include one red herring clue.

IMPORTANT: For each suspect, include these fields:
- "name": Do NOT use quotes or nicknames inside names (use "Vincent Malloy" not "Vincent "Vince" Malloy")
- "gender": MUST be exactly "male" or "female"
- "age": MUST be exactly one of: "young", "middle_aged", or "old" (based on their age)
- "nationality": MUST be exactly one of: "american", "british", "australian", or "standard" (based on their accent/nationality background)
  - Use "american" for US/Canadian characters
  - Use "british" for UK/English characters  
  - Use "australian" for Australian characters
  - Use "standard" for neutral/international accents
- "voice_id": The voice ID assigned from the available voices (or null if no voices available)

CRITICAL: Return ONLY valid JSON. Do NOT wrap it in markdown code blocks. Do NOT include any text before or after the JSON. Start with {{ and end with }}.""",
            ),
            ("human", "Generate a unique murder mystery scenario."),
        ]
    )

    # Add a step to strip markdown before parsing
    strip_markdown = RunnableLambda(strip_markdown_json)

    # Add validation step to ensure JSON is valid
    def validate_and_parse_json(text: str):
        """Validate JSON and parse it."""
        try:
            # Try to parse as JSON first to validate
            json.loads(text)
            return text
        except json.JSONDecodeError as e:
            # If JSON is invalid, try to extract valid JSON
            start_idx = text.find("{")
            end_idx = text.rfind("}")
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                json_text = text[start_idx : end_idx + 1]
                try:
                    json.loads(json_text)
                    return json_text
                except json.JSONDecodeError:
                    pass
            raise ValueError(
                f"Invalid JSON from LLM: {e!s}\n\nReceived text:\n{text[:500]}"
            ) from e

    validate_json = RunnableLambda(validate_and_parse_json)
    chain = prompt | llm | strip_markdown | validate_json | parser

    # Robust invocation with simple retry on JSON/parse errors
    attempts = 3
    for attempt in range(1, attempts + 1):
        try:
            logger.info("Generating full mystery (attempt %s/%s)...", attempt, attempts)
            mystery = chain.invoke(
                {
                    "format_instructions": parser.get_format_instructions(),
                    "premise_block": premise_block,
                    "tone_block": tone_block,
                    "difficulty_block": difficulty_block,
                    "voice_block": voice_block,
                }
            )
            logger.info("Successfully generated full mystery on attempt %s", attempt)
            
            # Validate and fix voice IDs (LLM sometimes uses names instead of IDs)
            if voice_summary:
                voice_service = get_voice_service()
                if voice_service.is_available:
                    available_voices = voice_service.get_available_voices()
                    voice_id_map = {v.voice_id: v for v in available_voices}
                    voice_name_to_id = {v.name.lower(): v.voice_id for v in available_voices}
                    
                    for suspect in mystery.suspects:
                        if suspect.voice_id:
                            # Check if voice_id is actually a name (common mistake)
                            if suspect.voice_id.lower() in voice_name_to_id:
                                logger.warning(
                                    "LLM used voice name '%s' instead of ID for %s, fixing...",
                                    suspect.voice_id, suspect.name
                                )
                                suspect.voice_id = voice_name_to_id[suspect.voice_id.lower()]
                            # Check if voice_id is invalid
                            elif suspect.voice_id not in voice_id_map:
                                logger.warning(
                                    "Invalid voice_id '%s' for %s, will be reassigned on-demand",
                                    suspect.voice_id, suspect.name
                                )
                                suspect.voice_id = None  # Will be fixed on-demand
            
            # Log voice assignments
            if voice_summary:
                assigned_voices = [s.voice_id for s in mystery.suspects if s.voice_id]
                logger.info(
                    "Voice assignments: %d/%d suspects have voices",
                    len(assigned_voices),
                    len(mystery.suspects)
                )
                for s in mystery.suspects:
                    logger.info(
                        "  %s: voice_id=%s, gender=%s, age=%s",
                        s.name, s.voice_id, s.gender, s.age
                    )
            # Clear any placeholder portrait_path values the LLM may have generated
            # (we generate portraits ourselves using the Image MCP server)
            for suspect in mystery.suspects:
                if suspect.portrait_path and not os.path.exists(suspect.portrait_path):
                    suspect.portrait_path = None
            
            # Assign location_hints to suspects (each suspect reveals one location)
            # This allows locations to be "unlocked" through suspect interrogation
            clue_locations = list(set(clue.location for clue in mystery.clues))
            for idx, suspect in enumerate(mystery.suspects):
                if idx < len(clue_locations):
                    suspect.location_hint = clue_locations[idx]
                    logger.info(
                        "Assigned location_hint '%s' to suspect %s",
                        suspect.location_hint, suspect.name
                    )
            
            break
        except Exception as e:
            logger.error("Error generating full mystery on attempt %s: %s", attempt, e)
            if attempt == attempts:
                logger.error("All full mystery generation attempts failed")
                raise
            logger.info("Retrying full mystery generation...")

    # Note: When voice_summary is provided, voices are assigned during generation
    # by the LLM. No post-hoc matching needed!
    # If no voice_summary, suspects will have voice_id=None (silent film mode)

    return mystery


def assign_voice_to_suspect(suspect, used_voice_ids: list = None) -> Optional[str]:
    """Assign a voice to a single suspect on-demand (fallback for late voice assignment).
    
    NOTE: With voice-first character generation, this function is rarely needed.
    It's kept as a fallback for edge cases where a suspect doesn't have a voice_id
    assigned during mystery generation.

    Args:
        suspect: Suspect object to assign voice to
        used_voice_ids: List of voice IDs already assigned (to avoid duplicates)

    Returns:
        Assigned voice_id or None if assignment failed
    """
    # If suspect already has a voice, don't reassign
    if suspect.voice_id:
        logger.info("Suspect %s already has voice_id=%s", suspect.name, suspect.voice_id)
        return suspect.voice_id
    
    try:
        voice_service = get_voice_service()

        if not voice_service.is_available:
            logger.info("ElevenLabs not configured, skipping voice assignment")
            return None

        used_voice_ids = used_voice_ids or []

        # Convert suspect to dict for voice matching
        suspect_dict = {
            "name": suspect.name,
            "role": suspect.role,
            "personality": suspect.personality,
            "gender": suspect.gender,
            "age": suspect.age,
            "nationality": suspect.nationality,
        }

        # Get available voices (use all voices, no filtering)
        voices = voice_service.get_available_voices(
            english_only=False, default_only=False
        )
        if not voices:
            logger.warning("No voices available for assignment")
            return None

        # Match voice to suspect
        voice = voice_service.match_voice_to_suspect(
            suspect_dict, voices, used_voice_ids
        )
        if voice:
            suspect.voice_id = voice.voice_id
            logger.info(
                "Assigned voice '%s' (%s) to %s (fallback)",
                voice.name,
                voice.voice_id,
                suspect.name,
            )
            return voice.voice_id
        else:
            logger.warning("Could not assign voice to %s", suspect.name)
            return None

    except Exception:
        logger.exception("Error assigning voice to %s", suspect.name)
        return None


def assign_voices_to_mystery(mystery: Mystery) -> Mystery:
    """Assign ElevenLabs voices to suspects based on their characteristics.

    DEPRECATED: This function is kept for backward compatibility but is no longer
    called during game startup. Voices are now assigned on-demand.

    Args:
        mystery: The generated mystery

    Returns:
        Mystery with voice_id assigned to each suspect
    """
    try:

        voice_service = get_voice_service()

        if not voice_service.is_available:
            logger.info("ElevenLabs not configured, skipping voice assignment")
            return mystery

        # Convert suspects to dicts for voice matching
        suspect_dicts = [
            {
                "name": s.name,
                "role": s.role,
                "personality": s.personality,
                "gender": s.gender,  # Include explicit gender if available
                "age": s.age,  # Include explicit age if available
                "nationality": s.nationality,  # Include explicit nationality/accent if available
            }
            for s in mystery.suspects
        ]

        # Get voice assignments
        assignments = voice_service.assign_voices_to_suspects(suspect_dicts)

        # Update suspects with voice IDs
        for suspect in mystery.suspects:
            if suspect.name in assignments:
                suspect.voice_id = assignments[suspect.name]
                logger.info("Assigned voice %s to %s", suspect.voice_id, suspect.name)

        return mystery

    except Exception:
        logger.exception("Error assigning voices")
        return mystery


def prepare_game_prompt(
    mystery: Mystery, tone_instruction: Optional[str] = None
) -> str:
    """Prepare the system prompt for the game master.
    
    IMPORTANT: This prompt is carefully structured to HIDE information
    the player hasn't discovered yet. The GM only sees:
    - Clue LOCATIONS (not descriptions) - so they know where to direct searches
    - Suspect public info (role, personality, alibi)
    - Suspect secrets are accessed by tools internally, NOT shown here
    """
    suspect_list = "\n".join([f"- {s.name} ({s.role})" for s in mystery.suspects])
    
    # Only show locations, NOT clue descriptions (to prevent early reveals)
    location_list = "\n".join(
        [f'- "{c.location}" (searchable)' for c in mystery.clues]
    )

    # Build suspect profiles WITHOUT secrets (secrets accessed by tool internally)
    suspect_profiles = "\n".join(
        [
            f"""
### {s.name}
Role: {s.role}
Personality: {s.personality}
Alibi: "{s.alibi}"
Voice ID: {s.voice_id or 'None'}

EMOTIONAL STATE (initial):
- Trust: 50%
- Nervousness: 30%
- Contradictions caught: 0

CONVERSATION HISTORY:
No previous conversations."""
            for s in mystery.suspects
        ]
    )

    tone_block = ""
    if tone_instruction:
        tone_block = f"""

## TONE
{tone_instruction}
"""

    system_prompt = f"""You are the Game Master for a murder mystery game.

## THE CASE
{mystery.setting}

## VICTIM
{mystery.victim.name}: {mystery.victim.background}

## SUSPECTS (public info only)
{suspect_list}

## SEARCHABLE LOCATIONS (clue details hidden until searched)
{location_list}

## SUSPECT PROFILES (for interrogate_suspect tool)
{suspect_profiles}

## YOUR ROLE

CRITICAL RULE: You can ONLY reveal information the player has EARNED through investigation!
- Clues are revealed when the player SEARCHES the correct location
- Suspect secrets emerge through INTERROGATION, not narration  
- Do NOT summarize case details the player hasn't discovered

### 1. TALKING TO SUSPECTS
When a player wants to talk to someone:
- Call "interrogate_suspect" with:
  * suspect_name: full name
  * player_question: what the player said
  * emotional_context: current trust/nervousness and conversation summary
- The tool has secure access to suspect secrets and will roleplay correctly
- Do NOT reveal secrets in your narration - let them emerge through dialogue

### 2. SEARCHING LOCATIONS
When a player searches somewhere:
- Call "describe_scene_for_image" with just the location_name
- The tool looks up clues and generates narration + image brief
- USE THE TOOL OUTPUT VERBATIM (includes all necessary markers)

### 3. ACCUSATIONS
When player formally accuses someone:
- Call "make_accusation" with suspect name
- Only for FINAL accusations, not theorizing

## RAG MEMORY TOOLS
- "search_past_statements" → When player references something said earlier
- "find_contradictions" → When checking if a suspect contradicted themselves  
- "get_cross_references" → When confronting a suspect with what others said

## GAME RULES
- 3 wrong accusations = lose
- Win = name murderer + provide evidence  
- NEVER reveal murderer, weapon, or motive until correct accusation
- NEVER reveal clue details until player searches that location
- NEVER reveal suspect secrets - let them emerge through interrogation

## RESPONSE STYLE - VERY IMPORTANT
The player can see suspects, locations, and found clues in sidebar cards.
- ALWAYS respond in ENGLISH
- Do NOT list out suspects, locations, or case summary
- Keep responses focused, atmospheric, and conversational
- TALK responses: 1 short paragraph (~60-80 words)
- SEARCH responses: 2-3 sentences (~50 words max) - just what they SEE
  * Do NOT summarise the case, do NOT give instructions, do NOT repeat the location name.
  * Example: "Dust motes drift through a shaft of light from the cracked window. A half-empty coffee mug sits beside a laptop, its screen frozen on an unfinished email."
- For any other narration: 1 short paragraph (2–3 sentences, ~60–80 words).
- When welcoming: Set the MOOD briefly (2–3 sentences), then ask what they'd like to do first.
- Be concise – no walls of text or bullet‑point lists of what's available.

{tone_block}

Welcome the player with atmosphere and ask what they'd like to investigate!"""

    return system_prompt


def prepare_secure_game_prompt(
    public_mystery: "PublicMystery",
    tone_instruction: Optional[str] = None,
) -> str:
    """Prepare the system prompt using ONLY public information.
    
    SECURE VERSION: Uses PublicMystery (sanitized view) instead of full Mystery.
    This ensures the GM agent CANNOT access:
    - Who the murderer is
    - Suspect secrets
    - Whether alibis are true/false
    
    Args:
        public_mystery: The sanitized public view of the mystery
        tone_instruction: Optional tone guidance
    """
    from game.public_mystery import build_gm_context
    
    # Get the context from public mystery
    case_context = build_gm_context(public_mystery)
    
    # Build suspect profiles from public info only
    suspect_profiles = "\n".join(
        f"""
### {s.name}
Role: {s.role}
Personality: {s.personality}
Alibi claim: "{s.alibi}"
Status: {"INTERROGATED" if s.has_been_interrogated else "Not yet questioned"}
"""
        for s in public_mystery.suspects
    )
    
    tone_block = ""
    if tone_instruction:
        tone_block = f"\n## TONE\n{tone_instruction}\n"
    
    return f"""You are the Game Master for a murder mystery game.

{case_context}

## SUSPECT PROFILES (for interrogate_suspect tool)
{suspect_profiles}

## YOUR ROLE AS GAME MASTER

CRITICAL: You can ONLY reveal information the player has EARNED through investigation!
- Clues are revealed when the player SEARCHES the correct location
- Suspect secrets emerge through INTERROGATION via the tool
- You do NOT know who the murderer is - only the Oracle knows

### AVAILABLE TOOLS

1. **interrogate_suspect** - When player wants to talk to someone
   - Pass: suspect_name, player_question
   - The Oracle generates the suspect's response
   - You receive ONLY the response text (no secrets exposed)

2. **describe_scene_for_image** - When player searches a location
   - Pass: location_name
   - Returns narration + image brief

3. **make_accusation** - When player formally accuses someone
   - Only for FINAL accusations, not theorizing

4. **RAG Memory Tools** - For recalling past conversations
   - search_past_statements, find_contradictions, get_cross_references

## GAME RULES
- 3 wrong accusations = lose
- Win = name murderer + provide evidence
- NEVER reveal murderer until correct accusation
- NEVER reveal clue details until player searches

## RESPONSE STYLE
- Keep responses SHORT for voice narration
- TALK: ~60-80 words
- SEARCH: ~50 words (just what they SEE)
- Be atmospheric and conversational
{tone_block}
Continue the investigation based on the player's message."""
