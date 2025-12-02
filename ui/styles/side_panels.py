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

.transcript-panel .html-container .suspects-list .suspect-cards-grid .suspect-card {
    flex-direction: column !important;
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

/* ========== SUSPECT RELATIONSHIP LABELS ========== */
.suspect-relationships {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin: 8px 0;
    padding: 6px 0;
    border-top: 1px dashed var(--terminal-green-border-soft);
}

.suspect-relationships-label {
    width: 100%;
    font-family: var(--font-retro-mono);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--terminal-green-muted);
    margin-bottom: 2px;
}

.rel-label {
    display: inline-block;
    font-size: 9px;
    padding: 2px 6px;
    font-family: var(--font-retro-mono);
    border-radius: 0;
}

.rel-accused {
    background: rgba(255, 68, 68, 0.15);
    border: 1px solid rgba(255, 68, 68, 0.4);
    color: #ff6666;
}

.rel-alibi {
    background: rgba(51, 255, 51, 0.15);
    border: 1px solid rgba(51, 255, 51, 0.4);
    color: var(--terminal-green);
}

.rel-mentioned {
    background: rgba(255, 204, 0, 0.15);
    border: 1px solid rgba(255, 204, 0, 0.4);
    color: #ffcc00;
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

/* ========== TIMELINE MAIN TAB ========== */
.timeline-tab .timeline-column {
    padding: 20px;
}

.timeline-main {
    min-height: 400px;
    max-height: 70vh;
    overflow-y: auto;
    padding: 16px;
    background: rgba(0, 20, 0, 0.3);
    border: 1px solid var(--terminal-green-border-soft);
    border-radius: 8px;
}

.timeline-main .timeline-entries {
    padding: 0;
}

.timeline-main .timeline-entry {
    padding: 12px 16px;
    margin-bottom: 12px;
}

/* ========== VERTICAL TABS IN LEFT COLUMN ========== */
.vertical-tabs-container {
    display: flex !important;
    flex-direction: row !important;
    width: 100% !important;
    height: 100% !important;
    gap: 0 !important;
}

/* Left side: Vertical tab navigation buttons */
.vertical-tabs-nav {
    display: flex !important;
    flex-direction: column !important;
    width: 60px !important;
    min-width: 60px !important;
    max-width: 60px !important;
    border-right: 2px solid var(--terminal-green-border-soft) !important;
    background: rgba(0, 20, 0, 0.4) !important;
    padding: 8px 4px !important;
    gap: 4px !important;
}

/* Style vertical tab buttons */
.vertical-tab-btn {
    width: 100% !important;
    padding: 12px 8px !important;
    font-family: var(--font-retro-mono) !important;
    font-size: 16px !important;
    font-weight: 600 !important;
    color: var(--terminal-green-muted) !important;
    background: transparent !important;
    border: 1px solid var(--terminal-green-border-soft) !important;
    border-radius: 0 !important;
    text-align: center !important;
    cursor: pointer !important;
    transition: all 0.2s ease !important;
    min-height: 50px !important;
}

.vertical-tab-btn:hover {
    background: var(--terminal-green-hover) !important;
    color: var(--terminal-green) !important;
    border-color: var(--terminal-green) !important;
}

.vertical-tab-btn:focus {
    background: rgba(51, 255, 51, 0.2) !important;
    color: var(--terminal-green) !important;
    border-color: var(--terminal-green) !important;
    text-shadow: 0 0 8px var(--terminal-green) !important;
}

/* Right side: Tab content area */
.vertical-tabs-content {
    flex: 1 !important;
    padding: 16px !important;
    background: rgba(0, 20, 0, 0.3) !important;
    border: 1px solid var(--terminal-green-border-soft) !important;
    min-height: 400px !important;
    overflow-y: auto !important;
}

/* Vertical tab content styling */
.vertical-tab-content {
    font-family: var(--font-body) !important;
    font-size: 14px !important;
    color: var(--terminal-green) !important;
    padding: 20px !important;
    text-align: center !important;
}

.vertical-tab-panel {
    width: 100% !important;
    height: 100% !important;
}

/* ========== INVESTIGATION TIMELINE ========== */
.investigation-timeline {
    position: relative;
    z-index: 20;
    padding: 12px;
}

.timeline-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--terminal-green-border-soft);
    flex-wrap: wrap;
    gap: 8px;
}

.timeline-title {
    font-family: var(--font-retro-mono);
    font-size: 14px;
    color: var(--terminal-green);
    text-transform: uppercase;
    letter-spacing: 2px;
    text-shadow: 0 0 8px var(--terminal-green);
}

.timeline-legend {
    display: flex;
    gap: 12px;
    font-size: 10px;
    color: var(--terminal-green-muted);
}

.legend-item {
    display: flex;
    align-items: center;
    gap: 4px;
}

.legend-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
}

.legend-dot.alibi {
    background: var(--terminal-green);
}

.legend-dot.witness {
    background: #ffcc00;
}

