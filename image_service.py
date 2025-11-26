"""Image generation service for character portraits and scene art.

Uses HuggingFace Inference API with fal-ai provider for fast generation.
Styled to look like 90s point-and-click adventure games (Monkey Island, Gabriel Knight, etc.)
"""

import os
import re
import logging
import hashlib
import tempfile
from typing import Optional, Dict
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from huggingface_hub import InferenceClient

logger = logging.getLogger(__name__)

# Directory for caching generated images
IMAGE_CACHE_DIR = os.path.join(tempfile.gettempdir(), "murder_mystery_images")
os.makedirs(IMAGE_CACHE_DIR, exist_ok=True)

# Art style prompt suffix for consistent 90s adventure game aesthetic
ART_STYLE = """
Style: 1990s point-and-click adventure game art, like Monkey Island or Gabriel Knight.
Painterly pixel art aesthetic, slightly exaggerated features, rich colors, 
dramatic lighting, hand-painted look, vintage video game portrait.
Square portrait composition, character facing slightly to the side.
No text, no words, no letters, no writing, no labels, no captions.
"""

SCENE_ART_STYLE = """
Style: 1990s point-and-click adventure game background art, like Monkey Island or Day of the Tentacle.
Painterly style, rich atmospheric colors, dramatic lighting, hand-painted look,
vintage video game scene, detailed environment, moody and mysterious.
Wide landscape composition suitable for a game background.
No text, no words, no letters, no writing, no labels, no captions, no signage.
"""


@dataclass
class GeneratedImage:
    """Container for generated image data."""

    image_path: str
    prompt: str
    cache_key: str


class ImageService:
    """Service for generating character portraits and scene art."""

    def __init__(self, hf_token: Optional[str] = None):
        """Initialize the image service.

        Args:
            hf_token: HuggingFace API token. Falls back to HF_TOKEN env var.
        """
        self.hf_token = hf_token or os.getenv("HF_TOKEN")
        self._client = None

    @property
    def is_available(self) -> bool:
        """Check if image generation is available."""
        return bool(self.hf_token)

    @property
    def client(self):
        """Lazy-load the HuggingFace client."""
        if self._client is None and self.is_available:
            try:

                self._client = InferenceClient(
                    provider="fal-ai",
                    api_key=self.hf_token,
                )
                logger.info("HuggingFace InferenceClient initialized")
            except ImportError:
                logger.error("huggingface_hub not installed")
                return None
            except Exception as e:
                logger.error(f"Failed to initialize HuggingFace client: {e}")
                return None
        return self._client

    def _get_cache_key(self, prompt: str) -> str:
        """Generate a cache key for a prompt."""
        return hashlib.md5(prompt.encode()).hexdigest()[:12]

    def _get_cached_image(self, cache_key: str) -> Optional[str]:
        """Check if image exists in cache."""
        cache_path = os.path.join(IMAGE_CACHE_DIR, f"{cache_key}.png")
        if os.path.exists(cache_path):
            logger.info(f"Found cached image: {cache_key}")
            return cache_path
        return None

    def _save_to_cache(self, image, cache_key: str) -> str:
        """Save PIL image to cache and return path."""
        cache_path = os.path.join(IMAGE_CACHE_DIR, f"{cache_key}.png")
        image.save(cache_path, "PNG")
        logger.info(f"Saved image to cache: {cache_path}")
        return cache_path

    def generate_character_portrait(
        self,
        name: str,
        role: str,
        personality: str,
        gender: Optional[str] = None,
        setting_context: Optional[str] = None,
    ) -> Optional[str]:
        """Generate a portrait for a character.

        Args:
            name: Character name
            role: Their role (e.g., "butler", "heiress")
            personality: Personality traits
            gender: Male/female if known
            setting_context: Optional setting for costume hints

        Returns:
            Path to generated image, or None on error
        """
        if not self.client:
            logger.warning("Image client not available")
            return None

        # Build character description prompt
        gender_str = gender if gender else "person"

        prompt = f"""Portrait of {name}, a {gender_str} who is a {role}.
Personality: {personality}.
{f'Setting: {setting_context}.' if setting_context else ''}
{ART_STYLE}
No text, no words, no letters, no writing, no labels, no captions, no name tags.
"""

        cache_key = self._get_cache_key(prompt)

        # Check cache first
        cached = self._get_cached_image(cache_key)
        if cached:
            return cached

        try:
            logger.info(f"Generating portrait for {name}...")
            image = self.client.text_to_image(
                prompt,
                model="black-forest-labs/FLUX.1-schnell",
            )

            path = self._save_to_cache(image, cache_key)
            logger.info(f"Generated portrait for {name}: {path}")
            return path

        except Exception as e:
            logger.error(f"Error generating portrait for {name}: {e}")
            return None

    def generate_scene(
        self, location_name: str, setting_description: str, mood: str = "mysterious", context: Optional[str] = None
    ) -> Optional[str]:
        """Generate a scene/background image for a location.

        Args:
            location_name: Name of the location
            setting_description: Description of the overall setting
            mood: Mood of the scene (mysterious, tense, etc.)
            context: Optional context from the game response describing what was found/seen

        Returns:
            Path to generated image, or None on error
        """
        if not self.client:
            logger.warning("Image client not available")
            return None

        # Build prompt with context if provided
        prompt_parts = [
            f"{location_name}.",
            f"Part of: {setting_description}.",
            f"Mood: {mood}, atmospheric."
        ]
        
        if context:
            # Add context from the game response (what was found, what it looks like, etc.)
            # Clean context - remove markdown and emotional tags
            clean_context = context.replace("**", "").replace("*", "")
            clean_context = re.sub(r"\[.*?\]", "", clean_context)  # Remove [excited], etc.
            # Take first 200 chars to keep prompt manageable
            clean_context = clean_context[:200].strip()
            if clean_context:
                prompt_parts.append(f"Context: {clean_context}")
        
        prompt_parts.append(SCENE_ART_STYLE)
        prompt_parts.append("No text, no words, no letters, no writing, no labels, no captions, no signage, no signs.")
        
        prompt = "\n".join(prompt_parts)

        cache_key = self._get_cache_key(prompt)

        # Check cache first
        cached = self._get_cached_image(cache_key)
        if cached:
            logger.info(f"Using cached scene for {location_name}")
            return cached

        try:
            logger.info(f"Generating scene for {location_name} with context...")
            image = self.client.text_to_image(
                prompt,
                model="black-forest-labs/FLUX.1-schnell",
            )

            path = self._save_to_cache(image, cache_key)
            logger.info(f"Generated scene for {location_name}: {path}")
            return path

        except Exception as e:
            logger.error(f"Error generating scene for {location_name}: {e}")
            return None

    def generate_title_card(self, title: str, setting: str) -> Optional[str]:
        """Generate a title card for the mystery.

        Args:
            title: Mystery title
            setting: Setting description

        Returns:
            Path to generated image, or None on error
        """
        if not self.client:
            logger.warning("Image client not available")
            return None

        prompt = f"""Title card for a murder mystery called "{title}".
{setting}
{SCENE_ART_STYLE}
Ominous, foreboding, sets the mood for a murder mystery.
No text, no words, no letters, no writing, no labels, no captions, no title text, no signage.
Atmospheric scene only, no text overlay.
"""

        cache_key = self._get_cache_key(prompt)

        cached = self._get_cached_image(cache_key)
        if cached:
            return cached

        try:
            logger.info(f"Generating title card...")
            image = self.client.text_to_image(
                prompt,
                model="black-forest-labs/FLUX.1-schnell",
            )

            path = self._save_to_cache(image, cache_key)
            logger.info(f"Generated title card: {path}")
            return path

        except Exception as e:
            logger.error(f"Error generating title card: {e}")
            return None


