# 逐层逐文件分析

> 接 [architecture.md](./architecture.md)

## 1. API 层 (`src/score_trans/api/`)

### `app.py` (~78 行)
FastAPI 应用工厂。注册 10 个路由模块、CORS 中间件、4 个全局异常处理器。

| 函数 | 职责 |
|---|---|
| `create_app() -> FastAPI` | 应用工厂 |
| `external_tool_error_handler` | ExternalToolError → 502 |
| `ocr_error_handler` | OCRError → 502 |
| `ai_transcription_error_handler` | AITranscriptionError → 502 |
| `validation_error_handler` | ValueError → 400 |

### `dependencies.py` (~36 行)
FastAPI 依赖注入工厂，9 个 `get_*_actions()` 函数，每次请求创建新实例。

### 路由模块

| 文件 | 行数 | 端点 | 说明 |
|---|---|---|---|
| `ai/routes.py` | 19 | `POST /ai/transcribe` | AI 转录 |
| `convert/routes.py` | 30 | 2 个 | MusicXML ↔ 简谱 |
| `export/routes.py` | 33 | 3 个 | MIDI/PDF 导出 |
| `files/routes.py` | 33 | 3 个 | 文件管理 |
| `health/routes.py` | 8 | `GET /health` | 健康检查 |
| `history/routes.py` | 50 | 6 个 | 历史 CRUD |
| `pipeline/routes.py` | 23 | `POST /pipeline` | 全流程 |
| `recognize/routes.py` | 20 | `POST /recognize` | OMR 识别 |
| `render/routes.py` | 53 | 5 个 | SVG 渲染 |
| `settings/routes.py` | 21 | 2 个 | 设置读写 |

---

## 2. Exec 层 (`src/score_trans/exec/`)

### `ai/actions.py` (~88 行)
| 类 | 方法 |
|---|---|
| `AiActions` | `transcribe_score(req)`, `_register_page_image(...)`, `get_config()` |

### `convert/actions.py` (~126 行)
| 类 | 方法 |
|---|---|
| `MusicXmlToJianpuAction` | `execute(...)`, `build_score(...)` |
| `JianpuToMusicXmlAction` | `execute_text(...)`, `execute_file(...)` |
| `ConvertActions` | `musicxml_to_jianpu_response(req)`, `jianpu_to_musicxml_response(req)` |

辅助函数：`_apply_measure_number_ocr(score, blocks, ...)`, `_measure_number_candidate_key(candidate)`

### `export/actions.py` (~96 行)
| 类 | 方法 |
|---|---|
| `ExportScoreAction` | `execute(...)`, `execute_from_score(...)` |
| `ExportActions` | `export_midi(...)`, `export_midi_text(req)`, `export_pdf(...)` |

### `files/actions.py` (~76 行)
| 类 | 方法 |
|---|---|
| `FileActions` | `upload_file(file)`, `_pdf_to_images(pdf_path)`, `download_file(file_id)`, `delete_file(file_id)` |

### `history/actions.py` (~102 行)
| 类 | 方法 |
|---|---|
| `HistoryActions` | `list_history()`, `create_batch(req)`, `get_history(batch_id)`, `update_history_page(page_id, req)`, `delete_history(batch_id)`, `delete_all_history()`, `_migrate_batch_texts(batch)` |

### `pipeline/actions.py` (~166 行)
| 类 | 方法 |
|---|---|
| `FullPipelineAction` | `execute(input_path, output_dir, *, config, ...)` |
| `PipelineActions` | `run_pipeline(file, *, target_key, ...)` |

辅助：`ScorePipelineOutputs` dataclass, `_copy_musicxml_output(...)`, `_extract_ocr_measure_numbers(...)`, `_is_ocr_image(...)`

### `recognize/actions.py` (~42 行)
| 类 | 方法 |
|---|---|
| `RecognizeScoreAction` | `execute(input_file, output_dir, config)` |
| `RecognizeActions` | `recognize(file, *, target_key, start_measure_number)` |

### `render/actions.py` (~347 行，本层最长)
| 类 | 方法 |
|---|---|
| `RenderMusicXmlJianpuAction` | `execute(...)`, `execute_page(...)`, `build_score(...)` |
| `RenderJianpuTextAction` | `execute(...)`, `execute_page(...)` |
| `RenderActions` | `render_jianpu_svg(req)`, `render_jianpu_text_svg(req)`, `normalize_jianpu_text(req)`, `render_preserving_layout(req)`, `render_final_output(req)` |

