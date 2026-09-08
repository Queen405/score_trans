# Score Trans 大文件拆分调研与实施方案

调研日期：2026-09-08。代码基线：`6c8bd7e`，调研开始时工作树干净。

本次只调研并新增本文档，没有实施业务代码拆分。以下新目录、模块名和行数目标均为建议，不代表已经创建。

**自评修订：2026-09-08。** 重新核对了渲染器和解析器的函数调用关系、转换页的导出/恢复链路、DAO 事务及测试加载方式。结论是拆分方向成立，但初版的模块数量和实施顺序偏激进。本文已收缩首轮范围；第 3–5 节列出的完整职责图属于可选目标，不能直接解释成需要全部创建的文件清单。详细修正依据见第 8 节。

## 1. 结论与统计口径

项目已有清晰的后端分层、前端 API 适配器、领域模型、渲染 scene 和部分组合函数，适合在现有结构内渐进拆分，无需更换框架。

统计使用 Git Bash、项目 `.venv` 中的 Python 3.13.5、`git ls-files` 和 Python AST；行数按 UTF-8 文本的物理行统计，包含注释、空行及 Vue 模板/样式。范围是 Git 跟踪的项目自有文件，排除 `third_party/`、依赖目录、构建输出和二进制资源。未跟踪文件及第三方内部大文件不属于本次重构范围。

共统计到 408 个 `.py/.ts/.tsx/.js/.mjs/.cjs/.vue/.css/.scss/.html` 文件，其中 backend 245 个、desktop 119 个、tests 44 个。超过 1000 行的代码文件有 19 个：**13 个手写业务文件、5 个测试文件、1 个自动生成文件**。

文件长度只是筛选条件。优先拆分的是职责混杂、独立变化频繁、依赖复杂的文件；不能仅通过搬走样式或制造大量小包装函数衡量维护性改善。

## 2. 超过千行的手写业务文件

“优先级”表示值得优先投入的程度，并非要求立即修改最高风险模块。实际实施顺序见第 7 节。

| 文件 | 行数 | 优先级 | 当前主要职责 |
|---|---:|---|---|
| [ConvertView.vue](../desktop/src/renderer/src/views/ConvertView.vue) | 2873 | 高 | 编辑同步、历史列表/恢复/重排、导出、最终排版、来源定位、实体修正、快照 |
| [renderer.py](../backend/score_trans/services/render/engraving/renderer.py) | 2790 | 高 | 间距计算、分行分页、场景构建、音符与符杠绘制、跨行连线、文本及文件输出 |
| [parse/jianpu_text.py](../backend/score_trans/domain/parse/jianpu_text.py) | 2336 | 高 | 文档分段、词法读取、单谱状态机、连音解析、演奏标记、诊断与定位 |
| [RecognizeView.vue](../desktop/src/renderer/src/views/RecognizeView.vue) | 2166 | 高 | 页面选择、上传预览、OMR/AI 任务、SSE/任务恢复、历史写回、批次渲染 |
| [parse/musicxml.py](../backend/score_trans/domain/parse/musicxml.py) | 1551 | 中 | 文件入口、多谱表拆分、小节时间线、音符/记号解析、连音恢复、来源标记 |
| [workspace.ts](../desktop/src/renderer/src/stores/workspace.ts) | 1369 | 高 | 当前页镜像、页面/批次、渲染产物、OCR、修订与未保存状态、后台任务 |
| [AiAssistant.vue](../desktop/src/renderer/src/components/AiAssistant.vue) | 1368 | 中 | 聊天界面、拖拽吸附、展开动画、消息滚动、Markdown/思考内容展示 |
| [exec/render/actions.py](../backend/score_trans/exec/render/actions.py) | 1290 | 高 | 渲染请求编排、批量多声部渲染、OCR 放置、来源范围、小节编号、产物注册 |
| [App.vue](../desktop/src/renderer/src/App.vue) | 1281 | 中 | 应用外壳、导航、主题、窗口控制、更新状态、关闭前保存与设置离开确认 |
| [history_dao.py](../backend/score_trans/dao/history/history_dao.py) | 1253 | 中 | SQLite 初始化/迁移/备份、批次和页面 CRUD、原子保存、快照、数据编解码 |
| [SyntaxView.vue](../desktop/src/renderer/src/views/SyntaxView.vue) | 1188 | 较低 | 语法帮助静态内容、搜索、乐器目录加载、复制交互和展示 |
| [JianpuEditor.vue](../desktop/src/renderer/src/components/JianpuEditor.vue) | 1172 | 中 | 输入与选区、语法着色、播放/错误定位、视口滚动、自动转调、页摘要 |
| [write/jianpu_text.py](../backend/score_trans/domain/write/jianpu_text.py) | 1092 | 中 | 简谱文档写出、音符/连音序列化、连线规范化、文本锚点与哈希 |

Vue 文件的组成进一步说明了拆分重点，下表不含 SFC 外层标签行：

| 文件 | template | script | style | 判断 |
|---|---:|---:|---:|---|
| ConvertView | 471 | 1892 | 502 | 首先拆业务流程，样式不是主要原因 |
| RecognizeView | 231 | 1312 | 615 | 任务控制器值得独立，页面选择与预览可另拆 |
| AiAssistant | 213 | 646 | 501 | 浮窗交互与消息展示边界明确 |
| App | 320 | 381 | 572 | 大量是 UI/主题，风险不同于同长度解析器 |
| SyntaxView | 320 | 467 | 393 | 先抽静态数据和搜索，不必引入复杂架构 |
| JianpuEditor | 124 | 651 | 389 | 优先隔离自动转调和视口生命周期 |

## 3. 后端具体拆分

