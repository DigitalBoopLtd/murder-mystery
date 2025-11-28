"""Tools for the game master agent."""

import logging
import os
import re
import tempfile
from typing import Annotated, Optional
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from services.tts_service import text_to_speech

logger = logging.getLogger(__name__)

# Directory for storing generated audio files
AUDIO_DIR = os.path.join(tempfile.gettempdir(), "murder_mystery_audio")
os.makedirs(AUDIO_DIR, exist_ok=True)

# Global dict to store alignment data for tool-generated audio
# Key: audio_path, Value: alignment_data list
_audio_alignment_cache = {}


@tool
def interrogate_suspect(
    suspect_name: Annotated[str, "The name of the suspect to interrogate"],
    suspect_profile: Annotated[
        str,
        "Full profile: role, personality, alibi, secret, clue_they_know, isGuilty",
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

    logger.info("\n%s", "=" * 60)
    logger.info("INTERROGATE_SUSPECT TOOL CALLED")
    logger.info("Suspect: %s", suspect_name)
    logger.info("Player question: %s", player_question)
    logger.info("Profile length: %d chars", len(suspect_profile))
    logger.info("Voice ID: %s", voice_id)
    logger.info("%s\n", "=" * 60)

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
- The player might speak in any language, but you MUST ALWAYS answer in natural, fluent ENGLISH only

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
    """Enhance text with capitalization for emphasis for more engaging speech.

    Uses capitalization and punctuation cues instead of emotional tags
    (which would be spoken). Voice settings handle emotional delivery.
    """
    enhanced = text

    # Don't add emotional tags - they get spoken! Instead, use:
    # - Capitalization for emphasis
    # - Voice settings for emotional delivery
    # - Natural text cues (exclamation marks, question marks)

    # Capitalize key dramatic words for emphasis
    dramatic_words = [
        "suddenly",
        "immediately",
        "finally",
        "quickly",
        "carefully",
        "silently",
        "slowly",
        "quietly",
    ]
    for word in dramatic_words:
        pattern = r"\b" + re.escape(word) + r"\b"
        enhanced = re.sub(pattern, word.upper(), enhanced, flags=re.IGNORECASE)

    return enhanced


def generate_suspect_audio(
    text: str, voice_id: str, suspect_name: str
) -> Optional[str]:
    """Generate audio for suspect response with alignment data.

    Args:
        text: The text to convert to speech
        voice_id: ElevenLabs voice ID
        suspect_name: Name of the suspect (for logging)

    Returns:
        Path to generated audio file, or None on error
        Also stores alignment data in _audio_alignment_cache
    """
    try:
        # Enhance text with capitalization for emphasis
        enhanced_text = enhance_text_for_speech(text)

        # Use services.tts_service to get audio with alignment data
        audio_path, alignment_data = text_to_speech(
            enhanced_text, voice_id=voice_id, speaker_name=suspect_name
        )

        if audio_path:
            # Store alignment data in cache for retrieval later
            _audio_alignment_cache[audio_path] = alignment_data
            if alignment_data:
                logger.info(
                    "Generated audio with %d word timestamps for %s: %s",
                    len(alignment_data),
                    suspect_name,
                    audio_path,
                )
            else:
                logger.info(
                    "Generated audio (no alignment data) for %s: %s",
                    suspect_name,
                    audio_path,
                )
            return audio_path
        else:
            logger.warning("Failed to generate audio for %s", suspect_name)
            return None

    except Exception as e:
        logger.error("Error generating audio: %s", e)
        return None


def get_audio_alignment_data(audio_path: str) -> Optional[list]:
    """Get alignment data for a tool-generated audio file.

    Args:
        audio_path: Path to audio file

    Returns:
        Alignment data list or None if not found
    """
    return _audio_alignment_cache.get(audio_path)
