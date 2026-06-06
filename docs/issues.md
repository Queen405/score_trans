# 问题报告与改进建议

> 接 [architecture.md](./architecture.md)、[file-by-file.md](./file-by-file.md)

## 统计概览

| 类别 | 数量 |
|---|---|
| 高严重度 Bug | 1 |
| ~~误报已移除~~ | ~~2~~ |
| 中严重度 Bug | 6 |
| ~~误报已移除~~ | ~~2~~ |
| 低严重度问题 | 5+ |
| 架构违规 | 2 |
| 死代码符号 | 9（原 16，7 个为误报） |
| 代码坏味道 | 25+ |
| 安全问题 | 6 |
| 性能问题 | 7 |

> **验证日期**：2026-06-05，所有条目已通过代码搜索验证。标记为 ❌ 的条目为原始分析中的误报，已确认实际代码行为正确或符号有实际引用。

---

## 一、高严重度 Bug

### 1. AI Provider 相对导入点数错误
- **位置**: `services/ai/providers/openai_compatible/provider.py`
- **问题**: `from .....models.common.errors` 使用了 5 个点，从 `services/ai/providers/openai_compatible/` 退回 5 级会到达 `src/` 而非 `score_trans/`。正确应为 4 个点（`....models`）。
- **影响**: 运行时 `ImportError`，AI 转录功能可能不可用。
- **建议**: 验证实际导入路径，修正点数。

### 2. TaskManager SSE 流式传输完全失效
- **位置**: `services/tasks/task_service.py`
- **问题**: `stream_sync` 方法在同步生成器中用 `asyncio.run()` 创建新事件循环来消费 `asyncio.Queue`，但 Queue 绑定到创建 TaskManager 时的事件循环，不同事件循环无法互相操作队列。
- **影响**: SSE 进度流完全无法工作。
- **状态**: 目前未被路由实际调用（死代码），但一旦启用就会失败。
- **建议**: 重写为 asyncio-native 方案，或改用 `asyncio.Queue` 的线程安全替代品。

### ~~3. ~~❌ rendering.py beam 位置计算~~（误报）
- **位置**: `services/render/rendering.py` — `_render_beam_run`
- **原始判断**: beam 的 y 坐标使用 `max(...)` 取所有音符的最大 y 值，应使用 `min(...)`。
- **验证结果**: **误报**。简谱中 duration line（减时线/beam）画在音符**下方**。SVG 坐标系 y 向下增大，`_duration_line_y` 返回值越大 = 越低。`max(...)` 将所有音符的 beam 对齐到最低那条线，确保 beam 不会穿过任何音符，这是**正确的渲染行为**。

---

## 二、中严重度 Bug

### 4. `_cfg_value` 错误消息非 f-string
- **位置**: `services/ai/base.py`
- **问题**: 错误消息 `"请在 {CONFIG_DIR / 'ai_prompt.json'} 中配置。"` 缺少 `f` 前缀，`{CONFIG_DIR}` 不会展开。
- **建议**: 改为 `f"请在 {CONFIG_DIR / 'ai_prompt.json'} 中配置。"`

### 5. OCR confidence 解析无保护
- **位置**: `services/ocr/parser.py` — `coerce_text_block`
- **问题**: `confidence = float(confidence)` 对非数值字符串（如 "high"）抛 ValueError 未捕获。
- **建议**: 加 `try/except ValueError`。

### 6. JPEG 解析死循环风险
- **位置**: `services/files/image_info.py` — `_jpeg_dimensions`
- **问题**: 段长度为 0 时 `max(0, -2) = 0`，`seek(0, 1)` 不移动指针导致死循环。
- **建议**: 检测 `length <= 2` 时 break。

### 7. PDF 只渲染第一页
- **位置**: `services/recognize/image_preprocessing.py` — `prepare_omr_input`
- **问题**: `pdf_page_to_png` 只渲染第一页（`page_001`），多页 PDF 后续页面丢失。
- **建议**: 改为渲染所有页或至少提供选项。

### 8. exec 层广泛使用 HTTPException（架构违规）
- **位置**: `exec/convert/actions.py`, `exec/files/actions.py`, `exec/pipeline/actions.py`, `exec/export/actions.py`, `exec/ai/actions.py`, `exec/recognize/actions.py`, `exec/render/actions.py`（共 7 个文件，20 处）
- **问题**: exec 层大量直接 `from fastapi import HTTPException` 并抛出，违反分层架构。exec 不应依赖 FastAPI。
- **影响**: exec 层无法在非 FastAPI 上下文（如 CLI、测试）中复用。
- **建议**: 抛业务异常（如 `ValueError`, `FileNotFoundError`），由 API 层统一转换为 HTTP 响应。

