# 问题报告与改进建议

> 接 [architecture.md](./architecture.md)、[file-by-file.md](./file-by-file.md)。
>
> **当前权威复核：2026-07-18**。本轮以当前工作树（包括用户尚未提交的修改）为准，重新检查旧报告的 N1-N26、P3 清单、架构约束和新增改动。旧的 2026-07-14 结论不再作为当前状态依据。
>
> **本轮边界**：只读代码和运行检查；除本文件外未修改项目文件。

> **修复执行状态（2026-07-18）**：阶段 A/B 已完成并暂停。已修复 R1、R2、N3、N4、N5 和 R4 的 lint 错误；T1 已补异步协调器行为测试，但完整 Vue DOM 跨视图测试仍待后续。统一验收为后端 `426 passed, 1 skipped`、Ruff lint 通过、前端 typecheck/API 契约通过、工具测试 67 通过/1 跳过、lint 0 error/2 条既有 warning、Audiveris JDK 25 编译通过。阶段 C 尚未开始。

## 一、结论总览

| 结论 | 数量 | 编号 |
|---|---:|---|
| 确认仍存在 | 15 | N1、N9-N11、N13-N14、N16、N18-N23、N25-N26 |
| 部分修复但仍有残余 | 1 | N12 |
| 已修复 | 4 | N2-N5 |
| 原报告不成立 | 3 | N6、N7、N8 |
| 证据不足，降级为待验证风险 | 2 | N15、N17 |
| 原问题需重新定义 | 1 | N24（源码不存在 MuseScore 集成，而不只是缺测试） |
| 本轮新增确认问题仍开放 | 3 | R3、R5、R6；R1/R2 已修复，R4 lint 已修复、format 归 R3 |
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
| N1 | **仍存在，范围收窄** | `pyproject.toml:10-23` 已正确声明 `fonttools`、`pyyaml` 和 test extra；但 `requirements.txt:1-8` 仍缺前两项，并把 pytest 当运行依赖。仅通过该文件安装的环境仍会缺运行依赖。 | 删除备用清单，或从 `pyproject.toml` 自动生成。验收：新环境分别用项目推荐安装方式和保留的兼容安装方式启动 API、加载 YAML、完成字体路径测试。 |
| N2 | **已修复** | `.github/workflows/ci.yml:1-66` 已恢复 Windows CI，覆盖锁定安装、Ruff lint、pytest、前端 lint/typecheck、工具测试、OpenAPI 漂移和 build。 | 不再按“无 CI”修复。残余门禁问题改列 R3。 |
| N3 | **已修复** | `_fraction_to_type` 现返回 0–3 的附点数量，MusicXML 写出相同数量的 `<dot>`，双/三附点不再回退到错误 type。 | 新增公开转换测试覆盖 quarter/eighth 的双附点与 quarter 三附点；修复前失败、修复后通过。 |
| N4 | **已修复** | tie 锚点优先读取 `tie_start/tie_stop`，仅为旧数据回退 slur role；Audiveris provenance 生产端根据 `SlurInter.isTie()` 写入 `ts/te` 或 `ss/se`。 | 新增同一音符同时含 tie+slur 的测试，两类锚点 source ID 独立。历史 MXL 若只有 `ss/se` 无法恢复原本丢失的语义，只能保持兼容回退。 |
| N5 | **已修复并通过独立复核修正** | `TextBlock` 向后兼容增加 `direction_attributes`；wedge/pedal/octave-shift 保存属性并结构化写回。独立审查发现初版 `.find()` 会丢失同一个 `direction-type` 内的重复同类元素，现已改为逐项解析。 | 单个 `direction-type` 内 2 wedge + 2 pedal + 2 octave-shift 的测试修复前只得到 3 项，修复后 6 项及全部属性顺序通过往返。按“不改变简谱文本语法”的约束，纯简谱文本仍不会携带这些结构属性。 |
| N6 | **原报告不成立** | `services/ai/core/parsing.py:51` 的 `d+` 有意匹配简谱时值前缀 `d/dd/...`；`domain/jianpu_tokens.py:8-25` 定义该语法，`tests/test_jianpu.py:326-334` 已覆盖。改成 `\d+` 会引入回归。 | 关闭该问题，不修改正则。可补一条注释或命名测试防止再次误报。 |
| N7 | **当前不成立** | `api/app.py:121-126` 的 stage 固定为 audiveris，但当前所有 `ExternalToolError` 抛出点都位于 `services/recognize/external_tools.py` 的 Audiveris/Java 运行链路，没有实际非 Audiveris 错标路径。 | 不作为现存 bug 修复。若以后复用该异常，再让异常携带 stage，并在 API 层透传。 |
| N8 | **原报告不成立** | `api/history/routes.py:23-110` 使用同步 `def`，但 FastAPI 会在线程池执行同步 path operation；旧报告“直接阻塞事件循环”的因果错误。 | 不要机械改为 async。只有在测得线程池饱和或改为 async 后，才对具体阻塞 I/O 使用 `asyncio.to_thread()`。 |
| N9 | **仍存在** | `exec/files/actions.py:50-73`、`exec/recognize/actions.py:139-157`、`exec/pipeline/actions.py:409-413,503-507` 仍有宽泛异常后返回 None，PDF 主功能或 OMR/overlay 辅助产物失败时缺诊断。 | 主功能失败返回明确错误；允许降级的辅助产物至少记录异常和任务诊断字段。验收：注入 PDF、OMR、overlay 失败，确认用户结果与日志能区分。 |
| N25 | **仍存在** | `services/correct/musicxml_patch.py:28-43,65-97` 对每个删除 ID 重复全树搜索，再逐候选寻找祖先/父节点，最坏接近 O(k*n²)。 | 单次解析后建立 parent map 和 locator 索引。验收：结果等价测试 + 大型合成 MusicXML 基准，修复后随节点数近线性增长。 |
| N26 | **仍存在** | `services/ai/providers/_http.py:46-49,83-84`、`services/ocr/providers/_http.py:38` 每次使用模块级同步请求 API，无法复用连接池/TLS。 | 由 composition/service 生命周期持有同步 `httpx.Client`，明确关闭时机。验收：多次请求复用连接，异常与流式关闭路径不泄漏；不要无理由改成 AsyncClient。 |

