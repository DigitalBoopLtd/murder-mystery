"""Image generation service for character portraits and scene art.

Uses HuggingFace Inference API with fal-ai provider for fast generation.
Styled to look like 90s point-and-click adventure games (Monkey Island, Day of the Tentacle, Gabriel Knight, etc.)

Supports two modes:
1. Direct mode (default): Uses prompt_enhancer directly + HuggingFace API
2. MCP mode (USE_MCP=true): Uses MCP server for parallel image generation

Prompts are enhanced using LLM (GPT-4o-mini) to generate detailed visual descriptions
optimized for Z-Image-Turbo, which works best with long, detailed prompts and ignores
negative prompts (guidance_scale=0.0).
"""

import os
import re
import logging
import hashlib
import tempfile
import asyncio
from typing import Optional, Dict
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from huggingface_hub import InferenceClient

from services.prompt_enhancer import (
    enhance_character_prompt,
    enhance_scene_prompt,
    enhance_title_card_prompt,
)

# Check if MCP mode is enabled
USE_MCP = os.getenv("USE_MCP", "false").lower() == "true"

# Initialize MCP variables (will be set if MCP is available)
MCP_AVAILABLE = False
MCPImageClient = None
mcp_generate_portrait = None
mcp_generate_scene = None

if USE_MCP:
    try:
        from services.mcp_image_client import (
            MCPImageClient as _MCPImageClient,
            generate_portrait_sync as _mcp_generate_portrait,
            generate_scene_sync as _mcp_generate_scene,
        )
        MCPImageClient = _MCPImageClient
        mcp_generate_portrait = _mcp_generate_portrait
        mcp_generate_scene = _mcp_generate_scene
        MCP_AVAILABLE = True
    except ImportError:
        USE_MCP = False

logger = logging.getLogger(__name__)

# Directory for caching generated images
IMAGE_CACHE_DIR = os.path.join(tempfile.gettempdir(), "murder_mystery_images")
os.makedirs(IMAGE_CACHE_DIR, exist_ok=True)


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

        gender_str = gender if gender else "person"

        # Use LLM to enhance prompt with detailed visual description
        prompt = enhance_character_prompt(
            name=name,
            role=role,
            personality=personality,
            gender=gender_str,
            setting=setting_context or ""
        )
        
        logger.info(f"[IMG] Enhanced portrait prompt for {name}: {len(prompt)} chars")

        cache_key = self._get_cache_key(prompt)

        # Check cache first
        cached = self._get_cached_image(cache_key)
        if cached:
            return cached

        try:
            logger.info(f"Generating portrait for {name}...")

            # Z-Image-Turbo ignores negative prompts (guidance_scale=0.0)
            # so we rely entirely on the enhanced positive prompt
            image = self.client.text_to_image(
                prompt,
                model="Tongyi-MAI/Z-Image-Turbo",
                width=1024,
                height=576,
            )

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

        # Clean context if provided
        clean_context = ""
        if context:
            clean_context = context.replace("**", "").replace("*", "")
            clean_context = re.sub(r"\[.*?\]", "", clean_context)  # Remove [excited], etc.
            clean_context = clean_context[:500].strip()

        # Use LLM to enhance prompt with detailed visual description
        prompt = enhance_scene_prompt(
            location=location_name,
            setting=setting_description,
            mood=mood,
            context=clean_context
        )
        
        logger.info(f"[IMG] Enhanced scene prompt for {location_name}: {len(prompt)} chars")

        cache_key = self._get_cache_key(prompt)

        # Check cache first
        cached = self._get_cached_image(cache_key)
        if cached:
            logger.info(f"Using cached scene for {location_name}")
            return cached

        try:
            logger.info(f"Generating scene for {location_name}...")

            # Z-Image-Turbo ignores negative prompts (guidance_scale=0.0)
            # so we rely entirely on the enhanced positive prompt
            image = self.client.text_to_image(
                prompt,
                model="Tongyi-MAI/Z-Image-Turbo",
                width=1024,
                height=576,
            )

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
        fast_mode: bool = False,
    ) -> Optional[str]:
        """Generate an atmospheric opening scene image for the mystery.

        Args:
            title: Mystery title (used only as semantic context, not rendered as text)
            setting: Setting description for the scene
            victim_name: Name of the murder victim (used for context, not shown)
            victim_background: Brief description of the victim
            fast_mode: If True, skip LLM prompt enhancement for faster generation

        Returns:
            Path to generated image, or None on error
        """
        if not self.client:
            logger.warning("Image client not available")
            return None

        # Use LLM to enhance prompt with detailed visual description
        # fast_mode=True skips the LLM call for ~6s faster generation
        prompt = enhance_title_card_prompt(
            title=title,
            setting=setting,
            victim_name=victim_name,
            victim_background=victim_background,
            fast_mode=fast_mode
        )
        
        logger.info(f"[IMG] Title card prompt ({('fast' if fast_mode else 'enhanced')}): {len(prompt)} chars")

        cache_key = self._get_cache_key(prompt)

        cached = self._get_cached_image(cache_key)
        if cached:
            return cached

        try:
            logger.info(f"Generating opening scene image...")

            # Z-Image-Turbo ignores negative prompts (guidance_scale=0.0)
            # so we rely entirely on the enhanced positive prompt
            image = self.client.text_to_image(
                prompt,
                model="Tongyi-MAI/Z-Image-Turbo",
                width=1024,
                height=576,
            )

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


