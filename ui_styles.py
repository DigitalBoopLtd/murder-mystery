"""UI styling for the murder mystery game interface."""

RETRO_CSS = """
/* Import Roblox-style fonts */
@import url('https://fonts.googleapis.com/css2?family=Source+Sans+Pro:wght@400;600;700&family=Inter:wght@400;500;600;700&display=swap');

/* Root variables for theming - Amiga 90s dark mode palette */
:root {
    --bg-primary: #000033;
    --bg-secondary: #0a0a1a;
    --bg-panel: #1a0033;
    --bg-card: #0d0d26;
    --text-primary: #FFFFFF;
    --text-secondary: #CCCCFF;
    /* Ensure Gradio's body text color matches our dark-theme primary text */
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
    --shadow-color: rgba(0, 0, 0, 0.5);
    --shadow-hover: rgba(0, 0, 0, 0.7);
}


/* Title bar */
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
    font-family: 'Courier New', 'Courier', 'Monaco', 'Menlo', monospace;
    font-size: 32px;
    font-weight: 700;
    color: var(--accent-blue);
    letter-spacing: 3px;
    text-transform: uppercase;
    display: flex;
    align-items: center;
    gap: 20px;
    text-shadow: 2px 2px 0px rgba(0, 0, 0, 0.8);
}

/* Detective avatar - circular frame */
.detective-avatar {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 70px;
    height: 70px;
    border-radius: 50%;
    border: 2px solid var(--accent-blue);
    background: #1a1a2a;
    font-size: 40px;
    line-height: 1;
    box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.6), 0 0 10px rgba(0, 255, 255, 0.3);
    flex-shrink: 0;
}

/* The Stage - main viewing area */
.stage-container {
    background: var(--bg-card);
    border: 2px solid var(--border-color);
    border-radius: 4px;
    margin: 16px;
    padding: 24px;
    min-height: 350px;
    position: relative !important;
    box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.6);
}

/* Make portrait image container relative for absolute positioning of subtitles overlay */
.stage-container > div:has(.portrait-image),
.stage-container > div:has(img.portrait-image) {
    position: relative !important;
}

/* Ensure portrait image itself is relative and visible */
.stage-container .portrait-image,
.stage-container img[class*="portrait"],
.stage-container .portrait-image img {
    position: relative !important;
    display: block !important;
    visibility: visible !important;
    opacity: 1 !important;
    background: transparent !important;
    z-index: 1 !important;
}

/* Speaker indicator */
.speaker-name {
    font-family: 'Source Sans Pro', sans-serif;
    font-size: 24px;
    font-weight: 700;
    color: #FFFFFF !important;
    text-align: center;
    margin-bottom: 16px;
    background: #000033 !important;
    border: 2px solid var(--accent-blue) !important;
    padding: 12px 20px !important;
    box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.5) !important;
    opacity: 1 !important;
    text-transform: uppercase;
    letter-spacing: 1px;
}

img, .image-frame { border-radius: 4px !important; }


.portrait-image {
    width: 100% !important;
    max-width: 100% !important;
    height: auto !important;
    border: 3px solid var(--accent-blue);
    border-radius: 4px;
    display: block;
    margin: 0 auto;
    position: relative;
    margin-bottom: 0 !important; /* Remove margin so overlay can align properly */
    box-shadow: inset 0 0 10px rgba(0, 0, 0, 0.5);
}

/* Hide image component buttons fullscreen, share, download) - be very specific */
.portrait-image button[aria-label*="Fullscreen"],
.portrait-image button[aria-label*="Share"],
.portrait-image button[aria-label*="Download"],
.portrait-image button[title*="Fullscreen"] {
    display: none !important;
    visibility: hidden !important;
}

/* Hide Gradio's image action button containers - but not the image */
.portrait-image [class*="image-controls"]:not(img),
.portrait-image [class*="image-actions"]:not(img),
.portrait-image [class*="toolbar"]:not(img) {
    display: none !important;
    visibility: hidden !important;
}

/* Ensure the image itself and its container are always visible */
.portrait-image,
.portrait-image img,
.portrait-image > img,
.portrait-image [class*="image"]:not([class*="button"]):not([class*="control"]):not([class*="action"]),
.portrait-image [class*="svelte"] img {
    display: block !important;
    visibility: visible !important;
    opacity: 1 !important;
    background: transparent !important;
    color: inherit !important;
}

/* Make the portrait image container a positioning context for overlay */
.portrait-image,
.portrait-image > div,
.stage-container > div:has(.portrait-image) {
    position: relative !important;
}

/* Input area - use column layout to stack audio above text input */
.input-bar {
    display: flex !important;
    flex-direction: column !important;
    gap: 0 !important;
    padding: 0 !important;
    background: var(--bg-secondary);
    border-top: 2px solid var(--accent-blue);
    box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.5);
}

/* Side panel */
.side-panel {
    background: var(--bg-card) !important;
    border: 2px solid var(--border-dark) !important;
    border-radius: 4px;
    padding: 20px 24px !important;
    height: fit-content;
    margin-bottom: 12px;
    box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.6);
}

/* Force dark background on all Gradio elements within side panels */
.side-panel,
.side-panel .block,
.side-panel .group,
.side-panel .gr-group,
.side-panel .gr-box,
.side-panel .gr-block,
.side-panel [class*="block"],
.side-panel [class*="group"],
.side-panel [class*="svelte"],
.side-panel > div,
.side-panel > div > div,
.side-panel [style*="background"] {
    background: var(--bg-card) !important;
    background-color: var(--bg-card) !important;
}

/* Override any inline styles on side panel elements */
.side-panel[style*="background"],
.side-panel [style*="background"] {
    background: var(--bg-card) !important;
    background-color: var(--bg-card) !important;
}

/* Target Gradio's internal structure for side panels */
/* Remove default padding from Gradio's internal containers */
.side-panel .block,
.side-panel .prose,
.side-panel [class*="svelte"] {
    padding: 0 !important;
}

.side-panel .html-container {
    padding: 8px !important;
}
/* Ensure the actual content container has padding */

.side-panel .prose.gradio-style,
.side-panel .prose {
    padding: 20px 24px !important;
}

/* Also target the block container directly */
.side-panel > .block {
    padding: 20px 24px !important;
}

/* Ensure panel title and content have proper spacing */
.side-panel .panel-title {
    margin-top: 0;
    margin-bottom: 16px;
    padding: 8px !important;
}

/* Ensure content inside side panels has proper spacing */
.side-panel > * {
    margin: 0;
}

.side-panel > *:not(:last-child) {
    margin-bottom: 12px;
}

.panel-title {
    font-family: 'Source Sans Pro', sans-serif;
    font-size: 16px;
    font-weight: 700;
    color: var(--accent-blue);
    border-bottom: 2px solid var(--accent-blue);
    padding: 8px;
    margin-bottom: 16px;
    margin-top: 0;
    text-transform: uppercase;
    letter-spacing: 1px;
}

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

/* Checkmarks for suspects and locations */
.suspect-check,
.location-check {
    color: var(--accent-green) !important;
    font-weight: 700;
}

/* Suspect item styling - collapsible (progressive disclosure) */
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

.suspect-item summary::-webkit-details-marker {
    display: none;
}

.suspect-item summary::before {
    content: '▶';
    display: inline-block;
    width: 12px;
    margin-right: 8px;
    font-size: 10px;
    color: var(--accent-green);
    transition: transform 0.2s ease;
}

.suspect-item[open] summary::before {
    transform: rotate(90deg);
}

.suspect-item summary:hover {
    background: var(--bg-panel);
}

.suspect-item.searched {
    opacity: 0.7;
    background: var(--bg-panel);
}

.suspect-item.searched summary {
    color: var(--text-secondary);
}

.suspect-header {
    flex: 1;
    line-height: 1.4;
}



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

.accusations-display {
    font-family: 'Source Sans Pro', sans-serif;
    font-size: 14px;
    font-weight: 500;
    color: var(--text-primary);
}

.accusations-pip {
    display: inline-block;
    width: 10px;
    height: 10px;
    background: var(--accent-blue);
    border-radius: 50%;
    margin: 0 4px;
}

.accusations-pip.used {
    background: var(--accent-red);
}

/* Audio player styling - Hide audio controls, show only subtitles */
/* Overlay at bottom of portrait image */
.audio-player {
    position: relative !important;
    width: 100% !important;
    max-width: 100% !important;
    margin: 0 !important;
    padding: 0 !important;
    opacity: 1 !important;
    border: none !important;
    border-radius: 0 !important;
    /* Reduced height for subtitles only */
    min-height: 60px !important;
    max-height: 60px !important;
    height: auto !important;
    overflow: visible !important;
    box-sizing: border-box !important;
    z-index: 10 !important;
    /* Only show background when there's actual content */
    background: transparent !important;
}

/* Hide audio player when it's empty (no audio file loaded) */
.audio-player:has(.empty),
.audio-player .empty {
    display: none !important;
    visibility: hidden !important;
    opacity: 0 !important;
    height: 0 !important;
    min-height: 0 !important;
    overflow: hidden !important;
}

/* Hide audio player controls - play/pause, rewind, skip buttons */
.audio-player .play-pause-wrapper,
.audio-player .play-pause-button,
.audio-player .rewind,
.audio-player .skip,
.audio-player button[aria-label*="Skip"],
.audio-player button[aria-label*="Pause"],
.audio-player button[aria-label*="Play"],
.audio-player .svelte-72dh9g {
    display: none !important;
    visibility: hidden !important;
    opacity: 0 !important;
    height: 0 !important;
    width: 0 !important;
    overflow: hidden !important;
}

/* Hide the entire audio-player block when it only contains empty state */
.block.audio-player:has(.empty:only-child),
.block.audio-player:has(.empty) {
    display: none !important;
    visibility: hidden !important;
    opacity: 0 !important;
    height: 0 !important;
    min-height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
    border: none !important;
    overflow: hidden !important;
}

/* Hide audio-player block when it has no audio source and no subtitle content */
.block.audio-player:not(:has(audio[src])):not(:has(.subtitle-display)):not(:has([data-testid="subtitle-display"])):not(:has([class*="subtitle"])) {
    display: none !important;
    visibility: hidden !important;
    opacity: 0 !important;
    height: 0 !important;
    min-height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
    border: none !important;
    overflow: hidden !important;
}

/* Hide the block container wrapper but keep subtitle-display visible */
/* This removes the extra block that appears below subtitles */
.block.audio-player {
    border: 2px solid var(--border-dark) !important;
    padding: 16px !important;
    margin: 0 !important;
    box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.6) !important;
    border-radius: 4px !important;
}

/* Keep dark background on main block, but make child elements transparent where needed */
.block.audio-player > div:not(:has(.subtitle-display)):not(:has([data-testid="subtitle-display"])),
.audio-player:not(:has(.subtitle-display)):not(:has([data-testid="subtitle-display"])),
.audio-player audio,
.audio-player > div:not(:has(.subtitle-display)):not(:has([data-testid="subtitle-display"])) {
    background: transparent !important;
    background-color: transparent !important;
}

/* Remove black backgrounds from child elements only - keep dark theme on main block */
.block.audio-player *:not(.subtitle-display):not([data-testid="subtitle-display"]):not([class*="subtitle"]):not([data-testid*="subtitle"]) {
    background: transparent !important;
    background-color: transparent !important;
}

.icon-button-wrapper {
    background-color: transparent !important;
    --bg-color: transparent !important;
}
.icon-button {
    background-color: #010101 !important;
    --bg-color: #010101 !important;
}
.mic-select,
.record-button,
.stop-button {
    background-color: transparent !important;
    --bg-color: transparent !important;
}

/* Overlay subtitles on portrait image */
/* Make the portrait image container relative for positioning context */
.stage-container > div:has(.portrait-image),
.stage-container > div:has(img.portrait-image) {
    position: relative !important;
}

/* Position audio player to overlay the bottom of the portrait image */
/* Gradio wraps components in .block divs, so we need to target those */
.stage-container:has(.portrait-image img[src]:not([src=""])) {
    position: relative !important;
}

/* Make the portrait-image block a positioning context and remove bottom spacing */
.stage-container:has(.portrait-image img[src]:not([src=""])) .block.portrait-image {
    position: relative !important;
    margin-bottom: 0 !important;
    padding-bottom: 0 !important;
    z-index: 1 !important;
    background: transparent !important;
}

/* Ensure portrait images are always visible */
.stage-container:has(.portrait-image img[src]:not([src=""])) .block.portrait-image img,
.stage-container:has(.portrait-image img[src]:not([src=""])) .portrait-image img {
    display: block !important;
    visibility: visible !important;
    opacity: 1 !important;
    background: transparent !important;
    z-index: 2 !important;
    position: relative !important;
}

/* Style audio player block when portrait image is present */
.stage-container:has(.portrait-image img[src]:not([src=""])) .block.audio-player {
    /* Removed absolute positioning - let it flow naturally after portrait */
    margin: 0 !important;
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
}

/* Style the audio player content - fully opaque */
.stage-container:has(.portrait-image img[src]:not([src=""])) .block.audio-player > div,
.stage-container:has(.portrait-image img[src]:not([src=""])) .block.audio-player .minimal-audio-player {
    padding: 16px 20px !important;
    # background: #00004d !important;
    opacity: 1 !important;
}

/* Position speaker name above subtitles in the overlay */
.stage-container:has(.portrait-image img[src]:not([src=""])) .speaker-name {
    position: absolute !important;
    /* Position above the subtitle overlay (which is at bottom: 24px) */
    /* Subtitle area is ~60px tall, so position speaker above it */
    bottom: 100px !important; /* 24px (subtitle bottom) + ~60px (subtitle height) + 16px (spacing) */
    left: 24px !important;
    right: 24px !important;
    width: calc(100% - 48px) !important;
    /* Dark blue background matching subtitle overlay - fully opaque */
    background: #00004d !important;
    z-index: 11 !important;
    color: #FFFFFF !important;
    font-size: 18px !important;
    text-shadow: 0 1px 3px rgba(0, 0, 0, 0.8) !important;
    font-weight: 600 !important;
    text-align: center !important;
    display: block !important;
    visibility: visible !important;
    opacity: 1 !important;
    margin: 0 !important;
    margin-top: -200px !important; /* Match the audio player's negative margin */
}

/* When there's no portrait image (e.g., start screen), don't overlay */
.stage-container:not(:has(.portrait-image img[src]:not([src=""]))) .audio-player {
    position: relative !important;
    background: var(--bg-panel) !important;
    border: 1px solid var(--border-color) !important;
    padding: 8px !important;
}

/* Hide ALL audio controls and buttons */
.audio-player button,
.audio-player [role="button"],
.audio-player .controls,
.audio-player .audio-controls,
.audio-player [class*="button"],
.audio-player [class*="control"] {
    display: none !important;
}

/* Hide the entire controls wrapper with volume, playback speed, and subtitle toggle */
/* Use very specific selectors with high priority */
.audio-player .controls,
.audio-player .controls.svelte-72dh9g,
.audio-player [data-testid="waveform-controls"],
.audio-player [data-testid="waveform-controls"].svelte-72dh9g,
.audio-player div.controls,
.audio-player div.controls.svelte-72dh9g,
.audio-player div[data-testid="waveform-controls"],
.audio-player div[data-testid="waveform-controls"].svelte-72dh9g,
.audio-player .control-wrapper,
.audio-player .control-wrapper.svelte-72dh9g,
.audio-player .settings-wrapper,
.audio-player .settings-wrapper.svelte-72dh9g,
.audio-player .play-pause-wrapper,
.audio-player .play-pause-wrapper.svelte-72dh9g,
.audio-player .volume,
.audio-player .playback,
.audio-player [aria-label*="volume"],
.audio-player [aria-label*="playback speed"],
.audio-player [data-testid="subtitles-toggle"],
.audio-player .cc-button,
/* Target by svelte class as well */
.audio-player .svelte-72dh9g.controls,
.audio-player div.svelte-72dh9g[data-testid="waveform-controls"],
/* Universal selector for any element with waveform-controls */
[data-testid="waveform-controls"],
div[data-testid="waveform-controls"],
.controls[data-testid="waveform-controls"] {
    display: none !important;
    visibility: hidden !important;
    opacity: 0 !important;
    height: 0 !important;
    width: 0 !important;
    min-height: 0 !important;
    min-width: 0 !important;
    max-height: 0 !important;
    max-width: 0 !important;
    overflow: hidden !important;
    pointer-events: none !important;
    position: absolute !important;
    left: -9999px !important;
    margin: 0 !important;
    padding: 0 !important;
}

/* Hide time element and timestamps */
.audio-player time,
.audio-player #time,
.audio-player [id="time"],
.audio-player [id="duration"],
.audio-player [class*="time"],
.audio-player .timestamps,
.audio-player .timestamps.svelte-1ffmt2w {
    display: none !important;
    visibility: hidden !important;
    height: 0 !important;
    width: 0 !important;
    overflow: hidden !important;
}

/* Hide waveform container and component wrapper - but NOT if it contains subtitle-display */
/* Be very specific about what to hide */
.audio-player .component-wrapper:not(:has(.subtitle-display)):not(:has([data-testid="subtitle-display"])),
.audio-player .component-wrapper.svelte-1ffmt2w:not(:has(.subtitle-display)):not(:has([data-testid="subtitle-display"])),
.audio-player [data-testid="waveform-Audio"]:not(:has(.subtitle-display)):not(:has([data-testid="subtitle-display"])),
.audio-player .waveform-container,
.audio-player .waveform-container.svelte-1ffmt2w,
.audio-player #waveform,
.audio-player #waveform.svelte-1ffmt2w,
.audio-player div[data-testid="waveform-Audio"]:not(:has(.subtitle-display)):not(:has([data-testid="subtitle-display"])),
/* Hide timestamps specifically */
.audio-player .timestamps,
.audio-player .timestamps.svelte-1ffmt2w {
    display: none !important;
    visibility: hidden !important;
    opacity: 0 !important;
    height: 0 !important;
    width: 0 !important;
    min-height: 0 !important;
    min-width: 0 !important;
    max-height: 0 !important;
    max-width: 0 !important;
    overflow: hidden !important;
    pointer-events: none !important;
    position: absolute !important;
    left: -9999px !important;
    margin: 0 !important;
    padding: 0 !important;
}

/* Style component-wrapper when it contains subtitles */
.audio-player .component-wrapper:has(.subtitle-display),
.audio-player .component-wrapper:has([data-testid="subtitle-display"]),
.audio-player .component-wrapper.svelte-1ffmt2w:has(.subtitle-display),
.audio-player .component-wrapper.svelte-1ffmt2w:has([data-testid="subtitle-display"]) {
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
    margin: 0 !important;
    /* Removed absolute positioning */
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
    justify-content: center !important;
}

/* Ensure subtitle-display inside component-wrapper is styled */
.audio-player .component-wrapper .subtitle-display,
.audio-player .component-wrapper [data-testid="subtitle-display"] {
    /* Removed positioning overrides - let it flow naturally */
    width: 100% !important;
}

/* CRITICAL: Ensure subtitle-display is ALWAYS visible - highest priority */
/* Must come after any hiding rules and have maximum specificity */
.audio-player .subtitle-display.svelte-1ffmt2w,
.audio-player [data-testid="subtitle-display"].svelte-1ffmt2w,
.audio-player .subtitle-display,
.audio-player [data-testid="subtitle-display"],
.audio-player .component-wrapper .subtitle-display,
.audio-player .component-wrapper [data-testid="subtitle-display"],
.audio-player .component-wrapper.svelte-1ffmt2w .subtitle-display,
.audio-player .component-wrapper.svelte-1ffmt2w [data-testid="subtitle-display"] {
    display: block !important;
    visibility: visible !important;
    opacity: 1 !important;
    height: auto !important;
    width: auto !important;
    min-height: 50px !important;
    /* Removed absolute positioning - let it flow naturally */
    pointer-events: auto !important;
    /* Removed z-index as it's no longer needed without absolute positioning */
}

/* Hide download/share buttons if present */
.audio-player [class*="download"],
.audio-player [class*="share"] {
    display: none !important;
}

/* Hide the audio element itself (but keep it functional for autoplay) */
.audio-player audio {
    position: absolute !important;
    width: 1px !important;
    height: 1px !important;
    opacity: 0 !important;
    pointer-events: none !important;
    overflow: hidden !important;
    clip: rect(0, 0, 0, 0) !important;
}

/* Hide waveform/canvas */
.audio-player canvas,
.audio-player [class*="waveform"],
.audio-player [class*="wave"],
.audio-player svg:not([class*="subtitle"]):not([data-testid*="subtitle"]) {
    display: none !important;
    height: 0 !important;
    width: 0 !important;
    visibility: hidden !important;
}

/* Show ONLY subtitles - make them fully visible and prominent */
/* Target all possible subtitle containers with very broad selectors */
.audio-player [class*="subtitle"],
.audio-player [class*="caption"],
.audio-player [class*="text"],
.audio-player [class*="transcript"],
.audio-player div[role="region"],
.audio-player > div > div:last-child,
.audio-player > div:last-child,
.audio-player [data-testid*="subtitle"],
.audio-player [data-testid*="caption"],
.audio-player div:has(span[data-timestamp]),
.audio-player div:has([class*="word"]),
.audio-player div:has([class*="highlight"]) {
    /* Make subtitles fully visible and take up the full space */
    display: block !important;
    visibility: visible !important;
    opacity: 1 !important;
    height: auto !important;
    max-height: none !important;
    min-height: 30px !important;
    overflow-y: visible !important;
    overflow-x: hidden !important;
    flex-shrink: 0 !important;
    box-sizing: border-box !important;
    /* Center the text */
    text-align: center !important;
    /* Ensure text wraps properly and is readable */
    word-wrap: break-word !important;
    line-height: 1.8 !important;
    padding: 4px 0 !important;
    margin: 0 !important;
    font-size: 18px !important;
    font-weight: 500 !important;
    /* White text for contrast on dark blue background */
    color: #FFFFFF !important;
    text-shadow: 0 1px 3px rgba(0, 0, 0, 0.8) !important;
    width: 100% !important;
    text-align: center !important;
    font-weight: 500 !important;
    # /* Ensure background is dark blue */
    # background: #00004d !important;
}

/* More aggressive: target any div that contains text after the audio element */
.audio-player audio ~ div,
.audio-player audio + div,
.audio-player > div > div:not(:first-child) {
    overflow-y: visible !important;
    max-height: 140px !important;
}

/* Force remove any inline styles that might be causing scrolling */
.audio-player * {
    /* Override any inline max-height that might be set */
}

/* Specifically target Gradio's subtitle rendering area */
.audio-player [style*="max-height"],
.audio-player [style*="overflow"] {
    max-height: 140px !important;
    overflow-y: visible !important;
    overflow: visible !important;
}

/* Ensure the audio component wrapper shows only subtitles with dark blue background */
/* Only apply background when there are actually subtitles */
.audio-player > div:has([class*="subtitle"]),
.audio-player > div:has([class*="caption"]),
.audio-player > div:has([role="region"]),
.audio-player > div:has([data-testid*="subtitle"]),
.audio-player > div:has([data-testid*="caption"]) {
    height: auto !important;
    min-height: 60px !important;
    max-height: 150px !important;
    display: flex !important;
    # background: #00004d !important;
    flex-direction: column !important;
    box-sizing: border-box !important;
    overflow: visible !important;
    gap: 0 !important;
    align-items: center !important;
    justify-content: center !important;
}

/* Default state - no background if no subtitles */
.audio-player > div {
    height: auto !important;
    min-height: 60px !important;
    max-height: 150px !important;
    display: flex !important;
    background: transparent !important;
    flex-direction: column !important;
    box-sizing: border-box !important;
    overflow: visible !important;
    gap: 0 !important;
    align-items: center !important;
    justify-content: center !important;
}

/* Target Gradio's internal structure - hide audio player UI, show subtitles */
.audio-player .minimal-audio-player,
.audio-player .minimal-audio-player > div {
    height: auto !important;
    max-height: none !important;
    overflow: visible !important;
}

/* Hide any audio player UI elements that aren't subtitles - but be careful not to hide subtitle containers */
.audio-player > div > div:first-child:not([class*="subtitle"]):not([class*="caption"]):not([role="region"]):not([data-testid*="subtitle"]):not([data-testid*="caption"]) {
    /* Only hide if it doesn't contain subtitle-related elements */
    display: none !important;
    height: 0 !important;
    overflow: hidden !important;
}

/* Ensure subtitle containers are always visible with dark blue background - fully opaque */
.audio-player [class*="subtitle"],
.audio-player [class*="caption"],
.audio-player [role="region"],
.audio-player [data-testid*="subtitle"],
.audio-player [data-testid*="caption"] {
    display: block !important;
    visibility: visible !important;
    opacity: 1 !important;
    text-align: center !important;
    # background: #00004d !important;
    color: #FFFFFF !important;
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.7) !important;
}

/* CRITICAL: Preserve and style subtitle-display element - must not be removed */
/* This ensures the specific subtitle-display element is always visible and styled */
.audio-player .subtitle-display,
.audio-player [data-testid="subtitle-display"],
.audio-player .subtitle-display.svelte-1ffmt2w,
.audio-player [data-testid="subtitle-display"].svelte-1ffmt2w {
    display: block !important;
    visibility: visible !important;
    opacity: 1 !important;
    color: #FFFFFF !important;
    text-align: center !important;
    font-size: 20px !important;
    font-weight: 600 !important;
    text-shadow: 0 1px 3px rgba(0, 0, 0, 0.8) !important;
    margin: 0 !important;
    height: auto !important;
    min-height: 0px !important;
    z-index: 100 !important;
    position: absolute !important;
    bottom: 5px !important;
}

/* Center all text elements within subtitle containers and ensure good contrast */
.audio-player [class*="subtitle"] *,
.audio-player [class*="caption"] *,
.audio-player [role="region"] *,
.audio-player [data-testid*="subtitle"] *,
.audio-player [data-testid*="caption"] *,
.audio-player div:has(span[data-timestamp]) *,
.audio-player div:has([class*="word"]) *,
.audio-player div:has([class*="highlight"]) *,
.audio-player > div > div:last-child *,
.audio-player > div:last-child * {
    /* White text for contrast on dark blue background */
    color: #FFFFFF !important;
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.7) !important;
    text-align: center !important;
    display: inline-block !important;
}

/* Ensure subtitle spans and words are centered */
.audio-player span[data-timestamp],
.audio-player [class*="word"],
.audio-player [class*="highlight"] {
    text-align: center !important;
    display: inline-block !important;
}

.html-container > div {
    padding: 8px !important;
}

.block.transcript-panel {
    padding: 8px !important;
}
/* Transcript panel */
.transcript-panel {
    max-height: 300px;
    overflow-y: auto;
    font-family: 'Source Sans Pro', sans-serif;
    font-size: 13px;
    line-height: 1.5;
}

/* Suspects list - fully visible without scrolling */
.suspects-list,
.suspects-panel .transcript-panel,
.side-panel.suspects-panel .transcript-panel {
    max-height: none !important;
    overflow-y: visible !important;
    overflow: visible !important;
    height: auto !important;
}

/* Suspects panel - allow it to grow to fit content */
.suspects-panel,
.side-panel.suspects-panel {
    height: auto !important;
    max-height: none !important;
    overflow: visible !important;
}

.start-button {
    font-family: 'Source Sans Pro', sans-serif !important;
    font-size: 16px !important;
    font-weight: 700 !important;
    background: var(--bg-card) !important;
    border: 3px solid var(--accent-blue) !important;
    color: var(--accent-blue) !important;
    padding: 14px 32px !important;
    border-radius: 4px !important;
    cursor: pointer !important;
    transition: all 0.2s ease !important;
    text-transform: uppercase !important;
    letter-spacing: 2px !important;
    box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.5) !important;
}

.start-button:hover {
    background: var(--accent-blue) !important;
    color: #000033 !important;
    transform: translateY(-2px) !important;
    box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.3) !important;
    text-shadow: none !important;
}

/* Start button container */
.start-button-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
}

/* Hide prose containers that are empty */
.prose.gradio-style:empty {
    display: none !important;
    visibility: hidden !important;
    height: 0 !important;
    min-height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
    overflow: hidden !important;
}

/* Hide prose containers that only contain a hidden speaker-name */
.prose.gradio-style:has(.speaker-name[style*="display: none"]):not(:has(*:not(.speaker-name[style*="display: none"]))) {
    display: none !important;
    visibility: hidden !important;
    height: 0 !important;
    min-height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
    overflow: hidden !important;
}

/* Also hide the html-container parent when it only contains empty prose or hidden speaker-name */
.html-container:has(.prose.gradio-style:empty),
.html-container:has(.prose.gradio-style:has(.speaker-name[style*="display: none"]):not(:has(*:not(.speaker-name[style*="display: none"])))) {
    display: none !important;
    visibility: hidden !important;
    height: 0 !important;
    min-height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
    overflow: hidden !important;
}

/* Gradio overrides */
.gradio-container {
    background: var(--bg-primary) !important;
    max-width: 100% !important;
    color: var(--text-primary) !important;
}


/* Override Gradio's default light backgrounds */
.gr-box,
.gr-form,
.gr-block,
.gr-group,
.block,
.group,
[class*="block"],
[class*="group"] {
    background: var(--bg-card) !important;
    background-color: var(--bg-card) !important;
    border-color: var(--border-dark) !important;
    color: var(--text-primary) !important;
}

/* Specifically target Gradio group elements (used for cards) */
.gr-group,
.group,
[class*="group"] {
    background: var(--bg-card) !important;
    background-color: var(--bg-card) !important;
}

.gr-button {
    font-family: 'Source Sans Pro', sans-serif !important;
}

.gr-box {
    background: var(--bg-card) !important;
    border-color: var(--border-dark) !important;
    border-radius: 4px !important;
    box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.6) !important;
}

footer {
    display: none !important;
}

/* ==========================================================================
   STATUS TRACKER - Fixed Position Loading Indicator
   Shows elapsed time during processing without causing layout shifts
   ========================================================================== */

/* Hide ALL inline status trackers that would cause layout shifts */
[data-testid="status-tracker"].wrap.center.translucent,
[data-testid="status-tracker"].wrap.center.full.translucent,
.stage-container [data-testid="status-tracker"].wrap.default.full.generating,
[data-testid="status-tracker"].wrap.default.full.hide,
.input-bar [data-testid="status-tracker"] {
    display: none !important;
    visibility: hidden !important;
    opacity: 0 !important;
    height: 0 !important;
    width: 0 !important;
    overflow: hidden !important;
    pointer-events: none !important;
}

/* Main status tracker - FIXED position at bottom center */
[data-testid="status-tracker"]:not(.translucent):not(.wrap.center):not(.hide) {
    /* Fixed positioning - won't affect layout */
    position: fixed !important;
    bottom: 24px !important;
    left: 50% !important;
    transform: translateX(-50%) !important;
    z-index: 9999 !important;
    
    /* Consistent sizing */
    min-width: 200px !important;
    max-width: 400px !important;
    width: auto !important;
    height: auto !important;
    min-height: 48px !important;
    
    /* Styling */
    background: linear-gradient(135deg, rgba(0, 0, 51, 0.98) 0%, rgba(20, 20, 80, 0.98) 100%) !important;
    border: 2px solid var(--accent-gold) !important;
    backdrop-filter: blur(8px) !important;
    border-radius: 8px !important;
    padding: 12px 24px !important;
    
    /* Visual effects */
    animation: statusPulse 2s ease-in-out infinite !important;
}

/* Pulse animation for the status tracker */
@keyframes statusPulse {
    0%, 100% {
        border-color: var(--accent-gold);
    }
    50% {
        border-color: var(--accent-blue);
    }
}

/* Status tracker text styling */
[data-testid="status-tracker"]:not(.translucent):not(.wrap.center):not(.hide) .progress-text,
[data-testid="status-tracker"]:not(.translucent):not(.wrap.center):not(.hide) .meta-text,
[data-testid="status-tracker"]:not(.translucent):not(.wrap.center):not(.hide) .meta-text-center,
[data-testid="status-tracker"]:not(.translucent):not(.wrap.center):not(.hide) span {
    color: var(--accent-gold) !important;
    font-family: var(--font-mono) !important;
    font-weight: 700 !important;
    font-size: 14px !important;
    text-shadow: 0 2px 4px rgba(0, 0, 0, 0.8) !important;
    text-transform: uppercase !important;
    letter-spacing: 1.5px !important;
    background: transparent !important;
}

/* Spinner styling */
[data-testid="status-tracker"]:not(.translucent):not(.wrap.center):not(.hide) svg {
    color: var(--accent-gold) !important;
    width: 20px !important;
    height: 20px !important;
    margin-right: 8px !important;
}

/* Remove any background from spinner wrapper */
[data-testid="status-tracker"]:not(.translucent):not(.wrap.center):not(.hide) .svelte-1vhirvf,
[data-testid="status-tracker"]:not(.translucent):not(.wrap.center):not(.hide) .svelte-1vhirvf.margin {
    background: transparent !important;
}

/* Hide status tracker when it has .hide class or is empty */
[data-testid="status-tracker"].hide,
[data-testid="status-tracker"]:empty {
    display: none !important;
    opacity: 0 !important;
    visibility: hidden !important;
    pointer-events: none !important;
}

/* Smooth fade in/out transition */
[data-testid="status-tracker"] {
    transition: opacity 0.3s ease, transform 0.3s ease !important;
}
"""
