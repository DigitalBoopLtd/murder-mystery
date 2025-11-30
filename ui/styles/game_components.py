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

/* Locations empty state */
.locations-empty {
    text-align: center;
    padding: 24px;
    color: var(--terminal-green-muted);
    font-family: var(--font-body);
    font-size: 14px;
    line-height: 1.6;
}

.locations-icon {
    font-size: 36px;
    margin-bottom: 12px;
    opacity: 0.6;
}

.locations-message {
    color: var(--terminal-green);
    font-weight: 600;
    margin-bottom: 6px;
}

.locations-hint {
    font-style: italic;
    opacity: 0.8;
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

/* ========== GAME STARTED MARKER ========== */
/* Container starts empty - when game starts, .game-active element is injected */
/* CSS uses :has(.game-active) to detect game state and show/hide UI */
.game-started-container {
    position: absolute;
    pointer-events: none;
    width: 0;
    height: 0;
    overflow: hidden;
}

.game-active {
    display: none;
}

/* ========== HIDE MAIN GAME CONTENT UNTIL GAME STARTS ========== */
/* Default: completely hide the CRT stage - don't take up any space */
.center-column > .gr-group {
    display: none !important;
}

/* When .game-active element exists, show the CRT stage */
.center-column:has(.game-active) > .gr-group {
    display: flex !important;
    opacity: 1;
    animation: fadeIn 0.4s ease-in;
}

@keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}

/* ========== SETUP WIZARD POSITIONING ========== */
/* Position wizard in the center where the game screen will appear */
.setup-wizard {
    display: flex;
    flex-direction: column;
    justify-content: center;
    min-height: 400px;
    margin: 0 auto;
    padding: 0;
}

/* When game has started (marker contains .game-active), hide the setup wizard */
.center-column:has(.game-active) .setup-wizard {
    display: none !important;
}
button.record.record-button { height: 48px !important; width: 48px !important; background: transparent; }
.mic-select, .icon-button, .icon-button-wrapper { display: none !important; }
.record-button.svelte-1xuh0j1:before {background: transparent !important;}

/* Let audio controls size themselves naturally – no global overrides on .record-button */

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
    justify-content: center;
    align-items: center;
    gap: 16px;
    margin-top: 24px;
    padding-top: 20px;
    border-top: 1px solid var(--terminal-green-border-soft);
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
    flex: 0;
    min-width: 200px;
    padding: 14px 32px !important;
    font-size: 16px !important;
    font-weight: 600 !important;
    background: var(--terminal-green) !important;
    color: #000 !important;
    border: none !important;
    border-radius: 4px !important;
    text-transform: uppercase;
    letter-spacing: 1px;
    transition: all 0.2s ease;
}

.wizard-primary-btn:hover {
    background: var(--terminal-green-accent) !important;
    transform: translateY(-1px);
}

