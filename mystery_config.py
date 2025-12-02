"""Mystery configuration and validation for game setup options."""

import random
from typing import Optional, List
from dataclasses import dataclass, field


# ============================================================================
# PREDEFINED OPTIONS
# ============================================================================

# Setting categories with their associated settings
SETTING_CATEGORIES = {
    "Historical": [
        "a 1920s speakeasy during Prohibition",
        "a Hollywood movie studio in the 1950s",
        "a traveling circus in the 1930s",
        "a jazz club in 1960s New Orleans",
        "a vintage airplane during a transatlantic flight",
    ],
    "Modern": [
        "a luxury cruise ship in the middle of the ocean",
        "a remote ski lodge during a blizzard",
        "a Las Vegas casino on New Year's Eve",
        "a prestigious university during finals week",
        "a fashion week event in Paris",
        "a tech billionaire's private island",
        "an overnight train through Europe",
        "a haunted theater on opening night",
        "a royal palace during a state dinner",
        "an archaeological dig in Egypt",
        "a mountain monastery",
        "a luxury safari lodge in Africa",
    ],
    "Tech & Gaming": [
        "a high-tech research lab during a power outage",
        "a gaming convention during a major tournament",
        "a Silicon Valley startup's launch party",
        "a hacker conference in Las Vegas",
        "a retro computing museum during a special exhibit",
        "a VR gaming arcade in Tokyo",
        "a retro arcade bar during a high-score tournament",
        "a game development studio during crunch time",
        "a tech incubator during demo day",
        "a cyber security summit in Geneva",
    ],
    "Sci-Fi & Futuristic": [
        "a space station orbiting Mars",
        "a submarine research vessel",
        "a space mission control center during a critical launch",
        "a quantum computing facility during an experiment",
        "a cyberpunk-themed nightclub in Neo-Tokyo",
        "a robotics competition at MIT",
        "a blockchain conference in Singapore",
        "an AI research facility during a breakthrough announcement",
        "a sci-fi convention during a costume contest",
        "a secret underground data center",
        "a futuristic smart home during a system malfunction",
        "a virtual reality theme park",
    ],
}

# Flatten all settings for validation
ALL_SETTINGS = []
for category_settings in SETTING_CATEGORIES.values():
    ALL_SETTINGS.extend(category_settings)
ALL_SETTINGS = list(set(ALL_SETTINGS))  # Remove any duplicates

# Difficulty levels
DIFFICULTY_LEVELS = ["Easy", "Normal", "Hard"]

# Era/category options (matches SETTING_CATEGORIES keys + "Any")
ERA_OPTIONS = ["Any"] + list(SETTING_CATEGORIES.keys())

# Tone options
TONE_OPTIONS = [
    "Classic Noir",
    "Cozy Mystery",
    "Darkly Comedic",
    "Flirty Noir",
    "Gothic Romance",
    "Random",
]


# ============================================================================
# CONFIGURATION DATACLASS
# ============================================================================


