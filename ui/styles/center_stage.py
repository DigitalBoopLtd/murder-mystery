"""Center stage CSS styles (main layout, CRT stage, portrait, speaker, audio)."""

CSS_CENTER_STAGE = """/* ========== MAIN LAYOUT ========== */
.main-layout-row {
    align-items: stretch !important;
}

/* ========== DESKTOP: Hide bottom tabs, show side panels ========== */
@media (min-width: 901px) {
    /* Hide the bottom info tabs on desktop - side panels show this info */
    .info-tabs {
        display: none !important;
    }
    
    /* Ensure side panels are visible */
    .side-column-left,
    .side-column-right {
        display: flex !important;
    }
}

/* ========== MOBILE/TABLET: Hide side panels, show bottom tabs ========== */
@media (max-width: 900px) {
    .main-layout-row {
        flex-direction: column !important;
    }
    
    /* Only show center column on mobile */
    .main-layout-row .center-column { 
        order: 1 !important; 
        width: 100% !important; 
    }
    
    /* Hide side panels on mobile - use bottom tabs instead */
    .main-layout-row .side-column-left,
    .main-layout-row .side-column-right,
    .side-column-left,
    .side-column-right {
        display: none !important;
    }
    
    /* Show bottom tabs on mobile */
    .info-tabs {
        display: block !important;
        margin-top: 16px;
    }
    
    /* Make the CRT stage more compact on mobile */
    .center-column > .gr-group {
        position: relative !important;
        overflow: hidden !important;
        aspect-ratio: 4 / 3; /* More square aspect for mobile */
        padding: 12px !important;
    }
    
    /* Adjust input bar for mobile */
    .input-bar {
        padding: 8px !important;
    }
    
    /* Make setup wizard full width on mobile */
    .setup-wizard {
        min-height: 300px;
        padding: 16px;
    }
    
    .wizard-settings {
        padding: 12px;
    }
    
    .wizard-buttons {
        flex-direction: column;
        gap: 12px;
    }
    
    .wizard-primary-btn {
        max-width: 100% !important;
        width: 100% !important;
    }
}

/* ========== CRT STAGE (Center Column) ========== */
.center-column > .gr-group,
.center-column .gr-group,
.center-column .crt-stage {
    background: #050510 !important;
    border: 4px solid var(--border-color) !important;
    padding: 24px !important;
    /* Enforce a 16:9 screen-like aspect ratio for the main CRT display */
    aspect-ratio: 16 / 9;
    position: relative !important;
    overflow: visible !important;
    isolation: isolate !important;
    border-radius: 16px / 12px !important;
    box-shadow: 
        inset 0 0 100px rgba(0, 255, 255, 0.1),
        inset 0 0 30px rgba(0, 255, 255, 0.05),
        0 0 40px rgba(0, 255, 255, 0.3),
        0 0 80px rgba(0, 255, 255, 0.1) !important;
    display: flex !important;
    flex-direction: column !important;
    align-items: stretch !important;
}

/* Hide unwanted elements that appear in center column during processing */
/* Hide any blocks that aren't our main components (speaker, portrait, audio, status tracker) */
.center-column > .gr-group > .block:not(:has(.speaker-name)):not(:has(.portrait-image)):not(:has(#mm-audio-player)):not(:has([data-testid="status-tracker"]:not(.hide):not(:empty))),
.center-column > .gr-group > .gr-block:not(:has(.speaker-name)):not(:has(.portrait-image)):not(:has(#mm-audio-player)):not(:has([data-testid="status-tracker"]:not(.hide):not(:empty))) {
    /* Only hide if empty or contains unwanted text/inputs */
}

/* Hide textareas, inputs, and textboxes in center column (except status tracker content) */
.center-column > .gr-group textarea:not([data-testid="status-tracker"] *),
.center-column > .gr-group input[type="text"]:not([data-testid="status-tracker"] *),
.center-column > .gr-group .gr-textbox:not([data-testid="status-tracker"] *),
.center-column > .gr-group .gr-textarea:not([data-testid="status-tracker"] *) {
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

/* Hide portrait container when no image is loaded */
.portrait-image:not(:has(img[src])),
.portrait-image:has(img[src=""]) {
    display: none !important;
    height: 0 !important;
    min-height: 0 !important;
    overflow: hidden !important;
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
    font-family: var(--font-retro-mono) !important;
    font-size: 22px !important;
    font-weight: 700 !important;
    color: #2d2418 !important;
    text-align: center !important;
    text-transform: uppercase !important;
    letter-spacing: 2px !important;
    padding: 10px 20px !important;
    margin: 0 auto 12px auto !important;
    display: block !important;
    width: fit-content !important;
    min-width: 200px !important;
}

/* Ensure the speaker-name wrapper uses the main stage background
   rather than the default card background. This removes the dark
   card strip under the (initially hidden) speaker name. */
.center-column .block.svelte-1plpy97:has(.speaker-name),
.center-column .block:has(.speaker-name),
.center-column .html-container,
.center-column .html-container .prose {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
    margin: 0 !important;
}

/* Make the styler wrapper stretch to full height */
.center-column > .gr-group > .styler {
    height: 100% !important;
    display: flex !important;
    flex-direction: column !important;
}

/* ========== AUDIO PLAYER & SUBTITLES ========== */
/* Main audio player container - use ID for precision */
#mm-audio-player {
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
#mm-audio-player audio {
    position: absolute !important;
    width: 1px !important;
    height: 1px !important;
    opacity: 0 !important;
    clip: rect(0, 0, 0, 0) !important;
}

/* Hide audio player when empty */
#mm-audio-player:has(.empty) {
    display: none !important;
    height: 0 !important;
    min-height: 0 !important;
}

/* Subtitle display - always visible */
#mm-audio-player .subtitle-display,
#mm-audio-player [data-testid="subtitle-display"] {
    display: block !important;
    visibility: visible !important;
    opacity: 1 !important;
    color: #2d2418 !important;
    text-align: center !important;
    font-size: 24px !important;
    font-family: var(--font-retro-mono) !important;
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
#mm-audio-player .component-wrapper:has(.subtitle-display) {
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
.center-column > .gr-group:has(.portrait-image img[src]:not([src=""])) #mm-audio-player {
    margin: 0 !important;
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
}

/* Audio player without portrait image */
.center-column > .gr-group:not(:has(.portrait-image img[src]:not([src=""]))) #mm-audio-player {
    position: relative !important;
    background: var(--bg-panel) !important;
    border: 1px solid var(--border-color) !important;
    padding: 8px !important;
}

/* ========== API KEYS SECTION ========== */

/* Settings tab styling */
.settings-tab .settings-column {
    padding: 20px;
    max-width: 800px;
}

.api-keys-group {
    padding: 16px;
    background: rgba(0, 20, 0, 0.3);
    border: 1px solid var(--terminal-green-border-soft);
    border-radius: 8px;
    margin: 16px 0;
}

.api-keys-group input[type="password"] {
    background: rgba(0, 30, 0, 0.5) !important;
    border: 1px solid var(--terminal-green-border-soft) !important;
}

.api-keys-group input[type="password"]:focus {
    border-color: var(--terminal-green) !important;
}

/* Legacy accordion styling (can be removed if not used) */
.api-keys-accordion {
    margin-bottom: 16px !important;
}

.api-keys-accordion .label-wrap {
    background: rgba(255, 204, 0, 0.1) !important;
    border: 1px solid rgba(255, 204, 0, 0.3) !important;
}

.api-keys-info {
    font-size: 12px;
    color: var(--terminal-green-muted);
    margin-bottom: 12px;
    padding: 8px;
    background: rgba(0, 20, 0, 0.3);
    border-radius: 4px;
    border-left: 3px solid var(--terminal-green);
}

.api-keys-info p {
    margin: 0;
}

.key-status-container {
    display: flex;
    align-items: center;
    padding-left: 8px;
}

.key-status {
    font-size: 12px;
    font-family: var(--font-mono);
    padding: 4px 8px;
    border-radius: 4px;
}

.key-ok {
    color: #00ff00;
    background: rgba(0, 255, 0, 0.1);
}

.key-env {
    color: #00ccff;
    background: rgba(0, 204, 255, 0.1);
}

.key-error {
    color: #ff4444;
    background: rgba(255, 68, 68, 0.1);
}

.key-missing {
    color: #ff8800;
    background: rgba(255, 136, 0, 0.1);
}

.key-optional {
    color: #888888;
    background: rgba(136, 136, 136, 0.1);
}

.save-keys-btn {
    background: rgba(255, 204, 0, 0.2) !important;
    border: 1px solid rgba(255, 204, 0, 0.5) !important;
    color: #ffcc00 !important;
}

.save-keys-btn:hover {
    background: rgba(255, 204, 0, 0.3) !important;
}

.keys-ready {
    color: #00ff00;
    font-size: 13px;
    font-weight: bold;
}

.keys-not-ready {
    color: #ff8800;
    font-size: 13px;
}

.keys-overall-status {
    padding: 8px;
}

"""
