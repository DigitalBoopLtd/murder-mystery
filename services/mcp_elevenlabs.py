"""MCP client for ElevenLabs voice service.

This module provides MCP-based access to ElevenLabs voices,
qualifying the app for the "MCP in Action" hackathon track.

Uses the official MCP SDK to communicate with the ElevenLabs MCP server.
Voice fetching works via MCP; TTS uses direct ElevenLabs API for reliability.
"""

import os
import asyncio
import json
import logging
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Check for MCP SDK availability
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    MCP_AVAILABLE = True
    logger.info("MCP SDK available")
except ImportError:
    MCP_AVAILABLE = False
    ClientSession = None
    StdioServerParameters = None
    stdio_client = None
    logger.warning("MCP SDK not installed. Run: pip install mcp")


@dataclass
class MCPVoice:
    """Voice data from ElevenLabs MCP server."""
    voice_id: str
    name: str
    gender: Optional[str] = None
    age: Optional[str] = None
    accent: Optional[str] = None
    description: Optional[str] = None
    use_case: Optional[str] = None
    category: Optional[str] = None
    language: Optional[str] = None
    descriptive: Optional[str] = None
    
    def __repr__(self):
        return f"MCPVoice({self.name}, {self.gender}, {self.age}, {self.accent})"


class ElevenLabsMCPClient:
    """MCP client for ElevenLabs voice service.
    
    Provides voice listing via MCP protocol.
    Falls back gracefully if MCP is not available.
    """
    
    def __init__(self):
        self._api_key = os.getenv("ELEVENLABS_API_KEY", "")
        
    @property
    def is_available(self) -> bool:
        """Check if MCP and API key are available."""
        return MCP_AVAILABLE and bool(self._api_key)
    
    def _get_server_params(self) -> Optional[Any]:
        """Get server parameters for the ElevenLabs MCP server.
        
        The ElevenLabs MCP server can be run via:
        - The installed console script 'mcp-elevenlabs' (preferred)
        - uvx mcp-elevenlabs (fallback, auto-installs)
        """
        if not MCP_AVAILABLE:
            return None
        
        import sys
        import shutil
        
        # Get the venv bin directory from the current Python executable
        venv_bin = os.path.dirname(sys.executable)
        mcp_script = os.path.join(venv_bin, "mcp-elevenlabs")
        
        # Check if the console script exists in the venv
        if os.path.isfile(mcp_script) and os.access(mcp_script, os.X_OK):
            logger.info("[MCP] Using venv console script: %s", mcp_script)
            return StdioServerParameters(
                command=mcp_script,
                args=[],
                env={
                    "ELEVENLABS_API_KEY": self._api_key,
                    "PATH": os.environ.get("PATH", ""),
                    **os.environ  # Pass through all environment variables
                }
            )
        
        # Check if mcp-elevenlabs is available on PATH
        if shutil.which("mcp-elevenlabs"):
            logger.info("[MCP] Using mcp-elevenlabs from PATH")
            return StdioServerParameters(
                command="mcp-elevenlabs",
                args=[],
                env={
                    "ELEVENLABS_API_KEY": self._api_key,
                    "PATH": os.environ.get("PATH", ""),
                    **os.environ
                }
            )
        
        # Fallback to uvx (which auto-installs if needed)
        logger.info("[MCP] mcp-elevenlabs not found, trying uvx...")
        return StdioServerParameters(
            command="uvx",
            args=["mcp-elevenlabs"],
            env={
                "ELEVENLABS_API_KEY": self._api_key,
                "PATH": os.environ.get("PATH", ""),
                **os.environ
            }
        )
    
    async def get_voices(self) -> Tuple[List[MCPVoice], str]:
        """Get available voices via MCP.
        
        Returns:
            Tuple of (voices list, status string)
            Status is one of: 'success', 'mcp_not_available', 'no_api_key', 
                              'timeout', 'failed', 'parse_error'
        """
        if not MCP_AVAILABLE:
            logger.warning("MCP SDK not available")
            return [], "mcp_not_available"
        
        if not self._api_key:
            logger.warning("ELEVENLABS_API_KEY not set")
            return [], "no_api_key"
        
        server_params = self._get_server_params()
        if not server_params:
            return [], "mcp_not_available"
        
        try:
            logger.info("[MCP] Connecting to ElevenLabs MCP server...")
            
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    # Initialize the session
                    await session.initialize()
                    logger.info("[MCP] Session initialized, calling get_voices tool...")
                    
                    # List available tools (for debugging)
                    tools = await session.list_tools()
                    tool_names = [t.name for t in tools.tools] if tools else []
                    logger.info("[MCP] Available tools: %s", tool_names)
                    
                    # Call the get_voices tool
                    # Note: Tool name might be different - check available tools
                    voice_tool = "get_voices"
                    if "get-voices" in tool_names:
                        voice_tool = "get-voices"
                    elif "list_voices" in tool_names:
                        voice_tool = "list_voices"
                    elif "list-voices" in tool_names:
                        voice_tool = "list-voices"
                    
                    logger.info("[MCP] Calling tool: %s", voice_tool)
                    result = await session.call_tool(voice_tool, arguments={})
                    
                    # Parse the response
                    voices = self._parse_voices_response(result)
                    
                    logger.info("[MCP] Successfully fetched %d voices", len(voices))
                    return voices, "success"
                    
        except asyncio.TimeoutError:
            logger.warning("[MCP] Voice fetch timed out")
            return [], "timeout"
        except FileNotFoundError as e:
            logger.error("[MCP] Python interpreter not found: %s", e)
            return [], "python_not_found"
        except Exception as e:
            logger.error("[MCP] Voice fetch failed: %s", e, exc_info=True)
            return [], "failed"
    
    def _parse_voices_response(self, result: Any) -> List[MCPVoice]:
        """Parse the MCP response into MCPVoice objects."""
        voices = []
        
        if not result:
            logger.warning("[MCP] Empty result from get_voices")
            return voices
        
        try:
            # MCP responses typically have a 'content' attribute with TextContent items
            if hasattr(result, 'content'):
                for item in result.content:
                    if hasattr(item, 'text'):
                        # Parse JSON from text content
                        try:
                            data = json.loads(item.text)
                            # Check if data is a list or dict before processing
                            if isinstance(data, list):
                                # Direct list of voices
                                for v in data:
                                    voices.append(self._create_voice_from_dict(v))
                            elif isinstance(data, dict):
                                # Dict with voices/data key
                                voices.extend(self._extract_voices_from_data(data))
                            else:
                                logger.warning("[MCP] Unexpected data type: %s", type(data))
                        except json.JSONDecodeError as e:
                            logger.warning("[MCP] Failed to parse voice JSON: %s", e)
                            # Try treating the text as a list directly
                            if isinstance(item.text, str) and item.text.startswith('['):
                                try:
                                    data = json.loads(item.text)
                                    if isinstance(data, list):
                                        for v in data:
                                            voices.append(self._create_voice_from_dict(v))
                                except:
                                    pass
            elif isinstance(result, dict):
                voices.extend(self._extract_voices_from_data(result))
            elif isinstance(result, list):
                for v in result:
                    voices.append(self._create_voice_from_dict(v))
                    
        except Exception as e:
            logger.error("[MCP] Error parsing voices response: %s", e, exc_info=True)
        
        return voices
    
    def _extract_voices_from_data(self, data: Dict) -> List[MCPVoice]:
        """Extract voices from a data dictionary."""
        voices = []
        
        # Handle different response formats
        voice_list = data.get('voices', data.get('data', []))
        if not isinstance(voice_list, list):
            voice_list = [data] if 'voice_id' in data else []
        
        for v in voice_list:
            voices.append(self._create_voice_from_dict(v))
        
        return voices
    
    def _create_voice_from_dict(self, v: Dict) -> MCPVoice:
        """Create an MCPVoice from a dictionary."""
        labels = v.get('labels', {})
        return MCPVoice(
            voice_id=v.get('voice_id', v.get('id', '')),
            name=v.get('name', 'Unknown'),
            gender=labels.get('gender'),
            age=labels.get('age'),
            accent=labels.get('accent'),
            description=labels.get('description', v.get('description')),
            use_case=labels.get('use_case'),
            category=v.get('category'),
            language=labels.get('language'),
            descriptive=labels.get('descriptive'),
        )