### 3.1 SVG 渲染器：按布局、绘制、输出分开

依据：`PublicationRenderer` 在 110–498 行；`_event_positions` 在 1140 行；符杠绘制主要在 1790–2053 行；连线在 2083–2291 行；连音括号在 2294–2436 行；长时值拆解在 2575–2698 行。单一文件同时承担多种独立算法。

建议在现有 `services/render/engraving/` 内组织：

| 建议模块 | 迁入内容 |
|---|---|
| `layout_types.py` | `_Cell`、`_System`、`_Anchor`、`SpanLayout`、`TextLayout` 等渲染内部结构 |
| `normalization.py` | `_normalize_parts`、显示小节号分配、`_visual_events`、长音符/休止符拆解 |
| `spacing.py` | 时值弹性、最小间距、拍界间距、`_event_positions` 与碰撞约束 |
| `pagination.py` | `_build_cells`、`_break_systems`、`_best_break`、`_paginate`、系统高度 |
| `primitives.py` | `_text`、`_line`、`_circle`、公共语义属性和文本宽度帮助函数 |
| `notes.py` | `_draw_event`、`_draw_pitch`、`_draw_duration`、`_draw_marks` |
| `beams.py` | `_draw_rhythm_lines`、`_draw_rhythm_run`、`_draw_explicit_beam_level` |
| `spanners.py` | 连线状态与路由、跨系统延续、跨度 bbox/来源登记 |
| `tuplets.py` | 连音括号、嵌套 span 选择及其标注位置 |
| `annotations.py` | 页眉、谱面标题、小节文本、歌词相关布局；保持现有 geometry 负责几何测量 |
| `output.py` | SVG 和 `.render-map.json` 写盘，接收已经完成的页面产物 |
| `renderer.py` | 保留 `PublicationRenderer` 门面和系统/小节绘制编排 |

目标依赖方向为：渲染器调用布局及绘制模块；布局和绘制依赖内部类型、现有 `geometry/scene/style/fonts`；绘制模块不反向导入 renderer。已经独立的 `scene.py`、`svg_backend.py`、`geometry.py`、`mark_graphics.py` 继续复用。

实际调用并不完全符合上表按名称划分的边界，实施前必须修正：`_boundary_extra_gap/_apply_beat_boundary_gaps` 调用目前位于符杠区域的 `_is_tuplet`，应将这个事件判断放到共享事件计算模块；`_system_extra_height` 调用 `_measure_text_layout`，文本几何测量应与 scene 绘制分开；beams 和 tuplets 都调用 `_span_attrs`，共享跨度属性不能被连线路由模块独占。这样布局无需依赖绘制模块，也避免 beams 为几个公共属性依赖整个 spanners。

首轮只选择 visual event 拆解、公共绘制原语、符杠算法中的一个职责簇，携带它实际需要的辅助函数和类型。`write_pages` 只有 27 行，暂留原类，不为缩短文件先建立 output 包装。布局/绘制的后续细分以调用闭包为依据，不照行号分段搬运。

内部类型留在 engraving。特别是 `PublicationPage.scene` 的类型为 `PublicationScene`，不能把 PublicationPage 直接搬进 `models/render/`，否则 models 会反向依赖 services。只有不携带渲染内部对象、确实需要跨层共享的纯数据 DTO 才适合放入 models。

稳定性要求：

- `document_spanners` 当前在页面循环外、按声部创建（约 154 行），拆分后仍必须跨页面存活，不能每页重建。
- `next_note_index` 必须保持全篇连续，来源 ID、角色 ID、bbox、分页范围、`layout_key` 和 SVG 节点顺序保持一致。
- 先保留 `PublicationRenderer`、`PublicationPage`、`MeasureRange` 的原导入入口，必要时仅显式重导出公开名称。
- 不与间距算法改进、引擎版本变更或字体替换合并实施。
- 取消首轮 renderer 必须达到 300–500 行的预期。先验收职责迁出和输出等价，复杂 spacing 与绘制编排暂时较长可以接受。

### 3.2 简谱解析器：先拆词法与诊断，再处理状态机

依据：`validate_jianpu_text` 从 233 行开始，`parse_jianpu_parts` 从 800 行开始，`parse_jianpu_score` 本身有 **429 行**，`_read_new_syntax` 有 **181 行**，`_parse_tuplet_token` 有 **164 行**。仅把这些函数移动到另一文件还不足以改善单函数复杂度。

建议保留 `domain/parse/jianpu_text.py` 为公开门面，新增相邻包 `domain/parse/jianpu/`：

| 模块 | 职责与原函数 |
|---|---|
| `types.py`、`errors.py` | 解析内部 token/options、语法错误及上下文；现有跨层验证异常仍在 `models/common/errors.py` |
| `source_positions.py` | UTF-16 长度、偏移转换、行列映射，明确区分 code point 和 UTF-16 单位 |
| `lexer.py` | `_read_new_syntax`、注释/小节标签剥离、带位置 token、调号/拍号/速度读取 |
| `document.py` | `@page/@part` 标记识别与顺序约束、分段、`parse_jianpu_parts`、位置重映射 |
| `events.py` | `_parse_event_token`、`_parse_pitch`、演奏标记目标校验和内联标记 |
| `tuplets.py` | 连音比例、组内容拆分、单音事件组合；依赖 events，不让 events 反向导入 tuplets |
| `score.py` | 单谱解析流程、必要时引入内部 `ParseState`/`MeasureBuilder`，显式管理当前小节与待应用标记 |
| `validation.py` | `validate_jianpu_text`、错误恢复、时值警告、小节号估算和重标号；调用底层解析，不被底层反向调用 |

