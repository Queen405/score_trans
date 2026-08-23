# Score Trans 项目架构

> 初始分析：2026-06-05 | 架构复核：2026-06-28

## 1. 项目概览

| 指标 | 数值 |
|---|---|
| 后端 Python 源文件 | 232 个 |
| 测试文件 | 32 个 Python 文件，另有 desktop 工具测试 |
| API 路由声明 | 51 个 |
| 核心依赖 | FastAPI, Pillow, PyMuPDF, mido, langchain, langchain-openai |

## 2. 技术栈

- **框架**：FastAPI + Uvicorn
- **数据库**：SQLite（settings.db + history.db）
- **OMR 引擎**：Audiveris（subprocess 调用，需 JDK 25）
- **AI 转录**：LangChain + OpenAI 兼容视觉 LLM（默认 Qwen3-VL-8B）
- **文字 OCR**：Python 服务调用 OpenAI 兼容 API（默认 DeepSeek-OCR）
- **前端**：Electron + Vue3（通过 CORS 连接后端）

## 3. 分层架构

```
api/         → 10 个路由模块，纯 HTTP 边界
exec/        → 9 个 Actions 编排类
services/    → 14 个服务子包（ocr, ai, render, recognize, export, files, history, settings, tasks 等）
domain/      → 纯算法（parse/, write/, constants, xml_utils）
models/      → Pydantic DTO + dataclass 实体
dao/         → history、settings、tasks、ai chat 等 SQLite DAO
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
- `domain/` 以纯算法为主，但 `domain/xml_utils.py` 和文件门面仍有文件/MXL I/O，属于待整改边界
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
    → domain/musicxml.musicxml_path_to_scores() → JianpuScore 列表
    → Python OCR provider 提取标题、歌词、表情等文字块
  → score_to_jianpu_text() → 简谱文本
  → PublicationRenderService.render_score_svg() → SVG + 渲染映射
  → 返回 { musicxml_file_id, jianpu_text, jianpu_file_id, svg_file_id, render_map_file_id }
```

Audiveris 只负责 OMR 符号识别。`f`、`mf`、`mp`、`ff` 等标准力度记号属于 Audiveris 的
`DYNAMICS_*` 符号分类，不依赖文字 OCR。Audiveris 的 `TEXTS` 步骤保留处理顺序兼容性，
但不再识别歌词、标题、排练号、和弦名或速度文字；这些内容由 Python OCR 以文字块形式
提供。`/recognize` 端点仍只返回 OMR MusicXML，Python OCR 在 pipeline、convert 和 render
路径中按请求使用。

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
| 视觉 LLM | AI 转录乐谱→简谱 | HTTP API（LangChain） |
| Python OCR API | 提取乐谱文字块 | HTTP API（urllib） |

## 8. 前端架构

```
Electron main / preload
          ↓ IPC
Vue views / components
          ↓
Pinia stores（workspace / settings / assistant / log）
          ↓
typed API adapters（统一返回 ApiResult<T>）
          ↓
FastAPI OpenAPI contract
```

- `stores/workspace.ts` 是 Score Workspace Module，集中维护 Source Page、Recognition Batch、历史记录身份和 Render Page 状态。
- `utils/batchRender.ts` 集中构造批量渲染请求，避免 Recognize、Convert、Export 三个页面分别解释分页语义。
- `models/openapi.ts` 由 FastAPI OpenAPI 自动生成；`models/contracts.ts` 提供稳定的前端语义别名，`models/types.ts` 只保留兼容重导出与纯前端类型。
- `api/client.ts` 定义统一的 `{ data, error }` Interface；各 API adapter 不向组件抛异常，组件/Store 在工作流边界通过 `requireData()` 接回原有错误展示流程。

## 9. 组合根与公开接口

- `exec/composition.py` 是后端进程级组合根，复用上传、文件、历史和设置等有状态服务；请求级 Actions 仍由 `api/dependencies.py` 创建。
- `services/render/__init__.py` 只公开渲染门面所需类型，具体 SVG 函数从 `services/render/main.py` 显式导入，减少包级 Interface 泄漏。
- 根目录 `CONTEXT.md` 定义 Source Page、History Page、Render Page 等领域语言，避免“page”在跨层协作中继续混用。

## 10. 自动化质量门禁

`.github/workflows/ci.yml` 在 Windows 环境执行：

1. Ruff 与全部 Pytest；
2. ESLint、Vue TypeScript 类型检查与前端工具测试；
3. OpenAPI 生成类型漂移检查；
4. Electron/Vue 生产构建。