# ============================================================================
# Convenience functions for use elsewhere in the app
# ============================================================================

async def fetch_voices_via_mcp(timeout: float = 30.0) -> Tuple[List[MCPVoice], str]:
    """Fetch voices using ElevenLabs MCP server.
    
    Args:
        timeout: Maximum time to wait for response
        
    Returns:
        Tuple of (voices list, status string)
    """
    client = ElevenLabsMCPClient()
    
    if not client.is_available:
        return [], "mcp_not_available" if not MCP_AVAILABLE else "no_api_key"
    
    try:
        return await asyncio.wait_for(client.get_voices(), timeout=timeout)
    except asyncio.TimeoutError:
        return [], "timeout"


def check_mcp_availability() -> Dict[str, Any]:
    """Check MCP availability and return status info.
    
    Returns:
        Dict with:
        - available: bool
        - sdk_installed: bool
        - api_key_set: bool
        - message: str
    """
    api_key_set = bool(os.getenv("ELEVENLABS_API_KEY"))
    
    return {
        "available": MCP_AVAILABLE and api_key_set,
        "sdk_installed": MCP_AVAILABLE,
        "api_key_set": api_key_set,
        "message": (
            "MCP ready" if MCP_AVAILABLE and api_key_set
            else "MCP SDK not installed (pip install mcp)" if not MCP_AVAILABLE
            else "ELEVENLABS_API_KEY not set"
        )
    }