### 前端

| 编号 | 当前结论 | 当前证据与影响 | 修复与验收要求 |
|---|---|---|---|
| N10 | **仍存在** | `stores/assistant.ts:19,218-231` 定义了 `abortStream()`，但 store 返回对象未暴露；UI 无法主动停止聊天流。 | 暴露动作并在组件卸载、切换会话和停止按钮中调用。验收：流、reader 和 loading 状态均结束。 |
| N11 | **仍存在** | `api/tasks.ts:21-34` 的 `tasksApi.stream()` 不接收外部 `AbortSignal`，只创建内部 controller；组件无法取消 SSE、轮询定时器和在途轮询。 | 接受外部 signal，并把取消传播到 fetch、reader、poller。验收：卸载后无网络请求、计时器和状态提交。 |
| N12 | **部分修复** | 旧报告 6 处剩 4 处：`ConversionSettingsPanel.vue:275-276`、`StorageSettingsPanel.vue:157-158`、`stores/settings.ts:338`、`ConvertView.vue:1517`。preload 已声明类型化 `window.api`。 | 移除剩余 `globalThis as any`，使用 `window.api` 和显式 capability check。验收：typecheck 通过，并打开 `no-explicit-any` 后不新增豁免。 |
| N13 | **仍存在** | `RecognizeView.vue:1101-1108` 的主任务路径直接返回 `completed.result as T`；结构守卫只用于恢复路径 `:1165-1171`。 | 按任务种类传入 decoder/type guard，校验后再返回。验收：错误结构进入可见错误状态，不进入渲染流程。 |
| N14 | **仍存在** | `JianpuPlayer.vue:180-182` 只取简谱前 50 个字符构造 loadId；共享前缀、后半段不同的谱面会错误复用旧 MIDI。 | 使用完整内容的稳定哈希，或以版本号/内容引用作为缓存键。验收：只修改第 51 字符后仍重新生成 MIDI。 |
| N15 | **降级为待验证** | `usePlayer.ts:100` 只把第一个 tempo 读入 `originalBpm`，但音符调度使用 MIDI 库给出的秒时间 `:107-125`；现有证据不足以证明原始多 tempo 播放失效。 | 先增加含两个 tempo event 的行为测试，分别验证原速播放、用户 BPM 覆盖和进度。测试失败后再决定时间缩放模型。 |
| N16 | **仍存在，描述已更新** | 当前结构是 `stores/workspace.ts:169-174` 的 Record，不是 Map。`removePage():674-709` 未删除最后一页所属批次的 OCR、dirty、Jianpu、pending 等记录；删除中间页后数字页索引也可能错位。 | 提供 batch 级统一销毁/重排函数。验收：删除首/中/末页和最后一页后，所有 per-batch/per-page Record 同步且无旧 OCR。 |
| N17 | **待复现风险** | `utils/liveRecognitionState.ts:12-13` 仍是模块级 Map；多个终态会清理，但 `RecognizeView.vue:481` 卸载未统一取消任务或清理。与 N11 叠加时，永久挂起任务可能长期保留。 | 先做卸载、失败、取消、恢复四类生命周期测试；再把 ownership 收到 store/task lifecycle，避免组件自行散落清理。 |
| N18 | **仍存在** | `FileUploader.vue:53,74-88` 未读取 hook 的 error；`useFileUpload.ts:24-27` 失败时返回 null，组件静默继续队列。 | 对每文件记录成功/失败并显示汇总；不要因一项失败丢失后续成功项。验收：网络错误、格式错误、部分成功三种场景。 |
| N19 | **仍存在** | `ConvertView.vue:587-608` 依靠共享布尔值和 `nextTick` 区分程序更新与用户输入；同一刷新周期的真实编辑可能被误判，导致 dirty/锚点/重渲染遗漏。 | 使用单调 generation/token 或显式事务来源。验收：恢复历史、程序替换和紧邻用户输入交错时状态准确。 |

