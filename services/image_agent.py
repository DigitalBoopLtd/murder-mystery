"""MCP client for image generation.

This module provides an MCP client that connects to the image generator
MCP server for generating character portraits, scenes, and title cards.

The MCP server handles:
1. Prompt enhancement (via GPT-4o-mini)
2. Image generation (via HuggingFace/Z-Image-Turbo)
3. Image caching

Using MCP allows for:
- True parallel image generation via concurrent tool calls
- Decoupled image generation from the main app
- "MCP in Action" hackathon track qualification
"""

import os
import sys
import asyncio
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Check for MCP SDK availability
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    MCP_AVAILABLE = True
    logger.info("[MCP-IMG] MCP SDK available")
except ImportError:
    MCP_AVAILABLE = False
    ClientSession = None
    StdioServerParameters = None
    stdio_client = None
    logger.warning("[MCP-IMG] MCP SDK not installed. Run: pip install mcp")


@dataclass
class ImageResult:
    """Result from image generation."""
    path: Optional[str]
    success: bool
    error: Optional[str] = None


class ImageAgent:
    """MCP client for the image generator server.
    
    Connects to the murder-mystery-images MCP server to generate
    portraits, scenes, and title cards.
    """
    
    def __init__(self):
        self._session: Optional[ClientSession] = None
        self._api_key_openai = os.getenv("OPENAI_API_KEY", "")
        self._api_key_hf = os.getenv("HF_TOKEN", "")
    
    @property
    def is_available(self) -> bool:
        """Check if MCP client can be used."""
        return MCP_AVAILABLE and bool(self._api_key_openai) and bool(self._api_key_hf)
    
    def _get_server_params(self) -> Optional[Any]:
        """Get server parameters for the image generator MCP server."""
        if not MCP_AVAILABLE:
            return None
        
        # Get the project root directory
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        venv_python = os.path.join(project_root, "venv", "bin", "python")
        
        # Use the venv python if available, otherwise fall back to sys.executable
        python_path = venv_python if os.path.isfile(venv_python) else sys.executable
        
        # Build environment with required API keys
        # Set PYTHONPATH to include project root so the module can be found
        existing_pythonpath = os.environ.get("PYTHONPATH", "")
        pythonpath = f"{project_root}:{existing_pythonpath}" if existing_pythonpath else project_root
        
        env = {
            "OPENAI_API_KEY": self._api_key_openai,
            "HF_TOKEN": self._api_key_hf,
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": pythonpath,
            "ENHANCE_PROMPTS": os.getenv("ENHANCE_PROMPTS", "true"),
        }
        # Pass through any other relevant env vars
        for key in ["HOME", "USER", "TMPDIR"]:
            if key in os.environ:
                env[key] = os.environ[key]
        
        logger.info("[MCP-IMG] Using Python: %s", python_path)
        logger.info("[MCP-IMG] Project root: %s", project_root)
        
        return StdioServerParameters(
            command=python_path,
            args=["-m", "mcp_servers.image_generator"],
            env=env,
        )
    
    async def _call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Optional[str]:
        """Call a tool on the MCP server and return the result.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments
            
        Returns:
            Result string (usually a file path) or None on error
        """
        server_params = self._get_server_params()
        if not server_params:
            logger.error("[MCP-IMG] Failed to get server parameters")
            return None
        
        try:
            logger.info("[MCP-IMG] Connecting to image generator server...")
            
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    # Initialize the session
                    await session.initialize()
                    logger.info("[MCP-IMG] Session initialized")
                    
                    # Call the tool
                    logger.info("[MCP-IMG] Calling tool: %s", tool_name)
                    result = await session.call_tool(tool_name, arguments=arguments)
                    
                    # Parse response
                    if result and hasattr(result, 'content'):
                        for item in result.content:
                            if hasattr(item, 'text'):
                                text = item.text.strip()
                                # Check if it's an error
                                if text.startswith("Error:"):
                                    logger.error("[MCP-IMG] Tool error: %s", text)
                                    return None
                                # Return the path
                                logger.info("[MCP-IMG] Tool result: %s", text[:100])
                                return text
                    
                    logger.warning("[MCP-IMG] No valid response from tool")
                    return None
                    
        except Exception as e:
            logger.error("[MCP-IMG] Tool call failed: %s", e, exc_info=True)
            return None
    
    async def generate_portrait(
        self,
        name: str,
        role: str,
        personality: str,
        gender: str = "person",
        setting: str = "",
    ) -> Optional[str]:
        """Generate a character portrait via MCP.
        
        Args:
            name: Character name
            role: Character role
            personality: Personality traits
            gender: Gender for visual description
            setting: Setting context for costume
            
        Returns:
            Path to generated image or None
        """
        logger.info("[MCP-IMG] Generating portrait for %s via MCP", name)
        return await self._call_tool(
            "generate_character_portrait",
            {
                "name": name,
                "role": role,
                "personality": personality,
                "gender": gender,
                "setting": setting,
            }
        )
    
    async def generate_scene(
        self,
        location: str,
        setting: str,
        mood: str = "mysterious",
        context: str = "",
    ) -> Optional[str]:
        """Generate a scene/location image via MCP.
        
        Args:
            location: Location name
            setting: Broader setting context
            mood: Scene mood
            context: Additional context
            
        Returns:
            Path to generated image or None
        """
        logger.info("[MCP-IMG] Generating scene for %s via MCP", location)
        return await self._call_tool(
            "generate_scene",
            {
                "location": location,
                "setting": setting,
                "mood": mood,
                "context": context,
            }
        )
    
    async def generate_title_card(
        self,
        title: str,
        setting: str,
        victim_name: str = "",
        victim_background: str = "",
    ) -> Optional[str]:
        """Generate a title card/opening scene via MCP.
        
        Args:
            title: Mystery title
            setting: Setting description
            victim_name: Victim's name
            victim_background: Victim background info
            
        Returns:
            Path to generated image or None
        """
        logger.info("[MCP-IMG] Generating title card via MCP")
        return await self._call_tool(
            "generate_title_card",
            {
                "title": title,
                "setting": setting,
                "victim_name": victim_name,
                "victim_background": victim_background,
            }
        )
    
    async def list_cached_images(self, limit: int = 10) -> List[Dict]:
        """List cached images via MCP.
        
        Returns:
            List of cached image info dicts
        """
        import json
        
        result = await self._call_tool("list_cached_images", {"limit": limit})
        if result:
            try:
                data = json.loads(result)
                return data.get("images", [])
            except json.JSONDecodeError:
                pass
        return []


