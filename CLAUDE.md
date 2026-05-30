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

# Run desktop GUI (PySide6)
.venv/Scripts/python.exe -m score_trans

# Run CLI
.venv/Scripts/python.exe -m score_trans to-jianpu input.mxl -o out.txt
.venv/Scripts/python.exe -m score_trans to-musicxml jianpu.txt -o out.musicxml
.venv/Scripts/python.exe -m score_trans render-musicxml input.mxl -o out.svg
.venv/Scripts/python.exe -m score_trans render-jianpu input.txt -o out.svg
.venv/Scripts/python.exe -m score_trans recognize image.pdf -o work/converted

# Lint
ruff check src/ tests/
```

## Architecture — Lightweight MVVM

```
src/score_trans/
  domain/          Pure domain models & conversion logic (no I/O, no Qt)
    models.py      JianpuScore, Measure, Beat, Event, JianpuPitch, TextBlock
    jianpu.py      Low-level Jianpu ↔ MusicXML text conversion (two-way)
    musicxml.py    Structured MusicXML → JianpuScore parsing + score → jianpu text
  services/        Infrastructure / external tool wrappers
    file_service.py      File I/O abstraction
    settings.py          ToolConfig (env vars, paths)
    env_file.py          .env loader (SCORE_TRANS_* variables)
    external_tools.py    subprocess wrapper for Audiveris & MuseScore CLI
    audiveris_service.py OMR recognition service
    musescore_service.py Score export service
    render_service.py    SVG render facade
    rendering.py         SVG generation engine (all layout, beams, spanners)
    ocr_service.py       OCR abstraction (unused directly, protocol only)
    ocr_provider.py      OpenAI-compatible OCR client + response parsing
    settings_service.py  Persistence for tool config
  use_cases/       User-facing operations (one class per action)
    convert_to_jianpu.py   MusicXML → JianpuScore (with optional OCR overlay)
    convert_to_musicxml.py Jianpu text → MusicXML XML string
    recognize_score.py     Image/PDF → MusicXML via Audiveris
    render_jianpu.py       Render Jianpu text or MusicXML → SVG
    render_score.py        (placeholder, not yet created)
    export_score.py        MusicXML → PDF/PNG/MIDI via MuseScore
    full_pipeline.py       Recognize + convert + render in one pass
  viewmodels/      Qt-agnostic state & command dispatch
    base.py               parse_optional_int helper
    main_window_vm.py     MainWindowViewModel (signals, business logic orchestration)
  views/           PySide6 UI (controls, dialogs, bindings only)
    main_window.py        MainWindow + run_app()
  cli/             CLI entry point
    commands.py           argparse subcommands → use cases
```

### Key Architectural Rules

- **`domain/` has zero dependencies** on services, Qt, or I/O. All music theory helpers (`FIFTHS_TO_KEY`, `KEY_TO_TONIC`, `MAJOR_SCALE`) live there.
- **`use_cases/`** are the public API surface. Each has an `execute()` method and accepts optional service dependencies for testing.
- **`viewmodels/`** use PySide6 `Signal` but contain no widget code. The `MainWindowViewModel` owns all business state and delegates to use cases.
- **`views/`** are thin — only widget layout, signal/slot wiring, and file dialogs. All logic flows through the ViewModel.
- **`services/rendering.py`** is the SVG engine (~800 lines). It takes either raw jianpu text or a `JianpuScore` and produces self-contained SVG with beams, ties, slurs, chords, and measure layout.

## Data Flow

1. **Image/PDF → MusicXML**: `RecognizeScoreUseCase` → `AudiverisService` → `external_tools.recognize_with_audiveris()` (subprocess)
2. **MusicXML → JianpuScore**: `ConvertMusicXmlToJianpuUseCase.build_score()` → `domain/musicxml.musicxml_path_to_score()` parses XML into structured `JianpuScore` with `Measure`/`Beat`/`Event` hierarchy
3. **JianpuScore → Jianpu text**: `domain/musicxml.score_to_jianpu_text()` flattens to the simple text format
4. **JianpuScore → SVG**: `rendering.render_score_svg()` layouts measures in rows, renders notes/beams/spanners per measure
5. **Jianpu text → MusicXML**: `domain/jianpu.parse_jianpu()` + `jianpu_to_musicxml()` tokenizes and emits XML
6. **Full pipeline**: `FullPipelineUseCase` chains recognize → convert → render → write all outputs

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
- **PySide6-Essentials**: GUI framework (optional — CLI works without it).

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

`ELECTRON_VUE_FASTAPI_MVVM_PLAN.md` describes a planned migration to Electron + Vue3 + FastAPI while keeping the existing `domain/services/use_cases` layers intact. The plan adds an `api/` layer (FastAPI routers + Pydantic DTOs) alongside the existing PySide6 views.
