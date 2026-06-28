# 问题报告与改进建议

> 接 [architecture.md](./architecture.md)、[file-by-file.md](./file-by-file.md)

## 统计概览

| 类别 | 当前数量 | 较上次变化 |
|---|---|---|
| 高严重度 Bug | 0 | 持平 |
| 中严重度 Bug | 4 | ↓2（`_cfg_value` 已修复，Python OMR 预处理链已移除） |
| 低严重度问题 | 5+ | 持平 |
| 架构违规 | 2 | 持平 |
| 死代码符号 | 0（本轮确认项已清理） | ↓7 |
| 代码坏味道 | 20+ | 略降 |
| 安全问题 | 5 | ↓1（API key 不再明文返回） |
| 性能问题 | 6 | ↓1（未使用的 `cleanup_old` 已清理） |

> **验证日期**：2026-06-28。本次基于 2026-06-15 报告继续复核，并清理已确认死代码与错误状态记录。

### 2026-06-28 架构改进记录

- ✅ 后端持久化服务通过 `exec/composition.py` 进程级复用。
- ✅ 前端核心状态由含混的 Task Store 更名为 Score Workspace Module，保留兼容导出。
- ✅ Recognize / Convert / Export 的批量渲染请求构造集中到 `utils/batchRender.ts`。
- ✅ 前端 DTO 改为从 FastAPI OpenAPI 自动生成，并增加 CI 漂移检查。
- ✅ 所有异步 API adapter 统一返回 `{ data, error }`。
- ✅ `services/render` 包级公开接口收窄到渲染门面和核心 DTO。
- ✅ 新增 Windows CI，覆盖后端测试、前端类型检查、契约检查和生产构建。

---

## 一、高严重度 Bug

当前高严重度 Bug 数量为 **0**。上次报告中的 2 个高严重度问题均已修复：

### ~~1. AI Provider 相对导入点数错误~~ ✅ 已修复
- **位置**: `services/ai/providers/openai_compatible.py`（文件路径已重构，不再有 `provider.py` 嵌套目录）
- **验证结果**: 当前使用 `from ....models.common.errors import AITranscriptionError`，路径正确，运行时无 `ImportError`。

### ~~2. TaskManager SSE 流式传输完全失效~~ ✅ 已修复
- **位置**: `services/tasks/task_service.py`
- **验证结果**: 已重写为 asyncio-native 实现。`stream()` 与 `global_events()` 均为 async generator，通过 `asyncio.wait_for(queue.get(), ...)` 消费 Queue，不再使用 `asyncio.run()`。该问题已彻底消除。

### 历史误报
- **rendering.py beam 位置计算**（2026-06-05 已标记为误报）：`services/render/drawing/beams.py` 中 `max(...)` 用于将 beam 对齐到最低音符下方，符合简谱 SVG 坐标系约定，行为正确。

---

## 二、中严重度 Bug

### 1. OCR confidence 解析无保护
- **位置**: `services/ocr/parsing/parser.py` — `coerce_text_block`
- **问题**: `confidence = float(confidence)` 对非数值字符串（如 "high"）抛 `ValueError` 未捕获。
- **影响**: 单个异常块会导致整页 OCR 解析失败。
- **建议**: 加 `try/except ValueError`，异常时回退为 `confidence = None`。

### 2. JPEG 解析死循环风险
- **位置**: `services/files/image_info.py` — `_jpeg_dimensions`
- **问题**: 当 JPEG 段长度 `<= 2` 时，`handle.seek(max(0, length - 2), 1)` 不移动指针，导致 `while True` 死循环。
- **影响**: 某些畸形 JPEG 输入会使进程挂死。
- **建议**: 在 `length <= 2` 时 `break`；并增加读取失败后的安全退出条件。

### 3. exec 层广泛使用 HTTPException（架构违规）
- **位置**: `exec/history/actions.py`、`exec/files/actions.py`、`exec/export/actions.py`、`exec/render/actions.py`（grep 仍有 20+ 处命中）
- **问题**: exec 层直接 `from fastapi import HTTPException` 并抛出，违反分层架构。exec 不应依赖 FastAPI。
- **影响**: exec 层无法在非 FastAPI 上下文（如 CLI、测试）中复用。
- **建议**: 抛业务异常（如 `ValueError`、`FileNotFoundError`），由 API 层统一转换为 HTTP 响应。

