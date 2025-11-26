"""Mystery generation logic."""

import os
import re
import json
import logging
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import RunnableLambda
from models import Mystery
from voice_service import get_voice_service

logger = logging.getLogger(__name__)


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


def generate_mystery() -> Mystery:
    """Generate a unique murder mystery scenario."""

    llm = ChatOpenAI(
        model="gpt-4o", temperature=0.9, api_key=os.getenv("OPENAI_API_KEY")
    )

    parser = PydanticOutputParser(pydantic_object=Mystery)

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a creative murder mystery writer. Generate a unique murder mystery scenario.
        
{format_instructions}

Be creative with the setting - could be a mansion, cruise ship, theater, space station, etc.

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
                f"Invalid JSON from LLM: {str(e)}\n\nReceived text:\n{text[:500]}"
            )

    validate_json = RunnableLambda(validate_and_parse_json)
    chain = prompt | llm | strip_markdown | validate_json | parser

    mystery = chain.invoke({"format_instructions": parser.get_format_instructions()})

    # Assign voices to suspects
    mystery = assign_voices_to_mystery(mystery)

    return mystery


def assign_voices_to_mystery(mystery: Mystery) -> Mystery:
    """Assign ElevenLabs voices to suspects based on their characteristics.

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
                logger.info(f"Assigned voice {suspect.voice_id} to {suspect.name}")

        return mystery

    except Exception as e:
        logger.error(f"Error assigning voices: {e}")
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
