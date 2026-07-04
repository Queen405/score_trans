# Score Trans 审计修复进度

> 审计来源：[AUDIT_REPORT.md](AUDIT_REPORT.md)  
> 详细执行方案：`.omc/plans/audit-remediation-2026-07-03.md`  
> 开始日期：2026-07-03  
> 状态：实施中

## 更新规则

每个独立修复工作包都必须按以下顺序更新本文档：

1. 开始前把条目标记为“进行中”，写明影响范围和预期测试。
2. 实现后记录实际修改、兼容性或迁移行为。
3. 验证后记录完整命令和结果。
4. 如发现新问题，立即写入“新发现问题”，不能藏在代码注释或会话中。
5. 只有目标测试和全量相关门禁通过后，条目才能标记为“已完成”。

## 当前基线

| 门禁 | 结果 |
|---|---|
| 后端全量测试 | 415 passed，1 skipped |
| 前端 ESLint | 0 error，1 个 `vue/no-v-html` warning |
| 前端 TypeScript | 通过 |
| 前端工具测试 | 62 passed，1 skipped |
| OpenAPI 类型漂移 | 通过 |

## 总体进度

审计报告约有 147 个有效问题。由于部分表格项需要在实现前拆分或合并，最终分母以逐项结案台账为准。

| 类别 | 状态 |
|---|---|
| 严重 Bug / 数据安全 | 第 1 章全部有效问题已完成（1.7 不成立）；另完成 5.6a |
| 音乐理论与 MusicXML | 第 2 章全部完成（2.1–2.13） |
| 架构违规 | 第 3 章全部完成（3.1–3.4） |
| 安全问题 | 第 4 章全部闭环（4.4 不成立）；4.6a MusicXML DOCTYPE 兼容回归已修复 |
| 功能缺陷 | 5.1–5.8 全部完成 |
| 前端问题 | 6.1 已完成；按用户要求停在 6.2 开始前 |
| 代码质量 | 待处理 |
| 测试覆盖 | 待处理 |
| 构建、依赖和文档 | 待处理 |

## 当前工作包

### 停点：6.2 TypeScript 类型安全

状态：未启动。6.1 已完成；遵照用户要求，本轮不修改 6.2 或后续代码。

恢复工作时的第一步：

1. 重新运行 `pnpm test:utils`、`pnpm typecheck`，确认停点基线没有漂移。
2. 搜索 renderer 中 `as any`、`window.api`、`completed.result as T` 和所有任务状态
   强制转换，建立 6.2 的精确现状清单。
3. 先写未知状态、畸形任务结果和 preload API 类型的失败测试，再开始实现。

## 后续修复报告

以下工作包均处于“未启动”状态，除非条目明确标注“已由前序工作包完成”或“部分
完成”。每个工作包仍须遵循红灯测试、最小修复、专项回归、相关组合回归、完整门禁、
立即更新本文档的顺序。

### 6.2 TypeScript 类型安全（下一工作包）

现存问题：

- `ConvertView.vue` 把后端字符串直接 `as` 为任务状态，没有运行时验证。
- renderer 仍有 `(window as any).api` / `(globalThis as any).api`，会绕过 5.8
  已建立的 preload 类型契约。
- `RecognizeView.vue` 的 `completed.result as T` 允许任意 SSE payload 冒充目标类型。

实施方案：

1. 在任务模型边界建立 `isTaskStatus` 和显式 decoder；未知状态不默认为成功，统一
   转为带原始值的可诊断错误。
2. 直接使用 `window.api` 的推导类型，删除 renderer 的 IPC `any` 绕过；测试环境
   使用类型化 adapter，不污染生产声明。
3. 将 `waitForTask<T>` 改为接收 endpoint-specific decoder。decoder 校验对象形状、
   必填字段和字段类型后才返回 `T`，失败时保留 task id 与 endpoint 上下文。

验收与防回归：

- 未知 task status、空 result、错误 result shape 均产生受控错误，不进入 completed
  分支。
- 全仓 renderer 不再出现用于 IPC 或 task payload 的 `as any` / `as T`。
- `pnpm test:utils`、`pnpm typecheck`、`pnpm lint`、`pnpm build`、
  `pnpm check:api-types` 全部通过。

主要风险：decoder 过严会拒绝旧任务记录；需使用当前 OpenAPI 类型和历史持久化样例
双向校验，并为可选字段保留兼容。

### 6.3 错误处理缺失

现状复核：

- `deleteSession` 已在 5.5 修复并有前端回归测试，不重复修改。
- Dashboard、QuickEntry、PDF 转换以及可选 overlay/识别降级仍需逐项复核。

实施方案：

1. Dashboard / QuickEntry 请求失败时保留现有数据，设置明确 error 或非阻塞
   Naive UI message，并在 `finally` 中复位 loading。
2. `_pdf_to_images` 对缺少 PyMuPDF、损坏 PDF 和页面转换失败抛领域明确异常；失败
   时清理本次产生的未注册文件，不以 `None` 混淆“无页面”和“失败”。
3. 对允许降级的 overlay/识别附加能力记录结构化 warning，并通过任务结果传给 UI；
   不允许降级的主路径继续失败。
4. 增加 AST 规则，禁止新增裸 `except Exception: return None`，但允许带日志、
   上下文和明确 fallback 契约的受控降级。

验收：前端错误可见且旧数据不闪空；PDF 三类失败均有稳定错误码/阶段；降级 warning
可从任务结果观察；运行 files/pipeline/recognize/API 组合测试和后端全量测试。

主要风险：把历史上的“可选失败”全部升级为致命错误会改变产品行为，因此必须先按
主功能/增强功能分类。

### 6.4 播放器正确性

现存问题：MIDI tempo map 只取首个速度、RAF 自动停止可能截短尾音、简谱缓存键只取
前 50 字符。6.1 只修复了音量持久化和生成失败反馈，没有提前处理这三项。

实施方案：

1. 以 MIDI 事件的绝对时间为基准保留多速度映射；用户 BPM 调整作为整体速度比例，
   同时缩放 note start/duration。
2. 调度确定的结束事件，在最后音符 duration 与 release 完成后复位；RAF 仅更新 UI，
   不承担唯一停止判定。
3. 缓存键改为完整输入摘要或单调 generation，并纳入转换选项，避免内容相同前缀但
   尾部不同仍复用旧 MIDI。

验收：双 tempo MIDI、相同 50 字符前缀的不同简谱、最后长音、seek、loop、播放中
调整 BPM 均有确定性测试；再运行完整前端门禁。

主要风险：Tone.js Transport 与 MIDI 秒时间混用会造成双重缩放；实现前先锁定唯一
时间基准。

### 6.5 SVG 预览稳定性

现存问题：坐标空间依赖 `<=1.5` 启发式、加载错误类型合并、未渲染节点的 `getBBox()`
失败被静默吞掉。

实施方案：

1. 在 source map/API 模型中显式携带 `coordinate_space: pixels | normalized`；
   旧数据只在解码边界执行一次兼容推断，并把结果持久化为显式值。
2. 区分 timeout/AbortError、HTTP、网络和 SVG 解析错误，UI 提供对应提示。
3. 仅对已连接且完成布局的 SVG 节点调用 `getBBox()`；失败时保留 class 高亮并在
   next frame 有界重试一次，仍失败则记录可诊断 warning。

验收：小像素坐标、归一化坐标、旧历史数据、四类加载错误、初次布局延迟和卸载竞态
均有测试；涉及后端模型时同步检查 OpenAPI 漂移和后端全量。

主要风险：坐标字段是持久化/API 契约变更，必须提供旧记录兼容 decoder，不能直接
让既有历史预览失效。

### 7.1–7.2 去重与渲染常量

现状复核：

- 三个 AI `transcribe_page` 的主要重复已在 5.5 通过 provider 基类收敛。
- A4 字体尺寸已在 5.4 进入 `A4RenderTheme`。
- AI/OCR HTTP、持久化设置读取、两条渲染主路径、render schema、前端 SVG 栅格化
  的剩余重复，以及页面几何/文本车道常量仍待处理。

实施方案：

1. 每次只收敛一种重复，并以旧入口兼容测试保护签名、异常和输出；不做跨子系统
   “万能 helper”。
2. HTTP 共享层只负责传输、超时和 OpenAI-compatible 响应解析，provider 保留领域
   prompt/配置职责。
3. 渲染提取 `_render_score_on_page()`、schema 公共基类和命名的 `PageGeometry` /
   `TextLaneMetrics`；常量必须包含单位及布局不变量测试。
4. PNG/JPEG 共用 `svgToRasterBlob(type, quality, background)`，wrapper 保持现有 API。

验收：去重前后 golden/结构化输出一致；render 专项、AI/OCR、export、OpenAPI 和
前端构建全部通过。

主要风险：抽象会改变异常文本、Pydantic schema 或 SVG 字符串顺序；先锁定公共契约，
再移动代码。

### 7.3 巨型函数与组件拆分

范围：`parse_jianpu_score`、render main、exec render、RecognizeView、ConvertView、
SyntaxView。

实施顺序：

1. 先补行为测试和依赖图，不在同一提交中修功能。
2. `parse_jianpu_score` 引入 `JianpuParserState`，分 lexer/parser/normalizer，逐步
   消除 nonlocal。
3. render 按 page/A4/multi-part/pagination 拆模块；exec render 按输入类型和 batch
   action 拆分，facade 保持旧导入路径。
4. Vue 页面先抽无 UI 的 composable，再抽 toolbar/page-list/pane；父页面只负责编排。
5. Syntax 静态数据移到 TS data 模块，章节使用可测试小组件。

验收：每次移动后立即运行对应专项；最终建议 view < 800 行、composable < 300 行、
Python 单函数 < 80 行，超过目标时在台账记录理由，而不是为了行数制造碎片。

主要风险：大规模移动极易与功能修复混杂；该工作包必须小步提交并保留兼容 re-export。

### 7.4 死代码清理

现状复核：

- `_render_beat_items`、`_render_articulation`、`_upper_mark_anchor_y` 已在 5.4 删除。
- 审计所称 OCR client “全文死代码”不准确；`ocr_prompt_for_model()` 仍有调用者。
- `measure.py` 冗余和 Audiveris 永不执行 fallback 仍待复核。

实施方案：用静态引用、运行时入口、测试和打包结果四重证据逐符号删除；OCR client
只删除确认无调用的 `build_request` / `send_request`，保留 prompt 能力；Audiveris
路径改为启动期显式校验时保持既有诊断信息。

验收：全仓引用检查、OCR/OMR/render 专项、Ruff、后端全量和 Electron build 通过。

### 7.5 API 一致性

实施方案：

1. `JianpuToMusicXmlRequest` 增加并贯通 `accidental_mode`。
2. `ExportMusicXmlRequest.target_key` 使用 `TargetKey`。
3. `jianpu_text` / `jianpu_file_id` 用 model validator 要求恰好一个。
4. 只保留 `measure_number_mode`；旧 `show_measure_numbers` 给一个兼容周期，冲突请求
   明确拒绝。
5. 由 typed error/route 决定错误 stage，移除全局 `ValueError => convert` 误标。
6. 保留同步 history route 在线程池执行的正确策略，并文档化同步 I/O 路由规则。

验收：请求组合真值表、旧字段兼容、错误 stage、OpenAPI 生成类型和前端调用方全部
测试；后端全量、前端类型/构建通过。

主要风险：这是公开 API 兼容工作，弃用字段不能一步删除。

### 8.1–8.3 测试体系

现状复核：

- 前端已有 63 个工具测试（62 通过、1 因 Windows 符号链接权限跳过），但尚未配置
  Vitest 组件测试和 Playwright Electron E2E。
- AI/OCR、任务并发、导出等覆盖已随前序修复增加，仍需按当前代码重新做缺口统计。
- FastAPI 越层豁免已清零；`KNOWN_LAYER_VIOLATIONS` 仍有 5 个 exec→domain 豁免。
- 审计提出 MuseScore CLI 测试不适用：当前仓库没有该 CLI 集成。

实施方案：

1. 先生成按模块/分支的覆盖率基线，再补 Vitest + Vue Test Utils 和最小 Electron
   Playwright smoke。
2. 后端重点覆盖 composition 注入/并发、AI/OCR HTTP 错误、fake external tool 的
   recognize/pipeline 全流程、Upload/History/Task/Chat 并发及导出失败。
3. SVG 测试改用 XML/class/data 查询和相对关系/容差；浮点用 `pytest.approx`；
   命令行只断言有语义要求的顺序。
4. 通过服务边界清除剩余 5 个 exec→domain 豁免，完成标准是删除
   `KNOWN_LAYER_VIOLATIONS`，不是扩白名单。

验收：覆盖率报告可复现、组件和 E2E 可在 CI 无交互执行、脆弱断言替换前后均能抓住
真实回归、架构测试不含已知豁免。

主要风险：E2E 依赖 Electron/后端/端口/进程清理，必须使用随机端口、临时数据目录和
有界 teardown，避免 CI 孤儿进程。

### 9.1 CI