辅助：`_parse_ocr_text(payload)`, `_serialize_ocr_text(blocks)`

### `settings/actions.py` (~78 行)
| 类 | 方法 |
|---|---|
| `SettingsActions` | `get_config()`, `get_settings()`, `update_settings(req)`, `_response()` |

---

## 3. Services 层 (`src/score_trans/services/`)

### OCR 服务 (`services/ocr/`)

| 文件 | 行数 | 职责 |
|---|---|---|
| `protocols.py` | 17 | `OCRProvider` Protocol + `OCRRequest` dataclass |
| `client.py` | ~78 | 构建 HTTP 请求并发送到 OpenAI 兼容 OCR API |
| `parser.py` | ~128 | 解析 OCR JSON 响应为 `OCRTextBlock` 列表 |
| `providers.py` | ~65 | `MockOCRProvider` + `OpenAICompatibleOCRProvider` |
| `service.py` | 27 | `OCRService` 高级封装 |
| `text.py` | 34 | 推断 OCR 块角色（expression/measure_number/other） |
| `utils.py` | ~46 | 工具函数和默认配置常量 |

### AI 转录服务 (`services/ai/`)

| 文件 | 行数 | 职责 |
|---|---|---|
| `base.py` | ~108 | `VisionJianpuProvider` Protocol、prompt 构建、结果解析 |
| `registry.py` | 38 | Provider 注册表（工厂模式） |
| `service.py` | ~220 | 完整 AI 转录流程（分页→逐页转录→校验→合并） |
| `providers/openai_compatible/provider.py` | ~100 | LangChain Vision Provider 实现 |
| `providers/mock/provider.py` | 38 | Mock Provider（测试用） |

### Recognize 服务 (`services/recognize/`)

| 文件 | 行数 | 职责 |
|---|---|---|
| `audiveris_service.py` | 8 | 薄封装 |
| `external_tools.py` | ~110 | subprocess 调用封装 + 代理配置 |
| `image_preprocessing.py` | ~145 | OMR 前图像预处理（裁白边、对比度、锐化、二值化） |

### Render 服务 (`services/render/`)

| 文件 | 行数 | 职责 |
|---|---|---|
| `main.py` | ~203 | 入口函数（render_jianpu_svg / render_score_svg / page 变体） |
| `render_service.py` | ~49 | 门面，委托给 main 模块的文件输出变体 |
| `options.py` | ~30 | RenderOptions dataclass |
| `constants.py` | 9 | 渲染常量（CHORD_GAP / OCTAVE_DOT_GAP 等） |
| `drawing/measure.py` | ~58 | 单小节 SVG 组装 |
| `drawing/beat.py` | ~57 | 拍内音符项渲染 |
| `drawing/token.py` | ~90 | 单 token/和弦渲染 |
| `drawing/beams.py` | ~39 | 符杠渲染 |
| `drawing/spanners.py` | ~93 | 延音线/圆滑线弧线渲染 |
| `drawing/text.py` | ~111 | 文本块渲染（OCR/表情/歌词） |
| `layout/measure.py` | ~51 | 单小节布局计算 |
| `layout/rows.py` | ~33 | 行排列 + 拉伸 |
| `layout/beat.py` | ~31 | 拍内视觉宽度 + 分配 |
| `items/factory.py` | ~33 | Event → RenderItem 转换 |
| `items/grouping.py` | ~78 | 小节 events 按拍分组 |
| `models/layout.py` | ~31 | RenderItem / BeatLayout / MeasureLayout |
| `models/shapes.py` | 11 | NoteShape dataclass |
| `parsing/tokens.py` | ~46 | token 字符串解析 |
| `parsing/events.py` | ~27 | Event → token 序列化 |
| `svg/header.py` | ~67 | SVG defs + CSS 样式 |
| `utils/geometry.py` | ~27 | 时值线 y 坐标计算 |
| `utils/metrics.py` | ~50 | token 视觉边界 |
| `utils/helpers.py` | ~55 | 辅助函数（bbox/accidental 等） |
| `utils/bars.py` | ~17 | 小节线渲染 |
| `utils/positioning.py` | ~52 | 文本/技法标记定位 |
| `utils/articulations.py` | 18 | 演奏记号 SVG |
| `utils/text.py` | ~35 | 文本转义/拆分 |

### Export 服务 (`services/export/`)

| 文件 | 行数 | 职责 |
|---|---|---|
| `export_service.py` | ~95 | JianpuScore → SVG/MIDI 导出 + PNG→PDF 合并 |