.legend-dot.clue {
    background: #00ccff;
}

.legend-dot.contradiction {
    background: #ff4444;
    animation: contradiction-pulse 1s ease-in-out infinite;
}

.timeline-content {
    display: flex;
    flex-direction: column;
    gap: 8px;
    max-height: 400px;
    overflow-y: auto;
}

.timeline-row {
    display: flex;
    gap: 12px;
    padding: 8px 0;
    border-bottom: 1px dashed var(--terminal-green-border-soft);
}

.timeline-time {
    width: 70px;
    min-width: 70px;
    font-family: var(--font-retro-mono);
    font-size: 12px;
    color: var(--terminal-green);
    text-shadow: 0 0 6px var(--terminal-green);
    padding-top: 4px;
}

.timeline-events {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.timeline-event {
    display: flex;
    gap: 8px;
    padding: 8px;
    background: rgba(0, 20, 0, 0.4);
    border-left: 3px solid var(--terminal-green);
    border-radius: 0 4px 4px 0;
}

.timeline-event.alibi {
    border-left-color: var(--terminal-green);
}

.timeline-event.witness {
    border-left-color: #ffcc00;
}

.timeline-event.clue {
    border-left-color: #00ccff;
}

.timeline-event.contradiction {
    border-left-color: #ff4444;
    background: rgba(255, 68, 68, 0.1);
    animation: contradiction-glow 2s ease-in-out infinite;
}

@keyframes contradiction-glow {
    0%, 100% { box-shadow: inset 0 0 10px rgba(255, 68, 68, 0.2); }
    50% { box-shadow: inset 0 0 15px rgba(255, 68, 68, 0.4); }
}

.event-icon {
    font-size: 16px;
    line-height: 1;
}

.event-content {
    flex: 1;
    min-width: 0;
}

.event-suspect {
    font-family: var(--font-retro-mono);
    font-size: 11px;
    color: var(--terminal-green);
    margin-bottom: 2px;
    display: flex;
    align-items: center;
    gap: 6px;
}

.verified-badge {
    font-size: 10px;
    color: #00ff00;
    background: rgba(0, 255, 0, 0.2);
    padding: 1px 4px;
    border-radius: 2px;
}

.event-desc {
    font-size: 12px;
    color: var(--terminal-green);
    line-height: 1.4;
}

.event-source {
    font-size: 10px;
    color: var(--terminal-green-muted);
    margin-top: 4px;
    font-style: italic;
}

.timeline-empty {
    text-align: center;
    padding: 40px 20px;
    color: var(--terminal-green-muted);
}

.timeline-empty-icon {
    font-size: 48px;
    margin-bottom: 12px;
    opacity: 0.5;
}

.timeline-empty-text {
    font-family: var(--font-retro-mono);
    font-size: 14px;
    color: var(--terminal-green);
    margin-bottom: 8px;
}

.timeline-empty-hint {
    font-size: 12px;
    line-height: 1.5;
}

.timeline-tip {
    margin-top: 12px;
    padding: 8px;
    background: rgba(255, 204, 0, 0.1);
    border: 1px solid rgba(255, 204, 0, 0.3);
    font-size: 11px;
    color: #ffcc00;
    border-radius: 4px;
}

/* Scrollbar for timeline */
.timeline-content::-webkit-scrollbar {
    width: 6px;
}

.timeline-content::-webkit-scrollbar-track {
    background: rgba(0, 20, 0, 0.3);
}

.timeline-content::-webkit-scrollbar-thumb {
    background: var(--terminal-green-muted);
}

.timeline-content::-webkit-scrollbar-thumb:hover {
    background: var(--terminal-green);
}

/* =========================================================
   CASE BOARD - Visual conspiracy board
   ========================================================= */

.case-board-plot {
    min-height: 400px;
    border-radius: 8px;
    overflow: hidden;
}

/* Main tab version - full height */
.case-board-tab .case-board-column {
    padding: 20px;
}

.case-board-plot-main {
    min-height: 500px;
    max-height: 80vh;
    border-radius: 8px;
    overflow: hidden;
}

/* Override Plotly modebar */
.case-board-plot .modebar {
    background: rgba(0, 0, 0, 0.7) !important;
}

.case-board-plot .modebar-btn {
    color: var(--terminal-green) !important;
}

.case-board-plot .modebar-btn:hover {
    color: #00ff00 !important;
}

/* Text fallback styling */
.case-board-text {
    padding: 20px;
    font-family: var(--font-mono);
    color: var(--terminal-green);
}

.case-board-text .board-title {
    font-size: 16px;
    font-weight: bold;
    margin-bottom: 16px;
    color: #00ff00;
    text-transform: uppercase;
}

.case-board-text .board-section {
    margin: 12px 0;
    font-size: 13px;
}

.case-board-text .board-item {
    margin-left: 16px;
    font-size: 12px;
    color: var(--terminal-green-muted);
}

"""
