"""UI components for displaying game information."""

from typing import Optional, List
from models import Mystery


def format_suspects_card(mystery: Optional[Mystery]) -> str:
    """Format suspects information for display card."""
    if not mystery:
        return "### 🎭 Suspects\n\n*Start a new game to see suspects*"

    lines = ["### 🎭 Suspects\n"]

    for suspect in mystery.suspects:
        lines.append(f"**{suspect.name}**")
        lines.append(f"- *{suspect.role}*")
        lines.append(f"- {suspect.personality}")
        lines.append("")

    return "\n".join(lines)


def format_objective_card(
    mystery: Optional[Mystery], wrong_accusations: int = 0
) -> str:
    """Format objective/rules for display card."""
    if not mystery:
        return "### 🎯 Objective\n\n*Start a new game to begin*"

    accusations_left = 3 - wrong_accusations
    status_emoji = (
        "🟢" if accusations_left == 3 else "🟡" if accusations_left == 2 else "🔴"
    )

    return f"""### 🎯 Objective

**Victim:** {mystery.victim.name}

**Your Mission:**
- Investigate the crime scene
- Interrogate suspects  
- Gather evidence
- Identify the murderer

**Accusations:** {status_emoji} {accusations_left} remaining

---
*Make your accusation with evidence when ready!*"""


def format_locations_card(
    mystery: Optional[Mystery], searched_locations: Optional[List[str]] = None
) -> str:
    """Format available locations for display card."""
    if not mystery:
        return "### 📍 Locations\n\n*Start a new game to explore*"

    searched = searched_locations or []

    # Extract unique locations from clues
    clue_locations = list(set(clue.location for clue in mystery.clues))

    lines = ["### 📍 Locations to Search\n"]

    for location in clue_locations:
        if location in searched:
            lines.append(f"- ~~{location}~~ ✓")
        else:
            lines.append(f"- {location}")

    lines.append("")
    lines.append("*Type 'search [location]' to investigate*")

    return "\n".join(lines)


def format_clues_card(clues_found: Optional[List[str]] = None) -> str:
    """Format discovered clues for display card."""
    if not clues_found:
        return "### 🔍 Clues Found\n\n*No clues discovered yet*"

    lines = ["### 🔍 Clues Found\n"]

    for i, clue in enumerate(clues_found, 1):
        lines.append(f"{i}. {clue}")

    return "\n".join(lines)


def format_game_status(
    mystery: Optional[Mystery], game_over: bool = False, won: bool = False
) -> str:
    """Format current game status."""
    if not mystery:
        return """### 🕵️ Murder Mystery

Type **"start"**, **"new game"**, **"begin"**, or **"play"** to begin!"""

    if game_over:
        if won:
            return """### 🎉 Case Solved!

**Congratulations!** You've identified the murderer and brought them to justice.

Type **"new game"** to play again!"""
        else:
            return f"""### 💀 Game Over

You've run out of accusations. The murderer was **{mystery.murderer}**.

Type **"new game"** to try again!"""

    return f"""### 🕵️ Active Investigation

**Case:** The murder of {mystery.victim.name}


**Setting:** {mystery.setting[:350]}{'...' if len(mystery.setting) > 350 else ''}"""


def get_all_card_content(
    mystery: Optional[Mystery],
    wrong_accusations: int = 0,
    clues_found: Optional[List[str]] = None,
    searched_locations: Optional[List[str]] = None,
    game_over: bool = False,
    won: bool = False,
) -> dict:
    """Get all card content as a dictionary.

    Returns:
        dict with keys: status, suspects, objective, locations, clues
    """
    return {
        "status": format_game_status(mystery, game_over, won),
        "suspects": format_suspects_card(mystery),
        "objective": format_objective_card(mystery, wrong_accusations),
        "locations": format_locations_card(mystery, searched_locations),
        "clues": format_clues_card(clues_found),
    }