`JianpuOptions`、`ParsedJianpuPart` 等已有外部使用者，首次迁移保留原导入可用。词法错误构造属于底层模块，不放进需要调用 parser 的 validation，以免形成环。

状态机当前包含大量 `nonlocal`，包括 cursor、待处理力度/演奏标记、跨音连线、反复、调拍号和来源起止位置。若后续迁移状态机，应先整体迁移并保持行为，再单独考虑将 flush/append 等操作纳入显式状态对象，不能一边搬文件一边改语法。

执行范围收缩：首轮优先提取共享 token/错误/位置基础和 lexer，或在这些基础明确后抽 validation；不要求同时创建上表全部模块，也不要求首轮搬迁单谱状态机。`ParseState/MeasureBuilder` 是后续可选重构，需要单独论证是否比现有局部闭包更清楚，不能作为拆分完成条件。文档标记扫描应成为 document 与 validation 共用的低层能力，不能复制一套标记规则。

验收重点：多页多声部编号、反复后的空小节、调拍号和速度继承、嵌套连音、诊断降级、中文及非 BMP 字符的位置。复用 `jianpu_tokens.py`、`performance_marks.py`、`measure_counts.py` 等既有规则。

### 3.3 MusicXML 解析器：分离时间线、记号和连音恢复

保留 `domain/parse/musicxml.py` 的公开函数；新增相邻 `musicxml_reader/` 包，避免同目录同时存在同名 `.py` 和包目录。

- `document.py`：入口、标题/乐器元数据、声部列表和 `_split_part_by_staff`。
- `measure.py`：`_parse_single_part`、小节属性、`backup/forward` 时间线、事件组装。
- `notes.py`：音高、时值、升降记号、beam 读取。
- `tuplets.py`：显式连音状态、time-modification 恢复、六连音推断。
- `directions.py`：`_direction_text_blocks`、速度、力度、wedge/pedal/octave-shift 及原始属性。
- `provenance.py`：`_note_provenance`、source role、和弦事件来源合并。

不要把整个 248 行 `_read_measure_events` 机械切成前后半段；先提取 note/direction 的独立读取函数，让小节入口继续管理共同 cursor、voice/staff 和跨小节状态。

现有 `musicxml_path_to_scores`、`read_musicxml_text` 经 `xml_utils` 做文件/MXL I/O，这是已有 domain 边界债务。本轮可以先保留兼容；后续单独将 I/O 迁到 `services/files/`，由 service 读取文本再调用 domain。不可让 domain 为了兼容反向导入 service。

验收：MusicXML 双向往返、复调时间线、多谱表空小节、同号嵌套连音、跨小节连音、微分音、结构方向属性及来源 ID。

### 3.4 渲染 Actions：编排留在 exec，计算下沉到 domain

依据：已有 `RenderMusicXmlJianpuAction`、`RenderJianpuTextAction` 和 `RenderActions`；后者从 318 行开始，混有 batch 处理和输出注册，831 行以后仍有大量纯计算与 OCR 辅助函数。

建议拆为：

- `exec/render/actions.py`：维持 API 调用的原门面，只转发请求级操作。
- `exec/render/musicxml_actions.py`：MusicXML 输入的单页/多页渲染编排。
- `exec/render/text_actions.py`：简谱文本输入、正规化和来源文本附件编排。
- `exec/render/batch_actions.py`：flat/multi-part 批次请求流及最终输出编排。
- `services/render/score_preparation.py`：调用 domain 完成文本解析、升降号模式、来源标记和附件放置，给 exec 提供服务入口。
- `domain/render_mapping.py`：页/小节范围映射、连续编号等纯计算。
- `services/render/ocr_overlay.py`：OCR 解析和来源页面适配；其中纯布局计算放到 domain 中，优先复用已有 `text_placement.py`。
- `services/render/artifacts.py`：渲染页注册、render map 与响应产物整理，持有组合根提供的文件服务。

关键约束：`tests/test_architecture.py` 的例外绑定到**原文件路径** `exec/render/actions.py`。把它现有的 domain import 原样搬进新的 exec 文件会违反架构门禁。应先补 service 入口，再拆 action，不扩大白名单。请求流程仍由 exec 拥有，service 只承担准备、渲染、登记等明确操作。

新协作对象由 `exec/composition.py`/既有依赖工厂组装，避免每个 action 重新创建有状态的 UploadService。API 仍负责 HTTP 错误映射与异步线程卸载。

首轮不创建三种新 action 和多层纯转发门面。先把一组明确的谱面准备或 OCR 适配操作通过 service 承接，并保留 RenderActions 的请求编排；只有单个请求流程可以独立维护时才另拆 action。已存在 `PublicationRenderService → main → PublicationRenderer` 的调用链，应避免再叠加多个没有独立职责的包装。

### 3.5 历史 DAO：按迁移、映射和 SQL 操作分离，保留事务拥有者

依据：`HistoryDao` 类占 1100 行；`_migrate_db` 有 152 行；`save_batch` 在 496 行显式启动 `BEGIN IMMEDIATE`，一并保存页面、批次、状态和快照。

在 `dao/history/` 内建议新增：

| 模块 | 职责 |
|---|---|
| `connection.py` | 连接工厂、SQLite 版本检查、foreign_keys/WAL/busy_timeout 配置 |
| `schema.py`、`migrations.py` | 建表、索引、版本升级与升级前备份；先照搬已支持的升级逻辑，不引入新的迁移框架 |
| `codecs.py` | JSON/string list、OCR、text anchors、text attachments 编解码 |
| `mappers.py` | SQLite row 到实体映射，优先接收已查出的行 |
| `batch_queries.py`、`page_queries.py` | 批次查询/更新、页面查询/更新/重排，接受外部 connection |
| `snapshots.py` | 快照 SQL 和行映射，写入同样接受现有 connection |
| `history_dao.py` | 保留公开方法、组合依赖和跨表事务边界 |

