"""Input bar CSS styles."""

CSS_INPUT_BAR = """/* ========== STICKY INPUT BAR (RESET) ========== */
#sticky-record-bar {
    position: fixed !important;
    bottom: 0 !important;
    left: 0 !important;
    right: 0 !important;
    z-index: 9999 !important;
    background: rgba(10, 10, 10, 0.96) !important;
    border-top: 1px solid var(--border-dark) !important;
    padding: 8px 12px !important;
}

/* Center the audio block, keep it narrow, and make the wrapper visually subtle */
#sticky-record-bar .block.record-audio-minimal {
    margin: 0 auto !important;
    max-width: 360px !important;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}

#sticky-record-bar .audio-container {
    display: flex;
    flex-direction: column;
    gap: 4px;
}

/* Make the inner component wrapper minimal so the record button stands out */
#sticky-record-bar .component-wrapper {
    padding: 0 !important;
    background: transparent !important;
    box-shadow: none !important;
}

#sticky-record-bar .controls {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 8px;
}

/* Hide the text label on the Record button, but keep the button itself visible.
   Style it as a neutral circular button with a centered microphone icon. */
#sticky-record-bar .controls .record-button {
    position: relative;
    font-size: 0;                            /* hide "Record" text */
    border-radius: 999px !important;         /* circular button */
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0;
    background: rgba(255, 255, 255, 0.06);    /* subtle neutral background */
    border: 1px solid rgba(255, 255, 255, 0.25);
    color: var(--text-primary);
}

#sticky-record-bar .controls .record-button::before {
    content: "🎙";                           /* simple microphone icon */
    font-size: 18px;
    line-height: 1;
}

/* Make the Stop buttons visually match the Record button */
#sticky-record-bar .controls .stop-button,
#sticky-record-bar .controls .stop-button-paused {
    position: relative;
    font-size: 0;                            /* hide "Stop" text */
    border-radius: 999px !important;         /* circular button */
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0;
    background: rgba(255, 255, 255, 0.06);   /* same neutral background */
    border: 1px solid rgba(255, 255, 255, 0.25);
    color: var(--text-primary);
}

#sticky-record-bar .controls .stop-button::before,
#sticky-record-bar .controls .stop-button-paused::before {
    content: "■";                            /* simple stop icon */
    font-size: 14px;
    line-height: 1;
}

/* Hide the secondary "stop paused" control so only one Stop is visible */
#sticky-record-bar .controls .stop-button-paused, #stop-paused {
    display: none !important;
}


.stop-button-paused, .resume-button {
    display: none !important;
}

/* Add bottom padding so content isn't hidden behind the bar */
.gradio-container {
    padding-bottom: 90px !important;
}


@media (max-width: 900px) {
    .gradio-container {
        padding-bottom: 110px !important;
    }
}
"""
