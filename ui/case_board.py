"""Case Board - Visual conspiracy board that builds as you investigate.

Creates a Plotly graph showing suspects, clues, and connections
discovered during the investigation.
"""

import logging
from typing import Dict, List, Optional, Any
import textwrap

logger = logging.getLogger(__name__)

# Check if plotly and networkx are available
try:
    import networkx as nx
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    logger.warning("plotly or networkx not available - case board will be disabled")


# =============================================================================
# ICONS FOR DIFFERENT NODE TYPES
# =============================================================================

ICONS = {
    "murderer": "🎯",      # Target (only shown when accused correctly)
    "suspect": "👤",       # Person silhouette
    "suspect_talked": "🗣️", # Person who's been interrogated
    "suspect_suspicious": "⚠️", # Suspect with contradictions
    "victim": "💀",        # The victim
    "crime_scene": "🔴",   # Crime scene / murder location
    "clue_weapon": "🔪",   # Weapon clue
    "clue_physical": "👣", # Physical evidence
    "clue_document": "📜", # Document/paper clue
    "clue_generic": "🔎",  # Generic clue
    "location": "📍",      # Location (not searched)
    "location_searched": "✅", # Searched location
    "location_alibi": "🏠", # Location where suspect claims to have been
    "motive": "💰",        # Motive
    "alibi": "🕐",         # Alibi/timeline
    "contradiction": "❌", # Contradiction found
    "witness": "👁️",       # Witness statement
}

# Colors for different node types
COLORS = {
    "suspect": "#4a90d9",      # Blue
    "suspect_talked": "#2ecc71", # Green
    "suspect_suspicious": "#e74c3c", # Red
    "victim": "#9b59b6",       # Purple
    "crime_scene": "#e74c3c",  # Red - crime scene
    "clue": "#f39c12",         # Orange
    "location": "#1abc9c",     # Teal
    "location_searched": "#27ae60", # Green - searched
    "location_alibi": "#3498db", # Light blue - alibi location
    "alibi": "#3498db",        # Light blue
    "contradiction": "#c0392b", # Dark red
    "motive": "#f1c40f",       # Gold - revealed motive/secret
}


