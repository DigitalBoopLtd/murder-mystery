"""MCP Client - Wrapper to call Murder Mystery MCP Server.

This module provides the same interface as the direct services,
but routes calls through the MCP server instead.

Toggle with: USE_MCP_SERVER=true in .env

Usage:
    from services.mcp_client import MCPGameClient
    
    client = MCPGameClient()
    await client.connect()
    
    # Same interface as direct calls
    result = await client.start_game(era="Victorian", tone="Noir")
    response = await client.interrogate_suspect("Marcus", "Where were you?")
"""

import asyncio
import json
import logging
import os
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Check if MCP mode is enabled
USE_MCP_SERVER = os.getenv("USE_MCP_SERVER", "false").lower() == "true"
MCP_SERVER_PATH = os.getenv("MCP_SERVER_PATH", "../murder-mystery-mcp/server.py")


@dataclass
class MCPResponse:
    """Response from MCP server."""
    success: bool
    content: str
    data: Optional[Dict] = None
    error: Optional[str] = None


class MCPGameClient:
    """Client for the Murder Mystery MCP Server.
    
    Provides the same interface as direct service calls,
    routing through MCP for testing/verification.
    """
    
    def __init__(self, server_path: Optional[str] = None):
        self.server_path = server_path or MCP_SERVER_PATH
        self._process: Optional[subprocess.Popen] = None
        self._reader = None
        self._writer = None
        self._session_id: Optional[str] = None
        self._connected = False
        self._request_id = 0
    
    @property
    def is_available(self) -> bool:
        """Check if MCP client is available."""
        return USE_MCP_SERVER and os.path.exists(self.server_path)
    
    async def connect(self) -> bool:
        """Start and connect to the MCP server."""
        if not self.is_available:
            logger.warning("[MCP Client] MCP mode not enabled or server not found")
            return False
        
        try:
            # Start the MCP server as a subprocess
            self._process = await asyncio.create_subprocess_exec(
                "python", self.server_path,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            self._reader = self._process.stdout
            self._writer = self._process.stdin
            
            # Send initialize request
            init_response = await self._send_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "murder-mystery-app", "version": "1.0.0"}
            })
            
            if init_response.success:
                self._connected = True
                logger.info("[MCP Client] Connected to MCP server")
                return True
            else:
                logger.error("[MCP Client] Failed to initialize: %s", init_response.error)
                return False
                
        except Exception as e:
            logger.exception("[MCP Client] Connection failed")
            return False
    
    async def disconnect(self):
        """Disconnect from the MCP server."""
        if self._process:
            self._process.terminate()
            await self._process.wait()
            self._process = None
        self._connected = False
        logger.info("[MCP Client] Disconnected")
    
    async def _send_request(self, method: str, params: Dict) -> MCPResponse:
        """Send a JSON-RPC request to the MCP server."""
        if not self._writer or not self._reader:
            return MCPResponse(success=False, content="", error="Not connected")
        
        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params
        }
        
        try:
            # Send request
            request_bytes = json.dumps(request).encode() + b"\n"
            self._writer.write(request_bytes)
            await self._writer.drain()
            
            # Read response
            response_line = await self._reader.readline()
            if not response_line:
                return MCPResponse(success=False, content="", error="No response")
            
            response = json.loads(response_line.decode())
            
            if "error" in response:
                return MCPResponse(
                    success=False,
                    content="",
                    error=response["error"].get("message", "Unknown error")
                )
            
            result = response.get("result", {})
            content = ""
            if isinstance(result, list) and len(result) > 0:
                content = result[0].get("text", "")
            elif isinstance(result, dict):
                content = result.get("content", [{}])[0].get("text", "")
            
            return MCPResponse(success=True, content=content, data=result)
            
        except Exception as e:
            logger.exception("[MCP Client] Request failed")
            return MCPResponse(success=False, content="", error=str(e))
    
    async def _call_tool(self, name: str, arguments: Dict) -> MCPResponse:
        """Call an MCP tool."""
        return await self._send_request("tools/call", {
            "name": name,
            "arguments": arguments
        })
    
    # =========================================================================
    # GAME API - Same interface as direct services
    # =========================================================================
    
    async def start_game(
        self,
        era: Optional[str] = None,
        tone: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> MCPResponse:
        """Start a new game via MCP server."""
        args = {}
        if era:
            args["era"] = era
        if tone:
            args["tone"] = tone
        if session_id:
            args["session_id"] = session_id
        
        response = await self._call_tool("start_game", args)
        
        # Extract session_id from response
        if response.success and "session_id" in response.content.lower():
            # Parse session ID from markdown response
            import re
            match = re.search(r"`([a-f0-9-]+)`", response.content)
            if match:
                self._session_id = match.group(1)
        
        return response
    
    async def get_game_state(self, session_id: Optional[str] = None) -> MCPResponse:
        """Get current game state via MCP server."""
        return await self._call_tool("get_game_state", {
            "session_id": session_id or self._session_id
        })
    
    async def interrogate_suspect(
        self,
        suspect_name: str,
        question: str,
        session_id: Optional[str] = None
    ) -> MCPResponse:
        """Interrogate a suspect via MCP server."""
        return await self._call_tool("interrogate_suspect", {
            "session_id": session_id or self._session_id,
            "suspect_name": suspect_name,
            "question": question
        })
    
    async def search_location(
        self,
        location: str,
        session_id: Optional[str] = None
    ) -> MCPResponse:
        """Search a location via MCP server."""
        return await self._call_tool("search_location", {
            "session_id": session_id or self._session_id,
            "location": location
        })
    
    async def make_accusation(
        self,
        suspect_name: str,
        evidence: str,
        session_id: Optional[str] = None
    ) -> MCPResponse:
        """Make an accusation via MCP server."""
        return await self._call_tool("make_accusation", {
            "session_id": session_id or self._session_id,
            "suspect_name": suspect_name,
            "evidence": evidence
        })
    
    async def search_memory(
        self,
        query: str,
        suspect_filter: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> MCPResponse:
        """Search memory via MCP server."""
        args = {
            "session_id": session_id or self._session_id,
            "query": query
        }
        if suspect_filter:
            args["suspect_filter"] = suspect_filter
        
        return await self._call_tool("search_memory", args)
    
    async def find_contradictions(
        self,
        suspect_name: str,
        session_id: Optional[str] = None
    ) -> MCPResponse:
        """Find contradictions via MCP server."""
        return await self._call_tool("find_contradictions", {
            "session_id": session_id or self._session_id,
            "suspect_name": suspect_name
        })
    
    async def get_timeline(self, session_id: Optional[str] = None) -> MCPResponse:
        """Get timeline via MCP server."""
        return await self._call_tool("get_timeline", {
            "session_id": session_id or self._session_id
        })
    
    # =========================================================================
    # IMAGE GENERATION
    # =========================================================================
    
    async def generate_scene_image(
        self,
        location: str,
        include_clue: bool = False,
        session_id: Optional[str] = None
    ) -> MCPResponse:
        """Generate scene image via MCP server."""
        return await self._call_tool("generate_scene_image", {
            "session_id": session_id or self._session_id,
            "location": location,
            "include_clue": include_clue
        })
    
    async def generate_portrait(
        self,
        suspect_name: str,
        session_id: Optional[str] = None
    ) -> MCPResponse:
        """Generate portrait via MCP server."""
        return await self._call_tool("generate_portrait", {
            "session_id": session_id or self._session_id,
            "suspect_name": suspect_name
        })
    
    async def generate_title_card(self, session_id: Optional[str] = None) -> MCPResponse:
        """Generate title card via MCP server."""
        return await self._call_tool("generate_title_card", {
            "session_id": session_id or self._session_id
        })


# =============================================================================
# SINGLETON CLIENT
# =============================================================================

_mcp_client: Optional[MCPGameClient] = None


def get_mcp_client() -> MCPGameClient:
    """Get or create the singleton MCP client."""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPGameClient()
    return _mcp_client


def is_mcp_mode() -> bool:
    """Check if MCP mode is enabled."""
    return USE_MCP_SERVER


async def ensure_mcp_connected() -> bool:
    """Ensure MCP client is connected."""
    if not USE_MCP_SERVER:
        return False
    
    client = get_mcp_client()
    if not client._connected:
        return await client.connect()
    return True