# =============================================================================
# SYNCHRONOUS WRAPPERS
# =============================================================================

def _run_async(coro):
    """Run an async coroutine in a new event loop."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def generate_portrait_sync(
    name: str,
    role: str,
    personality: str,
    gender: str = "person",
    setting: str = "",
) -> Optional[str]:
    """Synchronous wrapper for portrait generation.
    
    Args:
        name: Character name
        role: Character role  
        personality: Personality traits
        gender: Gender for visual description
        setting: Setting context
        
    Returns:
        Path to generated image or None
    """
    agent = ImageAgent()
    if not agent.is_available:
        logger.warning("[MCP-IMG] MCP not available for portrait generation")
        return None
    
    return _run_async(agent.generate_portrait(
        name=name,
        role=role,
        personality=personality,
        gender=gender,
        setting=setting,
    ))


def generate_scene_sync(
    location: str,
    setting: str,
    mood: str = "mysterious",
    context: str = "",
) -> Optional[str]:
    """Synchronous wrapper for scene generation.
    
    Args:
        location: Location name
        setting: Broader setting context
        mood: Scene mood
        context: Additional context
        
    Returns:
        Path to generated image or None
    """
    agent = ImageAgent()
    if not agent.is_available:
        logger.warning("[MCP-IMG] MCP not available for scene generation")
        return None
    
    return _run_async(agent.generate_scene(
        location=location,
        setting=setting,
        mood=mood,
        context=context,
    ))


def generate_title_card_sync(
    title: str,
    setting: str,
    victim_name: str = "",
    victim_background: str = "",
) -> Optional[str]:
    """Synchronous wrapper for title card generation.
    
    Args:
        title: Mystery title
        setting: Setting description
        victim_name: Victim's name
        victim_background: Victim background info
        
    Returns:
        Path to generated image or None
    """
    agent = ImageAgent()
    if not agent.is_available:
        logger.warning("[MCP-IMG] MCP not available for title card generation")
        return None
    
    return _run_async(agent.generate_title_card(
        title=title,
        setting=setting,
        victim_name=victim_name,
        victim_background=victim_background,
    ))


# =============================================================================
# CHECK AVAILABILITY
# =============================================================================

def check_mcp_image_availability() -> Dict[str, Any]:
    """Check MCP image generation availability.
    
    Returns:
        Dict with availability info
    """
    api_key_openai = bool(os.getenv("OPENAI_API_KEY"))
    api_key_hf = bool(os.getenv("HF_TOKEN"))
    
    return {
        "available": MCP_AVAILABLE and api_key_openai and api_key_hf,
        "sdk_installed": MCP_AVAILABLE,
        "openai_key_set": api_key_openai,
        "hf_token_set": api_key_hf,
        "message": (
            "MCP image generation ready" if MCP_AVAILABLE and api_key_openai and api_key_hf
            else "MCP SDK not installed (pip install mcp)" if not MCP_AVAILABLE
            else "Missing OPENAI_API_KEY" if not api_key_openai
            else "Missing HF_TOKEN"
        )
    }


# Log availability on module load
if MCP_AVAILABLE:
    status = check_mcp_image_availability()
    if status["available"]:
        logger.info("[MCP-IMG] ✅ MCP image generation ready")
    else:
        logger.warning("[MCP-IMG] ⚠️ MCP SDK loaded but missing keys: %s", status["message"])
else:
    logger.info("[MCP-IMG] MCP SDK not available")