def build_case_board(
    mystery: Optional[Any] = None,
    suspects_talked_to: List[str] = None,
    clues_found: List[str] = None,
    searched_locations: List[str] = None,
    discovered_timeline: List[Dict] = None,
    suspect_states: Dict = None,
) -> Optional[Any]:
    """Build the case board visualization.
    
    Args:
        mystery: The Mystery object (None if not ready)
        suspects_talked_to: List of suspect names talked to
        clues_found: List of clue descriptions found
        searched_locations: List of locations searched
        discovered_timeline: Timeline events discovered
        suspect_states: Dict of suspect emotional states
        
    Returns:
        Plotly Figure or None if not available
    """
    if not PLOTLY_AVAILABLE:
        return None
    
    suspects_talked_to = suspects_talked_to or []
    clues_found = clues_found or []
    searched_locations = searched_locations or []
    discovered_timeline = discovered_timeline or []
    suspect_states = suspect_states or {}
    
    # Create the graph
    G = nx.DiGraph()
    
    # Track alibi locations to avoid duplicates
    alibi_locations = {}  # location_name -> node_id
    
    # ==========================================================================
    # ADD CRIME SCENE (victim + location) AT CENTER
    # ==========================================================================
    crime_location = "Crime Scene"
    if mystery and mystery.victim:
        victim_name = mystery.victim.name
        # Extract crime location from setting if available
        if hasattr(mystery, 'setting') and mystery.setting:
            crime_location = mystery.setting[:30] + "..." if len(mystery.setting) > 30 else mystery.setting
        
        # Crime scene node (the location)
        G.add_node(
            "CRIME_SCENE",
            label=crime_location,
            icon=ICONS["crime_scene"],
            node_type="Crime Scene",
            desc=f"Where {victim_name} was found\n{mystery.setting if hasattr(mystery, 'setting') else ''}",
            color=COLORS["crime_scene"],
        )
        
        # Victim node
        G.add_node(
            "VICTIM",
            label=victim_name,
            icon=ICONS["victim"],
            node_type="Victim",
            desc=mystery.victim.background if mystery.victim else "The victim",
            color=COLORS["victim"],
        )
        
        # Connect victim to crime scene
        G.add_edge("VICTIM", "CRIME_SCENE")
    else:
        G.add_node(
            "VICTIM",
            label="Victim",
            icon=ICONS["victim"],
            node_type="Victim", 
            desc="Investigation in progress...",
            color=COLORS["victim"],
        )
    
    # ==========================================================================
    # ADD SUSPECT NODES WITH ALIBI LOCATIONS
    # ==========================================================================
    if mystery and mystery.suspects:
        for suspect in mystery.suspects:
            talked_to = suspect.name in suspects_talked_to
            state = suspect_states.get(suspect.name)
            has_contradictions = state and state.contradictions_caught > 0
            
            # Determine icon and type based on investigation progress
            if has_contradictions:
                icon = ICONS["suspect_suspicious"]
                node_type = "Suspicious"
                color = COLORS["suspect_suspicious"]
            elif talked_to:
                icon = ICONS["suspect_talked"]
                node_type = "Interrogated"
                color = COLORS["suspect_talked"]
            else:
                icon = ICONS["suspect"]
                node_type = "Suspect"
                color = COLORS["suspect"]
            
            # Build description
            desc_parts = [f"Role: {suspect.role}"]
            alibi_location = None
            
            if talked_to:
                # Extract alibi location
                if hasattr(suspect, 'structured_alibi') and suspect.structured_alibi:
                    alibi_location = suspect.structured_alibi.location_claimed
                    desc_parts.append(f"Claims: Was at {alibi_location}")
                else:
                    desc_parts.append(f"Alibi: {suspect.alibi[:50]}...")
                    
                if state:
                    desc_parts.append(f"Trust: {state.trust}%")
                    desc_parts.append(f"Nervousness: {state.nervousness}%")
                    if state.contradictions_caught > 0:
                        desc_parts.append(f"⚠️ {state.contradictions_caught} contradiction(s)!")
            else:
                desc_parts.append("Not yet interrogated")
            
            # Add suspect node
            suspect_node_id = f"SUSPECT_{suspect.name}"
            G.add_node(
                suspect_node_id,
                label=suspect.name,
                icon=icon,
                node_type=node_type,
                desc="\n".join(desc_parts),
                color=color,
            )
            
            # Connect suspect to victim (they're all suspects in the murder)
            G.add_edge(suspect_node_id, "VICTIM")
            
            # If we know their alibi location, add it and connect
            if talked_to and alibi_location:
                loc_key = alibi_location.lower().strip()
                if loc_key not in alibi_locations:
                    loc_node_id = f"ALIBI_LOC_{len(alibi_locations)}"
                    alibi_locations[loc_key] = loc_node_id
                    G.add_node(
                        loc_node_id,
                        label=alibi_location[:20] + "..." if len(alibi_location) > 20 else alibi_location,
                        icon=ICONS["location_alibi"],
                        node_type="Alibi Location",
                        desc=f"Location where suspect claims to have been",
                        color=COLORS["location_alibi"],
                    )
                else:
                    loc_node_id = alibi_locations[loc_key]
                
                # Connect suspect to their alibi location
                G.add_edge(suspect_node_id, loc_node_id)
            
            # If suspect's secret/motive has been revealed, show it!
            if state and state.secret_revealed and hasattr(suspect, 'secret') and suspect.secret:
                motive_node_id = f"MOTIVE_{suspect.name}"
                # Truncate long secrets for label
                secret_short = suspect.secret[:25] + "..." if len(suspect.secret) > 25 else suspect.secret
                G.add_node(
                    motive_node_id,
                    label=secret_short,
                    icon=ICONS["motive"],
                    node_type="Motive/Secret",
                    desc=f"🔓 {suspect.name}'s Secret:\n\n{suspect.secret}",
                    color=COLORS.get("motive", "#f1c40f"),  # Gold color for motive
                )
                # Connect motive to suspect
                G.add_edge(motive_node_id, suspect_node_id)
    
    # ==========================================================================
    # ADD CLUE NODES WITH DISCOVERY LOCATIONS
    # ==========================================================================
    if mystery and mystery.clues and clues_found:
        for clue in mystery.clues:
            if clue.description in clues_found or clue.id in [c for c in clues_found]:
                # Determine clue icon based on type
                clue_lower = clue.description.lower()
                if any(w in clue_lower for w in ["knife", "weapon", "gun", "poison", "murder"]):
                    icon = ICONS["clue_weapon"]
                elif any(w in clue_lower for w in ["letter", "note", "document", "paper", "email"]):
                    icon = ICONS["clue_document"]
                elif any(w in clue_lower for w in ["footprint", "fingerprint", "blood", "hair"]):
                    icon = ICONS["clue_physical"]
                else:
                    icon = ICONS["clue_generic"]
                
                clue_node_id = f"CLUE_{clue.id}"
                G.add_node(
                    clue_node_id,
                    label=clue.description[:20] + "...",
                    icon=icon,
                    node_type="Evidence",
                    desc=f"Found at: {clue.location}\n\n{clue.description}",
                    color=COLORS["clue"],
                )
                
                # Add/get location node for where clue was found
                loc_key = clue.location.lower().strip()
                if loc_key not in alibi_locations:
                    loc_node_id = f"LOC_{clue.location}"
                    alibi_locations[loc_key] = loc_node_id
                    is_searched = clue.location in searched_locations
                    G.add_node(
                        loc_node_id,
                        label=clue.location[:15] + "..." if len(clue.location) > 15 else clue.location,
                        icon=ICONS["location_searched"] if is_searched else ICONS["location"],
                        node_type="Searched" if is_searched else "Location",
                        desc=f"Searched location: {clue.location}",
                        color=COLORS["location_searched"] if is_searched else COLORS["location"],
                    )
                else:
                    loc_node_id = alibi_locations[loc_key]
                
                # Connect location to clue
                G.add_edge(loc_node_id, clue_node_id)
                
                # If clue contradicts a suspect's alibi, draw red line
                if clue.contradicts_alibi_of:
                    suspect_node = f"SUSPECT_{clue.contradicts_alibi_of}"
                    if G.has_node(suspect_node):
                        G.add_edge(clue_node_id, suspect_node, edge_type="contradiction")
    
    # ==========================================================================
    # ADD CONTRADICTION MARKERS
    # ==========================================================================
    contradiction_count = 0
    for i, event in enumerate(discovered_timeline):
        if event.get("is_contradiction"):
            contradiction_count += 1
            G.add_node(
                f"CONTRADICTION_{i}",
                label=f"Contradiction #{contradiction_count}",
                icon=ICONS["contradiction"],
                node_type="Contradiction",
                desc=event.get("description", "Conflicting information"),
                color=COLORS["contradiction"],
            )
            # Connect to suspect if known
            suspect_name = event.get("suspect_name")
            if suspect_name:
                suspect_node = f"SUSPECT_{suspect_name}"
                if G.has_node(suspect_node):
                    G.add_edge(f"CONTRADICTION_{i}", suspect_node, edge_type="contradiction")
    
    # ==========================================================================
    # GENERATE LAYOUT
    # ==========================================================================
    if len(G.nodes()) == 0:
        return _create_empty_board()
    
    # Use spring layout with crime scene at center
    pos = nx.spring_layout(G, seed=42, k=1.5, iterations=50)
    
    # Force crime scene and victim to center
    if "CRIME_SCENE" in pos:
        pos["CRIME_SCENE"] = (0, -0.1)
    if "VICTIM" in pos:
        pos["VICTIM"] = (0, 0.1)
    
    # ==========================================================================
    # BUILD PLOTLY TRACES
    # ==========================================================================
    
    # --- Normal Edges (grey string connections) ---
    normal_edge_x = []
    normal_edge_y = []
    # --- Contradiction Edges (red dashed) ---
    contradiction_edge_x = []
    contradiction_edge_y = []
    
    for edge in G.edges(data=True):
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_data = edge[2] if len(edge) > 2 else {}
        
        if edge_data.get("edge_type") == "contradiction":
            contradiction_edge_x.extend([x0, x1, None])
            contradiction_edge_y.extend([y0, y1, None])
        else:
            normal_edge_x.extend([x0, x1, None])
            normal_edge_y.extend([y0, y1, None])
    
    # Normal connections (grey, subtle)
    normal_edge_trace = go.Scatter(
        x=normal_edge_x, y=normal_edge_y,
        line=dict(width=1.5, color='rgba(150, 150, 150, 0.4)'),
        hoverinfo='none',
        mode='lines'
    )
    
    # Contradiction connections (red, bold, dashed)
    contradiction_edge_trace = go.Scatter(
        x=contradiction_edge_x, y=contradiction_edge_y,
        line=dict(width=3, color='rgba(231, 76, 60, 0.8)', dash='dash'),
        hoverinfo='none',
        mode='lines'
    )
    
    # --- Node Icons ---
    node_x = []
    node_y = []
    node_icons = []
    node_labels = []
    node_hovers = []
    node_sizes = []
    
    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        
        data = G.nodes[node]
        node_icons.append(data['icon'])
        node_labels.append(data['label'])
        
        # Size based on type
        if data['node_type'] in ["Victim", "Crime Scene"]:
            size = 55
        elif data['node_type'] in ["Suspicious", "Contradiction"]:
            size = 45
        elif data['node_type'] in ["Suspect", "Interrogated"]:
            size = 40
        elif data['node_type'] == "Evidence":
            size = 38
        else:
            size = 32  # Locations
        node_sizes.append(size)
        
        # Hover text
        wrapped_desc = "<br>".join(textwrap.wrap(data['desc'], width=35))
        hover = f"<b>{data['label']}</b><br>Type: {data['node_type']}<br>---<br>{wrapped_desc}"
        node_hovers.append(hover)
    
    # Icons trace
    icon_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='text',
        text=node_icons,
        textposition="middle center",
        hoverinfo='text',
        hovertext=node_hovers,
        textfont=dict(size=node_sizes)
    )
    
    # Labels trace (below icons)
    label_trace = go.Scatter(
        x=node_x, y=[y - 0.12 for y in node_y],
        mode='text',
        text=node_labels,
        textposition="bottom center",
        hoverinfo='none',
        textfont=dict(size=10, color='#666666')
    )
    
    # ==========================================================================
    # CREATE FIGURE
    # ==========================================================================
    fig = go.Figure(
        data=[normal_edge_trace, contradiction_edge_trace, label_trace, icon_trace],
        layout=go.Layout(
            title=dict(
                text='🔍 Case Board',
                font=dict(size=20, family="Georgia, serif", color="#333"),
                x=0.5,
            ),
            showlegend=False,
            hovermode='closest',
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, visible=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, visible=False),
            margin=dict(b=20, l=20, r=20, t=50),
            plot_bgcolor='rgba(30, 30, 30, 0.95)',
            paper_bgcolor='rgba(20, 20, 20, 1)',
            # Add annotations for legend
            annotations=[
                dict(
                    x=0.02, y=0.98, xref="paper", yref="paper",
                    text="💀 Victim | 🔴 Crime Scene | 👤 Suspect | 🗣️ Talked | ⚠️ Suspicious",
                    showarrow=False,
                    font=dict(size=9, color="#888"),
                    align="left",
                ),
                dict(
                    x=0.02, y=0.93, xref="paper", yref="paper",
                    text="🏠 Alibi Location | 📍 Location | 🔎 Clue | 💰 Motive | ❌ Contradiction",
                    showarrow=False,
                    font=dict(size=9, color="#888"),
                    align="left",
                )
            ]
        )
    )
    
    return fig


