"""Utility functions for the murder mystery game."""

import os
import logging
import tempfile
from typing import Optional, List, Dict
from PIL import Image, ImageDraw


# In-memory log buffer for UI debug panel
UI_LOG_BUFFER: List[str] = []
MAX_UI_LOG_LINES = 500


class UILogHandler(logging.Handler):
    """Logging handler that keeps a rolling buffer of recent logs for the UI."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
        except Exception:  # noqa: BLE001
            msg = record.getMessage()

        UI_LOG_BUFFER.append(msg)
        # Keep only the last N lines
        if len(UI_LOG_BUFFER) > MAX_UI_LOG_LINES:
            del UI_LOG_BUFFER[:-MAX_UI_LOG_LINES]


def setup_ui_logging() -> None:
    """Attach UI log handler to root logger so we capture logs from all modules."""
    _ui_log_handler = UILogHandler()
    _ui_log_handler.setLevel(logging.INFO)
    _ui_log_handler.setFormatter(
        logging.Formatter("%(levelname)s:%(name)s:%(message)s")
    )
    logging.getLogger().addHandler(_ui_log_handler)


def get_ui_logs() -> str:
    """Return recent log lines for display in the UI debug panel."""
    if not UI_LOG_BUFFER:
        return "No logs captured yet. Interact with the game to generate logs."
    # Show the most recent logs first for convenience
    return "\n".join(UI_LOG_BUFFER[-MAX_UI_LOG_LINES:])


def create_favicon() -> str:
    """Create a female detective favicon for the browser tab.

    Returns:
        Path to the favicon file
    """
    # Create a 32x32 favicon (standard size)
    size = 32
    img = Image.new("RGB", (size, size), color="#2C3E50")
    draw = ImageDraw.Draw(img)

    # Draw a simple female detective icon
    # Background circle
    draw.ellipse([2, 2, size - 2, size - 2], fill="#34495E", outline="#1A252F", width=1)

    # Head (circle)
    head_size = 14
    head_x = (size - head_size) // 2
    head_y = 6
    draw.ellipse(
        [head_x, head_y, head_x + head_size, head_y + head_size],
        fill="#FDB9B9",
        outline="#E8A5A5",
        width=1,
    )

    # Detective hat (fedora)
    hat_width = 18
    hat_x = (size - hat_width) // 2
    hat_y = 4
    # Hat brim
    draw.ellipse(
        [hat_x - 2, hat_y + 2, hat_x + hat_width + 2, hat_y + 6],
        fill="#1A1A1A",
        outline="#000000",
        width=1,
    )
    # Hat crown
    draw.ellipse(
        [hat_x + 2, hat_y, hat_x + hat_width - 2, hat_y + 8],
        fill="#2C2C2C",
        outline="#1A1A1A",
        width=1,
    )

    # Eyes (two small dots)
    eye_size = 2
    left_eye_x = head_x + 3
    right_eye_x = head_x + head_size - 5
    eye_y = head_y + 5
    draw.ellipse(
        [left_eye_x, eye_y, left_eye_x + eye_size, eye_y + eye_size], fill="#000000"
    )
    draw.ellipse(
        [right_eye_x, eye_y, right_eye_x + eye_size, eye_y + eye_size], fill="#000000"
    )

    # Magnifying glass (detective tool)
    glass_x = size - 10
    glass_y = size - 10
    glass_size = 6
    # Glass circle
    draw.ellipse(
        [glass_x, glass_y, glass_x + glass_size, glass_y + glass_size],
        fill=None,
        outline="#E8A5A5",
        width=2,
    )
    # Handle
    draw.line(
        [
            glass_x + glass_size,
            glass_y + glass_size,
            glass_x + glass_size + 3,
            glass_y + glass_size + 3,
        ],
        fill="#E8A5A5",
        width=2,
    )

    # Save as PNG (Gradio can use PNG as favicon)
    favicon_path = os.path.join(tempfile.gettempdir(), "murder_mystery_favicon.png")
    img.save(favicon_path)
    return favicon_path


def convert_alignment_to_subtitles(
    alignment_data: Optional[List[Dict]],
    offset_seconds: float = None,
) -> Optional[List[Dict]]:
    """Convert alignment_data format to Gradio subtitles format.

    Args:
        alignment_data: List of dicts with 'word', 'start', 'end' keys from TTS alignment
        offset_seconds: Time offset to add to all timestamps (positive = subtitles later, negative = earlier)
                       If None, uses SUBTITLE_OFFSET_SECONDS env var (default 0.0)

    Returns:
        List of dicts in format Gradio expects: [{"timestamp": [start, end], "text": str}, ...]
        or None if no alignment data

    Note:
        Gradio expects 'timestamp' field as a list/tuple [start, end] and 'text' field for each subtitle.
        Uses alignment data words directly - they represent what was actually spoken in the audio.
        
    Tuning:
        If subtitles appear TOO EARLY (before words are spoken): use positive offset (e.g., 0.2)
        If subtitles appear TOO LATE (after words are spoken): use negative offset (e.g., -0.2)
        Set via: export SUBTITLE_OFFSET_SECONDS=0.2
    """
    logger = logging.getLogger(__name__)
    if not alignment_data:
        logger.warning("[Subtitles] No alignment data provided")
        return None

    # Get offset from parameter or environment variable
    if offset_seconds is None:
        offset_seconds = float(os.getenv("SUBTITLE_OFFSET_SECONDS", "0.0"))

    # Gradio subtitles format: list of dicts with 'timestamp' (as [start, end]) and 'text' keys
    subtitles = []
    for word_data in alignment_data:
        word = word_data.get("word", "")
        start = word_data.get("start", 0.0) + offset_seconds
        end = word_data.get("end", 0.0) + offset_seconds
        
        # Ensure timestamps don't go negative
        start = max(0.0, start)
        end = max(start, end)

        # Only add if word has content after stripping whitespace
        if word.strip():
            subtitles.append(
                {
                    "timestamp": [float(start), float(end)],
                    "text": word,
                }
            )

    if offset_seconds != 0.0:
        logger.info(
            "[Subtitles] Converted %d words to %d subtitles (offset: %.2fs)",
            len(alignment_data),
            len(subtitles),
            offset_seconds,
        )
    else:
        logger.info(
            "[Subtitles] Converted %d alignment words to %d subtitles",
            len(alignment_data),
            len(subtitles),
        )
    return subtitles if subtitles else None