### Files 服务 (`services/files/`)

| 文件 | 行数 | 职责 |
|---|---|---|
| `file_service.py` | 16 | 简单文件读写 |
| `image_info.py` | ~65 | 通过文件头获取图片/PDF 尺寸 |
| `upload_service.py` | ~185 | 上传文件管理（保存/查找/注册/清理） |

### 其他服务

| 文件 | 行数 | 职责 |
|---|---|---|
| `history/history_service.py` | ~55 | 历史记录 CRUD（委托给 DAO） |
| `settings/settings_service.py` | ~55 | 设置管理（DAO + 环境变量 fallback） |
| `tasks/task_service.py` | ~85 | 后台任务管理器 + SSE 进度流 |
| `common/env_file.py` | 5 | 向后兼容的环境变量加载重导出 |

---

## 4. Domain 层 (`src/score_trans/domain/`)

| 文件 | 行数 | 职责 |
|---|---|---|
| `constants.py` | 61 | 乐理常量（音名↔半音、五度圈、大调音阶等） |
| `jianpu_tokens.py` | 68 | 简谱时值前缀映射（w/h/q/s/d → Fraction） |
| `jianpu.py` | 67 | 门面模块，组合 parse/write 子模块 |
| `musicxml.py` | 19 | re-export 核心函数 |
| `xml_utils.py` | 87 | XML/MXL 文件读取工具 |
| `parse/jianpu_text.py` | ~270 | **核心简谱解析器**（文本 → JianpuScore AST） |
| `parse/musicxml.py` | ~300 | **核心 MusicXML 解析器**（XML → JianpuScore） |
| `write/jianpu_text.py` | ~110 | JianpuScore → 简谱文本序列化 |
| `write/musicxml.py` | ~90 | JianpuScore → MusicXML 序列化 |

---

## 5. Models 层 (`src/score_trans/models/`)

### 核心领域模型
- `score.py` (~165 行)：`TextBlock`, `JianpuPitch`, `Event`, `Beat`, `Measure`, `JianpuScore`

### 请求/响应 Schema

| 文件 | 主要类 |
|---|---|
| `ai/schemas.py` | `AiTranscribeRequest`, `AiTranscribedPage`, `AiTranscribeResponse` |
| `convert/schemas.py` | `MusicXmlToJianpuRequest/Response`, `JianpuToMusicXmlRequest/Response` |
| `export/schemas.py` | `ExportResponse`, `ExportMidiTextRequest` |
| `files/schemas.py` | `UploadPage`, `UploadResponse` |
| `history/schemas.py` | `PageCreate`, `PageUpdate`, `PageResponse`, `BatchCreateRequest`, `BatchResponse`, `BatchListItem`, `DeleteAllResponse` |
| `pipeline/schemas.py` | `PipelineResponse` |
| `recognize/schemas.py` | `RecognizeResponse` |
| `render/schemas.py` | 5 对 Request/Response |
| `settings/schemas.py` | `SettingsResponse`, `SettingsUpdateRequest` |
| `tasks/schemas.py` | `SSEProgressEvent` |

### 实体/配置
- `history/entities.py`：`HistoryPage`, `HistoryBatch` dataclass
- `settings/config.py`：`ToolConfig` dataclass
- `tasks/entities.py`：`TaskStatus` Enum, `TaskProgress` dataclass
- `common/errors.py`：`ExternalToolError`, `OCRError`, `AITranscriptionError`
- `common/paths.py`：`PROJECT_ROOT`
- `common/schemas.py`：`ErrorResponse`（未使用）

---

## 6. DAO 层 (`src/score_trans/dao/`)

| 文件 | 行数 | 职责 |
|---|---|---|
| `history/history_dao.py` | ~213 | SQLite 历史记录持久化（建表、迁移、CRUD） |
| `settings/settings_dao.py` | ~100 | SQLite key-value 配置存储（单例模式） |

---

## 7. Utils 层 (`src/score_trans/utils/`)

| 文件 | 行数 | 职责 |
|---|---|---|
| `bbox.py` | ~80 | 多格式 bbox → `(x1,y1,x2,y2)` 统一转换 |
| `dict_tools.py` | 12 | `first_present` 字典工具 |
| `env.py` | 42 | `.env` 文件加载器 |
| `json_parsing.py` | 35 | LLM 响应 JSON 解析 |
| `media.py` | 15 | 图片 → base64 data URL |
| `pdf.py` | 48 | PDF 页面 → PNG 渲染 |
| `text.py` | ~60 | OCR 文本清洗 |
