"""Image generation service for character portraits and scene art.

Uses HuggingFace Inference API with fal-ai provider for fast generation.
Styled to look like 90s point-and-click adventure games (Monkey Island, Day of the Tentacle, Gabriel Knight, etc.)
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
Style: 1990s point-and-click adventure game art, like Monkey Island, Day of the Tentacle or Gabriel Knight.
Painterly pixel art aesthetic, slightly exaggerated features, rich colors, 
dramatic lighting, hand-painted look, vintage video game portrait.
Framing: varied close-up and medium shots — sometimes head-and-shoulders, sometimes waist-up or three-quarter body.
Camera: mix of straight-on, three-quarter, and slight profile angles; character not always perfectly centered, occasional head tilt or lean.
Background: clear sense of location behind the character, simplified but colorful, not just a flat color.
No text, no words, no letters, no writing, no labels, no captions.
"""

SCENE_ART_STYLE = """
Style: 1990s point-and-click adventure game background art, like Monkey Island, Day of the Tentacle, Gabriel Knight, or The Dig.
Painterly digital art with rich saturated colors and dramatic chiaroscuro lighting.
Hand-painted aesthetic with visible brushwork texture, slightly stylized proportions.
Cinematic composition with clear focal point, atmospheric depth and layered elements.
Moody and mysterious atmosphere with environmental storytelling details.
First-person detective POV, surveying the scene or a close-up of a key object.  Do not show the detective in the image.
Include period-appropriate props, furniture, and environmental details that tell a story.
People: follow the scene description carefully — some shots may be empty, others may show a few background characters.
No text, no words, no letters, no writing, no labels, no captions, no signage, no signs.
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
            # Comprehensive negative prompt to prevent any text in images
            negative_prompt = (
                "text, words, letters, writing, labels, captions, "
                "name tags, titles, signage, signs, typography, subtitles, "
                "text overlay, watermark, logo, alphabet, symbols, "
                "numbers, digits, text on image, written text, printed text, "
                "handwritten text, calligraphy, font, typeface, lettering, "
                "speech bubble text, comic text, subtitle text, caption text, title text, "
                "nameplate, placard, signboard, billboard, poster text, label text, "
                "badge text, tag text, watermark text, copyright text, signature text"
            )

            # Use Tongyi-MAI/Z-Image-Turbo for fast image generation
            models_to_try = [
                "Tongyi-MAI/Z-Image-Turbo",
            ]
            
            image = None
            last_error = None
            for model in models_to_try:
                try:
                    logger.info(f"Trying model: {model}")
                    # Force 16:9 aspect ratio for all portraits
                    image = self.client.text_to_image(
                        prompt,
                        model=model,
                        negative_prompt=negative_prompt,
                        width=1024,
                        height=576,
                    )
                    logger.info(f"Successfully generated with {model}")
                    break
                except Exception as e:
                    logger.warning(f"Model {model} failed: {e}")
                    last_error = e
                    continue
            
            if image is None:
                raise Exception(f"All models failed. Last error: {last_error}")

            path = self._save_to_cache(image, cache_key)
            logger.info(f"Generated portrait for {name}: {path}")
            return path

        except Exception as e:
            logger.error(f"Error generating portrait for {name}: {e}")
            return None

    def generate_scene(
        self,
        location_name: str,
        setting_description: str,
        mood: str = "mysterious",
        context: Optional[str] = None,
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

        # Extract era/period from setting description for period-accurate props
        era_hints = []
        setting_lower = setting_description.lower()
        if any(x in setting_lower for x in ["1920", "20s", "prohibition", "jazz age", "gatsby"]):
            era_hints.append("1920s Art Deco era")
        elif any(x in setting_lower for x in ["1930", "30s", "depression", "noir"]):
            era_hints.append("1930s noir era")
        elif any(x in setting_lower for x in ["1940", "40s", "war", "wartime"]):
            era_hints.append("1940s wartime era")
        elif any(x in setting_lower for x in ["1950", "50s", "atomic", "post-war"]):
            era_hints.append("1950s mid-century era")
        elif any(x in setting_lower for x in ["victorian", "1880", "1890", "19th century"]):
            era_hints.append("Victorian era, gas lamps and ornate furniture")
        elif any(x in setting_lower for x in ["medieval", "castle", "manor"]):
            era_hints.append("Medieval or Gothic era")
        elif any(x in setting_lower for x in ["modern", "contemporary", "2000", "2010", "2020"]):
            era_hints.append("Modern contemporary era")
        
        # Determine if likely interior or exterior
        location_lower = location_name.lower()
        is_interior = any(x in location_lower for x in [
            "room", "office", "study", "library", "kitchen", "bedroom", "bathroom",
            "hall", "chamber", "tent", "workshop", "shed", "cabin", "suite",
            "parlor", "lounge", "bar", "cellar", "attic", "closet", "pantry"
        ])
        is_exterior = any(x in location_lower for x in [
            "garden", "yard", "street", "dock", "pier", "forest", "woods",
            "beach", "park", "courtyard", "terrace", "balcony", "roof", "path"
        ])
        
        # Build rich descriptive prompt
        prompt_parts = [
            f"Scene: {location_name}",
        ]
        
        # Add era context
        if era_hints:
            prompt_parts.append(f"Era: {era_hints[0]}")
        
        # Add setting context
        prompt_parts.append(f"Setting: {setting_description}")
        
        # Add interior/exterior guidance
        if is_interior:
            prompt_parts.append("Interior scene with detailed furnishings, props, and atmospheric lighting through windows or lamps.")
        elif is_exterior:
            prompt_parts.append("Exterior scene with environmental details, natural lighting, and atmospheric weather effects.")
        else:
            prompt_parts.append("Atmospheric scene with period-appropriate details and dramatic lighting.")
        
        # Add mood
        mood_descriptions = {
            "mysterious": "Mysterious and foreboding atmosphere with deep shadows and hidden corners",
            "tense": "Tense atmosphere, something feels wrong, unsettling lighting",
            "peaceful": "Deceptively peaceful atmosphere, calm before the storm",
            "dark": "Dark and ominous, danger lurking in shadows",
            "dramatic": "Dramatically lit with strong contrast, theatrical staging",
        }
        mood_desc = mood_descriptions.get(mood, f"{mood} atmosphere")
        prompt_parts.append(f"Mood: {mood_desc}")
        
        # Add context from game response if provided
        if context:
            # Clean context - remove markdown and emotional tags
            clean_context = context.replace("**", "").replace("*", "")
            clean_context = re.sub(r"\[.*?\]", "", clean_context)  # Remove [excited], etc.
            # Extract descriptive phrases about the location
            clean_context = clean_context[:300].strip()
            if clean_context:
                prompt_parts.append(f"Scene details: {clean_context}")
        
        # Add style guide
        prompt_parts.append(SCENE_ART_STYLE)
        prompt_parts.append(
            "No text, no words, no letters, no writing, no labels, "
            "no captions, no signage, no signs, no people, no characters."
        )
        
        prompt = "\n".join(prompt_parts)

        cache_key = self._get_cache_key(prompt)

        # Check cache first
        cached = self._get_cached_image(cache_key)
        if cached:
            logger.info(f"Using cached scene for {location_name}")
            return cached

        try:
            logger.info(f"Generating scene for {location_name} with context...")
            # Comprehensive negative prompt to prevent any text in images
            negative_prompt = (
                "text, words, letters, writing, labels, captions, signage, signs, typography, "
                "subtitles, text overlay, watermark, logo, street signs, shop signs, billboards, "
                "alphabet, characters, symbols, numbers, digits, text on image, written text, "
                "printed text, handwritten text, calligraphy, font, typeface, lettering, "
                "inscription, engraving, text banner, speech bubble text, comic text, "
                "subtitle text, caption text, title text, nameplate, placard, signboard, "
                "billboard text, poster text, label text, badge text, tag text, "
                "watermark text, copyright text, signature text, store signs, "
                "building signs, door signs, window signs, neon signs with text"
            )
            # Use Tongyi-MAI/Z-Image-Turbo for fast image generation
            models_to_try = [
                "Tongyi-MAI/Z-Image-Turbo",
            ]
            
            image = None
            last_error = None
            for model in models_to_try:
                try:
                    logger.info(f"Trying model: {model}")
                    # Force 16:9 aspect ratio for all location scenes
                    image = self.client.text_to_image(
                        prompt,
                        model=model,
                        negative_prompt=negative_prompt,
                        width=1024,
                        height=576,
                    )
                    logger.info(f"Successfully generated with {model}")
                    break
                except Exception as e:
                    logger.warning(f"Model {model} failed: {e}")
                    last_error = e
                    continue
            
            if image is None:
                raise Exception(f"All models failed. Last error: {last_error}")

            path = self._save_to_cache(image, cache_key)
            logger.info(f"Generated scene for {location_name}: {path}")
            return path

        except Exception as e:
            logger.error(f"Error generating scene for {location_name}: {e}")
            return None

    def generate_title_card(
        self,
        title: str,
        setting: str,
        victim_name: Optional[str] = None,
        victim_background: Optional[str] = None,
    ) -> Optional[str]:
        """Generate an atmospheric opening scene image for the mystery.

        Args:
            title: Mystery title (used only as semantic context, not rendered as text)
            setting: Setting description for the scene
            victim_name: Name of the murder victim (to show in the scene)
            victim_background: Brief description of the victim

        Returns:
            Path to generated image, or None on error
        """
        if not self.client:
            logger.warning("Image client not available")
            return None

        # Build victim description for the scene.
        # We use the victim's details ONLY as atmospheric context, not to show the body.
        victim_desc = ""
        if victim_name:
            victim_desc = f"""
