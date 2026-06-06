# AGENTS.md — Score Trans

## Project Overview

Score Trans is a Windows desktop app for converting between Western staff notation (五线谱) and Jianpu (简谱, numbered musical notation). It uses OMR (Audiveris) to recognize score images/PDFs into MusicXML, then converts between MusicXML and Jianpu text/SVG.

- Full project context: [CLAUDE.md](CLAUDE.md)
- Architecture overview: [docs/architecture.md](docs/architecture.md)
- File-by-file index: [docs/file-by-file.md](docs/file-by-file.md)
- Known issues & roadmap: [docs/issues.md](docs/issues.md)
- Frontend development guide: [desktop/AGENTS.md](desktop/AGENTS.md)

## Build and Test

### Python Backend (uv + setuptools)
```bash
# Setup
uv venv .venv --python 3.13
uv pip install -e ".[test]" --python .venv/Scripts/python.exe

# Run all tests
python -m pytest

# Run specific test (SVG assertions are fragile)
python -m pytest tests/test_render.py
python -m pytest tests/test_architecture.py

# Lint
ruff check backend/ tests/

# Run FastAPI backend
$env:PYTHONPATH="backend"
.venv/Scripts/python.exe -m uvicorn score_trans.api.app:create_app --factory --reload --host 127.0.0.1 --port 19200
```

### Electron/Vue Frontend (pnpm + electron-vite)
```bash
cd desktop
$env:VITE_BACKEND_URL="http://127.0.0.1:19200"
pnpm dev
```

## Architecture Rules

Dependency direction is strictly **api → exec → services → dao / domain / models**.

- **`api/`** must not import `services`, `domain`, or `dao`. Architecture tests in `tests/test_architecture.py` enforce this.
- **`exec/`** owns request-level business flow. **Do not add new `HTTPException` imports here** — this is a known systemic violation (20 instances across 7 files). Use standard exceptions (`ValueError`, `FileNotFoundError`, `OCRError`) and let `api/` routes convert them to HTTP responses.
- **`dao/`** must not import `api`, `exec`, or `services`. It only depends on standard library and `models/`.
- **`domain/`** must have **zero I/O** (no file read/write, no network calls, no `print`). Architecture tests enforce this.

## Key Conventions

- `from __future__ import annotations` appears at the top of nearly every Python file.
- Type hints are required; use `|` union syntax (e.g., `str | Path`).
- `@dataclass(slots=True)` is the standard for DTOs, config objects, and domain entities.
- Environment variables are read **once at module top** as constants (e.g., `CHORD_GAP = int(os.getenv("SCORE_TRANS_RENDER_CHORD_GAP", "38"))`), not inside functions.
- Custom exceptions live in `models/common/errors.py`: `ExternalToolError`, `OCRError`, `AITranscriptionError`.
- The frontend uses Vue 3 Composition API (`<script setup>`) + Pinia + Naive UI. API calls go through typed wrappers in `desktop/src/renderer/api/`.

## Critical Pitfalls

- **`services/render/rendering.py`** is a ~1430-line SVG engine. It has fragile string assertions in `tests/test_render.py`. Always run `python -m pytest tests/test_render.py` after any rendering change.
- **Electron auto-starts the FastAPI backend** via `desktop/src/main/backend.ts`. Ensure `.venv` exists before launching the desktop app in development mode.
- **Audiveris requires JDK 25**. Set `SCORE_TRANS_JAVA_HOME` (default: `E:\ENV\JAVA\JDK25`) or place JDK at that path.
- **Long-running routes block the event loop**: `/pipeline`, `/recognize`, and `/ai/transcribe` invoke subprocesses or LLM calls synchronously. If modifying these, consider `asyncio.to_thread()` or background tasks.

## Environment Variables

Configured via `.env` or environment. See `backend/score_trans/config/env.example` for the full list.

Key variables:
- `SCORE_TRANS_AUDIVERIS` — Audiveris path (default: `third_party/audiveris/gradlew.bat`)
- `SCORE_TRANS_MUSESCORE` — MuseScore CLI path
- `SCORE_TRANS_JAVA_HOME` — JDK 25 path for Audiveris
- `SCORE_TRANS_OCR_API_KEY` / `SCORE_TRANS_OCR_BASE_URL` / `SCORE_TRANS_OCR_MODEL`
- `SCORE_TRANS_AI_API_KEY` / `SCORE_TRANS_AI_BASE_URL` / `SCORE_TRANS_AI_MODEL`
