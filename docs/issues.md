# 问题报告与改进建议

> 接 [architecture.md](./architecture.md)、[file-by-file.md](./file-by-file.md)
>
> **最近全面审计：2026-07-14**（5 个并行子代理逐字逐句通读全部 ~310 个源文件 / ~43,500 行代码）
> **上一轮审计：2026-07-03**（详见 [AUDIT_REPORT.md](AUDIT_REPORT.md)）

## 统计概览

| 类别 | 当前数量 | 较上次变化 |
|---|---|---|
| 高严重度 Bug（P0） | 0 | 持平 |
| 新回归 P1 | 2 | ↑2（CI 消失、requirements.txt 不同步） |
| 中严重度 Bug（P2） | 25 | ↑（含新发现） |
| 低严重度问题（P3） | 30+ | 持平 |
| 架构违规 | 1（5 处 exec→domain 已知违规，FastAPI 违规清零） | ↓1 |
| 死代码符号 | 8+ | ↑（新发现孤立符号） |
| 代码坏味道 | 20+ | 持平 |
| 安全问题 | 2（无代码签名、Gradle 校验禁用） | ↓3 |
| 性能问题 | 5 | 持平 |

> **关键进展**：2026-07-03 报告中的 ~40 项 P0/P1 问题已全部修复，含双变音记号、等音拼写、连音、重复记号、多声部、XML 炸弹、SSRF、路径遍历、上传限制、Bearer 认证、exec HTTPException 清零等。

---

## 一、新回归 P1（立即修复）

### N1. `requirements.txt` 与 `pyproject.toml` 严重不同步
- **位置**：`requirements.txt:1-9`
- **问题**：仅 8 行，缺少 `fonttools>=4.59`、`pyyaml>=6.0`（`pyproject.toml` 声明的运行时依赖），且 `pytest>=8` 仍列为运行时依赖。若用 `pip install -r requirements.txt` 安装，`yaml.safe_load`（ai_prompt 加载）和 `fontTools`（渲染）会 `ImportError`。
- **影响**：按 requirements.txt 安装的环境无法运行。
- **建议**：删除该文件（依赖 `uv.lock`）或从 `pyproject.toml` 运行时依赖重新生成（不含 test deps）。

### N2. 无任何 CI 流水线
- **位置**：`.github/workflows/` 目录不存在
- **问题**：上次审计尚有 Windows CI，现已完全消失。无 `ruff check`、无 `ruff format --check`、无 pytest、无覆盖率、无安全扫描、无 OpenAPI 契约漂移检查、无前端 lint/typecheck。
- **影响**：所有质量门禁靠人工执行，回归风险高。
- **建议**：恢复 CI，至少包含 `ruff check` + `ruff format --check` + `python -m pytest` + `vue-tsc --noEmit` + `pnpm lint` + `pnpm check:api-types`。

---

## 二、P2 — 短期修复

### 域名层（domain/）

| # | 问题 | 位置 | 说明 |
|---|---|---|---|
| N3 | 双附点/三附点音符在 jianpu→MusicXML 丢失 `<type>` 和 `<dot>` | `domain/write/musicxml.py:663-665` | `_fraction_to_type` 只匹配 `value + value/2`（单附点），双附点 `Fraction(7,1)` 不匹配，返回 `("quarter", False)`，`<duration>` 与 `<type>` 不一致。解析侧已正确支持双附点。 |
| N4 | Tie 锚点误用 slur 角色的 source_id | `domain/write/jianpu_text.py:403,415` | `event.source_roles.get("slur_start"/"slur_stop")` 应为 tie 角色。复制粘贴错误，导致 tie 锚点标错、slur ID 重复输出。 |
| N5 | Wedge/pedal/octave-shift 方向丢失 `direction_kind` | `domain/parse/musicxml.py:1161-1191` | 这三类方向调用 `_measure_text_block` 时未传 `direction_kind`，默认 None，写出侧变成 `<words>` 而非 `<wedge>`/`<pedal>`。渐强渐弱 wedge 往返丢失。 |
| N6 | `looks_like_jianpu_text` 正则 `d+` 应为 `\d+` | `services/ai/core/parsing.py:51` | `(?:[whqs]|d+)?` 中 `d+` 匹配字面字符 `d`，而非数字。影响非 JSON AI 响应回退判断。 |

### API / Exec 层