### 4. MIDI rest 语义不正确
- **位置**: `services/export/export_service.py` — `export_midi`
- **问题**: rest 事件发送 `mido.Message("note_off", note=0, velocity=0, time=ticks)`，语义上不是休止而是关闭 note 0。
- **影响**: 功能上可生成有效 MIDI，但与标准休止语义不符；依赖接收端对 note 0 的容忍。
- **建议**: 将 rest 转换为后续事件的 `time` 偏移累积，不生成 note_off(note=0)。

### 历史已修复/误报

#### ~~`_cfg_value` 错误消息非 f-string~~ ✅ 已修复
- **位置**: `services/ai/core/prompts.py`
- **状态**: 当前错误消息已使用 f-string，且配置已迁移为 `ai_prompt.yaml`。

#### ~~PDF 预处理只渲染第一页~~ ✅ 已修复
- **位置**: 原 Python OMR 预处理模块
- **状态**: Python OMR 预处理链已移除。上传 PDF 仍在 `/files/upload` 中拆成逐页 PNG；直接识别 PDF 时交由 Audiveris 原生处理。

#### ~~beat_type=0 时 ZeroDivisionError~~ ❌ 误报
- **位置**: `domain/write/jianpu_text.py` — `score_to_jianpu_text`
- **验证结果**: `score_to_jianpu_text` 中 `beat_type` 仅用于字符串拼接 `f"{score.beats}/{score.beat_type}"`，不存在 `Fraction(beats * 4, 0)` 调用。`beat_type=0` 会在解析阶段即报错。

#### ~~MusicXML 音高推导可能 ValueError~~ ❌ 误报
- **位置**: `domain/parse/musicxml.py` — `_note_pitch`
- **验证结果**: 防御分支 `(relative + 1) % 12` 在数学上永远不会触发 `MAJOR_SCALE.index()` 失败。

---

## 三、架构违规

### 1. exec → api 反向依赖（系统性问题）
- **位置**: `exec/` 层仍有 4 个 actions.py 文件直接 import/raise `HTTPException`：`exec/history/actions.py`、`exec/files/actions.py`、`exec/export/actions.py`、`exec/render/actions.py`（grep 命中 20+ 处）。`exec/convert/actions.py`、`exec/pipeline/actions.py`、`exec/ai/actions.py`、`exec/recognize/actions.py` 已无 `HTTPException` 导入。
- **说明**: exec 层不应依赖 FastAPI。应改为抛业务异常，由 API 层统一转换。

### 2. services 内部循环引用
- **位置**: `services/ocr/providers/__init__.py`、`services/ocr/providers/openai_compatible.py`、`services/ocr/providers/dashscope.py`、`services/ai/core/prompts.py` 仍导入 `services/settings/api_keys.py` 或 `services/settings/provider_profiles.py`
- **说明**: 通过延迟/局部导入绕过循环依赖，但仍违反单向依赖原则。

---

## 四、同步阻塞路由

| 路由 | 状态 | 说明 |
|---|---|---|
| `POST /pipeline` | ✅ 已修复 | 路由改为提交后台任务并返回 `TaskSubmitResponse`，实际执行在 `exec/tasks/background.py:run_sync_task()` 中用 `asyncio.to_thread()` 进行，并受 `OMR_SEMAPHORE` 并发限制。 |
| `POST /recognize` | ✅ 已修复 | 同上，已改为后台任务模式。 |
| `POST /ai/transcribe` | ✅ 已修复 | 同上，LLM 多页转写改为后台任务模式。 |

当前长耗时接口已统一为：先 `POST` 提交任务拿到 `task_id`，再通过 `GET /tasks/{task_id}` 或 SSE `/tasks/{task_id}/events` 轮询/流式获取进度。

---

## 五、DI 工厂重复初始化（已缓解）

- **位置**: `api/dependencies.py`
- **状态**: Actions 仍按请求创建，以保留 AI 供应商设置即时生效的语义；其依赖的文件、设置、历史和文件读写 Module 已通过 `exec/composition.py` 进行进程级复用。
- **修复**: `UploadService` 的旧目录迁移仅在默认运行目录启用，并对同一目标每进程最多执行一次；显式测试/自定义目录不再复制全局旧缓存。
- **验证**: 全量后端测试由超过 3 分钟未完成降至约 10 秒。