### 构建、供应链与文档

| 编号 | 当前结论 | 当前证据与影响 | 修复与验收要求 |
|---|---|---|---|
| N20 | **仍存在** | `build-app.py:174-257` 复制本机 Gradle 缓存、伪造状态文件并关闭 distribution URL/SHA 校验。风险是构建机缓存缺少显式完整性核验。 | 固定 Gradle 版本与 SHA-256；若必须离线缓存，先校验归档摘要再解包。验收：篡改缓存时构建必须失败。 |
| N21 | **仍存在** | `desktop/electron-builder.yml:14-19` 的 Windows 构建没有证书或签名配置；`pyinstaller.spec:107` 也未配置签名身份。 | 设计 Windows Authenticode 密钥托管与 CI 签名步骤。验收：安装器和主要 exe 均可验证签名，时间戳有效。 |
| N22 | **仍存在** | `backend/score_trans/config/ai_prompt.yaml:206-213` 的失败/超拍示例仍以绿色成功符号开头、以失败符号结尾，语义冲突。 | 用中性标题明确“错误示例”，并加 prompt 快照/解析测试，避免只改装饰符号。 |
| N23 | **仍存在，旧建议已过期** | `desktop/package.json:32` 仍使用 Electron `^33.3.1`，官方已将 33 标为 EOL。旧建议“升级到 36+”在当前日期也过时。 | 升到当前官方支持的主线，而不是固定 36；逐项验证 preload、IPC、child process、builder、NSIS、SVG 与文件导出。 |
| N24 | **重新定义后仍存在** | README `:20,28,35,42,70`、`docs/development.md:44`、`docs/environment.md:15,22` 宣称 MuseScore 导出和环境变量；当前 backend、desktop/src、tests 中没有 MuseScore 实现。原问题不是“缺测试”，而是文档声称不存在的功能。 | 二选一：删除全部 MuseScore 声明，或先实现真实集成再写测试。当前产品行为下优先修正文档，避免用户配置无效变量。 |

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