| # | 问题 | 位置 | 说明 |
|---|---|---|---|
| N7 | `external_tool_error_handler` 硬编码 `stage="audiveris"` | `api/app.py:125` | `ExternalToolError` 也用于 Java/其他工具失败，但响应总是标记 audiveris，误导前端。 |
| N8 | `api/history/routes.py` 全部用同步 `def` | `api/history/routes.py:24-108` | 11 个处理器都是 `def`（非 `async def`），SQLite 调用阻塞事件循环。其他路由已统一 `async def`+`to_thread`。 |
| N9 | `except Exception: return None` 静默吞错集群 | `exec/files/actions.py:72-73`、`exec/recognize/actions.py:146,156`、`exec/pipeline/actions.py:506` | PDF 转图、overlay 生成、omr 注册失败时静默返回 None，用户无反馈。至少应记录日志。 |

### 前端（Vue/TS）

| # | 问题 | 位置 | 说明 |
|---|---|---|---|
| N10 | AI 聊天流无法中断 | `stores/assistant.ts:19-24`（`abortStream` 未在 return 中暴露） | 切走组件时 SSE 流仍在跑，浪费带宽且无 UI 可停。 |
| N11 | `tasks.stream()` 不接受外部 AbortSignal | `api/tasks.ts:21-27` | 组件卸载后流/poller 仍跑到任务结束。 |
| N12 | `(globalThis as any).api` 仍在使用 | `ConvertView.vue:1511`、`settings.ts:338,347,398,414`、`ConversionSettingsPanel.vue:275`、`StorageSettingsPanel.vue:157` | preload 已提供类型化 `BackendAPI`，这些 `as any` 已不必要且破坏类型安全。 |
| N13 | `waitForTaskResult<T>` 用 `completed.result as T` 绕过校验 | `RecognizeView.vue:1108` | 主路径直接强转，已存在的 `isPipelineResponse`/`isAiTranscribeResponse` 守卫只在 resume 路径用。 |
| N14 | `JianpuPlayer` 去重键取前 50 字符 | `JianpuPlayer.vue:180` | 共享前缀的不同简谱会复用旧 MIDI。 |
| N15 | `usePlayer.ts` 只用第一个 tempo | `usePlayer.ts:100` | MIDI 中的速度变化不生效。 |
| N16 | workspace 每 batch 的 Map 清空时未清理 | `stores/workspace.ts:674-709` | `removePage` 置空数组但未 delete `batchRenderPageOcrTexts` 等键，长会话 OCR 文本无界增长。 |
| N17 | `liveRecognitionState` 模块级 Map 可能泄漏 | `utils/liveRecognitionState.ts:12-13` | 若识别未走完就离开，条目不释放。需确认所有路径调用 `clearLiveRecognitionPage`。 |
| N18 | FileUploader 不显示上传错误 | `components/FileUploader.vue:53` | `useFileUpload` 返回 `error` 但组件未解构，失败静默继续下一文件。 |
| N19 | `programmaticUpdate` 依赖 nextTick 时序 | `ConvertView.vue:585-609` | 脆弱，Vue 调度变化可能导致 dirty-mark 错误。建议改用 generation token。 |

### 构建 / 供应链

| # | 问题 | 位置 | 说明 |
|---|---|---|---|
| N20 | `build-app.py` 禁用 Gradle SHA-256 校验 | `build-app.py:244-256` | 注释掉 `distributionSha256Sum=` 并设 `validateDistributionUrl=false`，削弱供应链完整性。 |
| N21 | 无代码签名 | `pyinstaller.spec:107`、`electron-builder.yml` | SmartScreen 会拦截未签名发行版。 |
| N22 | `ai_prompt.yaml` 用 ✅ 标注失败示例 | `config/ai_prompt.yaml:206-213` | 失败示例（带 ❌）却以 ✅ 绿勾开头，语义矛盾，可能误导 LLM。 |
| N23 | Electron 33 已 EOL | `desktop/package.json:32` | 当前稳定版 36+，缺 Chromium 安全补丁。 |
| N24 | README 宣称 MuseScore 导出但未测试 | `README.md:20` | 测试实际用 PyMuPDF 从 SVG 页生成 PDF，MuseScore CLI 路径无覆盖。 |

### 性能

| # | 问题 | 位置 | 说明 |
|---|---|---|---|
| N25 | `_ancestor`/`_parent` O(n²) | `services/correct/musicxml_patch.py:82-97` | 每次删除遍历整树，大谱面慢。应用 parent map。 |
| N26 | 无 HTTP client 复用 | `services/ai/providers/_http.py:46,83`、`services/ocr/providers/_http.py:38` | 每次调用新建 httpx client，重付 TLS 握手。 |

---

## 三、P3 — 中期清理

### 死代码

