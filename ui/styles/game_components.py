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

/* Location cards for tabs (optional scene image + label) */
.location-card {
    display: flex;
    flex-direction: row;
    align-items: center;
    gap: 10px;
    margin-bottom: 6px;
}

.location-card .location-image {
    flex: 0 0 96px;
    width: 96px;
    height: 72px;
    border-radius: 4px;
    overflow: hidden;
    background: rgba(0, 20, 0, 0.6);
}

.location-card .location-image img {
    width: 100%;
    height: 100%;
    object-fit: cover;
}

.location-card .location-info {
    flex: 1;
    min-width: 0;
}

.location-card .location-name {
    font-family: var(--font-body);
    font-size: 14px;
    color: var(--text-primary);
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

/* ========== INVESTIGATION DASHBOARD ========== */
.investigation-dashboard {
    position: relative;
    z-index: 20;
    padding: 12px;
    font-family: var(--font-body);
    color: var(--terminal-green);
}

.dashboard-empty {
    text-align: center;
    padding: 24px;
    color: var(--terminal-green-muted);
    font-family: var(--font-body);
    font-size: 14px;
    line-height: 1.6;
}

.dashboard-icon {
    font-size: 36px;
    margin-bottom: 12px;
    opacity: 0.6;
}

/* Dashboard Status Card */
.dashboard-status {
    background: rgba(0, 30, 0, 0.6);
    border: 1px solid var(--terminal-green-border-soft);
    padding: 14px;
    margin-bottom: 16px;
}

.dashboard-status.ready-high {
    border-color: var(--terminal-green);
    background: rgba(51, 255, 51, 0.1);
}

.dashboard-status.ready-medium {
    border-color: #ffcc00;
    background: rgba(255, 204, 0, 0.08);
}

.dashboard-status.ready-low {
    border-color: var(--terminal-green-muted);
}

.status-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 8px;
}

.status-icon {
    font-size: 20px;
}

.status-score {
    font-family: var(--font-retro-mono);
    font-size: 20px;
    font-weight: 400;
    color: var(--terminal-green);
    text-shadow: 0 0 8px var(--terminal-green);
}

.status-text {
    font-size: 14px;
    color: var(--terminal-green-accent);
    margin-bottom: 10px;
    font-family: var(--font-body);
    line-height: 1.5;
}

.status-accusations {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    color: var(--terminal-green-muted);
    font-family: var(--font-body);
}

.status-accusations .pip {
    display: inline-block;
    width: 12px;
    height: 12px;
    background: var(--terminal-green);
    border-radius: 2px;
}

.status-accusations .pip.used {
    background: #ff4444;
    animation: pip-flash 1s ease-in-out infinite;
}

@keyframes pip-flash {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}

/* Dashboard Sections */
.dashboard-section {
    margin-bottom: 16px;
    background: rgba(0, 20, 0, 0.4);
    border: 1px solid var(--terminal-green-border-soft);
    padding: 12px;
}

.dashboard-section-header {
    font-family: var(--font-retro-mono);
    font-size: 14px;
    color: var(--terminal-green);
    letter-spacing: 2px;
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--terminal-green-border-soft);
    text-shadow: 0 0 6px var(--terminal-green);
}

/* Progress Rows */
.dashboard-progress-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 8px;
    font-size: 14px;
}

.dashboard-label {
    width: 120px;
    color: var(--terminal-green);
    flex-shrink: 0;
    font-family: var(--font-body);
    font-weight: 400;
}

.dashboard-bar-track {
    flex: 1;
    min-width: 0;
    height: 14px;
    background: rgba(0, 20, 0, 0.6);
    border: 1px solid var(--terminal-green-border-soft);
    border-radius: 2px;
    overflow: hidden;
}

.dashboard-bar-fill {
    height: 100%;
    transition: width 0.3s ease;
    border-radius: 1px;
}

.dashboard-value {
    width: 55px;
    text-align: right;
    color: var(--terminal-green);
    flex-shrink: 0;
    font-family: var(--font-body);
    font-weight: 600;
}

.dashboard-hint {
    font-size: 14px;
    color: var(--terminal-green-muted);
    text-align: center;
    padding: 16px;
    font-style: italic;
    font-family: var(--font-body);
    line-height: 1.5;
}

/* Suspicion Ranking */
.suspicion-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 6px;
    margin-bottom: 6px;
    background: rgba(0, 30, 0, 0.3);
    border-left: 3px solid transparent;
}

.suspicion-row:first-child {
    border-left-color: #ff4444;
    background: rgba(255, 68, 68, 0.1);
}

.suspicion-rank {
    width: 28px;
    text-align: center;
    font-size: 14px;
}

.suspicion-name {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--terminal-green);
    font-size: 14px;
    font-family: var(--font-body);
    font-weight: 600;
}

.suspicion-bar-track {
    width: 80px;
    height: 10px;
    background: rgba(0, 20, 0, 0.6);
    border: 1px solid var(--terminal-green-border-soft);
    border-radius: 2px;
    overflow: hidden;
    flex-shrink: 0;
}

.suspicion-bar-fill {
    height: 100%;
    transition: width 0.3s ease;
    border-radius: 1px;
}

.suspicion-contradiction {
    font-size: 11px;
    color: #ff6666;
    font-family: var(--font-body);
    animation: contradiction-pulse 2s ease-in-out infinite;
}

/* ========== SETUP WIZARD ========== */
.setup-wizard {
    margin: 0 auto;
    padding:0;
}

