# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Score Trans is a Windows desktop tool for converting between Western staff notation (五线谱) and Jianpu (简谱, numbered musical notation). It uses OMR (Audiveris) to recognize score images/PDFs into MusicXML, then converts between MusicXML and Jianpu text/SVG. External tools (Audiveris, MuseScore) are invoked via subprocess.

## Build & Run Commands

```bash
# Setup (uses uv)
uv venv .venv --python 3.13
uv pip install -e ".[test]" --python .venv/Scripts/python.exe

# Run tests
python -m pytest
python -m pytest tests/test_jianpu.py          # single test file
python -m pytest tests/test_jianpu.py -k "test_parse"  # single test

# Run FastAPI backend
$env:PYTHONPATH="src"
.venv/Scripts/python.exe -m uvicorn score_trans.api.app:create_app --factory --reload --host 127.0.0.1 --port 19200

# Run Electron/Vue desktop frontend
cd desktop
$env:VITE_BACKEND_URL="http://127.0.0.1:19200"
pnpm dev

# Lint
ruff check src/ tests/
```

## Architecture

```
src/score_trans/
  api/             FastAPI boundary. Routes only bind HTTP and delegate to exec.
  exec/            Business orchestration by module (convert/render/recognize/export/pipeline/files/history/settings).
  services/        Reusable service functions by module (files, render, OCR, external tools, settings, history).
  dao/             SQLite persistence only: table setup, migration, queries, row mapping.
  models/          Pydantic DTOs, dataclass entities, ToolConfig, and JianpuScore structures.
  domain/          Pure Jianpu/MusicXML algorithms only (no I/O, no services, no UI).
desktop/          Electron + Vue3 frontend
```

### Key Architectural Rules

- Dependency direction is **`api -> exec -> services -> dao/domain/models`**.
- **`api/`** must not import `services`, `domain`, or `dao`; architecture tests enforce this.
- **`exec/`** owns request-level business flow: file ID checks, output naming, registration, OCR parsing, history normalization, and response assembly.
- **`dao/`** must not import `api`, `exec`, or `services`; it only depends on standard library and `models`.
- **`domain/`** has zero dependencies on services, UI, or I/O. All music theory helpers (`FIFTHS_TO_KEY`, `KEY_TO_TONIC`, `MAJOR_SCALE`) live there.
- **`desktop/src/renderer/`** is the active desktop UI. Keep UI state in Pinia stores and call typed API wrappers.
- **`services/render/rendering.py`** is the SVG engine. It takes either raw jianpu text or a `JianpuScore` and produces self-contained SVG with beams, ties, slurs, chords, and measure layout.

## Data Flow

1. **Image/PDF → MusicXML**: `RecognizeScoreAction` → `AudiverisService` → `services/recognize/external_tools.recognize_with_audiveris()` (subprocess)
2. **MusicXML → JianpuScore**: `MusicXmlToJianpuAction.build_score()` → `domain/musicxml.musicxml_path_to_score()` parses XML into structured `JianpuScore` with `Measure`/`Beat`/`Event` hierarchy
3. **JianpuScore → Jianpu text**: `domain/musicxml.score_to_jianpu_text()` flattens to the simple text format
4. **JianpuScore → SVG**: `rendering.render_score_svg()` layouts measures in rows, renders notes/beams/spanners per measure
5. **Jianpu text → MusicXML**: `domain/jianpu.parse_jianpu()` + `jianpu_to_musicxml()` tokenizes and emits XML
6. **Full pipeline**: `FullPipelineAction` chains recognize → convert → render → write all outputs

## Environment Variables

All configured via `.env` file (auto-loaded by `env_file.py`) or environment:

| Variable | Purpose | Default |
|---|---|---|
| `SCORE_TRANS_AUDIVERIS` | Audiveris path or `gradlew.bat` | `third_party/audiveris/gradlew.bat` |
| `SCORE_TRANS_MUSESCORE` | MuseScore CLI path | `musescore` |
| `SCORE_TRANS_JAVA_HOME` | JDK 25 path (Audiveris needs it) | `E:\ENV\JAVA\JDK25` |
| `SCORE_TRANS_WORKDIR` | Working directory | `<project_root>/work` |
| `SCORE_TRANS_OCR_API_KEY` | OCR provider API key | — |
| `SCORE_TRANS_OCR_BASE_URL` | OCR endpoint | `https://api.siliconflow.cn/v1` |
| `SCORE_TRANS_OCR_MODEL` | OCR model name | `deepseek-ai/DeepSeek-OCR` |
| `SCORE_TRANS_DISABLE_DOTENV` | Set to skip `.env` loading | — |

## External Dependencies

- **Audiveris** (OMR): Source in `third_party/audiveris/`, built via Gradle. Requires JDK 25. Run as `gradlew.bat :app:run` in batch mode.
- **MuseScore Studio**: CLI used for MusicXML → PDF/PNG/MIDI export.
- **FastAPI / Uvicorn / python-multipart**: local API used by Electron/Vue and manual API testing.

## Jianpu Text Format

```
key=C
time=4/4
1 2 3 4 | 5 6 7 1' | 0 - 5. 3/ |
```

- `1`–`7`: scale degrees; `0`: rest; `|`: bar line
- `'`: octave up; `,`: octave down; `#`/`b`: accidentals
- `-`: extend previous note by one quarter; `/`: halve duration; `.`: dotted

## Future Direction

The old PySide6 Python GUI has been removed. `ELECTRON_VUE_FASTAPI_MVVM_PLAN.md` is historical planning context only; the active app is Electron + Vue3 + FastAPI.
