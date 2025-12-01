"""Base layout and utility CSS styles."""

CSS_BASE = """
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

label {
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
"""
