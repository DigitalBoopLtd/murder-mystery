"""UI styling for the murder mystery game interface."""

RETRO_CSS = """
/* Import Roblox-style fonts */
@import url('https://fonts.googleapis.com/css2?family=Source+Sans+Pro:wght@400;600;700&family=Inter:wght@400;500;600;700&display=swap');

/* ========== ROOT VARIABLES ========== */
:root {
    --bg-primary: #000033;
    --bg-secondary: #0a0a1a;
    --bg-panel: #1a0033;
    --bg-card: #0d0d26;
    --text-primary: #FFFFFF;
    --text-secondary: #CCCCFF;
    --body-text-color: var(--text-primary);
    --accent-blue: #00FFFF;
    --accent-blue-dark: #00CCCC;
    --accent-green: #00FF00;
    --accent-red: #FF0088;
    --accent-orange: #FF8800;
    --accent-magenta: #FF00FF;
    --accent-yellow: #FFFF00;
    --border-color: #00FFFF;
    --border-dark: #006666;
}

/* ========== UTILITY PATTERNS ========== */
/* Consolidated "hide element" pattern - use on selectors that need complete hiding */
.u-hidden,
.audio-player .play-pause-wrapper,
.audio-player .play-pause-button,
.audio-player .rewind,
.audio-player .skip,
.audio-player .controls,
.audio-player .volume,
.audio-player .playback,
.audio-player .cc-button,
.audio-player .waveform-container,
.audio-player #waveform,
.audio-player .timestamps,
.audio-player time,
.audio-player canvas,
.audio-player button,
.audio-player [role="button"],
.audio-player [class*="button"],
.audio-player [class*="control"]:not(:has(.subtitle-display)),
.audio-player [class*="waveform"],
.audio-player [class*="wave"],
.audio-player [aria-label*="Skip"],
.audio-player [aria-label*="Pause"],
.audio-player [aria-label*="Play"],
.audio-player [aria-label*="volume"],
.audio-player [aria-label*="playback speed"],
.audio-player [data-testid="waveform-controls"],
.audio-player [data-testid="subtitles-toggle"],
.audio-player [class*="download"],
.audio-player [class*="share"],
.audio-player svg:not([class*="subtitle"]),
.audio-player .component-wrapper:not(:has(.subtitle-display)),
[data-testid="waveform-controls"],
[data-testid="status-tracker"].wrap.center.translucent,
[data-testid="status-tracker"].wrap.default.full.hide,
.input-bar [data-testid="status-tracker"],
.audio-player [data-testid="status-tracker"] {
    display: none !important;
    visibility: hidden !important;
    opacity: 0 !important;
    height: 0 !important;
    width: 0 !important;
    overflow: hidden !important;
    pointer-events: none !important;
    position: absolute !important;
    left: -9999px !important;
}

/* ========== ANIMATIONS ========== */
@keyframes button-pulse {
    0%, 100% { 
        box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.5), 0 0 10px rgba(0, 255, 255, 0.4), 0 0 20px rgba(0, 255, 255, 0.2);
        transform: scale(1);
        border-color: rgba(0, 255, 255, 0.8);
    }
    50% { 
        box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.5), 0 0 25px rgba(0, 255, 255, 0.9), 0 0 50px rgba(0, 255, 255, 0.5), 0 0 80px rgba(0, 255, 255, 0.3);
        transform: scale(1.02);
        border-color: rgba(0, 255, 255, 1);
    }
}

@keyframes statusPulse {
    0%, 100% { border-color: var(--border-color); }
    50% { border-color: var(--border-dark); }
}

/* ========== BASE LAYOUT ========== */
.gradio-container {
    background: var(--bg-primary) !important;
    max-width: 100% !important;
    color: var(--text-primary) !important;
}

.gr-box,
.gr-form,
.gr-block,
.gr-group,
.block,
.group {
    background: var(--bg-card) !important;
    border-color: var(--border-dark) !important;
    color: var(--text-primary) !important;
}

/* Ensure portrait-image and ALL its children have transparent background */
.block.portrait-image,
.block.portrait-image *,
.portrait-image,
.portrait-image * {
    background: transparent !important;
    border: none !important;
}

.gr-box {
    border-radius: 4px !important;
    box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.6) !important;
}

.gr-button {
    font-family: 'Source Sans Pro', sans-serif !important;
}

footer { display: none !important; }

/* ========== TITLE BAR ========== */
.title-bar {
    background: var(--bg-secondary);
    border-bottom: 3px solid var(--accent-blue);
    border-top: 2px solid var(--accent-blue);
    padding: 8px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.5);
}

.game-title {
    font-family: 'Courier New', monospace;
    font-size: 18px;
    font-weight: 700;
    color: var(--accent-blue);
    letter-spacing: 3px;
    text-transform: uppercase;
    display: flex;
    align-items: center;
    gap: 20px;
    text-shadow: 2px 2px 0px rgba(0, 0, 0, 0.8), 0 0 20px rgba(0, 255, 255, 0.8), 0 0 40px rgba(0, 255, 255, 0.5), 0 0 60px rgba(0, 255, 255, 0.3);
}

.detective-avatar {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 60px;
    height: 60px;
    border-radius: 50%;
    border: 2px solid var(--accent-blue);
    background: #1a1a2a;
    font-size: 40px;
    line-height: 1;
    box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.6), 0 0 10px rgba(0, 255, 255, 0.3);
    flex-shrink: 0;
}

/* ========== MAIN LAYOUT ========== */
.main-layout-row {
    align-items: stretch !important;
}

@media (max-width: 900px) {
    .main-layout-row {
        flex-direction: column !important;
    }
    .main-layout-row .center-column { order: 1 !important; width: 100% !important; }
    .main-layout-row .side-column-left { order: 2 !important; width: 100% !important; }
    .main-layout-row .side-column-right { order: 3 !important; width: 100% !important; }
    
    .center-column > .gr-group {
        position: relative !important;
        overflow: hidden !important;
    }
}

/* ========== CRT STAGE (Center Column) ========== */
.center-column > .gr-group,
.center-column .gr-group {
    background: #050510 !important;
    border: 4px solid var(--border-color) !important;
    padding: 24px !important;
    min-height: 350px !important;
    position: relative !important;
    overflow: visible !important;
    isolation: isolate !important;
    border-radius: 16px / 12px !important;
    box-shadow: 
        inset 0 0 100px rgba(0, 255, 255, 0.1),
        inset 0 0 30px rgba(0, 255, 255, 0.05),
        0 0 40px rgba(0, 255, 255, 0.3),
        0 0 80px rgba(0, 255, 255, 0.1) !important;
}

/* Scanlines overlay */
.center-column > .gr-group::before,
.center-column .gr-group::before {
    content: '';
    position: absolute;
    inset: 0;
    background: repeating-linear-gradient(0deg, transparent, transparent 1px, rgba(0, 0, 0, 0.3) 1px, rgba(0, 0, 0, 0.3) 2px);
    pointer-events: none;
    z-index: 100;
    border-radius: inherit;
}

/* Screen vignette */
.center-column > .gr-group::after,
.center-column .gr-group::after {
    content: '';
    position: absolute;
    inset: 0;
    background: radial-gradient(ellipse at center, transparent 0%, transparent 60%, rgba(0, 0, 0, 0.4) 100%);
    pointer-events: none;
    z-index: 101;
    border-radius: inherit;
}

/* ========== PORTRAIT IMAGE ========== */
img, .image-frame { border-radius: 4px !important; }
img { border: 4px solid white !important; }

.portrait-image {
    width: 100% !important;
    max-width: 100% !important;
    height: auto !important;
    border: 3px solid var(--accent-blue);
    border-radius: 4px;
    display: block !important;
    margin: 0 auto;
    position: relative !important;
    margin-bottom: 0 !important;
    box-shadow: inset 0 0 10px rgba(0, 0, 0, 0.5);
}

/* Force image elements inside portrait-image to be visible */
/* But respect sr-only, hide classes for accessibility labels */
.portrait-image.portrait-image,
.portrait-image.portrait-image img,
.portrait-image.portrait-image > div,
.portrait-image.portrait-image > div > div,
.portrait-image.portrait-image > div > div > img {
    display: block !important;
    visibility: visible !important;
    opacity: 1 !important;
    position: relative !important;
    z-index: auto !important;
    background: transparent !important;
    height: auto !important;
    width: auto !important;
    max-height: none !important;
    max-width: 100% !important;
    overflow: visible !important;
    left: auto !important;
    top: auto !important;
}

/* Keep Gradio's hidden labels hidden */
.portrait-image .sr-only,
.portrait-image .hide,
.portrait-image [data-testid="block-label"],
.portrait-image label.sr-only {
    position: absolute !important;
    width: 1px !important;
    height: 1px !important;
    padding: 0 !important;
    margin: -1px !important;
    overflow: hidden !important;
    clip: rect(0, 0, 0, 0) !important;
    white-space: nowrap !important;
    border: 0 !important;
}

/* Make sure img elements have proper sizing */
.portrait-image img {
    width: 100% !important;
    height: auto !important;
    max-width: 100% !important;
}

/* Portrait image container positioning */
.center-column > .gr-group > div:has(.portrait-image) {
    position: relative !important;
}

/* Hide image control buttons (share, fullscreen, download) */
/* Only target actual button elements, not containers */
.portrait-image button:not(:has(img)),
.portrait-image button[aria-label],
.portrait-image a[aria-label*="Share"],
.portrait-image a[aria-label*="Download"],
.portrait-image button[aria-label*="Share"],
.portrait-image button[aria-label*="Fullscreen"],
.portrait-image button[aria-label*="Download"],
.portrait-image button[title*="Share"],
.portrait-image button[title*="Fullscreen"],
.portrait-image button[title*="Download"],
.portrait-image div[class*="icon-buttons"],
.portrait-image div[class*="toolbar"]:not(:has(img)),
.portrait-image div[class*="image-button"] {
    display: none !important;
    visibility: hidden !important;
}

/* Ensure portrait images are visible when source is set */
.center-column > .gr-group:has(.portrait-image img[src]:not([src=""])) .block.portrait-image,
.center-column > .gr-group:has(.portrait-image img[src]:not([src=""])) .block.portrait-image img,
.center-column > .gr-group:has(.portrait-image img[src]:not([src=""])) .portrait-image img {
    display: block !important;
    visibility: visible !important;
    opacity: 1 !important;
    background: transparent !important;
    z-index: 2 !important;
    position: relative !important;
}

/* ========== SPEAKER NAME ========== */
.speaker-name {
    font-family: 'Courier New', monospace !important;
    font-size: 16px !important;
    font-weight: 700 !important;
    color: var(--accent-blue) !important;
    text-align: center !important;
    text-transform: uppercase !important;
    letter-spacing: 2px !important;
    padding: 10px 20px !important;
    margin: 0 auto 12px auto !important;
    display: block !important;
    width: fit-content !important;
    min-width: 200px !important;
}

/* ========== AUDIO PLAYER & SUBTITLES ========== */
.audio-player {
    position: relative !important;
    width: 100% !important;
    margin: 0 !important;
    padding: 0 !important;
    border: none !important;
    border-radius: 0 !important;
    min-height: 60px !important;
    max-height: 60px !important;
    overflow: visible !important;
    z-index: 10 !important;
    background: transparent !important;
}

/* Hide audio element visually but keep functional */
.audio-player audio {
    position: absolute !important;
    width: 1px !important;
    height: 1px !important;
    opacity: 0 !important;
    clip: rect(0, 0, 0, 0) !important;
}

/* Hide audio player when empty */
.audio-player:has(.empty),
.block.audio-player:has(.empty) {
    display: none !important;
    height: 0 !important;
    min-height: 0 !important;
}

/* Subtitle display - always visible */
.audio-player .subtitle-display,
.audio-player [data-testid="subtitle-display"] {
    display: block !important;
    visibility: visible !important;
    opacity: 1 !important;
    color: #2d2418 !important;
    text-align: center !important;
    font-size: 20px !important;
    font-family: 'Courier New', monospace !important;
    font-weight: 600 !important;
    margin: 0 !important;
    height: auto !important;
    min-height: 0px !important;
    z-index: 100 !important;
    position: absolute !important;
    bottom: 10px !important;
    width: 100% !important;
}

/* Component wrapper containing subtitles */
.audio-player .component-wrapper:has(.subtitle-display) {
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
    margin: 0 !important;
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
    justify-content: center !important;
}

/* Audio player in context of portrait image */
.center-column > .gr-group:has(.portrait-image img[src]:not([src=""])) .block.audio-player {
    margin: 0 !important;
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
}

/* Audio player without portrait image */
.center-column > .gr-group:not(:has(.portrait-image img[src]:not([src=""]))) .audio-player {
    position: relative !important;
    background: var(--bg-panel) !important;
    border: 1px solid var(--border-color) !important;
    padding: 8px !important;
}

/* ========== INPUT BAR ========== */
.input-bar {
    display: flex !important;
    flex-direction: column !important;
    gap: 0 !important;
    padding: 0 !important;
    background: var(--bg-secondary);
    border-top: 2px solid var(--accent-blue);
    box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.5);
    flex-shrink: 0 !important;
    height: auto !important;
}

.icon-button-wrapper,
.mic-select,
.record-button,
.stop-button {
    background-color: transparent !important;
    --bg-color: transparent !important;
}

.icon-button {
    background-color: #010101 !important;
    --bg-color: #010101 !important;
}

/* ========== SIDE PANELS ========== */
.side-panel {
    background: var(--bg-card) !important;
    border: none !important;
    border-radius: 4px;
    height: fit-content;
    margin-bottom: 12px;
}

.gr-group:has(.panel-title) {
    border: 3px solid var(--border-color) !important;
    border-radius: 4px !important;
    background: var(--bg-card) !important;
    margin-bottom: 12px !important;
    padding: 8px 0 10px 0 !important;
    outline: 2px solid var(--border-dark) !important;
    outline-offset: 0;
    box-shadow: inset 0 0 0 2px var(--border-dark);
}

.gr-group:has(.panel-title) .block {
    border: none !important;
}

.side-panel .block,
.side-panel .prose {
    padding: 0 !important;
    background: var(--bg-card) !important;
}

.panel-title {
    font-family: 'Source Sans Pro', sans-serif;
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
    font-family: 'Source Sans Pro', sans-serif;
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
    font-family: 'Source Sans Pro', sans-serif;
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
    font-family: 'Source Sans Pro', sans-serif;
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
    font-size: 0.85em;
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
    font-size: 0.85em;
    color: var(--text-secondary);
    line-height: 1.4;
}

/* ========== ACCUSATIONS ========== */
.accusations-display {
    font-family: 'Source Sans Pro', sans-serif;
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
    font-family: 'Source Sans Pro', sans-serif;
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

/* ========== START BUTTON ========== */
.start-button {
    font-family: 'Source Sans Pro', sans-serif !important;
    font-size: 16px !important;
    font-weight: 700 !important;
    background: var(--bg-card) !important;
    border: 3px solid rgba(0, 255, 255, 0.8) !important;
    color: var(--accent-blue) !important;
    padding: 14px 32px !important;
    border-radius: 4px !important;
    cursor: pointer !important;
    text-transform: uppercase !important;
    letter-spacing: 2px !important;
    box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.5), 0 0 10px rgba(0, 255, 255, 0.4), 0 0 20px rgba(0, 255, 255, 0.2) !important;
    animation: button-pulse 1s ease-in-out 5 !important;
}

.download-link,
.share-link,
.fullscreen-link {
    display: none !important;
}

.start-button:hover {
    background: var(--accent-blue) !important;
    color: #000033 !important;
    transform: translateY(-2px) !important;
    box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.3) !important;
    text-shadow: none !important;
}

.start-button-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
}

.start-button-container:has(.start-button.hidden) {
    display: none !important;
    height: 0 !important;
    min-height: 0 !important;
}

.loading-message {
    font-size: 20px !important;
    color: var(--accent-blue) !important;
}

.image-container {
    padding-bottom: 2px;
    border-radius: 6px;
}

/* ========== STATUS TRACKER ========== */
[data-testid="status-tracker"]:not(.translucent):not(.wrap.center):not(.hide) {
    position: fixed !important;
    top: 50% !important;
    left: 50% !important;
    transform: translate(-50%, -50%) !important;
    z-index: 9999 !important;
    min-width: 200px !important;
    max-width: 400px !important;
    min-height: 124px !important;
    max-height: 180px !important;
    background: #000033 !important;
    border: 3px solid var(--border-color) !important;
    border-radius: 4px !important;
    padding: 16px 28px !important;
    outline: 3px solid var(--border-dark) !important;
    outline-offset: 0px !important;
    box-shadow: 
        inset 0 0 0 2px var(--border-dark),
        inset 0 0 0 4px #000033,
        inset 0 0 0 5px var(--border-color),
        inset 0 2px 8px rgba(0, 0, 0, 0.8) !important;
    animation: statusPulse 2s ease-in-out infinite !important;
}

[data-testid="status-tracker"]:not(.translucent):not(.wrap.center):not(.hide)::before,
[data-testid="status-tracker"]:not(.translucent):not(.wrap.center):not(.hide)::after {
    content: "◆";
    position: absolute;
    color: var(--border-color);
    font-size: 12px;
    left: 50%;
    transform: translateX(-50%);
}

[data-testid="status-tracker"]:not(.translucent):not(.wrap.center):not(.hide)::before { top: -8px; }
[data-testid="status-tracker"]:not(.translucent):not(.wrap.center):not(.hide)::after { bottom: -8px; }

[data-testid="status-tracker"]:not(.translucent):not(.wrap.center):not(.hide) .progress-text,
[data-testid="status-tracker"]:not(.translucent):not(.wrap.center):not(.hide) .meta-text,
[data-testid="status-tracker"]:not(.translucent):not(.wrap.center):not(.hide) .meta-text-center,
[data-testid="status-tracker"]:not(.translucent):not(.wrap.center):not(.hide) .eta,
[data-testid="status-tracker"]:not(.translucent):not(.wrap.center):not(.hide) span {
    color: var(--accent-blue) !important;
    font-family: 'Courier New', monospace !important;
    font-weight: 700 !important;
    font-size: 18px !important;
    text-transform: uppercase !important;
    letter-spacing: 2px !important;
    background: transparent !important;
}

[data-testid="status-tracker"]:not(.translucent):not(.wrap.center):not(.hide) svg {
    color: var(--border-color) !important;
    width: 24px !important;
    height: 24px !important;
    margin-right: 12px !important;
    opacity: 0.7 !important;
}

[data-testid="status-tracker"].hide,
[data-testid="status-tracker"]:empty {
    display: none !important;
    opacity: 0 !important;
    visibility: hidden !important;
}

[data-testid="status-tracker"] {
    transition: opacity 0.3s ease, transform 0.3s ease !important;
}
"""
