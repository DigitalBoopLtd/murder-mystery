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

"""
