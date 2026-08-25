# Score Trans 全面功能调研报告

> 调研日期：2026-08-26
> 基线：`786 passed, 1 skipped`（后端全量测试通过）
> 方法：逐功能代码审查 + 交叉使用场景分析
> 范围：Convert / Recognize / Render / Pipeline / AI / Export / History / Settings / Files / Correct / Syntax / 前端

---

## 一、执行摘要

本次调研对 Score Trans 的全部功能进行了逐一代码审查，并模拟了现实中的交叉、混乱使用场景。**所有现有自动化测试（786 项）均通过**，说明已覆盖的行为无回归。但通过代码路径直接分析，共发现 **58 个已确认 bug**、约 **80 个潜在风险**、以及大量测试缺口。

这些 bug 中，大多数集中在以下三类场景：
1. **边缘输入**（空字符串、损坏文件、非 UTF-8 编码、超大输入、极端时值/八度）
2. **并发与生命周期**（多请求并发、后台任务取消、组件卸载竞态、关闭流程）
3. **跨功能交叉使用**（recognize→convert→render→export 链路中的状态/资源不一致）

**核心结论**：软件在"正常单功能使用"下基本可用，但在"交叉、混乱、极端"使用下存在多个可触发的崩溃、数据丢失、资源泄漏和音乐语义错误。最关键的风险集中在 **OMR 子进程无超时**（可拖垮整个后端）、**file_id 目录穿越**（安全漏洞）、**OCR 失败致全流程失败**（非降级）、以及 **MIDI 导出忽略连音线**（音乐语义错误）。

---

## 二、Bug 汇总表（按优先级排序）

### P0 — 严重（可崩溃 / 安全漏洞 / 数据丢失）

| ID | 功能 | 文件:行号 | 触发条件 | 影响 |
|----|------|-----------|----------|------|
| B-REC-1 | Recognize | `services/recognize/external_tools.py:48` | Audiveris 进程挂起 | subprocess.run 无超时，OMR 信号量永久占用，2 个挂起即饿死所有 OMR 请求 |
| B-REC-3 | Recognize | `services/files/image_info.py:8-24` | 上传 WebP/TIFF/BMP | 尺寸误读为 1600×1200，大图直接送 Audiveris 可致 JVM OOM |
| B-HSF-2 | Files | `api/files/routes.py:35` + `upload_service.py:227` | `GET /files/..` | 目录穿越，可读取 uploads 父目录任意文件（含 settings.db API key） |
| B-HSF-1 | Settings | `dao/settings/settings_dao.py:46` | 并发设置写入 | SettingsDao 无 WAL/busy_timeout，并发写报 "database is locked" → 500 |
| B-CON-1 | Convert/Pipeline | `exec/convert/actions.py:84` | OCR 启用但 API 失败 | OCR 异常非降级，整个 convert/pipeline 返回 502，丢弃已成功的 OMR+转换结果 |
| B-CON-2 | Convert | `domain/xml_utils.py:49` | 损坏 MXL（无 XML 成员） | `next()` 无默认值 → StopIteration → 500 |
| B-EXP-1 | Export | `services/export/export_service.py:236` | 含连音线的乐谱导出 MIDI | MIDI 不处理 tie，连音符被重新触发，音乐语义错误 |
| B-EXP-6 | Export | `services/export/export_service.py:64-93` | 图片→PDF 导出异常 | `images_to_pdf` 无 try/finally，fitz 文档对象泄漏 |
| B-COR-6 | Correct | `api/correct/routes.py:29` + `safe_xml.py` | 空/损坏 MusicXML | ET.ParseError（SyntaxError 子类）无 handler → 500 |
| B-EXP-4 | Export | `services/export/export_service.py:203` | 任何 MIDI 导出 | 缺 end_of_track meta，违反 MIDI 1.0 规范 |
| B-REN-4 | Render | `exec/render/actions.py:952` | `source_page_index` 极大值 | `range(max_index+1)` 巨型列表分配 → 内存爆炸/崩溃 |
| B-REN-6 | Render | `engraving/renderer.py:1347` | 超大 duration 值 | 扩展线循环空转上亿次，单事件卡死线程 |

