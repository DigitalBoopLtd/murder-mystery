"""UI components for displaying game information cards."""
from typing import Optional
from models import Mystery


def format_suspects_card(mystery: Optional[Mystery]) -> str:
    """Format suspects information as a markdown card."""
    if not mystery:
        return """### 🎭 Suspects
        
*Start a new game to see suspects*"""
    
    suspects_md = "### 🎭 Suspects\n\n"
    for i, suspect in enumerate(mystery.suspects, 1):
        suspects_md += f"""**{i}. {suspect.name}**  
*{suspect.role}*  
_{suspect.personality}_

---
"""
    return suspects_md.strip()


def format_objective_card(mystery: Optional[Mystery], wrong_accusations: int = 0) -> str:
    """Format the objective/rules card."""
    if not mystery:
        return """### 🎯 Objective

*Start a new game to begin*"""
    
    remaining = 3 - wrong_accusations
    status_emoji = "🟢" if remaining == 3 else "🟡" if remaining == 2 else "🔴"
    
    return f"""### 🎯 Objective

**Solve the murder of {mystery.victim.name}**

- Interrogate suspects
- Search for clues  
- Make your accusation

---

**Accusations remaining:** {status_emoji} {remaining}/3

*Three wrong accusations = Game Over*"""


def format_locations_card(mystery: Optional[Mystery], searched_locations: list[str] = None) -> str:
    """Format the locations card with searchable areas."""
    if not mystery:
        return """### 📍 Locations

*Start a new game to explore*"""
    
    searched = searched_locations or []
    
    # Extract locations from clues
    clue_locations = list(set(clue.location for clue in mystery.clues))
    
    locations_md = "### 📍 Locations to Search\n\n"
    
    for loc in clue_locations:
        checked = "✅" if loc in searched else "⬜"
        locations_md += f"{checked} {loc}\n\n"
    
    return locations_md.strip()


def format_clues_card(clues_found: list[str] = None) -> str:
    """Format the clues found card."""
    clues = clues_found or []
    
    if not clues:
        return """### 🔍 Clues Found

*No clues discovered yet*

Search locations to find evidence!"""
    
    clues_md = "### 🔍 Clues Found\n\n"
    for i, clue in enumerate(clues, 1):
        clues_md += f"**{i}.** {clue}\n\n"
    
    return clues_md.strip()


def format_progress_card(
    mystery: Optional[Mystery],
    suspects_talked_to: list[str] = None,
    clues_found: list[str] = None
) -> str:
    """Format the investigation progress card."""
    if not mystery:
        return """### 📊 Progress

*Start a new game to track progress*"""
    
    talked = suspects_talked_to or []
    clues = clues_found or []
    
    total_suspects = len(mystery.suspects)
    total_clues = len(mystery.clues)
    
    suspects_progress = len(talked)
    clues_progress = len(clues)
    
    # Progress bars using unicode blocks
    def progress_bar(current, total, width=10):
        filled = int((current / total) * width) if total > 0 else 0
        empty = width - filled
        return "█" * filled + "░" * empty
    
    return f"""### 📊 Investigation Progress

**Suspects Interviewed**  
{progress_bar(suspects_progress, total_suspects)} {suspects_progress}/{total_suspects}

**Clues Discovered**  
{progress_bar(clues_progress, total_clues)} {clues_progress}/{total_clues}

---

*Interviewed:* {', '.join(talked) if talked else 'None yet'}"""


def format_victim_card(mystery: Optional[Mystery]) -> str:
    """Format the victim information card."""
    if not mystery:
        return """### 💀 The Victim

*Start a new game to see case details*"""
    
    return f"""### 💀 The Victim

**{mystery.victim.name}**

{mystery.victim.background}"""


def format_setting_card(mystery: Optional[Mystery]) -> str:
    """Format the setting/location card."""
    if not mystery:
        return """### 🏛️ Setting

*Start a new game to see the scene*"""
    
    return f"""### 🏛️ The Scene

{mystery.setting}"""


def get_all_card_data(
    mystery: Optional[Mystery],
    wrong_accusations: int = 0,
    suspects_talked_to: list[str] = None,
    clues_found: list[str] = None,
    searched_locations: list[str] = None
) -> dict:
    """Get all card data as a dictionary for easy updating."""
    return {
        "setting": format_setting_card(mystery),
        "victim": format_victim_card(mystery),
        "suspects": format_suspects_card(mystery),
        "objective": format_objective_card(mystery, wrong_accusations),
        "locations": format_locations_card(mystery, searched_locations),
        "clues": format_clues_card(clues_found),
        "progress": format_progress_card(mystery, suspects_talked_to, clues_found)
    }