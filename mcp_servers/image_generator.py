#!/usr/bin/env python3
"""MCP Server for Murder Mystery Image Generation.

This server provides image generation tools that can be called in parallel
from the main application. It handles:
1. Prompt enhancement (via GPT-4o-mini)
2. Image generation (via HuggingFace/Z-Image-Turbo)

Running this as an MCP server allows the main app to:
- Make parallel image generation requests
- Demonstrate MCP usage for hackathon
- Decouple image generation from the main event loop

Usage:
    python -m mcp_servers.image_generator
    
    Or configure in Claude Desktop:
    {
        "mcpServers": {
            "murder-mystery-images": {
                "command": "python",
                "args": ["-m", "mcp_servers.image_generator"],
                "env": {
                    "OPENAI_API_KEY": "...",
                    "HF_TOKEN": "..."
                }
            }
        }
    }
"""

import os
import sys
import asyncio
import logging
import hashlib
import tempfile
from typing import Any, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-image-generator")

# Try MCP imports
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    logger.error("MCP SDK not installed. Run: pip install mcp")

# Image generation imports (lazy loaded)
_hf_client = None
_openai_client = None

# Cache directory
IMAGE_CACHE_DIR = os.path.join(tempfile.gettempdir(), "murder_mystery_images")
os.makedirs(IMAGE_CACHE_DIR, exist_ok=True)


# =============================================================================
# ART STYLE CONSTANTS
# =============================================================================

ART_STYLE_SUFFIX = """

Rendered in the distinctive style of 1990s LucasArts point-and-click adventure games like Monkey Island, Day of the Tentacle, and Full Throttle. Hand-painted digital art with visible brushwork and painterly textures. Rich, saturated color palette with bold contrasts. Slightly stylized and exaggerated proportions, not photorealistic. Dramatic chiaroscuro lighting with warm amber highlights and deep cool shadows. Classic adventure game aesthetic with attention to environmental storytelling."""

PROMPT_SYSTEM = """You are a visual description artist creating prompts for 1990s POINT-AND-CLICK ADVENTURE GAME art style.
Think: Monkey Island, Day of the Tentacle, Gabriel Knight, Sam & Max, Full Throttle.

Your workflow:
1. PRESERVE all core elements: subject, names, roles, actions, quantities, colors
2. ADD concrete visual details: composition, lighting, textures, colors, spatial depth
3. BE LITERAL - no metaphors, no emotional language, no abstract concepts
4. NO META-TAGS - never use "8K", "masterpiece", "best quality", "highly detailed"
5. ALWAYS emphasize the specific art style in your output

Output ONLY the enhanced prompt (200-400 words), nothing else."""


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_hf_client():
    """Get HuggingFace Inference Client."""
    global _hf_client
    if _hf_client is None:
        from huggingface_hub import InferenceClient
        hf_token = os.getenv("HF_TOKEN")
        if not hf_token:
            raise ValueError("HF_TOKEN environment variable not set")
        _hf_client = InferenceClient(provider="fal-ai", api_key=hf_token)
        logger.info("HuggingFace client initialized")
    return _hf_client


def get_openai_client():
    """Get OpenAI client."""
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        _openai_client = OpenAI(api_key=api_key)
        logger.info("OpenAI client initialized")
    return _openai_client


def get_cache_key(prompt: str) -> str:
    """Generate cache key from prompt."""
    return hashlib.md5(prompt.encode()).hexdigest()[:12]


def get_cached_image(cache_key: str) -> Optional[str]:
    """Check if image exists in cache."""
    cache_path = os.path.join(IMAGE_CACHE_DIR, f"{cache_key}.png")
    if os.path.exists(cache_path):
        logger.info(f"Cache hit: {cache_key}")
        return cache_path
    return None


def save_to_cache(image, cache_key: str) -> str:
    """Save image to cache and return path."""
    cache_path = os.path.join(IMAGE_CACHE_DIR, f"{cache_key}.png")
    image.save(cache_path)
    logger.info(f"Cached image: {cache_path}")
    return cache_path


# =============================================================================
# PROMPT ENHANCEMENT
# =============================================================================

def enhance_prompt(template: str, **kwargs) -> str:
    """Enhance a prompt using GPT-4o-mini."""
    client = get_openai_client()
    
    user_prompt = template.format(**kwargs)
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": PROMPT_SYSTEM},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=700,
            temperature=0.7
        )
        enhanced = response.choices[0].message.content.strip()
        return enhanced + ART_STYLE_SUFFIX
    except Exception as e:
        logger.error(f"Prompt enhancement failed: {e}")
        # Fallback
        return kwargs.get("fallback", "A scene in 1990s adventure game style.")


CHARACTER_TEMPLATE = """Enhance this character portrait prompt for a 1990s point-and-click adventure game.

INPUT:
- Name: {name}
- Role: {role}
- Personality: {personality}
- Gender: {gender}
- Setting: {setting}

REQUIREMENTS:
- Art style: 1990s point-and-click adventure game like Monkey Island, Gabriel Knight
- Painterly digital art with visible brushwork, rich saturated colors
- Dramatic chiaroscuro lighting with warm tones
- Slightly stylized/exaggerated features (not photorealistic)
- Portrait framing: vary between head-and-shoulders, waist-up, or three-quarter body
- Background: simplified but colorful location suggesting the setting
- NO TEXT anywhere in the image

Generate a detailed visual description."""

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
- Atmospheric depth with layered foreground/midground/background
- NO TEXT, NO SIGNS, NO WRITING visible in the image
- NO PEOPLE unless specified

