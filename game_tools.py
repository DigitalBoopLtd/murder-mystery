"""Tools for the game master agent."""

import logging
import os
import re
import tempfile
import uuid
from typing import Annotated, Optional
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from voice_service import get_voice_service
logger = logging.getLogger(__name__)

# Directory for storing generated audio files
AUDIO_DIR = os.path.join(tempfile.gettempdir(), "murder_mystery_audio")
os.makedirs(AUDIO_DIR, exist_ok=True)


@tool
def interrogate_suspect(
    suspect_name: Annotated[str, "The name of the suspect to interrogate"],
    suspect_profile: Annotated[
        str,
        "Full profile including role, personality, alibi, secret, clue_they_know, and isGuilty status",
    ],
    player_question: Annotated[
        str, "The player's question or statement to the suspect"
    ],
    voice_id: Annotated[Optional[str], "Optional ElevenLabs voice ID for TTS"] = None,
) -> str:
    """Interrogate Suspect - Use when player wants to talk to a suspect.

    You MUST include in your request:
    1) Suspect's name,
    2) Their FULL profile (role, personality, alibi, secret, what they know, isGuilty status),
    3) Player's question.
    4) Optionally, their voice_id for audio generation.
    The tool needs all this info to roleplay correctly."""

    logger.info(f"\n{'='*60}")
    logger.info(f"INTERROGATE_SUSPECT TOOL CALLED")
    logger.info(f"Suspect: {suspect_name}")
    logger.info(f"Player question: {player_question}")
    logger.info(f"Profile length: {len(suspect_profile)} chars")
    logger.info(f"Voice ID: {voice_id}")
    logger.info(f"{'='*60}\n")

    llm = ChatOpenAI(
        model="gpt-4o", temperature=0.8, api_key=os.getenv("OPENAI_API_KEY")
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are roleplaying as a murder mystery suspect. Stay completely in character.

RULES:
- Speak in first person AS this character
- Use their personality in how you speak
- Protect your secret unless pressed very hard
- If GUILTY: be evasive, deflect, give alibis, NEVER confess unless overwhelming evidence
- If INNOCENT: you don't know who did it, but share what you know if asked well
- NEVER break character or mention AI
- Keep responses conversational, not too long (2-4 sentences ideal for voice)

Suspect Profile:
{suspect_profile}""",
            ),
            ("human", "Player says: {player_question}"),
        ]
    )

    chain = prompt | llm

    response = chain.invoke(
        {"suspect_profile": suspect_profile, "player_question": player_question}
    )

    text_response = response.content

    # Generate audio if voice_id is provided
    audio_path = None
    if voice_id:
        audio_path = generate_suspect_audio(text_response, voice_id, suspect_name)

    # Return response with audio path marker if audio was generated
    if audio_path:
        # Use a special marker that we can parse in app.py
        return f"[AUDIO:{audio_path}]{text_response}"

    return text_response


def enhance_text_for_speech(text: str) -> str:
    """Enhance text with emotional tags and emphasis for more engaging speech."""
    enhanced = text
    
    # Add emotional context based on content
    text_lower = text.lower()
    
    # Detect excitement/exclamation
    if any(word in text_lower for word in ['amazing', 'incredible', 'wow', 'fantastic', 'unbelievable']):
        enhanced = f"[excited] {enhanced}"
    elif '?' in text:
        enhanced = f"[curiously] {enhanced}"
    elif any(word in text_lower for word in ['suspicious', 'strange', 'odd', 'mysterious']):
        enhanced = f"[mysteriously] {enhanced}"
    elif any(word in text_lower for word in ['important', 'crucial', 'key', 'vital']):
        enhanced = f"[emphatically] {enhanced}"
    
    # Capitalize key dramatic words for emphasis
    dramatic_words = ['suddenly', 'immediately', 'finally', 'quickly', 'carefully', 'silently']
    for word in dramatic_words:
        pattern = r'\b' + re.escape(word) + r'\b'
        enhanced = re.sub(pattern, word.upper(), enhanced, flags=re.IGNORECASE)
    
    return enhanced


def generate_suspect_audio(
    text: str, voice_id: str, suspect_name: str
) -> Optional[str]:
    """Generate audio for suspect response.

    Args:
        text: The text to convert to speech
        voice_id: ElevenLabs voice ID
        suspect_name: Name of the suspect (for logging)

    Returns:
        Path to generated audio file, or None on error
    """
    try:

        voice_service = get_voice_service()

        if not voice_service.is_available:
            logger.info("ElevenLabs not available, skipping audio generation")
            return None

        # Generate unique filename
        filename = f"{suspect_name.replace(' ', '_')}_{uuid.uuid4().hex[:8]}.mp3"
        output_path = os.path.join(AUDIO_DIR, filename)

        # Enhance text with emotional tags and emphasis for more engaging speech
        enhanced_text = enhance_text_for_speech(text)
        
        # Generate audio with enhanced text
        result = voice_service.generate_speech_to_file(enhanced_text, voice_id, output_path)

        if result:
            logger.info(f"Generated audio for {suspect_name}: {output_path}")
            return output_path
        else:
            logger.warning(f"Failed to generate audio for {suspect_name}")
            return None

    except Exception as e:
        logger.error(f"Error generating audio: {e}")
        return None
