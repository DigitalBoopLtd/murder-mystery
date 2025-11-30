"""Prompt enhancement for Z-Image-Turbo image generation.

Uses LLM to expand short prompts into detailed visual descriptions
following Z-Image-Turbo best practices.

Key insights from Z-Image-Turbo documentation:
- Works best with long, detailed prompts (600-1000 words)
- Does NOT use negative prompts (guidance_scale=0.0)
- No meta-tags like "8K", "masterpiece", "best quality"
- Be literal and specific, avoid metaphors
"""

import os
import logging
import threading
import hashlib
from typing import Optional, Dict

from services.perf_tracker import perf

logger = logging.getLogger(__name__)

# Initialize OpenAI client lazily
_client = None

# Semaphore to limit concurrent API calls (prevents rate limit issues)
_api_semaphore = threading.Semaphore(3)  # Max 3 concurrent calls

# Simple in-memory cache for enhanced prompts
_prompt_cache: Dict[str, str] = {}
_cache_lock = threading.Lock()


def _cache_key(prompt_type: str, **kwargs) -> str:
    """Generate cache key from prompt parameters."""
    key_str = f"{prompt_type}:" + ":".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
    return hashlib.md5(key_str.encode()).hexdigest()[:16]


def get_client():
    """Get or create OpenAI client."""
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client


# =============================================================================
# SYSTEM PROMPT - Core instructions for the prompt enhancer
# =============================================================================

PROMPT_ENHANCER_SYSTEM = """You are a visual description artist who transforms simple prompts into rich, detailed image descriptions optimized for text-to-image AI models.

CRITICAL: You are creating prompts for 1990s POINT-AND-CLICK ADVENTURE GAME art style. 
Think: Monkey Island, Day of the Tentacle, Gabriel Knight, Sam & Max, Full Throttle.

Your workflow:
1. PRESERVE all core elements: subject, names, roles, actions, quantities, colors
2. ADD concrete visual details: composition, lighting, textures, colors, spatial depth
3. BE LITERAL - no metaphors, no emotional language, no abstract concepts
4. NO META-TAGS - never use "8K", "masterpiece", "best quality", "highly detailed", "award winning"
5. ALWAYS emphasize the specific art style in your output

Your descriptions should be:
- 200-400 words
- Specific and concrete
- Focused on what IS in the image, not what isn't
- Written as continuous prose, not bullet points
- ALWAYS include explicit art style description (painterly, hand-painted, visible brushstrokes, saturated colors)

Output ONLY the enhanced prompt, nothing else. No preamble, no explanation."""


# =============================================================================
# ART STYLE SUFFIX - Appended to all enhanced prompts for consistency
# =============================================================================

ART_STYLE_SUFFIX = """

Rendered in the distinctive style of 1990s LucasArts point-and-click adventure games like Monkey Island, Day of the Tentacle, and Full Throttle. Hand-painted digital art with visible brushwork and painterly textures. Rich, saturated color palette with bold contrasts. Slightly stylized and exaggerated proportions, not photorealistic. Dramatic chiaroscuro lighting with warm amber highlights and deep cool shadows. Classic adventure game aesthetic with attention to environmental storytelling."""


# =============================================================================
# TEMPLATES - Specific templates for different image types
# =============================================================================

CHARACTER_PORTRAIT_TEMPLATE = """Enhance this character portrait prompt for a 1990s point-and-click adventure game style image.

INPUT:
- Name: {name}
- Role: {role}
- Personality: {personality}
- Gender: {gender}
- Setting: {setting}

REQUIREMENTS:
- Art style: 1990s point-and-click adventure game like Monkey Island, Gabriel Knight, Day of the Tentacle
- Painterly digital art with visible brushwork, rich saturated colors
- Dramatic chiaroscuro lighting with warm tones
- Slightly stylized/exaggerated features (not photorealistic)
- Portrait framing: vary between head-and-shoulders, waist-up, or three-quarter body
- Camera angle: mix of straight-on, three-quarter view, slight profile
- Background: simplified but colorful location suggesting the setting
- NO TEXT anywhere in the image
- Infer appropriate age, clothing, physical features from role and personality

Generate a detailed visual description of this character portrait."""


SCENE_TEMPLATE = """Enhance this scene prompt for a 1990s point-and-click adventure game background.

INPUT:
- Location: {location}
- Setting: {setting}
- Mood: {mood}
- Context: {context}

REQUIREMENTS:
- Art style: 1990s adventure game backgrounds like Monkey Island, Gabriel Knight, The Dig
- Painterly digital art with visible brushwork texture
- Rich saturated colors with dramatic lighting
- First-person detective POV surveying the scene
- Include period-appropriate props, furniture, environmental details
- Atmospheric depth with layered foreground/midground/background
- NO TEXT, NO SIGNS, NO WRITING visible in the image
- NO PEOPLE unless specifically mentioned in context

Generate a detailed visual description of this scene."""