def generate_title_card_on_demand(mystery, fast_mode: bool = False) -> Optional[str]:
    """Generate an opening scene image for the mystery on-demand.
    
    Args:
        mystery: Mystery object with victim and setting
        fast_mode: If True, skip LLM prompt enhancement (~6s faster)
        
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
    
    logger.info("Generating opening scene image on-demand (fast_mode=%s, victim=%s)...", fast_mode, victim_name)
    path = service.generate_title_card(
        title=f"The Murder of {mystery.victim.name}",
        setting=mystery.setting,
        victim_name=victim_name,
        victim_background=victim_background,
        fast_mode=fast_mode,
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


# =============================================================================
# MCP-BASED PARALLEL GENERATION
# =============================================================================

def generate_all_mystery_images_mcp(mystery) -> Dict[str, str]:
    """Generate all mystery images using MCP server for true parallelism.
    
    This uses the MCP image generator server, which handles both prompt
    enhancement and image generation. Multiple images are generated in
    parallel via concurrent MCP calls.
    
    Args:
        mystery: Mystery object with suspects, victim, and setting
        
    Returns:
        Dict mapping names to image paths
    """
    if not MCP_AVAILABLE or MCPImageClient is None:
        logger.warning("MCP not available, falling back to direct generation")
        return generate_all_mystery_images(mystery, generate_portraits=True, generate_title=True)
    
    logger.info("[MCP] Starting parallel image generation via MCP server...")
    
    async def _generate_all():
        client = MCPImageClient()  # type: ignore
        
        # Prepare all generation tasks
        tasks = []
        
        # Character portraits
        for suspect in mystery.suspects:
            tasks.append((
                "portrait",
                suspect.name,
                client.generate_character_portrait(
                    name=suspect.name,
                    role=suspect.role,
                    personality=suspect.personality,
                    gender=getattr(suspect, "gender", "person"),
                    setting=mystery.setting
                )
            ))
        
        # Title card
        tasks.append((
            "title",
            "_opening_scene",
            client.generate_title_card(
                title=f"The Murder of {mystery.victim.name}",
                setting=mystery.setting,
                victim_name=mystery.victim.name,
                victim_background=mystery.victim.background
            )
        ))
        
        # Run ALL tasks in parallel
        logger.info(f"[MCP] Launching {len(tasks)} parallel image generations...")
        
        async def run_task(task_type, name, coro):
            try:
                path = await coro
                logger.info(f"[MCP] ✓ Generated {task_type}: {name}")
                return (name, path)
            except Exception as e:
                logger.error(f"[MCP] ✗ Failed {task_type} {name}: {e}")
                return (name, None)
        
        results = await asyncio.gather(*[
            run_task(t[0], t[1], t[2]) for t in tasks
        ])
        
        return {name: path for name, path in results if path}
    
    try:
        images = asyncio.run(_generate_all())
        
        # Update suspect portrait paths
        for suspect in mystery.suspects:
            if suspect.name in images:
                suspect.portrait_path = images[suspect.name]
        
        logger.info(f"[MCP] Completed: {len(images)} images generated")
        return images
        
    except Exception as e:
        logger.error(f"[MCP] Parallel generation failed: {e}")
        return {}


def generate_portrait_mcp(suspect, mystery_setting: str) -> Optional[str]:
    """Generate a single portrait using MCP server.
    
    Args:
        suspect: Suspect object
        mystery_setting: Setting description
        
    Returns:
        Path to generated image
    """
    if not MCP_AVAILABLE or mcp_generate_portrait is None:
        return generate_portrait_on_demand(suspect, mystery_setting)
    
    logger.info(f"[MCP] Generating portrait for {suspect.name}...")
    path = mcp_generate_portrait(
        name=suspect.name,
        role=suspect.role,
        personality=suspect.personality,
        gender=getattr(suspect, "gender", "person"),
        setting=mystery_setting
    )
    
    if path:
        suspect.portrait_path = path
        logger.info(f"[MCP] ✓ Generated portrait: {suspect.name}")
    
    return path


def generate_scene_mcp(
    location: str,
    setting: str,
    mood: str = "mysterious",
    context: str = ""
) -> Optional[str]:
    """Generate a scene image using MCP server.
    
    Args:
        location: Location name
        setting: Mystery setting
        mood: Scene mood
        context: Additional context
        
    Returns:
        Path to generated image
    """
    if not MCP_AVAILABLE or mcp_generate_scene is None:
        service = get_image_service()
        return service.generate_scene(location, setting, mood, context)
    
    logger.info(f"[MCP] Generating scene for {location}...")
    path = mcp_generate_scene(
        location=location,
        setting=setting,
        mood=mood,
        context=context
    )
    
    if path:
        logger.info(f"[MCP] ✓ Generated scene: {location}")
    
    return path


# =============================================================================
# UNIFIED API (automatically chooses MCP or direct based on USE_MCP)
# =============================================================================

def smart_generate_portrait(suspect, mystery_setting: str) -> Optional[str]:
    """Generate portrait using MCP if available, otherwise direct."""
    if USE_MCP and MCP_AVAILABLE:
        return generate_portrait_mcp(suspect, mystery_setting)
    return generate_portrait_on_demand(suspect, mystery_setting)


def smart_generate_scene(
    location: str,
    setting: str,
    mood: str = "mysterious",
    context: str = ""
) -> Optional[str]:
    """Generate scene using MCP if available, otherwise direct."""
    if USE_MCP and MCP_AVAILABLE:
        return generate_scene_mcp(location, setting, mood, context)
    service = get_image_service()
    return service.generate_scene(location, setting, mood, context)


def smart_generate_all(mystery) -> Dict[str, str]:
    """Generate all mystery images using MCP if available, otherwise direct."""
    if USE_MCP and MCP_AVAILABLE:
        return generate_all_mystery_images_mcp(mystery)
    return generate_all_mystery_images(mystery, generate_portraits=True, generate_title=True)


# Log MCP status on module load
if USE_MCP:
    if MCP_AVAILABLE:
        logger.info("🔌 MCP mode ENABLED - Using MCP server for image generation")
    else:
        logger.warning("⚠️ USE_MCP=true but MCP client not available, falling back to direct mode")