当前 CI 已有后端 Ruff check/pytest，以及前端 lint、typecheck、工具测试、OpenAPI
漂移和 build；仍缺格式、覆盖率、安全和版本矩阵。

实施方案：

1. 增加 `ruff format --check backend tests scripts`。
2. 生成 coverage XML/HTML，先记录基线，再按不低于基线门禁，避免一次性虚高阈值。
3. 增加 `pip-audit`、生产依赖 `pnpm audit --prod --audit-level=high` 和 PR dependency
   review；锁定例外必须注明 CVE、影响和到期日。
4. 后端测试 Python 3.11/3.13；纯后端增加 Ubuntu smoke，Electron build 保持 Windows。

验收：本地等价命令全部通过；CI 缓存不掩盖 lockfile 漂移；安全扫描失败可定位到具体
依赖而非静默 `continue-on-error`。

### 9.2 依赖治理

实施方案：

1. 以 `pyproject.toml + uv.lock` 为 Python 唯一事实来源；`requirements.txt` 删除，
   或改为 `uv export` 生成并在 CI 校验漂移。
2. 运行时直接导入的依赖必须在主依赖声明；pytest/coverage/Hypothesis 只在 test extra。
3. 增加 `[tool.ruff]`，从当前可通过的规则集开始，固定 Python 3.11 target。
4. Electron 33→目标版本单独立项，逐主版本阅读迁移说明并验证 contextBridge、IPC、
   protocol、窗口生命周期、builder 和真实关闭流程，不与普通代码清理混做。
5. 处理 Starlette TestClient/httpx 弃用警告时按 FastAPI/Starlette/httpx 兼容矩阵
   整组升级。

验收：全新环境 locked install、Python 3.11/3.13、前后端完整门禁和打包通过；
lockfile 只包含预期变化。

主要风险：Electron 跨多个主版本、Python Web 栈联动升级都可能产生隐性行为变化，
必须各自独立回归和回滚点。

### 9.3 文档与配置契约

实施方案：

1. README 加真实截图或删除占位符；只宣传已有且有测试证据的能力。
2. 删除不存在的 MuseScore CLI 描述，准确说明 PDF=PyMuPDF、MIDI=mido、
   PNG/JPEG=前端 Canvas。
3. 让 `env.example` / environment 文档覆盖 DATA_DIR、CACHE_DIR、WORKDIR、
   OUTPUT_DIR、上传限制、API token 等实际变量；用测试对比代码读取的变量集合。
4. AI prompt 将失败示例标成“❌ 反例”，同步双附点、显式 tuplet 和微音程语法。
5. 最终逐条回查原始审计报告，给每项标注已修复、不成立、被替代或仍开放，并链接
   验证记录。

验收：文档命令可复制执行、变量清单自动校验、README 功能与测试矩阵一致、原审计
没有无结论条目。

## 最近完成工作包

### 4.6a Audiveris MusicXML DOCTYPE 兼容回归

状态：已完成（2026-07-04）

问题与根因：

- 用户真实识别任务生成的两个 Audiveris 5.10.2 `.mxl` 均失败，错误为
  “不允许包含 DTD 或 ENTITY 声明”。
- 4.6 的 XML 安全预扫描把标准 MusicXML 4.0.3 `PUBLIC DOCTYPE` 与危险内部实体声明
  一并拒绝；解析器尚未读取 score 内容就失败。这是 4.6 引入的新兼容回归。

实际修改：

- `safe_xml` 默认策略仍拒绝所有 DTD/ENTITY；仅 MusicXML 文件/字符串读取边界可显式
  开启标准 DOCTYPE 兼容。
- 只接受根类型、Recordare 公共标识、版本、Partwise/Timewise 类型与
  `musicxml.org/dtds/*.dtd` 系统标识彼此一致的标准声明。
- 合法声明在交给 `ElementTree` 前替换为空白，并保留换行位置，因此不会发起外部 DTD
  请求，也不会影响后续解析错误的行号。
- 内部子集、任何 `ENTITY`、任意 `SYSTEM` DTD、非 MusicXML DTD、重复或畸形
  DOCTYPE 继续抛出 `UnsafeXmlError`；OMR、SVG 等其他 XML 入口没有放宽。

真实文件验证：

- `月亮之上-Fl. 1 2_page_001.mxl`：读取成功，解析 1 个 score、31 个小节。
- `月亮之上-Fl. 1 2_page_002.mxl`：读取成功，解析 1 个 score、41 个小节。

测试：

- 红灯测试：新增标准 Audiveris MXL 测试在旧实现上按预期失败，原有及新增危险
  DTD/ENTITY 样例通过拒绝测试。
- safe XML 专项：11 passed。
- safe XML、架构、转换、Audiveris、overlay、render 组合：150 passed。
- Ruff format/check：通过。
- 随机临时数据根下后端全量：415 passed、1 skipped；仅保留既有
  Starlette TestClient/httpx 弃用 warning。

未发现本修复引入的新问题。

### 6.1 Vue 响应性与生命周期

状态：已完成（2026-07-04）

实际修改与复核：

- log store 为每条记录分配稳定单调 ID，仅保留最近 1000 条；LogPanel 使用稳定 key，
  根容器正确绑定自动滚动 ref。
- FileUploader 的 `uploadQueue` 以及 RecognizeView 的 Map/Set 均位于
  `<script setup>`，实际是实例作用域；审计中的“跨实例共享”不成立，未实施会制造
  全局共享状态的无效重构，并用源码作用域测试锁定。
- AiAssistant 的动画 timer 在替换和 unmount 时清理；assistant 流式 delta 通过数组
  元素替换更新。
- JianpuEditor 删除会在历史恢复时改写文本的 immediate 格式化 watcher，并清除其
  遗留的未使用辅助函数；用户主动输入小节线的自动换行仍保留。
- JianpuPlayer 持久化 0–1 音量，损坏值回退 0.8；直接 MIDI、简谱生成和 MusicXML
  生成失败都会卸载旧音频、显示错误并发送 message。

验证：

- 旧实现专项：6 failed、1 passed；通过项为两个 `<script setup>` 作用域问题的复核。
- 修复后 6.1 专项：7 passed。
- 前端工具测试：62 passed、1 skipped。
- TypeScript、生产 build 通过；ESLint 0 error，仅保留既有 AI Markdown
  `vue/no-v-html` warning。

新增问题处理：

- lint 在移除自动格式化路径后发现 `splitInlineComment` 成为未使用函数；已作为同一
  工作包残留清理，重跑 lint 后未留下新 warning。
- 未发现 6.1 引入的开放问题。

### 5.8 Electron / IPC 缺陷组

状态：已完成（2026-07-04）

实际修改：

- preload 的 `BackendAPI` 从运行时 `api` 推导，删除 `__BACKEND_URL__` 死声明。
- backend connection 改为 invoke/handle；renderer mount 前初始化类型化连接缓存。
- 开发 uvicorn 移除 `--reload`；新增有界子进程树终止模块，启动失败和退出竞态均
  安全收敛。

验证：

- 四个旧实现红灯全部复现；静态契约和真实 Node 子进程终止夹具：4 passed。
- 前端工具测试：55 passed，1 skipped。
- typecheck、build、OpenAPI 类型漂移通过；ESLint 0 error、既有 1 warning。

### 5.7 设置系统缺陷组

状态：已完成（2026-07-03）

实际修改：

- SettingsUpdateRequest 增加 OCR/AI/assistant 的 base_url/model；URL 仅允许
  无凭据 HTTP(S)，model 非空且最长 256，heap 限定 `1g/2g/3g/4g`。
- 设置保存、响应、OCR provider、AI 转写和 assistant 全部使用持久化覆盖值。
- 字符串 `"0"` 项确认不成立并加入回归。
- 刷新前端 OpenAPI 类型。

验证：

- settings provider：14 passed，1 skipped。
- settings/API/AI/OCR/architecture 组合：103 passed，1 skipped。
- Ruff、OpenAPI 漂移、前端 typecheck/build 通过；ESLint 0 error、既有 1 warning。
- 随机临时数据根下后端全量：411 passed，1 skipped，保留既有
  Starlette TestClient/httpx 弃用 warning。

### 5.6 数据持久化缺陷组

状态：已完成（2026-07-03）

实际修改：

- 旧 history 表无损迁移；`list_batches` 固定两次查询；PATCH 使用 `UNSET`
  区分省略和显式 NULL。
- history schema v1 的 ALTER/回填/索引/user_version 在单一事务内完成，失败
  全量回滚并拒绝未来版本。
- chat 连接启用 WAL、foreign_keys、5 秒 busy timeout；任务恢复只选
  pending/running，未知状态降级为 failed 诊断。

验证：

- 六组红灯分别复现 N+1、NULL、半迁移、锁失败、终态误恢复和未知枚举崩溃。
- history：26 passed；AI：32 passed；tasks：10 passed。
- history + AI + tasks + API + architecture 组合：109 passed。
- Ruff format/check 与 OpenAPI 类型漂移检查通过。
- 随机临时数据根下后端全量：402 passed，1 skipped，保留既有
  Starlette TestClient/httpx 弃用 warning。

### 5.5 AI / OCR 服务缺陷组

状态：已完成（2026-07-03）

实际修改：

- OCR provider 工厂显式支持 `mock/openai_compatible/dashscope`，未知类型直接失败；
  DashScope 请求使用统一 `OCR_TEMPERATURE`。
- 三个 OpenAI-compatible 视觉 provider 复用
  `OpenAICompatibleVisionTranscriber`，统一校验、请求、异常和响应解析。
- chat schema 无损迁移到 `system/user/assistant` 三角色约束；空 YAML 和非法 YAML
  根节点统一转换为可诊断 `AITranscriptionError`。
- 前端删除会话维护 loading/error，服务端失败时不再误改本地状态。

验证：

- OCR / AI / settings / architecture 组合：62 passed，1 skipped。
- 前端工具测试：51 passed，1 skipped；TypeScript、OpenAPI 类型、build 通过；
  ESLint 0 error，保留既有 1 warning。
- Ruff format/check：通过。
- 随机临时数据根下后端全量：395 passed，1 skipped，保留既有
  Starlette TestClient/httpx 弃用 warning。

### 5.4 渲染服务缺陷组

状态：已完成（2026-07-03）

计划影响：

- `backend/score_trans/services/render/`
- `@text` 指令、A4 配置、多分谱布局、非 4/4 节拍分组
- 小节线/文本边界、CSS 角色和无调用死代码

目标：

- 按八个子项分别建立可观察回归，避免一次性重写脆弱 SVG 引擎。
- 让布局尺寸来自统一 RenderOptions/命名配置，而不是散落硬编码。
- 修正多分谱、非 4/4、极端音高和文本溢出的实际渲染边界。

子项进度：

- [x] 5.4.1 `@text`：确认旧指令覆盖结构化 OCR 文本与当前契约冲突；正式按弃用
  语法剥离，并将内部函数改名为 `_strip_legacy_text_directives`，避免继续暗示会解析
  该指令。结构化 `TextBlock` 仍是唯一权威来源。
- [x] 5.4.2 A4 字体尺寸硬编码：新增不可变 `A4RenderTheme`，11 个 A4 字体尺寸
  全部由命名主题注入 `_a4_render_options()`，函数体不再保留字体裸数值。
- [x] 5.4.3 多分谱页面范围：measure range 和 note index 现在汇总页面内所有声部，
  不再只读取第一声部。
- [x] 5.4.4 非 4/4 文本模式节拍分组：按 `4 / beat_type` 计算每拍时值，
  6/8 等拍号不再用 `int(cursor)` 错分半拍。
- [x] 5.4.5 小节线视觉高度：按本小节音符/和弦、八度点、连音组、演奏标记、
  力度、歌词和无坐标文本的实际视觉上下界扩展普通及反复小节线，同时保留原有
  最小高度。
- [x] 5.4.6 无坐标文本溢出边界：先验证候选基线是否位于页面安全区，再追加 SVG。
- [x] 5.4.7 `role=other` 的 CSS 分类：非力度、非歌词文本使用独立
  `annotation` 类。
- [x] 5.4.8 无调用渲染死代码：删除 `_render_beat_items`、
  `_render_articulation`、`_upper_mark_anchor_y` 的实现与重导出；全仓 Python
  引用只剩防回归断言。

阶段验证：

- 5.4.1 / 5.4.3 / 5.4.4 / 5.4.6 / 5.4.7 定向回归：5 passed。
- 多分谱回归在旧实现上按预期失败：第二声部的 source page range 缺失。
- 非 4/4、文本越界和文本角色测试在旧实现上分别按预期失败。
- 极端五音和弦的上下八度点在旧实现中越出固定小节线；动态边界修复后，相关
  八度点和反复记号组合回归 3 passed。
- A4 主题注入与非 4/4 `beat_duration` 接口回归：2 passed。
- 死代码重导出红灯测试在旧实现上按预期失败，清理后通过。
- 渲染专项：83 passed。
- Ruff format/check：通过。
- 临时数据根下后端全量测试：386 passed，1 skipped；保留既有
  Starlette TestClient/httpx 弃用 warning。