# Global image service instance
_image_service: Optional[ImageService] = None


def get_image_service() -> ImageService:
    """Get or create the global image service."""
    global _image_service
    if _image_service is None:
        _image_service = ImageService()
    return _image_service


def generate_all_mystery_images(mystery) -> Dict[str, str]:
    """Generate all images for a mystery (portraits + scenes) in parallel.

    Args:
        mystery: Mystery object with suspects and setting

    Returns:
        Dict mapping names/locations to image paths
    """
    service = get_image_service()
    images = {}

    if not service.is_available:
        logger.info("Image generation not available, skipping")
        return images

    # Prepare all image generation tasks
    tasks = []
    
    # Add suspect portrait tasks
    for suspect in mystery.suspects:
        tasks.append((
            suspect.name,
            "portrait",
            lambda s=suspect: service.generate_character_portrait(
                name=s.name,
                role=s.role,
                personality=s.personality,
                gender=getattr(s, "gender", None),
                setting_context=mystery.setting,
            )
        ))
    
    # Add title card task
    tasks.append((
        "_title",
        "title",
        lambda: service.generate_title_card(
            title=f"The Murder of {mystery.victim.name}", 
            setting=mystery.setting
        )
    ))
    
    # NOTE: Scene images are now generated on-demand when locations are searched
    # This allows us to use the game response as context for better scene generation

    # Generate all images in parallel
    logger.info(f"Generating {len(tasks)} images in parallel...")
    with ThreadPoolExecutor(max_workers=min(len(tasks), 10)) as executor:
        # Submit all tasks
        future_to_key = {
            executor.submit(task[2]): (task[0], task[1]) 
            for task in tasks
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_key):
            key, img_type = future_to_key[future]
            try:
                path = future.result()
                if path:
                    images[key] = path
                    logger.info(f"✓ Generated {img_type}: {key}")
                    
                    # Store portrait path on suspect object if it's a portrait
                    if img_type == "portrait":
                        for suspect in mystery.suspects:
                            if suspect.name == key:
                                suspect.portrait_path = path
                                break
            except Exception as e:
                logger.error(f"Error generating {img_type} {key}: {e}")

    logger.info(f"Completed generating {len(images)} images")
    return images
