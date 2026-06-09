# Score Trans 后端架构分析

> 生成日期：2026-06-05 | 分析工具：MiMo-V2.5-Pro 三代理深度扫描

## 1. 项目概览

| 指标 | 数值 |
|---|---|
| 后端 Python 源文件 | ~70 个 |
| 测试文件 | 11 个，约 1,300+ 行 |
| API 端点 | 22 个 |
| 核心依赖 | FastAPI, Pillow, PyMuPDF, mido, langchain, langchain-openai |

## 2. 技术栈

- **框架**：FastAPI + Uvicorn
- **数据库**：SQLite（settings.db + history.db）
- **OMR 引擎**：Audiveris（subprocess 调用，需 JDK 25）
- **AI 转录**：LangChain + OpenAI 兼容视觉 LLM（默认 Qwen3-VL-8B）
- **OCR**：OpenAI 兼容 API（默认 DeepSeek-OCR）
- **前端**：Electron + Vue3（通过 CORS 连接后端）

## 3. 分层架构

```
api/         → 10 个路由模块，纯 HTTP 边界
exec/        → 9 个 Actions 编排类
services/    → 9 个服务模块（ocr, ai, render, recognize, export, files, history, settings, tasks）
domain/      → 纯算法（parse/, write/, constants, xml_utils）
models/      → Pydantic DTO + dataclass 实体
dao/         → 2 个 SQLite DAO（history, settings）
config/      → .env 加载 + ai_prompt.yaml
utils/       → 7 个工具模块
```

### 依赖方向

```
api  →  exec  →  services  →  dao / domain / models
```

- `api/` 只依赖 `exec/`（通过 `dependencies.py` 工厂函数）
- `exec/` 编排 `services/` 和 `domain/`
- `services/` 可调用 `domain/`（纯算法）和 `dao/`（持久化）
- `domain/` 无外部依赖
- `dao/` 只依赖 `models/` 和标准库

## 4. API 端点清单

| 模块 | 前缀 | 端点 | 功能 |
|---|---|---|---|
| health | `/health` | `GET /health` | 健康检查 |
| files | `/files` | `POST /upload`, `GET /{file_id}`, `DELETE /{file_id}` | 文件上传/下载/删除 |
| convert | `/convert` | `POST /musicxml-to-jianpu`, `POST /jianpu-to-musicxml` | MusicXML ↔ 简谱互转 |
| recognize | `/recognize` | `POST /` | 乐谱图片/PDF → MusicXML（OMR） |
| render | `/render` | 5 个端点 | 简谱 → SVG 渲染 |
| pipeline | `/pipeline` | `POST /` | 一键全流程 |
| ai | `/ai` | `POST /transcribe` | AI 视觉 LLM 转录 |
| export | `/export` | `POST /midi`, `POST /midi-text`, `POST /pdf` | 导出 MIDI / PDF |
| history | `/history` | 6 个端点 | 历史记录 CRUD |
| settings | `/settings` | `GET /`, `PUT /` | 应用配置读写 |

## 5. 核心数据流

### Pipeline 全流程

```
用户上传图片/PDF
  → UploadService.save()
  → RecognizeScoreAction.execute()
    → AudiverisService.recognize()（subprocess）
    → 得到 MusicXML
  → MusicXmlToJianpuAction.build_score()
    → domain/musicxml.musicxml_path_to_score() → JianpuScore
    → 可选：OCR 补充小节号
  → score_to_jianpu_text() → 简谱文本
  → RenderService.render_score_svg() → SVG
  → 返回 { musicxml_file_id, jianpu_text, jianpu_file_id, svg_file_id }
```

### AI 转录流程

```
用户上传图片/PDF
  → AiActions.transcribe_score()
    → AiTranscriptionService.transcribe()
      → prepare_score_pages()（PDF→PNG 或直接用图片）
      → 每页: VisionJianpuProvider.transcribe_page()（调视觉 LLM）
      → clean_jianpu_text() + validate + merge
    → 合并简谱文本
```

## 6. 核心领域模型

```
JianpuScore（乐谱）
  ├── title, target_key, source_key, beats, beat_type
  ├── measures: list[Measure]
  │     ├── source_number, display_measure_number, duration
  │     ├── events: list[Event]
  │     │     ├── kind ("note" | "rest"), duration: Fraction
  │     │     ├── pitches: list[JianpuPitch]
  │     │     │     └── degree, octave, accidental, midi
  │     │     ├── tie_start/stop, slur_start/stop
  │     │     ├── dynamic, articulation, lyric
  │     │     └── ornaments, technical
  │     ├── beats: list[Beat]
  │     └── text_blocks: list[TextBlock]
  └── text_blocks: list[TextBlock]
```

## 7. 外部工具依赖

| 工具 | 用途 | 调用方式 |
|---|---|---|
| Audiveris | OMR 识别（乐谱→MusicXML） | subprocess（gradlew.bat） |
| JDK 25 | Audiveris 运行时 | 环境变量 JAVA_HOME |
| MuseScore | MusicXML → PDF/PNG/MIDI 导出 | subprocess（CLI） |
| 视觉 LLM | AI 转录乐谱→简谱 | HTTP API（LangChain） |
| OCR API | 提取乐谱文字 | HTTP API（urllib） |