最重要的约定：参与一次 `save_batch` 的子模块使用**同一个 connection**，子函数不能自行 `connect/commit`。原子保存、快照写入和异常回滚仍由门面统一控制，不要为了分文件引入多个各自提交的 DAO。

首轮实际建议仅新增 `codecs.py`；之后可把 schema、索引和迁移放进同一个 `migrations.py`。原 `_connect` 只有 7 行，继续由 HistoryDao 持有；备份和初始化的调用顺序也先保留。`mappers/batch_queries/page_queries/snapshots` 仅在后续出现独立维护收益时再拆，当前不预设九文件结构。

验收现有 `test_history_service.py`、`test_history_atomic_save.py`、`test_history_snapshot.py` 和缓存引用测试。数据库迁移只使用临时 fixture 数据库，验证备份、版本拒绝、字段兼容及失败回滚；不在用户实际历史库上试迁移。

### 3.6 简谱写出：文本生成和来源锚点共享同一套序列化规则

保留 `domain/write/jianpu_text.py` 门面，新增 `domain/write/jianpu/`：

- `normalize.py`：连线规范化、voice 分组及已有降级警告。
- `tokens.py`：音符/休止符 token、时值、演奏标记。
- `tuplets.py`：`_TupletEmission`、连音输出计划及连线括号处理。
- `document.py`：谱头、小节、`@page/@part`、多谱拼接和哈希。
- `anchors.py`：`_text_anchors_raw`、事件/前缀角色锚点、文本位置转换；如仍偏长，再分事件锚点和文档偏移。

锚点定位与正文必须共享 tokens/tuplets 的输出规则，避免二者各自实现音符展开。当前单谱和多谱写出有不同的偏移汇总路径，应以正文、`text_hash`、每个 anchor 的 source ID、role 和 UTF-16 范围联合验收。

首次只抽取已有输出计划；“统一为一次遍历同时输出正文和锚点”是后续可评估的算法改造，不与物理拆分同时做。测试里存在原 writer 模块私有函数访问和 logger 名称断言，迁移时要明确更新这些测试边界。

## 4. 前端具体拆分

前端沿用现有目录：组合函数放 `composables/<功能>/`，子组件放 `components/<功能>/`，纯数据/转换函数放 `utils/<功能>/`。初版提出的顶层 `features/` 不是完成拆分的必要条件，本轮撤回这一目录扩展，避免同时维护两套功能归属约定。组件保留 props/emits，异步 API 仍通过既有 `{ data, error }` wrapper，工作流边界继续由 `useMessage()` 展示错误。

### 4.1 ConvertView：按工作流拆，不制造一个新的超大 composable

建议提取：

| 模块/组件 | 迁入职责 |
|---|---|
| `composables/convert/useConversionDocument.ts` | 编辑文本同步、rekey 基线、普通编辑后的锚点更新与待合并识别结果 |
| `composables/convert/useSourceSelection.ts` | 原谱 source 点击、文本选区定位、渲染页来源查找，复用 sourceAnchorSelection |
| `composables/convert/useConversionExport.ts` | `exportScore`、下载、命名、格式分支、最终导出 |
| `composables/convert/useBatchPublication.ts` | 最终批次排版、渲染页/OCR 状态、render map 加载；复用 batchRender/usePublicationRender |
| `composables/convert/useScoreCorrection.ts` | `loadEntities`、删除选择、`applyCorrections`、编辑模式 |
| `composables/convert/useJianpuSnapshots.ts` | 快照列表、恢复和丢弃编辑确认流程 |
| `composables/history/useHistoryBrowser.ts` | 历史列表、展开、删除和重排；不再承载编辑器的其他操作 |
| `components/history/HistoryDrawer.vue` | 历史列表/页面卡片及其专属样式 |
| `components/convert/ConvertToolbar.vue`、`ConversionPreviewPane.vue` | 操作栏和预览容器；继续使用已有 JianpuEditor、OriginalPreview、PublicationPreview |

现有 `composables/useHistoryRestore.ts` 已实现快速历史恢复，而 ConvertView 仍有自己的 `handleRestorePage`、文件检查和保存前置逻辑。应先对照两条路径的差异，再抽共同的“历史 DTO → TaskPageInput”“文件有效性判断”“保存前置条件”，保留快速入口和抽屉入口各自的选择行为。不要另建第三套恢复流程。

`flushPendingEdits` 是 App 关闭保存、历史替换与自动转调之间的现有契约，拆分后保留 exposed 方法及等待顺序。新组合函数通过明确的 refs/少量回调传递依赖；若需要几十个回调或互相调用，说明边界还需调整。

首轮保留编辑 watcher、rekey 基线、历史恢复和关闭前保存的拥有关系，先抽一个展示组件或纯历史数据映射。`exportScore` 的 PNG/PDF 分支会调用 `renderExportSvgIds → renderFinalBatch → saveRenderState`，不能视为独立下载逻辑。要拆导出，先明确获取可导出 SVG 的窄接口及失败/取消行为，不让 export 与 publication 互相回调；没有必要为此先统一历史恢复。

ConvertView 最终可以以界面装配为主，但撤回首轮 300–500 行的预期。样式跟随归属组件迁移，避免抽成一个同样庞大的全局 CSS 文件。每次只搬同一职责的 refs、watcher 和清理逻辑，保持其注册顺序与 flush 配置，不同时调整 watch 行为。

### 4.2 RecognizeView：分离任务控制与页面展示