### P1 — 高（功能错误 / 资源泄漏 / 用户体验严重受损）

| ID | 功能 | 文件:行号 | 触发条件 | 影响 |
|----|------|-----------|----------|------|
| B-REC-2 | Recognize | `image_preprocess.py:47-83` | 降采样后再放大同路径 | Windows PermissionError，预防性放大静默失败 |
| B-REC-4 | Recognize | `exec/recognize/actions.py:105` | 每次 recognize | omr_dir 临时目录永不清理，磁盘累积泄漏 |
| B-REC-5 | Recognize | `overlay_service.py:99` | 多页 PDF/多 sheet | 仅注册第一个 overlay，后续页面丢失 |
| B-CON-4 | Convert | `domain/jianpu.py:49` | 非 UTF-8 简谱文件 | UnicodeDecodeError，UTF-16 BOM 文件无法处理 |
| B-CON-6 | Convert | `domain/write/musicxml.py:670` | 64 分音符及更短 | `<type>` 错写为 quarter，解析器与写入器不对称 |
| B-AI-1 | AI | `utils/json_parsing.py:46` | LLM 返回截断 JSON 且 finish_reason 非 length | 静默修复为合法 JSON，产出不完整简谱无告警 |
| B-AI-2 | AI | `services/ai/transcription/merging.py:63` | 多页乐谱中途转调/转拍 | strip_header 误删中部 `1=G`/`3/4`，合并后调号错误 |
| B-AI-3 | AI | `exec/ai/actions.py:52` | 转录失败 | 临时 PNG 不清理，磁盘累积 |
| B-AI-4 | AI | `api/tasks/routes.py` + `app.py:194` | 用户取消/应用关闭 | 无取消端点；关闭时无超时等待后台任务 |
| B-EXP-2 | Export | `export_service.py:236` | 同 part 多 voice 的 MusicXML | MIDI 忽略 event.start，多声部被串行播放 |
| B-EXP-7 | Export | `export_service.py:84` | PNG→PDF 多页大图 | pixmap 解码致内存放大，50 页可达 1.3GB |
| B-HSF-3 | Files | `exec/files/actions.py:93` | 删除被历史引用的 file_id | 不检查引用，产生悬挂引用，历史页 404 |
| B-HSF-5 | Files | `upload_service.py:156` | 并发上传 | _persist_index 丢失更新竞态，索引与磁盘漂移 |
| B-HSF-7 | Storage | `cache_service.py:41` | 清缓存时后台任务运行 | 无条件删 scratch 目录，进行中任务崩溃 |
| B-COR-1 | Correct | `musicxml_patch.py:59` | 并发 correct 请求 | ET.register_namespace 全局竞态，命名空间错乱 |
| B-COR-5 | Correct | `musicxml_patch.py:239` | 删除 part 首个谱号 | 硬编码默认 G2 高音谱号，F4 谱号删除后音高全错 |
| B-FE-1 | 前端 | `stores/workspace.ts:884` | 删除当前页且新页属不同批次 | currentBatchId 不一致，导航和批次文本错误 |
| B-FE-2 | 前端 | `stores/workspace.ts:470` | setInputFile 清空派生状态 | 顶层 ref（sourceMapFileId 等）不同步，UI 误显编辑按钮 |
| B-FE-3 | 前端 | `PublicationPreview.vue:619` | 拖拽中卸载组件 | body.userSelect 永久为 none，全应用无法选中文本 |

### P2 — 中（边缘崩溃 / 性能 / 一致性）

