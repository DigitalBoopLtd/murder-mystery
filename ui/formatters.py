"""UI formatting functions for displaying game information as HTML."""

import base64
import logging
import os
from typing import Dict, List, Optional, Tuple
from game.models import SuspectState

logger = logging.getLogger(__name__)


def _image_to_data_uri(image_path: str) -> Optional[str]:
    """Convert an image file to a base64 data URI for embedding in HTML.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        Data URI string or None if file doesn't exist/can't be read
    """
    if not image_path or not os.path.exists(image_path):
        return None
    
    try:
        # Determine MIME type from extension
        ext = os.path.splitext(image_path)[1].lower()
        mime_types = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
        }
        mime_type = mime_types.get(ext, 'image/png')
        
        with open(image_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
        
        return f"data:{mime_type};base64,{image_data}"
    except Exception as e:
        logger.warning("Failed to convert image to data URI: %s - %s", image_path, e)
        return None


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


def get_suspect_relationships(suspect_name: str) -> List[Tuple[str, str]]:
    """Get relationship labels for a suspect from RAG cross-references.
    
    Returns list of (other_suspect, relationship_type) tuples.
    Relationship types: "accused_by", "alibi_from", "mentioned_by"
    """
    try:
        from services.game_memory import get_game_memory
        memory = get_game_memory()
        
        if not memory.is_available:
            return []
        
        cross_refs = memory.search_cross_references(suspect_name, k=3)
        relationships = []
        
        for speaker, statement in cross_refs:
            statement_lower = statement.lower()
            
            # Detect relationship type from statement content
            if any(word in statement_lower for word in ["saw", "with", "together", "alibi"]):
                relationships.append((speaker, "alibi"))
            elif any(word in statement_lower for word in ["suspicious", "lying", "guilty", "killed", "murder"]):
                relationships.append((speaker, "accused"))
            else:
                relationships.append((speaker, "mentioned"))
        
        return relationships[:2]  # Limit to 2 most relevant
        
    except Exception as e:
        logger.debug("[FORMATTER] Could not get relationships: %s", e)
        return []


def format_suspects_list_html(
    mystery,
    talked_to: List[str] = None,
    loading: bool = False,
    suspect_states: Optional[Dict[str, SuspectState]] = None,
    portrait_images: Optional[Dict[str, str]] = None,
    layout: str = "row",
) -> str:
    """Format suspects list as HTML game cards with portraits.
    
    Args:
        mystery: The Mystery object with suspect data
        talked_to: List of suspect names that have been talked to
        loading: Whether to show loading state
        suspect_states: Dict mapping suspect name -> SuspectState (for trust/nervousness meters)
        portrait_images: Dict mapping suspect name -> portrait image path
        layout: "row" for horizontal layout (tabs), "column" for vertical layout (side panel)
    """
    if not mystery:
        if loading:
            return '<em style="color: var(--accent-gold);">🔍 Gathering suspect information...</em>'
        return "<em>Start a game to see suspects</em>"
    
    talked_to = talked_to or []
    suspect_states = suspect_states or {}
    portrait_images = portrait_images or {}
    
    # Debug logging for portrait images - use INFO level to ensure we see it
    logger.info("[FORMATTER] Rendering suspects list - portrait_images keys: %s", list(portrait_images.keys()))
    suspect_names = [s.name for s in mystery.suspects]
    logger.info("[FORMATTER] Suspect names from mystery: %s", suspect_names)
    for name, path in portrait_images.items():
        if not name.startswith('_'):  # Skip scene images
            exists = os.path.exists(path) if path else False
            logger.info("[FORMATTER] Portrait for '%s': path=%s, exists=%s", name, path, exists)
    
    cards = []
    
    for suspect in mystery.suspects:
        state = suspect_states.get(suspect.name)
        is_talked = suspect.name in talked_to
        card_class = "suspect-card talked-to" if is_talked else "suspect-card"
        
        # Portrait image or placeholder
        portrait_path = portrait_images.get(suspect.name) or getattr(suspect, 'portrait_path', None)
        data_uri = None
        if portrait_path:
            logger.info("[FORMATTER] Attempting to load portrait for %s from: %s", suspect.name, portrait_path)
            data_uri = _image_to_data_uri(portrait_path)
            if data_uri:
                logger.info("[FORMATTER] ✅ Successfully converted portrait for %s to data URI", suspect.name)
            else:
                logger.warning("[FORMATTER] ❌ Failed to convert portrait for %s (path: %s)", suspect.name, portrait_path)
        
        # Always render placeholder so card size is stable; overlay image when available
        placeholder_html = '<div class="suspect-card-portrait-placeholder">🎭</div>'
        img_html = f'<img src="{data_uri}" alt="{suspect.name}" />' if data_uri else ""
        
        # Status badges (simple chips in header)
        badges = []
        if is_talked:
            badges.append('<span class="suspect-card-badge talked">TALKED</span>')
        
        if state and state.contradictions_caught > 0:
            badges.append(f'<span class="suspect-card-badge contradiction">⚠️ {state.contradictions_caught}</span>')
        
        badges_html = f'<div class="suspect-card-status">{"".join(badges)}</div>' if badges else ''

        # Emotional state meters + relationships (only after you've talked to them)
        meters_html = ""
        contradiction_badge = ""
        relationship_labels = ""
        
        if is_talked and state:
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
            
            # Contradiction badge (larger, under name)
            if state.contradictions_caught > 0:
                contradiction_badge = f'''
                <span class="contradiction-badge" title="Caught in {state.contradictions_caught} contradiction(s)">
                    ⚠️ {state.contradictions_caught} contradiction{"s" if state.contradictions_caught > 1 else ""}
                </span>'''
            
            # Relationship labels from cross-references
            relationships = get_suspect_relationships(suspect.name)
            if relationships:
                labels = []
                for other, rel_type in relationships:
                    if rel_type == "accused":
                        labels.append(f'<span class="rel-label rel-accused" title="{other} accused them">🎯 {other}</span>')
                    elif rel_type == "alibi":
                        labels.append(f'<span class="rel-label rel-alibi" title="{other} provided alibi">🛡️ {other}</span>')
                    else:
                        labels.append(f'<span class="rel-label rel-mentioned" title="Mentioned by {other}">💬 {other}</span>')
                
                relationship_labels = f'''
                <div class="suspect-relationships">
                    <div class="suspect-relationships-label">Relationships</div>
                    {"".join(labels)}
                </div>'''
        
        # Motive snippet (always visible)
        motive_html = f'<div class="suspect-motive"><strong>Motive:</strong> <em>{suspect.secret}</em></div>'
        
        cards.append(f'''
        <div class="{card_class}" title="Click to see details">
            <div class="suspect-card-portrait">
                {placeholder_html}
                {img_html}
            </div>
            <div class="suspect-card-info">
                <div class="suspect-card-name">{suspect.name}{contradiction_badge}</div>
                <div class="suspect-card-role">{suspect.role}</div>
                {meters_html}
                {relationship_labels}
                {motive_html}
                {badges_html}
            </div>
        </div>''')
    
    # Use layout class to control card arrangement
    layout_class = "suspects-card-grid" if layout == "row" else "suspects-card-grid suspects-card-grid-column"
    return f'<div class="{layout_class}">{"".join(cards)}</div>'


def format_locations_html(
    mystery,
    searched: List[str],
    loading: bool = False,
    location_images: Optional[Dict[str, str]] = None,
) -> str:
    """Format locations as HTML, optionally with scene images.

    Args:
        mystery: The Mystery object with clues/locations
        searched: List of location names that have been searched
        loading: Whether to show loading state
        location_images: Dict mapping location name -> scene image path
    """
    if not mystery:
        if loading:
            return '<em style="color: var(--accent-gold);">🔍 Mapping the crime scene...</em>'
        return "<em>Start a game to see locations</em>"

    searched = searched or []
    location_images = location_images or {}

    # Collect unique locations from clues
    locations = list(set(clue.location for clue in mystery.clues))
    html_parts = []

    for loc in locations:
        cls = "location-item searched" if loc in searched else "location-item"
        check = '<span class="location-check"> ✓</span>' if loc in searched else ""

        # Try to find a scene image for this location
        img_path = location_images.get(loc)
        data_uri = _image_to_data_uri(img_path) if img_path else None

        if data_uri:
            html_parts.append(f'''
            <div class="location-card {cls}">
                <div class="location-image">
                    <img src="{data_uri}" alt="{loc}" />
                </div>
                <div class="location-info">
                    <div class="location-name">{loc}{check}</div>
                </div>
            </div>''')
        else:
            # Fallback to simple text row
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


def format_dashboard_html(
    mystery,
    clues_found: List[str] = None,
    suspects_talked_to: List[str] = None,
    searched_locations: List[str] = None,
    suspect_states: Optional[Dict[str, SuspectState]] = None,
    wrong_accusations: int = 0
) -> str:
    """Format the investigation dashboard with progress tracking and suspicion ranking.
    
    Shows at-a-glance:
    - Investigation progress (locations, suspects, clues)
    - Suspicion ranking based on contradictions and nervousness
    - Quick status/readiness indicator
    
    Args:
        mystery: The Mystery object
        clues_found: List of discovered clue descriptions
        suspects_talked_to: List of suspect names talked to
        searched_locations: List of searched location names
        suspect_states: Dict mapping suspect name -> SuspectState
        wrong_accusations: Number of wrong accusations made
    """
    if not mystery:
        return '''
        <div class="dashboard-empty">
            <div class="dashboard-icon">📊</div>
            <div>Start a mystery to track your investigation.</div>
        </div>'''
    
    clues_found = clues_found or []
    suspects_talked_to = suspects_talked_to or []
    searched_locations = searched_locations or []
    suspect_states = suspect_states or {}
    
    # Calculate progress percentages
    total_clues = len(mystery.clues)
    found_clues = len(clues_found)
    clue_pct = int((found_clues / total_clues) * 100) if total_clues > 0 else 0
    
    total_suspects = len(mystery.suspects)
    talked_suspects = len(suspects_talked_to)
    suspect_pct = int((talked_suspects / total_suspects) * 100) if total_suspects > 0 else 0
    
    available_locations = list(set(clue.location for clue in mystery.clues))
    total_locations = len(available_locations)
    searched_count = len(searched_locations)
    location_pct = int((searched_count / total_locations) * 100) if total_locations > 0 else 0
    
    # Calculate overall investigation score
    overall_pct = int((clue_pct * 0.35) + (suspect_pct * 0.30) + (location_pct * 0.20))
    
    # Count total contradictions
    total_contradictions = sum(
        state.contradictions_caught 
        for state in suspect_states.values()
    )
    # Bonus for contradictions (up to 15%)
    contradiction_bonus = min(total_contradictions * 5, 15)
    overall_pct = min(overall_pct + contradiction_bonus, 100)
    
    # Build progress bars HTML using CSS bars (Unicode blocks don't render well in VT323)
    def progress_bar(label: str, current, total, pct: int, icon: str, color: str) -> str:
        check = " ✓" if pct == 100 else ""
        return f'''
        <div class="dashboard-progress-row">
            <span class="dashboard-label">{icon} {label}</span>
            <div class="dashboard-bar-track">
                <div class="dashboard-bar-fill" style="width: {pct}%; background: {color};"></div>
            </div>
            <span class="dashboard-value">{current}/{total}{check}</span>
        </div>'''
    
    progress_html = f'''
    <div class="dashboard-section">
        <div class="dashboard-section-header">📊 INVESTIGATION PROGRESS</div>
        {progress_bar("Locations", searched_count, total_locations, location_pct, "📍", "#33ff33")}
        {progress_bar("Suspects", talked_suspects, total_suspects, suspect_pct, "🎭", "#33ff33")}
        {progress_bar("Clues", found_clues, total_clues, clue_pct, "🔎", "#33ff33")}
        {progress_bar("Contradictions", total_contradictions, "?", min(total_contradictions * 20, 100), "⚠️", "#ff6666" if total_contradictions > 0 else "#666")}
    </div>'''
    
    # Build suspicion ranking
    # Rank suspects by: contradictions (highest weight) + nervousness
    suspect_scores = []
    for suspect in mystery.suspects:
        state = suspect_states.get(suspect.name)
        if state and suspect.name in suspects_talked_to:
            # Score = contradictions * 40 + nervousness
            score = (state.contradictions_caught * 40) + state.nervousness
            suspect_scores.append({
                "name": suspect.name,
                "score": score,
                "contradictions": state.contradictions_caught,
                "nervousness": state.nervousness,
                "trust": state.trust
            })
        elif suspect.name in suspects_talked_to:
            # Talked to but no state recorded
            suspect_scores.append({
                "name": suspect.name,
                "score": 0,
                "contradictions": 0,
                "nervousness": 50,
                "trust": 50
            })
    
    # Sort by score descending
    suspect_scores.sort(key=lambda x: x["score"], reverse=True)
    
    suspicion_html = ""
    if suspect_scores:
        ranking_items = []
        for i, s in enumerate(suspect_scores[:5]):  # Top 5
            rank_icon = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"#{i+1}"
            
            # Build suspicion bar (visual indicator)
            suspicion_level = min(s["score"], 100)
            bar_color = "#ff4444" if suspicion_level > 70 else "#ffcc00" if suspicion_level > 40 else "#33ff33"
            
            # Contradiction indicator
            contradiction_text = f' <span class="suspicion-contradiction">⚠️ {s["contradictions"]}</span>' if s["contradictions"] > 0 else ""
            
            ranking_items.append(f'''
            <div class="suspicion-row">
                <span class="suspicion-rank">{rank_icon}</span>
                <span class="suspicion-name">{s["name"]}</span>
                <div class="suspicion-bar-track">
                    <div class="suspicion-bar-fill" style="width: {suspicion_level}%; background: {bar_color};"></div>
                </div>
                {contradiction_text}
            </div>''')
        
        suspicion_html = f'''
        <div class="dashboard-section">
            <div class="dashboard-section-header">🎯 SUSPICION RANKING</div>
            {"".join(ranking_items)}
        </div>'''
    else:
        suspicion_html = '''
        <div class="dashboard-section">
            <div class="dashboard-section-header">🎯 SUSPICION RANKING</div>
            <div class="dashboard-hint">Talk to suspects to build your suspicion list.</div>
        </div>'''
    
    # Readiness indicator
    accusations_remaining = 3 - wrong_accusations
    readiness_class = "ready-high" if overall_pct >= 70 else "ready-medium" if overall_pct >= 40 else "ready-low"
    
    if overall_pct >= 80:
        readiness_text = "Strong case — consider making an accusation"
        readiness_icon = "✅"
    elif overall_pct >= 50:
        readiness_text = "Building evidence — dig deeper"
        readiness_icon = "🔍"
    else:
        readiness_text = "Early stages — keep investigating"
        readiness_icon = "📋"
    
    status_html = f'''
    <div class="dashboard-status {readiness_class}">
        <div class="status-header">
            <span class="status-icon">{readiness_icon}</span>
            <span class="status-score">{overall_pct}% Complete</span>
        </div>
        <div class="status-text">{readiness_text}</div>
        <div class="status-accusations">
            <span>Accusations remaining:</span>
            {"".join(['<span class="pip"></span>' if i >= wrong_accusations else '<span class="pip used"></span>' for i in range(3)])}
        </div>
    </div>'''
    
    return f'''
    <div class="investigation-dashboard">
        {status_html}
        {progress_html}
        {suspicion_html}
    </div>'''