## 已完成

### 1.1 缓存清理删除被引用文件

完成日期：2026-07-03

实际修改：

- `HistoryDao.referenced_file_ids()` 使用两次直接查询收集引用，不再通过
  `list_batches()` 为每个批次额外查询页面。
- 覆盖页面的 input、MusicXML、SVG、overlay SVG、overlay 和 source map，
  以及批次的所有 render page 文件。
- `UploadService.prune_unreferenced()` 只删除未引用目录，并原子刷新
  `index.json`；保留目录会重新写入索引。
- 缓存统计继续区分删除项和保留上传数。

验证：

- 新回归测试在旧实现上出现 2 个预期失败，修复后 2 个均通过。
- 缓存、上传、历史、架构组合测试：36 passed。
- 后端全量测试：267 passed，1 skipped。

### 5.6a 旧 history 表无损迁移

完成日期：2026-07-03

实际修改：

- 删除新建 schema 前的 `DROP TABLE history`。
- 已知旧 schema 的每一行迁移为一个同 ID 的 batch/page，保留创建时间、
  输入文件、MusicXML、简谱、SVG、状态和错误信息。
- completed/failed 旧记录用原创建时间填充 completed_at。
- 建表、数据复制、索引和旧表重命名处于同一个 `BEGIN IMMEDIATE` 事务。
- 原表重命名为 `history_legacy_backup`；若同名备份已存在则停止迁移，避免覆盖。
- 缺少旧 schema 必需列时 fail-safe，原表保持不变。

验证：

- 两条真实旧 schema 样例完整迁移，第二次初始化不重复写入。
- 故障注入在部分 batch 插入后抛错，验证新表整体回滚、旧表两行仍在。
- 历史、缓存、上传、架构组合测试：38 passed。
- 后端全量测试：269 passed，1 skipped。

### 1.2 / 1.3 时值往返与双附点

完成日期：2026-07-03

实际修改：

- `duration_affixes()` 正确区分“整数拍”和“整数拍 + 分数拍”，混合时值使用
  `whole` 条延长线。
- 时值解析先计算附点、再增加延长线；`q5.-` 因此为 7/4 而非 9/4。
- 多附点统一按原始 base 计算几何级数；Event 保存真实附点数量。
- parser、renderer 和 `token_duration()` 共用 `consume_duration_suffix()`。
- 生成器支持最多三附点的规范短写；无法表示的时值明确抛错，不再静默退化成一拍。
- SVG 对未跨拍的双/三附点音符绘制对应数量的 rhythm dots，并为其预留宽度。

验证：

- 13 组基础、附点、混合和整数时值 round-trip 参数测试。
- 双附点、三附点、附点加延长线、无法表示时值均有回归测试。
- Jianpu 专项：62 passed。
- render 专项：71 passed。
- 后端全量测试：286 passed，1 skipped。

### 1.5 pipeline 空渲染页面

完成日期：2026-07-03

实际修改：

- 新增领域级 `RenderError`，renderer 未返回页面时不再泄漏 `IndexError`。
- `FullPipelineAction` 在渲染后立即验证页面列表；`PipelineActions` 在注册任何
  输出文件前再次验证，覆盖自定义或测试 pipeline 实现。
- `ScorePipelineOutputs.jianpu_svg_path` 也使用相同守卫，避免其他调用者重新引入
  下标越界。
- API 将该错误映射为结构化 `500` 响应：`stage=render`。
- 空渲染失败时上传目录保持为空，不留下已注册的 MusicXML 或简谱半成品。

验证：

- 红灯阶段两个测试模块因 `RenderError` 尚不存在而按预期收集失败。
- 空页面、零部分注册、API 错误映射：3 passed。
- pipeline、API、任务、架构组合测试：43 passed。
- Ruff 专项检查：通过。
- 后端全量测试：289 passed，1 skipped。

### 1.6 AI 对话流式失败原子持久化

完成日期：2026-07-03

实际修改：

- 同步与流式消息都不再在模型调用前持久化用户消息；当前用户输入以临时上下文
  参与模型请求。
- 历史窗口改为“最近 39 条已提交消息 + 当前临时用户消息”，保持原有最多
  40 条上下文的约束。
- 新增 `AiChatDao.add_exchange()`，在一个 `BEGIN IMMEDIATE` 事务中写入用户、
  助手两条消息，并在首轮成功时更新会话标题和时间。
- 模型调用失败、流式中断、客户端提前关闭生成器或第二条 INSERT 失败时，都不会
  留下孤立用户消息；既有会话标题也不会被失败请求改写。
- 成功流仍保持 `session → delta* → message → messages` 协议。

验证：

- 红灯测试：3 failed（流式孤立消息、同步孤立消息、缺少原子 DAO 方法）。
- AI chat 回归：7 passed。
- AI、架构组合测试：21 passed。
- Ruff 专项检查：通过。
- 后端全量测试：292 passed，1 skipped。

### 1.8 应用关闭任务收敛

完成日期：2026-07-03

实际修改：

- 关闭流程不再 `while` 重复 gather 同一集合，而是冻结一次任务快照、等待一次并
  在 `finally` 中显式移除该快照。
- 生命周期进入 shutdown 时关闭后台任务注册入口，标准调度函数拒绝后续注册。
- 被拒绝的 coroutine 会主动 `close()`，不产生“coroutine was never awaited”泄漏。
- 不强制取消已运行的 OMR/AI 线程，避免线程在 task 已失败后继续写入结果的副作用。
- lifespan 再次启动时会重新打开注册入口，兼容同一 app 实例的测试/重启生命周期。

验证：

- 红灯测试成功复现热循环；旧实现连 `asyncio.wait_for` 的超时回调都无法调度，
  因此外层测试命令超时，已按命令行精确清理对应 pytest 进程。
- 残留 completed task 清理与 shutdown 后拒绝注册：2 passed。
- 任务、API、架构组合测试：38 passed。
- Ruff 专项检查：通过。
- 后端全量测试：294 passed，1 skipped。

### 1.9 用户数据目录拼写迁移

完成日期：2026-07-03

实际修改：

- 后端与 Electron 默认目录从错误的 `.sorce_trans` 修正为 `.score_trans`，保留
  `LEGACY_USER_DATA_DIR_NAME` 作为迁移来源。
- 两端都按“只复制缺失项”递归迁移：不覆盖新目录已有文件、不删除旧目录，重复
  启动幂等；旧目录因此也保留为人工恢复备份。
- 文件复制使用排他创建，避免并发时覆盖刚出现的新文件；目录/文件类型冲突保留
  目标项，源项仍留在旧目录。
- 不跟随符号链接或特殊文件，避免迁移越出用户数据目录；初次迁移失败且新目录原本
  不存在时，后端继续使用旧目录。
- Electron 在读取配置前迁移旧配置和数据，并把旧默认 data/cache 路径规范化为
  新默认路径；失败时本次启动回退旧默认目录。
- 验证时设置临时 `SCORE_TRANS_DATA_DIR`，没有修改本机真实旧目录。

验证：

- 红灯阶段：后端因新常量/函数不存在而收集失败；Node 因迁移模块不存在而失败。
- 后端路径与架构测试：9 passed。
- 前端工具测试：41 passed，1 skipped（Windows 当前进程无符号链接权限）。
- 前端 ESLint：0 error，保留既有 1 warning；TypeScript：通过。
- Electron 生产构建：通过。
- Ruff 专项检查：通过。
- 临时数据根下后端全量测试：299 passed，1 skipped。

### 1.10 PDF max_pages=0

完成日期：2026-07-03

实际修改：

- `max_pages is None` 是唯一的“无限制”语义；`0` 现在产生空页面列表。
- 正数仍取 PDF 实际页数与限制的较小值。
- 负数在导入/打开 PyMuPDF 和创建输出目录之前抛出带参数名的 `ValueError`，
  不留下空目录或部分输出。

验证：

- 红灯测试：2 failed，旧实现把 0 当全部页且负数先尝试打开文件。
- PDF 专项：3 passed。
- AI、架构组合测试：23 passed。
- Ruff 专项检查：通过。
- 临时数据根下后端全量测试：301 passed，1 skipped。

### 1.4 TaskManager 订阅者幂等移除

完成日期：2026-07-03

实际修改：

- 全局 SSE 订阅队列由无界改为默认 128 条的有界队列，消除慢客户端造成的无限
  内存增长。
- 队列满时丢弃最旧进度并保留最新进度，不再从广播侧移除仍连接的订阅者，避免其
  后续只收到心跳却永远收不到更新。
- 生成器退出使用幂等移除，即使未来其他清理路径提前移除也不抛 `ValueError`。
- 队列容量可在构造时注入且必须大于 0，便于确定性并发测试。

验证：

- 红灯测试：旧构造器不支持有界队列参数，1 failed。
- TaskManager 专项：8 passed。
- 任务、API、架构组合测试：39 passed。
- Ruff 专项检查：通过。
- 临时数据根下后端全量测试：302 passed，1 skipped。

### 1.11 AI / OCR 流式空 choices

完成日期：2026-07-03

实际修改：

- AI 与 OCR 非流式 completion 共用严格响应解析，空/缺失/类型错误的 `choices`、
  `message`、`content` 都转为带 provider 名称的可诊断 `ValueError`。
- AI 流式解析把 `choices: []` 和缺少 choices 的 usage/keep-alive 帧视为空增量，
  直接跳过，不再下标越界。
- 流式 `error` payload 不会被当作空帧吞掉，会携带 provider message 抛出。
- 共享解析放入 `utils/openai_response.py`，避免 AI/OCR 修复再次漂移。

验证：

- 红灯测试：3 failed，均复现 `IndexError`。
- 空 choices / usage-only 专项：3 passed。
- AI、OCR、架构组合测试：39 passed。
- provider error payload 另有回归覆盖。
- Ruff 专项检查：通过。
- 临时数据根下后端全量测试：306 passed，1 skipped。

### 1.12 运行时 assert

完成日期：2026-07-03

实际修改：

- OCR 小节号应用逻辑用显式 `ValueError` 替换依赖优化级别的 assert。
- tie、slur、slide 共用 `_spanner_endpoints()`，在两个端点都缺失时稳定抛出
  带 start/stop 上下文的 `ValueError`，不再先发生 `None` 解包 `TypeError`。
- 删除对应的 `type: ignore`，端点类型经显式校验后自然收窄。
- 架构测试新增指定运行时校验文件的 `ast.Assert` 禁入门禁。

验证：

- 红灯测试：4 failed（2 个文件含 assert，3 个 spanner 暴露 TypeError）。
- 运行时校验专项：4 passed。
- render、convert、架构组合测试：89 passed。
- `python -O` 直接调用无端点 tie：输出 `optimized-validation-ok`。
- Ruff 专项检查：通过。
- 临时数据根下后端全量测试：310 passed，1 skipped。

### 2.1–2.3 双变音与等音拼写

完成日期：2026-07-03

实际修改：

- 新增基于调号五度数的书面音高映射：按目标调的七个音名字母、调号 alter 与
  MusicXML 源 step/alter 计算简谱 degree/accidental。
- double-sharp / double-flat 映射为 `x` / `bb`，不再按 MIDI 等音化为自然音。
- 写 MusicXML 时从简谱音级反推书面 step/alter，`b2` 保持降号方向、`#1`
  保持升号方向，双变音 magnitude 也保留。
- 修正跨 B→C 的调内八度计算；例如 D 调 `7` 现在写为 C#5，而不是 C#4。
- 显式 natural 只有在与“相对调号的简谱 accidental”一致时才保留文本符号；
  G 调 F-natural 正确写成 `b7`，不再错误输出 `n7`。
- provenance 锚点测试中 C# 的旧错误语义从 `#2` 更新为正确 `#1`，锚点范围未变。

验证：

- 红灯测试：3 failed（双变音、方向、跨调内八度均复现）。
- convert、Jianpu、render、架构组合测试：155 passed。
- 加入 provenance 后组合测试：166 passed。
- Ruff 专项检查：通过。
- 临时数据根下后端全量测试：314 passed，1 skipped。

新发现并已在本包修复：

- D 等非 C 调的高音级跨过 B/C 时，旧 writer 固定 `4 + octave` 会写低一个八度。

### 2.4–2.5 重复记号往返

完成日期：2026-07-03

实际修改：

- `Measure` 新增 ending start/stop/discontinue 与 new-page/new-system 字段，并在
  多 staff 拆分时完整复制。
- MusicXML parser 读取任意 barline location 中的 forward/backward repeat、
  backward `times` 和 ending 类型。
- parser 同时读取 `<print new-page>` / `<print new-system>`，覆盖审计正文中标题
  未单列的分页丢失问题。
- MusicXML writer 在左/右 barline 写回 ending 与 repeat；仅在 repeat_count > 1
  时写 `times`，避免伪造源中未声明的次数。
- 简谱已有 `|:` / `:|` 标志现在也会生成标准 MusicXML repeat 元素。

验证：