---

## 六、死代码清单

| 文件 | 符号 | 说明 | 验证状态 |
|---|---|---|---|
| ~~`jianpu_tokens.py`~~ | ~~`PREFIX_SLASHES`~~ | ~~未被任何代码引用~~ | ❌ **误报**：`parsing/tokens.py` 有引用 |
| ~~`xml_utils.py`~~ | ~~`_read_mxl()`~~ | ~~已被 `_read_musicxml` 替代~~ | ✅ 已清理 |
| ~~`xml_utils.py`~~ | ~~`_first_child_name()`~~ | ~~未调用~~ | ✅ 已清理：此前“有 import”的说明不再适用，当前无引用 |
| ~~`write/jianpu_text.py`~~ | ~~`_duration_suffix()`~~ | ~~旧斜杠写法~~ | ❌ **误报**：`_duration_suffix` 在自身内部递归调用 |
| ~~`write/jianpu_text.py`~~ | ~~`_fmt_num()`~~ | ~~定义但未调用~~ | ❌ **误报**：`_text_block_to_directive` 中有 4 处调用 |
| ~~`write/musicxml.py`~~ | ~~`_duration_prefix()`~~ | ~~未使用~~ | ✅ 已清理 |
| ~~`parse/musicxml.py`~~ | ~~`_extract_part_names()`~~ | ~~未调用~~ | ✅ 已清理 |
| ~~`dict_tools.py`~~ | ~~`first_present()`~~ | ~~未调用~~ | ❌ **误报**：`ocr/parser.py` 和 `ai/service.py` 有引用 |
| ~~`models/common/schemas.py`~~ | ~~`ErrorResponse`~~ | ~~`app.py` 直接构造 dict 而非使用此 schema~~ | ✅ 已清理 |
| ~~`models/tasks/*`~~ | ~~`TaskProgress`, `TaskStatus`, `SSEProgressEvent`~~ | ~~完全未使用~~ | ❌ **误报**：任务系统重构后已大量使用 |
| ~~`exec/ai/actions.py`~~ | ~~`AiActions.get_config()`~~ | ~~未被路由调用~~ | ✅ 已清理 |
| ~~`exec/settings/actions.py`~~ | ~~`SettingsActions.get_config()`~~ | ~~未被路由调用~~ | ✅ 已清理 |
| ~~`external_tools.py`~~ | ~~`find_tool()`~~ | ~~定义但未调用~~ | ✅ 已清理 |
| ~~`convert/schemas.py`~~ | ~~`MusicXmlToJianpuResponse.jianpu_file_id`~~ | ~~接口实际只返回 `jianpu_text`~~ | ✅ 已清理 |
| ~~`pipeline/schemas.py`~~ | ~~`PipelineResponse.task_id`~~ | ~~始终返回 None~~ | ✅ 已清理：当前 schema 无此字段 |
| ~~`recognize/schemas.py`~~ | ~~`RecognizeResponse.task_id`~~ | ~~始终返回 None~~ | ✅ 已清理：当前 schema 无此字段 |

---

## 七、代码重复

| 位置 A | 位置 B | 重复内容 |
|---|---|---|
| `utils/bbox.py:_first_present` | `utils/dict_tools.py:first_present` | 逻辑相同但 `first_present` 已被多处引用，非死代码 |
| `svg/header.py:_svg_header` | `svg/header.py:_svg_page_header` | 大段重复 CSS 样式 |
| `services/ocr/core/text.py:infer_text_role` | `domain/parse/musicxml.py:_is_dynamic_name` | 力度标记集合不一致 |
| `domain/constants.py:DYNAMICS` | `services/render/utils/helpers.py:_is_dynamic_text` | 力度集合不同（10 项 vs 17 项） |
| `services/ai/transcription/normalization.py:extract_header/strip_header` | `domain/parse/jianpu_text.py:_read_new_syntax` | 头信息解析逻辑重复 |

---

## 八、安全问题

