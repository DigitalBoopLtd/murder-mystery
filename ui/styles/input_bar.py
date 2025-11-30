"""Input bar CSS styles."""

CSS_INPUT_BAR = """/* ========== STICKY RECORD BUTTON ========== */
#sticky-record-bar {
    position: fixed !important;
    bottom: 0 !important;
    left: 0 !important;
    right: 0 !important;
    z-index: 9999 !important;
    display: flex !important;
    justify-content: center !important;
    align-items: center !important;
    padding: 20px !important;
    background: rgba(10, 10, 10, 0.98) !important;
    border-top: 2px solid var(--terminal-green, #00cc66) !important;
    backdrop-filter: blur(12px) !important;
    -webkit-backdrop-filter: blur(12px) !important;
}

/* Mobile - add safe area padding for notch devices */
@media (max-width: 900px) {
    #sticky-record-bar {
        padding-bottom: calc(24px + env(safe-area-inset-bottom)) !important;
    }
}

/* ===== HIDE ALL UNWANTED ELEMENTS ===== */
#sticky-record-bar label,
#sticky-record-bar .label-wrap,
#sticky-record-bar .icon-button,
#sticky-record-bar .icon-button-wrapper,
#sticky-record-bar .mic-select,
#sticky-record-bar select,
#sticky-record-bar .dropdown,
#sticky-record-bar .settings-button {
    display: none !important;
    visibility: hidden !important;
    width: 0 !important;
    height: 0 !important;
    overflow: hidden !important;
}

/* Hide any text labels inside the button */
#sticky-record-bar button span {
    display: none !important;
}

/* Center the audio component content */
#sticky-record-bar > div,
#sticky-record-bar .audio-component {
    display: flex !important;
    justify-content: center !important;
    align-items: center !important;
    background: transparent !important;
    border: none !important;
    width: 100% !important;
}

/* ===== THE RECORD BUTTON (SINGLE CONTROL) ===== */
#sticky-record-bar button.record-button,
#sticky-record-bar button[aria-label*="ecord"],
#sticky-record-bar button:not(.icon-button):not(.settings-button) {
    position: relative !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    width: 72px !important;
    height: 72px !important;
    min-width: 72px !important;
    min-height: 72px !important;
    max-width: 72px !important;
    max-height: 72px !important;
    border-radius: 50% !important;
    background: var(--terminal-green, #00cc66) !important;
    border: 2px solid rgba(255, 255, 255, 0.4) !important;
    cursor: pointer !important;
    transition: transform 0.15s ease-out !important;
    margin: 0 auto !important;
    color: transparent !important; /* hide any built-in text */
}

#sticky-record-bar button.record-button:hover,
#sticky-record-bar button[aria-label*="ecord"]:hover,
#sticky-record-bar button:not(.icon-button):not(.settings-button):hover {
    transform: scale(1.06) !important;
}

/* Recording state - change color only (no shadows) */
#sticky-record-bar button[aria-label*="top"],
#sticky-record-bar button.recording {
    background: #e74c3c !important;
    border-color: rgba(255, 120, 120, 0.8) !important;
}

/* Hide the default SVG icon so we can use our own */
#sticky-record-bar button svg {
    display: none !important;
}

/* Custom microphone icon (change content to use your own) */
#sticky-record-bar button.record-button::before,
#sticky-record-bar button[aria-label*="ecord"]::before,
#sticky-record-bar button:not(.icon-button):not(.settings-button)::before {
    content: "🎙";  /* Custom mic icon */
    font-size: 32px;
    line-height: 1;
    color: #000000;
}

/* Mobile - larger button + icon */
@media (max-width: 900px) {
    #sticky-record-bar button.record-button,
    #sticky-record-bar button[aria-label*="ecord"],
    #sticky-record-bar button:not(.icon-button):not(.settings-button) {
        width: 80px !important;
        height: 80px !important;
        min-width: 80px !important;
        min-height: 80px !important;
        max-width: 80px !important;
        max-height: 80px !important;
    }
    
    #sticky-record-bar button.record-button::before,
    #sticky-record-bar button[aria-label*="ecord"]::before,
    #sticky-record-bar button:not(.icon-button):not(.settings-button)::before {
        font-size: 36px;
    }
}

/* ===== PAGE PADDING ===== */
.gradio-container {
    padding-bottom: 120px !important;
}

@media (max-width: 900px) {
    .gradio-container {
        padding-bottom: 140px !important;
    }
}

/* Legacy class fallback */
.input-bar {
    position: fixed !important;
    bottom: 0 !important;
    left: 0 !important;
    right: 0 !important;
    z-index: 9999 !important;
    display: flex !important;
    justify-content: center !important;
}

"""