| 符号 | 位置 | 说明 |
|---|---|---|
| `SEMITONE_TO_STEP` | `domain/constants.py:42-55` | 等音拼写修复后已无人引用 |
| `_render_batch_a4_without_page_ocr` | `exec/render/actions.py:651` | 定义但全仓库无调用 |
| `A4RenderTheme` / `A4_RENDER_THEME` | `services/render/options.py:8-23` | 定义但无导入 |
| `RenderOptions` ~20 个未用字段 | `services/render/options.py:38-62` | renderer 只读 margin/note_font_size 等 ~7 个字段 |
| `RenderAnchor` | `models/provenance/schemas.py:86` | 定义并导出但无使用 |
| `build_request` / `send_request` | `services/ocr/client/client.py` | 无调用者（`ocr_prompt_for_model` 仍被使用） |
| `block_cipher = None` | `pyinstaller.spec:9` | PyInstaller 6 已忽略 |
| `get-backend-url` legacy handler | `desktop/src/main/index.ts:117-119` | 已被 `get-backend-connection` 取代 |

### 代码异味

| 问题 | 位置 | 说明 |
|---|---|---|
| A4 常量 1240/1754/84 多处重复 | `exec/render/actions.py:829,858`、`exec/pipeline/actions.py:350`、`domain/text_placement.py:16-20` | 应提取共享常量 |
| `parse_jianpu_score` 262 行+19 个 nonlocal | `domain/parse/jianpu_text.py:291-553` | 建议提取 `_MeasureBuilder` 类 |
| 巨型 Vue 组件 | RecognizeView 2624、ConvertView 2595、SyntaxView 1236 行 | 应拆分 |
| `raise ValueError(str(exc)) from exc` 空操作 | `exec/render/actions.py:355-356,414-415` | 捕获后原样重抛，应删除 try |
| 渲染魔法数字 | `services/render/engraving/renderer.py` 多处 | chord_gap=25、bbox height 76/51、tuplet y=-29 等 |
| `_utf16_length` 重复定义 | `domain/parse/jianpu_text.py:287,671` | 两处相同定义，第一处被遮蔽 |
| jianpuSyntax 重复正则 | `utils/jianpuSyntax.ts:20-23` ≡ `utils/jianpuPlayback.ts` | TOKEN_PATTERN 等常量重复 |

### 测试脆弱

| 问题 | 位置 | 说明 |
|---|---|---|
| 精确命令行参数列表断言 | `tests/test_recognize_external_tools.py:177-203,235-245` | CLI flag 顺序变化即断 |
| 二进制 fixture + 精确像素 | `tests/test_overlay.py:18-23,37-38` | 依赖提交的 .omr 文件 |
| 精确浮点断言 | `tests/test_text_attachments.py:82,106,171-172` | `relative_y == 0.41875` |
| composition 仅 13 行 | `tests/test_composition.py` | 整个组合根只有 1 个测试 |
| Vitest/Playwright 未配置 | `desktop/` | 组件级/E2E 测试缺失（node:test 工具测试已有 7 个） |

### 配置 / 文档

| 问题 | 位置 | 说明 |
|---|---|---|
| `env.example` 缺 `SCORE_TRANS_WORKDIR` | `backend/score_trans/config/env.example` | 变量存在于 `settings.py:84` 但文档未列 |
| 根 `AGENTS.md` 过时 | `AGENTS.md` Critical Pitfalls | "test_render.py ~1300 行脆弱断言"已不成立（现 208 行 ET-based）；"exec 20 处 HTTPException"已清零 |
| `eslint.config.mjs` 关闭 `no-explicit-any` | `desktop/eslint.config.mjs:54` | 与项目类型安全目标冲突 |
| `dao/settings_dao.py` 无 WAL/busy_timeout | `dao/settings/settings_dao.py:45-48` | 与 history_dao/chat_dao 不一致 |
| `dao/tasks/task_dao.py` 无 busy_timeout | `dao/tasks/task_dao.py:27-31` | 同上 |
| `test_architecture.py` 允许 dao/domain→utils | `tests/test_architecture.py:15-22` | 与 AGENTS.md "models only" 描述矛盾 |
| README 截图 TODO | `README.md:11-12` | `<!-- TODO: 替换为真实截图 -->` |
| `pyinstaller_entry.py` int(port) 未捕获 | `pyinstaller_entry.py:25` | 坏输入报 traceback |

### 前端小问题

