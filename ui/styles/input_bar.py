"""Input bar CSS styles."""

CSS_INPUT_BAR = """/* ========== STICKY INPUT BAR (RESET) ========== */
/* Target the sticky bar with maximum specificity to work in Hugging Face Spaces */
#sticky-record-bar,
.gradio-container #sticky-record-bar,
body #sticky-record-bar,
html body #sticky-record-bar {
    position: fixed !important;
    bottom: 0 !important;
    left: 0 !important;
    right: 0 !important;
    width: 100% !important;
    z-index: 99999 !important;
    background: rgba(10, 10, 10, 0.96) !important;
    border-top: 1px solid var(--border-dark) !important;
    padding: 16px 12px !important;
    margin: 0 !important;
    transform: none !important;
    will-change: auto !important;
    display: block !important;
    flex-grow: 0 !important;
    min-width: auto !important;
    max-width: none !important;
    flex-direction: unset !important;
}

/* Override Svelte's flex display */
#sticky-record-bar.svelte-vt1mxs,
#sticky-record-bar.column,
#sticky-record-bar.gap {
    display: block !important;
    flex-direction: unset !important;
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
    font-size: 0 !important;                  /* hide "Record" text */
    border-radius: 999px !important;         /* circular button */
    display: flex !important;                 /* Force visible by default */
    align-items: center;
    justify-content: center;
    padding: 0 !important;
    width: 56px !important;                    /* Make button bigger */
    height: 56px !important;                   /* Make button bigger */
    min-width: 56px !important;
    min-height: 56px !important;
    background: rgba(255, 255, 255, 0.06) url("data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none'%3E%3Cpath d='M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z' stroke='%23ffffff' stroke-width='2' stroke-linecap='round' stroke-linejoin='round' fill='none'/%3E%3Cpath d='M19 10v2a7 7 0 0 1-14 0v-2' stroke='%23ffffff' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'/%3E%3Cline x1='12' y1='19' x2='12' y2='23' stroke='%23ffffff' stroke-width='2' stroke-linecap='round'/%3E%3Cline x1='8' y1='23' x2='16' y2='23' stroke='%23ffffff' stroke-width='2' stroke-linecap='round'/%3E%3C/svg%3E") center/24px 24px no-repeat !important;
    border: 1px solid rgba(255, 255, 255, 0.25);
    color: var(--text-primary);
    margin: 0 !important;
    text-indent: -9999px;                     /* Additional text hiding */
    overflow: hidden;
}

/* Make the Stop buttons visually match the Record button */
#sticky-record-bar .controls .stop-button,
#sticky-record-bar .controls .stop-button-paused {
    position: relative;
    font-size: 0;                            /* hide "Stop" text */
    border-radius: 999px !important;         /* circular button */
    align-items: center;
    justify-content: center;
    padding: 0;
    width: 56px !important;                    /* Match record button size */
    height: 56px !important;                   /* Match record button size */
    min-width: 56px !important;
    min-height: 56px !important;
    background: rgba(255, 255, 255, 0.06);   /* same neutral background */
    border: 1px solid rgba(255, 255, 255, 0.25);
    color: var(--text-primary);
}

#sticky-record-bar .controls .stop-button::before,
#sticky-record-bar .controls .stop-button-paused::before {
    content: "■";                            /* simple stop icon */
    font-size: 20px;                          /* Bigger icon to match */
    line-height: 1;
}

/* Hide the secondary "stop paused" control so only one Stop is visible */
#sticky-record-bar .controls .stop-button-paused, #stop-paused {
    display: none !important;
}


.stop-button-paused, .resume-button {
    display: none !important;
}

/* ========== RECORD/STOP BUTTON TOGGLE ========== */
/* Force hide stop button by default - use maximum specificity */
#sticky-record-bar .controls button.stop-button.svelte-1xuh0j1,
#sticky-record-bar .controls .stop-button.svelte-1xuh0j1,
#sticky-record-bar .controls button.stop-button,
#sticky-record-bar .controls .stop-button {
    display: none !important;
    visibility: hidden !important;
    opacity: 0 !important;
    pointer-events: none !important;
    position: absolute !important;
    width: 1px !important;
    height: 1px !important;
    overflow: hidden !important;
    clip: rect(0, 0, 0, 0) !important;
}

/* Force show record button by default */
#sticky-record-bar .controls button.record-button.svelte-1xuh0j1,
#sticky-record-bar .controls .record-button.svelte-1xuh0j1,
#sticky-record-bar .controls button.record-button,
#sticky-record-bar .controls .record-button {
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    pointer-events: auto !important;
}

/* When recording starts: Gradio hides record button (adds display:none to style), show stop button */
#sticky-record-bar .controls:has(.record-button[style*="display: none"]) button.stop-button.svelte-1xuh0j1,
#sticky-record-bar .controls:has(.record-button[style*="display: none"]) .stop-button.svelte-1xuh0j1,
#sticky-record-bar .controls:has(.record-button[style*="display: none"]) button.stop-button,
#sticky-record-bar .controls:has(.record-button[style*="display: none"]) .stop-button {
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    pointer-events: auto !important;
    position: relative !important;
    width: 56px !important;
    height: 56px !important;
    min-width: 56px !important;
    min-height: 56px !important;
    overflow: visible !important;
    clip: auto !important;
}

/* When stop button is visible (has display:flex in style), keep record hidden */
#sticky-record-bar .controls:has(.stop-button[style*="display: flex"]) .record-button {
    display: none !important;
    visibility: hidden !important;
    opacity: 0 !important;
    pointer-events: none !important;
}

/* Add bottom padding so content isn't hidden behind the bar */
.gradio-container {
    padding-bottom: 100px !important;
}


@media (max-width: 900px) {
    .gradio-container {
        padding-bottom: 120px !important;
    }
}
"""
