"""Side panels CSS styles (terminal theme)."""

CSS_SIDE_PANELS = """/* ========== SIDE PANELS - BASE ========== */
.side-panel {
    height: fit-content;
    margin-bottom: 24px;
}

/* Add margin to panels to account for bezel */
.side-column-left .gr-group:has(.panel-title),
.side-column-right .gr-group:has(.panel-title) {
    margin: 16px 8px 24px 8px;
}

.gr-group:has(.panel-title) .block {
    border: none !important;
}

.side-panel .block,
.side-panel .prose {
    padding: 0 !important;
}

/* ========== SIDE PANELS - GREEN PHOSPHOR TERMINAL ========== */
.side-column-left .gr-group:has(.panel-title),
.side-column-right .gr-group:has(.panel-title) {
    background: #040804 !important;
    /* Screen glass edge - subtle green tint */
    border: 2px solid #0a2a0a !important;
    border-radius: 6px !important;
    position: relative;
    overflow: hidden;
    padding: 12px 10px 10px 10px !important;
    box-sizing: border-box;
    /* CRT monitor bezel - layered effect using box-shadow */
    /* Inner bevel (dark) -> Mid bezel (gray) -> Outer bevel (highlight) -> Ambient glow */
    box-shadow: 
        inset 0 0 20px rgba(0, 0, 0, 0.8),
        0 0 0 4px #1a1a1a,
        0 0 0 6px #3a3a3a,
        0 0 0 10px #2d2d2d,
        0 0 0 12px #1a1a1a,
        0 0 20px var(--terminal-green-glow) !important;
}

/* Power LED indicator */
.side-column-left .gr-group:has(.panel-title) .panel-title::after,
.side-column-right .gr-group:has(.panel-title) .panel-title::after {
    content: '●';
    position: absolute;
    right: 8px;
    top: 50%;
    transform: translateY(-50%);
    font-size: 8px;
    color: var(--terminal-green);
    text-shadow: 0 0 6px var(--terminal-green), 0 0 12px var(--terminal-green);
    animation: led-pulse 2s ease-in-out infinite;
}

@keyframes led-pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.6; }
}

/* Terminal scanlines */
.side-column-left .gr-group:has(.panel-title)::before,
.side-column-right .gr-group:has(.panel-title)::before {
    content: '';
    position: absolute;
    inset: 0;
    background: repeating-linear-gradient(
        0deg,
        transparent,
        transparent 2px,
        rgba(0, 0, 0, 0.4) 2px,
        rgba(0, 0, 0, 0.4) 4px
    );
    pointer-events: none;
    z-index: 10;
}

/* Phosphor screen glow */
.side-column-left .gr-group:has(.panel-title)::after,
.side-column-right .gr-group:has(.panel-title)::after {
    content: '';
    position: absolute;
    inset: 0;
    background: radial-gradient(ellipse at center, var(--terminal-green-vignette) 0%, transparent 70%);
    pointer-events: none;
    z-index: 1;
}

/* Terminal header with system prompt */
.side-column-left .panel-title,
.side-column-right .panel-title {
    font-family: var(--font-retro-mono) !important;
    color: var(--terminal-green) !important;
    font-size: 13px !important;
    font-weight: 400 !important;
    text-shadow: 0 0 8px var(--terminal-green), 0 0 16px var(--terminal-green-soft-strong);
    letter-spacing: 2px !important;
    text-transform: uppercase !important;
    padding: 4px 8px !important;
    margin-bottom: 8px !important;
    border-bottom: 1px solid var(--terminal-green-border-strong);
    position: relative;
    z-index: 20;
}

/* Add terminal prompt before title */
.side-column-left .panel-title::before,
.side-column-right .panel-title::before {
    content: 'C:\\> ';
    opacity: 0.7;
}

/* Left panel content */
.side-column-left .transcript-panel,
.side-column-left .suspects-list {
    color: var(--terminal-green) !important;
    font-family: var(--font-body) !important;
    font-size: 14px !important;
    line-height: 1.6 !important;
    position: relative;
    z-index: 20;
}

.side-column-left .side-panel .block,
.side-column-left .side-panel .prose,
.side-column-right .side-panel .block,
.side-column-right .side-panel .prose {
    background: transparent !important;
}

/* Suspect items in terminal style */
.side-column-left .suspect-item {
    background: rgba(0, 20, 0, 0.4) !important;
    border: 1px solid rgba(51, 255, 51, 0.3) !important;
    border-radius: 0 !important;
    margin-bottom: 6px;
    font-family: var(--font-body) !important;
    position: relative;
    z-index: 20;
}

.side-column-left .suspect-item summary {
    color: var(--terminal-green) !important;
    font-weight: 400;
}

.side-column-left .suspect-item summary::before {
    color: var(--terminal-green) !important;
    content: '>' !important;
    text-shadow: 0 0 6px var(--terminal-green);
}

.side-column-left .suspect-item[open] summary::before {
    content: 'v' !important;
    transform: none !important;
}

.side-column-left .suspect-item summary:hover {
    background: var(--terminal-green-hover) !important;
}

.side-column-left .suspect-details {
    background: rgba(0, 30, 0, 0.5) !important;
    border-top: 1px solid var(--terminal-green-border-soft) !important;
    color: var(--terminal-green) !important;
}

.side-column-left .suspect-role-preview {
    color: var(--terminal-green-accent) !important;
}

.side-column-left .suspect-check {
    color: var(--terminal-green-accent) !important;
    text-shadow: 0 0 6px var(--terminal-green);
}

/* Left & right panel accordion buttons */
.side-column-left button.label-wrap,
.side-column-right button.label-wrap {
    background: transparent !important;
    color: var(--terminal-green) !important;
}

.side-column-left button.label-wrap:hover,
.side-column-right button.label-wrap:hover {
    background: var(--terminal-green-hover) !important;
}

.side-column-left button.label-wrap svg,
.side-column-right button.label-wrap svg {
    color: var(--terminal-green) !important;
    filter: drop-shadow(0 0 4px var(--terminal-green));
}

/* Location items - terminal style */
.side-column-right .location-item {
    font-family: var(--font-body) !important;
    font-size: 14px !important;
    color: #ffffff !important;
    background: transparent !important;
    border-radius: 0 !important;
    padding: 4px 8px !important;
    margin-bottom: 2px !important;
    position: relative;
    z-index: 20;
}

.side-column-right .location-item::before {
    content: '> ';
    opacity: 0.6;
}

.side-column-right .location-item.searched {
    color: var(--terminal-green-muted) !important;
    text-decoration: line-through;
    opacity: 0.6;
}

.side-column-right .location-check {
    color: var(--terminal-green-accent) !important;
    text-shadow: 0 0 6px var(--terminal-green);
}

/* Clue items - terminal log entries */
.side-column-right .clue-item {
    font-family: var(--font-body) !important;
    font-size: 11px !important;
    color: var(--terminal-green) !important;
    background: rgba(0, 20, 0, 0.4) !important;
    border-left: 2px solid var(--terminal-green) !important;
    border-radius: 0 !important;
    padding: 6px 10px !important;
    margin-bottom: 4px !important;
    position: relative;
    z-index: 20;
    text-shadow: 0 0 4px rgba(51, 255, 51, 0.3);
}

.side-column-right .clue-item::before {
    content: '[LOG] ';
    color: var(--terminal-green-muted);
    font-weight: 700;
}

/* Accusations display - terminal warning style */
.side-column-right .accusations-display {
    font-family: var(--font-body) !important;
    font-size: 12px !important;
    color: var(--terminal-green) !important;
    position: relative;
    z-index: 20;
    padding: 8px;
}

.side-column-right .accusations-pip {
    background: var(--terminal-green) !important;
    width: 12px !important;
    height: 12px !important;
    border: 1px solid var(--terminal-green-muted);
}

.side-column-right .accusations-pip.used {
    background: #ff3333 !important;
    border-color: #8b0000;
    animation: pip-warning 1s ease-in-out infinite;
}

@keyframes pip-warning {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}

/* Terminal cursor blink effect on last clue */
.side-column-right .clue-item:last-child::after {
    content: '█';
    animation: cursor-blink 1s step-end infinite;
    margin-left: 4px;
    color: var(--terminal-green);
}

@keyframes cursor-blink {
    0%, 50% { opacity: 1; }
    51%, 100% { opacity: 0; }
}

/* Right panel accordion buttons */
/* (Right panel accordion buttons share base styles with left via unified selector above) */

/* ========== SUSPECT EMOTIONAL STATE METERS ========== */
.suspect-meters {
    margin: 8px 0;
    padding: 6px 0;
    border-top: 1px dashed var(--terminal-green-border-soft);
}

.meter-row {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 4px;
    font-size: 10px;
}

.meter-label {
    width: 40px;
    color: var(--terminal-green-muted);
    font-family: var(--font-retro-mono);
    font-size: 11px;
    letter-spacing: 1px;
}

.meter-bar {
    flex: 1;
    height: 8px;
    background: rgba(0, 20, 0, 0.6);
    border: 1px solid var(--terminal-green-border-soft);
    border-radius: 0;
    overflow: hidden;
}

.meter-fill {
    height: 100%;
    transition: width 0.3s ease, background 0.3s ease;
}

.meter-value {
    width: 32px;
    text-align: right;
    color: var(--terminal-green);
    font-family: var(--font-retro-mono);
    font-size: 10px;
}

/* ========== CONTRADICTION INDICATORS ========== */
.contradiction-badge {
    display: inline-block;
    background: rgba(255, 68, 68, 0.2);
    border: 1px solid #ff4444;
    color: #ff6666;
    font-size: 9px;
    padding: 2px 6px;
    margin-left: 8px;
    font-family: var(--font-retro-mono);
    animation: contradiction-pulse 2s ease-in-out infinite;
}

@keyframes contradiction-pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.7; }
}

/* ========== DETECTIVE NOTEBOOK ========== */
.detective-notebook {
    position: relative;
    z-index: 20;
}

.notebook-empty {
    text-align: center;
    padding: 20px;
    color: var(--terminal-green-muted);
    font-family: var(--font-body);
}

.notebook-icon {
    font-size: 32px;
    margin-bottom: 8px;
    opacity: 0.6;
}

.notebook-hint {
    font-size: 11px;
    margin-top: 8px;
    opacity: 0.7;
    font-style: italic;
}

.section-header {
    font-family: var(--font-retro-mono);
    font-size: 12px;
    color: var(--terminal-green);
    letter-spacing: 2px;
    padding: 6px 8px;
    margin-bottom: 8px;
    border-bottom: 1px solid var(--terminal-green-border-soft);
    text-shadow: 0 0 6px var(--terminal-green);
}

.contradictions-section {
    margin-bottom: 16px;
    background: rgba(255, 68, 68, 0.05);
    border: 1px solid rgba(255, 68, 68, 0.3);
    padding: 8px;
}

.contradictions-section .section-header {
    color: #ff6666;
    border-color: rgba(255, 68, 68, 0.3);
    text-shadow: 0 0 6px rgba(255, 68, 68, 0.5);
}

.contradiction-item {
    padding: 8px;
    margin-bottom: 6px;
    background: rgba(255, 68, 68, 0.1);
    border-left: 2px solid #ff4444;
}

.contradiction-suspect {
    font-family: var(--font-retro-mono);
    font-size: 11px;
    color: #ff6666;
    margin-bottom: 4px;
}

.contradiction-detail {
    font-size: 11px;
    color: var(--terminal-green);
    line-height: 1.4;
}

.timeline-section {
    max-height: 300px;
    overflow-y: auto;
}

.timeline-entries {
    padding: 0 4px;
}

.notebook-entry {
    padding: 8px;
    margin-bottom: 6px;
    background: rgba(0, 20, 0, 0.4);
    border-left: 2px solid var(--terminal-green-muted);
    font-size: 11px;
}

.notebook-entry.contradiction-entry {
    border-left-color: #ff4444;
    background: rgba(255, 68, 68, 0.08);
}

.entry-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
}

.entry-turn {
    font-family: var(--font-retro-mono);
    font-size: 10px;
    color: var(--terminal-green-muted);
    background: rgba(0, 30, 0, 0.5);
    padding: 2px 6px;
}

.entry-suspect {
    font-family: var(--font-retro-mono);
    font-size: 11px;
    color: var(--terminal-green);
    font-weight: 600;
}

.contradiction-icon {
    margin-left: auto;
    animation: contradiction-pulse 1.5s ease-in-out infinite;
}

.entry-question {
    color: var(--terminal-green-accent);
    margin-bottom: 4px;
    font-style: italic;
    line-height: 1.4;
}

.entry-answer {
    color: var(--terminal-green);
    line-height: 1.4;
}

/* Scrollbar styling for notebook */
.timeline-section::-webkit-scrollbar {
    width: 6px;
}

.timeline-section::-webkit-scrollbar-track {
    background: rgba(0, 20, 0, 0.3);
}

.timeline-section::-webkit-scrollbar-thumb {
    background: var(--terminal-green-muted);
    border-radius: 0;
}

.timeline-section::-webkit-scrollbar-thumb:hover {
    background: var(--terminal-green);
}

"""