| 问题 | 位置 | 严重程度 | 状态 |
|---|---|---|---|
| 无上传文件大小限制 | `upload_service.py:save` | 中 | ❌ 仍存在 |
| ~~API key 明文返回~~ | ~~`settings/schemas.py:SettingsResponse`~~ | ~~中~~ | ✅ **已修复**：响应改为 `ocr_api_key_set` / `ai_api_key_set` / `assistant_api_key_set` 布尔标志 |
| Prompt injection（title/extra_prompt 直接插入 prompt） | `services/ai/core/prompts.py:build_jianpu_prompt` | 低 | ❌ 仍存在 |
| CORS `allow_methods=["*"]` 无生产开关 | `api/app.py` | 低 | ⚠️ 仍存在（来源可配置，但 methods/headers 仍全通） |
| `json_parsing.py` 无大小限制的 `json.loads` | `utils/json_parsing.py` | 低 | ⚠️ 仍存在 |
| SSL 证书未显式验证 | `services/ocr/client/client.py` 或 `services/ocr/providers/_http.py` | 低 | ⚠️ 仍存在 |

---

## 九、性能问题

| 问题 | 位置 | 状态 |
|---|---|---|
| 大图 base64 嵌入 JSON（无流式上传） | `services/ocr/client/client.py` 或 `services/ocr/providers/_http.py` | ❌ 仍存在 |
| 每次 OCR/AI 调用创建新 HTTP 客户端 | `services/ocr/providers/`、`services/ai/providers/` | ❌ 仍存在 |
| DAO 每次操作 open/close SQLite 连接 | `dao/history/history_dao.py`、`dao/settings/settings_dao.py` | ❌ 仍存在 |
| 环境变量函数体内每次读取（20+ 处） | 分散在多处 | ❌ 仍存在 |
| 正则未预编译 | `services/ocr/core/text.py`、`domain/parse/jianpu_text.py` | ❌ 仍存在 |
| `services/render/` 模块化渲染，无缓存 | `services/render/` | ❌ 仍存在 |
| ~~`cleanup_old` 每个过期目录写一次 index.json~~ | ~~`services/files/upload_service.py`~~ | ✅ 已清理：未使用的清理入口已删除 |

---

## 十、测试覆盖评估

| 模块 | 覆盖质量 | 缺口 |
|---|---|---|
| `domain/parse/jianpu_text.py` | **好** | 缺错误路径测试 |
| `domain/parse/musicxml.py` | **好** | 缺多声部测试 |
| `domain/write/` | 中 | 仅通过 roundtrip 间接覆盖 |
| `exec/` 层 | 中 | `settings`、`files` 的 Actions 未直接测试；任务提交流程未覆盖 |
| `services/render/` | **好** | beam/tie/slur 细节未覆盖 |
| `services/tasks/` | 中 | 已覆盖进度、完成、过期、恢复和后台调度；仍缺并发与 SSE 背压测试 |
| `services/ai/` | 好 | provider 集成测试不足；prompt 注入、规范化路径未覆盖 |
| `utils/*` | **低** | `image_info.py`、`json_parsing.py`、`bbox.py` 等无直接单元测试 |
| `config/*` | **无** | 无测试 |

---

## 十一、改进建议优先级

### 立即修复（影响正确性或可能导致挂死/失败）
1. JPEG 尺寸解析死循环（`services/files/image_info.py:_jpeg_dimensions`）
2. OCR confidence `float()` 未保护（`services/ocr/parsing/parser.py:coerce_text_block`）

### 短期清理（架构债与技术债）
3. 清理 exec 层剩余 4 个文件的 `HTTPException`（`history/files/export/render`），改为业务异常
4. ~~消除 `api/dependencies.py` 下持久化 Module 的重复初始化~~ ✅ 已通过 `exec/composition.py` 复用
5. 统一 `DYNAMICS` 力度集合（`domain/constants.py` 与 `services/render/utils/helpers.py`）
6. DAO 层引入连接池或至少复用连接

### 中期改进
8. 上传文件大小限制与类型校验
9. AI prompt 输入转义/过滤，防止 prompt injection
10. MIDI rest 改为标准语义（time 偏移累积）
11. 补充 `utils/*`、`services/tasks/`、`services/ocr/parsing` 的单元测试
