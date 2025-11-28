"""CSS variables and root-level styles."""

CSS_VARIABLES = """
/* Import fonts */
@import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&family=VT323&family=Source+Sans+3:wght@300;400;600;700&display=swap');

/* ========== ROOT VARIABLES ========== */
:root {
    --bg-primary: #000033;
    --bg-secondary: #0a0a1a;
    --bg-panel: #1a0033;
    --bg-card: #0d0d26;
    --text-primary: #FFFFFF;
    --text-secondary: #CCCCFF;
    --body-text-color: var(--text-primary);
    --accent-blue: #00FFFF;
    --accent-blue-dark: #00CCCC;
    --accent-green: #00FF00;
    --accent-red: #FF0088;
    --accent-orange: #FF8800;
    --accent-magenta: #FF00FF;
    --accent-yellow: #FFFF00;
    --border-color: #00FFFF;
    --border-dark: #006666;
    --terminal-green: #33ff33;
    --terminal-green-soft: rgba(51, 255, 51, 0.3);
    --terminal-green-soft-strong: rgba(51, 255, 51, 0.5);
    --terminal-green-glow: rgba(51, 255, 51, 0.15);
    --terminal-green-vignette: rgba(51, 255, 51, 0.08);
    --terminal-green-hover: rgba(51, 255, 51, 0.1);
    --terminal-green-border-strong: rgba(51, 255, 51, 0.3);
    --terminal-green-border-soft: rgba(51, 255, 51, 0.2);
    --terminal-green-accent: #90EE90;
    --terminal-green-muted: #1a8f1a;
    --font-body: 'Source Sans 3', system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    --font-retro-mono: 'VT323', monospace;
    --font-retro-title: 'Press Start 2P', cursive;
}
"""