- `composables/recognize/useRecognitionSelection.ts`：选择集、可启动页面、批次进度派生。
- `composables/recognize/useRecognitionPreview.ts`：预览加载、object URL 回收、页面重新上传；继续复用 `useFileUpload`。
- `composables/recognize/useRecognitionTasks.ts`：提交任务、owned task/controller 集合、等待结果、中断恢复、卸载清理。
- `utils/recognize/recognitionResults.ts`：OMR/AI 响应到统一页面结果的纯适配，保留两种模式的差异。
- `composables/recognize/useRecognitionPersistence.ts`：prepareHistory、task ID 绑定、成功/失败持久化与历史事件通知。
- `composables/recognize/useRecognitionBatchRender.ts`：完成后渲染、重复请求合并、批次文本同步。
- `RecognitionToolbar.vue`、`SourcePageCard.vue`、`RecognitionProgress.vue`：拆页面 UI 并携带其样式。

协调状态仍在 composable 实例中创建，不提到模块顶层。特别保留 ownedTaskIds、resumingTaskIds、AbortController 和 `batchRenderInFlight` 的拥有关系。两个识别模式目前足以用显式适配函数表示，不需要先造通用插件注册框架。

UI 切换目前有 `v-show` 保活语义；隐藏页面不等于卸载，也不等于取消任务。应分别验证切换页面、销毁组件、重识别和后端任务恢复。

首轮只提取选择/预览或已确认无副作用的结果字段映射。任务等待、历史落库和完成后批次渲染属于同一异步生命周期，先继续由一个控制入口拥有；实际依赖没有收敛前不按上表拆成互相回调的三个 composable。

### 4.3 workspace：保留一个公开 Store，先拆内部状态职责

不建议第一步拆成多个互相 import 的 Pinia Store。页面、批次与未保存状态具有一致性要求，先保持 `useWorkspaceStore` 的外部 API。

在 `stores/workspace/` 建议放置：

- `types.ts`、`pageFactory.ts`：TaskPage/TaskPageInput、默认值和深复制。
- `pageState.ts`：pages/currentPageIndex、patch/select，以及当前页镜像同步。
- `renderState.ts`：批次 SVG、OCR、layout key、stale 状态。
- `documentState.ts`：批次简谱文本、待合并页面集合。
- `revisionState.ts`：用户修订、保存时 revision 捕获/确认、不可持久化状态；调用既有 `unsavedChangeState.ts`。
- `taskState.ts`：busy/currentTask/backgroundTaskCount。

`workspace.ts` 组合这些内部模块，并继续统一执行 `removePage`、`replacePage`、`loadBatch`、`reorderBatchPages`、`reset` 等跨模块动作。内部模块接收其需要的状态或窄接口，不反向调用 `useWorkspaceStore()`。

必须保护三点：删除/替换批次时所有 per-batch map 一并处理；保存只确认捕获到的 revision；渲染输出过期不等同于用户有未保存编辑。当前已有对应测试，应作为拆分护栏。

把顶层当前页镜像 refs 改为 computed 是另一个状态模型变更，应在内部拆分后单独评估，以免改变 watcher 时序与赋值语义。

首轮仅迁出 types/pageFactory 和可独立复用的纯集合转换函数；已有 `unsavedChangeState.ts` 已承担修订算法，不再套一层只转发它的 revision 模块。`loadBatch/removePage/reset` 等跨状态动作及 ref 创建继续留在原 Store。状态切片属于后续有条件工作，不能仅按字段名称执行。

### 4.4 其余四个千行 Vue 文件

| 文件 | 建议拆法 | 必须保护的行为 |
|---|---|---|
| AiAssistant | `AssistantPanel/AssistantMessageList/AssistantMessage/AssistantComposer`；`useAssistantFloatingPanel` 管拖拽/吸附/动画，`useAssistantScroll` 管滚动；`messageFormatting.ts` 管 Markdown/think 分段 | 继续由现有 assistant store 管会话和流式请求；保持 HTML 转义、链接处理、think 折叠、拖拽结束与定时器清理；切 tab 不卸载助手 |
| App | `AppTitleBar/AppNavigation/CloseConfirmDialog/SettingsDiscardDialog`；`useWindowLifecycle/useCloseConfirmation/useAppNavigation`；主题数据迁到 `theme/naiveOverrides.ts` | 保持统一 close request 协议、等待编辑器 flush 再保存、保存失败留在应用中；保留各视图单根元素和 v-show 生命周期；全局基础样式仍由 App 入口引入 |
| SyntaxView | `utils/syntax/catalog.ts` 放静态内容；`useSyntaxSearch` 放搜索；`useInstrumentCatalog` 放加载状态；`SyntaxSearchResults/SyntaxSection` 展示 | 例子内容、搜索分组、加载失败提示、复制反馈；先抽数据与纯搜索，适合作为低风险试点 |
| JianpuEditor | `useEditorViewport` 管滚动/metrics/选区定位；`useEditorHighlight` 管语法/播放/错误映射；`useAutoTranspose` 管 debounce、在途请求、失败重试和 flush；小节栏/页摘要拆子组件 | 保留 `flushPendingAutoTranspose`、`selectRange`、`getSelectionRange` 等对外能力；`rekey-applied` 先于文本更新；转调失败阻止保存；定时器、ResizeObserver 和事件监听由创建方释放 |

抽取 `AiAssistant` 的文本格式化时，先保留现有输出语义；是否更换 Markdown 库应作为独立变更。编辑器语法 token 继续复用 `utils/jianpuSyntax.ts`，转调继续复用 `autoTransposeGate.ts`，不重复实现。

## 5. 测试、生成文件与次级候选

### 5.1 超过千行的测试