Generate a detailed visual description."""

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
- Include subtle visual hints about the victim through environmental details
- DO NOT show any body, blood, violence, or graphic content
- NO TEXT anywhere in the image
- Cinematic composition with clear focal point

Generate a detailed visual description."""


# =============================================================================
# IMAGE GENERATION
# =============================================================================

def generate_image(prompt: str, width: int = 1024, height: int = 576) -> str:
    """Generate image from prompt and return path."""
    # Check cache first
    cache_key = get_cache_key(prompt)
    cached = get_cached_image(cache_key)
    if cached:
        return cached
    
    # Generate new image
    client = get_hf_client()
    
    logger.info(f"Generating image ({len(prompt)} char prompt)...")
    image = client.text_to_image(
        prompt,
        model="Tongyi-MAI/Z-Image-Turbo",
        width=width,
        height=height,
    )
    
    path = save_to_cache(image, cache_key)
    logger.info(f"Generated: {path}")
    return path


# =============================================================================
# MCP SERVER
# =============================================================================

if MCP_AVAILABLE:
    server = Server("murder-mystery-images")
    
    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List available image generation tools."""
        return [
            Tool(
                name="generate_character_portrait",
                description="Generate a character portrait in 1990s adventure game style. Returns the file path to the generated image.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Character name"},
                        "role": {"type": "string", "description": "Character's role (e.g., 'butler', 'detective')"},
                        "personality": {"type": "string", "description": "Personality traits"},
                        "gender": {"type": "string", "description": "Gender for physical description", "default": "person"},
                        "setting": {"type": "string", "description": "Setting context for costume", "default": ""}
                    },
                    "required": ["name", "role", "personality"]
                }
            ),
            Tool(
                name="generate_scene",
                description="Generate a scene/location image in 1990s adventure game style. Returns the file path.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "location": {"type": "string", "description": "Location name"},
                        "setting": {"type": "string", "description": "Broader setting context"},
                        "mood": {"type": "string", "description": "Mood/atmosphere", "default": "mysterious"},
                        "context": {"type": "string", "description": "Additional context", "default": ""}
                    },
                    "required": ["location", "setting"]
                }
            ),
            Tool(
                name="generate_title_card",
                description="Generate an atmospheric opening scene for a murder mystery. Returns the file path.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Mystery title"},
                        "setting": {"type": "string", "description": "Setting description"},
                        "victim_name": {"type": "string", "description": "Victim's name", "default": ""},
                        "victim_background": {"type": "string", "description": "Victim background", "default": ""}
                    },
                    "required": ["title", "setting"]
                }
            )
        ]
    
    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle tool calls - generate images."""
        try:
            if name == "generate_character_portrait":
                # Enhance prompt
                prompt = enhance_prompt(
                    CHARACTER_TEMPLATE,
                    name=arguments.get("name", "Unknown"),
                    role=arguments.get("role", "person"),
                    personality=arguments.get("personality", ""),
                    gender=arguments.get("gender", "person"),
                    setting=arguments.get("setting", ""),
                    fallback=f"Portrait of {arguments.get('name', 'a character')} in 1990s adventure game style."
                )
                
                # Generate image
                path = generate_image(prompt)
                return [TextContent(type="text", text=path)]
                
            elif name == "generate_scene":
                prompt = enhance_prompt(
                    SCENE_TEMPLATE,
                    location=arguments.get("location", ""),
                    setting=arguments.get("setting", ""),
                    mood=arguments.get("mood", "mysterious"),
                    context=arguments.get("context", ""),
                    fallback=f"Scene of {arguments.get('location', 'a location')} in 1990s adventure game style."
                )
                
                path = generate_image(prompt)
                return [TextContent(type="text", text=path)]
                
            elif name == "generate_title_card":
                prompt = enhance_prompt(
                    TITLE_CARD_TEMPLATE,
                    title=arguments.get("title", ""),
                    setting=arguments.get("setting", ""),
                    victim_name=arguments.get("victim_name", ""),
                    victim_background=arguments.get("victim_background", ""),
                    fallback=f"Atmospheric opening scene for a murder mystery in 1990s adventure game style."
                )
                
                path = generate_image(prompt)
                return [TextContent(type="text", text=path)]
                
            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]
                
        except Exception as e:
            logger.error(f"Tool {name} failed: {e}")
            return [TextContent(type="text", text=f"Error: {str(e)}")]


# =============================================================================
# MAIN
# =============================================================================

async def main():
    """Run the MCP server."""
    if not MCP_AVAILABLE:
        print("ERROR: MCP SDK not installed. Run: pip install mcp")
        sys.exit(1)
    
    logger.info("Starting Murder Mystery Image Generator MCP Server...")
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())