| ID | 功能 | 文件:行号 | 触发条件 | 影响 |
|----|------|-----------|----------|------|
| B-CON-3 | Convert | `xml_utils.py:37` | MXL container.xml 含 ENTITY | UnsafeXmlError 未捕获，降级逻辑被跳过 |
| B-CON-5 | Convert | `exec/convert/actions.py:177` | register 失败 | 孤儿文件残留 |
| B-REC-6 | Recognize | `external_tools.py:89` | 重试再次失败 | 不调用 _summarize，用户只看到原始错误 |
| B-REC-7 | Recognize | `external_tools.py:470` | EXTRA_ARGS 含 Windows 路径 | shlex.split 吞反斜杠 |
| B-REC-8 | Recognize | `external_tools.py:116` | 路径含逗号 | Gradle cmdLineArgs 拆分错位 |
| B-REN-1 | Render | `render/main.py:197` | 文件输出路径 | initial_measure_number 被丢弃 |
| B-REN-2 | Render | `exec/render/actions.py:459` | 批量渲染 | 同一组分数渲染两次，性能翻倍 |
| B-REN-3 | Render | `exec/render/actions.py:349` | jianpu-text-svg 异常 | 临时 .txt 文件泄漏 |
| B-REN-5 | Render | `renderer.py:203` | 渲染中崩溃/磁盘满 | SVG 与 render-map 非原子写入 |
| B-REN-7 | Render | `renderer.py:1326` | 极大 octave 值 | 八度点循环无上限，O(N²) 内存 |
| B-EXP-3 | Export | `export_service.py:212` | 任何 MIDI | 缺 key_signature meta |
| B-EXP-5 | Export | `export_service.py:203` | 多声部 MIDI | 无 program_change/channel 分配，全 channel 0 |
| B-HSF-4 | History | `history_dao.py:735` | update_page 清空 svg | engine_version 仍写非空值，与 save_batch 不一致 |
| B-HSF-6 | Settings | `exec/settings/actions.py:46` | 多字段更新中途失败 | 非原子，半更新状态无回滚 |
| B-COR-2 | Correct | `musicxml_patch.py:65` | 大型 MusicXML + 多删除 | O(k·n²) 性能 |
| B-COR-3 | Correct | `musicxml_patch.py:65` | id 存在子串包含 | 误报"定位不唯一" |
| B-COR-4 | Correct | `musicxml_patch.py:232` | 空 `<line>` 元素 | int("") 崩溃 |
| B-COR-7 | Syntax | `schemas.py:20` | 超大 jianpu_text | 无输入上限，DoS |
| B-FE-4 | 前端 | `stores/assistant.ts:202` | 流式中切换会话再切回 | onDone 与 finally 竞态，显示错误会话消息 |
| B-FE-5 | 前端 | `RecognizeView.vue:1376` | 批次渲染中卸载 | 后台渲染仍写 store |
| B-FE-6 | 前端 | `ConvertView.vue:573` | 卸载时 entityLoadController 未 abort | 卸载后回调仍执行 |
| B-FE-7 | 前端 | `JianpuEditor.vue:409` | 粘贴含多个 `\|` | 只有最后一个 `|` 自动换行 |

### P3 — 低（文案 / 轻微 UX）

详见各功能域报告，此处略。

---

## 三、交叉使用场景分析

以下是现实中"交叉、混乱使用"的场景及其 bug 触发点。

### 场景 1：反复识别同一张谱子（recognize × N）

**用户行为**：识别一张谱子→结果不满意→改设置→再识别→再改→再识别...

**触发 bug**：
- **B-REC-4**：每次 recognize 创建 `work_dir/audiveris/{uuid}` 不清理。反复识别 10 次后 `audiveris/` 下有 10 个目录（每个含 .omr 几十 MB），磁盘占满后新识别因 `mkdir` 失败报错。
- **B-REC-1**：若某次 Audiveris 挂起（如 JVM OOM），`OMR_SEMAPHORE(2)` 永久占用 1 个槽位。再识别 1 次又挂起 → 2 个槽位全满 → **所有后续 recognize/pipeline 永久排队**。
- **RISK**：Gradle 缓存争用（2 个并发 OMR 共享 GRADLE_USER_HOME）。

