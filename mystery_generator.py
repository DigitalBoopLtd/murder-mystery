"""Mystery generation logic."""

import os
import re
import json
import random
import logging
from typing import Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import RunnableLambda
from models import Mystery, MysteryPremise
from voice_service import get_voice_service

logger = logging.getLogger(__name__)


# Diverse, tech/geek-friendly mystery settings
SETTING_TYPES = [
    "a luxury cruise ship in the middle of the ocean",
    "a 1920s speakeasy during Prohibition",
    "a remote ski lodge during a blizzard",
    "a Hollywood movie studio in the 1950s",
    "a space station orbiting Mars",
    "a Las Vegas casino on New Year's Eve",
    "a traveling circus in the 1930s",
    "a prestigious university during finals week",
    "a fashion week event in Paris",
    "a tech billionaire's private island",
    "an overnight train through Europe",
    "a haunted theater on opening night",
    "a submarine research vessel",
    "a royal palace during a state dinner",
    "an archaeological dig in Egypt",
    "a jazz club in 1960s New Orleans",
    "a mountain monastery",
    "a luxury safari lodge in Africa",
    "a vintage airplane during a transatlantic flight",
    # Tech/geek-friendly additions
    "a high-tech research lab during a power outage",
    "a gaming convention during a major tournament",
    "a Silicon Valley startup's launch party",
    "a hacker conference in Las Vegas",
    "a retro computing museum during a special exhibit",
    "a space mission control center during a critical launch",
    "a VR gaming arcade in Tokyo",
    "a quantum computing facility during an experiment",
    "a cyberpunk-themed nightclub in Neo-Tokyo",
    "a robotics competition at MIT",
    "a blockchain conference in Singapore",
    "an AI research facility during a breakthrough announcement",
    "a retro arcade bar during a high-score tournament",
    "a sci-fi convention during a costume contest",
    "a secret underground data center",
    "a futuristic smart home during a system malfunction",
    "a cyber security summit in Geneva",
    "a game development studio during crunch time",
    "a tech incubator during demo day",
    "a virtual reality theme park",
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


def generate_mystery_premise() -> MysteryPremise:
    """Generate a lightweight premise for fast startup."""

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
        }
    )
    logger.info(
        "Generated mystery premise: setting=%s, victim=%s",
        premise.setting,
        premise.victim_name,
    )
    return premise


def generate_mystery(premise: Optional[MysteryPremise] = None) -> Mystery:
    """Generate a complete murder mystery scenario.

    If a premise is provided, the model MUST keep the setting and victim
    consistent with that premise.
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

Create an interesting victim with enemies, 4 distinct suspects with secrets and motives, and 5 clues that lead to solving the case. One suspect is the murderer. Include one red herring clue.

IMPORTANT: For each suspect, include these fields for voice matching (not displayed to players):
- "gender": MUST be exactly "male" or "female"
- "age": MUST be exactly one of: "young", "middle_aged", or "old" (based on their age)
- "nationality": MUST be exactly one of: "american", "british", "australian", or "standard" (based on their accent/nationality background)
  - Use "american" for US/Canadian characters
  - Use "british" for UK/English characters  
  - Use "australian" for Australian characters
  - Use "standard" for neutral/international accents

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
                }
            )
            logger.info("Successfully generated full mystery on attempt %s", attempt)
            break
        except Exception as e:
            logger.error("Error generating full mystery on attempt %s: %s", attempt, e)
            if attempt == attempts:
                logger.error("All full mystery generation attempts failed")
                raise
            logger.info("Retrying full mystery generation...")

    # Voices will be assigned on-demand when suspects are first talked to
    # This avoids the API call delay during game startup

    return mystery


def assign_voice_to_suspect(suspect, used_voice_ids: list = None) -> Optional[str]:
    """Assign a voice to a single suspect on-demand.

    Args:
        suspect: Suspect object to assign voice to
        used_voice_ids: List of voice IDs already assigned (to avoid duplicates)

    Returns:
        Assigned voice_id or None if assignment failed
    """
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

        # Get available voices (will be cached after first call)
        voices = voice_service.get_available_voices(
            english_only=True, default_only=True
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
                "Assigned voice '%s' (%s) to %s",
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


def prepare_game_prompt(mystery: Mystery) -> str:
    """Prepare the system prompt for the game master."""
    suspect_list = "\n".join([f"- {s.name} ({s.role})" for s in mystery.suspects])
    clue_list = "\n".join(
        [f'- "{c.id}": {c.description} [Location: {c.location}]' for c in mystery.clues]
    )

    suspect_profiles = "\n".join(
        [
            f"""
### {s.name}
Role: {s.role}
Personality: {s.personality}
Alibi: "{s.alibi}"
Secret: {s.secret}
Will share if asked: {s.clue_they_know}
Guilty: {s.isGuilty}
Voice ID: {s.voice_id or 'None'}{f'''
Murder details: Used {mystery.weapon} because {mystery.motive}''' if s.isGuilty else ''}"""
            for s in mystery.suspects
        ]
    )

    system_prompt = f"""You are the Game Master for a murder mystery game.

## THE CASE
{mystery.setting}

## VICTIM
{mystery.victim.name}: {mystery.victim.background}

## SUSPECTS
{suspect_list}

## CLUES (reveal when player searches correct location)
{clue_list}

## SUSPECT PROFILES (use when calling Interrogate Suspect tool)
{suspect_profiles}

## YOUR ROLE
1. When player wants to TALK to a suspect → Use "Interrogate Suspect" tool. IMPORTANT: Pass the suspect's FULL PROFILE from above INCLUDING their Voice ID.
2. When player wants to SEARCH a location → Describe findings, reveal clues if correct location
3. When player makes ACCUSATION → Check if correct with evidence

## GAME RULES
- 3 wrong accusations = lose
- Win = name murderer + provide evidence  
- Never reveal murderer until correct accusation

## SECRET (NEVER REVEAL)
Murderer: {mystery.murderer}
Weapon: {mystery.weapon}
Motive: {mystery.motive}

## RESPONSE STYLE - VERY IMPORTANT
The player can already see suspects, locations, objectives, and found clues in sidebar cards on their screen.
- Do NOT list out all suspects or their roles
- Do NOT list all locations to search  
- Do NOT repeat the case summary or victim info
- Keep responses focused, atmospheric, and conversational
- When welcoming: Set the MOOD briefly (2-3 sentences), then ask what they'd like to do first
- Be concise - no walls of text or bullet-point lists of what's available

Welcome the player with atmosphere and ask what they'd like to investigate!"""

    return system_prompt
