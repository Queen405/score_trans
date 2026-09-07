# Score Trans 内核资源与稳定性调研报告

> 调研日期：2026-09-07  
> 调研目标：降低内存占用、磁盘浪费、卡死与崩溃概率，使应用在长时间、多页面使用场景下保持稳定。  
> 调研范围：Python/FastAPI 后端、Audiveris/JVM 外部进程、文件与任务存储、Electron 主进程、Vue/Pinia 渲染进程。  
> 调研方式：当前工作树静态审计、只读磁盘与 SQLite 盘点、现有测试、隔离复现和轻量内存基线。未启动子代理，未调用外部 AI/OMR 服务。

## 1. 执行摘要

当前没有发现纯 Python 简谱渲染内核存在持续增长的典型堆内存泄漏，但确认存在多处资源生命周期缺口。它们并非都表现为传统意义上的“对象无法回收”，却会产生相同的用户后果：磁盘持续增长、后台工作无法停止、内存峰值过高、界面长时间等待，以及低内存环境下的进程崩溃。

本轮最重要的结论如下：

1. **生成文件缺少所有权和释放时机。** Pipeline scratch、旧 SVG、渲染映射、播放器 MIDI 和导出文件会持续留在缓存中。当前运行目录已经接近 1GB。
2. **任务数据库的过期清理存在跨重启缺口。** 当前 `tasks.db` 中 76 条记录已经全部过期，仍保留约 11MB 的完整结果 JSON。
3. **批量 AI 识别没有并发上限。** 多页面任务会一次性提交，可能形成数十个并行图片处理和 HTTP 请求。
4. **Audiveris 没有执行超时，客户端取消也不能停止底层线程或子进程。** 这是最直接的“任务一直转圈”和退出困难风险。
5. **PDF 上传、预览和图片导出缺少页数、像素与峰值内存预算。** 大 PDF 会同时放大磁盘、Chromium Blob 和 MuPDF 内存压力。
6. **运行任务时仍可清理缓存。** 清理动作可能删除正在写入的工作目录或尚未写入历史的活动文件。

因此，本项目当前更准确的诊断不是“存在一个单点内存泄漏”，而是**临时资源长期持久化、并发缺少背压、取消不贯通、批量操作峰值不受控**。

## 2. 调研基线与现场数据

Electron 当前配置使用：

- 用户数据：`D:\tmp\score_trans\data`
- 缓存目录：`D:\tmp\score_trans\cache`
- `work_dir`：未单独覆盖，使用缓存根目录

只读盘点结果：

| 项目 | 数量/大小 | 说明 |
|---|---:|---|
| 缓存总量 | 约 974MB，9,036 个文件 | 逻辑文件大小约 1,005,490,797 bytes |
| Pipeline scratch | 51 个目录，537 个文件，约 110MB | 每次 pipeline 使用独立 UUID 目录 |
| Uploads | 2,760 个目录，约 486MB | 每个 file ID 一个目录 |
| 历史仍引用的 uploads | 340 个，约 156MB | 引用文件全部存在 |
| 未被历史引用的 uploads | 2,420 个，约 327MB | 只能依赖手动缓存清理回收 |
| Electron 会话缓存 | 约 389MB | HTTP Cache 约 299MB，Code Cache 约 87MB |
| Render 目录 | 约 9MB | 当前清理服务不处理该目录 |
| `tasks.db` | 约 11MB | 76 条记录全部过期，结果 JSON 约 10,997,465 bytes |
| `history.db` | 约 16MB | 13 个批次、50 个历史页面 |

未引用 uploads 的主要构成：

| 类型 | 文件数 | 大小 |
|---|---:|---:|
| SVG | 482 | 约 202MB |
| JSON 渲染/映射数据 | 529 | 约 90MB |
| PNG | 68 | 约 14MB |
| MIDI | 1,231 | 约 10.5MB |
| OMR | 37 | 约 7.3MB |

旧默认目录 `~/.score_trans` 也保留了 2,125 个上传目录，以及 207 条全部过期、结果 JSON 约 5.1MB 的任务记录。这说明问题能够跨目录迁移和应用重启长期积累。

## 3. 风险总览