- 红灯测试：2 failed（parser 标志均为 false，writer 无 barline）。
- repeat/ending/print 专项：2 passed。
- convert、Jianpu、render、provenance、架构组合测试：168 passed。
- Ruff 专项检查：通过。
- 临时数据根下后端全量测试：316 passed，1 skipped。

### 2.6–2.8 连音结构与时值

完成日期：2026-07-03

实际修改：

- `Event` 新增 `tuplet_spans`，每个 span 有独立 id、MusicXML number 和
  start/stop；旧单值字段继续指向最外层，兼容现有 renderer。
- parser 使用有序栈而非 `number → id` 字典，同编号内外层通过 LIFO 正确闭合，
  MusicXML writer 可写回全部嵌套 start/stop。
- active tuplet 栈提升到 part 级，不再每小节清空，跨小节 start/stop 保持同一 id。
- 保存 `tuplet_normal_count`，MusicXML note type 与 time-modification 不再假设固定
  base。
- 裸 `$123$` 保持历史语义（总长一拍）；含显式时值的 `$q1 q2 q3$`、
  `$h1 h2 h3$` 按 normal/actual 比例缩放，后者总长四拍并能规范化写回。

验证：

- 红灯测试：3 failed（缺少 spans、跨小节断裂、half-note triplet 被压成一拍）。
- convert、Jianpu、render、provenance、架构组合测试：171 passed。
- Ruff 专项检查：通过。
- 临时数据根下后端全量测试：319 passed，1 skipped。

兼容边界：

- 当前 `$...$` 文本语法没有嵌套或跨小节分组的无损表示；模型与 MusicXML 直通已
  无损，导出简谱文本时兼容字段选择最外层单层表示。后续语法扩展需先定义稳定格式，
  不能在本包中发明不可兼容标记。

### 2.12–2.13 八度点与力度词汇

完成日期：2026-07-03

实际修改：

- 高音点按 dot index 每层向上 7px，低音点每层向下 7px；所有同一音符的八度点
  共用 x 坐标，符合垂直堆叠习惯。
- note/chord 的视觉 top/bottom 与低音时值线使用最外层点坐标，避免修正绘制后发生
  裁切或 beam 碰撞。
- `DYNAMICS` 补齐 pppp、ffff、sf、fz、rfz、sfp，并让 MusicXML
  `_is_dynamic_name()` 复用同一集合，消除双词汇表漂移。
- 扩展力度从 MusicXML 导出简谱后可被 parser 再次接受。

验证：

- 红灯测试：8 failed（六种力度、MusicXML 往返、八度点横排）。
- 八度点/力度专项：8 passed。
- render、Jianpu、convert、架构组合测试：168 passed。
- Ruff 专项检查：通过。
- 临时数据根下后端全量测试：327 passed，1 skipped。

### 2.10 标题、速度与方向输出

完成日期：2026-07-03

实际修改：

- MusicXML 默认标题改为 score 自身标题；API 显式传入 title 时仍具有最高优先级，
  未传入时不再用 `Jianpu Import` 覆盖原始元数据。
- `JianpuScore` 增加 tempo 语义，简谱文本的 `tempo=` 可写入 MusicXML
  `<metronome>` 和 `<sound tempo>`，MusicXML 速度也能解析回 score 和简谱文本。
- `TextBlock` 保留 words、rehearsal、dynamics、metronome 等方向类型；writer 按事件
  起点输出标准 `<direction>`，并保留 placement 和 staff。
- 同起点已存在 direction dynamics 时抑制重复的音符级 dynamics，避免往返后出现
  两份相同力度。
- 调整 `<staff>` 与 `<sound>` 的生成顺序以符合 MusicXML direction 的 schema 顺序。
- 后端请求 schema 的 title 改为可空，并同步刷新前端生成的 OpenAPI 类型。

验证：

- 红灯测试：2 failed（默认标题被固定覆盖、方向类型没有模型字段）。
- 标题、速度、方向专项：3 passed。
- convert、Jianpu、架构组合测试：96 passed。
- 临时数据根下后端全量测试：330 passed，1 skipped。
- OpenAPI 类型门禁和 TypeScript 类型检查：通过。
- 前端 ESLint：0 error，保留既有 1 个 `vue/no-v-html` warning。
- 未发现本工作包引入的新问题。

### 2.9 多声部 MusicXML

完成日期：2026-07-03

实际修改：

- writer 按 `(staff, voice)` 建立独立时间线，声部按原始首次出现顺序稳定输出，声部内
  事件按 start 排序且保留同起点原顺序。
- 声部切换和游标后退输出 `<backup>`，声部内空隙和尾部对齐输出 `<forward>`；
  divisions 同时纳入事件和方向起点分母，避免非整数拍起点被截断。
- 多声部 note 输出 `<voice>` / `<staff>`，和弦中的每个 note 均保留相同归属；单声部
  且原模型没有 voice 时继续省略 `<voice>`，保持既有输出兼容。
- 方向块仅在第一条时间线输出一次，但与事件共同按 start 定位；即使方向落在长音内部，
  MusicXML 往返后仍保留正确起点。
- 无 voice/staff 的 generated 尾部休止并入首条时间线，避免把解析器补齐事件误写成
  新的并发声部。
- 同步把 note 中 `<tie>` 调整到 `<voice>` 之前，符合 MusicXML note schema 顺序。

验证：

- 红灯测试：2 failed（多声部无 voice/backup、单声部显式空隙无 forward）。
- 多声部与单声部空隙专项：2 passed。
- convert、Jianpu、render、provenance、架构组合测试：184 passed。
- Ruff 专项检查：通过。
- 临时数据根下后端全量测试：332 passed，1 skipped。
- 未发现本工作包引入的新问题。

### 2.11 微音程信息

完成日期：2026-07-03

实际修改：

- `JianpuPitch.accidental`、`alter`、`midi` 使用 `Fraction` 精确保留，MusicXML
  parser 不再执行 `int(float(...))`；writer 用十进制文本无损写回 `<alter>`。
- MusicXML quarter / three-quarters accidental 与 ASCII 简谱 `qs`、`qf`、`tqs`、
  `tqf` 双向映射，±0.5、±1.5 不再伪装成普通 `#` / `b`。
- 共享时值解析使用最长前缀判定：`qs1` 是四分之一升的四分音符，`q1` 仍是
  八分音符，二者无语法冲突。
- SVG 把四种微音程 accidental 作为独立文本 glyph 绘制并纳入宽度/排序计算；
  前端语法高亮和播放定位同步识别这些 token。
- MIDI 在构造输出文件前扫描精确音高；遇到微音程明确报错“需要 pitch bend
  通道分配”，不会静默取整，也不会留下半成品文件。
- 同步更新 AI 转写语法提示和 [简谱语法文档](jianpu-syntax.md)，记录文本格式、
  SVG 表示及 MIDI 能力边界。

验证：

- 红灯测试：3 failed（MusicXML 取整、文本语法拒绝、MIDI 未到拒绝边界）。
- 微音程 MusicXML / SVG / MIDI 专项：3 passed。
- convert、Jianpu、render、export、provenance、架构组合测试：191 passed。
- Ruff 专项检查：通过。
- 临时数据根下后端全量测试：335 passed，1 skipped。
- 前端 ESLint、TypeScript、工具测试和生产构建：通过；保留既有 1 warning、
  1 个无符号链接权限 skip。
- 未发现本工作包引入的新问题。

### 3.1 models / DAO 反向导入 config

完成日期：2026-07-03

实际修改：

- `AiTranscribeRequest.render_dpi` 改为“请求可省略”；`AiActions` 在执行边界从唯一
  配置源注入默认 DPI，显式请求值仍优先，transcription service 不再保留第二个硬编码
  默认值。
- `SettingsResponse` 的 provider / base_url / model 改为必填响应字段；这些值一直由
  `SettingsActions` 完整装配，models 不再读取环境配置。
- `SettingsDao` 改为接收 defaults 映射，只负责 `INSERT OR IGNORE` 持久化；
  `services/settings/defaults.py` 负责从环境配置构造生产默认值。
- 所有 service 的默认设置 DAO 都经同一装配函数获取；重复构造不会重复写库，后续环境
  默认值也不会覆盖用户已保存值。
- 架构门禁同时禁止 models 和 DAO 导入 config，删除两个 models 的已知违规豁免，
  并把 DAO 的允许依赖恢复为 models / utils / 同层模块。
- 同步刷新 OpenAPI 类型：SettingsResponse 配置字段对前端变为可靠必填，
  AI `render_dpi` 为可省略/可空。

验证：

- 红灯测试：1 failed，准确列出 3 个反向依赖文件。
- 架构专项：6 passed。
- 架构、AI transcription、settings provider、API 组合测试：62 passed，1 skipped。
- 默认值注入覆盖“省略使用配置默认”和“显式请求覆盖默认”；DAO 覆盖“补缺但不覆盖
  用户值”。
- Ruff、OpenAPI 类型门禁、TypeScript、ESLint：通过；保留既有 1 warning。
- 临时数据根下后端全量测试：339 passed，1 skipped。
- 未发现本工作包引入的新问题。

### 3.2 exec 层 HTTPException / FastAPI 越层依赖

完成日期：2026-07-03

实际修改：

- export、files、history、render actions 不再构造 `HTTPException`，分别使用
  `ValueError`、`FileNotFoundError` 和领域级 `RenderError`。
- API 全局异常处理器在边界保留 400 / 404 / 500 状态及原错误文本；通用
  ValueError 的 stage 从误导性的 `convert` 改为 `validation`。
- 新增 models 层 `UploadFileLike` 结构协议；export、files、pipeline、recognize 和
  UploadService 不再为了类型注解导入 FastAPI。
- 删除 7 项 FastAPI 越层豁免，架构门禁现在硬性要求 API 之外 FastAPI 导入为零。
- render 的 lenient OCR 解析改为捕获 `ValueError`；空渲染结果使用已有 RenderError，
  保持 1.5 工作包的结构化 500 语义。

验证：

- 红灯测试：1 failed，列出当前全部 7 个 FastAPI 越层文件。
- files/export/render API 边界回归覆盖 404、404、400 的状态、文本和 stage。
- 架构、API、render、export、history、pipeline、OCR 组合测试：158 passed。
- Ruff 专项检查：通过。
- 临时数据根下后端全量测试：340 passed，1 skipped。
- 未发现本工作包引入的新问题。

### 3.3 API 异步路由同步阻塞

完成日期：2026-07-03

实际修改：

- export 的 MIDI/MusicXML 同步转换全部通过 `asyncio.to_thread()` 等待结果；
  PDF 保持异步读取 UploadFile，但 PDF 生成和注册整体在线程中执行。
- settings 的读取、更新、缓存统计/删除全部移入线程，避免 SQLite 与递归文件操作
  阻塞事件循环。
- files 的上传、存在性检查、下载解析和删除移入线程；AI 会话的同步 SQLite
  list/create/get/delete 同样处理。
- 已有 render 路由的 to_thread 和 chat/pipeline/recognize 真异步路径保持不变，
  没有误用 BackgroundTasks。
- 架构测试扫描 async route 中 15 个已知阻塞 action，禁止直接调用。

验证：

- 红灯测试：2 failed，export 和 clear-cache 均阻塞事件循环约 200ms。
- export、clear-cache 修复后与既有 render 心跳测试：3 passed。
- 架构、API、export、AI、settings、cache 组合测试：73 passed，1 skipped。
- Ruff 专项检查：通过。
- 临时数据根下后端全量测试：343 passed，1 skipped。
- 未发现本工作包引入的新问题。

### 3.4 config / utils 循环导入

完成日期：2026-07-03

实际修改：

- `CONFIG_DIR` 下沉到 `models/common/paths.py`，与 PROJECT_ROOT 共同维护开发和
  PyInstaller 路径语义；`config.__init__` 仅兼容性重导出。
- `utils/env.py` 直接依赖路径模型，不再反向导入 config，dotenv 查找仍优先
  CONFIG_DIR/.env，再回退 PROJECT_ROOT/.env。
- 同源的 `utils/pdf.py → config.settings` 一并移除；PDF 工具函数改为调用方必传
  DPI，AI 执行边界仍使用环境配置默认值。
- 新增架构门禁，禁止任何 utils 模块导入 config，并增加 CONFIG_DIR 所有权/兼容
  重导出测试。

验证：

- 红灯测试：1 failed，列出 `utils/env.py` 与同源 `utils/pdf.py` 两个反向依赖。
- 架构、路径、dotenv、PDF/AI 组合测试：51 passed。
- Ruff 专项检查：通过。
- 临时数据根下后端全量测试：345 passed，1 skipped。
- 未发现本工作包引入的新问题。

### 4.1 API 认证与授权边界

完成日期：2026-07-03

实际修改：

- FastAPI 增加纯 ASGI Bearer 中间件；除 `/health` 和不携带业务数据的 CORS
  preflight 外，JSON、multipart、SSE、OpenAPI、文件 GET/HEAD 和 Range 请求均受
  同一策略保护。失败统一返回 `401`、`stage=auth` 和 `WWW-Authenticate: Bearer`。
