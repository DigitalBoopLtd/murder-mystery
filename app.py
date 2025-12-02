"""Thin entrypoint for the murder mystery app.

The full Gradio app wiring lives in the `app` package. This file exists so
commands like `python app.py` or `uvicorn app:app` continue to work.
"""

# Fix OpenMP duplicate library error on macOS (numpy + torch conflict)
import os
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

from app import create_app  # type: ignore  # re-exported from app package


if __name__ == "__main__":
    app = create_app()
    # Use Gradio's queue so the global progress/status tracker is visible
    app.queue().launch(server_name="0.0.0.0", server_port=7860, share=False)

 