| 编号 | 严重度 | 结论 | 主要后果 |
|---|---|---|---|
| F1 | 高 | 临时与派生文件持续持久化 | 磁盘膨胀、索引变大、设置页扫描变慢 |
| F2 | 高 | 过期任务跨重启不删除 | `tasks.db` 永久增长、结果在内存驻留 |
| F3 | 高 | AI 无并发限制，OMR 并发内存预算过大 | 内存压力、线程池拥塞、系统换页或崩溃 |
| F4 | 高 | 外部进程无超时，取消不贯通 | 永久运行、退出困难、后台持续耗 CPU |
| F5 | 高 | PDF/图片批处理峰值无约束 | 大文件导致内存和磁盘突增 |
| F6 | 高 | 缓存清理可破坏运行中任务 | 当前任务失败、活动文件丢失 |
| F7 | 中 | 大范围文本差异计算阻塞 UI | 粘贴或整谱替换时明显卡顿 |
| F8 | 中 | HTTP 连接不复用，普通请求无默认超时 | 延迟、连接抖动、loading 长期不结束 |
| F9 | 中低 | 工作区可保留无上限的历史活动批次 | 长会话内存随批次数量增长 |

## 4. 详细发现

### F1. 临时与派生文件持续持久化

三个主要流程都会建立唯一工作目录：

