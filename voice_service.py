"""Voice service for ElevenLabs TTS integration."""

import os
import logging
import random
import re
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass
import requests

logger = logging.getLogger(__name__)

ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1"


@dataclass
class Voice:
    """Represents an ElevenLabs voice."""

    voice_id: str
    name: str
    gender: Optional[str] = None
    age: Optional[str] = None
    accent: Optional[str] = None
    description: Optional[str] = None
    use_case: Optional[str] = None

    def __repr__(self):
        return f"Voice({self.name}, {self.gender}, {self.age}, {self.accent})"


class VoiceService:
    """Service for managing ElevenLabs voices and TTS generation."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
        self._voices_cache: Optional[List[Voice]] = None

    @property
    def is_available(self) -> bool:
        """Check if ElevenLabs API is available."""
        return bool(self.api_key)

    def _get_headers(self) -> dict:
        """Get API headers."""
        return {"xi-api-key": self.api_key, "Content-Type": "application/json"}

    def get_available_voices(self, force_refresh: bool = False) -> List[Voice]:
        """Fetch all available voices from ElevenLabs.

        Returns:
            List of Voice objects with metadata
        """
        if self._voices_cache and not force_refresh:
            return self._voices_cache

        if not self.is_available:
            logger.warning("ElevenLabs API key not set")
            return []

        try:
            response = requests.get(
                f"{ELEVENLABS_API_URL}/voices", headers=self._get_headers(), timeout=10
            )
            response.raise_for_status()
            data = response.json()

            voices = []
            for voice_data in data.get("voices", []):
                labels = voice_data.get("labels", {})
                voices.append(
                    Voice(
                        voice_id=voice_data["voice_id"],
                        name=voice_data["name"],
                        gender=labels.get("gender"),
                        age=labels.get("age"),
                        accent=labels.get("accent"),
                        description=labels.get("description"),
                        use_case=labels.get("use_case"),
                    )
                )

            self._voices_cache = voices
            logger.info(f"Fetched {len(voices)} voices from ElevenLabs")
            return voices

        except requests.RequestException as e:
            logger.error(f"Error fetching voices: {e}")
            return []

    def extract_suspect_characteristics(self, suspect_profile: dict) -> dict:
        """Extract voice-relevant characteristics from a suspect profile.

        Args:
            suspect_profile: Dict with name, role, personality, gender, etc.

        Returns:
            Dict with extracted characteristics for voice matching
        """
        name = suspect_profile.get("name", "").lower()
        role = suspect_profile.get("role", "").lower()
        personality = suspect_profile.get("personality", "").lower()

        # Combine all text for analysis
        full_text = f"{name} {role} {personality}"

        characteristics = {"gender": None, "age": None, "accent": None, "tone": None}

        # Gender detection - use explicit gender if provided, otherwise infer
        explicit_gender = suspect_profile.get("gender")
        if explicit_gender:
            # Use explicit gender from suspect model
            characteristics["gender"] = explicit_gender.lower()
            logger.info(f"Using explicit gender '{characteristics['gender']}' for {suspect_profile.get('name')}")
        else:
            # Fall back to inference if not provided
            # Gender detection - first check name for common patterns
            # Common female name endings
            female_name_endings = ["a", "ia", "ella", "ella", "ette", "ine", "ina", "ana", "ena", "ina", "elle"]
            # Common female first names
            common_female_names = ["elena", "sarah", "emily", "jessica", "amanda", "lisa", "maria", "anna", "sophia", 
                                  "olivia", "isabella", "charlotte", "victoria", "diana", "helen", "katherine", "elizabeth",
                                  "jennifer", "michelle", "nicole", "stephanie", "rebecca", "rachel", "lauren", "ashley"]
            
            first_name = name.split()[0] if name else ""
            name_is_female = False
            if first_name:
                # Check if first name ends with common female endings
                if any(first_name.lower().endswith(ending) for ending in female_name_endings):
                    name_is_female = True
                # Check if it's a known female name
                elif first_name.lower() in common_female_names:
                    name_is_female = True
            
            # Gender detection from text
            male_indicators = [
                "he",
                "him",
                "his",
                "mr.",
                "sir",
                "gentleman",
                "man",
                "male",
                "father",
                "brother",
                "husband",
                "uncle",
                "nephew",
                "son",
                "butler",
                "valet",
                "businessman",
                "chairman",
                "lord",
                "duke",
                "baron",
                "earl",
                "count",
                "prince",
                "king",
                "waiter",
                "barman",
            ]
            female_indicators = [
                "she",
                "her",
                "hers",
                "mrs.",
                "ms.",
                "miss",
                "madam",
                "woman",
                "female",
                "mother",
                "sister",
                "wife",
                "aunt",
                "niece",
                "daughter",
                "maid",
                "housekeeper",
                "businesswoman",
                "chairwoman",
                "lady",
                "duchess",
                "baroness",
                "countess",
                "princess",
                "queen",
                "waitress",
            ]

            male_score = sum(1 for word in male_indicators if word in full_text)
            female_score = sum(1 for word in female_indicators if word in full_text)
            
            # Boost female score if name suggests female
            if name_is_female:
                female_score += 3

            if male_score > female_score:
                characteristics["gender"] = "male"
            elif female_score > male_score:
                characteristics["gender"] = "female"

        # Age detection
        young_indicators = [
            "young",
            "youth",
            "youthful",
            "teenage",
            "twenties",
            "early",
            "junior",
            "apprentice",
            "intern",
            "student",
            "fresh",
            "naive",
        ]
        old_indicators = [
            "old",
            "elderly",
            "aged",
            "senior",
            "retired",
            "veteran",
            "grandfather",
            "grandmother",
            "elder",
            "ancient",
            "wise",
            "experienced",
            "seasoned",
            "grey",
            "gray",
            "wrinkled",
        ]
        middle_indicators = [
            "middle-aged",
            "middle aged",
            "mature",
            "established",
            "thirties",
            "forties",
            "fifties",
        ]

        if any(word in full_text for word in old_indicators):
            characteristics["age"] = "old"
        elif any(word in full_text for word in young_indicators):
            characteristics["age"] = "young"
        elif any(word in full_text for word in middle_indicators):
            characteristics["age"] = "middle_aged"

        # Accent detection
        accent_map = {
            "british": [
                "british",
                "english",
                "london",
                "oxford",
                "cambridge",
                "butler",
                "manor",
                "estate",
                "lord",
                "lady",
                "duchess",
                "earl",
            ],
            "american": [
                "american",
                "new york",
                "texas",
                "california",
                "usa",
                "states",
            ],
            "australian": ["australian", "aussie", "sydney", "melbourne"],
            "irish": ["irish", "ireland", "dublin"],
            "scottish": ["scottish", "scotland", "glasgow", "edinburgh"],
            "french": ["french", "paris", "france", "monsieur", "madame"],
            "german": ["german", "germany", "berlin", "munich"],
            "italian": ["italian", "italy", "rome", "milan", "sicily"],
            "spanish": ["spanish", "spain", "madrid", "barcelona"],
            "russian": ["russian", "russia", "moscow", "soviet"],
            "indian": ["indian", "india", "mumbai", "delhi"],
        }

        for accent, keywords in accent_map.items():
            if any(keyword in full_text for keyword in keywords):
                characteristics["accent"] = accent
                break

        # Tone/personality for voice style
        authoritative_indicators = [
            "stern",
            "strict",
            "commanding",
            "authoritative",
            "formal",
            "serious",
            "cold",
            "harsh",
            "intimidating",
            "powerful",
        ]
        warm_indicators = [
            "warm",
            "friendly",
            "kind",
            "gentle",
            "soft",
            "caring",
            "motherly",
            "fatherly",
            "nurturing",
            "compassionate",
        ]
        dramatic_indicators = [
            "dramatic",
            "theatrical",
            "expressive",
            "passionate",
            "emotional",
            "intense",
            "fiery",
            "volatile",
        ]
        mysterious_indicators = [
            "mysterious",
            "enigmatic",
            "secretive",
            "quiet",
            "reserved",
            "cryptic",
            "shadowy",
            "eerie",
            "unsettling",
        ]

        if any(word in full_text for word in authoritative_indicators):
            characteristics["tone"] = "authoritative"
        elif any(word in full_text for word in warm_indicators):
            characteristics["tone"] = "warm"
        elif any(word in full_text for word in dramatic_indicators):
            characteristics["tone"] = "dramatic"
        elif any(word in full_text for word in mysterious_indicators):
            characteristics["tone"] = "mysterious"

        logger.info(
            f"Extracted characteristics for {suspect_profile.get('name')}: {characteristics}"
        )
        return characteristics

    def score_voice_match(self, voice: Voice, characteristics: dict) -> int:
        """Score how well a voice matches the desired characteristics.

        Args:
            voice: Voice object to score
            characteristics: Desired characteristics dict

        Returns:
            Integer score (higher is better match)
        """
        score = 0

        # Gender match (most important)
        if characteristics.get("gender"):
            if voice.gender and voice.gender.lower() == characteristics["gender"]:
                score += 10
            elif voice.gender and voice.gender.lower() != characteristics["gender"]:
                score -= 20  # Strong penalty for wrong gender

        # Age match
        if characteristics.get("age") and voice.age:
            voice_age = voice.age.lower()
            desired_age = characteristics["age"]

            if desired_age in voice_age or voice_age in desired_age:
                score += 5
            # Handle variations
            elif desired_age == "old" and any(
                x in voice_age for x in ["old", "senior", "elderly"]
            ):
                score += 5
            elif desired_age == "young" and any(
                x in voice_age for x in ["young", "youth"]
            ):
                score += 5
            elif desired_age == "middle_aged" and any(
                x in voice_age for x in ["middle", "mature"]
            ):
                score += 5

        # Accent match
        if characteristics.get("accent") and voice.accent:
            voice_accent = voice.accent.lower()
            desired_accent = characteristics["accent"]

            if desired_accent in voice_accent or voice_accent in desired_accent:
                score += 7
            # British/English equivalence
            elif desired_accent == "british" and "english" in voice_accent:
                score += 7
            elif desired_accent == "english" and "british" in voice_accent:
                score += 7

        # Use case bonus (prefer "characters" or "narrative" for game)
        if voice.use_case:
            use_case = voice.use_case.lower()
            if "character" in use_case or "narrative" in use_case:
                score += 2
            elif "audiobook" in use_case:
                score += 1

        return score

    def match_voice_to_suspect(
        self,
        suspect_profile: dict,
        available_voices: List[Voice],
        used_voice_ids: Optional[List[str]] = None,
    ) -> Optional[Voice]:
        """Match a suspect to the best available voice.

        Args:
            suspect_profile: Dict with suspect details
            available_voices: List of available voices
            used_voice_ids: List of already-used voice IDs to avoid

        Returns:
            Best matching Voice or None
        """
        used_voice_ids = used_voice_ids or []

        # Filter out already used voices
        candidates = [v for v in available_voices if v.voice_id not in used_voice_ids]

        if not candidates:
            logger.warning("No available voices for matching")
            return None

        # Extract characteristics
        characteristics = self.extract_suspect_characteristics(suspect_profile)

        # Score each voice
        scored_voices = [
            (voice, self.score_voice_match(voice, characteristics))
            for voice in candidates
        ]

        # Sort by score (highest first)
        scored_voices.sort(key=lambda x: x[1], reverse=True)

        # Log top matches
        logger.info(f"Top voice matches for {suspect_profile.get('name')}:")
        for voice, score in scored_voices[:3]:
            logger.info(f"  {voice.name} (score: {score})")

        # Return best match
        best_voice, best_score = scored_voices[0]

        # If score is very negative, consider random selection
        if best_score < -10:
            logger.warning(f"Best match score is {best_score}, using random selection")
            return random.choice(candidates)

        return best_voice

    def assign_voices_to_suspects(self, suspects: List[dict]) -> Dict[str, str]:
        """Assign voices to all suspects.

        Args:
            suspects: List of suspect profile dicts

        Returns:
            Dict mapping suspect name to voice_id
        """
        if not self.is_available:
            logger.warning("ElevenLabs not available, skipping voice assignment")
            return {}

        voices = self.get_available_voices()
        if not voices:
            logger.warning("No voices available")
            return {}

        assignments = {}
        used_voice_ids = []

        for suspect in suspects:
            voice = self.match_voice_to_suspect(suspect, voices, used_voice_ids)
            if voice:
                assignments[suspect["name"]] = voice.voice_id
                used_voice_ids.append(voice.voice_id)
                logger.info(
                    f"Assigned voice '{voice.name}' to suspect '{suspect['name']}'"
                )
            else:
                logger.warning(f"Could not assign voice to {suspect['name']}")

        return assignments

    def generate_speech(
        self,
        text: str,
        voice_id: str,
        model_id: str = "eleven_multilingual_v2",
        output_format: str = "mp3_44100_128",
    ) -> Optional[bytes]:
        """Generate speech audio from text.

        Args:
            text: Text to convert to speech
            voice_id: ElevenLabs voice ID
            model_id: TTS model to use
            output_format: Audio output format

        Returns:
            Audio bytes or None on error
        """
        if not self.is_available:
            logger.warning("ElevenLabs API key not set")
            return None

        try:
            response = requests.post(
                f"{ELEVENLABS_API_URL}/text-to-speech/{voice_id}",
                headers=self._get_headers(),
                json={
                    "text": text,
                    "model_id": model_id,
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.75,
                        "style": 0.5,
                        "use_speaker_boost": True,
                    },
                },
                timeout=30,
            )
            response.raise_for_status()

            logger.info(
                f"Generated speech for {len(text)} chars using voice {voice_id}"
            )
            return response.content

        except requests.RequestException as e:
            logger.error(f"Error generating speech: {e}")
            return None

    def generate_speech_to_file(
        self, text: str, voice_id: str, output_path: str, **kwargs
    ) -> Optional[str]:
        """Generate speech and save to file.

        Args:
            text: Text to convert
            voice_id: Voice ID to use
            output_path: Where to save the audio
            **kwargs: Additional args for generate_speech

        Returns:
            Output path on success, None on error
        """
        audio_data = self.generate_speech(text, voice_id, **kwargs)
        if audio_data:
            with open(output_path, "wb") as f:
                f.write(audio_data)
            logger.info(f"Saved audio to {output_path}")
            return output_path
        return None


# Global voice service instance
_voice_service: Optional[VoiceService] = None


def get_voice_service() -> VoiceService:
    """Get or create the global voice service."""
    global _voice_service
    if _voice_service is None:
        _voice_service = VoiceService()
    return _voice_service