| 文件 | 行数 | 拆分方案 |
|---|---:|---|
| `tests/test_render.py` | 2644 | 按 spacing、beams、spanners/tuplets、annotations、pagination、render map 和 action 集成拆；bbox/XML 断言助手放 `tests/support/render_assertions.py`，复用现有 `tests/fixtures/render_cases.py` |
| `tests/test_convert.py` | 1616 | 按音高/调号、时值/连音、voice/staff 时间线、演奏/结构记号、转换动作拆；大型 MusicXML 输入按语义放 fixture 文件，不把每个短字符串都外置 |
| `tests/test_jianpu.py` | 1317 | 按基础语法、文档页/声部、反复/小节、连音、演奏标记、文本往返拆；与现有 measure_numbering/syntax_validation/anchors 专项保持职责区分 |
| `tests/test_api_routes.py` | 1139 | 按 render、convert/jianpu、history、settings、files/export、async 边界拆；公共 TestClient fixture 放在相应测试子目录的 conftest |
| `desktop/scripts/test-jianpu-page-sections.mjs` | 1166 | 按标记解析、文本拆合、连续编号、分页/多声部统计拆；共享模块加载助手，仍让 `pnpm test:utils` 收集所有新增文件 |

不把全局测试文件迁移作为业务拆分前置条件。保留现有公开入口测试，先补当前职责缺失的行为断言，再随该职责迁移内部测试导入与加载器。单纯整理测试目录应单独提交，核对用例及参数化场景的迁移映射，而不只比较总数量。不要把一批测试改成只检查新文件/函数存在。

项目并非“前端没有测试”：当前使用 Node `node:test`，部分测试编译真实 Store 和 Vue SFC setup；但没有完整浏览器 DOM/E2E 设施。`test-history-restore-transpose.mjs` 还通过 AST 从 ConvertView 抽取指定函数，部分 workspace 测试硬编码模块路径并替换 import，业务拆分必须同步调整这些加载器。

`test_render.py` 直接导入 `_Anchor/_Cell/_event_positions` 等私有实现。应把算法测试迁到相应新模块，同时让公开 API/集成测试继续经过旧公开入口。不要长期通过 renderer 重导出所有私有函数只为维持测试结构。

渲染测试改目录时，过渡期保留 `tests/test_render.py` 的门面回归测试，执行它及新 `tests/render/` 目录；统一切换后同步 AGENTS.md、文档和 CI 命令，避免只跑旧文件却漏掉主要用例。`tests/test_code_reduction.py` 的固定源码文件清单也需要调整到新实现范围。

### 5.2 不手动拆分的文件

- `desktop/src/renderer/src/models/openapi.ts`：4753 行，文件声明由 openapi-typescript 自动生成。保持生成器负责，手写代码依赖已有 `contracts.ts` 的语义别名；不要手拆原始类型文件。
- `desktop/pnpm-lock.yaml`：5074 行，锁文件由 pnpm 管理，与业务维护性拆分无关。
- `uv.lock`：730 行，同属自动维护的依赖锁文件。

### 5.3 500–1000 行的后续观察清单

这些是候选，不表示都应立刻拆；先以本节建议职责检查收益。

| 业务文件 | 行数 | 后续可拆边界 |
|---|---:|---|
| `components/PublicationPreview.vue` | 889 | SVG 加载/替换、来源高亮、坐标/交互，保留现有异步 gate 与 sanitizer |
| `domain/rekey.py` | 856 | 调号编辑识别、音高转写、文本/锚点映射 |
| `domain/performance_marks.py` | 773 | 静态记号目录与查询/规范化规则；仅在目录继续增长时按乐器组织数据 |
| `views/SettingsView.vue` | 769 | 设置分类导航和离开确认；已有 settings 子面板继续复用 |
| `domain/write/musicxml.py` | 721 | 文档骨架、小节/voice 写出、note/notation/direction 写出 |
| `stores/settings.ts` | 697 | 配置快照/dirty 比较、provider 配置适配、加载保存 |
| `exec/pipeline/actions.py` | 605 | OCR、转换、渲染的独立服务操作；新 exec 文件同样不能继承旧 domain import 白名单 |
| `components/OriginalPreview.vue` | 602 | 资源加载与回收、overlay/来源选择、缩放交互 |
| `utils/jianpuPageSections.ts` | 585 | 页/声部标记扫描、文本拆合、小节统计，避免与后端各自改变语法 |
| `utils/jianpuPlayback.ts` | 562 | 播放音符 span、页定位和时值解析 |
| `engraving/mark_graphics.py` | 538 | 若继续扩展，再分标记图形类别；与 renderer 拆分保持独立 |
| `components/JianpuPlayer.vue` | 535 | 控制条 UI 与播放显示；核心播放继续由 usePlayer 拥有 |
| `services/recognize/external_tools.py` | 532 | 工具路径/Java 检查、Audiveris 参数构造、进程执行与结果读取 |

本区测试文件另有：`test_ai_transcription.py` 894、`test_history_service.py` 875、`test_ai_continuation.py` 649、`test_rekey.py` 635、`test_provenance.py` 595、`test_syntax_validation.py` 573、`test_settings_providers.py` 525 行。随对应功能拆分即可，不单独发起所有测试的大迁移。

## 6. 稳定性护栏与当前验证

首轮调研实际执行结果（此次自评只重新进行静态检查，没有再次运行这组测试）：

| 检查 | 结果 |
|---|---|
| bash 激活 `.venv`，检查解释器 | Python 3.13.5，`sys.prefix` 指向项目 `.venv` |
| 后端完整 `pytest` | **1027 passed、1 skipped、1 xfailed**，23.54 秒 |
| 前端 `pnpm test:utils` | **238 passed、1 skipped、0 failed** |
| 前端 `pnpm typecheck` | 通过，覆盖 web/node 两个 tsconfig |