**建议**：为 subprocess 加 timeout；在 recognize_from_path 的 finally 中清理 omr_dir。

### 场景 2：识别→转换→渲染→导出 全链路（pipeline 一键流程）

**用户行为**：上传一张图片→一键 pipeline→得到 SVG→导出 MIDI→播放

**触发 bug**：
- **B-CON-1**：若 OCR 启用但 API key 无效/网络超时，**整条 pipeline 失败**。已成功的 OMR+convert+render 全部丢弃，用户只看到 FAILED。对比：overlay/omr 查找失败会降级，唯独 OCR 不降级。
- **B-EXP-1**：导出的 MIDI 不处理连音线（tie），跨小节延音线被拆成两个独立音符重新击发，播放效果错误。
- **B-EXP-2**：若原谱含多 voice（钢琴左右手同 part），MIDI 忽略 event.start，声部被串行播放。
- **B-EXP-3**：MIDI 无 key_signature，播放器显示 C 大调而非实际调号。
- **B-REC-5**：多页 PDF 的 pipeline，overlay 只注册第一页，后续页无叠加层。

**建议**：OCR 失败应降级（与 overlay 一致）；MIDI exporter 应处理 tie、event.start、key_signature。

### 场景 3：编辑简谱→转回 MusicXML→再编辑（往返一致性）

**用户行为**：识别得到简谱→手动修改简谱文本→转回 MusicXML→再转简谱→对比

**触发 bug**：
- **B-CON-6**：若简谱含 64 分音符，MusicXML 写入器 `_fraction_to_type` 只到 32nd，64 分音符被写为 quarter，往返后时值错误。
- **B-CON-4**：若用户上传的简谱文件是 GBK/UTF-16 编码，`read_text(encoding="utf-8")` 崩溃。
- **RISK**：嵌套连音线被丢弃（简谱格式不支持嵌套）；多 staff 钢琴谱拆分不可逆；调号中途变更不传播到 target_key。
- **RISK**：变音记号模式切换后，`pitch_spelling` 重新选择音名，往返后 step/alter 可能不同。

**建议**：补全 `_fraction_to_type` 到 256th；简谱文件读取用 `utf-8-sig` 或先检测编码。

### 场景 4：同时做多个操作（并发）

**用户行为**：识别中→同时打开另一个谱子开始转换→同时导出上一个的 MIDI→同时清缓存

**触发 bug**：
- **B-HSF-1**：并发设置写入 → SettingsDao 无 WAL → "database is locked" → 500。
- **B-HSF-5**：并发上传 → `_persist_index` 丢失更新 → 索引与磁盘漂移。
- **B-HSF-7**：清缓存时后台任务运行 → scratch 目录被删 → 进行中任务崩溃。
- **B-COR-1**：并发 correct → `ET.register_namespace` 全局竞态 → 命名空间错乱。
- **B-REN-1（风险1）**：首次并发渲染 → font_registry lru_cache 竞态 + TTFont 懒加载非线程安全。
- **B-REC-1**：2 个 OMR 同时挂起 → OMR_SEMAPHORE 饿死。
- **B-AI（RISK-2）**：多个 AI 转录并发 → 无信号量限制 → 耗尽默认线程池。

**建议**：SettingsDao 启用 WAL + busy_timeout；为 AI 转录加信号量；CacheService.clear 检查后台任务状态。

### 场景 5：识别→删除标记→重新渲染（correct 链路）

**用户行为**：识别得到简谱→发现谱号识别错→删除错误谱号→重新渲染

**触发 bug**：
- **B-COR-5**：删除 part 的第一个谱号 → 硬编码默认 G2 → 若实际是 F4，后续音符音高全错。
- **B-COR-4**：若 MusicXML 含空 `<line></line>` → `int("")` 崩溃 → 400。
- **B-COR-6**：若 original_musicxml 为空或损坏 → ParseError → 500。
- **B-COR-2**：大型乐谱 + 多删除 → O(k·n²) → 超时。
- **B-COR-3**：id 子串包含（note-1 vs note-10）→ 误报不唯一 → 修正被拒。
- **RISK-10**：删除小节唯一音符 → 空小节 → render 失败。

