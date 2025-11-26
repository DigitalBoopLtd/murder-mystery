"""UI styling for the murder mystery game interface."""

RETRO_CSS = """
/* Import Roblox-style fonts */
@import url('https://fonts.googleapis.com/css2?family=Source+Sans+Pro:wght@400;600;700&family=Inter:wght@400;500;600;700&display=swap');

/* Root variables for theming - Roblox inspired palette */
:root {
    --bg-primary: #F7F7F7;
    --bg-secondary: #FFFFFF;
    --bg-panel: #F2F2F2;
    --bg-card: #FFFFFF;
    --text-primary: #1E1E1E;
    --text-secondary: #6B6B6B;
    --accent-blue: #00A2FF;
    --accent-blue-dark: #0088CC;
    --accent-green: #00C853;
    --accent-red: #E53935;
    --accent-orange: #FF6F00;
    --border-color: #E0E0E0;
    --shadow-color: rgba(0, 0, 0, 0.1);
    --shadow-hover: rgba(0, 162, 255, 0.2);
}

/* Main container */
.adventure-game {
    background: var(--bg-primary) !important;
    min-height: 100vh;
    font-family: 'Source Sans Pro', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

/* Title bar */
.title-bar {
    background: var(--bg-secondary);
    border-bottom: 2px solid var(--border-color);
    padding: 16px 24px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.game-title {
    font-family: 'Source Sans Pro', sans-serif;
    font-size: 20px;
    font-weight: 700;
    color: var(--accent-blue);
    letter-spacing: -0.5px;
}

/* The Stage - main viewing area */
.stage-container {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    margin: 16px;
    padding: 24px;
    min-height: 350px;
    position: relative !important;
}

/* Make portrait image container relative for absolute positioning of subtitles overlay */
.stage-container > div:has(.portrait-image),
.stage-container > div:has(img.portrait-image) {
    position: relative !important;
}

/* Ensure portrait image itself is relative */
.stage-container .portrait-image,
.stage-container img[class*="portrait"],
.stage-container .portrait-image img {
    position: relative !important;
}

/* Speaker indicator */
.speaker-name {
    font-family: 'Source Sans Pro', sans-serif;
    font-size: 24px;
    font-weight: 600;
    color: var(--accent-blue);
    text-align: center;
    margin-bottom: 16px;
}

/* Caption display area */
.caption-display {
    font-family: 'Source Sans Pro', sans-serif;
    font-size: 16px;
    line-height: 1.6;
    color: var(--text-primary);
    text-align: center;
    padding: 20px 24px;
    min-height: 120px;
    max-height: 200px;
    overflow-y: auto;
}

.caption-display em {
    color: var(--text-secondary);
}

/* Portrait display */
.portrait-container {
    text-align: center;
    margin: 10px 0;
}

.portrait-image {
    width: 100% !important;
    max-width: 100% !important;
    height: auto !important;
    border: 2px solid var(--border-color);
    border-radius: 12px;
    display: block;
    margin: 0 auto;
    position: relative;
    margin-bottom: 0 !important; /* Remove margin so overlay can align properly */
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
}

/* Make the portrait image container a positioning context for overlay */
.portrait-image,
.portrait-image > div,
.stage-container > div:has(.portrait-image) {
    position: relative !important;
}

/* Speaking indicator */
.speaking-indicator {
    display: flex;
    justify-content: center;
    gap: 4px;
    margin: 15px 0;
}

.speaking-indicator .bar {
    width: 4px;
    height: 20px;
    background: var(--accent-blue);
    animation: pulse 0.5s ease-in-out infinite;
    border-radius: 2px;
}

.speaking-indicator .bar:nth-child(2) { animation-delay: 0.1s; }
.speaking-indicator .bar:nth-child(3) { animation-delay: 0.2s; }
.speaking-indicator .bar:nth-child(4) { animation-delay: 0.3s; }
.speaking-indicator .bar:nth-child(5) { animation-delay: 0.4s; }

@keyframes pulse {
    0%, 100% { transform: scaleY(0.5); opacity: 0.5; }
    50% { transform: scaleY(1); opacity: 1; }
}

/* Suspect buttons */
.suspect-bar {
    display: flex;
    justify-content: center;
    gap: 12px;
    padding: 16px;
    background: var(--bg-primary);
    flex-wrap: wrap;
}

.suspect-button {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 12px 16px;
    cursor: pointer;
    transition: all 0.2s ease;
    text-align: center;
    min-width: 140px;
    color: var(--text-primary);
}

.suspect-button:hover {
    border-color: var(--accent-blue);
    transform: translateY(-2px);
    background: #F8FBFF;
}

.suspect-button img {
    width: 80px;
    height: 80px;
    border-radius: 8px;
    border: 1px solid var(--border-color);
    margin-bottom: 8px;
}

.suspect-button .name {
    font-family: 'Source Sans Pro', sans-serif;
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
}

.suspect-button .role {
    font-family: 'Source Sans Pro', sans-serif;
    font-size: 12px;
    color: var(--text-secondary);
}

/* Action bar */
.action-bar {
    display: flex;
    justify-content: center;
    gap: 12px;
    padding: 16px;
    background: var(--bg-primary);
}

.action-button {
    font-family: 'Source Sans Pro', sans-serif !important;
    font-size: 14px !important;
    font-weight: 600 !important;
    background: var(--accent-blue) !important;
    border: none !important;
    color: #FFFFFF !important;
    padding: 10px 20px !important;
    border-radius: 6px !important;
    cursor: pointer !important;
    transition: all 0.2s ease !important;
}

.action-button:hover {
    background: var(--accent-blue-dark) !important;
    transform: translateY(-1px) !important;
}

/* Input area */
.input-bar {
    display: flex;
    gap: 12px;
    padding: 16px;
    background: var(--bg-primary);
    border-top: 1px solid var(--border-color);
    align-items: center;
    justify-content: center;
}

.text-input {
    font-family: 'Source Sans Pro', sans-serif !important;
    font-size: 14px !important;
    background: var(--bg-card) !important;
    border: 1px solid var(--border-color) !important;
    color: var(--text-primary) !important;
    padding: 10px 16px !important;
    border-radius: 6px !important;
    flex-grow: 1 !important;
    max-width: 500px !important;
}

.text-input:focus {
    border-color: var(--accent-blue) !important;
    outline: none !important;
}

/* Side panel */
.side-panel {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 20px 24px !important;
    height: fit-content;
    margin-bottom: 12px;
}

/* Target Gradio's internal structure for side panels */
/* Remove default padding from Gradio's internal containers */
.side-panel .block,
.side-panel .html-container,
.side-panel .prose,
.side-panel [class*="svelte"] {
    padding: 0 !important;
}

/* Ensure the actual content container has padding */
.side-panel .html-container,
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
    padding-top: 0;
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
    font-weight: 600;
    color: var(--accent-blue);
    border-bottom: 2px solid var(--border-color);
    padding-bottom: 12px;
    margin-bottom: 16px;
    margin-top: 0;
}

.clue-item {
    font-family: 'Source Sans Pro', sans-serif;
    font-size: 13px;
    color: var(--text-primary);
    padding: 8px 12px;
    border-left: 3px solid var(--accent-blue);
    margin-bottom: 6px;
    background: #F8FBFF;
    border-radius: 4px;
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

/* Status bar */
.status-bar {
    background: var(--bg-card);
    border-top: 1px solid var(--border-color);
    padding: 12px 24px;
    display: flex;
    justify-content: space-between;
    align-items: center;
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
    background: var(--accent-green) !important;
    border: none !important;
    border-radius: 0 !important;
    /* Reduced height for subtitles only */
    min-height: 60px !important;
    max-height: 60px !important;
    height: auto !important;
    overflow: visible !important;
    box-sizing: border-box !important;
    z-index: 10 !important;
}

/* Overlay subtitles on portrait image */
/* Make the portrait image container relative for positioning context */
.stage-container > div:has(.portrait-image),
.stage-container > div:has(img.portrait-image) {
    position: relative !important;
}

/* Position audio player to overlay the bottom of the portrait image */
/* Since portrait and audio are siblings, we position audio absolutely */
.stage-container:has(.portrait-image img[src]:not([src=""])) .audio-player {
    position: absolute !important;
    /* Position to overlay the bottom of the portrait image */
    /* Since image and audio are siblings, we need to position relative to image */
    /* Use a large negative margin-top to pull it up onto the image */
    bottom: 24px !important;
    left: 24px !important;
    right: 24px !important;
    width: calc(100% - 48px) !important;
    padding: 16px 20px !important;
    /* Much darker background for better readability */
    background: linear-gradient(to top, rgba(0, 0, 0, 0.95) 0%, rgba(0, 0, 0, 0.85) 100%) !important;
    border-radius: 0 0 12px 12px !important;
    z-index: 10 !important;
    /* Pull up to overlay the image - use large negative margin */
    margin-top: -400px !important; /* Large enough to pull up onto any image height */
}

/* Position speaker name above subtitles in the overlay */
.stage-container:has(.portrait-image img[src]:not([src=""])) .speaker-name {
    position: absolute !important;
    bottom: 120px !important; /* Position above the subtitle overlay */
    left: 24px !important;
    right: 24px !important;
    width: calc(100% - 48px) !important;
    padding: 8px 20px !important;
    /* Dark background matching subtitle overlay */
    background: linear-gradient(to top, rgba(0, 0, 0, 0.95) 0%, rgba(0, 0, 0, 0.85) 100%) !important;
    border-radius: 12px 12px 0 0 !important;
    z-index: 11 !important;
    color: #FFFFFF !important;
    font-size: 18px !important;
    font-weight: 600 !important;
    text-align: center !important;
    text-shadow: 0 1px 3px rgba(0, 0, 0, 0.8) !important;
    display: block !important;
    visibility: visible !important;
    margin: 0 !important;
    /* Pull up to align with image overlay */
    margin-top: -400px !important; /* Match the audio player's negative margin */
}

/* When there's no portrait image (e.g., start screen), don't overlay */
.stage-container:not(:has(.portrait-image img[src]:not([src=""]))) .audio-player {
    position: relative !important;
    background: var(--bg-panel) !important;
    border: 1px solid var(--border-color) !important;
    border-radius: 8px !important;
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

/* Hide time element */
.audio-player time,
.audio-player #time,
.audio-player [id="time"],
.audio-player [class*="time"],
.audio-player .svelte-1ffmt2w {
    display: none !important;
    visibility: hidden !important;
    height: 0 !important;
    width: 0 !important;
    overflow: hidden !important;
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
.audio-player svg {
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
    min-height: 50px !important;
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
    /* White text for contrast on dark overlay */
    color: #FFFFFF !important;
    text-shadow: 0 1px 3px rgba(0, 0, 0, 0.8) !important;
    width: 100% !important;
    text-align: center !important;
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

/* Ensure the audio component wrapper shows only subtitles */
.audio-player > div {
    height: auto !important;
    min-height: 60px !important;
    max-height: 150px !important;
    display: flex !important;
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

/* Ensure subtitle containers are always visible */
.audio-player [class*="subtitle"],
.audio-player [class*="caption"],
.audio-player [role="region"],
.audio-player [data-testid*="subtitle"],
.audio-player [data-testid*="caption"] {
    display: block !important;
    visibility: visible !important;
    opacity: 1 !important;
    text-align: center !important;
}

/* Center all text elements within subtitle containers */
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

/* ============================================================================
   LIVE CAPTIONS - Word-by-word highlighting
   ============================================================================ */

.live-captions-container {
    display: flex;
    flex-direction: column;
    align-items: center;
}

.live-captions-container audio {
    width: 100%;
    max-width: 400px;
    margin: 10px auto;
    display: block;
}

.live-captions {
    font-family: 'Source Sans Pro', sans-serif;
    font-size: 20px;
    line-height: 1.8;
    color: var(--text-primary);
    padding: 20px 24px;
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    margin-top: 12px;
    min-height: 80px;
    max-height: 250px;
    overflow-y: auto;
    text-align: center;
}

/* Individual word - inline display for natural text flow */
.caption-word {
    display: inline;
    transition: all 0.2s ease;
    padding: 1px 2px;
}

/* Upcoming words - dimmed, waiting to be spoken */
.caption-word.upcoming {
    color: var(--text-secondary);
    opacity: 0.5;
}

/* Active word - currently being spoken - HIGHLIGHTED */
.caption-word.active {
    color: var(--accent-blue);
    font-weight: 700;
    opacity: 1;
    background: rgba(0, 162, 255, 0.15);
    padding: 2px 4px;
    border-radius: 3px;
    text-shadow: 0 0 2px rgba(0, 162, 255, 0.3);
}

/* Spoken words - already said, normal visibility */
.caption-word.spoken {
    color: var(--text-primary);
    opacity: 0.9;
}

/* Transcript panel */
.transcript-panel {
    max-height: 300px;
    overflow-y: auto;
    font-family: 'Source Sans Pro', sans-serif;
    font-size: 13px;
    line-height: 1.5;
}

.transcript-entry {
    padding: 8px 0;
    border-bottom: 1px solid var(--border-color);
}

.transcript-speaker {
    font-family: 'Source Sans Pro', sans-serif;
    font-weight: 600;
    color: var(--accent-blue);
    font-size: 13px;
}

.transcript-text {
    color: var(--text-secondary);
    margin-top: 4px;
}

/* New game splash */
.splash-screen {
    text-align: center;
    padding: 60px 20px;
}

.splash-title {
    font-family: 'Source Sans Pro', sans-serif;
    font-size: 32px;
    font-weight: 700;
    color: var(--accent-blue);
    margin-bottom: 16px;
}

.splash-subtitle {
    font-family: 'Source Sans Pro', sans-serif;
    font-size: 16px;
    color: var(--text-secondary);
    margin-bottom: 32px;
}

.start-button {
    font-family: 'Source Sans Pro', sans-serif !important;
    font-size: 16px !important;
    font-weight: 600 !important;
    background: var(--accent-blue) !important;
    border: none !important;
    color: #FFFFFF !important;
    padding: 14px 32px !important;
    border-radius: 8px !important;
    cursor: pointer !important;
    transition: all 0.2s ease !important;
}

.start-button:hover {
    background: var(--accent-blue-dark) !important;
    transform: translateY(-2px) !important;
}

/* Theme toggle */
.theme-toggle {
    font-family: 'Source Sans Pro', sans-serif !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    background: var(--bg-card) !important;
    border: 1px solid var(--border-color) !important;
    color: var(--text-primary) !important;
    padding: 6px 12px !important;
    border-radius: 6px !important;
    cursor: pointer !important;
    transition: all 0.2s ease !important;
}

.theme-toggle:hover {
    border-color: var(--accent-blue) !important;
    color: var(--accent-blue) !important;
    background: #F8FBFF !important;
}

/* Loading state */
.loading-indicator {
    font-family: 'Source Sans Pro', sans-serif;
    font-size: 16px;
    font-weight: 500;
    color: var(--accent-blue);
    text-align: center;
    animation: blink 1s infinite;
}

@keyframes blink {
    0%, 50% { opacity: 1; }
    51%, 100% { opacity: 0; }
}

/* Gradio overrides */
.gradio-container {
    background: var(--bg-primary) !important;
    max-width: 100% !important;
}

.gr-button {
    font-family: 'Source Sans Pro', sans-serif !important;
}

.gr-box {
    background: var(--bg-card) !important;
    border-color: var(--border-color) !important;
    border-radius: 8px !important;
}

footer {
    display: none !important;
}
"""