The scene subtly reflects the life and personality of the victim, {victim_name}, through personal items and environmental details.
Do NOT show any dead body, violence, or explicit depiction of the crime itself.
"""
            if victim_background:
                # Extract any visual hints from background (e.g., profession, age)
                victim_desc += f"Victim context: {victim_background[:150]}\n"

        # We describe this as an opening scene rather than a title card to
        # avoid encouraging any rendered text in the image.
        prompt = f"""Opening scene for a murder mystery – an atmospheric view of the location shortly after the crime.
The case is called "{title}", but do NOT draw or write the title or ANY text in the image.
Setting: {setting}
{victim_desc}
{SCENE_ART_STYLE}
Ominous, foreboding mood focused on the environment and clues, not on the body.
Do NOT show the victim's body or any graphic depiction of the crime.
No text, no words, no letters, no writing, no labels, no captions, no signage, no title.
Atmospheric scene only, no text overlay.
"""

        cache_key = self._get_cache_key(prompt)

        cached = self._get_cached_image(cache_key)
        if cached:
            return cached

        try:
            logger.info(f"Generating opening scene image...")
            # Comprehensive negative prompt to prevent any text in images
            negative_prompt = (
                "text, words, letters, writing, labels, captions, title text, signage, signs, "
                "typography, subtitles, text overlay, watermark, logo, title card text, "
                "movie title, game title, alphabet, characters, symbols, numbers, digits, "
                "text on image, written text, printed text, handwritten text, calligraphy, "
                "font, typeface, lettering, inscription, engraving, text banner, "
                "speech bubble text, comic text, subtitle text, caption text, "
                "nameplate, placard, signboard, billboard text, poster text, label text, "
                "badge text, tag text, watermark text, copyright text, signature text, "
                "title overlay, title card overlay, game title overlay, movie title overlay"
            )
            # Use Tongyi-MAI/Z-Image-Turbo for fast image generation
            models_to_try = [
                "Tongyi-MAI/Z-Image-Turbo",
            ]
            
            image = None
            last_error = None
            for model in models_to_try:
                try:
                    logger.info(f"Trying model: {model}")
                    # Force 16:9 aspect ratio for the opening scene image
                    image = self.client.text_to_image(
                        prompt,
                        model=model,
                        negative_prompt=negative_prompt,
                        width=1024,
                        height=576,
                    )
                    logger.info(f"Successfully generated with {model}")
                    break
                except Exception as e:
                    logger.warning(f"Model {model} failed: {e}")
                    last_error = e
                    continue
            
            if image is None:
                raise Exception(f"All models failed. Last error: {last_error}")

            path = self._save_to_cache(image, cache_key)
            logger.info(f"Generated opening scene image: {path}")
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


def generate_portrait_on_demand(suspect, mystery_setting: str) -> Optional[str]:
    """Generate a portrait for a suspect on-demand.
    
    Args:
        suspect: Suspect object with name, role, personality, etc.
        mystery_setting: The mystery setting for context
        
    Returns:
        Path to generated image, or None on error
    """
    service = get_image_service()
    if not service.is_available:
        logger.warning("Image service not available for on-demand portrait generation")
        return None
    
    logger.info(f"Generating portrait on-demand for {suspect.name}...")
    path = service.generate_character_portrait(
        name=suspect.name,
        role=suspect.role,
        personality=suspect.personality,
        gender=getattr(suspect, "gender", None),
        setting_context=mystery_setting,
    )
    
    if path:
        suspect.portrait_path = path
        logger.info(f"✓ Generated portrait on-demand: {suspect.name}")
    
    return path


def generate_title_card_on_demand(mystery) -> Optional[str]:
    """Generate an opening scene image for the mystery on-demand.
    
    Args:
        mystery: Mystery object with victim and setting
        
    Returns:
        Path to generated image, or None on error
    """
    service = get_image_service()
    if not service.is_available:
        logger.warning("Image service not available for opening scene generation")
        return None
    
    # Extract victim info
    victim_name = getattr(mystery.victim, "name", None) if hasattr(mystery, "victim") else None
    victim_background = getattr(mystery.victim, "background", None) if hasattr(mystery, "victim") else None
    
    logger.info("Generating opening scene image on-demand (with victim: %s)...", victim_name)
    path = service.generate_title_card(
        title=f"The Murder of {mystery.victim.name}",
        setting=mystery.setting,
        victim_name=victim_name,
        victim_background=victim_background,
    )
    
    if path:
        logger.info("✓ Generated opening scene image on-demand")
    
    return path


def generate_all_mystery_images(
    mystery, generate_portraits: bool = False, generate_title: bool = False
) -> Dict[str, str]:
    """Generate images for a mystery (now optional - mainly for backward compatibility).

    Args:
        mystery: Mystery object with suspects and setting
        generate_portraits: If True, generate all suspect portraits (default: False for on-demand)
        generate_title: If True, generate opening scene image (default: False for on-demand)

    Returns:
        Dict mapping names/locations to image paths
    """
    service = get_image_service()
    images = {}

    if not service.is_available:
        logger.info("Image generation not available, skipping")
        return images

    # Only generate if explicitly requested (for backward compatibility or special cases)
    if not generate_portraits and not generate_title:
        logger.info("Skipping startup image generation (using on-demand generation)")
        return images

    # Prepare image generation tasks based on flags
    tasks = []
    
    if generate_portraits:
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
    
    if generate_title:
        # Add opening scene task (with victim in the scene)
        victim_name = getattr(mystery.victim, "name", None) if hasattr(mystery, "victim") else None
        victim_bg = getattr(mystery.victim, "background", None) if hasattr(mystery, "victim") else None
        tasks.append((
            "_opening_scene",
            "opening_scene",
            lambda vn=victim_name, vb=victim_bg: service.generate_title_card(
                title=f"The Murder of {mystery.victim.name}", 
                setting=mystery.setting,
                victim_name=vn,
                victim_background=vb,
            )
        ))
    
    # NOTE: Scene images are always generated on-demand when locations are searched
    # This allows us to use the game response as context for better scene generation

    if not tasks:
        return images

    # Generate requested images in parallel
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