/* ========== SUSPECT CARDS LIST (TAB & SIDE PANEL) ========== */
.suspects-card-grid {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

/* Side panel suspects: compact row layout with small portrait to reduce height */
.suspects-card-grid-column .suspect-card {
    flex-direction: row;
    align-items: center;
}

.suspects-card-grid-column .suspect-card-portrait {
    flex: 0 0 56px;
    max-width: 56px;
    aspect-ratio: 1 / 1;
}

.suspects-card-grid-column .suspect-card-info {
    padding: 8px 10px;
}

/* Hide deep meters/relationships in side panel to keep cards short;
   full detail is available in the main Suspects tab. */
.suspects-card-grid-column .suspect-meters,
.suspects-card-grid-column .suspect-relationships,
.suspects-card-grid-column .suspect-motive {
    display: none;
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

/* Minimal card style - no portrait area until questioned */
.suspect-card-minimal {
    min-height: auto;
}

/* Loading indicator while portrait generates */
.suspect-card-portrait-loading {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 32px;
    color: var(--terminal-green-muted);
    background: linear-gradient(135deg, rgba(0, 30, 0, 0.6) 0%, rgba(0, 20, 0, 0.8) 100%);
    animation: pulse 1.5s ease-in-out infinite;
}

/* Compact suspects list in desktop/tab view: small thumbnail + name/role only */
.suspects-list .suspect-card-compact .suspect-card-portrait {
    flex: 0 0 56px;
    max-width: 56px;
    aspect-ratio: 1 / 1;
}

.suspects-list .suspect-card-compact .suspect-card-name {
    font-size: 14px;
}

.suspects-list .suspect-card-compact .suspect-card-role {
    font-size: 12px;
    margin-bottom: 4px;
}

@keyframes pulse {
    0%, 100% { opacity: 0.5; }
    50% { opacity: 1; }
}

.suspect-card-info {
    flex: 1;
    min-width: 0;
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

/* ========== ACCUSATIONS TAB ========== */
.accusations-tab {
    padding: 16px;
    font-family: var(--font-body);
}

/* Fired Screen */
.fired-screen {
    text-align: center;
    padding: 40px 20px;
    background: rgba(255, 50, 50, 0.1);
    border: 2px solid #ff4444;
    border-radius: 8px;
    margin: 20px;
}

.fired-icon {
    font-size: 64px;
    margin-bottom: 16px;
}

.fired-title {
    font-family: var(--font-retro-mono);
    font-size: 32px;
    color: #ff4444;
    text-shadow: 0 0 20px #ff4444;
    margin-bottom: 16px;
    letter-spacing: 4px;
}

.fired-message {
    font-size: 16px;
    color: var(--text-primary);
    line-height: 1.6;
    max-width: 400px;
    margin: 0 auto 20px;
}

.fired-hint {
    font-size: 14px;
    color: var(--terminal-green);
    font-style: italic;
}

/* Accusations Remaining */
.accusations-remaining {
    background: rgba(0, 30, 0, 0.4);
    border: 1px solid var(--terminal-green-border-soft);
    padding: 16px;
    margin-bottom: 16px;
    text-align: center;
}

.accusations-label {
    font-family: var(--font-retro-mono);
    font-size: 14px;
    color: var(--terminal-green);
    letter-spacing: 2px;
    margin-bottom: 12px;
}

.accusations-pips {
    display: flex;
    justify-content: center;
    gap: 16px;
    margin-bottom: 8px;
}

.accusation-pip {
    font-size: 24px;
}

.accusation-pip.used {
    opacity: 0.5;
}

.accusations-count {
    font-size: 16px;
    color: var(--terminal-green);
    margin-bottom: 8px;
}

.accusations-warning {
    font-size: 13px;
    color: var(--terminal-green-accent);
    font-style: italic;
}

/* Checklist */
.accusations-checklist {
    background: rgba(0, 20, 0, 0.4);
    border: 1px solid var(--terminal-green-border-soft);
    padding: 16px;
    margin-bottom: 16px;
}

.checklist-header {
    font-family: var(--font-retro-mono);
    font-size: 14px;
    color: var(--terminal-green);
    letter-spacing: 2px;
    margin-bottom: 4px;
    text-shadow: 0 0 6px var(--terminal-green);
}

.checklist-subtitle {
    font-size: 13px;
    color: var(--terminal-green-muted);
    margin-bottom: 12px;
}

.checklist-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px;
    margin-bottom: 4px;
    border-radius: 4px;
}

.checklist-item.met {
    background: rgba(51, 255, 51, 0.1);
}

.checklist-item.unmet {
    background: rgba(255, 255, 255, 0.02);
}

.checklist-icon {
    font-size: 16px;
}

.checklist-label {
    flex: 1;
    font-size: 14px;
    color: var(--text-primary);
}

.checklist-importance {
    font-size: 11px;
    color: var(--terminal-green-accent);
    font-style: italic;
}

.checklist-item.unmet .checklist-importance {
    color: #ffcc00;
}

.checklist-strength {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid var(--terminal-green-border-soft);
    font-size: 14px;
    color: var(--terminal-green);
}

.strength-bar {
    flex: 1;
    height: 12px;
    background: rgba(0, 20, 0, 0.6);
    border: 1px solid var(--terminal-green-border-soft);
    border-radius: 2px;
    overflow: hidden;
}

.strength-fill {
    height: 100%;
    background: var(--terminal-green);
    transition: width 0.3s ease;
}

.strength-pct {
    font-family: var(--font-retro-mono);
    min-width: 40px;
    text-align: right;
}

.checklist-tip {
    margin-top: 12px;
    padding: 10px;
    background: rgba(51, 255, 51, 0.05);
    border-radius: 4px;
    font-size: 13px;
    color: var(--terminal-green-accent);
    text-align: center;
}

/* Accusation History */
.accusations-history {
    background: rgba(0, 20, 0, 0.4);
    border: 1px solid var(--terminal-green-border-soft);
    padding: 16px;
}

.history-header {
    font-family: var(--font-retro-mono);
    font-size: 14px;
    color: var(--terminal-green);
    letter-spacing: 2px;
    margin-bottom: 12px;
    text-shadow: 0 0 6px var(--terminal-green);
}

.history-empty {
    text-align: center;
    padding: 20px;
    color: var(--terminal-green-muted);
    font-style: italic;
}

.history-item {
    display: flex;
    gap: 12px;
    padding: 12px;
    margin-bottom: 8px;
    background: rgba(0, 0, 0, 0.2);
    border-radius: 4px;
    border-left: 3px solid transparent;
}

.history-item.success {
    border-left-color: var(--terminal-green);
    background: rgba(51, 255, 51, 0.1);
}

.history-item.wrong_suspect {
    border-left-color: #ff4444;
    background: rgba(255, 68, 68, 0.1);
}

.history-item.insufficient_evidence {
    border-left-color: #ffcc00;
    background: rgba(255, 204, 0, 0.1);
}

.history-number {
    font-family: var(--font-retro-mono);
    font-size: 16px;
    color: var(--terminal-green-muted);
    padding: 4px 8px;
    background: rgba(0, 20, 0, 0.4);
    border-radius: 4px;
}

.history-details {
    flex: 1;
}

.history-accused {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 4px;
}

.history-outcome {
    font-size: 13px;
    color: var(--terminal-green-accent);
    margin-bottom: 4px;
}

.history-reason {
    font-size: 12px;
    color: var(--terminal-green-muted);
    font-style: italic;
}

.history-strength {
    font-size: 11px;
    color: var(--terminal-green-muted);
    margin-top: 4px;
}

/* ========== CASE FILE (TOP TAB) ========== */
/* Styled like an official police case folder / manila file */

.case-file-root {
    font-family: 'Georgia', 'Times New Roman', serif;
    color: #1a1a1a;
    max-width: 720px;
    margin: 0 auto;
    background: linear-gradient(135deg, #f5f0e1 0%, #e8dcc8 50%, #d9cdb4 100%);
    border-radius: 2px;
    position: relative;
    /* Subtle paper texture via noise */
    background-image: 
        url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='0.04'/%3E%3C/svg%3E"),
        linear-gradient(135deg, #f5f0e1 0%, #e8dcc8 50%, #d9cdb4 100%);
}

/* Top edge fold effect */
.case-file-root::before {
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 6px;
    background: linear-gradient(to bottom, rgba(0,0,0,0.12), transparent);
    border-radius: 2px 2px 0 0;
}

.case-file-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    padding: 24px 28px 16px;
    border-bottom: 2px solid #8b7355;
    background: linear-gradient(to bottom, rgba(139,115,85,0.15), transparent);
}

.case-file-title-block {
    display: flex;
    flex-direction: column;
    gap: 2px;
}

.case-file-division {
    font-family: 'Courier New', monospace;
    font-size: 10px;
    letter-spacing: 3px;
    text-transform: uppercase;
    color: #6b5a4a;
    font-weight: 600;
}

.case-file-title {
    font-family: 'Courier New', monospace;
    font-size: 20px;
    letter-spacing: 4px;
    text-transform: uppercase;
    color: #3d2b1f;
    font-weight: 700;
    text-shadow: 1px 1px 0 rgba(255,255,255,0.5);
}

.case-file-meta {
    font-family: 'Courier New', monospace;
    font-size: 11px;
    text-align: right;
    color: #5a4a3a;
    line-height: 1.6;
}

.case-file-meta-value {
    font-weight: 700;
    color: #3d2b1f;
}

.case-file-status {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 2px;
    font-size: 10px;
    font-family: 'Courier New', monospace;
    letter-spacing: 2px;
    text-transform: uppercase;
    font-weight: 700;
    margin-top: 4px;
}

.case-file-status-open {
    background: #fff3cd;
    border: 1px solid #c9a227;
    color: #856404;
}

.case-file-status-solved {
    background: #d4edda;
    border: 1px solid #28a745;
    color: #155724;
}

.case-file-status-failed {
    background: #f8d7da;
    border: 1px solid #dc3545;
    color: #721c24;
}

.case-file-body {
    padding: 24px 28px;
}

.case-file-section {
    margin-bottom: 24px;
}

.case-file-section-title {
    font-family: 'Courier New', monospace;
    font-size: 12px;
    letter-spacing: 3px;
    text-transform: uppercase;
    color: #5a4a3a;
    border-bottom: 1px solid #a89070;
    padding-bottom: 6px;
    margin-bottom: 14px;
    font-weight: 700;
}

.case-file-victim-grid {
    display: grid;
    grid-template-columns: 140px 1fr;
    gap: 8px 16px;
    font-size: 14px;
    background: rgba(255,255,255,0.4);
    padding: 16px;
    border: 1px solid #c4b49a;
    border-radius: 2px;
}

.case-file-victim-label {
    font-family: 'Courier New', monospace;
    color: #6b5a4a;
    text-transform: uppercase;
    letter-spacing: 1px;
    font-size: 11px;
    font-weight: 600;
    padding-top: 2px;
}

.case-file-victim-value {
    color: #2d2d2d;
    line-height: 1.5;
}

.case-file-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
    background: rgba(255,255,255,0.35);
    border: 1px solid #c4b49a;
}

.case-file-table th {
    text-align: left;
    padding: 10px 14px;
    font-family: 'Courier New', monospace;
    font-size: 10px;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: #5a4a3a;
    background: rgba(139,115,85,0.15);
    border-bottom: 1px solid #a89070;
    font-weight: 700;
}

.case-file-table td {
    padding: 12px 14px;
    border-bottom: 1px solid #d4c4a8;
    vertical-align: top;
}

.case-file-table tr:last-child td {
    border-bottom: none;
}

.case-file-table tr:hover {
    background: rgba(139,115,85,0.08);
}

.case-file-cell-name {
    font-weight: 600;
    color: #2d2d2d;
}

.case-file-cell-role {
    color: #5a5a5a;
    font-style: italic;
}

.case-file-cell-status {
    font-size: 12px;
    white-space: nowrap;
}

.case-file-cell-empty {
    text-align: center;
    padding: 24px 14px;
    font-style: italic;
    color: #7a6a5a;
}

.case-file-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 16px;
    padding: 16px 0 8px;
    border-top: 1px dashed #a89070;
    font-size: 12px;
}

.case-file-stamp {
    display: inline-block;
    padding: 6px 14px;
    border: 3px solid #c41e3a;
    color: #c41e3a;
    font-family: 'Courier New', monospace;
    letter-spacing: 3px;
    text-transform: uppercase;
    font-weight: 700;
    font-size: 11px;
    transform: rotate(-4deg);
    opacity: 0.85;
}

.case-file-footer-right {
    text-align: right;
    color: #6b5a4a;
    font-family: 'Courier New', monospace;
    font-size: 10px;
}

.case-file-empty {
    text-align: center;
    padding: 48px 24px;
    color: #7a6a5a;
    font-size: 15px;
}

.case-file-empty-icon {
    font-size: 40px;
    margin-bottom: 12px;
    opacity: 0.7;
}

.case-file-empty-text {
    max-width: 320px;
    margin: 0 auto;
    line-height: 1.5;
}
"""
