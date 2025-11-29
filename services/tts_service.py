"""Text-to-speech service using ElevenLabs with optional timestamps.

Strategy:
1. Try convert_with_timestamps for precise timing (non-streaming)
2. Fallback to basic convert() which always works
"""

import os
import re
import base64
import tempfile
import logging
import uuid
from typing import Optional, Tuple, List, Dict

logger = logging.getLogger(__name__)

# These will be set by app.py
elevenlabs_client = None
openai_client = None
GAME_MASTER_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"


def init_tts_service(elevenlabs, openai, game_master_voice_id: str):
    """Initialize TTS service with clients."""
    global elevenlabs_client, openai_client, GAME_MASTER_VOICE_ID
    elevenlabs_client = elevenlabs
    openai_client = openai
    GAME_MASTER_VOICE_ID = game_master_voice_id
    logger.info(f"TTS service initialized. ElevenLabs client: {elevenlabs is not None}")


def transcribe_audio(audio_path: str) -> str:
    """Transcribe audio using OpenAI Whisper."""
    if not openai_client:
        return ""

    try:
        with open(audio_path, "rb") as audio_file:
            transcript = openai_client.audio.transcriptions.create(
                model="whisper-1", file=audio_file
            )
        return transcript.text
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        return ""


def enhance_text_for_speech(text: str) -> str:
    """Enhance text with capitalization for emphasis."""
    enhanced = text
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


def characters_to_words(
    characters: List[str], start_times: List[float], end_times: List[float]
) -> List[Dict]:
    """Convert character-level timestamps to word-level timestamps."""
    if (
        not characters
        or len(characters) != len(start_times)
        or len(characters) != len(end_times)
    ):
        return []

    words = []
    current_word = ""
    word_start = None
    word_end = None

    for i, char in enumerate(characters):
        if char in (" ", "\n", "\t"):
            if current_word:
                words.append(
                    {"word": current_word, "start": word_start, "end": word_end}
                )
            current_word = ""
            word_start = None
            word_end = None
        else:
            if word_start is None:
                word_start = start_times[i]
            current_word += char
            word_end = end_times[i]

    if current_word and word_start is not None:
        words.append({"word": current_word, "start": word_start, "end": word_end})

    return words