默认 pytest 首轮因系统 `pytest-of-Lenovo` 临时目录的 WinError 5 出现 fixture setup 错误。通过 bash `mktemp -d` 在项目 `.pytest_cache/` 下新建独立目录，再指定其全新子路径为 `--basetemp` 后全量通过。没有修改系统目录权限、删除原临时目录或修改代码来绕过测试。仍有一条既有 Starlette TestClient 弃用警告。

本次没有启动 Electron、执行真实 OMR/联网 OCR/AI 或做浏览器 UI 验收，也没有运行 lint/build/OpenAPI 漂移检查。因此测试结果证明的是当前自动化基线，不等同于实际桌面流程全部验收。

后续每个业务拆分批次：

1. 在移动前固定对应公开入口行为，特别是页面/声部/source ID、诊断位置、保存 revision 和事务语义。
2. 先运行对应专项；阶段合并前跑完整 pytest、前端 lint/typecheck/test:utils，涉及构建模块边界时跑 production build。
3. 改 Python 导入层次必须跑 `tests/test_architecture.py`。不扩大跨层例外；共享 DTO 归 models，纯规则归 domain，业务流程归 exec。
4. 涉及公开 Pydantic 模型时执行 OpenAPI 生成/漂移检查；纯拆分应避免改变 API 字段、默认值、返回形状和错误码。
5. 复杂前端拆分前补关键行为覆盖：保存过程中编辑、转调未完成就保存/恢复、删除/重排当前页、切换页后旧请求返回、失败重试和卸载。现有 Node/SFC 测试能表达的先复用；真实坐标点击和 CSS/焦点行为需要 DOM 或 Electron/Playwright 验收。
6. SVG 拆分对固定 fixture 比较完整 SVG/render-map 输出，并保留几何约束测试；视觉基线改变需要单独解释，不能批量更新快照掩盖差异。
7. 历史层保留临时 SQLite 数据库上的中途失败回滚、旧 schema 升级和快照一致性测试。

推荐 bash 验证方式（从项目根目录执行，后端临时路径每次新建）：

```bash
source .venv/Scripts/activate
mkdir -p .pytest_cache
audit_tmp=$(mktemp -d "$PWD/.pytest_cache/refactor-audit.XXXXXX")
python -m pytest -q --basetemp "$audit_tmp/pytest"
```

前端在 `desktop/` 下运行既有 `pnpm lint`、`pnpm typecheck`、`pnpm test:utils`、`pnpm check:api-types`、`pnpm build`。以上是后续验收要求，不代表本次全部执行。

## 7. 推荐实施顺序与完成标准

| 阶段 | 内容 | 可以验收的交付物 |
|---|---|---|
| A：最小试点 | 从 HistoryDao JSON codecs 或 renderer visual event 拆解中选择一个；核对依赖、迁出实现、调整相关内部测试 | 一个新实现模块，旧公开入口可用；无新增状态/事务拥有者；专项与完整后端测试通过 |
| B：低耦合职责拆分 | renderer 公共属性/几何依赖整理后抽符杠；parser 共享基础/lexer；DAO schema 与迁移；可独立开展 SyntaxView 数据提取 | 布局不依赖绘制；底层模块不回引原门面；无新跨层例外；原输出和异常行为一致 |
| C：前端展示及纯转换 | Convert 子组件/历史字段映射，Recognize 选择/预览；Store 先抽类型和默认值 | 不改变保存与异步流程；props/emits、样式作用域、watcher 和清理语义通过对应检查 |
| D：有行为护栏后拆工作流 | 导出通过明确接口获取渲染结果；历史恢复先覆盖两种入口差异；Recognize 保持统一任务拥有者再拆辅助操作；RenderActions 先补实际 service 能力 | 不引入循环回调或重复业务流程；保存/取消/恢复/错误分支有行为测试 |
| E：按收益决定更深拆分 | Store 状态切片、parser 状态对象、渲染 spacing/spanners、DAO SQL 分组、编辑器自动转调 | 只在现有边界仍妨碍维护时执行；证明接口更简单及关键行为不变，不能以降到指定行数代替论证 |
| F：逐批收尾 | 随每批更新导入入口、测试映射和文档；500–1000 行候选保持观察 | 不遗留重复实现；所有新测试实际收集；必要兼容门面有明确范围 |

每阶段允许多个小提交，每次只移动一个职责簇并验证。语法变更、数据库 schema 变更、取消/保存语义变更及算法优化应独立提交，保证失败时能定位和回退具体变更。

完成标准不设“所有文件必须小于 N 行”的硬指标，而采用以下可检查条件：

- 手写文件超过约 500 行需要复核职责，超过 800 行作为审查提示；生成文件、数据表和测试 fixture 明确豁免。阈值是建议，不是当前仓库规则。
- 新增一种演奏标记、识别结果适配或导出入口时，有明确的模块归属，不需要同时理解整个页面或渲染器。
- 外部公开接口稳定，内部依赖无环；迁移过渡只保留必要公开重导出，不保留两份算法。
- 每个有状态模块明确谁创建、谁清理、谁可以写入；Store 跨状态操作和 DAO 跨表操作继续有统一协调者。
- 测试收集没有遗漏，行为断言没有因拆分被删弱；UI 的 scoped 样式和全局选择器归属明确。

首批建议仅完成 A 的一个职责簇。它不是为了立刻把千行文件压到几百行，而是验证“定位边界—移动实现—保持行为”的方法和测试适配成本，再进入 B。无需等待大规模前端改造，才能开始已有较强自动化覆盖的后端拆分。

