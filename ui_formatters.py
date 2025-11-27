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


def format_suspects_list_html(mystery, talked_to: List[str] = None, loading: bool = False) -> str:
    """Format suspects list as HTML for quick reference."""
    if not mystery:
        if loading:
            return '<em style="color: var(--accent-gold);">🔍 Gathering suspect information...</em>'
        return "<em>Start a game to see suspects</em>"
    
    talked_to = talked_to or []
    html_parts = []
    
    for suspect in mystery.suspects:
        # Use a dedicated suspect item class so we can style progressive disclosure
        talked_class = "suspect-item searched" if suspect.name in talked_to else "suspect-item"
        check = '<span class="suspect-check"> ✓</span>' if suspect.name in talked_to else ""
        html_parts.append(
            f'<details class="{talked_class}">'
            f'<summary>'
            f'<div class="suspect-header">'
            f'<strong>{suspect.name}</strong>{check}<br>'
            f'<span class="suspect-role-preview">{suspect.role}</span>'
            f'</div>'
            f'</summary>'
            f'<div class="suspect-details">'
            f'<div class="suspect-motive">Motive: <em>{suspect.secret}</em></div>'
            f'</div>'
            f'</details>'
        )
    
    return "".join(html_parts)


def format_locations_html(mystery, searched: List[str], loading: bool = False) -> str:
    """Format locations as HTML."""
    if not mystery:
        if loading:
            return '<em style="color: var(--accent-gold);">🔍 Mapping the crime scene...</em>'
        return "<em>Start a game to see locations</em>"

    locations = list(set(clue.location for clue in mystery.clues))
    html_parts = []

    for loc in locations:
        cls = "location-item searched" if loc in searched else "location-item"
        check = '<span class="location-check"> ✓</span>' if loc in searched else ""
        html_parts.append(f'<div class="{cls}">{loc}{check}</div>')

    return "".join(html_parts)