| 问题 | 位置 | 说明 |
|---|---|---|
| `renderAssistantMessage` 每次 render 重解析 markdown | `AiAssistant.vue:152` | O(n·m) per render，长聊天卡顿 |
| `noteSpans`/`highlightedLines` 每次按键重算 | `JianpuEditor.vue:147-148` | 大谱面输入延迟 |
| 归一化坐标启发式 ≤1.5 脆弱 | `PublicationPreview.vue:175` | 像素 [0,0,1,1] 被误判为归一化 |
| 15s SVG 超时不区分错误类型 | `PublicationPreview.vue:377` | 统一显示"SVG 加载失败" |
| `getBBox()` 静默 try/catch | `PublicationPreview.vue:456-460` | 未渲染元素静默返回 |
| `body.userSelect` 卸载时未重置 | `PublicationPreview.vue:551-556` | 拖拽中卸载组件导致 body 保持 none |
| `fileExists` 失败 fail-open 返回 true | `api/client.ts:224-234` | 探测失败时假定文件存在 |
| `usePlayer.loadMidi` 无 abort signal | `usePlayer.ts:329-335` | 快速切换 URL 时旧 fetch 覆盖新 |
| `usePlayer` 自动停止可能截断尾音 | `usePlayer.ts:272-275` | rAF ~16ms 粒度超调 |

---

## 四、架构违规

### 1. exec→domain 已知违规（5 处，已减少）
- **位置**：`test_architecture.py:24-30` 中 `KNOWN_LAYER_VIOLATIONS` 含 5 个 `("exec/.../actions.py", "domain")` 条目
- **状态**：较上次 7 处减少 2 处。FastAPI 导入违规已从 7 处清零（`test_no_fastapi_imports_outside_api` 断言 `offenders == set()`）。
- **说明**：这 5 处是已知技术债，架构测试允许但无清理强制机制。

---

## 五、历史问题验证状态

### 已修复（~40 项，详见 [AUDIT_REPORT.md](AUDIT_REPORT.md) 各章）

**P0 全部修复**：缓存删引用文件(1.1)、时值往返 whole-1(1.2)、双附点解析(1.3)、TaskManager 双移除(1.4)、pipeline 空渲染 IndexError(1.5)、AI 孤立用户消息(1.6)、应用关闭死循环(1.8)、`.sorce_trans` typo(1.9)、PDF max_pages=0(1.10)、HTTP 空 choices IndexError(1.11)、exec assert(1.12)。

**P1 音乐理论全部修复**：双变音记号(2.1)、等音拼写(2.2)、色音调号方向(2.3)、重复记号/结尾段(2.4/2.5)、共享编号嵌套连音(2.6)、连音时值硬编码(2.7)、跨小节连音(2.8)、多声部输出(2.9)、标题/速度/表情(2.10)、微音程(2.11)、八度点(2.12, render 重写)、力度词汇(2.13)。

**P1 安全全部修复**：无认证(4.1→Bearer)、SSRF(4.2→ArrayBuffer-only)、路径遍历(4.3→validateExportDirectory)、XML 炸弹(4.6→safe_xml)、上传无限制(4.7→request_limits)、API key 明文(已修复)。

**P2 架构全部修复**：models 导入 config(3.1)、exec HTTPException(3.2, 7→0)、异步路由同步阻塞(3.3)、config↔utils 循环(3.4)。

**P2 功能缺陷全部修复**：简谱解析 6 项(5.1)、MusicXML 解析 3 项(5.2)、简谱生成 3 项(5.3)。

**前端 P3 大量修复**：log 无界(6.1a)、FileUploader 模块级 queue(6.1b)、RecognizeView 模块级 Map(6.1c)、AiAssistant setTimeout(6.1d)、LogPanel ref/`:key`(6.1e/f)、assistant mutation/deleteSession(6.1g/h)、JianpuEditor 自动格式(6.1i)、JianpuPlayer 音量/MIDI 错误(6.1j/k)、SvgPreview v-html(文件删除)。

### 仍存在

| 历史编号 | 当前状态 | 说明 |
|---|---|---|
| 7.3 巨型函数/组件 | 仍存在 | RecognizeView 2624、ConvertView 2595、parse_jianpu_score 262 行 |
| 7.5 API 不对称 | 仍存在 | `jianpu_to_musicxml` 无 `accidental_mode` |
| 8.2 测试脆弱断言 | 部分仍存在 | test_recognize_external_tools、test_overlay、test_text_attachments、test_composition |
| 8.3 架构测试已知违规 | 部分修复 | FastAPI 7→0；层违规 7→5 |
| 9.1 CI 缺失步骤 | **恶化** | 从"缺步骤"变成"无 CI"（见 N2） |
| 9.2 requirements.txt | **恶化** | 不同步，缺 fonttools/pyyaml（见 N1） |
| 9.2 Electron 过时 | 仍存在 | 仍 33（见 N23） |
| 9.2 无 [tool.ruff] | 仍存在 | — |
| 9.3 README TODO | 仍存在 | — |
| 9.3 env.example 缺 WORKDIR | 仍存在 | — |
| 9.3 ai_prompt.yaml ✅ 标失败 | 仍存在 | 行号 205→206（见 N22） |