.wizard-settings {
    background: rgba(0, 20, 0, 0.4);
    border: 1px solid var(--terminal-green-border-soft);
    padding: 20px;
    margin-bottom: 20px;
}

.wizard-section-title {
    font-family: var(--font-retro-mono);
    font-size: 16px;
    color: var(--terminal-green);
    letter-spacing: 2px;
    margin-bottom: 16px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--terminal-green-border-soft);
    text-shadow: 0 0 6px var(--terminal-green);
    text-transform: uppercase;
}

.wizard-buttons {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
}

.wizard-secondary-btn {
    background: transparent !important;
    border: 1px solid var(--terminal-green-border-soft) !important;
    color: var(--terminal-green-muted) !important;
    font-size: 12px !important;
    padding: 8px 16px !important;
}

.wizard-secondary-btn:hover {
    border-color: var(--terminal-green) !important;
    color: var(--terminal-green) !important;
}

.wizard-primary-btn {
    flex: 1;
    max-width: 300px;
}

/* ========== SUSPECT CARDS LIST (TAB) ========== */
.suspects-card-grid {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 8px;
}

.suspect-card {
    display: flex;
    flex-direction: row;
    align-items: flex-start; /* don't stretch portrait; keep its own height */
    background: var(--bg-card);
    border: 1px solid var(--terminal-green-border-soft);
    border-radius: 6px;
    overflow: hidden;
    transition: border-color 0.2s ease, transform 0.15s ease, background 0.2s ease;
    cursor: pointer;
    position: relative;
}

.suspect-card:hover {
    border-color: var(--terminal-green);
    transform: translateY(-2px);
}

.suspect-card.talked-to {
    border-color: var(--terminal-green-border-strong);
}

.suspect-card.talked-to::after {
    content: '✓';
    position: absolute;
    top: 8px;
    right: 8px;
    color: var(--terminal-green);
    font-size: 14px;
    font-weight: bold;
    z-index: 2;
    text-shadow: 0 0 6px var(--terminal-green);
}

.suspect-card-portrait {
    position: relative;
    flex: 0 0 120px;
    max-width: 120px;
    width: 100%;
    /* Square aspect ratio so cards never jump when images load, regardless of content */
    aspect-ratio: 1 / 1;
    background: rgba(0, 20, 0, 0.4);
    overflow: hidden;
    align-self: flex-start; /* explicitly prevent flexbox from stretching */
}

.suspect-card-portrait img {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    object-fit: cover;
    filter: sepia(10%) saturate(1.1);
    transition: filter 0.2s ease;
}

.suspect-card:hover .suspect-card-portrait img {
    filter: sepia(0%) saturate(1.2);
}

.suspect-card-portrait-placeholder {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 48px;
    color: var(--terminal-green-muted);
    background: linear-gradient(135deg, rgba(0, 30, 0, 0.6) 0%, rgba(0, 20, 0, 0.8) 100%);
}

/* Hide placeholder once an image is present, but keep layout fixed */
.suspect-card-portrait:has(img) .suspect-card-portrait-placeholder {
    opacity: 0;
    visibility: hidden;
}

.suspect-card-info {
    flex: 1;
    min-width: 0;
    padding: 12px;
    position: relative;
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.suspect-card-name {
    font-family: var(--font-body);
    font-size: 15px;
    font-weight: 700;
    color: var(--terminal-green);
    margin-bottom: 4px;
    text-shadow: 0 0 4px var(--terminal-green-glow);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.suspect-card-role {
    font-family: var(--font-body);
    font-size: 13px;
    color: var(--terminal-green-accent);
    font-style: italic;
    margin-bottom: 8px;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

.suspect-card-status {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    margin-top: 6px;
}

.suspect-card-badge {
    font-family: var(--font-retro-mono);
    font-size: 11px;
    padding: 2px 6px;
    border-radius: 3px;
    background: rgba(51, 255, 51, 0.1);
    border: 1px solid var(--terminal-green-border-soft);
    color: var(--terminal-green-muted);
}

.suspect-card-badge.contradiction {
    background: rgba(255, 68, 68, 0.15);
    border-color: #ff4444;
    color: #ff6666;
}

.suspect-card-badge.talked {
    background: rgba(51, 255, 51, 0.2);
    color: var(--terminal-green);
}

/* Responsive adjustments */
@media (max-width: 600px) {
    .suspect-card {
        flex-direction: column;
    }
    
    .suspect-card-info {
        padding: 8px;
    }
    
    .suspect-card-name {
        font-size: 13px;
    }
    
    .suspect-card-role {
        font-size: 11px;
    }
}

@media (min-width: 900px) {
    .suspects-card-grid {
        grid-template-columns: repeat(4, 1fr);
    }
}

/* ========== REFRESH SUSPECTS BUTTON ========== */
.refresh-suspects-btn {
    background: transparent !important;
    border: 1px solid var(--terminal-green-border-soft) !important;
    color: var(--terminal-green-muted) !important;
    font-family: var(--font-retro-mono) !important;
    font-size: 16px !important; /* slightly larger icon */
    padding: 0 !important;
    border-radius: 4px !important;
    cursor: pointer !important;
    transition: all 0.2s ease !important;
    width: 32px !important;
    height: 32px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}

.refresh-suspects-btn:hover {
    border-color: var(--terminal-green) !important;
    color: var(--terminal-green) !important;
    background: rgba(51, 255, 51, 0.1) !important;
}
"""
