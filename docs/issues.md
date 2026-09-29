# 问题报告与改进建议

> 接 [architecture.md](./architecture.md)、[file-by-file.md](./file-by-file.md)。
>
> **历史复核记录：2026-07-18**。本文保留 N1-N26 的历史验证过程；当前代码删减、分层和过时文档以本文（§三–§六）与当前测试结果为准。
>
> **本轮边界**：以当前工作树（包括用户尚未提交的修改）为基线，按阶段实施已验证的修复；不会撤销或覆盖用户既有改动。

> **修复执行状态（2026-07-19）**：阶段 A/B 与 C 已完成；本轮阶段 D 已修复 N1、N9、N20、N22、N23、N24、R5、R6，并固定 CI Ruff 版本。后端完整 pytest、固定版本 Ruff lint、前端 lint/typecheck/工具测试均通过；全仓 Ruff format、Windows 签名和 Vue DOM 跨视图测试仍待专门批次。

> **修复执行状态（历史记录）**：2026-08-20 的测试和清理数字只代表当时基线；执行新的删减批次时必须重新运行当前 `.venv` 测试、前端 typecheck 和生产构建。

## 〇、当前待办清单（2026-09-29）

### 进行中：歌词语法重构（未提交）

当前工作树有一大批未提交改动（`parse/write/jianpu_text.py`、`rekey.py`、`renderer.py`、前端 `jianpuSyntax.ts`/`jianpuPageSections.ts`/`jianpuPlayback.ts`/`JianpuEditor.vue`/`SyntaxView.vue`、i18n、相关测试与 `docs/jianpu-syntax.md`），是新版 `/L:` 歌词语法特性的主体。

- [ ] 提交歌词重构主体改动（含 i18n 与测试），并决定是否将 [lyric-refactor-fix-plan.md](lyric-refactor-fix-plan.md) 纳入版本管理。

### 已完成：歌词重构修复批次 B1–C1（2026-09-29）

按 [lyric-refactor-fix-plan.md](lyric-refactor-fix-plan.md) 四批次全部实施完成：

- [x] **B1**（Bug）英文歌词以 `s`/`h`/`q`/`w` 开头被截断 — `d` 特判已扩展到全部 5 个时值前缀字母，新增回归测试 `test_lyric_words_starting_with_duration_letters_are_preserved`
- [x] **B2**（Bug）`lyric_line_count` 对带换行符的行多算 1 — 已改为 `sum(1 for line in lines if "/L:" in line)`
- [x] **B3**（Bug）测试名与内容不符 — 已改名 `test_lyric_block_without_terminator_is_rejected`
- [x] **D1**（设计）`rfind("/")` 误匹配后续行 — 后端 `_extract_lyric_blocks` 优先同行查找；前端 `jianpuSyntax.ts` 新增公共 `findLyricBlockRange`
- [x] **D2**（设计）前端歌词块定位逻辑重复 — `jianpuPageSections.ts`（2 处）、`jianpuPlayback.ts`（1 处）已复用 `lyricBlockLineIndexes`/`maskJianpuLyricBlocks`；5 个内联编译的 Node 测试脚本同步补充 `jianpuSyntax` 依赖注入
- [x] **D3**（设计）`JianpuEditor.vue` 每行重算 — 已提取到 `map` 之前只算一次
- [x] **D4**（设计）`LyricLineSummary` 死字段 — `schemas.py` 移除三字段，同步删除 `JianpuEditor.vue` 死代码引用与中英文 i18n 键（`lyricNotes`/`lyricMissing`/`lyricExtra`），`openapi.ts` 已重新生成且 `check:api-types` 通过
- [x] **D5**（设计）`validate_jianpu_lyrics` 双重解析 — 已改用 `_parse_score_tokens` 复用首次解析结果（保留 BOM strip）
- [x] **D6**（设计）`_split_lyric_block` 匹配注释 — 已增加行首检查
- [x] **C1**（清理）`.gitignore` 已添加 `.pytest-*/`，`.pytest-lyrics-investigation-20260929/` 已删除

**验证结果**：后端全量 pytest `1247 passed, 1 skipped, 1 xfailed`；Ruff check / format --check 全绿；前端 `vue-tsc` 通过、ESLint 0 error（残余 42 条可修复 warning 均为用户既有改动文件 `App.vue`/`LiveJianpuPreview.vue`/`ConvertView.vue`，非本批次引入）；`pnpm test:utils` 288 项全过；`pnpm check:api-types` 通过。

注：本机 `C:\Users\15732\AppData\Local\Temp\pytest-of-Lenovo` 目录无访问权限，pytest 需加 `--basetemp` 指向可写目录运行（环境问题，与代码无关）。