---

## 六、改进建议优先级

### 立即修复（P1）
1. 删除或重新生成 `requirements.txt`（从 `pyproject.toml` 运行时依赖，不含 test deps）
2. 恢复 CI：`ruff check` + `ruff format --check` + pytest + `vue-tsc` + `pnpm lint` + `check:api-types`

### 短期修复（P2）
3. 修复 `_fraction_to_type` 支持双/三附点（`domain/write/musicxml.py:663-665`）
4. 修复 tie 锚点角色（`domain/write/jianpu_text.py:403,415`）
5. 补全 wedge/pedal/octave-shift 的 `direction_kind`（`domain/parse/musicxml.py:1161-1191`）
6. 修复 `looks_like_jianpu_text` 正则 `d+` → `\d+`（`services/ai/core/parsing.py:51`）
7. `api/history/routes.py` 改为 `async def`+`to_thread`
8. `external_tool_error_handler` stage 从异常派生
9. 静默 `except Exception: return None` 至少加日志
10. 暴露 `abortStream`，`tasks.stream` 接受 AbortSignal
11. 清除 `(globalThis as any).api`，用类型化 `window.api`
12. `waitForTaskResult` 用守卫校验而非 `as T`
13. 升级 Electron 33 → 36+
14. 修复 `ai_prompt.yaml:206-213` 用中性符号标注失败示例
15. workspace per-batch Map 清理 + `liveRecognitionState` 边界化

### 中期改进（P3）
16. 清理死代码（`SEMITONE_TO_STEP`、`_render_batch_a4_without_page_ocr`、`A4RenderTheme`、`RenderOptions` 未用字段、`RenderAnchor`、ocr `build_request`/`send_request`）
17. 提取 A4 常量为共享常量
18. `dao/settings_dao.py`、`dao/tasks/task_dao.py` 加 WAL + busy_timeout
19. 补 `env.example` 的 `SCORE_TRANS_WORKDIR`
20. 更新根 `AGENTS.md` 过时描述
21. 拆分巨型 Vue 组件 / 提取 `_MeasureBuilder` 类
22. 引入 Vitest 组件测试 + Playwright E2E
23. 代码签名（发行版）
24. 缓解 `programmaticUpdate` nextTick 时序耦合

---

## 七、历史清理记录

### 2026-07-14 全面审计
- ✅ 验证 2026-07-03 报告中 ~40 项 P0/P1 问题已全部修复
- ✅ 确认 exec 层 HTTPException 从 7 处清零
- ✅ 确认 test_render.py 从 1681 行脆弱断言重写为 208 行 ET-based
- ✅ 确认 SvgPreview.vue v-html 已删除，改用 sanitizeSvg + importNode
- ✅ 确认 Electron 主进程安全（SSRF/路径遍历/孤儿进程）全部修复并有测试守护
- ⚠️ 发现 2 项新回归（CI 消失、requirements.txt 不同步）
- ⚠️ 发现 25 项新 P2 问题（含双附点 type 丢失、tie 锚点角色错误、wedge direction_kind 丢失等）

### 2026-07-03 删除优先清理记录
- ✅ 删除不可达的旧 `HistoryView.vue`、`api/recognize.ts` 和 `stores/task.ts`
- ✅ 删除后端 6 个、前端 4 个全仓库零引用函数，并移除无引用的 `useTaskStore` 兼容导出
- ✅ 合并 bbox 首值查找、渲染 token 斜线计数、OCR 首小节号选择和 SVG 公共样式
- ✅ 移除未使用的前端直接依赖 `date-fns`、本地 OMC 状态和 5 份 JVM 崩溃日志
- ✅ Ruff、后端全量测试、前端 lint/typecheck/工具测试和生产构建通过

### 2026-06-28 架构改进记录
- ✅ 后端持久化服务通过 `exec/composition.py` 进程级复用
- ✅ 前端核心状态更名为 Score Workspace Module
- ✅ Recognize / Convert / Export 的批量渲染请求构造集中到 `utils/batchRender.ts`
- ✅ 前端 DTO 改为从 FastAPI OpenAPI 自动生成，并增加 CI 漂移检查
- ✅ 所有异步 API adapter 统一返回 `{ data, error }`
- ✅ `services/render` 包级公开接口收窄到渲染门面和核心 DTO
- ✅ 新增 Windows CI，覆盖后端测试、前端类型检查、契约检查和生产构建
