"""Image Agent - MCP Client for Image Generation.

This agent/client calls the Image MCP Server for image generation.
It's used both in the app AND as a hackathon demo showing MCP composition.

Usage in app:
    from services.image_agent import ImageAgent
    
    agent = ImageAgent()
    path = await agent.generate_portrait("Holmes", "Detective", "Analytical")

Usage for demo (reading MCP Resources):
    stats = await agent.get_cache_stats()  # images://stats
    styles = await agent.get_available_styles()  # images://styles

Parallel generation:
    paths = await agent.generate_portraits_parallel([
        {"name": "John", "role": "Butler", "personality": "Nervous"},
        {"name": "Mary", "role": "Maid", "personality": "Secretive"},
    ])
"""

import os
import sys
import asyncio
import json
import logging
from typing import Optional, Dict, Any, List

# Add parent for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

# Try MCP imports
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    logger.warning("MCP SDK not available - agent will use direct calls")


class ImageAgent:
    """MCP Client/Agent for the Image Generator Server.
    
    Used in the app for image generation AND for hackathon demo.
    """
    
    def __init__(self, max_workers: int = 4):
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.max_workers = max_workers
        
    def _get_server_params(self) -> "StdioServerParameters":
        """Get MCP server parameters."""
        return StdioServerParameters(
            command=sys.executable,
            args=["-m", "mcp_servers.image_generator"],
            cwd=self.project_root,
            env={
                **os.environ,
                "PYTHONPATH": self.project_root,
            }
        )
    
    async def _call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Call a tool on the Image MCP server."""
        if not MCP_AVAILABLE:
            raise RuntimeError("MCP SDK not installed")
        
        async with stdio_client(self._get_server_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments=arguments)
                if result.content:
                    return result.content[0].text
                return ""
    
    async def _read_resource(self, uri: str) -> str:
        """Read a resource from the Image MCP server."""
        if not MCP_AVAILABLE:
            raise RuntimeError("MCP SDK not installed")
        
        async with stdio_client(self._get_server_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.read_resource(uri)
                if result.contents:
                    return result.contents[0].text
                return "{}"
    
    # =========================================================================
    # SINGLE IMAGE GENERATION (MCP Tools)
    # =========================================================================
    
    async def generate_portrait(
        self,
        name: str,
        role: str,
        personality: str,
        gender: str = "person",
        setting: str = ""
    ) -> str:
        """Generate a character portrait.
        
        Returns the file path to the generated image.
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
        """Generate a scene/location image.
        
        Returns the file path to the generated image.
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
        """Generate an atmospheric title card.
        
        Returns the file path to the generated image.
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
                path = await self.generate_portrait(
                    name=name,
                    role=char.get("role", ""),
                    personality=char.get("personality", ""),
                    gender=char.get("gender", "person"),
                    setting=char.get("setting", "")
                )
                logger.info(f"[ImageAgent] Generated portrait for {name}: {path}")
                return (name, path)
            except Exception as e:
                logger.error(f"[ImageAgent] Failed to generate portrait for {name}: {e}")
                return (name, None)
        
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
                logger.info(f"[ImageAgent] Generated scene for {location}: {path}")
                return (location, path)
            except Exception as e:
                logger.error(f"[ImageAgent] Failed to generate scene for {location}: {e}")
                return (location, None)
        
        tasks = [generate_one(scene) for scene in scenes]
        results = await asyncio.gather(*tasks)
        return {loc: path for loc, path in results if path}
    
    # =========================================================================
    # MCP RESOURCE QUERIES (for demo/hackathon)
    # =========================================================================
    
    async def get_cache_stats(self) -> Dict:
        """Get image cache statistics via MCP Resource."""
        result = await self._read_resource("images://stats")
        return json.loads(result)
    
    async def list_cached_images(self, limit: int = 10) -> List[Dict]:
        """List cached images via MCP Tool."""
        result = await self._call_tool("list_cached_images", {"limit": limit})
        data = json.loads(result)
        return data.get("images", [])
    
    async def get_available_styles(self) -> Dict:
        """Get available art styles via MCP Resource."""
        result = await self._read_resource("images://styles")
        return json.loads(result)
    
    # =========================================================================
    # MYSTERY-LEVEL GENERATION (for app integration)
    # =========================================================================
    
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
        
        # Prepare title card task
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
        agent = ImageAgent()
        return await agent.generate_portrait(name, role, personality, gender, setting)
    
    try:
        return asyncio.run(_run())
    except Exception as e:
        logger.error(f"[ImageAgent] Portrait generation failed: {e}")
        return None


def generate_scene_sync(
    location: str,
    setting: str,
    mood: str = "mysterious",
    context: str = ""
) -> Optional[str]:
    """Synchronous wrapper for single scene generation."""
    async def _run():
        agent = ImageAgent()
        return await agent.generate_scene(location, setting, mood, context)
    
    try:
        return asyncio.run(_run())
    except Exception as e:
        logger.error(f"[ImageAgent] Scene generation failed: {e}")
        return None


def generate_all_images_sync(mystery, setting: str) -> Dict[str, str]:
    """Synchronous wrapper for parallel image generation."""
    async def _run():
        agent = ImageAgent()
        return await agent.generate_all_mystery_images(mystery, setting)
    
    try:
        return asyncio.run(_run())
    except Exception as e:
        logger.error(f"[ImageAgent] Batch generation failed: {e}")
        return {}


# =============================================================================
# DEMO
# =============================================================================

async def demo():
    """Demo the Image Agent."""
    print("\n" + "=" * 60)
    print("🎨 IMAGE AGENT DEMO")
    print("=" * 60)
    print("\nThis demonstrates MCP tool composition for image generation.\n")
    
    if not MCP_AVAILABLE:
        print("❌ MCP SDK not installed. Run: pip install mcp")
        return
    
    agent = ImageAgent()
    
    # Check cache stats
    print("📊 Cache Statistics:")
    try:
        stats = await agent.get_cache_stats()
        print(f"   Total images: {stats.get('total_images', 0)}")
        print(f"   Cache size: {stats.get('total_size_mb', 0)} MB")
        print(f"   Location: {stats.get('cache_directory', 'unknown')}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # List cached images
    print("\n📁 Recent Cached Images:")
    try:
        images = await agent.list_cached_images(5)
        if images:
            for img in images:
                print(f"   • {img['key']} ({img['size_kb']}KB)")
        else:
            print("   (no cached images)")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Show available styles
    print("\n🎭 Available Art Styles:")
    try:
        styles = await agent.get_available_styles()
        for key, style in styles.get("styles", {}).items():
            print(f"   • {style['name']}: {style['description'][:50]}...")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n" + "=" * 60)
    print("💡 To generate an image, use:")
    print("   path = await agent.generate_portrait('Name', 'Role', 'Traits')")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(demo())