### ~~9. ~~❌ beat_type=0 时 ZeroDivisionError~~（误报）
- **位置**: `domain/write/jianpu_text.py` — `score_to_jianpu_text`
- **原始判断**: `Fraction(beats * 4, 0)` 抛 ZeroDivisionError。
- **验证结果**: **误报**。`score_to_jianpu_text` 中 `f"{score.beats}/{score.beat_type}"` 只做字符串拼接，不存在 `Fraction(beats * 4, beat_type)` 的调用。`beat_type` 始终由解析器赋值为正整数（默认 4），且在 Measure 层面使用时 `Fraction(4, beat_type)` 在 `_normalize_measure` 中调用——如果 `beat_type=0` 会在解析阶段就已报错，不会传播到 write 层。

### ~~10. ~~❌ MusicXML 音高推导可能 ValueError~~（误报）
- **位置**: `domain/parse/musicxml.py` — `_note_pitch`
- **原始判断**: 不在大调音阶上的音符，`MAJOR_SCALE.index(...)` 可能抛 ValueError。
- **验证结果**: **误报**。`MAJOR_SCALE = [0, 2, 4, 5, 7, 9, 11]` 覆盖大调 7 个音级。对于任意 `relative`（0-11），不在 MAJOR_SCALE 中的 5 个值 `[1, 3, 6, 8, 10]`，`(relative + 1) % 12` 一定在 MAJOR_SCALE 中（因为 +1 后变为 `[2, 4, 7, 9, 11]`，全部在集合内）。因此第 3 个分支**永远不会执行**，不存在 ValueError 风险。该分支可视为防御性代码。

### 11. MIDI rest 语义不正确
- **位置**: `services/export/export_service.py` — `export_midi`
- **问题**: rest 事件发送 `note_off(note=0)`，语义不正确（应发送空白时间）。
- **建议**: 改为 `track.append(mido.Message("note_off", note=0, velocity=0, time=ticks))` 保持当前行为（功能无害）或使用 `time` 偏移。

---

## 三、架构违规

### 1. exec → api 反向依赖（系统性问题）
- **位置**: `exec/` 层 7 个 actions.py 文件，共 20 处 `raise HTTPException(...)`
- **说明**: exec 层不应依赖 FastAPI。应改为抛业务异常，由 API 层统一转换。

### 2. services 内部循环引用
- **位置**: `ocr/utils.py`, `ai/base.py`, `ai/providers/*/provider.py` → `settings_service`
- **说明**: 通过局部导入绕过循环依赖，但违反单向依赖原则。

---

## 四、同步阻塞路由

| 路由 | 问题 | 建议 |
|---|---|---|
| `POST /pipeline` | Audiveris subprocess 可能耗时数分钟，阻塞事件循环 | 改用 `asyncio.to_thread()` 或后台任务 + SSE |
| `POST /recognize` | 同上 | 同上 |
| `POST /ai/transcribe` | 多页 LLM 调用，阻塞事件循环 | 同上 |

---

## 五、DI 工厂无缓存

- **位置**: `api/dependencies.py`
- **问题**: 每次请求创建新 Actions 实例，内部 Service/DAO 重复初始化。
- **建议**: 使用 `@lru_cache` 或 app state 单例。

---

## 六、死代码清单

| 文件 | 符号 | 说明 | 验证状态 |
|---|---|---|---|
| ~~`jianpu_tokens.py`~~ | ~~`PREFIX_SLASHES`~~ | ~~未被任何代码引用~~ | ❌ **误报**：`rendering.py` 有 5 处引用 |
| `xml_utils.py` | `_read_mxl()` | 已被 `_read_musicxml` 替代 | ✅ 确认 |
| ~~`xml_utils.py`~~ | ~~`_first_child_name()`~~ | ~~未调用~~ | ❌ **误报**：`parse/musicxml.py` 有 import |
| ~~`write/jianpu_text.py`~~ | ~~`_duration_suffix()`~~ | ~~旧斜杠写法~~ | ❌ **误报**：`_duration_suffix` 在自身内部递归调用 |
| ~~`write/jianpu_text.py`~~ | ~~`_fmt_num()`~~ | ~~定义但未调用~~ | ❌ **误报**：`_text_block_to_directive` 中有 4 处调用 |
| `write/musicxml.py` | `_duration_prefix()` | 未使用 | ✅ 确认 |
| `parse/musicxml.py` | `_extract_part_names()` | 未调用 | ✅ 确认 |
| ~~`dict_tools.py`~~ | ~~`first_present()`~~ | ~~未调用~~ | ❌ **误报**：`ocr/parser.py` 和 `ai/service.py` 有引用 |
| `models/common/schemas.py` | `ErrorResponse` | `app.py` 直接构造 dict 而非使用此 schema | ✅ 确认 |
| `models/tasks/*` | `TaskProgress`, `TaskStatus`, `SSEProgressEvent` | 完全未使用（为未来异步任务预留） | ✅ 确认 |
| `exec/ai/actions.py` | `AiActions.get_config()` | 未被路由调用 | ✅ 确认 |
| `exec/settings/actions.py` | `SettingsActions.get_config()` | 未被路由调用 | ✅ 确认 |
| `external_tools.py` | `find_tool()` | 定义但未调用 | ✅ 确认 |
| `convert/schemas.py` | `MusicXmlToJianpuResponse.jianpu_file_id` | 始终返回 None | ✅ 确认 |
| `pipeline/schemas.py` | `PipelineResponse.task_id` | 始终返回 None | ✅ 确认 |
| `recognize/schemas.py` | `RecognizeResponse.task_id` | 始终返回 None | ✅ 确认 |