### 需求与问题待办（2026-09-29 用户提出）

- [x] **W1 语法报错缺小节号（多声部）**（已修复 2026-09-29）：「各声部小节数量不一致」现携带第一个缺失小节的按页连续显示号（repeat 加权 span + 页 base），文案追加 `（X从第 N 小节起缺失）` 提示；数量不同但占位相同（反复结构）时保持为空避免误导。「歌词小节数不能超过谱面小节数」同步补齐显示号；顺带修复第二轮按声部分段解析的 token 错误在多页文档透传段内局部号的错号 bug（`_relabel_part_error_measure` 统一换算）。标记格式/歌词块形状/instrument/拍号/旧 `L:` 等结构级错误维持 `measure=None`（朴素小节线计数与 tokenizer T8 反复语义存在线性发散，填入即为错号）。回归测试见 `test_syntax_validation.py` 尾部 W1 系列
- [x] **W2 歌词支持多行编辑**（已修复 2026-09-29）：歌词块 `/L: .../` 解除"必须写在同一行"限制，块内换行等同空白，小节仍由 `|` 划分（与谱面正文规则一致），`&` 分流与"歌词小节可少不可多"等对齐规则不变。结束符规则简化为"`/L:` 之后第一个独立 `/`"（`(?<!/)/(?!/)`，`//` 注释标记自动跳过），后端 `_extract_lyric_blocks` 与前端 `findLyricBlockRange` 同步采用；块内内容错误（`&` 流数量不一致、时值前缀缺词）从锚定 `/L:` 行改进为锚定出错小节/词的实际行列。行为变更：`/L: 一 / 二/` 与 `/L: 一/二/` 的报错由"不能包含保留符号"改为"结束符 / 后不能有内容"（更准确）。写出端仍输出单行块；多声部全文扫描"只允许一个 /L: 块"为既有行为未在本批次处理。回归测试见 `test_syntax_validation.py` W2 系列与前端 `test-jianpu-page-sections.mjs`/`test-jianpu-transpose.mjs` 多行歌词块用例
- [ ] **W3 复调识别转换问题**：复调（多声部叠置）的 OMR 识别与转换结果存在较大问题（具体表现待补充用例；排查方向：`SCORE_TRANS_POLYPHONY_MODE`、`&` 多流对齐、Audiveris voice 解析）
- [ ] **W4 歌词对应的小节显示问题**：歌词与谱面小节的对齐/显示不正确（具体场景待补充；可能与时值累计、截断歌词 `allow_truncated` 或渲染层歌词布局相关）
- [ ] **W5 简谱谱面自定义渲染样式**：支持用户自定义谱面渲染样式（字体、字号、间距、主题等；当前渲染选项集中在 `services/render/options.py`，前端无样式设置入口）
- [ ] **W6 删除标记界面显示音符置信度**：在纠错/删除标记功能界面中展示 OMR 识别到的音符置信度（需 Audiveris provenance 链路携带 confidence 并在前端纠错界面呈现）
- [ ] **W7 部分已识别音符不可点击**：某些音符已被识别并渲染，但无法点击定位（点击映射/source ID 缺失或坐标错位；关联 T1 的点击链路测试缺口）
- [ ] **W8 民乐标记的正确渲染问题**：民乐（如二胡等）演奏标记的渲染不正确（具体标记类型与错误表现待补充；排查方向：MusicXML articulation/technical 元素解析、`services/render/` 的 ornament/technique glyph 布局与字体支持）
- [ ] **W9 PDF 转图片非原图无损转换**：PDF 转换到图片的过程似乎不是原图无损转换（排查方向：PDF 渲染 DPI/分辨率参数、是否引入压缩或缩放、渲染库的输出质量设置）

> 除 W1 已修复外其余 8 项均未开始排查；W3/W4/W7/W8/W9 需要先补充具体复现用例再定修复方案。

### 长期开放项（来自本文 N/T 系列）

- [ ] **N21** Windows 安装包/exe 无签名 — 需设计 Authenticode 密钥托管与 CI 签名步骤
- [ ] **N25** `musicxml_patch.py` 删除路径最坏 O(k·n²) — 单次解析建立 parent map + locator 索引
- [ ] **N26** AI/OCR provider 每次新建同步请求、无连接池 — 由 composition 持有 `httpx.Client`
- [ ] **T1**（部分完成）缺 Vue DOM 挂载测试设施与 Playwright 点击链路（R2 异步行为已覆盖）
- [ ] **T2** correction 标题/文本附件缺完整集成回归
- [ ] **P3 技术债**：死代码候选清理、A4 尺寸常量收敛、大视图拆分（RecognizeView/ConvertView/SyntaxView）、SQLite WAL/busy_timeout、`no-explicit-any` 收紧、README 截图等（详见 §六）