- 后端默认 fail-closed：启用认证时 `SCORE_TRANS_API_TOKEN` 必须至少 32 字符；
  只有显式 `SCORE_TRANS_API_AUTH_DISABLED=1` 才可关闭，pytest 仅在
  `tests/conftest.py` 中使用该测试入口，认证测试则重新强制启用。
- Electron 主进程每次实例化后端时生成新的 256-bit 随机 token，通过子进程环境
  传给 FastAPI，并经 context-isolated preload IPC 以进程内连接信息传给 renderer；
  token 不进入 URL、日志、设置、历史或磁盘。
- renderer 的普通请求、XHR 上传、AI 流、任务 SSE、文件探测和播放器统一使用认证
  请求。原生 `EventSource` 改为支持 Authorization header 的 fetch 流，并保留原有
  轮询降级。
- 图片、PDF、SVG 预览和导出先认证获取 Blob，再使用可回收 object URL；直接下载
  同样先取 Blob，避免 token 查询参数和未鉴权媒体 URL。
- 开发文档、环境样例与 OpenAPI 生成脚本同步 token 配置；架构门禁禁止 renderer
  再次出现绕过认证客户端的原生 fetch 或 EventSource。

验证：

- 红灯测试：5 failed，均因应用工厂尚不支持认证参数而按预期失败。
- 认证专项：5 passed，覆盖无/错/正确 token、查询参数拒绝、health、CORS、
  request body、HEAD、Range、OpenAPI 与 SSE。
- API、任务、上传、架构组合：60 passed。
- 真实 uvicorn 子进程：`health=200 missing=401 wrong=401 correct=200`。
- 前端工具测试：41 passed，1 skipped；其中断言 renderer 实际发送 Bearer header。
- TypeScript、OpenAPI 类型漂移和 Electron 生产构建：通过。
- ESLint：0 error，保留既有 1 个 `vue/no-v-html` warning。
- Ruff：通过。
- 临时数据根下后端全量测试：351 passed，1 skipped。

新发现并已在本包修复：

- Node 工具测试环境没有 Vite 注入的 `import.meta.env`；API 客户端改为兼容缺失
  env 对象，并让该测试同时验证进程内 token 的 Authorization header。

未发现本工作包遗留的新问题。

### 4.2 Electron 主进程 SSRF

完成日期：2026-07-03

实际修改：

- renderer 对后端导出文件先使用 4.1 的认证文件客户端获取 Blob，再把
  `ArrayBuffer` 交给 preload；正常导出链不再向主进程传 URL。
- preload 与主进程 IPC 契约收窄为 `{ buffer: ArrayBuffer }`，主进程参数使用
  `unknown` 接收后做运行时校验，拒绝 URL、TypedArray、字符串和伪造对象。
- 新增纯主进程边界函数 `exportSourceBuffer()`，只负责验证并复制字节；`files.ts`
  完全移除 `fetch` 和任何网络来源分支，因此 renderer 即使被攻破也无法借导出 IPC
  请求 localhost、内网、云元数据服务或 `file://`。
- preload 全局类型同步补全 `saveExportFile` / `openFolder`，避免安全契约只存在于
  运行时代码。

验证：

- 红灯测试：新安全测试因 `exportSource.ts` 不存在而按预期失败。
- 新增 3 个主进程安全测试：合法字节保真；localhost/元数据/file URL 与伪 buffer
  全部拒绝；`files.ts` 不含 fetch 或 URL 来源类型。
- 前端工具测试：44 passed，1 skipped。
- TypeScript：通过。
- ESLint：0 error，保留既有 1 warning。
- Electron 生产构建：通过。
- 后端未修改，4.1 的 351 passed、1 skipped 基线保持。

未发现本工作包引入的新问题。

### 4.3 导出路径遍历

完成日期：2026-07-03

实际修改：

- 文件名清理扩展为控制字符、路径分隔符、保留字符、前导/尾随点与空格；空结果使用
  `export`，`CON/PRN/AUX/NUL/COM1-9/LPT1-9` 等 Windows 设备名自动加安全前缀，
  超长文件名保留扩展名后截断。
- 导出目录必须为无 NUL 的绝对路径，并在任何规范化前拒绝原始 `..` 路径片段。
- 创建目录前逐级 `lstat`，拒绝已有符号链接/Windows junction 重解析点和非目录
  中间组件；创建后再以 `realpath` 验证 canonical 路径未被重定向。
- 每个候选目标都用 `path.relative` 验证严格位于 canonical 导出目录内。
- 唯一文件名不再使用“先 access、后 write”的竞态流程；改用 `wx` 原子独占创建，
  已存在则生成 `(1)`、`(2)`，写入失败会关闭并删除本次创建的残缺文件。

验证：

- 红灯测试：安全路径模块不存在，专项按预期失败。
- 路径专项 6 passed：文件名遍历、Windows 设备名、唯一命名、真实文件内容、
  原始目录 `..`、junction/symlink 重定向全部覆盖。
- 前端工具测试：47 passed，1 skipped。
- TypeScript：通过。
- ESLint：0 error，保留既有 1 warning。
- Electron 生产构建：通过。
- 后端未修改，351 passed、1 skipped 基线保持。

测试过程中仅发现用 `path.join()` 构造恶意样例会提前消除 `..`，已改为保留原始
IPC 字符串的测试写法；这是测试夹具问题，不是产品新缺陷。

### 4.5 SVG v-html 防御纵深

完成日期：2026-07-03

实际修改：

- `SvgPreview` 完全移除 `v-html`，不再把字符串交给 Vue/浏览器直接解释；现在先生成
  独立 XML DOM，经清洗后 `document.importNode()` 并 `replaceChildren()` 挂载。
- SVG 元素改为严格白名单，仅保留当前 renderer 使用的 svg/defs/style/g、基础形状
  与文本元素；script、foreignObject、image、use、a、animate 及所有未知元素整棵
  子树删除。
- 属性按元素白名单处理；href/xlink/src、inline style、事件属性和未知命名空间均
  不允许。path、transform、paint、数字、class 和 provenance data 属性另做值格式
  与长度校验。
- `<style>` 只能位于 `<defs>`；CSS 重新解析并构造，只保留 renderer 需要的属性和
  简单 class/text selector。`@import`、URL/function、转义、未知 property 和危险
  selector 不会进入结果。
- 保留播放高亮所需 class、note index、source ids、bbox、路径数据和安全的动态字体
  样式，现有 DOM 查询与交互机制不变。

验证：

- 红灯测试：SVG sanitizer 模块不存在，专项按预期失败。
- 3 个纯安全测试通过：元素/属性白名单、恶意 CSS、无 v-html DOM 挂载。
- 隐藏 Electron BrowserWindow 实测通过：恶意 script/foreignObject/image/use、
  onload/onclick/href/inline style、`@import` 和 `url(javascript:)` 全部移除；正常
  path 与 `data-source-ids` 保留。
- 前端工具测试：50 passed，1 skipped。
- TypeScript：通过。
- ESLint：0 error；SvgPreview warning 消失，仅保留审计 4.4 已确认安全的 AI
  Markdown `vue/no-v-html` warning。
- Electron 生产构建：通过。
- 后端未修改，351 passed、1 skipped 基线保持。

未发现本工作包引入的新问题。

### 4.6 XML 炸弹

完成日期：2026-07-03

实际修改：

- 新增统一的有界 XML 解析入口，默认限制单个 XML 文档或压缩包成员为 64 MiB；
  文件和 ZIP 成员均采用 `上限 + 1` 的有界读取，不依赖可伪造的 ZIP 元数据。
- 解析前拒绝 `DOCTYPE` 和 `ENTITY` 声明，阻断十亿笑声、外部实体及参数实体类
  攻击；注释和 CDATA 中的同名字面量不会被误判。
- MusicXML、MXL container/rootfile、Audiveris 多乐章合并、OMR sheet、渲染 SVG
  映射和文本锚点等全部 XML 入口改用同一安全解析器，不只修报告中的单个样本。
- MXL 与 OMR 压缩成员在解压过程中执行同一大小上限，防止压缩包声明尺寸不可信时
  绕过限制。
- 架构门禁禁止在安全解析器之外新增 `ElementTree.fromstring()` / `parse()`，
  防止后续代码重新引入无界解析。
- 正常 UTF-8/XML 行为保持不变；非法编码、超限、DTD/ENTITY 均返回带来源名称的
  可诊断错误。

验证：

- 红灯阶段因安全解析模块尚不存在而按预期收集失败。
- 安全 XML、架构、转换、Audiveris 合并、OMR、render 组合回归：137 passed。
- Ruff 格式化与静态检查：通过。
- 随机临时数据根下后端全量测试：359 passed，1 skipped。
- 唯一 warning 仍是既有 Starlette `TestClient` 弃用提醒。

未发现本工作包引入的新问题。

### 4.7 文件上传大小限制

完成日期：2026-07-03

实际修改：

- 新增默认 256 MiB 单文件上限和 512 MiB multipart 请求总上限，分别可通过
  `SCORE_TRANS_MAX_UPLOAD_FILE_BYTES` 与 `SCORE_TRANS_MAX_UPLOAD_REQUEST_BYTES`
  配置；非正整数在启动导入阶段直接报出变量名和期望格式。
- `/files/upload`、`/pipeline`、`/recognize`、`/export/pdf` 在 multipart 解析前
  统一执行请求总大小限制；有 `Content-Length` 时立即拒绝，无长度或伪造长度时
  按 ASGI 数据块累计并在越界当下返回 413。
- `UploadService.save()` 改为 1 MiB 分块有界写入；单文件越界会删除整个临时上传
  目录，不写索引、不留下半文件。
- PDF 导出对每个图片和全部图片字节总量再次执行服务层限制，覆盖绕过 HTTP
  中间件的内部调用与测试调用。
- 新增 `UploadTooLargeError`，API 统一映射为
  `413 {"error": "...", "stage": "upload"}`；现有前端 API 错误显示无需改协议。
- 架构门禁通过 AST 收集所有 `UploadFile` 路由，并要求其集合与请求限制白名单完全
  一致，后续新增上传端点不会静默漏保护。

验证：

- 红灯阶段因请求限制模块尚不存在而按预期收集失败。
- 单文件边界、半文件清理、服务层 413、Content-Length、真实 ASGI 分块请求、
  PDF 单文件/总量限制：6 passed。
- 上传、API、pipeline、recognize、export、认证和架构组合回归：77 passed。
- Ruff 格式化与静态检查：通过。
- 随机临时数据根下后端全量测试：366 passed，1 skipped。

新发现并已在本包修复：

- 初版分块限制通过抛异常中止 multipart；FastAPI 会把该异常包装为 400。现改为
  越界时由 ASGI 中间件直接发送 413、抑制下游解析响应，并以真实无
  `Content-Length` multipart 数据流验证。

### 5.1 简谱文本解析缺陷组

完成日期：2026-07-03

实际修改：

- 行首小节标签识别不再吞掉独占一行的 `0.`–`7.` 附点音符，包括尾随空格的
  情况；冒号标签和带后续正文的点号标签仍按原规则忽略。
- 顶层和连音组中的未知 `^xy` 标记统一抛出带行列信息的明确语法错误，不再作为
  任意 articulation 静默保存。
- 同时修复文档已公开的紧贴标记语法：`^.2`、`^>3`、`^-4` 等会把已知标记
  正确附着到后续音符；未知紧贴标记仍被拒绝。
- 无空格连音扫描器支持和弦、时值前缀、双变音、附点、延长线和既有标记，
  `$[1+3]2$` 可稳定拆成两个连音事件。
- 简谱小节少拍现在记录 `小节少拍：实际 …，目标 …`，与既有超拍校验对称；
  不自动伪造休止符，原始输入事件保持不变。
- 只把第一次 `1=X` 声明作为全局头部；已有全局调号后、首个音符前的第二次声明
  会作为小节级换调，不再覆盖整首初始调。
- 后缀双变音 `1bb` / `2x` 与既有前缀 `bb1` / `x2` 等价，规范化输出继续采用
  稳定的前缀形式。

验证：

- 红灯测试：8 failed，六类审计缺陷均被实际复现。
- 新增 9 项核心回归，覆盖尾随空格和已公开紧贴标记语法。
- Jianpu 全量专项：78 passed。
- Jianpu、MusicXML、render、AI 转录、provenance、架构组合回归：225 passed。
- Ruff 格式化与静态检查：通过。
- 随机临时数据根下后端全量测试：375 passed，1 skipped。

新发现并已在本包修复：

- `docs/jianpu-syntax.md` 已声明支持 `^.2`、`^>3` 等紧贴标记，但旧实现会把整
  个 token 当成标记，音符被静默吞掉；严格未知标记校验若不同时修正此路径会造成
  新回归，因此一并闭环。

### 5.2 MusicXML 解析缺陷组

完成日期：2026-07-03

实际修改：

- MusicXML metronome 文本使用标准音符符号：quarter 显示为 `♩=108`，并补齐
  whole、half、eighth、16th–128th 映射；beat-unit-dot 会保留为符号后的点。