def text_to_speech_basic(text: str, voice_id: str = None) -> Optional[str]:
    """Basic TTS using convert() - ALWAYS works.

    This is the reliable fallback that just generates audio without timestamps.
    """
    if not elevenlabs_client:
        logger.error("ElevenLabs client not initialized!")
        return None

    if not text or not text.strip():
        logger.warning("Empty text provided to TTS")
        return None

    voice_id = voice_id or GAME_MASTER_VOICE_ID
    enhanced_text = enhance_text_for_speech(text)

    # Create persistent audio directory
    audio_dir = os.path.join(tempfile.gettempdir(), "murder_mystery_audio")
    os.makedirs(audio_dir, exist_ok=True)

    try:
        logger.info(
            f"[TTS] Generating audio with convert() for {len(enhanced_text)} chars"
        )

        # This is the simplest, most reliable method
        audio_generator = elevenlabs_client.text_to_speech.convert(
            voice_id=voice_id,
            text=enhanced_text,
            model_id="eleven_flash_v2_5",
            output_format="mp3_44100_128",
        )

        # Collect all audio chunks
        audio_chunks = []
        for chunk in audio_generator:
            if chunk:
                audio_chunks.append(chunk)

        if not audio_chunks:
            logger.error("[TTS] No audio chunks received from convert()")
            return None

        audio_bytes = b"".join(audio_chunks)

        if len(audio_bytes) < 100:
            logger.error(f"[TTS] Audio too small: {len(audio_bytes)} bytes")
            return None

        # Save to persistent directory with unique name

        audio_path = os.path.join(audio_dir, f"tts_{uuid.uuid4().hex[:8]}.mp3")
        with open(audio_path, "wb") as f:
            f.write(audio_bytes)

        logger.info(
            f"[TTS] SUCCESS: Generated {len(audio_bytes)} bytes -> {audio_path}"
        )
        return audio_path

    except Exception as e:
        logger.error(f"[TTS] convert() failed: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return None


def text_to_speech_with_timestamps(
    text: str, voice_id: str = None
) -> Tuple[Optional[str], Optional[List[Dict]]]:
    """Try to get TTS with timestamps using convert_with_timestamps.

    Returns (audio_path, word_timestamps) or (None, None) on failure.
    """
    if not elevenlabs_client:
        logger.error("ElevenLabs client not initialized!")
        return None, None

    if not text or not text.strip():
        return None, None

    voice_id = voice_id or GAME_MASTER_VOICE_ID
    enhanced_text = enhance_text_for_speech(text)

    # Create persistent audio directory
    audio_dir = os.path.join(tempfile.gettempdir(), "murder_mystery_audio")
    os.makedirs(audio_dir, exist_ok=True)

    try:
        logger.info(
            f"[TTS] Trying convert_with_timestamps for {len(enhanced_text)} chars"
        )

        # Check if method exists
        if not hasattr(elevenlabs_client.text_to_speech, "convert_with_timestamps"):
            logger.warning("[TTS] convert_with_timestamps not available in SDK")
            return None, None

        response = elevenlabs_client.text_to_speech.convert_with_timestamps(
            voice_id=voice_id,
            text=enhanced_text,
            model_id="eleven_flash_v2_5",
            output_format="mp3_44100_128",
        )

        # Log response type for debugging
        logger.info(f"[TTS] Response type: {type(response)}")

        # Extract audio - the SDK returns audio_base_64 attribute (with underscore!)
        audio_data = None

        # Method 1: Check audio_base_64 attribute (this is what ElevenLabs SDK uses)
        if hasattr(response, "audio_base_64") and response.audio_base_64:
            logger.info("[TTS] Found audio_base_64 attribute")
            audio_data = base64.b64decode(response.audio_base_64)

        # Method 2: Check audio_base64 (alternate naming)
        elif hasattr(response, "audio_base64") and response.audio_base64:
            logger.info("[TTS] Found audio_base64 attribute")
            audio_data = base64.b64decode(response.audio_base64)

        # Method 3: Check if it's a dict
        elif isinstance(response, dict):
            if "audio_base_64" in response:
                audio_data = base64.b64decode(response["audio_base_64"])
            elif "audio_base64" in response:
                audio_data = base64.b64decode(response["audio_base64"])

        if not audio_data or len(audio_data) < 100:
            logger.warning(f"[TTS] No valid audio data from convert_with_timestamps")
            return None, None

        # Save audio to persistent directory

        audio_path = os.path.join(audio_dir, f"tts_{uuid.uuid4().hex[:8]}.mp3")
        with open(audio_path, "wb") as f:
            f.write(audio_data)

        logger.info(f"[TTS] Audio saved: {len(audio_data)} bytes -> {audio_path}")

        # Extract alignment data
        word_timestamps = None
        alignment = getattr(response, "alignment", None)

        if alignment:
            chars = getattr(alignment, "characters", [])
            starts = getattr(alignment, "character_start_times_seconds", [])
            ends = getattr(alignment, "character_end_times_seconds", [])

            if chars and starts and ends and len(chars) == len(starts) == len(ends):
                word_timestamps = characters_to_words(
                    list(chars), list(starts), list(ends)
                )
                logger.info(
                    "[TTS] Extracted %d word timestamps from %d chars",
                    len(word_timestamps), len(chars)
                )
            else:
                logger.warning(
                    f"[TTS] Alignment data incomplete: chars={len(chars) if chars else 0}"
                )
        else:
            logger.warning("[TTS] No alignment data in response")

        return audio_path, word_timestamps

    except Exception as e:
        logger.warning(f"[TTS] convert_with_timestamps failed: {e}")
        import traceback

        logger.debug(traceback.format_exc())
        return None, None


def text_to_speech(
    text: str, voice_id: str = None, speaker_name: str = None
) -> Tuple[Optional[str], Optional[List[Dict]]]:
    """Generate speech from text, with timestamps if available.

    Strategy:
    1. Try convert_with_timestamps for precise timing
    2. If that fails, use basic convert() which always works

    Returns:
        Tuple of (audio_file_path, word_timestamps_list or None)
    """
    if not elevenlabs_client:
        logger.error("[TTS] No ElevenLabs client - cannot generate audio!")
        return None, None

    if not text or not text.strip():
        logger.warning("[TTS] Empty text provided")
        return None, None

    voice_id = voice_id or GAME_MASTER_VOICE_ID

    # Try to get timestamps (non-streaming, more reliable than streaming)
    audio_path, timestamps = text_to_speech_with_timestamps(text, voice_id)

    if audio_path:
        logger.info(f"[TTS] SUCCESS with timestamps: {audio_path}")
        return audio_path, timestamps

    # Fallback to basic TTS (no timestamps but should be reliable)
    logger.info("[TTS] Falling back to basic convert()")
    audio_path = text_to_speech_basic(text, voice_id)

    # If that failed AND we were using a non-default voice, retry once with the
    # default Game Master voice to avoid total failure from a bad voice_id.
    if not audio_path and voice_id and voice_id != GAME_MASTER_VOICE_ID:
        logger.warning(
            "[TTS] Basic convert() failed for voice_id '%s', retrying with "
            "default Game Master voice",
            voice_id,
        )
        audio_path = text_to_speech_basic(text, GAME_MASTER_VOICE_ID)

    if audio_path:
        logger.info(f"[TTS] SUCCESS with basic convert: {audio_path}")
    else:
        logger.error("[TTS] FAILED - no audio generated!")

    return audio_path, None