## 一、结论总览

| 结论 | 数量 | 编号 |
|---|---:|---|
| 确认仍存在 | 15 | N1、N9-N11、N13-N14、N16、N18-N23、N25-N26 |
| 部分修复但仍有残余 | 1 | N12 |
| 已修复 | 5 | N2-N5、N15 |
| 原报告不成立 | 3 | N6、N7、N8 |
| 证据不足，降级为待验证风险 | 1 | N17 |
| 原问题需重新定义 | 1 | N24（源码不存在 MuseScore 集成，而不只是缺测试） |
| 本轮新增确认问题仍开放 | 0 | 无；R1-R6 均已修复（R3 于 2026-08-20 随 format 门禁落地关闭） |
| 本轮新增测试缺口 | 2 | T1 部分完成、T2 未开始 |

当前没有发现新的 P0。阶段 A/B 已消除来源 ID 错配、SVG 加载竞态和 N3-N5 乐理往返问题；下一优先级是 N14/N16 的播放与批次状态正确性、N9 的失败诊断、N10/N11/N17 的统一取消生命周期，其后才是 N20/N23 的供应链与运行时安全风险。

## 二、验证基线

| 检查 | 结果 | 说明 |
|---|---|---|
| 后端全量测试 | 通过 | 阶段 A/B 后为 `426 passed, 1 skipped`；另有 1 条 Starlette TestClient 弃用警告 |
| 前端类型检查 | 通过 | `pnpm typecheck` 退出码 0 |
| 前端工具测试 | 通过 | 阶段 A/B 后为 68 项：67 通过、1 项因 Windows 符号链接权限跳过 |
| 前端 ESLint | 通过但有警告 | 0 error；`AiAssistant.vue` 的 `v-html` XSS 警告、`ConversionSettingsPanel.vue` 未使用类型警告 |
| Python Ruff lint | 通过 | 已删除 `exec/settings/actions.py:10` 未使用的 `TargetKey` 导入；`uvx ruff check backend tests scripts` 通过 |
| Python Ruff format | 未通过 | 17 个文件需要格式化；CI 当前没有运行 `ruff format --check` |
| 依赖锁校验 | 通过 | `uv lock --check` 通过 |
| 前端生产依赖审计 | 通过 | `pnpm audit --prod` 未发现已知漏洞 |
| 工作树空白检查 | 不适用 | 开始前已有 12 个用户修改文件；本轮没有撤销或覆盖这些修改 |

这些通过结果只能证明现有测试覆盖到的行为没有回归，不能推翻下面由代码路径直接确认的问题。

## 三、旧问题逐项复核

### 后端与乐理