- MusicXML writer 同时接受新的音符符号和旧的 `quarter=108` 兼容文本，并写回
  标准 `<beat-unit>` / `<beat-unit-dot>` / `<per-minute>` 与 `<sound tempo>`，
  不因显示格式修正丢失结构语义。
- 同一游标位置多个方向力度按“时间位置最大、同位置文档顺序最后”确定当前有效
  力度；该时点及更早的 pending 力度一次性消费，不会把旧力度错误附到下一音符。
- 即使音符自身已有 notations dynamics，也会消费同时间的方向力度，避免方向事件
  泄漏到后续音符；原始方向 TextBlock 仍全部保留，往返信息不丢失。

复查结论：

- “多谱表分谱丢失 `staff=None/generated=True` 休止符”在当前代码不可复现。
  拆分后的每个 staff 都调用 `_normalize_measure()`，会按该 staff 的真实时长补回
  generated rest；既有 `test_split_multi_staff_part_preserves_empty_measure_slots`
  已验证完全空的 staff 小节仍有补齐休止符。为避免复制同一个无 staff 休止符造成
  重复时值，本项不做无效代码改动。

验证：

- 红灯测试：2 failed（非标准 `quarter=108`、同位置首个力度错误胜出）。
- metronome、同位置力度与多谱表补齐休止符核心回归：3 passed。
- convert、Jianpu、render、export、provenance、架构组合回归：207 passed。
- Ruff 格式化与静态检查：通过。
- 随机临时数据根下后端全量测试：376 passed，1 skipped。

未发现本工作包引入的新问题。

### 5.3 简谱文本生成缺陷组

完成日期：2026-07-03

实际修改：

- 锚点扫描找不到当前事件 token 时，不再把游标留在原位；会按该事件实际输出的
  力度、演奏标记、滑音和音符 token 数跳过一个完整逻辑事件，避免后续相同音级
  被错误归给前一 source id。
- 连音组内部 token 定位失败时直接越过完整 `$...$` 区间，不继续在同组内猜测；
  这遵循“宁可缺失异常锚点，也不能生成错误锚点”的 provenance 安全原则。
- `tuplet_id=None` 时使用声明的 `tuplet_count` 作为严格上界，并在遇到其他具名
  tuplet 时停止；不会再因条件恒假吞掉小节剩余普通音符。
- `_accidental_span()` 后缀匹配扩展为 `bb|x|#|b`，双降和重升范围覆盖完整两个或
  一个字符，不再只锚定最后一个 `b` 或完全漏掉 `x`。

验证：

- 红灯测试：3 failed（后续锚点错位、无 id 连音吞小节、双变音范围错误）。
- 三项核心回归：3 passed。
- provenance、Jianpu、convert、render、架构组合回归：205 passed。
- Ruff 格式化与静态检查：通过。
- 随机临时数据根下后端全量测试：379 passed，1 skipped。

未发现本工作包引入的新问题。

## 待处理

按上方“后续修复报告”以及详细执行方案依次处理。当前是用户指定的停点，没有后续
工作包处于进行中。恢复后的优先级：

1. 6.2 TypeScript 类型安全。
2. 6.3 错误处理缺失。
3. 6.4 播放器正确性。
4. 6.5 SVG 预览稳定性。
5. 7.1–9.3 按依赖顺序执行：先去重/边界，再拆分，再测试与 CI，最后文档总核验。

## 新发现问题

本轮实际发现并已闭环的回归：

- 4.6 XML 安全加固误拒绝 Audiveris 标准 MusicXML `PUBLIC DOCTYPE`，导致真实 `.mxl`
  识别结果无法读取。已作为 4.6a 修复：只在 MusicXML 边界接受并剥离严格匹配的标准
  声明，危险 DTD/ENTITY 继续拒绝；不存在未关闭的后续问题。

以下是制定方案时对审计报告的复核结果，尚未计为新增缺陷：

- 1.3 不能简单把单附点 `if` 改成 `while`，否则第二个附点会按累计值计算。
- 1.4 当前订阅队列无界，`QueueFull` 分支实际不可达，但删除操作仍需改成幂等。
- 5.4 `@text` 有现有测试明确要求忽略，属于旧语法兼容策略，不应直接恢复。
- 6.1 中两个所谓“模块级共享状态”位于 Vue `<script setup>`，实际是实例局部状态。
- 7.4 OCR client 中 `ocr_prompt_for_model()` 仍有调用者，不能整文件删除。
- 缓存清理与尚未写入历史记录的当前工作区文件之间仍缺少显式租约。1.1 已保证所有
  历史引用安全，但“用户在上传完成后、历史落库前立即清缓存”的产品语义需要在并发
  工作包中增加 active upload lease，不能把普通索引项永久当作历史引用。
- renderer 会把超过一拍的音符拆成拍内 RenderItem，`_note_body_token()` 会丢失原
  附点并用延长占位表现持续时间。因此普通 `5..` 的时值和文本往返已正确，但 SVG
  仍可能不显示原附点；已排入 5.4 渲染布局工作包，需区分“视觉记谱 token”和
  “跨拍布局占位”。
- 全量测试持续出现 Starlette 关于 `httpx` TestClient 的弃用警告；排入依赖/测试
  基础设施工作包，升级前需核对 FastAPI/Starlette 兼容组合。
- 6.1 清理 JianpuEditor 的自动格式化 watcher 后，`splitInlineComment` 变成未使用
  函数；已在 6.1 内删除并重跑 lint，未形成开放缺陷。
- 8.3 原审计数字已经过时：FastAPI 越层导入豁免已清零，但架构测试仍保留 5 个
  exec→domain 的 `KNOWN_LAYER_VIOLATIONS`，后续以当前清单为准。
- 8.1/9.3 所称 MuseScore CLI 与当前实现不符；仓库没有该集成，后续测试和文档应
  覆盖真实的 PyMuPDF、mido 和浏览器 Canvas 能力。

## 验证记录