**建议**：删除首谱号时应从 MusicXML 的 part-info 或 score-info 获取正确谱号；空元素需防御性处理。

### 场景 6：AI 转录多页 PDF

**用户行为**：上传多页 PDF→AI 转录→得到简谱→编辑→渲染

**触发 bug**：
- **B-AI-1**：某页 LLM 返回截断 JSON 且 finish_reason 非 length → 静默修复 → 产出不完整简谱无告警。
- **B-AI-2**：第 2 页转调到 G → `strip_header` 误删中部的 `1=G` → 合并后调号仍为第 1 页的 C。
- **B-AI-3**：转录失败 → 临时 PNG 不清理。
- **B-AI-4**：用户想取消 → 无取消端点 → 只能等超时。
- **B-AI-5**：某页 5xx → 整个转录失败，无重试，前几页 token 浪费。

**建议**：截断 JSON 修复必须带 warning；strip_header 只剥头部不剥中部；加重试/退避。

### 场景 7：快速切换页面 + 点击高亮（前端竞态）

**用户行为**：识别多页谱子→快速切页→点击左侧某个音符→右侧高亮

**触发 bug**：
- **B-FE-3**：若在拖拽 OCR block 时切换视图 → body.userSelect 永久 none → 全应用无法选中文本。
- **B-FE-1**：删除当前页后新页属不同批次 → currentBatchId 不一致 → 导航失效。
- **RISK（已修复 R2）**：快速切页后点击高亮 → LatestAsyncGate 已修复此问题。
- **B-FE-2**：切换页面后 sourceMapFileId 等 ref 不同步 → "删除标记"按钮误可点。
- **B-REC-5**：多页 overlay 只注册第一页 → 后续页无叠加层可高亮。

**建议**：removePage 后基于当前页重新计算 currentBatchId；clearDerived 同步所有顶层 ref。

### 场景 8：上传各种格式的文件

**用户行为**：上传 PNG/JPEG/PDF/WebP/TIFF/BMP/MXL/非 UTF-8 文本/超大文件/损坏文件

**触发 bug**：
- **B-REC-3**：WebP/TIFF/BMP → 尺寸误读 1600×1200 → 大图直接送 Audiveris → OOM。
- **B-CON-2**：损坏 MXL → StopIteration → 500。
- **B-CON-3**：MXL container.xml 含 ENTITY → UnsafeXmlError 未捕获。
- **B-CON-4**：非 UTF-8 简谱 → UnicodeDecodeError。
- **B-HSF-2**：`GET /files/..` → 目录穿越。
- **RISK**：零字节文件、Windows 保留设备名（CON/PRN）、路径穿越（../）。
- **RISK**：16-bit PNG、CMYK JPEG 的色彩处理。

**建议**：image_dimensions 增加 WebP/TIFF/BMP 解析或统一用 PIL；file_id 路由层加格式校验（`^[a-f0-9]{12}$`）。

### 场景 9：长时间使用后磁盘/内存增长

**用户行为**：使用数小时，反复识别/转换/渲染/导出

**触发 bug（累积）**：
- **B-REC-4**：`work_dir/audiveris/` 下 UUID 目录累积（每次几十 MB）。
- **B-AI-3**：`work_dir/ai_transcribe/` 下 PNG 累积。
- **B-CON-5 / B-EXP（RISK-3）**：convert/export 失败时孤儿文件残留。
- **B-REN-3**：render 失败时临时 .txt 泄漏。
- **B-HSF-5**：索引漂移导致文件存在但 index 无记录（或反之）。
- **RISK（R11）**：AI 转录的 PNG 双份存储（scratch + uploads）。

**建议**：所有 scratch 目录在任务完成/失败后清理；定期自动 prune。

### 场景 10：应用关闭时的行为