| 编号 | 当前结论 | 当前证据与影响 | 修复与验收要求 |
|---|---|---|---|
| N1 | **已修复** | 兼容安装清单已与 `pyproject.toml` 的运行依赖对齐：补充 `fonttools`、`pyyaml`，并从运行清单移除仅测试需要的 pytest。 | 推荐路径仍是 `uv sync`；保留的 `requirements.txt` 不再导致 YAML 或字体运行依赖缺失。 |
| N2 | **已修复** | `.github/workflows/ci.yml:1-66` 已恢复 Windows CI，覆盖锁定安装、Ruff lint、pytest、前端 lint/typecheck、工具测试、OpenAPI 漂移和 build。 | 不再按“无 CI”修复。残余门禁问题改列 R3。 |
| N3 | **已修复** | `_fraction_to_type` 现返回 0–3 的附点数量，MusicXML 写出相同数量的 `<dot>`，双/三附点不再回退到错误 type。 | 新增公开转换测试覆盖 quarter/eighth 的双附点与 quarter 三附点；修复前失败、修复后通过。 |
| N4 | **已修复** | tie 锚点优先读取 `tie_start/tie_stop`，仅为旧数据回退 slur role；Audiveris provenance 生产端根据 `SlurInter.isTie()` 写入 `ts/te` 或 `ss/se`。 | 新增同一音符同时含 tie+slur 的测试，两类锚点 source ID 独立。历史 MXL 若只有 `ss/se` 无法恢复原本丢失的语义，只能保持兼容回退。 |
| N5 | **已修复并通过独立复核修正** | `TextBlock` 向后兼容增加 `direction_attributes`；wedge/pedal/octave-shift 保存属性并结构化写回。独立审查发现初版 `.find()` 会丢失同一个 `direction-type` 内的重复同类元素，现已改为逐项解析。 | 单个 `direction-type` 内 2 wedge + 2 pedal + 2 octave-shift 的测试修复前只得到 3 项，修复后 6 项及全部属性顺序通过往返。按“不改变简谱文本语法”的约束，纯简谱文本仍不会携带这些结构属性。 |
| N6 | **原报告不成立** | `services/ai/core/parsing.py:51` 的 `d+` 有意匹配简谱时值前缀 `d/dd/...`；`domain/jianpu_tokens.py:8-25` 定义该语法，`tests/test_jianpu.py:326-334` 已覆盖。改成 `\d+` 会引入回归。 | 关闭该问题，不修改正则。可补一条注释或命名测试防止再次误报。 |
| N7 | **当前不成立** | `api/app.py:121-126` 的 stage 固定为 audiveris，但当前所有 `ExternalToolError` 抛出点都位于 `services/recognize/external_tools.py` 的 Audiveris/Java 运行链路，没有实际非 Audiveris 错标路径。 | 不作为现存 bug 修复。若以后复用该异常，再让异常携带 stage，并在 API 层透传。 |
| N8 | **原报告不成立** | `api/history/routes.py:23-110` 使用同步 `def`，但 FastAPI 会在线程池执行同步 path operation；旧报告“直接阻塞事件循环”的因果错误。 | 不要机械改为 async。只有在测得线程池饱和或改为 async 后，才对具体阻塞 I/O 使用 `asyncio.to_thread()`。 |
| N9 | **已修复** | PDF 转页的依赖缺失与转换失败分别返回明确的 `RuntimeError` / 用户可见 `ValueError`；OMR/overlay 是允许降级的辅助产物，失败时保留 `None`，但以 `logger.exception` 记录完整诊断。 | 新增注入 PDF、OMR、overlay 失败测试，确认 PDF 不再泄漏底层错误，辅助路径同时保留降级结果和日志。 |
| N25 | **仍存在** | `services/correct/musicxml_patch.py:28-43,65-97` 对每个删除 ID 重复全树搜索，再逐候选寻找祖先/父节点，最坏接近 O(k*n²)。 | 单次解析后建立 parent map 和 locator 索引。验收：结果等价测试 + 大型合成 MusicXML 基准，修复后随节点数近线性增长。 |
| N26 | **仍存在** | `services/ai/providers/_http.py:46-49,83-84`、`services/ocr/providers/_http.py:38` 每次使用模块级同步请求 API，无法复用连接池/TLS。 | 由 composition/service 生命周期持有同步 `httpx.Client`，明确关闭时机。验收：多次请求复用连接，异常与流式关闭路径不泄漏；不要无理由改成 AsyncClient。 |

### 前端

| 编号 | 当前结论 | 当前证据与影响 | 修复与验收要求 |
|---|---|---|---|
| N10 | **已修复** | assistant store 已公开 `abortStream()`；发送中显示停止图标，组件卸载同样调用该动作。 | 新行为测试验证 store 暴露、停止按钮和卸载均连到同一取消动作。 |
| N11 | **已修复** | `tasksApi.stream(taskId, onEvent?, signal?)` 接受外部 AbortSignal，取消会终止 SSE reader、在途轮询和 interval，返回已取消的 ApiResult，且不会回退轮询。 | 新测试注入挂起 reader 与 polling fetch，验证取消后 reader cancel 一次、轮询不新增、结果为取消错误。 |
| N12 | **已修复** | 设置面板、settings store 和 ConvertView 均改用类型化 `window.api`，保留 desktop capability 检查但移除 `globalThis/window as any` API 逃逸。 | 新回归检查四个原问题文件不再出现这两种 API cast；typecheck 和目标测试通过。 |
| N13 | **已修复** | `waitForTaskResult()` 现只返回 `unknown`；OMR 与 AI 主提交路径在读取字段前分别调用既有 `isPipelineResponse` / `isAiTranscribeResponse` 守卫，错误结构会进入现有失败处理。 | 新回归断言禁止恢复泛型强转，验证两条主路径均先 guard；专项测试和 typecheck 通过。 |
| N14 | **已修复** | 播放加载键已提取为 `playerLoadId`，使用 MIDI file ID、MusicXML file ID 与完整 Jianpu 文本的稳定 JSON 元组，不再截断 50 字符。 | 新增回归测试：两份前 50 字符相同、后缀不同的简谱生成不同键；同一输入保持相同键。目标脚本 8 项通过，typecheck 通过。 |
| N15 | **已修复（2026-09-03）** | MIDI 导出现在写出完整 tempo map，`@tonejs/midi` 将各段速度换算为音符秒时间；播放器只施加独立的全局倍率，不再用单一 BPM 覆盖曲内速度。 | 回归测试覆盖 120→80 tempo event 的 BPM 与绝对 tick、五档倍率时间换算和播放器固定倍率控件。 |
| N16 | **已修复** | `removePage()` 现统一重排 SVG/OCR/dirty 的数字页索引，删除最后一页时清除该批次所有派生 Record，并在当前批次删空时切换或清空选择；同时修正 final-page 路径缺失 `musicxmlText` ref。 | 新增 3 项 store 行为测试覆盖中间页重排、末页无陈旧 key、最后一页完整清理；脚本已加入 `pnpm test:utils`。 |
| N17 | **已修复** | RecognizeView 维护本组件拥有的等待 controller 与 live page ID；卸载时取消本地等待并清理 Map，不把仍在后端执行的任务持久化为失败，因此后续可恢复。 | 新测试覆盖 owned wait、卸载 cleanup 和 `liveRecognitionTaskPatch` 释放。真实 Vue DOM 卸载仍待后续组件/E2E 测试基础设施。 |
| N18 | **已修复** | FileUploader 读取 hook 的 error；每个失败文件写入可见错误汇总和日志，队列继续处理后续文件；新的上传批次会清空旧汇总。 | 回归测试验证错误状态、可见汇总、日志和“不抛错中断队列”的契约；typecheck 与目标测试通过。 |
| N19 | **已修复** | ConvertView 用单调 generation 与一次性“期望外部文本” token 标识 store 恢复，不再依赖 `nextTick` 共享布尔值；非该 token 的文本变化仍按用户编辑更新 anchors、dirty 和渲染缓存。 | 新回归检查禁止恢复 `programmaticUpdate`，并验证 token 设置/消费路径；typecheck 与目标测试通过。 |

