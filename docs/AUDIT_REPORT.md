# Score Trans 项目深度调研报告

> 审计日期：2026-07-03
> 审计范围：全部项目源代码（不含 third_party/audiveris），约 43,500 行代码，310 个源文件
> 审计方法：逐文件逐函数完整通读，使用并行子代理覆盖各子系统
> **修订：** 2026-07-03 对全部 150+ 条目进行了逐条源码验证。3 条经复查不成立（1.7 JPEG 检测、4.4 AI 回复 XSS、5.7b falsy 回退），已标注 ~~删除线~~ 并附复查结论。6 条部分准确的条目（2.6、5.4b、6.1g、6.2a、7.3a-f、9.1）已修正描述与行号。统计数字已同步更新。

---

## 目录

1. [严重 Bug（数据丢失 / 崩溃）](#1-严重-bug数据丢失--崩溃)
2. [音乐理论正确性问题](#2-音乐理论正确性问题)
3. [架构违规](#3-架构违规)
4. [安全漏洞](#4-安全漏洞)
5. [功能缺陷与缺失特性](#5-功能缺陷与缺失特性)
6. [前端问题](#6-前端问题)
7. [代码质量问题](#7-代码质量问题)
8. [测试覆盖问题](#8-测试覆盖问题)
9. [构建与 CI 问题](#9-构建与-ci-问题)
10. [问题统计汇总](#10-问题统计汇总)

---

## 1. 严重 Bug（数据丢失 / 崩溃）

### 1.1 缓存清理删除被引用的文件 — 数据丢失

**文件：** `services/storage/cache_service.py:67-79`

`_referenced_file_ids()` 仅检查 `input_file_id`、`musicxml_file_id`、`svg_file_id` 三个字段，遗漏了 `overlay_file_id`、`overlay_svg_file_id`、`source_map_file_id` 以及 `HistoryBatch.render_page_file_ids`。清理缓存时，这些被引用的 overlay 和源映射文件会被删除，导致历史记录中的链接失效。

**修复方案：** 补全所有文件 ID 字段的引用检查。

### 1.2 简谱时值标记往返转换失败 — 音符时值错误

**文件：** `domain/jianpu_tokens.py:49-53`

`duration_affixes(Fraction(5,2))` 生成 token `q5-`，但 `token_duration("q5-")` 返回 `3/2` 而非 `5/2`。原因：当 `remain` 非零时，应使用 `whole` 个连字符而非 `whole - 1`。同理 `Fraction(9,4)`、`Fraction(7,4)` 等混合整数+分数时值均受影响。

```python
# 当前（错误）
return prefix, suffix + "-" * max(0, whole - 1)
# 应改为
return prefix, suffix + "-" * (whole if remain else max(0, whole - 1))
```

### 1.3 双附点音符无法解析

**文件：** `domain/jianpu_tokens.py:66-67`

`token_duration` 使用 `if work.endswith(".")` 而非 `while`，只能解析单附点。双附点音符（如 `5..`）第二个点被忽略，时值计算错误。同样，`domain/parse/jianpu_text.py:772-775` 也只支持单附点。

### 1.4 TaskManager 订阅者双重移除崩溃

**文件：** `services/tasks/task_service.py:174, 209`

`global_events()` 在 `finally` 中调用 `self._subscribers.remove(sub)`，但 `_broadcast` 可能已因 `QueueFull` 移除了该订阅者，导致 `ValueError: list.remove(x): x not in list`。

### 1.5 pipeline 空渲染页面 IndexError

**文件：** `exec/pipeline/actions.py:363`

`svg_file_id=render_pages[0].svg_file_id` — 若渲染器未生成 SVG 页面，`render_pages` 为空列表，触发 `IndexError`。

### 1.6 AI 聊天流式失败留下孤立用户消息

**文件：** `services/ai/chat_service.py:95-114`

`stream_message` 在流式开始前持久化用户消息。若流式生成失败（模型异常），用户消息已保存但无对应的助手回复，导致会话历史中出现孤立消息，无回滚机制。

### 1.7 ~~JPEG 检测与 PyMuPDF 格式标识符错误~~（经复查不成立）

**文件：** `services/export/export_service.py:42-43`、`exec/export/actions.py:132-138`

> **复查结论：此项不成立。** JPEG 规范规定 SOI 标记 `FF D8` 之后紧跟下一个 marker 段，其首字节恒为 `FF`（JFIF 为 `FF E0`，EXIF 为 `FF E1` 等），因此 `img_data[:3] == b"\xff\xd8\xff"` 是正确的检测方式。PyMuPDF 1.27.2 同时接受 `"jpg"` 和 `"jpeg"` 作为格式标识符。此项保留编号但不视为缺陷。

### 1.8 应用关闭时可能死循环

**文件：** `api/app.py:126-129`

`_wait_for_background_tasks` 循环 `while background_tasks:` 但不从集合中移除已完成任务，可能导致关闭时无限循环。

### 1.9 用户数据目录名拼写错误

**文件：** `models/common/paths.py:9` 和 `desktop/src/main/storage.ts:5`

`USER_DATA_DIR_NAME = ".sorce_trans"` — "sorce" 应为 "score"。此 typo 同时存在于 Python 后端和 Electron 前端，已在用户系统上创建了拼写错误的目录。修复需迁移现有用户数据。

### 1.10 PDF 页数限制参数为 0 时返回全部页面

**文件：** `utils/pdf.py:26`

`min(len(doc), max_pages) if max_pages else len(doc)` — 当 `max_pages=0` 时，`if max_pages` 为 `False`（0 是 falsy），返回全部页面。应改为 `if max_pages is not None`。

### 1.11 HTTP 流式响应空 choices 数组 IndexError

**文件：** `services/ai/providers/_http.py:91`

`data.get("choices", [{}])[0]` — 若 `choices` 存在但为空列表 `[]`，`[][0]` 抛出 `IndexError`。OCR 的 `services/ocr/providers/_http.py:38` 有相同问题。

### 1.12 `assert` 用于运行时校验

**文件：** `exec/convert/actions.py:203`、`drawing/spanners.py:85,113,141`

使用 `assert` 进行运行时校验。当 Python 以 `-O` 标志运行时，assert 语句被移除，校验失效。

---

## 2. 音乐理论正确性问题

### 2.1 MusicXML→简谱丢失双变音记号

**文件：** `domain/parse/musicxml.py:590-629`

`_note_pitch` 不保留双变音记号。C##（alter=2）映射到 MIDI 62（D），在 MAJOR_SCALE 中渲染为 degree 2 且 `accidental=0`，双升号被静默丢失。同理 Bbb→A、Ex→F 等。

### 2.2 简谱→MusicXML 等音拼写错误

**文件：** `domain/write/musicxml.py:234-246`

`_append_pitch_xml` 通过 `SEMITONE_TO_STEP[semitone]` 查表，总是返回升号拼写。简谱 `b2`（C 大调中的 Db）输出为 `C#`（step=C, alter=1）而非 `Db`（step=D, alter=-1）。**所有变化音的等音拼写均丢失。**

### 2.3 色音拼写忽略调号方向

**文件：** `domain/parse/musicxml.py:611-629`

色音拼写优先检查降号（`relative+1 in MAJOR_SCALE`），忽略调号的升/降方向。在 D 大调中，Eb 应拼为 D#（升号方向），但代码输出 Eb。

### 2.4 MusicXML 重复记号和结尾段被忽略

**文件：** `domain/parse/musicxml.py:326-469`

`_read_measure_events` 不处理 `<print>`（分页/分系统）和 `<barline>`（重复、结尾段）元素。MusicXML 中的重复记号和结尾段被静默丢弃。

### 2.5 简谱→MusicXML 不输出重复记号

**文件：** `domain/write/musicxml.py:71-104`

`_append_score_measures` 不输出 `<repeat>` 元素。`measure.repeat_start` / `measure.repeat_end` 被静默忽略，重复记号在 MusicXML 输出中丢失。

### 2.6 共享编号的嵌套连音处理缺陷

**文件：** `domain/parse/musicxml.py:539-560`

`_apply_tuplet_notations` 的 `active_tuplets` 按连音 `number` 属性索引。不同 `number` 的嵌套连音可以正确区分，但当内外连音共享同一 `number` 时（某些 MusicXML 导出工具会这样做），内层连音会覆盖外层条目，嵌套结构丢失。

### 2.7 连音组时值硬编码

**文件：** `domain/parse/jianpu_text.py:656`

连音时值硬编码为 `Fraction(1, len(parsed))`（每个音符 = 1/n 全音符）。无法表示半音符三连音、四分音符五连音或不占满 1 拍的连音。

### 2.8 跨小节连音断裂

**文件：** `domain/parse/musicxml.py:335-336`

`active_tuplets` 按小节声明（每小节重置）。跨小节连音（MusicXML 中合法的 tuplet start/stop 在不同小节）被破坏。

### 2.9 简谱→MusicXML 不输出多声部

**文件：** `domain/write/musicxml.py:103-104`

不输出 `<backup>` 或 `<forward>` 元素。多声部乐谱被顺序展平，MusicXML 中的节奏错误。

### 2.10 简谱→MusicXML 丢失标题/速度/表情术语

**文件：** `domain/write/musicxml.py:115-148`

不输出速度、方向/文本块或小节级力度作为 `<direction>` 元素。仅音符级力度（在 `<notations>` 内）被写入。乐谱级文本（标题、表情术语、速度标记）丢失。

### 2.11 微音程信息有损转换

**文件：** `domain/parse/musicxml.py:880-896`

`_accidental_token` 将四分之一升→`#`、四分之一降→`b`，有损微音程取整。无警告。

### 2.12 八度点未垂直堆叠

**文件：** `services/render/utils/metrics.py:21-25, 28-36`

`_high_octave_dot_y` 和 `_low_octave_dot_y` 接收 `dot_index` 参数但从不使用。多个八度点（如 octave_up=2 或 3）在同一 y 坐标水平排列，而非按简谱标准垂直堆叠。二/三八度音符的 SVG 渲染视觉错误。

### 2.13 动态术语词汇表不一致

**文件：** `domain/constants.py:56` vs `domain/parse/musicxml.py:859-877`

解析器使用的 `DYNAMICS` 集合省略了 `pppp`、`ffff`、`sf`、`fz`、`rfz`、`sfp`，但 MusicXML 导入器的 `_is_dynamic_name` 接受这些。导入包含 `\sf` 的 MusicXML 后，往返简谱文本时解析失败。

---

## 3. 架构违规

### 3.1 models 层导入 config 模块（3 处违规）

AGENTS.md 规定 `models/` 不得导入任何其他项目模块。

| 文件 | 违规导入 |
|------|---------|
| `models/ai/schemas.py:5` | `from score_trans.config.settings import PDF_RENDER_DPI` |
| `models/settings/schemas.py:5-15` | 多个 `from score_trans.config.settings import ...` |
| `dao/settings/settings_dao.py:6-25` | 多个 `from score_trans.config.settings import ...` |

### 3.2 exec 层 HTTPException 导入（已知技术债务，3 个文件）

| 文件 | 行号 | 使用次数 |
|------|------|---------|
| `exec/export/actions.py` | 6 | 4 处 |
| `exec/files/actions.py` | 5 | 2 处 |
| `exec/history/actions.py` | 3 | 8 处 |

### 3.3 API 异步路由处理器中使用同步阻塞调用

AGENTS.md 规定异步路由处理器不得直接使用同步阻塞调用。

| 文件 | 行号 | 说明 |
|------|------|------|
| `api/export/routes.py` | 17-23, 43-48, 51-56 | `export_midi`、`export_musicxml`、`export_musicxml_text` 为 `async def` 但同步调用 actions |
| `api/settings/routes.py` | 38-42 | `clear_cache` 为 `async def` 但同步执行文件删除 |

### 3.4 config 与 utils 循环导入

`config/settings.py:5-8` 导入 `utils/env.py`，而 `utils/env.py:8-9` 导入 `..config`。仅因导入顺序巧合而工作，架构脆弱。

---

## 4. 安全漏洞

### 4.1 无认证无授权

**文件：** 所有 API 路由

所有端点公开可访问，包括设置（API 密钥）、文件删除、历史删除。对于本地 Electron 桌面应用，风险较低；但若部署到网络，是严重安全缺口。

### 4.2 SSRF 风险 — 主进程 fetch 渲染器提供的 URL

**文件：** `desktop/src/main/files.ts:53-54`

主进程 `fetch(source.url)` 使用渲染器提供的 URL。若渲染器被攻破，可提供 `file://` URL 或内网 URL 进行 SSRF。应验证 URL 为指向 localhost 后端的 HTTP/HTTPS URL。

### 4.3 路径遍历风险

**文件：** `desktop/src/main/files.ts:6-8, 10-12`

`sanitizeFilename` 替换 `\/:*?"<>|` 但不处理 `..` 文件名。`isValidExportDir` 不检查路径遍历序列。组合使用可逃逸目录。

### 4.4 ~~AI 回复 v-html 渲染存在 XSS 风险~~（经复查不成立）

**文件：** `desktop/src/renderer/src/components/AiAssistant.vue:748-773`

> **复查结论：此项不成立。** `renderMarkdown` 在链接替换前（第 761 行）已对全文执行 `escapeHtml`，链接正则（第 768 行）要求 `https?://` 协议前缀，`javascript:` URL 不会匹配。原始 HTML 标签也被 `escapeHtml` 转义，无法注入。此项保留编号但不视为漏洞。

### 4.5 SVG v-html 渲染

**文件：** `desktop/src/renderer/src/components/SvgPreview.vue:17`

`v-html="svgText"` 渲染服务端生成的 SVG。虽有 `sanitizeSvg` 移除 `<script>`、`foreignObject` 等，但 DOMParser 方式可能无法捕获所有 XSS 向量。

### 4.6 XML 炸弹风险

**文件：** `services/recognize/external_tools.py:132`

`ET.fromstring` 对 XML 炸弹/十亿笑声攻击脆弱。输入来自 Audiveris（可信本地工具），风险低。

### 4.7 文件上传无大小限制

**文件：** `services/files/upload_service.py:142-161`、所有上传路由

无文件大小限制。大文件上传可耗尽内存/磁盘。

---

## 5. 功能缺陷与缺失特性

### 5.1 简谱文本解析缺陷

| 缺陷 | 文件:行号 | 说明 |
|------|----------|------|
| 单音符小节被当作小节标签吃掉 | `parse/jianpu_text.py:557` | `^\s*\d+[.:：]:(?:\s+|$)` 匹配独占一行的 `1.` |
| 未知 `^xy` 标记静默接受 | `parse/jianpu_text.py:926-933` | 无验证错误，垃圾标记被存储 |
| 紧凑连音不支持和弦 | `parse/jianpu_text.py:671-688` | `$[1+3]2$` 失败，必须用空格 |
| 小节下溢静默忽略 | `parse/jianpu_text.py:851-871` | 记录溢出但不记录下溢 |
| 行内调号变化被吞为头部 | `parse/jianpu_text.py:451` | `1=G` 在首行被当作头部而非行内标记 |
| 后缀双变音记号不支持 | `parse/jianpu_text.py:804-831` | `1bb` 解析失败但无清晰错误信息 |

### 5.2 MusicXML 解析缺陷

| 缺陷 | 文件:行号 | 说明 |
|------|----------|------|
| 多谱表分谱丢失生成休止符 | `parse/musicxml.py:225-281` | `staff=None` 且 `generated=True` 的休止符被丢弃 |
| 节拍器格式非标准 | `parse/musicxml.py:816-823` | 返回 `"quarter=120"` 而非 `"♩=120"` |
| 力度事件时序错误 | `parse/musicxml.py:449-453` | 同一游标位置多个力度时，仅第一个被使用 |

### 5.3 简谱文本生成缺陷

| 缺陷 | 文件:行号 | 说明 |
|------|----------|------|
| 源锚点字符串搜索失败时游标不更新 | `write/jianpu_text.py:225-239` | `line.find` 返回 -1 时 continue 不更新游标，后续事件位置错位 |
| 连音收集可能吃掉整个小节 | `write/jianpu_text.py:468-478` | `tuplet_id=None` 时条件总为 False，循环消耗到小节末尾 |
| 后缀变音记号 `x`/`bb` 锚点丢失 | `write/jianpu_text.py:396-405` | `_accidental_span` 只匹配 `[#b]$` |

### 5.4 渲染服务缺陷

| 缺陷 | 文件:行号 | 说明 |
|------|----------|------|
| `@text` 指令功能未实现 | `main.py:92-94` | `_extract_text_directives` 总返回空列表 |
| A4 渲染大部分字体大小硬编码 | `main.py:614-623` | `_a4_render_options` 硬编码大部分字体大小（`note_font_size` 和 `measure_number_font_size` 使用了命名常量） |
| 多分谱模式测量范围不含其他分谱 | `main.py:1015` | 仅包含第一分谱的布局 |
| 非 4/4 拍号文本模式节拍分组错误 | `layout/measure.py:120` | `int(cursor)` 仅在 `beat_duration==1` 时正确映射 |
| 小节线高度不适应内容 | `utils/bars.py:5` | 固定 `[y-50, y+58]`，超出范围的音符/标记不被包含 |
| 文本溢出检查在追加之后 | `drawing/text.py:126-127` | 最后一段文本可能超出边界 |
| `role="other"` 文本块获得错误的 `lyric` CSS 类 | `drawing/text.py:41` | 非动态文本被标记为歌词样式 |
| 死代码：`_render_beat_items`、`_render_articulation`、`_upper_mark_anchor_y` 无调用者 | 多处 | 维护负担 |

### 5.5 AI/OCR 服务缺陷

| 缺陷 | 文件:行号 | 说明 |
|------|----------|------|
| OCR provider 创建忽略 "mock" 类型 | `ocr/providers/__init__.py:17-26` | 未知 provider 静默回退到 OpenAI 兼容 |
| DashScope OCR 忽略用户配置的温度 | `ocr/providers/dashscope.py:85` | 硬编码 `temperature=0.1` |
| AI provider `transcribe_page` 方法三重复制 | `ai/providers/` 三个文件 | ~95% 相同代码 |
| 聊天 DAO 不支持 system 角色消息 | `dao/ai/chat_dao.py:45` | CHECK 约束拒绝 system 角色 |
| 空 YAML 导致 prompts 模块 TypeError | `ai/core/prompts.py:40` | `yaml.safe_load` 返回 None 时 `_cfg_value` 崩溃 |
| AI 聊天无会话删除错误处理 | `stores/assistant.ts:59-67` | `deleteSession` 无 try/catch |

### 5.6 数据持久化缺陷

| 缺陷 | 文件:行号 | 说明 |
|------|----------|------|
| 历史 DAO 迁移 `DROP TABLE` 不迁移数据 | `dao/history/history_dao.py:46` | 旧 `history` 表被删除，用户历史静默丢失 |
| 历史 DAO N+1 查询问题 | `dao/history/history_dao.py:544-567` | `list_batches` 对每个 batch 单独查询页面 |
| 可选字段无法清除为 NULL | `dao/history/history_dao.py:282-351` | `if value is not None` 语义下，传 None 意为"不更新" |
| 迁移 ALTER TABLE 无事务保护 | `dao/history/history_dao.py:455-533` | 迁移中途失败导致部分迁移状态 |
| chat_dao 无 WAL/busy_timeout | `dao/ai/chat_dao.py:22-26` | 并发写入可能 `database is locked` |
| task_dao `load_active` 返回已完成/失败任务 | `dao/tasks/task_dao.py:94-102` | 文档说"启动恢复"但包含不需要恢复的任务 |
| TaskStatus 枚举解析无防御 | `dao/tasks/task_dao.py:120-133` | DB 中未知状态字符串导致 `ValueError` |

### 5.7 设置系统缺陷

| 缺陷 | 文件:行号 | 说明 |
|------|----------|------|
| 无法通过更新端点修改 base_url 和 model | `models/settings/schemas.py:61-79` | 设置响应暴露但更新请求不含这些字段 |
| ~~`audiveris_max_pixel_count` 为 "0" 时的 falsy 回退~~（经复查不成立） | `services/settings/settings_service.py:101-103` | Python 中字符串 `"0"` 是 truthy，`or` 不会触发回退。仅空串 `""` 或 `None` 时才回退。此条不视为缺陷 |
| heap 值无验证 | `exec/settings/actions.py:54-55` | 无效值静默存储，运行 Audiveris 时才失败 |
| audiveris 步骤/强制等参数不可通过 DAO 持久化 | `services/settings/settings_service.py:93-103` | 仅通过环境变量配置 |

### 5.8 Electron/IPC 缺陷

| 缺陷 | 文件:行号 | 说明 |
|------|----------|------|
| preload 类型声明缺少 `saveExportFile` 和 `openFolder` | `preload/index.d.ts:3-18` | 调用者被迫使用 `as any` |
| `__BACKEND_URL__` 声明但从未设置 | `preload/index.d.ts:24` | 死类型声明 |
| 后端进程崩溃可能留下孤儿进程 | `main/backend.ts:42-54` | uvicorn reloader 子进程退出时 exit 事件触发 |
| `get-backend-url` 使用同步 IPC | `main/index.ts:110-112` | 主进程忙时阻塞渲染器 |

---

## 6. 前端问题

### 6.1 Vue 响应性与内存泄漏

| 问题 | 文件:行号 | 说明 |
|------|----------|------|
| 日志条目无上限，无限增长 | `stores/log.ts:10` | 长会话内存泄漏 |
| 模块级 `uploadQueue` 跨实例共享 | `components/FileUploader.vue:57` | 多个上传组件交叉污染 |
| 模块级 Map/Set 跨实例共享 | `views/RecognizeView.vue:396-398` | `batchRenderInFlight`、`ownedTaskIds`、`resumingTaskIds` |
| `setTimeout` 未在 unmount 时清理 | `components/AiAssistant.vue:312, 324` | 动画期间卸载组件触发已卸载 ref 的状态更新 |
| `LogPanel` 自动滚动失效 | `components/LogPanel.vue:31` | `logContainer` ref 未在模板中绑定，永远为 undefined |
| `LogPanel` 使用数组索引作为 :key | `components/LogPanel.vue:4` | 日志增删时 DOM 节点错误复用 |
| `assistant.ts` 直接修改响应式对象属性 | `stores/assistant.ts:108` | `target.content += content` 在 Vue 3 Proxy 响应式下可正常追踪，但属于风格问题（建议替换整个对象元素） |
| `JianpuEditor` 自动格式化覆盖历史文本 | `components/JianpuEditor.vue:427-439` | 恢复的历史记录立即被重格式化 |
| `JianpuPlayer` 音量不持久化 | `components/JianpuPlayer.vue:162` | 每次重载重置为 0.8 |
| `JianpuPlayer` MIDI 生成失败静默 | `components/JianpuPlayer.vue:191-207` | 后端宕机时用户无反馈 |

### 6.2 TypeScript 类型安全

| 问题 | 文件:行号 | 说明 |
|------|----------|------|
| 多处 `as any` 状态转换 | `ConvertView.vue:911,1241` | 后端状态字符串无验证转换为前端联合类型（`RecognizeView.vue` 无此问题） |
| 多处 `(window as any).api` | `ConvertView.vue:1419`、`settings.ts:321,330,379,395` 等 | preload 类型不完整导致 |
| `completed.result as T` 不安全泛型转换 | `RecognizeView.vue:1054` | SSE 结果类型 `unknown` 无验证转换为 `T` |

### 6.3 错误处理缺失

| 问题 | 文件:行号 | 说明 |
|------|----------|------|
| EfficiencyDashboard 静默吞错误 | `EfficiencyDashboard.vue:93-99` | API 错误不显示给用户 |
| HistoryQuickEntry 静默吞错误 | `HistoryQuickEntry.vue:84-91` | 同上 |
| `deleteSession` 无 try/catch | `stores/assistant.ts:59-67` | 未捕获的 Promise 拒绝 |
| `_pdf_to_images` 静默返回 None | `exec/files/actions.py:73-74` | PDF 转换失败用户无反馈 |
| 多处 `except Exception: return None` | `exec/pipeline/actions.py:471-473`、`exec/recognize/actions.py:133-144` | 调试困难 |

### 6.4 播放器问题

| 问题 | 文件:行号 | 说明 |
|------|----------|------|
| 仅使用第一个速度标记 | `composables/usePlayer.ts:99` | MIDI 速度变化不生效 |
| 自动停止可能截断最后一个音符 | `composables/usePlayer.ts:270-274` | requestAnimationFrame ~16ms 粒度导致超调 |
| 去重键使用前 50 字符 | `components/JianpuPlayer.vue:168` | 相同前缀的不同简谱导致播放旧 MIDI |

### 6.5 SVG 预览问题

| 问题 | 文件:行号 | 说明 |
|------|----------|------|
| 归一化坐标检测启发式脆弱 | `SvgPreview.vue:166` | 所有值 ≤1.5 的像素坐标被误判为归一化 |
| 15 秒超时不区分超时与网络错误 | `SvgPreview.vue:367` | 统一显示"SVG 加载失败" |
| `getBBox()` 在未渲染时抛异常 | `SvgPreview.vue:470-477` | try/catch 静默返回 |

---

## 7. 代码质量问题

### 7.1 大规模代码重复

| 重复 | 位置 | 说明 |
|------|------|------|
| AI provider `transcribe_page` | `ai/providers/dashscope.py`、`openai_compatible.py`、`xiaomi_mimo.py` | 三份 ~95% 相同代码 |
| HTTP `chat_completions` | `ai/providers/_http.py` 和 `ocr/providers/_http.py` | 几乎完全相同 |
| `persisted_*_settings` | `ai/core/prompts.py` 和 `ocr/core/utils.py` | 相同模式 + 相同异常吞咽 |
| 渲染主函数 | `main.py:77-168` 和 `main.py:184-261` | ~80 行近乎相同的代码 |
| 渲染 schema 字段 | `models/render/schemas.py` | 4 个 schema 重复相同字段 |
| SVG 转 PNG/JPEG | `api/export.ts:51-73` | 两个函数逻辑几乎相同 |

### 7.2 魔法数字泛滥

渲染服务中遍布未命名的魔法数字：`26`（content_x 偏移）、`56`（内容宽度缩减）、`28`（八度点偏移）、`50/58`（小节线范围）、`160`（行高）、`18/20`（文本车道间距）等。`domain/text_placement.py` 中 A4 尺寸和边距全部硬编码为 150 DPI。

### 7.3 巨型函数/文件

| 文件 | 行数 | 问题 |
|------|------|------|
| `domain/parse/jianpu_text.py:175-422` | 247 行 | `parse_jianpu_score` 含 ~19 个 nonlocal 变量的嵌套闭包 |
| `services/render/main.py` | 1133 行 | 渲染主入口过大 |
| `exec/render/actions.py` | 1276 行 | 渲染执行层过大 |
| `desktop/.../RecognizeView.vue` | 2551 行 | 单组件过大 |
| `desktop/.../ConvertView.vue` | 2340 行 | 单组件过大 |
| `desktop/.../SyntaxView.vue` | 1208 行 | 单组件过大 |

### 7.4 死代码

| 文件:行号 | 说明 |
|----------|------|
| `services/ocr/client/client.py` 全文 | `build_request` 和 `send_request` 无调用者，实际使用 `providers/_http.py` |
| `services/render/drawing/beat.py:20-35` | `_render_beat_items` 无调用者 |
| `services/render/utils/articulations.py:13-38` | `_render_articulation` 无调用者 |
| `services/render/utils/positioning.py:48-55` | `_upper_mark_anchor_y` 无调用者 |
| `services/render/layout/measure.py:115-116` | 冗余赋值和重复导入 |
| `services/recognize/external_tools.py:77` | `config.audiveris_path or "audiveris"` 的 `or` 分支永不执行 |

### 7.5 不一致的 API 设计

- `jianpu_to_musicxml` 不接受 `accidental_mode` 但 `musicxml_to_jianpu` 接受 — 不对称 API
- `ExportMusicXmlRequest.target_key` 使用 `str` 而非 `TargetKey` Literal — 无验证
- `JianpuToMusicXmlRequest` 的 `jianpu_text` 和 `jianpu_file_id` 均可选但无"至少一个必填"验证
- `pipeline/routes.py:63-64` 的 `show_measure_numbers` 和 `measure_number_mode` 双向耦合 — 令人困惑的行为
- `app.py:102-107` 全局 `ValueError` 处理器总是标记 `stage: "convert"` — 误导性错误响应
- `history/routes.py` 使用 `def`（同步）而其他路由使用 `async def` — 不一致

---

## 8. 测试覆盖问题

### 8.1 严重覆盖缺口

| 缺口 | 说明 |
|------|------|
| 无 MuseScore PDF/PNG 导出测试 | README 称为核心功能但完全未测试 |
| 无前端组件/E2E 测试 | `desktop/AGENTS.md` 提到 vitest 但未配置 |
| `test_composition.py` 仅 13 行 | 整个 composition 模块只有一个测试 |
| 无 OCR/AI 错误处理测试 | HTTP 失败、超时、畸形响应均未测试 |
| 无 `/recognize` 或 `/pipeline` 实际执行测试 | 仅检查 schema 属性 |
| 无并发测试 | 任务管理器、文件上传、历史 DAO 的竞态条件未测试 |
| 无导出错误处理测试 | 无效 MusicXML、文件缺失、MuseScore 未找到 |

### 8.2 脆弱断言

**`tests/test_render.py`（1681 行，最脆弱的测试文件）：**
- 15+ 处魔法数字坐标断言（`stroke-width="3.0"`、`y > float(...) - 64`、`40.0 < y <= 64.0` 等）
- SVG 解析使用字符串分割（`line.split('y="')[1].split('"')[0]`）而非 `xml.etree.ElementTree`
- SVG path `d` 属性通过空格分割解析（`accent.attrib["d"].split()[2]`）

**`tests/test_recognize_external_tools.py:136-160`：** 精确命令行参数列表按精确顺序硬编码。

**`tests/test_overlay.py`：** 完全依赖一个提交的二进制 fixture 文件，断言精确像素尺寸（2396×3650）。

**`tests/test_text_attachments.py:82,107`：** 精确浮点数断言（`relative_y == 0.41875`）。

### 8.3 架构测试允许已知违规

`tests/test_architecture.py` 接受 7 个已知层级违规 + 7 个已知 FastAPI 导入违规，无清理强制机制。

---

## 9. 构建与 CI 问题

### 9.1 CI 缺失步骤

| 缺失 | 说明 |
|------|------|
| 无 `ruff format --check` | 代码格式未在 CI 中验证（仅有 `ruff check`） |
| 无覆盖率测量 | 无 `--cov` 报告 |
| 无安全扫描 | 无 `pip-audit` 或 `npm audit` |
| 无多平台/多版本测试 | 仅 Python 3.13 / Windows |

### 9.2 依赖管理问题

| 问题 | 说明 |
|------|------|
| `requirements.txt` 完全重复 `pyproject.toml` | 维护负担，可能不同步 |
| `pytest>=8` 在 `requirements.txt` 中列为运行时依赖 | 应仅限开发 |
| `pyproject.toml` 要求 `>=3.11` 但 CI 仅测试 3.13 | 可能无意中使用 3.14+ 特性 |
| Electron 33 过时 | 当前稳定版 35+ |
| 无 `[tool.ruff]` 配置 | lint 规则未版本控制 |

### 9.3 文档问题

| 问题 | 文件:行号 | 说明 |
|------|----------|------|
| 截图占位符 TODO 未完成 | `README.md:11-12` | `<!-- TODO: 替换为真实截图 -->` |
| MuseScore PDF/PNG 导出未测试但 README 宣传 | `README.md:20` | 功能声明与测试覆盖不匹配 |
| `env.example` 缺少 `SCORE_TRANS_WORKDIR` 等 | `config/env.example` | 用户无法找到工作目录配置方式 |
| `ai_prompt.yaml` 用 ✅ 标记失败示例 | `config/ai_prompt.yaml:205-213` | 矛盾且混淆 LLM |

---

## 10. 问题统计汇总

### 按严重程度分类

| 严重程度 | 数量 | 典型问题 |
|---------|------|---------|
| **P0 — 数据丢失/崩溃** | 11 | 缓存清理删引用文件、时值往返失败、双重移除崩溃、空渲染页面 IndexError |
| **P1 — 音乐理论错误** | 13 | 等音拼写丢失、双变音丢失、重复记号丢失、共享编号嵌套连音缺陷、八度点不堆叠 |
| **P1 — 安全漏洞** | 6 | 无认证、SSRF、路径遍历、SVG 渲染（~4.4 XSS 经复查不成立） |
| **P2 — 功能缺陷** | 39+ | @text 未实现、多声部不输出、设置无法修改 base_url、各种解析缺陷 |
| **P2 — 架构违规** | 7 | models 导入 config（3处）、exec HTTPException（3处）、异步路由同步调用（4处） |
| **P3 — 前端问题** | 25+ | 内存泄漏、类型不安全、错误处理缺失、播放器缺陷 |
| **P3 — 代码质量** | 20+ | 大规模重复、魔法数字、巨型函数、死代码 |
| **P3 — 测试缺口** | 15+ | 无前端组件测试、render 测试脆弱、composition 仅 1 测试 |
| **P3 — 构建/CI** | 9+ | 无 `ruff format --check`、无覆盖率、依赖重复、Electron 过时 |

### 按子系统分布

| 子系统 | Bug | 缺陷 | 质量 | 安全 | 架构 |
|--------|-----|------|------|------|------|
| domain/ (解析/生成) | 8 | 12 | 5 | 0 | 0 |
| services/render/ | 5 | 10 | 8 | 0 | 0 |
| services/ai/ | 4 | 6 | 5 | 0 | 0 |
| services/ocr/ | 2 | 4 | 3 | 1 | 0 |
| services/recognize/ | 1 | 2 | 3 | 1 | 0 |
| services/overlay/ | 1 | 2 | 2 | 0 | 0 |
| services/storage/ | 1 | 1 | 2 | 0 | 0 |
| services/tasks/ | 2 | 2 | 2 | 0 | 0 |
| services/export/ | 2 | 3 | 1 | 0 | 0 |
| services/files/ | 0 | 2 | 2 | 1 | 0 |
| services/settings/ | 1 | 3 | 1 | 0 | 0 |
| dao/ | 2 | 5 | 4 | 0 | 1 |
| models/ | 1 | 4 | 3 | 0 | 2 |
| config/ | 2 | 2 | 1 | 0 | 1 |
| api/ | 2 | 6 | 4 | 1 | 2 |
| exec/ | 2 | 5 | 5 | 0 | 3 |
| utils/ | 2 | 2 | 3 | 0 | 0 |
| frontend (Vue/TS) | 15 | 10 | 8 | 2 | 0 |
| Electron (main/preload) | 2 | 4 | 2 | 2 | 0 |
| tests/ | — | 15+ | 5 | 0 | 0 |
| build/CI | — | 10+ | 3 | 0 | 0 |

### 建议修复优先级

**立即修复（P0）：**
1. 缓存清理补全所有文件 ID 引用（`cache_service.py`）
2. 简谱时值标记 `whole` vs `whole-1` 连字符计算（`jianpu_tokens.py`）
3. TaskManager 订阅者双重移除（`task_service.py`）
4. pipeline 空渲染页面保护（`pipeline/actions.py`）
5. 应用关闭死循环（`app.py`）

**短期修复（P1）：**
6. 简谱→MusicXML 等音拼写修复（`write/musicxml.py`）
7. MusicXML→简谱双变音记号保留（`parse/musicxml.py`）
8. 重复记号/结尾段处理（解析 + 生成）
9. 八度点垂直堆叠（`render/utils/metrics.py`）
10. SVG 渲染加固（`SvgPreview.vue` sanitize 补全）
11. 路径遍历防护（Electron files.ts）

**中期改进（P2-P3）：**
12. AI provider 代码去重
13. 巨型 Vue 组件拆分
14. 测试覆盖补充（MuseScore 导出、前端组件、错误处理）
15. CI 补全 `ruff format --check` 和覆盖率
16. 魔法数字提取为命名常量
17. 架构违规清理

---

*报告结束。共审计 310 个源文件，约 43,500 行代码，发现 150+ 个问题（经复查 3 条不成立，实际有效问题约 147 个）。*