### R3. CI 质量门禁仍不完整且 Ruff 未锁版本（P2）

- **位置**：`.github/workflows/ci.yml:28-29`
- **证据**：CI 已恢复，但只运行 `uvx ruff check`，不运行 `ruff format --check`；Ruff 未在锁文件/命令中固定版本。当前本地 format check 已发现 17 个漂移文件。
- **修复方案**：把 Ruff 固定为项目开发依赖或显式版本，CI 增加 format check；之后再分阶段增加覆盖率阈值、依赖审计和必要的 Python 版本矩阵。
- **验收**：同一 commit 在本地与 CI 使用同一 Ruff 版本，lint/format 结果一致。

### R4. 当前 Python 静态质量门禁不通过（P2，已修复 lint 部分）

- **位置**：`backend/score_trans/exec/settings/actions.py:10`，另有 17 个 Ruff format 漂移文件。
- **问题**：未使用的 `TargetKey` 导入会使现有 CI 的 `ruff check` 失败；格式漂移暂时不会被 CI 发现。
- **修复方案**：删除确认无用的导入，统一运行项目固定版本的 formatter；不要顺带做功能重构。
- **验收**：`ruff check backend tests scripts` 与 `ruff format --check backend tests scripts` 均通过，后端全量测试保持通过。
- **2026-07-18 进度**：已删除 `exec/settings/actions.py` 未使用的 `TargetKey` 导入，`uvx ruff check backend tests scripts` 通过。17 个文件的格式漂移未在本批次处理，R3 的固定 Ruff 与 format 门禁仍待后续阶段。

### R5. 根 AGENTS 与当前代码/测试约束冲突（P2，协作风险）

- **位置**：`AGENTS.md:55-67,87`、`tests/test_architecture.py:15-30,140-172`
- **问题**：AGENTS 声称 exec 尚有 20 个 FastAPI 导入违规，但当前为 0；其层级导入规则也与架构测试允许的 config/utils 边界不同；`test_render.py` 规模描述也已过时。
- **影响**：后续人工或自动代理会按错误约束修改代码、重复清理已解决问题，或误判合法/非法依赖。
- **修复方案**：以架构测试为可执行事实源，统一文档；对 5 个已知 `exec→domain` 白名单逐步清零，不再维护互相矛盾的文字规则。

### R6. 环境变量示例不完整（P3）

- **位置**：`backend/score_trans/config/settings.py` 与 `backend/score_trans/config/env.example:1-76`
- **问题**：示例至少缺 `SCORE_TRANS_WORKDIR`、`SCORE_TRANS_JAVA_HOME`、`SCORE_TRANS_OUTPUT_DIR`、`SCORE_TRANS_AI_SYSTEM_MSG`。
- **修复方案**：从设置读取点生成/校验示例清单，标明必填、可选、默认值和 Windows 路径格式。验收时比较代码读取集合与示例集合。

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

- **2026-07-18**：重新验证当前工作树；撤销 N6/N7/N8 的错误结论，确认 N2 已修复，重定义 N24，新增 R1-R6 和 T1-T2。
- **2026-07-14**：旧全面审计建立 N1-N26；其行号、数量和若干因果判断已被本轮替代。
- **2026-07-03**：完成早期 P0/P1 安全、架构和前端生命周期修复；详细历史仍见 [AUDIT_REPORT.md](AUDIT_REPORT.md)。