| 日期 | 工作包 | 命令 | 结果 |
|---|---|---|---|
| 2026-07-03 | 实施前基线 | `.venv/Scripts/python.exe -m pytest -q` | 266 passed，1 skipped |
| 2026-07-03 | 实施前基线 | `pnpm lint && pnpm typecheck && pnpm test:utils && pnpm check:api-types` | 全部通过；ESLint 1 warning |
| 2026-07-03 | 1.1 红灯测试 | `.venv/Scripts/python.exe -m pytest tests/test_cache_service.py -q` | 2 failed（预期） |
| 2026-07-03 | 1.1 专项回归 | `.venv/Scripts/python.exe -m pytest tests/test_cache_service.py tests/test_uploads.py tests/test_history_service.py tests/test_architecture.py -q` | 36 passed |
| 2026-07-03 | 1.1 全量回归 | `.venv/Scripts/python.exe -m pytest -q` | 267 passed，1 skipped |
| 2026-07-03 | 5.6a 红灯测试 | `.venv/Scripts/python.exe -m pytest tests/test_history_service.py -q -k legacy_history` | 2 failed（预期） |
| 2026-07-03 | 5.6a 专项回归 | `.venv/Scripts/python.exe -m pytest tests/test_history_service.py tests/test_cache_service.py tests/test_uploads.py tests/test_architecture.py -q` | 38 passed |
| 2026-07-03 | 5.6a 全量回归 | `.venv/Scripts/python.exe -m pytest -q` | 269 passed，1 skipped |
| 2026-07-03 | 1.2/1.3 红灯测试 | `.venv/Scripts/python.exe -m pytest tests/test_jianpu.py -q -k "duration_affixes or multiple_dots or extensions_are_added"` | 10 failed、6 passed（预期） |
| 2026-07-03 | 1.2/1.3 Jianpu 专项 | `.venv/Scripts/python.exe -m pytest tests/test_jianpu.py -q` | 62 passed |
| 2026-07-03 | 1.2/1.3 render 专项 | `.venv/Scripts/python.exe -m pytest tests/test_render.py -q` | 71 passed |
| 2026-07-03 | 1.2/1.3 全量回归 | `.venv/Scripts/python.exe -m pytest -q` | 286 passed，1 skipped |
| 2026-07-03 | 1.5 红灯测试 | `.venv/Scripts/python.exe -m pytest tests/test_pipeline.py tests/test_api_routes.py -q -k "empty_render or partial_outputs or render_error"` | 2 个模块收集失败（预期：`RenderError` 尚不存在） |
| 2026-07-03 | 1.5 核心回归 | 同上 | 3 passed |
| 2026-07-03 | 1.5 组合回归 | `.venv/Scripts/python.exe -m pytest tests/test_pipeline.py tests/test_api_routes.py tests/test_tasks.py tests/test_architecture.py -q` | 43 passed |
| 2026-07-03 | 1.5 全量回归 | `.venv/Scripts/python.exe -m pytest -q` | 289 passed，1 skipped |
| 2026-07-03 | 1.6 红灯测试 | `.venv/Scripts/python.exe -m pytest tests/test_ai_transcription.py -q -k "orphan_user or committed_atomically"` | 3 failed（预期） |
| 2026-07-03 | 1.6 AI chat 回归 | `.venv/Scripts/python.exe -m pytest tests/test_ai_transcription.py -q -k "ai_chat"` | 7 passed |
| 2026-07-03 | 1.6 组合回归 | `.venv/Scripts/python.exe -m pytest tests/test_ai_transcription.py tests/test_architecture.py -q` | 21 passed |
| 2026-07-03 | 1.6 全量回归 | `.venv/Scripts/python.exe -m pytest -q` | 292 passed，1 skipped |
| 2026-07-03 | 1.8 红灯测试 | `.venv/Scripts/python.exe -m pytest tests/test_tasks.py -q -k "shutdown or rejects_registration"` | 旧实现进入热循环，外层命令超时（预期复现） |
| 2026-07-03 | 1.8 核心回归 | 同上 | 2 passed |
| 2026-07-03 | 1.8 组合回归 | `.venv/Scripts/python.exe -m pytest tests/test_tasks.py tests/test_api_routes.py tests/test_architecture.py -q` | 38 passed |
| 2026-07-03 | 1.8 全量回归 | `.venv/Scripts/python.exe -m pytest -q` | 294 passed，1 skipped |
| 2026-07-03 | 1.9 红灯测试 | 后端路径专项 + `pnpm test:utils` | 后端收集失败、Node 模块缺失（预期） |
| 2026-07-03 | 1.9 后端专项 | `pytest tests/test_user_data_paths.py tests/test_architecture.py -q`（临时数据根） | 9 passed |
| 2026-07-03 | 1.9 前端门禁 | `pnpm test:utils && pnpm lint && pnpm typecheck && pnpm build` | 41 passed、1 skipped；lint 仅既有 1 warning；其余通过 |
| 2026-07-03 | 1.9 全量回归 | `pytest -q`（随机临时 `SCORE_TRANS_DATA_DIR`） | 299 passed，1 skipped |
| 2026-07-03 | 1.10 红灯测试 | `pytest tests/test_ai_transcription.py -q -k "pdf_to_png_pages"` | 2 failed、1 passed（预期） |
| 2026-07-03 | 1.10 专项回归 | 同上 | 3 passed |
| 2026-07-03 | 1.10 组合回归 | `pytest tests/test_ai_transcription.py tests/test_architecture.py -q` | 23 passed |
| 2026-07-03 | 1.10 全量回归 | `pytest -q`（随机临时 `SCORE_TRANS_DATA_DIR`） | 301 passed，1 skipped |
| 2026-07-03 | 1.4 红灯测试 | `pytest tests/test_tasks.py -q -k "keep_latest"` | 1 failed（预期） |
| 2026-07-03 | 1.4 TaskManager 专项 | `pytest tests/test_tasks.py -q` | 8 passed |
| 2026-07-03 | 1.4 组合回归 | `pytest tests/test_tasks.py tests/test_api_routes.py tests/test_architecture.py -q` | 39 passed |
| 2026-07-03 | 1.4 全量回归 | `pytest -q`（随机临时 `SCORE_TRANS_DATA_DIR`） | 302 passed，1 skipped |
| 2026-07-03 | 1.11 红灯测试 | `pytest tests/test_ai_transcription.py tests/test_ocr.py -q -k "empty_choices or usage_only"` | 3 failed（预期 `IndexError`） |
| 2026-07-03 | 1.11 核心回归 | 同上 | 3 passed |
| 2026-07-03 | 1.11 组合回归 | `pytest tests/test_ai_transcription.py tests/test_ocr.py tests/test_architecture.py -q` | 39 passed |
| 2026-07-03 | 1.11 全量回归 | `pytest -q`（随机临时 `SCORE_TRANS_DATA_DIR`） | 306 passed，1 skipped |
| 2026-07-03 | 1.12 红灯测试 | `pytest tests/test_architecture.py tests/test_render.py -q -k "runtime_validation or missing_endpoints"` | 4 failed（预期） |
| 2026-07-03 | 1.12 核心回归 | 同上 | 4 passed |
| 2026-07-03 | 1.12 组合回归 | `pytest tests/test_render.py tests/test_convert.py tests/test_architecture.py -q` | 89 passed |
| 2026-07-03 | 1.12 优化模式 | `python -O -c "..._render_tie_arc(None, None, 100)..."` | `optimized-validation-ok` |
| 2026-07-03 | 1.12 全量回归 | `pytest -q`（随机临时 `SCORE_TRANS_DATA_DIR`） | 310 passed，1 skipped |
| 2026-07-03 | 2.1–2.3 红灯测试 | `pytest tests/test_convert.py -q -k "double_accidentals or accidental_direction or scale_boundary"` | 3 failed（预期） |
| 2026-07-03 | 2.1–2.3 核心组合 | `pytest tests/test_convert.py tests/test_jianpu.py tests/test_render.py tests/test_architecture.py -q` | 155 passed |
| 2026-07-03 | 2.1–2.3 provenance 组合 | `pytest tests/test_provenance.py tests/test_convert.py tests/test_jianpu.py tests/test_render.py tests/test_architecture.py -q` | 166 passed |
| 2026-07-03 | 2.1–2.3 全量回归 | `pytest -q`（随机临时 `SCORE_TRANS_DATA_DIR`） | 314 passed，1 skipped |
| 2026-07-03 | 2.4–2.5 红灯测试 | `pytest tests/test_convert.py -q -k "repeat_endings or repeat_flags"` | 2 failed（预期） |
| 2026-07-03 | 2.4–2.5 专项回归 | 同上 | 2 passed |
| 2026-07-03 | 2.4–2.5 组合回归 | `pytest tests/test_convert.py tests/test_jianpu.py tests/test_render.py tests/test_provenance.py tests/test_architecture.py -q` | 168 passed |
| 2026-07-03 | 2.4–2.5 全量回归 | `pytest -q`（随机临时 `SCORE_TRANS_DATA_DIR`） | 316 passed，1 skipped |
| 2026-07-03 | 2.6–2.8 红灯测试 | `pytest tests/test_convert.py tests/test_jianpu.py -q -k "nested_tuplets or continues_across or explicit_note_values"` | 3 failed（预期） |
| 2026-07-03 | 2.6–2.8 组合回归 | `pytest tests/test_convert.py tests/test_jianpu.py tests/test_render.py tests/test_provenance.py tests/test_architecture.py -q` | 171 passed |
| 2026-07-03 | 2.6–2.8 全量回归 | `pytest -q`（随机临时 `SCORE_TRANS_DATA_DIR`） | 319 passed，1 skipped |
| 2026-07-03 | 2.12–2.13 红灯测试 | `pytest tests/test_render.py tests/test_jianpu.py tests/test_convert.py -q -k "stack_vertically or extended_musicxml"` | 8 failed（预期） |
| 2026-07-03 | 2.12–2.13 专项回归 | 同上 | 8 passed |
| 2026-07-03 | 2.12–2.13 组合回归 | `pytest tests/test_render.py tests/test_jianpu.py tests/test_convert.py tests/test_architecture.py -q` | 168 passed |
| 2026-07-03 | 2.12–2.13 全量回归 | `pytest -q`（随机临时 `SCORE_TRANS_DATA_DIR`） | 327 passed，1 skipped |
| 2026-07-03 | 2.10 红灯测试 | `pytest tests/test_convert.py -q -k "title_and_tempo or direction_kinds"` | 2 failed（预期） |
| 2026-07-03 | 2.10 专项回归 | `pytest tests/test_convert.py -q -k "title_and_tempo or direction_kinds or direction_metadata"` | 3 passed |
| 2026-07-03 | 2.10 组合回归 | `pytest tests/test_convert.py tests/test_jianpu.py tests/test_architecture.py -q` | 96 passed |
| 2026-07-03 | 2.10 全量回归 | `pytest -q`（临时 `SCORE_TRANS_DATA_DIR`） | 330 passed，1 skipped |
| 2026-07-03 | 2.10 前端契约 | `pnpm check:api-types && pnpm exec vue-tsc --noEmit && pnpm lint` | 通过；ESLint 保留既有 1 warning |
| 2026-07-03 | 2.9 红灯测试 | `pytest tests/test_convert.py -q -k "multivoice_timeline or single_voice_compatible"` | 2 failed（预期） |
| 2026-07-03 | 2.9 专项回归 | 同上 | 2 passed |
| 2026-07-03 | 2.9 组合回归 | `pytest tests/test_convert.py tests/test_jianpu.py tests/test_render.py tests/test_provenance.py tests/test_architecture.py -q` | 184 passed |
| 2026-07-03 | 2.9 全量回归 | `pytest -q`（临时 `SCORE_TRANS_DATA_DIR`） | 332 passed，1 skipped |
| 2026-07-03 | 2.11 红灯测试 | `pytest tests/test_convert.py tests/test_render.py tests/test_export.py -q -k "microtonal or microtones"` | 3 failed（预期） |
| 2026-07-03 | 2.11 专项回归 | 同上 | 3 passed |
| 2026-07-03 | 2.11 组合回归 | `pytest tests/test_convert.py tests/test_jianpu.py tests/test_render.py tests/test_export.py tests/test_provenance.py tests/test_architecture.py -q` | 191 passed |
| 2026-07-03 | 2.11 全量回归 | `pytest -q`（临时 `SCORE_TRANS_DATA_DIR`） | 335 passed，1 skipped |
| 2026-07-03 | 2.11 前端回归 | `pnpm lint && pnpm typecheck && pnpm test:utils && pnpm build` | 通过；ESLint 1 warning，工具测试 41 passed、1 skipped |
| 2026-07-03 | 3.1 红灯测试 | `pytest tests/test_architecture.py -q -k "models_and_dao_do_not_import_config"` | 1 failed，列出 3 个违规文件（预期） |
| 2026-07-03 | 3.1 组合回归 | `pytest tests/test_architecture.py tests/test_ai_transcription.py tests/test_settings_providers.py tests/test_api_routes.py -q` | 62 passed，1 skipped |
| 2026-07-03 | 3.1 前端契约 | `pnpm check:api-types && pnpm typecheck && pnpm lint` | 通过；ESLint 保留既有 1 warning |
| 2026-07-03 | 3.1 全量回归 | `pytest -q`（临时 `SCORE_TRANS_DATA_DIR`） | 339 passed，1 skipped |
| 2026-07-03 | 3.2 红灯测试 | `pytest tests/test_architecture.py -q -k "fastapi_is_only"` | 1 failed，列出 7 个违规文件（预期） |
| 2026-07-03 | 3.2 组合回归 | `pytest tests/test_architecture.py tests/test_api_routes.py tests/test_render.py tests/test_export.py tests/test_history_service.py tests/test_pipeline.py tests/test_ocr.py -q` | 158 passed |
| 2026-07-03 | 3.2 全量回归 | `pytest -q`（临时 `SCORE_TRANS_DATA_DIR`） | 340 passed，1 skipped |
| 2026-07-03 | 3.3 红灯测试 | `pytest tests/test_api_routes.py -q -k "export_route_offloads or clear_cache_route_offloads"` | 2 failed，事件循环各阻塞约 200ms（预期） |
| 2026-07-03 | 3.3 专项回归 | `pytest tests/test_api_routes.py -q -k "route_offloads or clear_cache_route_offloads"` | 3 passed |
| 2026-07-03 | 3.3 组合回归 | `pytest tests/test_architecture.py tests/test_api_routes.py tests/test_export.py tests/test_ai_transcription.py tests/test_settings_providers.py tests/test_cache_service.py -q` | 73 passed，1 skipped |
| 2026-07-03 | 3.3 全量回归 | `pytest -q`（临时 `SCORE_TRANS_DATA_DIR`） | 343 passed，1 skipped |
| 2026-07-03 | 3.4 红灯测试 | `pytest tests/test_architecture.py -q -k "utils_do_not_import_config"` | 1 failed，列出 2 个反向依赖（预期） |
| 2026-07-03 | 3.4 组合回归 | `pytest tests/test_architecture.py tests/test_user_data_paths.py tests/test_ocr.py tests/test_ai_transcription.py -q` | 51 passed |
| 2026-07-03 | 3.4 全量回归 | `pytest -q`（临时 `SCORE_TRANS_DATA_DIR`） | 345 passed，1 skipped |
| 2026-07-03 | 4.1 红灯测试 | `pytest tests/test_api_auth.py -q` | 5 failed（预期：应用工厂无认证参数） |
| 2026-07-03 | 4.1 认证专项 | 同上 | 5 passed |
| 2026-07-03 | 4.1 组合回归 | `pytest tests/test_api_auth.py tests/test_api_routes.py tests/test_tasks.py tests/test_uploads.py tests/test_architecture.py -q` | 60 passed |
| 2026-07-03 | 4.1 真实进程 | 随机端口启动 uvicorn 后请求 health/settings | 200 / 401 / 401 / 200 |
| 2026-07-03 | 4.1 前端门禁 | `pnpm test:utils && pnpm typecheck && pnpm lint && pnpm check:api-types && pnpm build` | 全部通过；41 passed、1 skipped，ESLint 1 warning |
| 2026-07-03 | 4.1 全量回归 | `pytest -q`（临时 `SCORE_TRANS_DATA_DIR`） | 351 passed，1 skipped |
| 2026-07-03 | 4.2 红灯测试 | `pnpm test:utils` | 新安全模块不存在（预期） |
| 2026-07-03 | 4.2 前端门禁 | `pnpm test:utils && pnpm typecheck && pnpm lint && pnpm build` | 44 passed、1 skipped；其余通过，ESLint 1 warning |
| 2026-07-03 | 4.3 红灯测试 | `node --test scripts/test-main-file-security.mjs` | 路径安全模块不存在（预期） |
| 2026-07-03 | 4.3 路径专项 | 同上 | 6 passed |
| 2026-07-03 | 4.3 前端门禁 | `pnpm test:utils && pnpm typecheck && pnpm lint && pnpm build` | 47 passed、1 skipped；其余通过，ESLint 1 warning |
| 2026-07-03 | 4.5 红灯测试 | `node --test scripts/test-svg-sanitizer.mjs` | sanitizer 模块不存在（预期） |
| 2026-07-03 | 4.5 浏览器安全实测 | `pnpm exec electron scripts/test-svg-sanitizer-electron.cjs` | 通过 |
| 2026-07-03 | 4.5 前端门禁 | `pnpm test:utils && pnpm typecheck && pnpm lint && pnpm build` | 50 passed、1 skipped；其余通过，ESLint 仅 AI Markdown 1 warning |
| 2026-07-03 | 4.6 红灯测试 | `pytest tests/test_safe_xml.py tests/test_architecture.py -q -k "safe_xml or bounded_safe_parser"` | 安全解析模块不存在，收集失败（预期） |
| 2026-07-03 | 4.6 组合回归 | `pytest tests/test_safe_xml.py tests/test_architecture.py tests/test_convert.py tests/test_recognize_external_tools.py tests/test_overlay.py tests/test_render.py -q`（临时数据根） | 137 passed |
| 2026-07-03 | 4.6 全量回归 | `pytest -q`（随机临时 `SCORE_TRANS_DATA_DIR`） | 359 passed，1 skipped |
| 2026-07-03 | 4.7 红灯测试 | `pytest tests/test_upload_limits.py -q` | 请求限制模块不存在，收集失败（预期） |
| 2026-07-03 | 4.7 核心回归 | `pytest tests/test_upload_limits.py -q`（临时数据根） | 6 passed |
| 2026-07-03 | 4.7 组合回归 | `pytest tests/test_upload_limits.py tests/test_uploads.py tests/test_api_routes.py tests/test_pipeline.py tests/test_recognize_external_tools.py tests/test_export.py tests/test_api_auth.py tests/test_architecture.py -q`（临时数据根） | 77 passed |
| 2026-07-03 | 4.7 全量回归 | `pytest -q`（随机临时 `SCORE_TRANS_DATA_DIR`） | 366 passed，1 skipped |
| 2026-07-03 | 5.1 红灯测试 | `pytest tests/test_jianpu.py -q -k "single_dotted_note_line or unknown_performance_marks or compact_tuplet_supports_chords or underfilled_measure or second_key_declaration or postfix_double_accidentals"` | 8 failed（预期） |
| 2026-07-03 | 5.1 Jianpu 专项 | `pytest tests/test_jianpu.py -q`（临时数据根） | 78 passed |
| 2026-07-03 | 5.1 组合回归 | `pytest tests/test_jianpu.py tests/test_convert.py tests/test_render.py tests/test_ai_transcription.py tests/test_provenance.py tests/test_architecture.py -q`（临时数据根） | 225 passed |
| 2026-07-03 | 5.1 全量回归 | `pytest -q`（随机临时 `SCORE_TRANS_DATA_DIR`） | 375 passed，1 skipped |
| 2026-07-03 | 5.2 红灯测试 | `pytest tests/test_convert.py -q -k "direction_metadata_roundtrips or same_cursor_dynamics"` | 2 failed（预期） |
| 2026-07-03 | 5.2 核心回归 | `pytest tests/test_convert.py -q -k "direction_metadata_roundtrips or same_cursor_dynamics or split_multi_staff"` | 3 passed |
| 2026-07-03 | 5.2 组合回归 | `pytest tests/test_convert.py tests/test_jianpu.py tests/test_render.py tests/test_export.py tests/test_provenance.py tests/test_architecture.py -q`（临时数据根） | 207 passed |
| 2026-07-03 | 5.2 全量回归 | `pytest -q`（随机临时 `SCORE_TRANS_DATA_DIR`） | 376 passed，1 skipped |
| 2026-07-03 | 5.3 红灯测试 | `pytest tests/test_provenance.py -q -k "missing_anchor_token or tuplet_without_id or accidental_span_supports"` | 3 failed（预期） |
| 2026-07-03 | 5.3 核心回归 | 同上 | 3 passed |
| 2026-07-03 | 5.3 组合回归 | `pytest tests/test_provenance.py tests/test_jianpu.py tests/test_convert.py tests/test_render.py tests/test_architecture.py -q`（临时数据根） | 205 passed |
| 2026-07-03 | 5.3 全量回归 | `pytest -q`（随机临时 `SCORE_TRANS_DATA_DIR`） | 379 passed，1 skipped |
| 2026-07-03 | 5.4 分项红灯 | 多分谱范围、非 4/4、文本边界/角色、小节线、死代码定向测试 | 均在旧实现上按预期失败 |
| 2026-07-03 | 5.4 渲染专项 | `pytest tests/test_render.py -q`（临时数据根） | 83 passed |
| 2026-07-03 | 5.4 Ruff | `ruff format --check` + `ruff check`（render + test_render） | 通过 |
| 2026-07-03 | 5.4 全量回归 | `pytest -q`（随机临时 `SCORE_TRANS_DATA_DIR`） | 386 passed，1 skipped |
| 2026-07-03 | 5.5 前端红灯 | `pnpm test:utils` | 1 failed、50 passed、1 skipped（预期） |
| 2026-07-03 | 5.5 组合回归 | `pytest tests/test_ocr.py tests/test_ai_transcription.py tests/test_settings_providers.py tests/test_architecture.py -q`（临时数据根） | 62 passed，1 skipped |
| 2026-07-03 | 5.5 前端门禁 | `pnpm test:utils && pnpm typecheck && pnpm lint && pnpm check:api-types && pnpm build` | 51 passed、1 skipped；其余通过，ESLint 1 warning |
| 2026-07-03 | 5.5 Ruff | `ruff format --check` + `ruff check`（本工作包 Python 文件） | 通过 |
| 2026-07-03 | 5.5 全量回归 | `pytest -q`（随机临时 `SCORE_TRANS_DATA_DIR`） | 395 passed，1 skipped |
| 2026-07-03 | 5.6 分项红灯 | N+1、显式 NULL、ALTER 回滚、chat 锁、任务恢复/枚举定向测试 | 7 项均按预期失败 |
| 2026-07-03 | 5.6 组合回归 | `pytest tests/test_history_service.py tests/test_ai_transcription.py tests/test_tasks.py tests/test_api_routes.py tests/test_architecture.py -q`（临时数据根） | 109 passed |
| 2026-07-03 | 5.6 Ruff/API 契约 | `ruff format --check` + `ruff check` + `pnpm check:api-types` | 通过 |
| 2026-07-03 | 5.6 全量回归 | `pytest -q`（随机临时 `SCORE_TRANS_DATA_DIR`） | 402 passed，1 skipped |
| 2026-07-03 | 5.7 红灯/复核 | `pytest tests/test_settings_providers.py -q` | 9 failed；`"0"` 项直接通过 |
| 2026-07-03 | 5.7 组合回归 | `pytest tests/test_settings_providers.py tests/test_api_routes.py tests/test_ai_transcription.py tests/test_ocr.py tests/test_architecture.py -q`（临时数据根） | 103 passed，1 skipped |
| 2026-07-03 | 5.7 前端门禁 | `pnpm check:api-types && pnpm typecheck && pnpm lint && pnpm build` | 通过；ESLint 1 warning |
| 2026-07-03 | 5.7 全量回归 | `pytest -q`（随机临时 `SCORE_TRANS_DATA_DIR`） | 411 passed，1 skipped |
| 2026-07-04 | 5.8 红灯测试 | `node --test scripts/test-backend-lifecycle.mjs` | 4 failed（预期） |
| 2026-07-04 | 5.8 生命周期专项 | 同上 | 4 passed，含真实子进程 |
| 2026-07-04 | 5.8 前端门禁 | `pnpm test:utils && pnpm typecheck && pnpm lint && pnpm build && pnpm check:api-types` | 55 passed、1 skipped；其余通过，ESLint 1 warning |
| 2026-07-04 | 6.1 红灯/复核 | `node --test scripts/test-frontend-lifecycle.mjs` | 6 failed、1 passed；通过项确认两个 `<script setup>` 共享状态报告不成立 |
| 2026-07-04 | 6.1 响应性专项 | 同上 | 7 passed |
| 2026-07-04 | 6.1 前端工具全量 | `pnpm test:utils` | 62 passed、1 skipped |
| 2026-07-04 | 6.1 类型门禁 | `pnpm typecheck` | 通过 |
| 2026-07-04 | 6.1 静态门禁 | `pnpm lint` | 0 error；仅既有 `AiAssistant.vue` `vue/no-v-html` warning |
| 2026-07-04 | 6.1 生产构建 | `pnpm build` | main、preload、renderer 全部构建通过 |
| 2026-07-04 | 4.6a 真实故障复现 | 读取用户任务的两个 Audiveris `.mxl` | 两个文件均复现相同 `UnsafeXmlError` |
| 2026-07-04 | 4.6a 红灯测试 | `pytest tests/test_safe_xml.py -q`（修复前） | 1 failed、10 passed；标准 MusicXML DOCTYPE 按预期失败 |
| 2026-07-04 | 4.6a XML 专项 | `pytest tests/test_safe_xml.py -q` | 11 passed |
| 2026-07-04 | 4.6a 真实文件回归 | `read_musicxml_text` + `musicxml_path_to_scores` | 两页成功；31 / 41 小节 |
| 2026-07-04 | 4.6a 组合回归 | `pytest tests/test_safe_xml.py tests/test_architecture.py tests/test_convert.py tests/test_recognize_external_tools.py tests/test_overlay.py tests/test_render.py -q`（随机临时数据根） | 150 passed |
| 2026-07-04 | 4.6a Ruff | `ruff format` + `ruff check`（本工作包文件） | 通过 |
| 2026-07-04 | 4.6a 后端全量 | `pytest -q`（随机临时 `SCORE_TRANS_DATA_DIR`） | 415 passed、1 skipped、1 个既有 warning |