---

## 七、代码重复

| 位置 A | 位置 B | 重复内容 |
|---|---|---|
| `utils/bbox.py:_first_present` | `utils/dict_tools.py:first_present` | 逻辑相同但 `first_present` 已被 `ocr/parser.py` 引用，非死代码 |
| `rendering.py:_svg_header` | `rendering.py:_svg_page_header` | 大段重复 CSS 样式 |
| `ocr/text.py:infer_text_role` | `parse/musicxml.py:_is_dynamic_name` | 力度标记集合不一致 |
| `domain/constants.py:DYNAMICS` | `rendering.py:_is_dynamic_text` | 力度集合不同（10 项 vs 17 项） |
| `ai/service.py:extract_header/strip_header` | `domain/parse/jianpu_text.py:_read_new_syntax` | 头信息解析逻辑重复 |

---

## 八、安全问题

| 问题 | 位置 | 严重程度 |
|---|---|---|
| 无上传文件大小限制 | `upload_service.py:save` | 中 |
| API key 明文返回 | `settings/schemas.py:SettingsResponse` | 中 |
| Prompt injection（title/extra_prompt 直接插入 prompt） | `ai/base.py:build_jianpu_prompt` | 低 |
| CORS `allow_methods=["*"]` 无生产开关 | `api/app.py` | 低 |
| `json_parsing.py` 无大小限制的 `json.loads` | `utils/json_parsing.py` | 低 |
| SSL 证书未显式验证 | `ocr/client.py:send_request` | 低 |

---

## 九、性能问题

| 问题 | 位置 |
|---|---|
| 大图 base64 嵌入 JSON（无流式上传） | `ocr/client.py` |
| 每次 OCR/AI 调用创建新 HTTP 客户端 | `ocr/providers.py`, `ai/providers/*/provider.py` |
| DAO 每次操作 open/close SQLite 连接 | `dao/history/history_dao.py`, `dao/settings/settings_dao.py` |
| 环境变量函数体内每次读取（20+ 处） | 分散在多处 |
| 正则未预编译 | `ocr/text.py`, `parse/jianpu_text.py` |
| `rendering.py` 1430 行单文件，渲染无缓存 | `services/render/rendering.py` |
| `cleanup_old` 每个过期目录写一次 index.json | `upload_service.py` |

---

## 十、测试覆盖评估

| 模块 | 覆盖质量 | 缺口 |
|---|---|---|
| `domain/parse/jianpu_text.py` | **好** | 缺错误路径测试 |
| `domain/parse/musicxml.py` | **好** | 缺多声部测试 |
| `domain/write/` | 中 | 仅通过 roundtrip 间接覆盖 |
| `exec/` 层 | 中 | `settings`, `files` 的 Actions 未直接测试 |
| `services/render/rendering.py` | **好** | beam/tie/slur 细节未覆盖 |
| `services/tasks/` | **无** | 完全未测试 |
| `services/ai/` | 好 | LangChain provider 未集成测试 |
| `utils/*` | **低** | 无直接单元测试 |
| `config/*` | **无** | 无测试 |

---

## 十一、改进建议优先级

### 立即修复
1. 验证 AI provider 的相对导入点数（`.....models` → `....models`？）
2. 清理 exec 层 HTTPException（7 个文件，20 处），改为业务异常
3. 统一 `DYNAMICS` 力度集合

### 短期优化
4. 将长耗时路由改为 `asyncio.to_thread()` 或后台任务
5. `dependencies.py` 加 `@lru_cache` 或 app state 单例
6. 清理真死代码（9 个确认符号）
7. DAO 层引入连接池或至少复用连接
8. 修复 `_cfg_value` f-string 缺失

### 中期改进
9. `TaskManager` 重写为 asyncio-native
10. 将 `langchain`/`langchain-openai` 移至 optional 依赖
11. 补充 `utils/*` 和 `services/tasks/` 的单元测试
12. `ErrorResponse` schema 应被 `app.py` 异常处理器使用
