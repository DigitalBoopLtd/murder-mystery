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
    box-shadow: 0 2px 4px var(--shadow-color);
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
    position: relative;
    box-shadow: 0 2px 8px var(--shadow-color);
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
    box-shadow: 0 4px 12px var(--shadow-color);
    display: block;
    margin: 0 auto;
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
    box-shadow: 0 2px 4px var(--shadow-color);
}

.suspect-button:hover {
    border-color: var(--accent-blue);
    transform: translateY(-2px);
    box-shadow: 0 4px 12px var(--shadow-hover);
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
    box-shadow: 0 2px 4px var(--shadow-color) !important;
}

.action-button:hover {
    background: var(--accent-blue-dark) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 8px var(--shadow-hover) !important;
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
    box-shadow: 0 0 0 3px rgba(0, 162, 255, 0.1) !important;
}

/* Side panel */
.side-panel {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 16px;
    height: fit-content;
    box-shadow: 0 2px 4px var(--shadow-color);
    margin-bottom: 12px;
}

.panel-title {
    font-family: 'Source Sans Pro', sans-serif;
    font-size: 16px;
    font-weight: 600;
    color: var(--accent-blue);
    border-bottom: 2px solid var(--border-color);
    padding-bottom: 8px;
    margin-bottom: 12px;
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
    box-shadow: 0 -2px 4px var(--shadow-color);
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

/* Audio player styling - VISIBLE with full controls */
.audio-player {
    display: block !important;
    width: 100% !important;
    max-width: 500px !important;
    margin: 15px auto !important;
    padding: 10px !important;
    background: var(--bg-panel) !important;
    border: 1px solid var(--border-color) !important;
    border-radius: 8px !important;
}

.audio-player audio {
    width: 100% !important;
    height: 50px !important;
    display: block !important;
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
    box-shadow: 0 4px 12px var(--shadow-hover) !important;
    transition: all 0.2s ease !important;
}

.start-button:hover {
    background: var(--accent-blue-dark) !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 16px var(--shadow-hover) !important;
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