### 构建、供应链与文档

| 编号 | 当前结论 | 当前证据与影响 | 修复与验收要求 |
|---|---|---|---|
| N20 | **已修复** | `build-app.py` 保留 wrapper 的 Gradle 版本、`distributionSha256Sum` 与 URL 校验配置；复制本机缓存前对原始 ZIP 计算 SHA-256，缺少 ZIP 时不复用，摘要不匹配则中止构建。 | 新增 `tests/test_build_app.py` 覆盖可信归档复制和篡改归档拒绝；两项测试通过。 |
| N21 | **仍存在** | `desktop/electron-builder.yml:14-19` 的 Windows 构建没有证书或签名配置；`pyinstaller.spec:107` 也未配置签名身份。 | 设计 Windows Authenticode 密钥托管与 CI 签名步骤。验收：安装器和主要 exe 均可验证签名，时间戳有效。 |
| N22 | **已修复** | `ai_prompt.yaml` 中所有超拍失败示例现以失败标记开头，不再同时出现互相矛盾的成功/失败标记。 | 配置仍由既有 YAML 加载路径验证；后续 prompt 语义效果应在模型评估集而不是单元测试中衡量。 |
| N23 | **已修复（构建级验证）** | Electron 已从 `^33.3.1` 升级并锁定到 `43.1.1`，这是本轮官方当前稳定补丁线；锁文件同步更新。 | 已运行 typecheck、前端工具测试与 electron-vite production build。实际 Windows NSIS 安装、preload/IPC、后台进程、SVG 与导出的人机验收仍应在签名发布候选包上执行。 |
| N24 | **已修复** | README、开发说明和环境变量参考已删除 MuseScore CLI、PDF/PNG 导出和 `SCORE_TRANS_MUSESCORE` 的不存在声明，改为项目实际输出能力。 | 文档不再引导用户配置无效路径；未来若实现 MuseScore 集成，必须同时补齐配置、实现和测试。 |

## 四、本轮新增问题

### R1. 和弦变音记号来源 ID 可能错配（P1，已修复）

- **位置**：`services/render/engraving/renderer.py:799-804,837-856`
- **原因**：渲染器先按 `pitch.rank` 重排和弦音，再用排序后的 `pitch_index` 索引 `event.source_roles['accidental']`。来源列表不保证按相同顺序重排，而每个 `JianpuPitch` 已有精确的 `accidental_source_id`（`domain/parse/musicxml.py:518-523,535-539`）。
- **影响**：和弦中点击变音记号可能定位到另一个音的源元素，纠错也可能作用到错误目标。
- **修复方案**：优先使用当前 pitch 的 `accidental_source_id`，仅在缺失时回退 role 列表；不要用排序索引关联 provenance。
- **验收**：构造 MusicXML 源顺序与音高排序相反、包含两个不同变音记号的和弦，验证每个 glyph 的 source ID、点击定位和纠错目标。
- **2026-07-18 结果**：已通过公开 `render_score_svg()` 增加“源顺序低→高、渲染顺序高→低”的和弦回归测试；测试在修复前稳定显示 ♯/♭ 来源互换，修复后隔离测试通过，`tests/test_render.py` 26 项全部通过。实现优先使用 `pitch.accidental_source_id`，仅在旧数据缺失该字段时保留事件级兼容回退。旧数据只含事件级列表时仍无法无歧义恢复排序关系，保留为兼容风险。

