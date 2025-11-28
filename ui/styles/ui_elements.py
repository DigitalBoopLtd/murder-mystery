"""UI element CSS styles (start button, status text, status tracker)."""

CSS_UI_ELEMENTS = """/* ========== START BUTTON ========== */
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
