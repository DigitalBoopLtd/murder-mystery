"""Mystery generation logic."""
import os
import re
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import RunnableLambda
from models import Mystery


def strip_markdown_json(message) -> str:
    """Strip markdown code blocks from JSON output."""
    # Extract content if it's an AIMessage object
    if hasattr(message, 'content'):
        text = message.content
    elif isinstance(message, str):
        text = message
    else:
        text = str(message)
    
    # Remove markdown code blocks (```json ... ``` or ``` ... ```)
    text = re.sub(r'^```(?:json)?\s*\n', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n```\s*$', '', text, flags=re.MULTILINE)
    return text.strip()


def generate_mystery() -> Mystery:
    """Generate a unique murder mystery scenario."""
    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0.9,
        api_key=os.getenv("OPENAI_API_KEY")
    )
    
    parser = PydanticOutputParser(pydantic_object=Mystery)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a creative murder mystery writer. Generate a unique murder mystery scenario.
        
{format_instructions}

Be creative with the setting - could be a mansion, cruise ship, theater, space station, etc.

Create an interesting victim with enemies, 4 distinct suspects with secrets and motives, and 5 clues that lead to solving the case. One suspect is the murderer. Include one red herring clue.

IMPORTANT: Return ONLY valid JSON. Do not wrap it in markdown code blocks."""),
        ("human", "Generate a unique murder mystery scenario.")
    ])
    
    # Add a step to strip markdown before parsing
    strip_markdown = RunnableLambda(strip_markdown_json)
    chain = prompt | llm | strip_markdown | parser
    
    mystery = chain.invoke({"format_instructions": parser.get_format_instructions()})
    return mystery


def prepare_game_prompt(mystery: Mystery) -> str:
    """Prepare the system prompt for the game master."""
    suspect_list = "\n".join([f"- {s.name} ({s.role})" for s in mystery.suspects])
    clue_list = "\n".join([f"- \"{c.id}\": {c.description} [Location: {c.location}]" for c in mystery.clues])
    
    suspect_profiles = "\n".join([
        f"""
### {s.name}
Role: {s.role}
Personality: {s.personality}
Alibi: "{s.alibi}"
Secret: {s.secret}
Will share if asked: {s.clue_they_know}
Guilty: {s.isGuilty}{f'''
Murder details: Used {mystery.weapon} because {mystery.motive}''' if s.isGuilty else ''}"""
        for s in mystery.suspects
    ])
    
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
1. When player wants to TALK to a suspect → Use "Interrogate Suspect" tool. IMPORTANT: Pass the suspect's FULL PROFILE from above.
2. When player wants to SEARCH a location → Describe findings, reveal clues if correct location
3. When player makes ACCUSATION → Check if correct with evidence
4. Track game state (clues found, suspects talked to)

## GAME RULES
- 3 wrong accusations = lose
- Win = name murderer + provide evidence  
- Never reveal murderer until correct accusation

## SECRET (NEVER REVEAL)
Murderer: {mystery.murderer}
Weapon: {mystery.weapon}
Motive: {mystery.motive}

Welcome the player and set the scene!"""
    
    return system_prompt

