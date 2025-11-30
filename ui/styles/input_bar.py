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
    padding: 10px 12px !important;
    background: rgba(10, 10, 10, 0.96) !important;
    border-top: 1px solid var(--terminal-green, #00cc66) !important;
    backdrop-filter: blur(8px) !important;
    -webkit-backdrop-filter: blur(8px) !important;
}

/* Mobile - add safe area padding for notch devices */
@media (max-width: 900px) {
    #sticky-record-bar {
        padding-bottom: calc(14px + env(safe-area-inset-bottom)) !important;
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
    display: flex;
    align-items: center !important;
    justify-content: center !important;
    width: 56px !important;
    height: 56px !important;
    min-width: 56px !important;
    min-height: 56px !important;
    max-width: 56px !important;
    max-height: 56px !important;
    border-radius: 50% !important;
    background: var(--terminal-green, #00cc66) !important;
    border: 2px solid rgba(255, 255, 255, 0.35) !important;
    cursor: pointer !important;
    transition: transform 0.15s ease-out !important;
    margin: 0 auto !important;
    font-size: 0 !important; /* hide built-in text like 'Record' */
}

#sticky-record-bar button.record-button:hover,
#sticky-record-bar button[aria-label*="ecord"]:hover,
#sticky-record-bar button:not(.icon-button):not(.settings-button):hover {
    transform: scale(1.03) !important;
}

/* Recording state - change color only */
#sticky-record-bar button[aria-label*="top"],
#sticky-record-bar button.recording {
    background: #e74c3c !important;
    border-color: rgba(255, 120, 120, 0.8) !important;
}

/* Hide extra control buttons (keep record + stop) */
.pause-button,
#stop-paused,
.resume-button {
    display: none !important;
}

/* Stop button styling */
#sticky-record-bar .stop-button {
    position: relative !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    width: 40px !important;
    height: 40px !important;
    min-width: 40px !important;
    min-height: 40px !important;
    max-width: 40px !important;
    max-height: 40px !important;
    border-radius: 50% !important;
    background: #e74c3c !important;
    border: 2px solid rgba(255, 255, 255, 0.4) !important;
    cursor: pointer !important;
    margin-left: 10px !important;
    font-size: 0 !important;  /* hide 'Stop' text */
}

#sticky-record-bar .stop-button::before {
    content: "■";
    font-size: 14px;
    line-height: 1;
    color: #000000;
}

/* Use any custom microphone icon via pseudo-element (optional) */
/* If you want a mic emoji, uncomment the content line below. */
#sticky-record-bar button.record-button::before,
#sticky-record-bar button[aria-label*="ecord"]::before,
#sticky-record-bar button:not(.icon-button):not(.settings-button)::before {
    /* content: "🎤"; */
    font-size: 18px;
    line-height: 1;
    color: #000000;
}

/* Mobile - slightly larger button + icon */
@media (max-width: 900px) {
    #sticky-record-bar button.record-button,
    #sticky-record-bar button[aria-label*="ecord"],
    #sticky-record-bar button:not(.icon-button):not(.settings-button) {
        width: 64px !important;
        height: 64px !important;
        min-width: 64px !important;
        min-height: 64px !important;
        max-width: 64px !important;
        max-height: 64px !important;
    }
    
    #sticky-record-bar button.record-button::before,
    #sticky-record-bar button[aria-label*="ecord"]::before,
    #sticky-record-bar button:not(.icon-button):not(.settings-button)::before {
        font-size: 20px;
    }

    #sticky-record-bar .stop-button {
        width: 48px !important;
        height: 48px !important;
        min-width: 48px !important;
        min-height: 48px !important;
        max-width: 48px !important;
        max-height: 48px !important;
    }
}

/* ===== PAGE PADDING ===== */
.gradio-container {
    padding-bottom: 100px !important;
}

@media (max-width: 900px) {
    .gradio-container {
        padding-bottom: 120px !important;
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
