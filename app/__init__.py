"""Application wiring and startup package.

This package hosts the high-level Gradio wiring and startup logic, keeping
it separate from core game domain logic and services.
"""

from .main import create_app  # Re-export for `from app import create_app`