**用户行为**：识别/AI 转录进行中→关闭应用

**触发 bug**：
- **B-AI-4**：`_wait_for_background_tasks` 无超时 → 等 5 分钟的 AI 转录完成才退出。
- **B-REC-1**：Audiveris subprocess 在线程中，asyncio 无法取消 → 关闭流程挂起。
- **B-FE-5/6**：前端组件卸载后后台回调仍执行 → 写已关闭的后端。
- **RISK**：OCR 的 httpx 同步调用在 to_thread 中无法被 asyncio 取消。

**建议**：`_wait_for_background_tasks` 加 `asyncio.wait_for` 超时；subprocess 加 timeout。

---

## 四、各功能域详细发现

### 4.1 Convert（MusicXML ↔ 简谱互转）

**已确认 bug**：6 个
- OCR 失败非降级（B-CON-1，P0）
- 损坏 MXL StopIteration（B-CON-2，P0）
- MXL container.xml 不安全内容（B-CON-3，P2）
- 非 UTF-8 简谱文件（B-CON-4，P1）
- register 失败孤儿文件（B-CON-5，P2）
- 64 分音符写入错误（B-CON-6，P1）

**关键风险**：并发 OCR 耗尽线程池；file_id TOCTOU；多 staff 拆分丢歌词；嵌套连音线丢失；调号中途变更不传播；超大 divisions。

### 4.2 Recognize（OMR 识别）

**已确认 bug**：8 个
- subprocess 无超时（B-REC-1，P0）
- source==dest 覆盖写入（B-REC-2，P1）
- WebP/TIFF/BMP 尺寸误读（B-REC-3，P0）
- omr_dir 不清理（B-REC-4，P1）
- 多 sheet overlay 丢失（B-REC-5，P1）
- 重试失败不 summarize（B-REC-6，P2）
- shlex.split Windows 路径（B-REC-7，P2）
- 逗号拼接 cmdLineArgs（B-REC-8，P2）

**关键风险**：大图 OOM；Gradle 缓存争用；log stat TOCTOU；无 JDK 版本校验；无文件类型校验；stderr 含错误但 exit 0 静默忽略。

### 4.3 Render（简谱 SVG 渲染）

**已确认 bug**：7 个
- initial_measure_number 文件路径丢弃（B-REN-1，P2）
- 批量双重渲染（B-REN-2，P2）
- 临时 .txt 泄漏（B-REN-3，P2）
- source_page_index 巨型列表（B-REN-4，P0）
- 文件写入非原子（B-REN-5，P2）
- 超长 duration 循环无上限（B-REN-6，P0）
- 八度点循环无上限（B-REN-7，P2）

**关键风险**：字体注册表全局单例并发不安全；几何 QA O(N²)；pitch_layouts O(N²)；单系统超高分页溢出；jianpu_text 无长度限制；OCR 放置硬编码坐标。

### 4.4 Pipeline（一键全流程）

**已确认 bug**：3 个
- OCR 失败致全流程失败（= B-CON-1，P0）
- 失败时 output_dir 不清理（B-PIPE-2，P1）
- 注册非原子（B-PIPE-3，P2）

**关键风险**：Audiveris 无超时（= B-REC-1）；RUNNING 任务无 TTL；PDF 不走 OCR（与手动流程不一致）；双倍存储；OCR 占 OMR 信号量。

### 4.5 AI Transcribe

**已确认 bug**：6 个
- 截断 JSON 静默修复（B-AI-1，P0）
- strip_header 误删中部调号（B-AI-2，P0）
- 失败路径 PNG 不清理（B-AI-3，P1）
- 无取消机制（B-AI-4，P1）
- 无重试/退避（B-AI-5，P1）
- 流式断连丢消息（B-AI-6，P1）

**关键风险**：looks_like_jianpu_text 误判；无并发上限；persisted_ai_settings 吞异常；image_to_data_url 硬编码 2000px；聊天与转录共用 timeout；无 token 计数。

### 4.6 Export（MIDI/PDF/PNG 导出）

