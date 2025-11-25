"""Tools for the game master agent."""
from typing import Annotated
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import os


@tool
def interrogate_suspect(
    suspect_name: Annotated[str, "The name of the suspect to interrogate"],
    suspect_profile: Annotated[str, "Full profile including role, personality, alibi, secret, clue_they_know, and isGuilty status"],
    player_question: Annotated[str, "The player's question or statement to the suspect"]
) -> str:
    """Interrogate Suspect - Use when player wants to talk to a suspect. 
    
    You MUST include in your request: 
    1) Suspect's name, 
    2) Their FULL profile (role, personality, alibi, secret, what they know, isGuilty status), 
    3) Player's question. 
    The tool needs all this info to roleplay correctly."""
    
    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0.8,
        api_key=os.getenv("OPENAI_API_KEY")
    )
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are roleplaying as a murder mystery suspect. Stay completely in character.

RULES:
- Speak in first person AS this character
- Use their personality in how you speak
- Protect your secret unless pressed very hard
- If GUILTY: be evasive, deflect, give alibis, NEVER confess unless overwhelming evidence
- If INNOCENT: you don't know who did it, but share what you know if asked well
- NEVER break character or mention AI
- Keep responses conversational, not too long

Suspect Profile:
{suspect_profile}"""),
        ("human", "Player says: {player_question}")
    ])
    
    chain = prompt | llm
    
    response = chain.invoke({
        "suspect_profile": suspect_profile,
        "player_question": player_question
    })
    
    return response.content

