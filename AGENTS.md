# AGENTS.md

This file provides guidance to the AI agent when working with code in this repository.

# AGENTS.md — Score Trans

## Project Overview

Score Trans is a Windows desktop app for converting between Western staff notation (五线谱) and Jianpu (简谱, numbered musical notation). It uses OMR (Audiveris) to recognize score images/PDFs into MusicXML, then converts between MusicXML and Jianpu text/SVG.

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

# Format and lint
.venv/Scripts/python.exe -m ruff format backend/ tests/
.venv/Scripts/python.exe -m ruff check --fix backend/ tests/

# Run FastAPI backend
$env:PYTHONPATH="backend"
$env:SCORE_TRANS_API_TOKEN="replace-with-a-random-token-at-least-32-characters"
.venv/Scripts/python.exe -m uvicorn score_trans.api.app:create_app --factory --reload --host 127.0.0.1 --port 19200
```

### Electron/Vue Frontend (pnpm + electron-vite)
```bash
cd desktop
$env:VITE_BACKEND_URL="http://127.0.0.1:19200"
$env:VITE_BACKEND_TOKEN=$env:SCORE_TRANS_API_TOKEN
pnpm dev

# Lint
pnpm lint

# Type check
npx vue-tsc --noEmit
```

## Branching & Release Workflow

Two long-lived branches:

- **`main`** — release branch. Holds only release-ready code. A push to `main`
  triggers `build-windows.yml` + `build-mac.yml` (full packaging builds →
  downloadable artifacts in the Actions run). A push of a tag `vX.Y.Z` triggers
  them again and the tag-gated step **auto-creates the GitHub Release and uploads
  both installers**.
- **`dev`** — day-to-day development. Commit/branch here. PRs into `main`/`dev`
  run only `ci.yml` (lint + tests); they do **not** run the heavy packaging builds.

Standard loop: `dev / feature branch → (PR validates via ci.yml) → merge to main → bump version → push main (packaging builds validate) → tag vX.Y.Z → Release auto-published`.

- Verify a packaging build on a branch without merging: run the workflow manually
  (Actions → "Run workflow" / `workflow_dispatch`).
- Full release recipe (version bump, tag, manifests): see [RELEASE.md](RELEASE.md).
- PR/`push` build artifacts live in the Actions run's **Artifacts** section
  (14-day retention); the **Release** page only gets assets on a tag push.
- Installers are **unsigned** (no Authenticode/Apple Developer cert). Windows
  shows SmartScreen "unknown publisher"; macOS users right-click → Open.

## Architecture Rules
Import permissions (no reverse imports are permitted):

- `api/` may import from `config/`, `exec/`, and `models/`.
- `exec/` may import from `config/`, `models/`, `services/`, and `utils/`.
- `services/` may import from `config/`, `dao/`, `domain/`, `models/`, and `utils/`.
- `dao/` and `domain/` may import from `models/` and `utils/`.
- All layers (`api/`, `exec/`, `services/`, `dao/`, `domain/`) may import from `models/`. `models/` must not import from any other project module.

Architecture tests in `tests/test_architecture.py` enforce these rules. Five existing
`exec/` actions directly import `domain/`; they are an explicit test whitelist, not a
pattern for new code.

- **`models/`** contains cross-cutting DTOs, exceptions (`OCRError`, `ExternalToolError`), and protocol definitions usable by all layers. **`domain/`** contains business logic and domain-specific computations with zero I/O. Place shared data structures in `models/`; place business rules and calculations in `domain/`.
- **`exec/`** owns request-level business flow. **Do not add new `HTTPException` imports here**. Use standard exceptions (`ValueError`, `FileNotFoundError`, `OCRError`) in new or modified code and let `api/` routes convert them to HTTP responses.

## Key Conventions

- `from __future__ import annotations` appears at the top of nearly every Python file.
- Type hints are required; use `|` union syntax (e.g., `str | Path`).
- `@dataclass(slots=True)` is the standard for DTOs, config objects, and domain entities.
- Environment variables must be read at module global scope (not inside functions or classes). Use `os.getenv` with an explicit default only for optional variables (e.g., `CACHE_TTL = int(os.getenv("SCORE_TRANS_CACHE_TTL", "3600"))`); use `os.environ[var]` for required variables to fail fast. If a required environment variable is missing or malformed at import time, raise `ValueError` with the variable name and expected format.
- Custom exceptions live in `models/common/errors.py`: `ExternalToolError`, `OCRError`, `AITranscriptionError`.
- The frontend uses Vue 3 Composition API (`<script setup>`) + Pinia + Naive UI. API calls go through typed wrappers in `desktop/src/renderer/api/`.
- Frontend error handling: API wrappers must return `{ data, error }` tuples, never throw. Components display errors via Naive UI `useMessage()`. Pinia stores handle async state with explicit `loading`/`error` flags.
- Commit messages use Chinese conventional commits: `feat: 添加XXX功能`, `fix: 修复XXX`, `refactor: 重构XXX`.
- Frontend tests (vitest, playwright) are not yet set up despite being mentioned in desktop/AGENTS.md.

## Critical Pitfalls

When modifying specific areas, follow these rules:

| If you change... | Then you must... |
|------------------|------------------|
| `services/render/` | Run `python -m pytest tests/test_render.py` — the SVG engine (~1300 lines) has fragile string assertions |
| `desktop/src/main/backend.ts` or launching app | Verify `.venv` exists — Electron auto-starts the FastAPI backend |
| Audiveris integration or OMR | Verify `SCORE_TRANS_JAVA_HOME` exists and contains `bin/java.exe`. If invalid, raise `ExternalToolError` with diagnostic message. Do not defer this check to first invocation |
| `/pipeline`, `/recognize`, `/ai/transcribe` | Use `asyncio.to_thread()` when the route must return the result to the caller; use FastAPI `BackgroundTasks` only for fire-and-forget operations. Never use synchronous blocking calls directly in async route handlers |

- **Audiveris requires JDK 25**. Set `SCORE_TRANS_JAVA_HOME` (default on Windows: `E:/ENV/JAVA/JDK25`; use forward slashes or `pathlib.Path` for cross-platform compatibility) or place JDK at that path.

## Environment Variables

Configured via `.env` or environment. See `backend/score_trans/config/env.example` for the full list.

Key variables:
- `SCORE_TRANS_AUDIVERIS` — Audiveris path (default: `third_party/audiveris/gradlew.bat`)
- `SCORE_TRANS_JAVA_HOME` — JDK 25 path for Audiveris
- `SCORE_TRANS_AUDIVERIS_AUTO_UPSCALE` — auto-upscale low-res raster images before OMR (default: `1`)
- `SCORE_TRANS_AUDIVERIS_MIN_IMAGE_EDGE` — target long-edge pixel count for preventive upscale (default: `2500`)
- `SCORE_TRANS_OCR_API_KEY` / `SCORE_TRANS_OCR_BASE_URL` / `SCORE_TRANS_OCR_MODEL`
- `SCORE_TRANS_AI_API_KEY` / `SCORE_TRANS_AI_BASE_URL` / `SCORE_TRANS_AI_MODEL`
