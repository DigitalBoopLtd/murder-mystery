"""Title bar CSS styles."""

CSS_TITLE_BAR = """/* ========== TITLE BAR ========== */
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
    font-family: var(--font-retro-title);
    font-size: 18px;
    font-weight: 700;
    color: var(--accent-blue);
    letter-spacing: 3px;
    text-transform: uppercase;
    display: flex;
    align-items: center;
    gap: 20px;
    text-shadow: 2px 2px 0px rgba(0, 0, 0, 0.8), 0 0 20px rgba(0, 255, 255, 0.8), 0 0 40px rgba(0, 255, 255, 0.5), 0 0 60px rgba(0, 255, 255, 0.3);
}

.detective-avatar {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 60px;
    height: 60px;
    border-radius: 50%;
    border: 2px solid var(--accent-blue);
    background: #1a1a2a;
    font-size: 40px;
    line-height: 1;
    box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.6), 0 0 10px rgba(0, 255, 255, 0.3);
    flex-shrink: 0;
}

/* ========== RESTART BUTTON ========== */
.restart-button {
    font-family: var(--font-retro-mono) !important;
    font-size: 11px !important;
    font-weight: 500 !important;
    background: transparent !important;
    border: 1px solid rgba(0, 255, 255, 0.3) !important;
    color: rgba(0, 255, 255, 0.7) !important;
    padding: 6px 12px !important;
    border-radius: 3px !important;
    cursor: pointer !important;
    text-transform: uppercase !important;
    letter-spacing: 0.5px !important;
    transition: all 0.2s ease !important;
    opacity: 0.8 !important;
    align-self: center !important;
}

.restart-button:hover {
    background: rgba(0, 255, 255, 0.1) !important;
    color: rgba(0, 255, 255, 0.9) !important;
    border-color: rgba(0, 255, 255, 0.5) !important;
    opacity: 1 !important;
}

.restart-button:active {
    transform: translateY(0) !important;
}

"""
