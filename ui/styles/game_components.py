"""Game component CSS styles (clues, suspects, accusations, transcript)."""

CSS_GAME_COMPONENTS = """/* ========== BASE PANEL TITLE (fallback) ========== */
.panel-title {
    font-family: var(--font-retro-mono);
    font-size: 16px;
    font-weight: 700;
    color: var(--accent-blue);
    padding: 8px;
    margin-bottom: 16px;
    margin-top: 0;
    text-transform: uppercase;
    letter-spacing: 1px;
}

/* ========== CLUES & ITEMS ========== */
.clue-item {
    font-family: var(--font-body);
    font-size: 13px;
    color: var(--text-primary);
    padding: 8px 12px;
    border-left: 3px solid var(--accent-blue);
    margin-bottom: 6px;
    background: var(--bg-panel);
    border-radius: 4px;
    box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.5);
}

.location-item {
    font-family: var(--font-body);
    font-size: 14px;
    padding: 6px 12px;
    color: var(--text-primary);
    border-radius: 4px;
    margin-bottom: 4px;
}

.location-item.searched {
    color: var(--text-secondary);
    text-decoration: line-through;
    background: var(--bg-panel);
}

.suspect-check,
.location-check {
    color: var(--accent-green) !important;
    font-weight: 700;
}

/* ========== SUSPECT ITEMS ========== */
.suspect-item {
    font-family: var(--font-body);
    font-size: 14px;
    color: var(--text-primary);
    border-radius: 4px;
    margin-bottom: 4px;
    border: 1px solid var(--border-dark);
    background: var(--bg-card);
}

.suspect-item summary {
    padding: 8px 12px;
    cursor: pointer;
    user-select: none;
    list-style: none;
    transition: background 0.2s ease;
    display: flex;
    align-items: flex-start;
}

.suspect-item summary::-webkit-details-marker { display: none; }

.suspect-item summary::before {
    content: '▶';
    display: inline-block;
    width: 12px;
    margin-right: 8px;
    font-size: 10px;
    color: var(--accent-green);
    transition: transform 0.2s ease;
}

.suspect-item[open] summary::before { transform: rotate(90deg); }
.suspect-item summary:hover { background: var(--bg-panel); }
.suspect-item.searched { opacity: 0.7; background: var(--bg-panel); }
.suspect-item.searched summary { color: var(--text-secondary); }

.suspect-header { flex: 1; line-height: 1.4; }

.suspect-role-preview {
    font-size: 1em;
    color: var(--accent-orange) !important;
    font-weight: normal;
    font-style: italic;
}

.suspect-details {
    padding: 8px 12px 12px 32px;
    border-top: 1px solid var(--border-dark);
    background: rgba(0, 0, 0, 0.2);
}

.suspect-motive {
    font-size: 1em;
    color: var(--text-secondary);
    line-height: 1.4;
}

/* ========== ACCUSATIONS ========== */
.accusations-display {
    font-family: var(--font-retro-mono);
    font-size: 14px;
    font-weight: 500;
    color: var(--text-primary);
    display: flex;
    flex-direction: column;
}

.accusations-pip {
    display: inline-block;
    width: 10px;
    height: 10px;
    background: var(--accent-blue);
    border-radius: 50%;
    margin: 0 4px;
}

.accusations-pip.used { background: var(--accent-red); }

/* ========== TRANSCRIPT PANEL ========== */
.transcript-panel {
    max-height: 300px;
    overflow-y: auto;
    font-family: var(--font-retro-mono);
    font-size: 13px;
    line-height: 1.5;
}

/* Suspects list - fully visible */
.suspects-list,
.suspects-panel .transcript-panel {
    max-height: none !important;
    overflow-y: visible !important;
    height: auto !important;
}

.suspects-panel {
    height: auto !important;
    max-height: none !important;
    overflow: visible !important;
}

"""
