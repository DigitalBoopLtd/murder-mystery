"""Input bar CSS styles."""

CSS_INPUT_BAR = """/* ========== INPUT BAR ========== */
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

"""
