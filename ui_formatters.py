"""UI formatting functions for displaying game information as HTML."""

from typing import List


def format_victim_scene_html(mystery) -> str:
    """Format victim and scene information as HTML."""
    if not mystery:
        return "<em>Start a game to see case details...</em>"
    
    return f"""
    <div style="margin-bottom: 12px;">
        <div style="font-weight: 700; margin-bottom: 8px; font-size: 1.1em; border-bottom: 1px solid var(--border-color); padding-bottom: 8px;">
            The Murder of {mystery.victim.name}
        </div>
        <div style="font-weight: 600; color: var(--accent-blue); margin-bottom: 8px;">Victim:</div>
        <div style="color: var(--text-primary); margin-bottom: 12px;">{mystery.victim.name}</div>
        <div style="font-weight: 600; color: var(--accent-blue); margin-bottom: 8px;">Scene:</div>
        <div style="color: var(--text-primary);">{mystery.setting}</div>
    </div>
    """


def format_clues_html(clues: List[str]) -> str:
    """Format found clues as HTML."""
    if not clues:
        return "<em>No clues discovered yet...</em>"

    return "".join(f'<div class="clue-item">• {clue}</div>' for clue in clues)


def format_suspects_list_html(mystery, talked_to: List[str] = None) -> str:
    """Format suspects list as HTML for quick reference."""
    if not mystery:
        return "<em>Start a game to see suspects</em>"
    
    talked_to = talked_to or []
    html_parts = []
    
    for suspect in mystery.suspects:
        talked_class = "location-item searched" if suspect.name in talked_to else "location-item"
        check = " ✓" if suspect.name in talked_to else ""
        html_parts.append(
            f'<div class="{talked_class}">'
            f'<strong>{suspect.name}</strong> - {suspect.role}{check}<br>'
            f'<em style="font-size: 0.9em; color: var(--text-secondary);">Motive: {suspect.secret}</em>'
            f'</div>'
        )
    
    return "".join(html_parts)


def format_locations_html(mystery, searched: List[str]) -> str:
    """Format locations as HTML."""
    if not mystery:
        return "<em>Start a game to see locations</em>"

    locations = list(set(clue.location for clue in mystery.clues))
    html_parts = []

    for loc in locations:
        cls = "location-item searched" if loc in searched else "location-item"
        check = " ✓" if loc in searched else ""
        html_parts.append(f'<div class="{cls}">{loc}{check}</div>')

    return "".join(html_parts)