@dataclass
class MysteryConfig:
    """Validated configuration for mystery generation."""

    setting: Optional[str] = None  # None means random
    era: str = "Any"
    difficulty: str = "Normal"
    tone: str = "Random"

    def get_setting_for_generation(self) -> str:
        """Get the setting to use for mystery generation.

        If a specific setting was chosen, return it.
        Otherwise, pick randomly based on era filter.
        """
        if self.setting and self.setting != "Random":
            return self.setting

        # Filter settings by era if specified
        if self.era and self.era != "Any":
            available_settings = SETTING_CATEGORIES.get(self.era, ALL_SETTINGS)
        else:
            available_settings = ALL_SETTINGS

        return random.choice(available_settings)

    def get_difficulty_modifier(self) -> dict:
        """Get difficulty-based modifiers for mystery generation.

        Returns a dict with settings that can be passed to the LLM prompt.
        """
        modifiers = {
            "Easy": {
                "clue_clarity": "clear and straightforward",
                "red_herrings": "minimal",
                "alibi_complexity": "simple",
                "hint_level": "generous hints when player is stuck",
            },
            "Normal": {
                "clue_clarity": "somewhat subtle but fair",
                "red_herrings": "one or two",
                "alibi_complexity": "moderately complex",
                "hint_level": "occasional nudges",
            },
            "Hard": {
                "clue_clarity": "subtle and requires careful analysis",
                "red_herrings": "multiple misleading clues",
                "alibi_complexity": "intricate with potential contradictions",
                "hint_level": "no assistance - player must deduce everything",
            },
        }
        return modifiers.get(self.difficulty, modifiers["Normal"])

    def get_rag_settings(self) -> dict:
        """Get RAG (retrieval) settings based on difficulty.
        
        Controls how much help the AI provides when searching memories.
        """
        settings = {
            "Easy": {
                "search_k": 7,  # More results returned
                "contradiction_threshold": 0.5,  # Easier to catch lies
                "hint_detail": "detailed",  # Rich hints
                "cross_ref_k": 5,  # More cross-references shown
            },
            "Normal": {
                "search_k": 5,
                "contradiction_threshold": 0.7,
                "hint_detail": "moderate",
                "cross_ref_k": 3,
            },
            "Hard": {
                "search_k": 3,  # Fewer results - must be more specific
                "contradiction_threshold": 0.85,  # Harder to auto-detect lies
                "hint_detail": "minimal",  # Vague hints only
                "cross_ref_k": 2,
            },
        }
        return settings.get(self.difficulty, settings["Normal"])

    def get_tone_instruction(self) -> str:
        """Get tone instruction for the LLM prompt."""
        tones = {
            "Classic Noir": (
                "Write in a classic noir detective style - cynical, atmospheric, "
                "with sharp dialogue and a sense of moral ambiguity. Think Raymond Chandler."
            ),
            "Cozy Mystery": (
                "Write in a cozy mystery style - warm, charming, with quirky characters "
                "and a lighter tone despite the murder. Think Agatha Christie's village mysteries."
            ),
            "Darkly Comedic": (
                "Write with dark humor and wit - clever wordplay, absurd situations, "
                "and characters who don't take themselves too seriously. Think Knives Out."
            ),
            "Cheeky Adult Comedy": (
                "Dial up bawdy but good‑natured adult comedy in the vein of classic "
                "point‑and‑click games: constant innuendo, double‑entendres, flirty mishaps, "
                "and self‑aware jokes at the protagonist's expense. Let characters clearly "
                "pursue dates, crushes, and romantic escapades, but keep anything beyond kissing "
                "or suggestive fade‑to‑black moments off‑screen and non‑graphic (no explicit sex or nudity)."
            ),
            "Flirty Noir": (
                "Make the atmosphere thick with flirtation: lingering looks, charged banter, "
                "close physical proximity, and a sense that everyone has at least one inappropriate crush. "
                "Lean hard on innuendo and implication, but do not describe explicit sexual acts or nudity; "
                "any intimacy beyond a kiss should be implied and quickly fade to black."
            ),
            "Gothic Romance": (
                "Emphasize brooding attraction, longing, and emotionally intense relationships "
                "in a gothic, atmospheric setting. Use sensual imagery around setting, clothing, "
                "and mood rather than bodies; any physical intimacy should be implied, stylized, "
                "and fade to black without explicit sexual detail."
            ),
            "Random": None,  # Let the LLM decide
        }
        return tones.get(self.tone)


# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================


def validate_setting(value: str) -> str:
    """Validate and normalize a setting value.

    Args:
        value: The setting value from the UI

    Returns:
        Validated setting string

    Raises:
        ValueError: If the setting is not in the allowed list
    """
    if not value or value == "Random":
        return None  # Will be randomly selected later

    if value not in ALL_SETTINGS:
        raise ValueError(
            f"Invalid setting: '{value}'. Must be one of the predefined options or 'Random'."
        )
    return value


def validate_era(value: str) -> str:
    """Validate era selection.

    Args:
        value: The era value from the UI

    Returns:
        Validated era string

    Raises:
        ValueError: If the era is not in the allowed list
    """
    if not value:
        return "Any"

    if value not in ERA_OPTIONS:
        raise ValueError(
            f"Invalid era: '{value}'. Must be one of: {', '.join(ERA_OPTIONS)}"
        )
    return value


def validate_difficulty(value: str) -> str:
    """Validate difficulty selection.

    Args:
        value: The difficulty value from the UI

    Returns:
        Validated difficulty string

    Raises:
        ValueError: If the difficulty is not in the allowed list
    """
    if not value:
        return "Normal"

    if value not in DIFFICULTY_LEVELS:
        raise ValueError(
            f"Invalid difficulty: '{value}'. Must be one of: {', '.join(DIFFICULTY_LEVELS)}"
        )
    return value


def validate_tone(value: str) -> str:
    """Validate tone selection.

    Args:
        value: The tone value from the UI

    Returns:
        Validated tone string

    Raises:
        ValueError: If the tone is not in the allowed list
    """
    if not value:
        return "Random"

    if value not in TONE_OPTIONS:
        raise ValueError(
            f"Invalid tone: '{value}'. Must be one of: {', '.join(TONE_OPTIONS)}"
        )
    return value


def create_validated_config(
    setting: str = "Random",
    era: str = "Any",
    difficulty: str = "Normal",
    tone: str = "Random",
) -> MysteryConfig:
    """Create a validated MysteryConfig from user inputs.

    All inputs are validated before creating the config object.

    Args:
        setting: Mystery setting/location
        era: Era category filter
        difficulty: Game difficulty level
        tone: Narrative tone

    Returns:
        Validated MysteryConfig object

    Raises:
        ValueError: If any input fails validation
    """
    return MysteryConfig(
        setting=validate_setting(setting),
        era=validate_era(era),
        difficulty=validate_difficulty(difficulty),
        tone=validate_tone(tone),
    )


def get_settings_for_era(era: str) -> List[str]:
    """Get available settings for a given era.

    Args:
        era: Era category name

    Returns:
        List of setting strings for that era
    """
    if era == "Any" or era not in SETTING_CATEGORIES:
        return ALL_SETTINGS
    return SETTING_CATEGORIES[era]