def _create_empty_board() -> Any:
    """Create an empty case board with placeholder text."""
    if not PLOTLY_AVAILABLE:
        return None
    
    fig = go.Figure()
    fig.add_annotation(
        x=0.5, y=0.5,
        text="🔍 Case Board Empty<br><br>Start investigating to build your case!<br>• Talk to suspects<br>• Search locations<br>• Find connections",
        showarrow=False,
        font=dict(size=16, color="#888"),
        align="center",
    )
    fig.update_layout(
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, visible=False, range=[0, 1]),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, visible=False, range=[0, 1]),
        plot_bgcolor='rgba(30, 30, 30, 0.95)',
        paper_bgcolor='rgba(20, 20, 20, 1)',
        margin=dict(b=20, l=20, r=20, t=20),
    )
    return fig


def format_case_board_html(
    mystery: Optional[Any] = None,
    suspects_talked_to: List[str] = None,
    clues_found: List[str] = None,
    searched_locations: List[str] = None,
    discovered_timeline: List[Dict] = None,
    suspect_states: Dict = None,
) -> str:
    """Format the case board as HTML for display.
    
    If Plotly isn't available, returns a text-based fallback.
    """
    if not PLOTLY_AVAILABLE:
        return _format_text_fallback(
            mystery, suspects_talked_to, clues_found, 
            searched_locations, discovered_timeline, suspect_states
        )
    
    # Return empty indicator - actual plot handled by gr.Plot
    return ""


def _format_text_fallback(
    mystery, suspects_talked_to, clues_found, 
    searched_locations, discovered_timeline, suspect_states
) -> str:
    """Text-based fallback when Plotly isn't available."""
    suspects_talked_to = suspects_talked_to or []
    clues_found = clues_found or []
    
    html = '<div class="case-board-text">'
    html += '<div class="board-title">📋 CASE BOARD</div>'
    
    # Victim
    if mystery and mystery.victim:
        html += f'<div class="board-section"><b>💀 VICTIM:</b> {mystery.victim.name}</div>'
    
    # Suspects
    html += '<div class="board-section"><b>👥 SUSPECTS:</b></div>'
    if mystery and mystery.suspects:
        for s in mystery.suspects:
            status = "🗣️ Talked" if s.name in suspects_talked_to else "❓ Unknown"
            html += f'<div class="board-item">• {s.name} ({s.role}) - {status}</div>'
    
    # Clues
    html += f'<div class="board-section"><b>🔎 CLUES FOUND:</b> {len(clues_found)}</div>'
    for clue in clues_found[:5]:
        html += f'<div class="board-item">• {clue[:40]}...</div>'
    
    html += '</div>'
    return html