**已确认 bug**：7 个
- MIDI 不处理 tie（B-EXP-1，P0）
- MIDI 忽略 event.start（B-EXP-2，P1）
- 缺 key_signature（B-EXP-3，P2）
- 缺 end_of_track（B-EXP-4，P0）
- 无 program_change/channel 分配（B-EXP-5，P2）
- images_to_pdf 无 try/finally（B-EXP-6，P0）
- PNG 路径 pixmap 内存放大（B-EXP-7，P1）

**关键风险**：_strip_invisible_text 正则不完整；无背景 SVG 导出全黑；临时文件不清理；部分成功孤儿文件；MIDI 时值截断漂移；export_pdf 全量内存缓冲。

### 4.7 History / Settings / Files

**已确认 bug**：7 个
- SettingsDao 无 WAL（B-HSF-1，P0）
- file_id 目录穿越（B-HSF-2，P0）
- delete_file 不检查引用（B-HSF-3，P1）
- update_page engine_version 不一致（B-HSF-4，P2）
- _persist_index 丢失更新（B-HSF-5，P1）
- update_settings 非原子（B-HSF-6，P2）
- CacheService 破坏运行态（B-HSF-7，P1）

**关键风险**：HistoryDao 多数写方法未用 BEGIN IMMEDIATE；prune TOCTOU；index.json 损坏后 cleanup 静默；PDF fitz doc 未关闭；delete_batch 不清理文件；request 超限仍保存部分文件。

### 4.8 Correct / Syntax

**已确认 bug**：7 个
- register_namespace 全局竞态（B-COR-1，P1）
- O(k·n²) 性能（B-COR-2，P2）
- 子串匹配误报（B-COR-3，P2）
- int("") 崩溃（B-COR-4，P2）
- 删首谱号默认 G2（B-COR-5，P1）
- ParseError → 500（B-COR-6，P0）
- 无输入上限（B-COR-7，P0）

**关键风险**：空小节破坏 correct→render；宽泛 except 掩盖 bug；正则解析错误消息文本；语法截断边界跳变；后代启发式误删。

### 4.9 前端组件与状态管理

**已确认 bug**：7 个
- removePage currentBatchId 不一致（B-FE-1，P1）
- clearDerived 顶层 ref 不同步（B-FE-2，P1）
- 拖拽卸载 userSelect 永久 none（B-FE-3，P1）
- assistant onDone/finally 竞态（B-FE-4，P2）
- 批次渲染卸载后写 store（B-FE-5，P2）
- entityLoadController 未 abort（B-FE-6，P2）
- 粘贴不自动换行（B-FE-7，P2）