TITLE_CARD_TEMPLATE = """Enhance this opening scene prompt for a murder mystery game.

INPUT:
- Title: {title}
- Setting: {setting}
- Victim Name: {victim_name}
- Victim Background: {victim_background}

REQUIREMENTS:
- Art style: 1990s adventure game like Gabriel Knight or The Dig
- Atmospheric establishing shot of the crime scene location
- Moody, foreboding atmosphere with dramatic lighting
- Show the environment AFTER the crime (ominous, disturbed)
- Include subtle visual hints about the victim's life/status through environmental details
- DO NOT show any body, blood, violence, or graphic content
- NO TEXT anywhere in the image
- Cinematic composition with clear focal point

Generate a detailed visual description of this atmospheric opening scene."""


# =============================================================================
# CORE ENHANCEMENT FUNCTIONS
# =============================================================================

def enhance_character_prompt(
    name: str,
    role: str,
    personality: str,
    gender: str = "person",
    setting: str = ""
) -> str:
    """Enhance a character portrait prompt using LLM.
    
    Args:
        name: Character name
        role: Their role (butler, detective, etc.)
        personality: Personality traits
        gender: Gender for physical description
        setting: Setting context for costume/environment hints
        
    Returns:
        Enhanced prompt string (200-400 words)
    """
    # Check cache first
    cache_key = _cache_key("char", name=name, role=role, personality=personality[:50], gender=gender)
    with _cache_lock:
        if cache_key in _prompt_cache:
            logger.info(f"[PE] Cache hit for character {name}")
            return _prompt_cache[cache_key]
    
    client = get_client()
    
    user_prompt = CHARACTER_PORTRAIT_TEMPLATE.format(
        name=name,
        role=role,
        personality=personality,
        gender=gender,
        setting=setting or "unspecified"
    )
    
    try:
        perf.start("prompt_enhance_char", details=f"gpt-4o-mini for {name}")
        # Use semaphore to limit concurrent API calls
        with _api_semaphore:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": PROMPT_ENHANCER_SYSTEM},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=700,
                temperature=0.7
            )
        
        enhanced = response.choices[0].message.content.strip()
        # Always append the art style suffix for consistent visual style
        enhanced = enhanced + ART_STYLE_SUFFIX
        perf.end("prompt_enhance_char", details=f"{len(enhanced)} chars")
        logger.info(f"[PE] Enhanced character prompt for {name}: {len(enhanced)} chars")
        
        # Cache the result
        with _cache_lock:
            _prompt_cache[cache_key] = enhanced
        
        return enhanced
        
    except Exception as e:
        perf.end("prompt_enhance_char", status="error", details=str(e))
        logger.error(f"[PE] Character enhancement failed: {e}")
        # Fallback to basic prompt
        return _fallback_character_prompt(name, role, personality, gender, setting)


def enhance_scene_prompt(
    location: str,
    setting: str,
    mood: str = "mysterious",
    context: str = ""
) -> str:
    """Enhance a scene/location prompt using LLM.
    
    Args:
        location: Location name
        setting: Overall setting description
        mood: Mood of the scene
        context: Optional context from game response
        
    Returns:
        Enhanced prompt string (200-400 words)
    """
    # Check cache first (note: context is excluded from cache key for prewarm)
    cache_key = _cache_key("scene", location=location, setting=setting[:100], mood=mood)
    with _cache_lock:
        if cache_key in _prompt_cache:
            logger.info(f"[PE] Cache hit for scene {location}")
            return _prompt_cache[cache_key]
    
    client = get_client()
    
    user_prompt = SCENE_TEMPLATE.format(
        location=location,
        setting=setting,
        mood=mood,
        context=context[:500] if context else "No additional context provided"
    )
    
    try:
        perf.start("prompt_enhance_scene", details=f"gpt-4o-mini for {location[:20]}")
        # Use semaphore to limit concurrent API calls
        with _api_semaphore:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": PROMPT_ENHANCER_SYSTEM},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=700,
                temperature=0.7
            )
        
        enhanced = response.choices[0].message.content.strip()
        # Always append the art style suffix for consistent visual style
        enhanced = enhanced + ART_STYLE_SUFFIX
        perf.end("prompt_enhance_scene", details=f"{len(enhanced)} chars")
        logger.info(f"[PE] Enhanced scene prompt for {location}: {len(enhanced)} chars")
        
        # Cache the result
        with _cache_lock:
            _prompt_cache[cache_key] = enhanced
        
        return enhanced
        
    except Exception as e:
        perf.end("prompt_enhance_scene", status="error", details=str(e))
        logger.error(f"[PE] Scene enhancement failed: {e}")
        return _fallback_scene_prompt(location, setting, mood)


