"""API Key Management - Secure handling of API keys.

Provides a unified interface for API keys that:
1. Uses environment variables for local development
2. Accepts user-provided keys for deployed version
3. Never persists keys to disk
4. Never logs or exposes keys
"""

import os
import logging
from typing import Optional, Dict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# =============================================================================
# API KEY STORAGE (Session-scoped, in-memory only)
# =============================================================================

# Session -> API Keys mapping (never persisted)
_session_keys: Dict[str, "APIKeys"] = {}


@dataclass
class APIKeys:
    """Container for API keys - stored only in memory."""
    openai_key: Optional[str] = None
    elevenlabs_key: Optional[str] = None
    huggingface_key: Optional[str] = None
    
    # Track which keys were user-provided vs env
    _user_provided: Dict[str, bool] = field(default_factory=dict)
    
    def has_openai(self) -> bool:
        return bool(self.openai_key)
    
    def has_elevenlabs(self) -> bool:
        return bool(self.elevenlabs_key)
    
    def has_huggingface(self) -> bool:
        return bool(self.huggingface_key)
    
    def is_user_provided(self, key_name: str) -> bool:
        return self._user_provided.get(key_name, False)
    
    def get_status(self) -> Dict[str, str]:
        """Get status of each key (for UI display)."""
        return {
            "openai": self._get_key_status("openai", self.openai_key),
            "elevenlabs": self._get_key_status("elevenlabs", self.elevenlabs_key),
            "huggingface": self._get_key_status("huggingface", self.huggingface_key),
        }
    
    def _get_key_status(self, name: str, value: Optional[str]) -> str:
        if not value:
            return "❌ Not set"
        if self._user_provided.get(name):
            return "✅ User key"
        return "✅ Environment"


def get_session_keys(session_id: str) -> APIKeys:
    """Get or create API keys for a session.
    
    First checks for user-provided keys in the session.
    Falls back to environment variables.
    """
    if session_id not in _session_keys:
        _session_keys[session_id] = _create_keys_from_env()
    return _session_keys[session_id]


def set_session_key(
    session_id: str, 
    key_name: str, 
    key_value: str,
    validate: bool = True
) -> tuple[bool, str]:
    """Set an API key for a session.
    
    Args:
        session_id: The session ID
        key_name: One of 'openai', 'elevenlabs', 'fal'
        key_value: The API key value (will be stripped)
        validate: Whether to validate the key format
        
    Returns:
        Tuple of (success, message)
    """
    if session_id not in _session_keys:
        _session_keys[session_id] = _create_keys_from_env()
    
    keys = _session_keys[session_id]
    key_value = key_value.strip() if key_value else ""
    
    # Validate key format (basic checks)
    if validate and key_value:
        valid, msg = _validate_key_format(key_name, key_value)
        if not valid:
            return False, msg
    
    # Set the key
    if key_name == "openai":
        keys.openai_key = key_value if key_value else None
        keys._user_provided["openai"] = bool(key_value)
        # Update environment for this session's processes
        if key_value:
            os.environ["OPENAI_API_KEY"] = key_value
        logger.info("OpenAI key %s for session %s", 
                   "set" if key_value else "cleared", 
                   session_id[:8])
    elif key_name == "elevenlabs":
        keys.elevenlabs_key = key_value if key_value else None
        keys._user_provided["elevenlabs"] = bool(key_value)
        if key_value:
            os.environ["ELEVENLABS_API_KEY"] = key_value
        logger.info("ElevenLabs key %s for session %s",
                   "set" if key_value else "cleared",
                   session_id[:8])
    elif key_name == "huggingface":
        keys.huggingface_key = key_value if key_value else None
        keys._user_provided["huggingface"] = bool(key_value)
        if key_value:
            os.environ["HF_TOKEN"] = key_value
        logger.info("HuggingFace key %s for session %s",
                   "set" if key_value else "cleared",
                   session_id[:8])
    else:
        return False, f"Unknown key type: {key_name}"
    
    return True, f"✅ {key_name.title()} key saved"


def clear_session_keys(session_id: str):
    """Clear all keys for a session (call on session end)."""
    if session_id in _session_keys:
        del _session_keys[session_id]
        logger.info("Cleared keys for session %s", session_id[:8])


def _create_keys_from_env() -> APIKeys:
    """Create APIKeys from environment variables."""
    keys = APIKeys(
        openai_key=os.getenv("OPENAI_API_KEY"),
        elevenlabs_key=os.getenv("ELEVENLABS_API_KEY"),
        huggingface_key=os.getenv("HF_TOKEN"),
    )
    # Mark all as not user-provided (from env)
    keys._user_provided = {
        "openai": False,
        "elevenlabs": False,
        "huggingface": False,
    }
    return keys


def _validate_key_format(key_name: str, key_value: str) -> tuple[bool, str]:
    """Basic validation of key format."""
    if not key_value:
        return True, ""  # Empty is OK (means use env)
    
    if key_name == "openai":
        # OpenAI keys start with sk-
        if not key_value.startswith("sk-"):
            return False, "OpenAI keys should start with 'sk-'"
        if len(key_value) < 20:
            return False, "OpenAI key seems too short"
    
    elif key_name == "elevenlabs":
        # ElevenLabs keys are typically 32 chars hex
        if len(key_value) < 20:
            return False, "ElevenLabs key seems too short"
    
    elif key_name == "huggingface":
        # HuggingFace tokens start with hf_
        if not key_value.startswith("hf_"):
            return False, "HuggingFace tokens should start with 'hf_'"
        if len(key_value) < 20:
            return False, "HuggingFace token seems too short"
    
    return True, ""


# =============================================================================
# HELPER FUNCTIONS FOR SERVICES
# =============================================================================

def get_openai_key(session_id: Optional[str] = None) -> Optional[str]:
    """Get OpenAI API key, preferring session key over env."""
    if session_id:
        keys = get_session_keys(session_id)
        if keys.openai_key:
            return keys.openai_key
    return os.getenv("OPENAI_API_KEY")


def get_elevenlabs_key(session_id: Optional[str] = None) -> Optional[str]:
    """Get ElevenLabs API key, preferring session key over env."""
    if session_id:
        keys = get_session_keys(session_id)
        if keys.elevenlabs_key:
            return keys.elevenlabs_key
    return os.getenv("ELEVENLABS_API_KEY")


def get_huggingface_key(session_id: Optional[str] = None) -> Optional[str]:
    """Get HuggingFace token, preferring session key over env."""
    if session_id:
        keys = get_session_keys(session_id)
        if keys.huggingface_key:
            return keys.huggingface_key
    return os.getenv("HF_TOKEN")


def has_required_keys(session_id: Optional[str] = None) -> tuple[bool, list[str]]:
    """Check if all required keys are available.
    
    All three keys (OpenAI, ElevenLabs, HuggingFace) are required.
    
    Returns:
        Tuple of (all_present, list of missing key names)
    """
    missing = []
    
    if not get_openai_key(session_id):
        missing.append("OpenAI")
    
    if not get_elevenlabs_key(session_id):
        missing.append("ElevenLabs")
    
    if not get_huggingface_key(session_id):
        missing.append("HuggingFace")
    
    return len(missing) == 0, missing

