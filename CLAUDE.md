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

## Documentation

- `docs/architecture.md` — 后端架构概览（技术栈、分层、API 端点、数据流）
- `docs/file-by-file.md` — 逐层逐文件分析索引
- `docs/issues.md` — 已知问题清单与改进路线图（已人工验证，标注误报）

## Known Issues

### exec 层大量使用 HTTPException（系统性架构违规）
`exec/` 层 7 个 actions.py 文件中共有 20 处 `from fastapi import HTTPException` 并直接抛出。这违反了 `api -> exec -> services` 的分层方向，导致 exec 层无法在非 FastAPI 上下文（如 CLI、单元测试）中复用。

短期 workaround：保持现状（测试已 mock）。长期应改为在 exec 层抛业务异常（`ValueError`, `FileNotFoundError`, `OCRError` 等），由 `api/` 层的路由统一转换为 HTTP 响应。

### 长耗时路由阻塞事件循环
`POST /pipeline`、`POST /recognize`、`POST /ai/transcribe` 内部包含 subprocess（Audiveris 可能运行数分钟）或多页 LLM 调用，当前同步执行会阻塞 FastAPI worker。应使用 `asyncio.to_thread()` 或后台任务 + SSE 进度流。

### DI 工厂无缓存
`api/dependencies.py` 每次请求都创建新的 Actions 实例，连带内部的 Service 和 DAO 也重复初始化。`SettingsDao.default()` 单例缓解了 settings 的问题，但 `UploadService` 每次都重新加载 `index.json`。

### 依赖项隔离不足
`langchain` / `langchain-openai` 是重型依赖，仅用于 AI 转录功能，但已声明为核心依赖。应考虑移至 `[ai]` optional extra。

## Development Notes

- 修改代码前先运行 `python -m pytest` 确保基线通过。
- 添加新环境变量时，同步更新 `src/score_trans/config/env.example`。
- `services/render/rendering.py` 是单文件 SVG 引擎（~1430 行），修改 beam/tie/slur 逻辑时需同步检查 `tests/test_render.py` 中的 SVG 字符串断言（测试较脆弱）。
- `domain/` 层必须保持零 I/O（无文件读写、无网络调用、无 print），架构测试 `test_architecture.py` 会强制执行。
- 使用 `os.getenv()` 读取配置时，优先在模块顶部定义常量（如 `DEFAULT_XXX = os.getenv(...)`），避免在函数体内每次调用都读取环境变量。

## Future Direction

The old PySide6 Python GUI has been removed. `ELECTRON_VUE_FASTAPI_MVVM_PLAN.md` is historical planning context only; the active app is Electron + Vue3 + FastAPI.