def enhance_title_card_prompt(
    title: str,
    setting: str,
    victim_name: Optional[str] = None,
    victim_background: Optional[str] = None,
    fast_mode: bool = False
) -> str:
    """Enhance an opening scene/title card prompt using LLM.
    
    Args:
        title: Mystery title
        setting: Setting description
        victim_name: Name of the victim
        victim_background: Background info about victim
        fast_mode: If True, skip LLM enhancement and use fast fallback (saves ~6s)
        
    Returns:
        Enhanced prompt string (200-400 words)
    """
    # Fast mode: use direct template without LLM call (for startup speed)
    if fast_mode:
        logger.info("[PE] Using fast mode for title card (no LLM enhancement)")
        return _fallback_title_prompt(title, setting)
    
    # Check cache first
    cache_key = _cache_key("title", title=title, setting=setting[:100], victim=victim_name or "")
    with _cache_lock:
        if cache_key in _prompt_cache:
            logger.info("[PE] Cache hit for title card")
            return _prompt_cache[cache_key]
    
    client = get_client()
    
    user_prompt = TITLE_CARD_TEMPLATE.format(
        title=title,
        setting=setting,
        victim_name=victim_name or "Unknown victim",
        victim_background=victim_background or "No background provided"
    )
    
    try:
        perf.start("prompt_enhance_title", details="gpt-4o-mini")
        # Use semaphore to limit concurrent API calls
        with _api_semaphore:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": PROMPT_ENHANCER_SYSTEM},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=700,
                temperature=0.7
            )
        
        enhanced = response.choices[0].message.content.strip()
        # Always append the art style suffix for consistent visual style
        enhanced = enhanced + ART_STYLE_SUFFIX
        perf.end("prompt_enhance_title", details=f"{len(enhanced)} chars")
        logger.info("[PE] Enhanced title card prompt: %d chars", len(enhanced))
        
        # Cache the result
        with _cache_lock:
            _prompt_cache[cache_key] = enhanced
        
        return enhanced
        
    except Exception as e:
        perf.end("prompt_enhance_title", status="error", details=str(e))
        logger.error(f"[PE] Title card enhancement failed: {e}")
        return _fallback_title_prompt(title, setting)


# =============================================================================
# FALLBACK PROMPTS - Used when LLM enhancement fails
# =============================================================================

def _fallback_character_prompt(
    name: str, role: str, personality: str, gender: str, setting: str
) -> str:
    """Generate a basic prompt when LLM enhancement fails."""
    return f"""Portrait of {name}, a {gender} who works as a {role}. Their personality can be described as {personality}. 

The character is shown from the chest up, positioned slightly off-center with a three-quarter view angle. Their expression reflects their personality. The background suggests {setting if setting else 'an atmospheric interior'}, rendered in soft focus with muted colors.

Slightly stylized proportions with expressive eyes and defined features. No text or writing anywhere in the image.
{ART_STYLE_SUFFIX}"""


def _fallback_scene_prompt(location: str, setting: str, mood: str) -> str:
    """Generate a basic scene prompt when LLM enhancement fails."""
    return f"""A view of {location}. {setting}.

The scene has a {mood} atmosphere with dramatic lighting casting long shadows across the space. The composition draws the eye through layered depth - interesting elements in the foreground, the main area of interest in the midground, and atmospheric background elements fading into shadow. Period-appropriate props and furniture fill the space naturally.

First-person perspective as if the detective is surveying the scene. No people visible. No text, signs, or writing anywhere in the image.
{ART_STYLE_SUFFIX}"""


def _fallback_title_prompt(title: str, setting: str) -> str:
    """Generate a basic title card prompt when LLM enhancement fails."""
    return f"""An atmospheric establishing shot for a murder mystery set in {setting}.

The mood is ominous and foreboding, suggesting something terrible has happened. Cinematic composition with a clear focal point drawing the viewer into the scene. Environmental details hint at wealth, status, and secrets. Deep shadows and pools of warm light create visual tension.

No body or explicit violence shown - only the aftermath suggested through disturbed elements and ominous atmosphere. No text or writing anywhere in the image.
{ART_STYLE_SUFFIX}"""

