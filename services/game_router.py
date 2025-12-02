"""Game Router - Switches between direct calls and MCP server mode.

This module provides a unified interface that can route game operations
to either:
1. Direct mode - Calls services directly (current behavior)
2. MCP mode - Calls the MCP server (for testing/verification)

Toggle with USE_MCP_SERVER=true in .env

Usage:
    from services.game_router import GameRouter
    
    router = GameRouter(session_id)
    
    # These calls work the same regardless of mode
    result = await router.start_game(era="Victorian")
    response = await router.interrogate_suspect("Marcus", "Where were you?")
"""

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Mode toggle
USE_MCP_SERVER = os.getenv("USE_MCP_SERVER", "false").lower() == "true"


@dataclass
class GameResult:
    """Unified result from either direct or MCP calls."""
    success: bool
    text: str  # Main response text
    speaker: Optional[str] = None  # Speaker name (for interrogation)
    audio_path: Optional[str] = None
    image_url: Optional[str] = None
    data: Optional[Dict] = None
    error: Optional[str] = None


class GameRouter:
    """Routes game operations to either direct services or MCP server.
    
    This allows testing the MCP server produces identical results
    to the direct implementation.
    """
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self._mode = "mcp" if USE_MCP_SERVER else "direct"
        self._mcp_client = None
        
        logger.info("[ROUTER] Mode: %s", self._mode)
    
    @property
    def is_mcp_mode(self) -> bool:
        return self._mode == "mcp"
    
    async def _get_mcp_client(self):
        """Lazy-load MCP client."""
        if self._mcp_client is None:
            from services.mcp_client import get_mcp_client, ensure_mcp_connected
            self._mcp_client = get_mcp_client()
            await ensure_mcp_connected()
        return self._mcp_client
    
    # =========================================================================
    # GAME OPERATIONS
    # =========================================================================
    
    async def start_game(
        self,
        era: Optional[str] = None,
        tone: Optional[str] = None
    ) -> GameResult:
        """Start a new game."""
        if self.is_mcp_mode:
            return await self._start_game_mcp(era, tone)
        else:
            return await self._start_game_direct(era, tone)
    
    async def _start_game_mcp(self, era, tone) -> GameResult:
        """Start game via MCP server."""
        client = await self._get_mcp_client()
        response = await client.start_game(
            era=era, tone=tone, session_id=self.session_id
        )
        return GameResult(
            success=response.success,
            text=response.content,
            data=response.data,
            error=response.error
        )
    
    async def _start_game_direct(self, era, tone) -> GameResult:
        """Start game via direct calls."""
        from game.startup import start_new_game
        
        try:
            result = start_new_game(self.session_id)
            # start_new_game returns a tuple of UI values
            # The welcome text is typically the first or second item
            text = result[0] if isinstance(result, tuple) else str(result)
            return GameResult(success=True, text=text)
        except Exception as e:
            logger.exception("[ROUTER] Direct start_game failed")
            return GameResult(success=False, text="", error=str(e))
    
    async def interrogate_suspect(
        self,
        suspect_name: str,
        question: str
    ) -> GameResult:
        """Interrogate a suspect."""
        if self.is_mcp_mode:
            return await self._interrogate_mcp(suspect_name, question)
        else:
            return await self._interrogate_direct(suspect_name, question)
    
    async def _interrogate_mcp(self, suspect_name, question) -> GameResult:
        """Interrogate via MCP server."""
        client = await self._get_mcp_client()
        response = await client.interrogate_suspect(
            suspect_name=suspect_name,
            question=question,
            session_id=self.session_id
        )
        
        # Parse speaker from response
        speaker = None
        if "# 🗣️" in response.content:
            # Extract speaker name from markdown header
            import re
            match = re.search(r"# 🗣️ (.+?)\n", response.content)
            if match:
                speaker = match.group(1)
        
        return GameResult(
            success=response.success,
            text=response.content,
            speaker=speaker,
            data=response.data,
            error=response.error
        )
    
    async def _interrogate_direct(self, suspect_name, question) -> GameResult:
        """Interrogate via direct tool call."""
        from game.tools import interrogate_suspect
        
        try:
            # The tool is synchronous, wrap it
            loop = asyncio.get_event_loop()
            text = await loop.run_in_executor(
                None,
                lambda: interrogate_suspect.invoke({
                    "suspect_name": suspect_name,
                    "player_question": question,
                    "emotional_context": ""
                })
            )
            
            # Get speaker from tool output store
            from game.state_manager import get_tool_output_store
            store = get_tool_output_store()
            speaker = store.interrogation.suspect_name if store.interrogation else None
            audio_path = store.audio_path
            
            return GameResult(
                success=True,
                text=text,
                speaker=speaker,
                audio_path=audio_path
            )
        except Exception as e:
            logger.exception("[ROUTER] Direct interrogate failed")
            return GameResult(success=False, text="", error=str(e))
    
    async def search_location(self, location: str) -> GameResult:
        """Search a location."""
        if self.is_mcp_mode:
            return await self._search_location_mcp(location)
        else:
            return await self._search_location_direct(location)
    
    async def _search_location_mcp(self, location) -> GameResult:
        """Search location via MCP server."""
        client = await self._get_mcp_client()
        response = await client.search_location(
            location=location,
            session_id=self.session_id
        )
        return GameResult(
            success=response.success,
            text=response.content,
            data=response.data,
            error=response.error
        )
    
    async def _search_location_direct(self, location) -> GameResult:
        """Search location via direct tool call."""
        from game.tools import describe_scene_for_image
        
        try:
            loop = asyncio.get_event_loop()
            text = await loop.run_in_executor(
                None,
                lambda: describe_scene_for_image.invoke({
                    "location_name": location
                })
            )
            
            return GameResult(success=True, text=text)
        except Exception as e:
            logger.exception("[ROUTER] Direct search_location failed")
            return GameResult(success=False, text="", error=str(e))
    
    async def make_accusation(
        self,
        suspect_name: str,
        evidence: str
    ) -> GameResult:
        """Make an accusation."""
        if self.is_mcp_mode:
            return await self._make_accusation_mcp(suspect_name, evidence)
        else:
            return await self._make_accusation_direct(suspect_name, evidence)
    
    async def _make_accusation_mcp(self, suspect_name, evidence) -> GameResult:
        """Make accusation via MCP server."""
        client = await self._get_mcp_client()
        response = await client.make_accusation(
            suspect_name=suspect_name,
            evidence=evidence,
            session_id=self.session_id
        )
        return GameResult(
            success=response.success,
            text=response.content,
            data=response.data,
            error=response.error
        )
    
    async def _make_accusation_direct(self, suspect_name, evidence) -> GameResult:
        """Make accusation via direct tool call."""
        from game.tools import make_accusation
        
        try:
            loop = asyncio.get_event_loop()
            text = await loop.run_in_executor(
                None,
                lambda: make_accusation.invoke({
                    "suspect_name": suspect_name,
                    "evidence_summary": evidence
                })
            )
            
            return GameResult(success=True, text=text)
        except Exception as e:
            logger.exception("[ROUTER] Direct make_accusation failed")
            return GameResult(success=False, text="", error=str(e))
    
    async def search_memory(
        self,
        query: str,
        suspect_filter: Optional[str] = None
    ) -> GameResult:
        """Search game memory."""
        if self.is_mcp_mode:
            client = await self._get_mcp_client()
            response = await client.search_memory(
                query=query,
                suspect_filter=suspect_filter,
                session_id=self.session_id
            )
            return GameResult(
                success=response.success,
                text=response.content,
                data=response.data,
                error=response.error
            )
        else:
            from services.game_memory import get_game_memory
            memory = get_game_memory()
            
            if suspect_filter:
                results = memory.search_by_suspect(suspect_filter, query)
            else:
                results = memory.search(query)
            
            # Format results
            text = "\n".join([
                f"- {r[0]}" for r in results
            ]) if results else "No results found."
            
            return GameResult(success=True, text=text, data={"results": results})
    
    async def get_timeline(self) -> GameResult:
        """Get investigation timeline."""
        if self.is_mcp_mode:
            client = await self._get_mcp_client()
            response = await client.get_timeline(session_id=self.session_id)
            return GameResult(
                success=response.success,
                text=response.content,
                data=response.data,
                error=response.error
            )
        else:
            from game.state_manager import get_or_create_state
            state = get_or_create_state(self.session_id)
            timeline = state.discovered_timeline
            
            return GameResult(
                success=True,
                text=f"Timeline has {len(timeline)} events",
                data={"timeline": timeline}
            )
    
    # =========================================================================
    # IMAGE GENERATION
    # =========================================================================
    
    async def generate_scene_image(
        self,
        location: str,
        include_clue: bool = False
    ) -> GameResult:
        """Generate scene image."""
        if self.is_mcp_mode:
            client = await self._get_mcp_client()
            response = await client.generate_scene_image(
                location=location,
                include_clue=include_clue,
                session_id=self.session_id
            )
            
            # Extract image URL from markdown
            image_url = None
            if "![" in response.content:
                import re
                match = re.search(r"\!\[.*?\]\((.*?)\)", response.content)
                if match:
                    image_url = match.group(1)
            
            return GameResult(
                success=response.success,
                text=response.content,
                image_url=image_url,
                error=response.error
            )
        else:
            from services.image_service import generate_scene_on_demand
            
            try:
                from game.state_manager import get_or_create_state
                state = get_or_create_state(self.session_id)
                
                image_path = generate_scene_on_demand(
                    location, state.mystery.setting if state.mystery else ""
                )
                
                return GameResult(
                    success=True,
                    text=f"Generated scene for {location}",
                    image_url=image_path
                )
            except Exception as e:
                logger.exception("[ROUTER] Direct scene generation failed")
                return GameResult(success=False, text="", error=str(e))
    
    async def generate_portrait(self, suspect_name: str) -> GameResult:
        """Generate suspect portrait."""
        if self.is_mcp_mode:
            client = await self._get_mcp_client()
            response = await client.generate_portrait(
                suspect_name=suspect_name,
                session_id=self.session_id
            )
            
            # Extract image URL
            image_url = None
            if "![" in response.content:
                import re
                match = re.search(r"\!\[.*?\]\((.*?)\)", response.content)
                if match:
                    image_url = match.group(1)
            
            return GameResult(
                success=response.success,
                text=response.content,
                image_url=image_url,
                error=response.error
            )
        else:
            from services.image_service import generate_portrait_on_demand
            from game.state_manager import get_or_create_state
            
            try:
                state = get_or_create_state(self.session_id)
                suspect = None
                if state.mystery:
                    for s in state.mystery.suspects:
                        if s.name.lower() == suspect_name.lower():
                            suspect = s
                            break
                
                if suspect:
                    image_path = generate_portrait_on_demand(
                        suspect, state.mystery.setting
                    )
                    return GameResult(
                        success=True,
                        text=f"Generated portrait for {suspect_name}",
                        image_url=image_path
                    )
                else:
                    return GameResult(
                        success=False,
                        text="",
                        error=f"Suspect {suspect_name} not found"
                    )
            except Exception as e:
                logger.exception("[ROUTER] Direct portrait generation failed")
                return GameResult(success=False, text="", error=str(e))


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_current_mode() -> str:
    """Get the current routing mode."""
    return "MCP Server" if USE_MCP_SERVER else "Direct"


def create_router(session_id: str) -> GameRouter:
    """Create a game router for a session."""
    return GameRouter(session_id)

