"""MCP Client for parallel image generation.

This client connects to the Murder Mystery Image Generator MCP server
and allows making multiple image generation requests in parallel.

Architecture:
- Each image generation request spawns a connection to the MCP server
- Multiple requests can run concurrently using asyncio.gather()
- Results are collected and returned as a batch

Usage:
    from services.mcp_image_client import MCPImageClient
    
    async with MCPImageClient() as client:
        # Generate multiple portraits in parallel
        paths = await client.generate_portraits_parallel([
            {"name": "John", "role": "Butler", "personality": "Nervous"},
            {"name": "Mary", "role": "Maid", "personality": "Secretive"},
        ])
"""

import os
import sys
import asyncio
import logging
from typing import Optional, List, Dict, Any
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# Try MCP imports
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    logger.warning("MCP client SDK not available")


class MCPImageClient:
    """Client for the Murder Mystery Image Generator MCP server.
    
    Supports parallel image generation by making concurrent MCP calls.
    """
    
    def __init__(self, max_workers: int = 4):
        """Initialize the client.
        
        Args:
            max_workers: Maximum number of parallel image generations
        """
        self.max_workers = max_workers
        self._server_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "mcp_servers",
            "image_generator.py"
        )
    
    def _get_server_params(self) -> "StdioServerParameters":
        """Get MCP server parameters."""
        return StdioServerParameters(
            command=sys.executable,
            args=[self._server_path],
            env={
                "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
                "HF_TOKEN": os.getenv("HF_TOKEN", ""),
                "PATH": os.environ.get("PATH", ""),
            }
        )
    
    async def _call_tool(self, tool_name: str, arguments: dict) -> str:
        """Make a single MCP tool call.
        
        Each call spawns a new connection to the server.
        This allows true parallelism.
        """
        if not MCP_AVAILABLE:
            raise RuntimeError("MCP SDK not available")
        
        server_params = self._get_server_params()
        
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                result = await session.call_tool(tool_name, arguments=arguments)
                
                if result.content and len(result.content) > 0:
                    return result.content[0].text
                return ""
    
    # =========================================================================
    # SINGLE IMAGE GENERATION
    # =========================================================================
    
    async def generate_character_portrait(
        self,
        name: str,
        role: str,
        personality: str,
        gender: str = "person",
        setting: str = ""
    ) -> str:
        """Generate a single character portrait.
        
        Returns:
            Path to the generated image file
        """
        return await self._call_tool("generate_character_portrait", {
            "name": name,
            "role": role,
            "personality": personality,
            "gender": gender,
            "setting": setting
        })
    
    async def generate_scene(
        self,
        location: str,
        setting: str,
        mood: str = "mysterious",
        context: str = ""
    ) -> str:
        """Generate a single scene image.
        
        Returns:
            Path to the generated image file
        """
        return await self._call_tool("generate_scene", {
            "location": location,
            "setting": setting,
            "mood": mood,
            "context": context
        })
    
    async def generate_title_card(
        self,
        title: str,
        setting: str,
        victim_name: str = "",
        victim_background: str = ""
    ) -> str:
        """Generate a title card/opening scene.
        
        Returns:
            Path to the generated image file
        """
        return await self._call_tool("generate_title_card", {
            "title": title,
            "setting": setting,
            "victim_name": victim_name,
            "victim_background": victim_background
        })
    
    # =========================================================================
    # PARALLEL IMAGE GENERATION
    # =========================================================================
    
    async def generate_portraits_parallel(
        self,
        characters: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        """Generate multiple character portraits in parallel.
        
        Args:
            characters: List of dicts with keys: name, role, personality, gender, setting
            
        Returns:
            Dict mapping character name to image path
        """
        async def generate_one(char: dict) -> tuple:
            name = char.get("name", "Unknown")
            try:
                path = await self.generate_character_portrait(
                    name=name,
                    role=char.get("role", ""),
                    personality=char.get("personality", ""),
                    gender=char.get("gender", "person"),
                    setting=char.get("setting", "")
                )
                logger.info(f"[MCP] Generated portrait for {name}: {path}")
                return (name, path)
            except Exception as e:
                logger.error(f"[MCP] Failed to generate portrait for {name}: {e}")
                return (name, None)
        
        # Run all generations in parallel
        tasks = [generate_one(char) for char in characters]
        results = await asyncio.gather(*tasks)
        
        return {name: path for name, path in results if path}
    
    async def generate_scenes_parallel(
        self,
        scenes: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        """Generate multiple scene images in parallel.
        
        Args:
            scenes: List of dicts with keys: location, setting, mood, context
            
        Returns:
            Dict mapping location name to image path
        """
        async def generate_one(scene: dict) -> tuple:
            location = scene.get("location", "Unknown")
            try:
                path = await self.generate_scene(
                    location=location,
                    setting=scene.get("setting", ""),
                    mood=scene.get("mood", "mysterious"),
                    context=scene.get("context", "")
                )
                logger.info(f"[MCP] Generated scene for {location}: {path}")
                return (location, path)
            except Exception as e:
                logger.error(f"[MCP] Failed to generate scene for {location}: {e}")
                return (location, None)
        
        tasks = [generate_one(scene) for scene in scenes]
        results = await asyncio.gather(*tasks)
        
        return {loc: path for loc, path in results if path}
    
    async def generate_all_mystery_images(
        self,
        mystery,
        setting: str
    ) -> Dict[str, str]:
        """Generate all images for a mystery in parallel.
        
        Args:
            mystery: Mystery object with suspects and victim
            setting: Setting description
            
        Returns:
            Dict mapping names/locations to image paths
        """
        results = {}
        
        # Prepare character data
        characters = []
        for suspect in mystery.suspects:
            characters.append({
                "name": suspect.name,
                "role": suspect.role,
                "personality": suspect.personality,
                "gender": getattr(suspect, "gender", "person"),
                "setting": setting
            })
        
        # Prepare title card
        title_card_task = self.generate_title_card(
            title=f"The Murder of {mystery.victim.name}",
            setting=setting,
            victim_name=mystery.victim.name,
            victim_background=mystery.victim.background
        )
        
        # Generate all in parallel
        portrait_task = self.generate_portraits_parallel(characters)
        
        # Wait for both
        portraits, title_path = await asyncio.gather(portrait_task, title_card_task)
        
        results.update(portraits)
        if title_path:
            results["_title_card"] = title_path
        
        return results


# =============================================================================
# SYNC WRAPPERS (for use in non-async code)
# =============================================================================

def generate_portrait_sync(
    name: str,
    role: str,
    personality: str,
    gender: str = "person",
    setting: str = ""
) -> Optional[str]:
    """Synchronous wrapper for single portrait generation."""
    async def _run():
        client = MCPImageClient()
        return await client.generate_character_portrait(name, role, personality, gender, setting)
    
    try:
        return asyncio.run(_run())
    except Exception as e:
        logger.error(f"[MCP] Portrait generation failed: {e}")
        return None


def generate_scene_sync(
    location: str,
    setting: str,
    mood: str = "mysterious",
    context: str = ""
) -> Optional[str]:
    """Synchronous wrapper for single scene generation."""
    async def _run():
        client = MCPImageClient()
        return await client.generate_scene(location, setting, mood, context)
    
    try:
        return asyncio.run(_run())
    except Exception as e:
        logger.error(f"[MCP] Scene generation failed: {e}")
        return None


def generate_all_images_sync(mystery, setting: str) -> Dict[str, str]:
    """Synchronous wrapper for parallel image generation."""
    async def _run():
        client = MCPImageClient()
        return await client.generate_all_mystery_images(mystery, setting)
    
    try:
        return asyncio.run(_run())
    except Exception as e:
        logger.error(f"[MCP] Batch generation failed: {e}")
        return {}


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    async def test():
        print("Testing MCP Image Client...")
        
        client = MCPImageClient()
        
        # Test single portrait
        print("\n1. Testing single portrait generation...")
        path = await client.generate_character_portrait(
            name="Test Character",
            role="Butler",
            personality="Nervous and secretive",
            gender="male",
            setting="1920s mansion"
        )
        print(f"   Result: {path}")
        
        # Test parallel portraits
        print("\n2. Testing parallel portrait generation...")
        paths = await client.generate_portraits_parallel([
            {"name": "John Smith", "role": "Butler", "personality": "Nervous", "gender": "male", "setting": "1920s"},
            {"name": "Mary Jones", "role": "Maid", "personality": "Secretive", "gender": "female", "setting": "1920s"},
        ])
        print(f"   Results: {paths}")
        
        print("\nDone!")
    
    asyncio.run(test())