- [`RecognizeActions.recognize_from_path`](../backend/score_trans/exec/recognize/actions.py#L98) 创建 `work_dir/audiveris/<uuid>`。
- [`PipelineActions.run_pipeline_from_path`](../backend/score_trans/exec/pipeline/actions.py#L340) 创建 `work_dir/pipeline/<uuid>`。
- [`AiActions.transcribe_score`](../backend/score_trans/exec/ai/actions.py#L52) 创建 `work_dir/ai_transcribe/<uuid>`。

这些方法成功返回和异常退出时都没有 `try/finally` 回收。产物随后通过 [`UploadService.register`](../backend/score_trans/services/files/upload_service.py#L196) 复制到 `uploads/<file_id>`，所以 scratch 中的原件已经没有继续保留的必要。

更持续的增长来自派生文件：

- 每次重新渲染都会注册新的 SVG 和 render map，历史只引用最新版本。
- [`JianpuPlayer`](../desktop/src/renderer/src/components/JianpuPlayer.vue#L180) 在简谱文本变化后重新请求 MIDI。
- 前端 `filesApi` 只提供存在性查询，没有调用后端现有的 `DELETE /files/{file_id}`。
- 用户导出完成后，后端中转文件仍保留在 uploads。
- 删除历史只删除数据库记录，不立即回收其文件。

当前 2,420 个孤立目录和 327MB 孤立数据直接证实了该生命周期缺口。

**建议：** 将文件明确区分为持久历史资产、活动租约资产和一次性临时资产。任务成功后立即清 scratch；播放器、导出和被替换的渲染结果在消费完成后释放 file ID；启动时和低频后台任务只清理超过安全年龄且没有租约的孤立文件。

### F2. 任务过期清理无法覆盖跨重启记录

任务完成结果会完整序列化到 SQLite，见 [`TaskDao.save`](../backend/score_trans/dao/tasks/task_dao.py#L52)。结果通常包含 MusicXML 文本、简谱文本、页面数组和映射。

启动时 [`TaskDao.load_active`](../backend/score_trans/dao/tasks/task_dao.py#L94) 只恢复 pending/running 任务，不加载 completed/failed 记录。另一方面，[`TaskManager.cleanup_expired`](../backend/score_trans/services/tasks/task_service.py#L181) 只有在内存字典中发现过期任务时才调用数据库级 `delete_expired()`。

因此，应用重启前尚未到期的 completed/failed 记录，重启后不会进入内存；以后也不会触发数据库删除。

隔离复现结果：

```text
expired_row_before=True
expired_row_after_restart_and_create=True
```

运行期间，完成任务及其完整结果还会在 `_tasks` 中保留一小时；每个任务的 per-task queue 也是无界 `asyncio.Queue`。单个任务事件不多，但大量任务和大型结果会形成可观的短期驻留。

**建议：** TaskManager 初始化时无条件执行一次数据库 `delete_expired(now)`，运行期间周期清理；数据库只持久化恢复所需的最小结果或结果文件 ID；为内存任务数、单结果大小和队列长度设置上限。

### F3. 批量识别缺少统一资源预算

[`submitRecognitionTargets`](../desktop/src/renderer/src/views/RecognizeView.vue#L655) 遍历所有页面并通过 `void run.finally(...)` 一次性启动任务，不对前端提交速度施加背压。

OMR 使用并发数 2 的 [`OMR_SEMAPHORE`](../backend/score_trans/exec/tasks/background.py#L13)，而默认每个 Audiveris JVM 最大堆为 3GB。JVM 不一定立即占满堆，但两项重任务同时增长时，理论上可接近 6GB，再叠加 Electron、Python、图片和操作系统占用，对 8GB 机器风险较高。

AI 后台任务在 [`AiActions.submit_transcribe_task`](../backend/score_trans/exec/ai/actions.py#L125) 中没有传入任何 semaphore。多页 AI 模式可能同时进入默认线程池，执行图片读取、缩放、Base64 编码和 HTTP 请求。

**建议：** 为 OMR、AI、渲染和导出建立独立并发预算。OMR 默认并发建议为 1，并允许根据物理内存配置；AI 建议 2-4；前端只维持有限数量的已提交任务，其余显示为排队状态。

### F4. 外部进程没有超时，取消只停在界面层

[`external_tools._run`](../backend/score_trans/services/recognize/external_tools.py#L44) 使用 `subprocess.run(capture_output=True)`：

- 没有 `timeout`；
- 无法保存进程句柄并执行分阶段 terminate/kill；
- stdout/stderr 在进程退出前完整保存在 Python 内存；
- Java 或 Gradle 卡住时任务不会自然结束。

后台包装在 [`run_sync_task`](../backend/score_trans/exec/tasks/background.py#L34) 中使用 `asyncio.to_thread()`。取消 asyncio Task 不能停止已经运行的 Python 线程，更不能自动终止线程中的 Audiveris 子进程。前端 AbortController 只会取消 SSE/fetch 等待，不会向后端发出任务取消指令。

FastAPI lifespan 在退出时无截止时间地 `gather` 全部后台任务，见 [`api.app.lifespan`](../backend/score_trans/api/app.py#L35)。Electron 最终会尝试结束进程树，但这属于进程级兜底，不是任务级取消。

**建议：** 使用 `Popen` 和独立进程组；增加可配置硬超时、正常终止宽限期和强制结束；增加任务取消端点与协作式取消 token；后端关闭等待应有总截止时间；外部工具日志改为流式写入有大小上限的日志文件或环形缓冲。

### F5. PDF 与图片批处理的峰值缺少约束

[`FileActions._pdf_to_images`](../backend/score_trans/exec/files/actions.py#L53) 会以 300 DPI 转换 PDF 的全部页面，没有页数上限。页面 PNG 先写入原 PDF 的 file ID 目录，再由 `register()` 复制到新的 file ID 目录，造成重复写入。

识别页的预览 watcher 使用 [`Promise.all`](../desktop/src/renderer/src/views/RecognizeView.vue#L403) 同时下载当前批次全部图片，并为每张图片保存 Blob URL。离开识别页时 URL 会正确 revoke，因此它不是永久泄漏；但在识别页打开期间，内存峰值与页面总数和图片大小线性增长。

图片转 PDF 路径在 [`ExportActions.export_pdf`](../backend/score_trans/exec/export/actions.py#L191) 中将所有输入读取为 `list[bytes]`，总请求上限可达 512MB；随后 MuPDF 还需要解码和构建 PDF。`images_to_pdf()` 的 `fitz` 文档也只在成功路径显式关闭，异常路径缺少 `finally`。

**建议：** 上传 PDF 增加最大页数、最大总像素和最大展开后字节预算；生成缩略图而不是直接持有全分辨率页面；预览使用虚拟列表和可见窗口加载；图片转 PDF 改为逐页读取与释放；所有 MuPDF 文档使用 context manager 或 `try/finally`。

### F6. 缓存清理与运行中任务存在竞争

[`CacheService.clear`](../backend/score_trans/services/storage/cache_service.py#L41) 会直接删除整个 `audiveris`、`pipeline` 和 `ai_transcribe` 根目录，并根据历史引用集合删除 uploads。

设置页的清理按钮仅根据自身 `clearingCache` 状态显示 loading，没有根据 workspace 后台任务状态禁用，见 [`StorageSettingsPanel`](../desktop/src/renderer/src/components/settings/StorageSettingsPanel.vue#L58)。

可能出现两种破坏性竞争：

1. 后台任务仍在工作时，其输出目录被整体删除。
2. 当前工作区文件尚未持久化为历史引用时，被 prune 判定为孤立文件。

**建议：** 后端维护活动目录和活动 file ID 租约，清理逻辑必须跳过租约对象；运行中任务存在时拒绝全量清理；前端禁用按钮只作为辅助保护，不能代替后端约束。

### F7. 大范围文本差异计算会同步阻塞 UI

[`textDiff.ts`](../desktop/src/renderer/src/utils/textDiff.ts#L1) 将最大编辑距离设为 2048，并为 Myers 算法的每一层复制 frontier Map。最坏时间和空间接近 O(D²)。

现有 2,100 字符完全替换用例在本机单独执行耗时约 296ms。该逻辑由文本锚点协调路径在 Electron 渲染线程同步调用，整谱粘贴或大范围替换时会产生明显掉帧。

**建议：** 对大文本、大长度差和低相似度输入提前走线性前后缀替换；显著降低编辑距离上限；如必须计算精细 diff，则移入 Web Worker，并设置时间预算。

### F8. HTTP 连接复用和请求截止时间不足

AI 与 OCR 分别直接调用模块级 [`httpx.post/httpx.stream`](../backend/score_trans/services/ai/providers/_http.py#L77) 和 [`httpx.post`](../backend/score_trans/services/ocr/providers/_http.py#L38)。每次请求都新建连接，无法复用 TCP/TLS 连接池。

前端 [`authenticatedFetch`](../desktop/src/renderer/src/api/client.ts#L46) 没有默认超时。部分组件自己提供 AbortController 或 15 秒超时，但普通 JSON API、上传 XHR 和部分文件获取可能无限等待，导致 loading 状态长期保持。

**建议：** 在进程组合根持有共享 `httpx.Client`，在 lifespan 结束时关闭；针对元数据、渲染、AI、上传分别定义合理超时；上传和普通 API 都应允许用户取消。

### F9. 工作区状态可随批次数量长期增长

[`workspace.addInputPage`](../desktop/src/renderer/src/stores/workspace.ts#L307) 会为已经 sealed 的批次创建新 batch ID，但旧批次页面继续保留在 `pages` 中。每个页面可能持有 MusicXML、简谱、OCR、锚点和纠错状态。

这是产品为了批次切换而保留的状态，不属于丢失引用式泄漏，但没有数量或内存上限。长时间连续处理许多批次时，渲染进程内存仍会增长。

**建议：** 只保留当前批次和少量最近批次的完整状态；其他批次保留摘要并按需从历史加载；建立显式“关闭批次”行为。

## 5. 对初步报告的重新核验

| 初步结论 | 本轮结论 |
|---|---|
| Scratch 目录持续累积 | **确认成立。** 当前已有 51 个 pipeline 目录、约 110MB。 |
| workspace `loadBatch()` 留下批次 Record | **当前不成立。** 当前代码已在替换页面前清空批次级 Record。 |
| 上传文件没有自动 prune | **确认成立。** 仅手动清理缓存时 prune；当前有 2,420 个孤立目录。 |
| 任务注册表空闲时不清理 | **确认且影响高于初判。** 内存清理是事件驱动，跨重启数据库记录还会永久残留。 |
| Electron 后端进程生命周期健全 | **静态设计基本健全，但真实强杀仍缺发布环境验证。** |
| 对象 URL 和主要 SSE 存在泄漏 | **未发现。** 当前实现大多有 revoke、abort 和卸载清理。 |

## 6. 已确认健壮的部分

- 识别预览、原图预览和导出 Blob URL 均存在回收逻辑。
- 主要 window/document 事件监听器在组件卸载时移除。
- 日志 Store 上限为 1,000 条。
- 语法诊断响应上限为 1,000 条，并有 debounce、sequence 和 AbortController。
- 后台 asyncio Task 使用集合保持强引用，并通过 done callback 从集合移除。
- OMR 已有全局信号量，说明代码已经具备增加统一资源预算的基础。
- `FileResponse` 使用文件响应而非一次性读入下载文件。
- SVG/PDF 导出的多数 MuPDF 路径使用 `try/finally` 关闭资源。
- 字体测量和轮廓缓存具有 8,192 项 LRU 上限；overlay 字形缓存虽然使用无界 `@cache`，实际 key 来自有限 SMuFL 映射。
- 当前 `loadBatch()` 会重置旧的批次级映射，最初担心的孤儿 Record 已得到处理。

## 7. 动态验证结果

### 7.1 后端测试

使用项目虚拟环境 Python 3.13.5，并将数据和缓存隔离到临时目录：

```text
1027 passed, 1 skipped, 1 xfailed, 1 warning
```

第一次直接执行时有 77 项失败，均收敛到沙箱禁止测试进程在外部数据目录切换 SQLite WAL；隔离目录后全部消失，不属于代码断言失败。

### 7.2 前端测试

- Vue TypeScript 类型检查通过。
- 排除真实 Windows 子进程终止用例后：228 项通过，1 项因 Windows 符号链接权限跳过。
- 真实子进程终止测试在当前受限环境下返回 `Access Denied`，无法据此判断发布版行为，需在正常 Windows 打包环境复核。

### 7.3 Python 渲染内存基线

预热后，对同一份 20 小节乐谱重复渲染 8 次：

```text
elapsed_seconds=0.798
retained_delta_bytes=20969
peak_bytes=564106
```

这组结果没有显示纯 Python 渲染路径存在明显的逐次堆增长。该结论仅覆盖 Python 分配器，不覆盖 JVM、Chromium、Pillow/MuPDF 原生堆和显存。

### 7.4 缓存扫描开销

当前 9,036 个缓存文件的完整 stat/rglob 扫描约耗时 1.0 秒。设置响应每次都会计算缓存大小，因此文件继续增长后，进入设置页的 I/O 延迟也会增加。

## 8. 建议实施顺序

### 阶段 A：阻止继续增长

1. Pipeline、Recognize、AI 使用每请求 `try/finally` 清理 scratch。
2. 播放器 MIDI、导出中转文件和被替换的渲染文件使用短期租约，消费后删除。
3. TaskManager 启动时无条件删除过期数据库记录，并增加周期清理。
4. 缓存清理增加活动任务与 file ID 租约保护。

### 阶段 B：限制峰值并解决卡死

1. OMR 默认并发降为 1；AI 增加 2-4 的可配置并发限制。
2. 前端批量提交改为有界队列。
3. Audiveris 改用可管理的 `Popen` 进程组，增加硬超时与取消。
4. PDF 增加最大页数、总像素和展开后大小预算。
5. 预览改为虚拟列表和按需 Blob 加载。

### 阶段 C：降低常态延迟

1. HTTP 客户端连接池复用。
2. 大文本 diff 快速降级或迁移至 Worker。
3. 非活动工作区批次按需加载。
4. 缓存大小改为后台增量统计，避免每次设置请求遍历全树。

## 9. 建议验收指标

| 场景 | 建议指标 |
|---|---|
| 连续播放/更新简谱 100 次 | 临时 MIDI 在任务结束或 TTL 后归零，缓存净增长低于 5MB |
| 连续重新渲染 100 次 | 只保留当前和历史引用版本，孤立 SVG/JSON 不持续增长 |
| 关闭运行中的 OMR | 10 秒内应用退出，Python、Java、Gradle 子进程全部消失 |
| 50 页 PDF 打开识别页 | 只加载可见缩略图，renderer RSS 不随全页原图总量线性增长 |
| AI 识别全部页 | 实际并发不超过配置值，其余任务明确显示排队 |
| 2 小时混合操作 soak test | 完成 GC 和 TTL 清理后，Python/Electron RSS 回到稳定平台 |
| 应用重启 | `tasks.db` 中过期任务为 0，崩溃遗留 scratch 按安全年龄回收 |
| 运行中清理缓存 | 后端拒绝破坏活动租约，正在执行的任务不受影响 |

## 10. 调研边界

- 未实际调用 Audiveris、远程 AI 或 OCR，因此没有测量真实 JVM 峰值、网络故障恢复时间和供应商连接行为。
- 未执行 Electron 打包版长时间 soak test、Chrome heap snapshot、Windows Performance Recorder 或原生句柄追踪。
- `tracemalloc` 不能观察 Pillow、MuPDF、Chromium、音频上下文和 JVM 的原生内存。
- 当前工作树包含用户已有的未提交前端改动；本报告按当前实际代码审计，没有回退这些改动。

## 11. 最终判断

Score Trans 当前的资源管理基础并不差：主要监听器、Blob URL、SSE 和 Python 渲染路径都有较好的释放意识，现有测试覆盖也较广。真正需要优先治理的是跨模块的资源所有权：一个任务创建的目录、文件、数据库结果、线程和外部进程，必须有唯一负责人和明确的终止条件。

只要优先完成阶段 A 与阶段 B，软件的磁盘增长、长时间卡住和高峰值崩溃风险会明显下降；继续优化字体缓存或零散微小对象的收益远低于这些结构性修复。