### R2. SVG 快速切换时高亮等待旧 Promise（P2，已修复）

- **位置**：`desktop/src/renderer/src/components/PublicationPreview.vue:434-436`
- **原因**：`highlightSource()` 只等待调用瞬间捕获的 `svgLoadPromise`。等待期间若 `svgUrl` 再次变化，旧加载会因 generation 退出，但调用方不会继续等待新 promise。
- **影响**：快速切页/重渲染后点击来源，可能误报“当前渲染页中没有该元素”。
- **修复方案**：等待循环同时绑定 generation；旧 generation 完成后若 URL 已变化，改等当前 promise，直到成功、明确失败或取消。
- **验收**：用可控延迟连续切换 A→B→C，在 A/B 未完成时触发高亮，最终只能在 C 中查找且不出现旧页误报。
- **2026-07-18 结果**：新增 `LatestAsyncGate`，generation 更新时等待者立即转向最新任务；快速切换会 abort 旧 SVG 请求，卸载会终止 gate 并释放等待者。行为测试覆盖 A→B→C（A 永久挂起、C 已完成）、最新任务失败和卸载取消；修复前前两类等待无法正确结束，修复后 3 项通过。前端工具测试现为 68 项（67 通过、1 跳过），typecheck 通过，lint 0 error/2 条既有 warning。

### R3. CI 质量门禁仍不完整且 Ruff 未锁版本（P2，已修复）

- **位置**：`.github/workflows/ci.yml:28-29`
- **2026-08-20 结果**：全仓 `ruff format` 已执行（33 个文件重排），CI 在 lint 步骤后新增 `uvx ruff@0.15.22 format --check backend tests scripts` 门禁；本地与 CI 使用同一固定 Ruff 版本。后续覆盖率阈值、依赖审计、Python 版本矩阵仍可分期增加。

### R4. 当前 Python 静态质量门禁不通过（P2，已修复 lint 部分）

- **位置**：`backend/score_trans/exec/settings/actions.py:10`，另有 17 个 Ruff format 漂移文件。
- **问题**：未使用的 `TargetKey` 导入会使现有 CI 的 `ruff check` 失败；格式漂移暂时不会被 CI 发现。
- **修复方案**：删除确认无用的导入，统一运行项目固定版本的 formatter；不要顺带做功能重构。
- **验收**：`ruff check backend tests scripts` 与 `ruff format --check backend tests scripts` 均通过，后端全量测试保持通过。
- **2026-07-19 进度**：已固定 CI Ruff 版本并格式化本轮自有的构建脚本及测试；为保护用户既有修改，其余格式漂移和 `ruff format --check` CI 门禁留待专门的纯格式化提交。

### R5. 根 AGENTS 与当前代码/测试约束冲突（P2，协作风险）

- **位置**：`AGENTS.md:55-67,87`、`tests/test_architecture.py:15-30,140-172`
- **已修复**：已移除不存在的 HTTPException 违规数量，并把 import 权限改为与架构测试一致的 `config`/`utils` 边界；五个历史 `exec→domain` 白名单被明确标为不可仿效。

### R6. 环境变量示例不完整（P3，已修复）

- **位置**：`backend/score_trans/config/settings.py` 与 `backend/score_trans/config/env.example:1-76`
- **修复**：示例已增加 `SCORE_TRANS_WORKDIR`、`SCORE_TRANS_JAVA_HOME`、`SCORE_TRANS_OUTPUT_DIR`、`SCORE_TRANS_AI_SYSTEM_MSG`，均保持空值默认语义；新增 settings 测试防止再次遗漏。

### R7. 语法检查估算路径在反复结构下小节号偏差（P2，已修复）

