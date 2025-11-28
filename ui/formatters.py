"""UI formatting functions for displaying game information as HTML."""

from typing import Dict, List, Optional
from game.models import SuspectState


def format_victim_scene_html(mystery) -> str:
    """Format victim and scene information as HTML."""
    if not mystery:
        return "<em>Start a game to see case details...</em>"
    
    return f"""
    <div style="margin-bottom: 12px;">
        <div style="font-weight: 700; margin-bottom: 8px; font-size: 1.2em; padding-bottom: 8px;">
            The Murder of {mystery.victim.name}
        </div>
        <div style="font-weight: 600; color: var(--accent-blue); margin-bottom: 8px;">Victim:</div>
        <div style="color: var(--text-primary); margin-bottom: 12px;">{mystery.victim.name}</div>
        <div style="font-weight: 600; color: var(--accent-blue); margin-bottom: 8px;">Scene of the Crime:</div>
        <div style="color: var(--text-primary);">{mystery.setting}</div>
    </div>
    """


def format_clues_html(clues: List[str]) -> str:
    """Format found clues as HTML."""
    if not clues:
        return "<em>No clues discovered yet...</em>"

    return "".join(f'<div class="clue-item">• {clue}</div>' for clue in clues)


def format_suspects_list_html(
    mystery,
    talked_to: List[str] = None,
    loading: bool = False,
    suspect_states: Optional[Dict[str, SuspectState]] = None
) -> str:
    """Format suspects list as HTML for quick reference.
    
    Args:
        mystery: The Mystery object with suspect data
        talked_to: List of suspect names that have been talked to
        loading: Whether to show loading state
        suspect_states: Dict mapping suspect name -> SuspectState (for trust/nervousness meters)
    """
    if not mystery:
        if loading:
            return '<em style="color: var(--accent-gold);">🔍 Gathering suspect information...</em>'
        return "<em>Start a game to see suspects</em>"
    
    talked_to = talked_to or []
    suspect_states = suspect_states or {}
    html_parts = []
    
    for suspect in mystery.suspects:
        # Get emotional state for this suspect
        state = suspect_states.get(suspect.name)
        
        # Use a dedicated suspect item class so we can style progressive disclosure
        talked_class = "suspect-item searched" if suspect.name in talked_to else "suspect-item"
        check = '<span class="suspect-check"> ✓</span>' if suspect.name in talked_to else ""
        
        # Build emotional state meters (only show if talked to)
        meters_html = ""
        contradiction_badge = ""
        if suspect.name in talked_to and state:
            trust_pct = state.trust
            nervousness_pct = state.nervousness
            
            # Trust meter - green when high, yellow when medium, red when low
            trust_color = "#33ff33" if trust_pct > 60 else "#ffcc00" if trust_pct > 30 else "#ff4444"
            
            # Nervousness meter - inverse: green when low, red when high (nervous = bad for them)
            nervousness_color = "#33ff33" if nervousness_pct < 40 else "#ffcc00" if nervousness_pct < 70 else "#ff4444"
            
            meters_html = f'''
            <div class="suspect-meters">
                <div class="meter-row">
                    <span class="meter-label">TRUST</span>
                    <div class="meter-bar">
                        <div class="meter-fill" style="width: {trust_pct}%; background: {trust_color};"></div>
                    </div>
                    <span class="meter-value">{trust_pct}%</span>
                </div>
                <div class="meter-row">
                    <span class="meter-label">NERVE</span>
                    <div class="meter-bar">
                        <div class="meter-fill" style="width: {nervousness_pct}%; background: {nervousness_color};"></div>
                    </div>
                    <span class="meter-value">{nervousness_pct}%</span>
                </div>
            </div>'''
            
            # Contradiction badge
            if state.contradictions_caught > 0:
                contradiction_badge = f'''
                <div class="contradiction-badge" title="Caught in {state.contradictions_caught} contradiction(s)">
                    ⚠️ {state.contradictions_caught} contradiction{"s" if state.contradictions_caught > 1 else ""}
                </div>'''
        
        html_parts.append(
            f'<details class="{talked_class}">'
            f'<summary>'
            f'<div class="suspect-header">'
            f'<strong>{suspect.name}</strong>{check}{contradiction_badge}<br>'
            f'<span class="suspect-role-preview">{suspect.role}</span>'
            f'</div>'
            f'</summary>'
            f'<div class="suspect-details">'
            f'{meters_html}'
            f'<div class="suspect-motive"><strong>Motive:</strong> <em>{suspect.secret}</em></div>'
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


def format_detective_notebook_html(
    suspect_states: Optional[Dict[str, SuspectState]] = None,
    detected_contradictions: Optional[List[Dict]] = None
) -> str:
    """Format detective notebook with conversation timeline and contradictions.
    
    The notebook shows:
    - A timeline of all conversations across suspects
    - Detected contradictions highlighted
    - Pinned/important statements (future feature)
    
    Args:
        suspect_states: Dict mapping suspect name -> SuspectState
        detected_contradictions: List of detected contradiction records
    """
    suspect_states = suspect_states or {}
    detected_contradictions = detected_contradictions or []
    
    # Collect all conversations from all suspects into a unified timeline
    all_conversations = []
    for suspect_name, state in suspect_states.items():
        for conv in state.conversations:
            all_conversations.append({
                "suspect": suspect_name,
                "question": conv.get("question", ""),
                "answer": conv.get("answer", ""),
                "turn": conv.get("turn", 0)
            })
    
    # Sort by turn number
    all_conversations.sort(key=lambda x: x["turn"])
    
    if not all_conversations:
        return '''
        <div class="notebook-empty">
            <div class="notebook-icon">📓</div>
            <div>No interrogations recorded yet.</div>
            <div class="notebook-hint">Talk to suspects to fill your notebook.</div>
        </div>'''
    
    # Build contradiction lookup for quick reference
    contradiction_turns = set()
    for c in detected_contradictions:
        if "turn" in c:
            contradiction_turns.add(c["turn"])
    
    # Build timeline HTML
    timeline_items = []
    for conv in all_conversations:
        is_contradiction = conv["turn"] in contradiction_turns
        contradiction_class = " contradiction-entry" if is_contradiction else ""
        contradiction_icon = ' <span class="contradiction-icon" title="Contradiction detected!">⚠️</span>' if is_contradiction else ""
        
        # Truncate long answers for display
        answer = conv["answer"]
        if len(answer) > 150:
            answer = answer[:147] + "..."
        
        timeline_items.append(f'''
        <div class="notebook-entry{contradiction_class}">
            <div class="entry-header">
                <span class="entry-turn">#{conv["turn"] + 1}</span>
                <span class="entry-suspect">{conv["suspect"]}</span>
                {contradiction_icon}
            </div>
            <div class="entry-question">Q: "{conv["question"]}"</div>
            <div class="entry-answer">A: "{answer}"</div>
        </div>''')
    
    # Build contradictions section if any
    contradictions_html = ""
    if detected_contradictions:
        contradiction_items = []
        for c in detected_contradictions:
            contradiction_items.append(f'''
            <div class="contradiction-item">
                <div class="contradiction-suspect">⚠️ {c.get("suspect", "Unknown")}</div>
                <div class="contradiction-detail">{c.get("explanation", "Contradiction detected")}</div>
            </div>''')
        
        contradictions_html = f'''
        <div class="contradictions-section">
            <div class="section-header">🚨 CONTRADICTIONS FOUND</div>
            {"".join(contradiction_items)}
        </div>'''
    
    return f'''
    <div class="detective-notebook">
        {contradictions_html}
        <div class="timeline-section">
            <div class="section-header">📋 INTERROGATION LOG</div>
            <div class="timeline-entries">
                {"".join(timeline_items)}
            </div>
        </div>
    </div>'''