**关键风险**：v-html XSS 攻击面；预览 URL revoke 时序；SSE 回退轮询双重调度；generation token 误吞编辑；svgSanitizer 拒绝 url(#gradient)；端口检测 TOCTOU；模块级 Map 内存泄漏。

---

## 五、测试缺口汇总

| 类别 | 缺口数 | 关键项 |
|------|--------|--------|
| **并发测试** | 全域缺失 | 无并发 convert/recognize/render/correct/settings/upload 测试 |
| **超时/取消测试** | 全域缺失 | 无 subprocess 超时、任务取消、应用关闭测试 |
| **损坏/极端输入** | 大量缺失 | 损坏 MXL/PDF、非 UTF-8 文本、空元素、超大输入、零字节文件 |
| **资源清理** | 大量缺失 | omr_dir/ai_transcribe/pipeline scratch 不清理测试、孤儿文件测试 |
| **前端组件测试** | 全域缺失 | 无 Vitest/Playwright，所有组件交互逻辑无测试 |
| **跨链路集成** | 大量缺失 | correct→render、AI 合并调号、MIDI tie/event.start、多页 overlay |
| **安全测试** | 缺失 | file_id 目录穿越、v-html XSS、svgSanitizer 攻击向量 |
| **性能测试** | 缺失 | 大谱渲染、O(k·n²) correct、大图 OOM |

---

## 六、修复优先级建议

### 第一优先级（P0，立即修复）

1. **B-REC-1**：为 `subprocess.run` 加 `timeout` 参数（如 600s），捕获 `TimeoutExpired` 并 kill 子进程。
2. **B-HSF-2**：file_id 路由层加格式校验（`^[a-f0-9]{12}$`），拒绝 `..` 等非法值。
3. **B-HSF-1**：SettingsDao 启用 WAL + busy_timeout=5000，与 HistoryDao 对齐。
4. **B-CON-1**：`build_scores` 中对 `provider.recognize` 加 try/except，OCR 失败降级为空 blocks。
5. **B-EXP-1**：MIDI exporter 处理 tie，合并连音符为一个持续音符。
6. **B-EXP-6**：`images_to_pdf` 加 try/finally，确保 fitz doc 关闭。
7. **B-COR-6**：为 `safe_xml_fromstring` 的 ParseError 注册异常处理器或包装为 ValueError。
8. **B-REN-4/6**：source_page_index 加 `le` 上限；duration 扩展线循环加 break/上限。

### 第二优先级（P1，尽快修复）

9. **B-REC-3**：image_dimensions 增加 WebP/TIFF/BMP 尺寸解析。
10. **B-REC-4**：recognize_from_path 的 finally 中清理 omr_dir。
11. **B-REC-5**：多 sheet overlay 全部注册。
12. **B-CON-4/6**：简谱文件用 utf-8-sig 读取；补全 _fraction_to_type 到 256th。
13. **B-AI-1/2**：截断 JSON 修复必须带 warning；strip_header 只剥头部。
14. **B-AI-4**：加取消端点；_wait_for_background_tasks 加超时。
15. **B-HSF-3/5/7**：delete_file 检查引用；_persist_index 合并而非替换；CacheService.clear 检查后台任务。
16. **B-COR-1/5**：用局部命名空间注册代替全局；删首谱号从 part-info 获取。
17. **B-FE-1/2/3**：removePage 重算 currentBatchId；clearDerived 同步所有 ref；拖拽卸载恢复 userSelect。

### 第三优先级（P2+，择机修复）

18. 性能优化（O(k·n²) correct、批量双重渲染、字体并发）。
19. 边缘输入防御（空元素、损坏文件、超大输入）。
20. 测试补齐（并发、超时、取消、损坏输入、前端组件）。

---

## 七、结论

Score Trans 在架构设计上表现良好（分层清晰、异步正确使用 `asyncio.to_thread`、统一 `{data, error}` API 契约、安全 XML 解析、路径穿越防护），已有 786 项自动化测试覆盖核心行为。但在以下方面存在系统性弱点：

1. **资源生命周期管理不足**：scratch 目录（audiveris/pipeline/ai_transcribe）、临时文件、fitz 文档对象的清理普遍缺失或仅在成功路径执行。
2. **并发与线程安全不足**：SettingsDao 无 WAL、ET.register_namespace 全局竞态、_persist_index 丢失更新、font_registry lru_cache 竞态。
3. **降级策略不一致**：overlay/omr 查找失败会降级，但 OCR 失败不降级；convert 路径 OCR 失败可重试，pipeline 路径不可。
4. **输入边界防御不足**：file_id 无校验、jianpu_text 无长度限制、duration/octave/source_page_index 无上限、WebP/TIFF 尺寸误读。
5. **超时/取消机制缺失**：subprocess 无超时、后台任务无 TTL、无取消端点、关闭流程无超时。
6. **MIDI 导出音乐语义缺陷**：tie/event.start/key_signature/program_change 全部缺失。
7. **前端测试基础设施缺失**：无 Vitest/Playwright，状态机和组件交互无自动化保护。

建议按第六节的优先级分批修复，每批修复后运行全量测试 + 新增回归测试，确保不引入新问题。

---

*报告完毕。以上所有结论均基于代码路径的直接分析，未修改任何代码。*
