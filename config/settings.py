"""Environment-level configuration for the murder mystery app.

This module isolates things that depend on the deployment environment
(API keys, model choices, feature flags) from pure game-domain logic.
"""

import os
from dataclasses import dataclass


@dataclass
class EnvironmentSettings:
    """Environment / deployment settings."""

    openai_api_key: str | None = None
    elevenlabs_api_key: str | None = None

    @classmethod
    def from_env(cls) -> "EnvironmentSettings":
        """Build settings from environment variables."""
        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            elevenlabs_api_key=os.getenv("ELEVENLABS_API_KEY"),
        )


def get_env_settings() -> EnvironmentSettings:
    """Convenience accessor for environment settings."""
    return EnvironmentSettings.from_env()


