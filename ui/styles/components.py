"""Component-specific CSS styles."""

CSS_COMPONENTS = """
/* ========== UTILITY PATTERNS ========== */
/* Hide utility class */
.u-hidden {
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

/* Hide all built-in audio player controls - use precise ID selector */
#mm-audio-player button,
#mm-audio-player [role="button"],
#mm-audio-player [class*="button"],
#mm-audio-player [class*="control"]:not(:has(.subtitle-display)),
#mm-audio-player [class*="waveform"],
#mm-audio-player [class*="wave"],
#mm-audio-player [data-testid="waveform-controls"],
#mm-audio-player [data-testid="subtitles-toggle"],
#mm-audio-player [class*="download"],
#mm-audio-player [class*="share"],
#mm-audio-player svg:not([class*="subtitle"]),
#mm-audio-player .component-wrapper:not(:has(.subtitle-display)),
#mm-audio-player canvas,
#mm-audio-player time {
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

/* Hide status trackers that appear in wrong places (input bar, audio player, inline) */
/* Only the centered modal should be visible - handled by dedicated status tracker section below */
.input-bar [data-testid="status-tracker"],
#mm-audio-player [data-testid="status-tracker"],
[data-testid="status-tracker"].wrap.default.full.hide,
[data-testid="status-tracker"].wrap.default:not(.full),
[data-testid="status-tracker"].wrap.default.full:not(.center) {
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

/* Hide duplicate/extra status tracker wrappers that appear during processing */
/* Only hide wrapper divs that don't contain the visible status tracker */
.wrap.default.full:not(:has([data-testid="status-tracker"]:not(.hide):not(:empty))),
.wrap.default:not(.full):not(:has([data-testid="status-tracker"]:not(.hide):not(:empty))) {
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

/* Hide unwanted Gradio UI elements that appear during processing in center column */
/* Hide empty input/textarea/textbox fields */
.center-column textarea:empty,
.center-column input[type="text"]:empty,
.center-column .gr-textbox:empty,
.center-column .gr-textbox:not(:has(*)) {
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

/* Hide empty blocks in center column that aren't our main components */
.center-column > .gr-group > .block:not(:has(.speaker-name)):not(:has(.portrait-image)):not(:has(#mm-audio-player)):not(:has([data-testid="status-tracker"]:not(.hide):not(:empty))):empty,
.center-column > .gr-group > .gr-block:not(:has(.speaker-name)):not(:has(.portrait-image)):not(:has(#mm-audio-player)):not(:has([data-testid="status-tracker"]:not(.hide):not(:empty))):empty {
    display: none !important;
    visibility: hidden !important;
    opacity: 0 !important;
    height: 0 !important;
    min-height: 0 !important;
    overflow: hidden !important;
}

/* Hide any stray text/percentage indicators that appear during processing */
/* Target text that contains percentage signs but isn't in status tracker */
.center-column > .gr-group *:not([data-testid="status-tracker"] *):not(.speaker-name *):not(.portrait-image *):not(#mm-audio-player *) {
    /* Only hide if it's clearly a progress indicator - be conservative */
}

/* ========== BASE LAYOUT ========== */
.gradio-container {
    background: var(--bg-primary) !important;
    max-width: 100% !important;
    color: var(--text-primary) !important;
    /* Ensure all generic surfaces & inputs use dark theme by default */
    --background-fill-primary: var(--bg-card);
    --background-fill-secondary: var(--bg-panel);
    --input-background-fill: var(--bg-card);
    --input-shadow: none;
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

/* Settings tab: make input containers & labels transparent (no white cards),
   but keep dropdown menus on a solid dark background. */
.settings-column {
    --input-background-fill: transparent;
    --input-shadow: none;
    --input-background-fill-focus: transparent;
    --input-shadow-focus: none;
    /* Use our dark card color for any generic primary fills (e.g. dropdown menus) */
    --background-fill-primary: var(--bg-card);
    --checkbox-label-background-fill: transparent;
    --checkbox-label-shadow: none;
}

.settings-column label {
    background: transparent !important;
    box-shadow: none !important;
}

/* Prevent settings inputs/blocks from flashing white on focus */
.settings-column .block,
.settings-column .block:focus-within {
    background: transparent !important;
    box-shadow: none !important;
}

/* Outer input wrapper (dropdown/inputs) - kill light focus-within background */
.settings-column .wrap.svelte-1xfsv4t,
.settings-column .wrap.svelte-1xfsv4t:focus-within {
    background: transparent !important;
    box-shadow: none !important;
}

.settings-column input,
.settings-column input.svelte-1xfsv4t {
    background: transparent !important;
    color: var(--body-text-color) !important;
}

/* Inner label wrapper for radios / dropdown trigger text - keep dark on focus */
.settings-column .wrap-inner.svelte-1xfsv4t,
.settings-column .wrap-inner.svelte-1xfsv4t:focus,
.settings-column .wrap-inner.svelte-1xfsv4t:focus-within {
    background-color: transparent !important;
    box-shadow: none !important;
}

/* Inner Gradio settings form wrapper (prevents large light-gray panel) */
.settings-column div.svelte-ptprg1 {
    background: transparent !important;
    box-shadow: none !important;
    border-color: var(--border-dark) !important;
}

/* Dropdown trigger & visible value area in Settings */
.settings-column [role="combobox"],
.settings-column select {
    background-color: var(--bg-card) !important;
    color: var(--body-text-color) !important;
    box-shadow: none !important;
}

.settings-column [role="combobox"]:focus,
.settings-column [role="combobox"]:focus-within,
.settings-column select:focus {
    background-color: var(--bg-card) !important;
    color: var(--body-text-color) !important;
}

/* Global dropdown menus/options: keep dark theme even when portal is outside settings column */
[role="listbox"],
[role="listbox"] [role="option"],
[role="option"],
select option {
    background-color: var(--bg-card) !important;
    color: var(--body-text-color) !important;
}

/* Global fix for Svelte checkbox/radio-style labels (used by dropdown triggers, etc.)
   Ensure they never flash white, and match our retro dark card styling instead. */
label.svelte-19qdtil {
    background: var(--bg-card) !important;
    border-color: var(--border-dark) !important;
    box-shadow: none !important;
    color: var(--text-primary) !important;
}

label.svelte-19qdtil:hover {
    background: var(--bg-panel) !important;
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
    font-family: var(--font-retro-mono) !important;
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
    font-family: var(--font-retro-title);
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

/* ========== SIDE PANELS - BASE ========== */
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

/* ========== BASE PANEL TITLE (fallback) ========== */
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

/* ========== START BUTTON ========== */
.start-button {
    font-family: 'Press Start 2P', cursive !important;
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

/* ========== STATUS TEXT ========== */
.status-text {
    text-align: center !important;
    font-size: 16px !important;
    color: var(--accent-blue) !important;
    padding: 12px 16px !important;
    min-height: 24px !important;
    background: transparent !important;
    border: none !important;
}

.status-text:empty {
    display: none !important;
}

.image-container {
    padding-bottom: 2px;
    border-radius: 6px;
}

/* ========== STATUS TRACKER ========== */
/* Style ALL status trackers consistently - one centered modal */
[data-testid="status-tracker"]:not(.hide):not(:empty) {
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
    /* Center content */
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
    justify-content: center !important;
    text-align: center !important;
}

[data-testid="status-tracker"]:not(.hide):not(:empty)::before,
[data-testid="status-tracker"]:not(.hide):not(:empty)::after {
    content: "◆";
    position: absolute;
    color: var(--border-color);
    font-size: 12px;
    left: 50%;
    transform: translateX(-50%);
}

[data-testid="status-tracker"]:not(.hide):not(:empty)::before { top: -8px; }
[data-testid="status-tracker"]:not(.hide):not(:empty)::after { bottom: -8px; }

[data-testid="status-tracker"]:not(.hide):not(:empty) .progress-text,
[data-testid="status-tracker"]:not(.hide):not(:empty) .meta-text,
[data-testid="status-tracker"]:not(.hide):not(:empty) .meta-text-center,
[data-testid="status-tracker"]:not(.hide):not(:empty) span {
    color: var(--accent-blue) !important;
    font-family: var(--font-retro-mono) !important;
    font-weight: 700 !important;
    font-size: 18px !important;
    text-transform: uppercase !important;
    letter-spacing: 2px !important;
    background: transparent !important;
    text-align: center !important;
}

[data-testid="status-tracker"]:not(.hide):not(:empty) svg {
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

/* Hide status trackers that appear during component updates (like when audio stops) */
/* These brief flashes don't have proper processing content - hide them immediately */
/* The main processing status tracker has .progress-text/.meta-text so it will still show */
[data-testid="status-tracker"]:not(.hide):not(:empty):not(:has(.progress-text)):not(:has(.meta-text)):not(:has(.meta-text-center)):not(:has(span:not(:empty))) {
    display: none !important;
    opacity: 0 !important;
    visibility: hidden !important;
    height: 0 !important;
    width: 0 !important;
    overflow: hidden !important;
    pointer-events: none !important;
    position: absolute !important;
    left: -9999px !important;
}

[data-testid="status-tracker"] {
    transition: opacity 0.1s ease, transform 0.1s ease !important;
}
"""