- **位置**：`backend/score_trans/domain/parse/jianpu_text.py` 的 `_estimate_measure_spans`（随 F3「事后重打号」引入）
- **原因**：估算路径（`parse_jianpu_parts` 失败时的降级）用段内 token 累计号的极差估算小节数，但 `_read_new_syntax` 的累计号会被 `*N` 干扰：backward `:| *2` 推进 +1（极差高估），forward `*3` 不推进（极差低估）。
- **影响**：仅限"语法错误 + 反复结构"同时出现的文档；错误之后的页的小节号会偏大/偏小。错误的行号、列号、高亮区间仍正确，仅小节号偏差。
- **实测**：第 1 页 `1 2 3 4 :| *2 |` + 第 2 页 `2 3 4 8 |`，`8` 准确应为第 3 小节，估算报第 4 小节。
- **2026-09-04 修复（v2 T8）**：双管齐下——
  1. `_read_new_syntax` 补齐 `flush_measure` 的推进规则（`|:`/`:` 不产生空小节、`:` 后空小节吞并、backward `*N` 后空小节吞并、forward `*N` 在 bar 时占号），累计号与 display_number 语义对齐；
  2. `_estimate_measure_spans` 改为**逐段单独 `parse_jianpu_score`**，好段拿准确的 `sum(repeat_count)`，只有坏段回退极差（而极差在 1 落地后也已对齐 display 语义）。
  实测 T2 复现用例现在报第 3 小节（准确）。新增 3 条 T8 回归测试。
- **已知残余边界**：段末悬空配置行（如 `1 2 3 4 |\n2/4` 后无音符）会让该段极差高估 1，但仅在"该段所在整篇文档的其它段有语法错误"时才走估算路径，且只影响该页之后的 base；场景罕见，暂不处理。
- **2026-09-04**：v1 随 F1+F2+F3 交付（详见本文 R7「事后重打号」架构说明）。

## 五、新增测试缺口

### T1. 新的 SVG 来源高亮修复缺完整组件集成测试（部分完成）

阶段 A/B 开始前，`desktop/scripts/test-svg-sanitizer.mjs:101-105` 主要以源码字符串/正则断言确认实现形状，没有挂载 `PublicationPreview`，也没有覆盖 URL 快速切换、坐标变换、语义目标优先级或“第四组音符”点击链路；当时的工具测试通过不足以证明 R2 或真实点击问题已解决。

2026-07-18 已新增组件实际使用的纯异步协调器测试，覆盖快速切换、失败和卸载取消，R2 的 promise/generation 行为已有自动化保护；项目仍缺 Vue DOM 挂载设施，`fetchFileBlob → sanitizeSvg → replaceChildren → highlightSource` 以及真实“第四组音符”跨视图点击尚未自动化，T1 因此不能关闭。

同日使用 `examples/二胡/月亮之上-Fl. 1 2.omr` 和 JDK 25 重新导出并走当前解析、简谱文档和 SVG 渲染链路：第一页第 1 小节解析为 24 个事件、4 个独立六连音组，每组均为 6 个事件且 `tuplet_count=6`；第四组 6 个 note source ID 全部存在于简谱 anchors 与 SVG。导出 MXL 仅用于临时验收，验证后已删除。真实后端链路已通过，但 UI 自动点击仍需未来的 Vue/Playwright 集成测试。

建议增加 Vitest + Vue Test Utils 组件测试，并至少保留一条 Playwright 流程：加载真实批次 → 切换页 → 点击左侧第四组音符 → 右侧只高亮对应 token。测试需要同时断言 source ID、page ID、part ID 和文本范围。

### T2. correction 标题/文本附件缺完整集成回归

当前新增测试覆盖了 `_document_title` 等静态局部行为，但没有覆盖 correction → MusicXML/领域模型 → 附件布局 → SVG 重新渲染 → 点击定位的完整链路。当前未发现确定性功能 bug，但该链路仍可能在下一次改动中断裂。

## 六、仍存在的 P3 技术债

以下条目已重新抽查，仍存在，但优先级低于上述正确性问题：

- **死代码候选**：`domain/constants.py:42` 的 `SEMITONE_TO_STEP`；`exec/render/actions.py:651` 的 `_render_batch_a4_without_page_ocr`；`services/render/options.py:9,23` 的 A4 theme；`models/provenance/schemas.py` 的 `RenderAnchor`；OCR client 的 `build_request/send_request`。删除前仍需用动态入口/导出检查确认。
- **重复与复杂度**：A4 尺寸常量散落在 render/pipeline/text_placement；`domain/parse/jianpu_text.py:287,671` 重复 `_utf16_length`；RecognizeView 2624 行、ConvertView 2603 行、SyntaxView 1236 行。
- **测试脆弱**：Audiveris 精确参数顺序、真实二进制 OMR fixture、精确浮点值、composition 仅 1 项测试；前端仍无 Vitest/Playwright。
- **SQLite 配置不一致**：SettingsDao 缺 WAL/busy_timeout；TaskDao 已有 WAL，但仍缺 busy_timeout。旧报告称 TaskDao 也缺 WAL 已过时。
- **前端性能/生命周期**：AiAssistant 重复解析 markdown；JianpuEditor 全文重算；PublicationPreview 坐标启发式、统一超时报错、静默 getBBox、卸载未恢复 `body.userSelect`；`fileExists` fail-open；MIDI fetch 无取消。
- **类型约束**：`desktop/eslint.config.mjs:54` 仍关闭 `no-explicit-any`。
- **文档**：README 截图仍是 TODO；`pyinstaller_entry.py` 对非法 port 的 `int()` 没有友好诊断。
- **兼容接口**：`get-backend-url` 仍由 preload 暴露和调用，renderer 已不用；它是遗留 surface，不是“全仓零引用”。