## 变更日志

### 2026-07-04

- 完成工作包 5.8“Electron / IPC 缺陷组”，加入类型化异步连接与有界后端进程树清理。
- 完成工作包 6.1“Vue 响应性与生命周期”；10 个审计子项逐项修复或证伪。
- 清理 6.1 产生的 JianpuEditor 未使用函数，最终 lint 未新增 warning。
- 前端工具测试基线更新为 62 passed、1 skipped。
- 按用户要求停在 6.2 开始前，没有修改 6.2 或后续代码。
- 完善 6.2–9.3 后续修复报告，补充每包现状、实施方案、验收门禁和主要风险。
- 收到真实识别失败报告后完成 4.6a：恢复 Audiveris 标准 MusicXML DOCTYPE 兼容，
  同时保持内部实体和非标准 DTD 拒绝策略。
- 用用户刚失败的两页 `.mxl` 完成真实回归，并将后端基线更新为
  415 passed、1 skipped。

### 2026-07-03

- 建立持续更新的审计修复台账。
- 完成工作包 1.1“缓存清理引用保护”。
- 记录 active upload lease 的新增并发风险，排入后续并发工作包。
- 完成工作包 5.6a“旧 history 表无损迁移”。
- 完成工作包 1.2/1.3“时值往返与双附点”。
- 记录跨拍长附点音符的 SVG 视觉语义问题和 TestClient 弃用警告。
- 完成工作包 1.5“pipeline 空渲染页面”，未发现新的独立缺陷。
- 完成工作包 1.6“AI 对话流式失败原子持久化”，并同步修复非流式同源缺陷。
- 完成工作包 1.8“应用关闭任务收敛”，确认审计问题会造成不可中断的热循环。
- 完成工作包 1.9“`.sorce_trans` → `.score_trans` 用户数据目录迁移”。
- 完成工作包 1.10“PDF max_pages=0 语义修复”。
- 完成工作包 1.4“TaskManager 订阅者幂等移除”，并补上真实背压策略。
- 完成工作包 1.11“AI / OCR 流式空 choices”，统一两端响应校验。
- 完成工作包 1.12“运行时 assert”；第 1 章全部有效问题结案。
- 完成工作包 2.1–2.3“双变音与等音拼写”，并修复跨调内 B/C 的八度错误。
- 完成工作包 2.4–2.5“重复记号往返”，并保留 print 分页/换行标记。
- 完成工作包 2.6–2.8“连音结构与时值”，记录文本语法的单层兼容边界。
- 完成工作包 2.12–2.13“八度点与力度词汇”。
- 启动工作包 2.10“标题、速度与方向输出”。
- 完成工作包 2.10“标题、速度与方向输出”，同步刷新前端 OpenAPI 类型。
- 启动工作包 2.9“多声部 MusicXML”。
- 完成工作包 2.9“多声部 MusicXML”，同时保留单声部输出兼容。
- 启动工作包 2.11“微音程信息”。
- 完成工作包 2.11“微音程信息”；第 2 章全部结案。
- 启动工作包 3.1“models 层反向导入 config”。
- 完成工作包 3.1“models / DAO 反向导入 config”，同步强化 OpenAPI 响应类型。
- 启动工作包 3.2“exec 层 HTTPException”，按当前 7 个违规文件而非旧报告 3 个样本处理。
- 完成工作包 3.2“exec 层 HTTPException / FastAPI 越层依赖”，删除全部 7 项豁免。
- 启动工作包 3.3“API 异步路由同步阻塞”。
- 完成工作包 3.3“API 异步路由同步阻塞”，覆盖 export/settings/files/AI 会话。
- 启动工作包 3.4“config / utils 循环导入”。
- 完成工作包 3.4“config / utils 循环导入”；第 3 章全部结案。
- 启动工作包 4.1“API 认证与授权边界”。
- 完成工作包 4.1“API 认证与授权边界”，所有本地 API 与流式/文件传输统一鉴权。
- 启动工作包 4.2“Electron 主进程 SSRF”。
- 完成工作包 4.2“Electron 主进程 SSRF”，主进程导出 IPC 移除全部网络能力。
- 启动工作包 4.3“导出路径遍历”。
- 完成工作包 4.3“导出路径遍历”，加入 canonical containment、重解析点拒绝和原子写入。
- 4.4 经审计报告复查已确认不成立，不实施无效改动。
- 启动工作包 4.5“SVG v-html 防御纵深”。
- 完成工作包 4.5“SVG v-html 防御纵深”，改为严格白名单 DOM 挂载并完成 Electron 恶意样例实测。
- 启动工作包 4.6“XML 炸弹”。
- 完成工作包 4.6“XML 炸弹”，统一收紧 MusicXML、MXL、OMR 与 SVG XML 解析入口。
- 启动工作包 4.7“文件上传大小限制”。
- 完成工作包 4.7“文件上传大小限制”；第 4 章全部有效安全问题结案。
- 启动工作包 5.1“简谱文本解析缺陷组”。
- 完成工作包 5.1“简谱文本解析缺陷组”，并补齐已公开紧贴演奏标记语法。
- 启动工作包 5.2“MusicXML 解析缺陷组”。
- 完成工作包 5.2“MusicXML 解析缺陷组”；多谱表 generated rest 项确认当前实现已闭环。
- 启动工作包 5.3“简谱文本生成缺陷组”。
- 完成工作包 5.3“简谱文本生成缺陷组”，锚点失败改为保守跳过而非错误重绑定。
- 启动工作包 5.4“渲染服务缺陷组”。
- 完成工作包 5.4“渲染服务缺陷组”；旧 `@text` 确认为弃用兼容语法，其余七项
  完成实现修复或死代码清理。
- 启动工作包 5.5“AI / OCR 服务缺陷组”。
- 完成工作包 5.5“AI / OCR 服务缺陷组”，六项缺陷全部建立回归并通过全量门禁。
- 启动工作包 5.6“数据持久化缺陷组”；5.6.1 已提前完成，继续处理其余六项。
- 完成工作包 5.6“数据持久化缺陷组”，查询、迁移、SQLite 并发与任务恢复全部闭环。
- 启动工作包 5.7“设置系统缺陷组”。
- 完成工作包 5.7“设置系统缺陷组”；字符串 `"0"` 项确认不成立，其余缺陷闭环。
- 启动工作包 5.8“Electron / IPC 缺陷组”。
- 完成工作包 5.8“Electron / IPC 缺陷组”；第 5 章全部结案。
- 启动工作包 6.1“Vue 响应性与生命周期”。
