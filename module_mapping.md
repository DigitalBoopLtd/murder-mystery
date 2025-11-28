# Module Mapping for Murder Mystery Refactor

This document records how existing top-level modules map into the new packages.

## Game domain (`game/`)

- `game_actions.py` → `game/actions.py`
- `game_handlers.py` → `game/handlers.py`
- `game_media.py` → `game/media.py`
- `game_parser.py` → `game/parser.py`
- `game_startup.py` → `game/startup.py`
- `game_state.py` → `game/state.py`
- `game_state_manager.py` → `game/state_manager.py`
- `game_tools.py` → `game/tools.py`
- `mystery_generator.py` → `game/mystery_generator.py`
- `models.py` → `game/models.py`

Game-specific configuration from `mystery_config.py` (e.g. defaults for settings,
tone, difficulty) will eventually be split so that:

- Game-facing config types and helpers stay importable as `game.config` (e.g. `MysteryConfig`)
- Environment / deployment settings move under `config/` as needed.

## UI (`ui/`)

- `ui_styles.py` → `ui/styles.py`
- `ui_formatters.py` → `ui/formatters.py`
- `static/` → `ui/static/` (including `static/startup-audio.mp3`)

## Services / integrations (`services/`)

- `image_service.py` → `services/image_service.py`
- `tts_service.py` → `services/tts_service.py`
- `voice_service.py` → `services/voice_service.py`
- `agent.py` → `services/agent.py`

## App / entrypoint (`app/`)

- `app.py` → `app/main.py`

The top-level `app.py` module will be reduced to a thin entrypoint that imports
and runs the Gradio app from `app/main.py`, so external commands (like `python app.py`
or `uvicorn app:app`) continue to work.