## 七、修复顺序与停点

### 阶段 A：当前改动的正确性护栏

1. 修 R1 的 accidental source ID 绑定。
2. 为 R1、R2 增加行为测试，优先复现“第四组音符/快速切页后点击”链路。
3. 修 R2 的 generation/promise 竞态。
4. 运行 `tests/test_render.py`、后端全量测试、前端 typecheck/lint/test:utils 和新增组件测试。

**停点**：点击映射和 SVG 快速切换测试未稳定前，不继续扩大 correction/render 重构。

**2026-07-18 完成情况**：R1、R2、R4 lint 已修复；渲染专项 26 项通过，真实月亮之上第一页四组六连音和第四组 6 个来源 ID 已验证。T1 的真实 Vue DOM 点击自动化仍待后续测试基础设施。

### 阶段 B：乐理往返正确性

1. N3 双/三附点。
2. N4 tie/slur provenance 分离。
3. N5 三类 direction 的解析与写出成对实现。
4. 每项均先建立失败用例，再修改实现；验收必须是双向往返而非只看单侧 XML。

**2026-07-18 完成情况**：N3-N5 已完成。3 个新增用例修复前全部失败、修复后全部通过；独立审查又发现并修复 N5 同一 direction-type 重复元素丢失问题。相关转换/来源测试 146 项通过，最终后端全量 426 项通过/1 项跳过，Audiveris Java 编译通过。

### 阶段 C：前端任务与状态生命周期

1. N14 缓存键、N16 批次销毁/重排。
2. N10/N11 统一取消链路，借此验证 N17 是否仍能泄漏。
3. N13 响应解码、N18 上传错误、N19 generation token。
4. N12 类型收紧最后处理，避免掩盖行为修复的差异。

### 阶段 D：供应链与质量门禁

1. 先修 R4，让现有 lint 恢复绿色；再落地 R3 的固定 Ruff + format check。
2. N20 Gradle 摘要校验。
3. N23 升级到当前受支持 Electron 主线并做桌面回归。
4. N21 发行签名。

### 阶段 E：文档与低风险清理

1. N24、R5、R6 一次性对齐代码、可执行测试和用户文档。
2. 对 P3 死代码逐项证明无动态引用后删除；每个小批次单独测试，不做大爆炸式清理。
3. N25/N26 用基准或连接复用观测验证收益后实施。

## 八、已核对且暂未发现新回归的当前改动

- `svgSanitizer.ts` 新增的 `data-source-role*` 属性名受严格正则限制，值排除了控制字符；未发现可确认的新安全回归。
- `ConvertView.vue` 对异步 `highlightSource()` 的 await 接入本身一致；PublicationPreview 的 promise generation 竞态已在 R2 修复并增加独立行为测试。
- `openapi.ts` 当前变更主要增加可选 `text_attachments` 字段，未发现类型回归。
- correction 的标题/文本附件静态链路未发现确定性新 bug，但保留 T2 的集成测试缺口。

## 九、历史记录

- **2026-09-04**：修复多页文档语法检查的小节号/行号错误（F1 按页分组校验 + 降级 warning、F2 `@page` 切断声部正文、F3 按页连续编号的事后重打号）；新增 R7（估算路径反复结构偏差）。
- **2026-08-20**：修复 `ee3f38c` 重构残留（后端 14 测试、前端约 60 处死引用、12 个工具测试、openapi 契约漂移、生产构建失败）；修复 typecheck 门禁空转与 `window.api` 类型遮蔽；执行全仓 ruff format 并在 CI 增加 format 门禁（R3/R4 关闭）；提交方案 A 结构标记删除。
- **2026-07-18**：重新验证当前工作树；撤销 N6/N7/N8 的错误结论，确认 N2 已修复，重定义 N24，新增 R1-R6 和 T1-T2。
- **2026-07-14**：旧全面审计建立 N1-N26；其行号、数量和若干因果判断已被本轮替代。
- **2026-07-03**：完成早期 P0/P1 安全、架构和前端生命周期修复；详细历史仍见 [AUDIT_REPORT.md](AUDIT_REPORT.md)。