## 8. 自我复核：哪些合理，哪些需要撤回

### 8.1 总体判断

初版适合作为职责地图，不适合不加裁剪地转成施工清单。当前代码和测试足以支持小步抽取，尚不足以证明整套细粒度结构落地后会降低维护成本。此次没有实现试拆或性能实验，因此不声称所有候选模块的可行性已经验证。

继续保留的判断是：大文件清单、生成文件豁免、保留公开入口、DAO 单事务、Store 单一公开入口、分层白名单约束以及分离物理迁移与行为修改。需要撤回的是：过早确定全部文件名、低估前端流程耦合、优先把已有良好覆盖的后端排到大规模 UI 拆分之后，以及把行数目标当成近期结果。

### 8.2 具体发现及修正

| 问题 | 复核证据 | 对实施的影响与修正 |
|---|---|---|
| 按函数区域划分 renderer 会留下不合理依赖 | `_boundary_extra_gap:775`、`_apply_beat_boundary_gaps:1406` 调用 `_is_tuplet:2071`；`_system_extra_height:1024` 调用 `_measure_text_layout:2439`；beams/tuplets 调用 `_span_attrs:2267` | 抽出共享事件判断、文本几何和跨度属性，再分布局与绘制。AST 发现的是依赖边界缺口，不表示当前代码存在循环导入 |
| 把跨服务使用等同于“必须把类型搬到 models”过于粗糙 | `PublicationPage:49` 的 scene 字段引用 `PublicationScene` | 渲染产物保留在 services 内部类型模块；不能为类型归档违反 models 无反向依赖的规则 |
| DAO 和输出层过度细分 | `_connect` 7 行，SQLite 版本检查 8 行，`write_pages` 27 行；建表/迁移/索引由同一初始化流程使用 | 不分别建立细碎门面；DAO 首轮抽 codecs，其后合并迁移职责；写盘方法暂留原类 |
| 把 Convert 导出或历史恢复当成低风险独立切片不准确 | `exportScore:1542` 经 `renderExportSvgIds:1758` 调用 `renderFinalBatch:1773`，后者更新 store 并保存渲染状态；`handleRestorePage:1212` 还选择历史页、等待渲染并触发定位 | 首轮只抽展示/纯映射，工作流抽取需明确渲染和保存接口。快速恢复与抽屉恢复先保留行为差异，不顺便合并 |
| Store、识别任务按字段/步骤细分可能增加协调成本 | Store 删除/替换/加载同时操作多张 per-batch map；识别任务从 prepareHistory 到结果写回及批次渲染共享 task/page 身份与取消状态 | 原入口继续拥有跨状态和异步生命周期；先抽纯函数，只有依赖收敛后再拆状态/任务模块 |
| 测试总数高不代表组件重构已有足够保护 | `test-frontend-lifecycle.mjs` 检查变量位于 SFC setup 内、原组件包含清理代码；其他测试用 AST 抽取指定函数或手工替换 import | 移到 composable 后这些测试可能在行为未变时失败。不能仅改正则使其通过，应以两个实例互不影响、卸载真正清理等行为补足原意 |
| 提前全量拆测试会增加迁移面 | 现有测试共享 fixture、私有导入和固定源文件路径 | 测试随一个业务职责局部适配。若单独整理测试，记录旧 node ID 到新测试的对应关系及参数化案例，不只比总数量 |
| 推行 features 目录和统一小文件目标缺乏当前必要性 | 项目已经使用 components/composables/utils；Vue 大文件中样式与模板占比不同 | 沿用现有约定，以功能子目录组织；不把减少行数或增加模块数量本身当成收益 |

### 8.3 启动每一批前应有的最小设计

每个拆分批次在实施前写清楚以下内容即可，无需再做全项目设计：

1. **迁移清单**：具体函数、类型、常量，以及关联 watcher/fixture；不能只有“拆成 xxx 模块”。
2. **依赖闭包**：迁出代码引用什么，谁调用它；共享低层函数应先确定归属，不允许新模块回引原门面来取私有实现。
3. **拥有关系**：唯一的 state、connection、AbortController、request gate 或 timer 由谁持有，其他模块只获得必要访问权。
4. **兼容范围**：保留哪些公开路径和 exposed 方法；测试的私有导入与 patch 目标移到真实实现处。公开兼容不等于永久重导出所有私有名称。
5. **等价证据**：选择能触及该职责的既有 fixture，说明还缺哪个行为场景；确定测试命令和需要的 UI/几何验收。
6. **停止细分的条件**：如果新增模块大量传递原有局部状态、相互回调或只转发调用，合并回同一职责簇，不用通用 Context/registry 掩盖边界不清。

例如 DAO codecs 试点只移动 `_dump/_load` 序列化函数及其模型依赖，HistoryDao 保留连接、查询、事务、迁移与返回实体的过程；验收旧 JSON、空列表、可选字段、现有批次保存/快照场景。若这些用例暴露原编解码缺陷，应另列问题，不能在移动中悄悄改变容错规则。

### 8.4 收益和可行性如何判断

“可实施”先由无循环/无违规导入、兼容入口及相关测试证明；“值得实施”还需比较迁移前后的修改路径。例如改一个 JSON 字段只需定位 codecs，改符杠绘制不需要阅读分页和连线状态。若实现文件变短却必须同时修改更多文件，或有更多隐式共享状态，该边界就应重新合并。

不对完整计划给出无依据的工期或成功概率。先用一个实际试拆记录业务迁移规模、测试适配量和回归情况，再估算后续批次。仅修改文档的此次复核不需要重复全量功能测试，首轮调研测试结果保留为带日期的基线。
