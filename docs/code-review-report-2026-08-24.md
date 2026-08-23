# Score Trans 代码审计复核报告

> 日期：2026-08-24  
> 复核基线：`bdaa842` 及复核期间可见的未提交工作区  
> 复核目标：逐项验证原《Score Trans 全量代码审计报告》，纠正误报、严重度和证据，并补充遗漏问题。  
> 命令约束：所有仓库命令使用 Bash；所有 Python 探针和测试使用 `.venv/Scripts/python.exe`。

## 一、结论摘要

原报告找到了若干真实问题，但不能继续作为“已逐一确认”的事实清单使用，主要原因如下：

1. 将单个可选端点失效定义为 P0，严重度标准过宽。按通常的发布阻断标准，本项目当前没有已确认 P0。
2. 多项代码风险被写成已经复现的运行时故障，例如 OCR 坐标错位、字体并发、SSE 瞬断失败；其中部分需要真实样本，部分与代码行为相反。
3. 一些安全加固建议被当作现存漏洞，例如 `data-shape` 注入。该分支实际受固定 SMuFL shape 白名单保护，注入结论不成立。
4. P3 使用合并段落列出“60+”项，却没有逐项状态和证据，无法审计数量，也混入设计选择、重复项和不可定位描述。
5. 原报告声称 `623 passed, 1 skipped`，但没有保留命令输出。本次当前工作区收集并完整运行了 632 项测试，最新结果为 `630 passed, 1 failed, 1 skipped`；相关聚焦测试为 `150 passed`。因此当前不能写成“全量全绿”。

修正后的高层结论：

| 严重度 | 已确认数量 | 说明 |
|---|---:|---|
| P0 | 0 | 没有确认到系统整体不可用、不可恢复数据破坏或远程代码执行 |
| P1 | 9 | 端点必坏、常用功能失效、数据串批/覆盖、本地文件越界读取、打包必坏分支等 |
| P2 | 见第三节 | 竞态、资源生命周期、输入校验、安全边界和可测量性能风险 |
| P3 | 见第五节 | 低风险健壮性、死代码、文档/测试债务；已剔除误报 |

## 二、已确认 P1

### P1-1 `/render/preserving-layout` 必然抛 `TypeError`

- 位置：`backend/score_trans/services/render/render_service.py:39-60`，`backend/score_trans/services/render/main.py:280-302`
- 状态：确认；从原 P0 下调为 P1。
- 复现：调用 `PublicationRenderService.render_score_page_svg(...)` 得到 `TypeError: render_score_page_file_to_svg() got an unexpected keyword argument 'initial_measure_number'`。
- 原因：service 传入 `initial_measure_number`，main 函数签名没有该参数。
- 修复：补充参数并写入 `RenderOptions`；新增 route -> action -> service -> main 完整回归测试。

### P1-2 A4 落盘链路忽略自定义起始小节号

- 位置：`backend/score_trans/services/render/main.py:170-203`
- 状态：确认。
- 复现：以 `initial_measure_number=37` 渲染落盘 SVG，结果仍包含小节号 1，不包含 37。
- 原因：`RenderOptions` 收到该值，但 `renderer.render_scores(...)` 未传 `initial_measure_number`。
- 修复：在落盘路径透传，并分别覆盖内存/文件、多页/多声部。

### P1-3 文件 ID 回退扫描可越出 uploads 目录

- 位置：`backend/score_trans/services/files/upload_service.py:214-241`
- 状态：确认，但原报告“任意文件读取”描述过宽。
- 复现：`get_path('..\\outside')` 和 `get_path('../outside')` 均返回 uploads 外目录中字典序第一个普通文件。
- 实际能力：攻击者可选择目录并读取其中首个文件，不能直接把任意具体文件路径作为 `file_id` 读取。
- 前提：请求仍需本地 API token，或显式关闭鉴权。
- 修复：统一验证 12 位十六进制 ID；索引值及 fallback 结果都要求 `is_relative_to(base_dir)`。

### P1-4 多声部 MIDI 轨道共用 channel 0

- 位置：`backend/score_trans/services/export/export_service.py:236-269`
- 状态：确认。
- 影响：多个声部同时演奏同音高时，一个轨道的 `note_off` 可能提前终止另一个轨道的音符，具体表现依赖播放器/合成器。
- 附带问题：休止符用 `note_off(note=0)` 承载 delta time，语义不干净。
- 修复：为声部分配 MIDI channel；用无副作用的 meta event 或绝对 tick 游标推进休止。

### P1-5 Audiveris 无超时，关停可无限等待

- 位置：`backend/score_trans/services/recognize/external_tools.py:44-73`，`backend/score_trans/api/app.py:194-203`
- 状态：确认。
- 影响：卡死的 Gradle/JVM 永久占用工作线程和 `OMR_SEMAPHORE`；应用 lifespan 等待后台任务时也没有截止时间。
- 修复：改用可终止进程树的 `Popen` 管理器，设置运行超时；shutdown 使用有界等待并终止遗留进程。

### P1-6 JDK 下载分支生成错误目录结构

- 位置：`build-app.py:560-629`，`backend/score_trans/services/settings/settings_service.py:37-58`
- 状态：确认。
- 原因：本地复制写入 `jre/jdk`，下载解压保留 `jre/jdk-25...`；运行时只探测 `third_party/jre/jdk/bin/java.exe`。
- 影响：没有本地 JDK 的干净构建机可能产出无法找到捆绑 JDK 的安装包。
- 修复：解压到临时目录后原子归一化到 `JRE_DIR/jdk`，打包前断言 `bin/java.exe`。

### P1-7 历史批次拖拽排序可覆盖未保存编辑

- 位置：`desktop/src/renderer/src/views/ConvertView.vue:881-924`
- 状态：确认。
- 原因：排序从 `expandedBatchJianpuText` 的历史详情快照重建正文；编辑器修改的是 `store.currentBatchJianpuText`，两者不自动同步。
- 影响：编辑后对同一历史批次排序，会把旧正文提交并写回 store。
- 修复：使用当前 store 正文；存在 dirty 编辑时要求确认；提交前校验批次和正文 revision。

### P1-8 慢渲染完成后可写入另一个批次

- 位置：`desktop/src/renderer/src/views/ConvertView.vue:1009-1025,1478-1502,1562-1598`
- 状态：确认。
- 原因：`renderFinalBatch()` 没有捕获/校验开始时的本地 batch ID 和 history batch ID；持久化默认参数在 await 后读取当前批次。
- 触发：A 恢复触发慢渲染，期间切到已有缓存、不触发新渲染的 B；A 返回后写入 B。
- 修复：请求开始捕获 batch 身份和 epoch；所有落账前校验；持久化函数必须显式传 batch ID。

### P1-9 播放器 BPM 调节在常见路径基本不改变播放速度

- 位置：`desktop/src/renderer/src/composables/usePlayer.ts:107-155,220-228`
- 状态：新增确认问题；原报告 P2-28 的“两个时间域混用”因果解释错误。
- 原因：MIDI 的 `note.time`/`note.duration` 是秒值；数字秒值在当前 BPM 下转换为 Transport tick，播放时又按同一 BPM 转回秒，变化相互抵消；`triggerAttackRelease` 的 duration 也仍是秒。
- 影响：播放前调整 BPM 时，用户通常仍听到原速度。
- 修复：保留 MIDI tick，或显式按 `originalBpm / requestedBpm` 缩放所有开始时间、时长、总时长、seek 和循环区间。

## 三、已确认 P2

| 编号 | 问题 | 复核结论 |
|---|---|---|
| P2-1 | 非 ASCII Bearer token 触发 `compare_digest(str, str)` TypeError | 确认；应返回 401 而不是异常，原 P1 过高 |
| P2-2 | `-PcmdLineArgs` 用逗号串接 | 确认；Audiveris `app/build.gradle` 明确 `split(',')`，含逗号路径会断裂 |
| P2-3 | MIDI 连音时值逐事件向下取整 | 确认；五/七连音会累计 tick 误差，改绝对游标/误差余数 |
| P2-4 | `midi_tempo=0` 可进入 `bpm2tempo` | 确认；设置和导出 schema 缺少 1..400 约束 |
| P2-5 | AI 续写用尽轮数后丢弃已生成内容 | 确认；非流式不返回，流式已展示但不会写入数据库 |
| P2-6 | 自定义 prompt 的裸花括号触发 `str.format` KeyError | 确认；需把模板错误转换为带字段名的 `AITranscriptionError` |
| P2-7 | TaskManager 在事件循环同步访问 SQLite | 确认；锁等待会阻塞 SSE 和其他请求 |
| P2-8 | `cleanup_expired()` 删除异常未隔离 | 确认；原报告“把成功任务标失败”不准确，实际可中断 create/update/stream/complete |
| P2-9 | 单个 task 只有一个共享 SSE queue | 确认；多个订阅者竞争事件，漏掉终态者可永久 keepalive |
| P2-10 | PDF 页面 PNG 双份保存且 `doc.close()` 不在 finally | 确认 |
| P2-11 | 渲染临时文件与 cache prune 存在 TOCTOU | 确认；临时 SVG/TXT 直接写 uploads 根，注册前可被清理 |
| P2-12 | `settings.applyDraft()` 缺少并发/编辑中保护 | 确认；双击或保存过程中继续编辑可被旧响应覆盖 |
| P2-13 | preload 暴露完整 `electronAPI` | 确认；sandbox 在 Electron 43 默认启用，原报告“未显式即未启用”不准确 |
| P2-14 | `file:open-folder` 可对任意绝对文件调用 `shell.openPath` | 确认；应 `stat` 并只接受目录 |
| P2-15 | 大型 JSON 请求无统一 body limit | 确认；`/correct/apply`、`/history` 可带全文；“尾斜杠直接绕过”未复现 |
| P2-16 | 历史/task schema 缺少边界和枚举 | 部分确认；`page_index`、status、列表长度值得补约束，不能笼统称为漏洞 |
| P2-17 | 几何 QA 两两比较为 O(n²) | 确认算法复杂度；“单页分钟级”没有基准数据，不能当已复现事实 |
| P2-18 | `_draw_system` 重复 flatten 导致 O(n²) | 确认 |
| P2-19 | 删除 patch 每个 ID 反复扫描 XML 树 | 确认，docs/issues.md N25 仍存在 |
| P2-20 | 大文本编辑每键多次全文分词/解析 | 确认结构性热点；尚无输入延迟基准 |
| P2-21 | AI 流式消息反复计算全历史并重渲染 Markdown | 确认结构性 O(n²) 风险 |
| P2-22 | 播放高亮倒扫过早 break | 确认；较晚短音结束后会遮蔽更早仍持续的长音 |
| P2-23 | MIDI 加载无 Abort/内部 generation | 确认；旧请求可在组件外层 generation 检查前覆盖 player 状态 |
| P2-24 | Convert/Recognize 使用独立渲染 gate | 确认可并发；“一定双重持久化”取决于是否同时操作同一批次 |
| P2-25 | 全局 Delete/Backspace 不检查事件目标 | 确认；焦点在其他输入控件时可能删除已选 OCR 块 |
| P2-26 | `n-input-number` 清空值未正规化 | 确认；tempo/min edge 多数被后端忽略，max pixel 可写入字符串 `null` 并在识别时失败 |
| P2-27 | 显式选择非当前 AI profile 时 API key 可能错配 | 新增确认；`_create_named_or_profile_provider` 传 base/model 不传该 profile 的 key |
| P2-28 | 同窗导航无 `will-navigate` 拦截且无 CSP | 确认安全边界缺口；与宽泛 preload bridge 组合后风险高于普通 Web UI |
| P2-29 | `PublicationPreview` 卸载不恢复 `body.userSelect` | 确认；拖拽中卸载会把全局文本选择留为 `none` |
| P2-30 | JianpuEditor 没有 IME composition 保护 | 确认；组合输入期间 `onInput` 仍会插入/撤销换行 |

## 四、需要外部样本或发布环境确认

### V-1 OCR 坐标缩放契约冲突

- 代码事实：`image_to_data_url()` 会把长边缩到 2000；DeepSeek OCR prompt 要求“原图像素坐标”；下游使用原图尺寸。
- 不能直接确认的部分：不同模型可能返回归一化坐标，或不严格遵循 prompt。
- 结论：风险成立，但“所有大图系统性错位”尚未复现。需要每个 provider 使用 >2000px 样本记录发送尺寸、返回 bbox 和最终叠加位置。

### V-2 代码签名

- 仓库事实：`publisherName: queen` 不是签名凭据；仓库 CI 未配置证书，也没有签名验收步骤。
- 边界：本地/外部发布环境仍可能通过 `WIN_CSC_LINK` 或证书库注入凭据，因此不能断言“任何构建一定未签名”。
- 正确结论：仓库不能保证产物签名，且不会在缺证书时 fail closed。

### V-3 JDK/Gradle 供应链

- JDK 使用动态 latest URL 且不校验 digest：确认。
- Gradle ZIP 校验：确认有效。
- 已解压 Gradle 目录未逐文件验证且缓存目录遍历不排序：确认加固缺口。
- 严重度：发布供应链 P2，不应与运行时 P1 混为一类。

### V-4 JAVA_HOME 预检

- 确认：设置保存不校验；存量坏路径加载时静默回退；真正的 `bin/java.exe` 校验发生在识别调用。
- 边界：空 `java_home` 可能有意使用系统 PATH，不能一概视为错误。
- 结论：违反项目 AGENTS.md 的明确契约，按配置/诊断问题列 P2。

## 五、原报告逐项核验矩阵

### 5.1 原 P0/P1

| 原编号 | 状态 | 修正 |
|---|---|---|
| P0-1 | 确认 | 下调 P1；单个端点完全不可用，不是系统级 P0 |
| P1-1 | 确认 | 保持 P1 |
| P1-2 | 确认 | 下调 P2；畸形未认证请求错误映射 |
| P1-3 | 确认 | 能读取指定目录首文件，不是无条件任意文件 |
| P1-4 | 确认 | 保持 P1 |
| P1-5 | 确认 | 保持 P1 |
| P1-6 | 部分 | 移至 V-1，真实模型样本未验证 |
| P1-7 | 部分 | 下调 P2；空值允许系统 Java，坏值静默回退仍有问题 |
| P1-8 | 确认 | 保持 P1 |
| P1-9 | 部分 | 配置不能保证签名；不能排除外部环境注入证书 |
| P1-10 | 确认 | 下调发布供应链 P2 |
| P1-11 | 确认 | 保持 P1 |
| P1-12 | 确认 | 保持 P1 |

### 5.2 原 P2

| 原编号 | 状态 | 修正说明 |
|---|---|---|
| P2-1 | 确认 | Gradle 确实按逗号 split |
| P2-2 | 确认 | 需要绝对 tick/余数算法 |
| P2-3 | 确认 | 0 BPM 可进入导出 |
| P2-4 | 部分 | DOCTYPE/注释会丢；对修正后 MusicXML 是否必须保留属于产品约定，`register_namespace` 风险很低 |
| P2-5 | 确认 | 错误路径不持久化部分回复 |
| P2-6 | 确认 | 影响背景转写失败或助手 500，原文统一写“500”不精确 |
| P2-7 | 未证实 | role 是自由字符串属 schema 弱约束；没有构造出当前解析器会错配的输入 |
| P2-8 | 部分 | PRAGMA 不一致成立；Python sqlite 默认已有约 5 秒 busy timeout，原文“缺 busy_timeout”不准确 |
| P2-9 | 部分 | context manager 不 close 成立，但“全部 DAO”过度概括；CPython 通常会及时回收 |
| P2-10 | 确认 | 同步 DB 位于 async 热路径 |
| P2-11 | 确认 | 影响描述已修正 |
| P2-12 | 确认 | 多订阅者会竞争终态 |
| P2-13 | 确认 | 双份页图和 close 泄漏窗口 |
| P2-14 | 确认 | uploads 根文件会被 prune 删除 |
| P2-15 | 误报/设计选择 | 缺字体和哈希错误主动失败是确定性出版渲染要求；并发首载最多重复构造，无共享对象破坏证据 |
| P2-16 | 确认 | 保存竞态/编辑覆盖 |
| P2-17 | 误报 | `shape` 必须命中固定 `_SMUFL_CODEPOINTS` 才进入未转义属性分支 |
| P2-18 | 部分 | 暴露完整 bridge 成立；Electron 43 的 sandbox 默认是 true |
| P2-19 | 确认 | 应只允许目录 |
| P2-20 | 部分 | JSON 大请求无限制成立；尾斜杠通常先重定向，未证明可直接绕过 |
| P2-21 | 部分 | 若干字段应加约束；不能用一个条目代表所有 schema 都有漏洞 |
| P2-22 | 确认算法 | 性能量级未做基准，删除“分钟级”断言 |
| P2-23 | 确认 | 重复 flatten 为 O(n²) |
| P2-24 | 部分 | 重复计算成立；“10-30 倍”无测量证据 |
| P2-25 | 确认 | N25 仍存在 |
| P2-26 | 确认风险 | 缺少基准数据 |
| P2-27 | 确认风险 | 长流式回复下放大明显 |
| P2-28 | 误报并替换 | 不是两个秒域混用；真实问题为 BPM 调节通常无效，见 P1-9 |
| P2-29 | 确认 | 长音高亮会漏 |
| P2-30 | 确认 | 旧加载可覆盖 player 内部状态 |
| P2-31 | 误报 | SSE 中断会自动切到轮询；只有轮询连续失败 30 次才失败 |
| P2-32 | 部分 | 两个 gate 独立成立，实际写冲突需要同批次并发操作 |
| P2-33 | 确认 | 全局键盘处理缺 target guard |
| P2-34 | 确认 | 各数值项后果不同，已分别说明 |

### 5.3 原 P3：渲染与识别

| 原主张 | 状态 | 修正说明 |
|---|---|---|
| `_mark_glyph/_rendered_mark_label` 死代码 | 确认 | 无调用点 |
| `_rhythm_line_count/_accidental_text` 三处拷贝 | 部分 | 当前明确看到 renderer/geometry 两套；“三处”未证实 |
| `_append_ranges` 只统计声部 0 | 确认边界 | 每 cell 遇首个非空 measure 后 break；同页同号声部通常无影响 |
| 渲染器原地修改输入 | 确认 | 修改 `display_number`、measure-number text block |
| render-map selector 未转义 | 部分 | 字符串未转义，但正常 source ID 是受控 `sN:iN` |
| A4 忽略 `RenderOptions.margin` | 确认 | 自定义页面使用，A4 固定物理边距；需要文档化或拆选项 |
| scene/svg 精度不同 | 确认 | 3 位与 6 位；未发现可见功能故障 |
| 子进程强制 UTF-8 导致中文乱码 | 待实测 | 取决于 Gradle/JVM 实际输出编码 |
| 日志 `stat()` TOCTOU | 确认低风险 | 日志恰在排序时删除可抛异常 |
| OCR parser 类型防御不足 | 确认 | 非数值 confidence 会抛，measure_number 可带不期望类型 |
| OMR picture 尺寸 `int()` 未捕获 | 确认低风险 | overlay 路径多为非致命，correct 路径可失败 |
| PDF MediaBox 正则启发式 | 确认设计限制 | 是缺少正常解析器时的 fallback，不应描述为主路径 bug |
| UUID 截断无碰撞重试 | 确认理论风险 | 48-bit ID，现实概率低但碰撞会复用目录 |
| 上传 safe_name 空串 | 确认低风险 | 会失败并清理，不构成路径穿越 |
| index cache TOCTOU/shared tmp | 部分 | 单进程有全局锁；跨进程和 stat/read 窗口仍存在 |
| progress callback 最多阻塞 5 秒 | 确认 | 阻塞 worker thread，不是直接阻塞 event loop |
| global event 快照重复 | 确认 | 订阅先加入，再发送快照，期间更新会再排队 |
| RenderedSvgPage 固定 A4 尺寸 | 误报 | 这些注册函数只处理 A4 输出；preserving-layout 单独返回实际尺寸 |
| 鸭子类型冗余调用 | 不可审计 | 原报告没有函数名/位置，删除 |
| OMR 未设 `CREATE_NO_WINDOW` | 确认低风险 | 可能闪控制台，需 Windows 打包实测 |

### 5.4 原 P3：AI、导出、设置

| 原主张 | 状态 | 修正说明 |
|---|---|---|
| 续写重复启发式误杀规律乐谱 | 可能 | 算法存在误判条件，未给出真实回复复现 |
| 视觉转写仅一次紧凑重试 | 设计选择 | 不是自身 bug；`content_filter` 缺专门错误提示属健壮性问题 |
| AI SSE 丢无效 data/不支持多行 data | 确认兼容缺口 | OpenAI 常见实现通常单行 JSON，风险较低 |
| provider 永久缓存，换 key 要重启 | 误报 | FastAPI dependency 每次构造新的 action/service/provider |
| `_merge_scores_by_part` 修改入参 | 确认 | 直接 extend 第一个 score 的 measures |
| `images_to_pdf` 固定 A4 竖版 | 设计选择 | 端点目标就是 PDF 页面；横图留白不等于 bug |
| `src_doc` 不在 finally | 确认 |
| 隐形文本正则漏单引号/style | 确认低风险 | 当前内部 SVG 固定生成双引号属性 |
| profile 二次解析可能错发 key | 确认 | 已提升为 P2-27 |
| 同请求换 provider+写 key 归属错误 | 误报 | update 顺序先切 provider，再按当前 ID 写 key |
| `get_int` 负值钳 0 | 确认设计行为 | schema 正常入口可限制；坏 DB 值会静默改变 |
| 未知 bool 一律 true | 确认宽松解析 | 建议只接受显式 true/false 集合 |
| SenseNova 类级可变 dict | 误报 | 当前只作为只读 extra body，调用方复制到请求 body |
| `Image.open` 未 close | 确认 |
| EXIF 方向丢失 | 确认 | 只在发生重编码缩放时 |
| prompts 裸 except 吞设置故障 | 确认低风险 | fallback 会隐藏数据库/配置错误 |
| chat 失败残留空会话 | 确认 | session 在 provider 调用前创建 |

### 5.5 原 P3：API、前端、测试与文档

| 原主张 | 状态 | 修正说明 |
|---|---|---|
| required env 解析错误无统一诊断 | 确认 | `_i/_f` 裸转换、`_s` KeyError 不满足项目 fail-fast 文案要求 |
| pyinstaller port 裸 `int()` | 确认低风险 |
| CORS 总加入 `null` 是漏洞 | 误报/设计 | packaged Electron `file://` 需要；Bearer token 仍保护 API |
| 原生 EventSource 不能带 Bearer | 事实但非 bug | 前端明确使用 fetch stream |
| DELETE 缺 response model | 确认质量项 |
| multipart filename 在 query | 事实但非功能 bug | FastAPI 参数声明如此；当前主工作流使用 rendered-pdf JSON 接口 |
| published defaults 异常类型混用 | 确认质量项 |
| `SettingsDao.default` 无锁 | 确认理论首载竞态 |
| dotenv 不支持 `export`/行内注释 | 事实但未违反当前文档契约 |
| legacy SQLite 裸复制活动 WAL | 部分 | sidecar 也复制，但不是一致性快照；双实例启动时有风险 |
| `update_page` 强制 engine version | 基线低风险，当前工作区已成回归 | 见第六节 W-1 |
| token 长度校验两处重复 | 确认质量项 |
| 全局 ValueError -> 400 | 确认架构风险 | 可能掩盖程序错误，但许多 domain API 有意使用 ValueError |
| 卸载不恢复 body.userSelect | 确认，提升 P2-29 |
| 编辑器无 IME 保护 | 确认，提升 P2-30 |
| `fileExists` fail-open | 确认死代码 | 当前无调用点 |
| FileUploader 重复 key/不去重 | 确认低风险 |
| HistoryQuickEntry/EfficiencyDashboard 静默失败 | 确认低风险 |
| applyDraft 并发 | 确认，已列 P2-12 |
| FAB localStorage 未捕获 | 确认低风险 |
| Markdown 占位符可碰撞 | 确认文本破坏边界 |
| loadSvg nextTick 后无代际复查 | 确认窄竞态 |
| 非手势调用 `Tone.start` | 待 Electron 实测 | 浏览器 autoplay 策略可能拒绝，Electron 行为依配置而异 |
| OCR 叠加硬编码浅色 | 确认视觉问题 |
| 纯浏览器环境裸 `window.api` | 确认；AGENTS.md 同时描述浏览器开发配置，行为与文档不一致 |
| getBBox 失败静默 | 事实但合理降级 | 仅导致不自动滚入视图 |
| `v-for` 与 `v-else` 同元素 | 未定位/误报 | 当前模板没有报告所述结构，删除 |
| API 普遍无前端超时 | 确认健壮性项 |
| Electron 强杀残留后端 | 确认 | 正常退出已有进程树终止；强杀需 Job Object |
| port 探测 TOCTOU | 确认低概率 | stderr 会写日志，但启动错误框不包含 stderr |
| workspace 顶层 musicxmlText 切页不同步 | 确认陷阱字段 | 当前主要消费者用 currentPage，现实影响有限 |
| App 纯浏览器首屏报错 | 确认 |
| 无 will-navigate/CSP | 确认并提升 P2-28 |
| stores 抛异常违反 API tuple 契约 | 误报 | tuple 约束针对 API wrapper；AGENTS.md 允许 store/page 在边界用 `requireData` |
| `findNotePageIndex` 假定页号连续 | 确认边界 | 非连续手改 marker 会映射错误 |
| eslint 关闭 no-explicit-any | 确认质量项 |
| storage IPC 接受任意路径 | 确认安全加固项 |
| exportPath 漏 DEL | 误报 | Windows 禁止的是 U+0001..U+001F；DEL 不是同一限制 |
| conftest 关闭鉴权导致鉴权无测试 | 误报 | `tests/test_api_auth.py` 明确以 auth enabled 覆盖 JSON/HEAD/range/OpenAPI/SSE |
| 前端测试多为源码正则 | 确认且原文低估 | 11 个脚本中 10 个读取源码；其中部分同时有行为测试 |
| CI 无覆盖率/打包冒烟 | 确认 | Windows 单矩阵与产品目标一致，不应单独视为缺陷 |
| lint 不扫描 desktop/scripts | 确认 |
| 架构白名单/opt-in 检查 | 部分确认 | 是维护债务，不是运行时 bug |
| test_render 恒真断言/写真实 uploads | 确认当前工作区 | 属未提交 A4 测试，见第六节 |
| architecture.md 失真 | 确认 | 仍列 langchain，Electron 实际为 43.1.1 |

## 六、当前未提交工作区观察

复核期间另一组 A4 版式改动持续写入工作区。本节不评价其最终设计，只记录当前快照中可证明的回归，避免误归因到 `bdaa842`。

### W-1 复核期间出现后已修正：HistoryDao 引擎版本硬编码

- 复核中途，`backend/score_trans/models/render/layout.py` 已升级为 `publication-5`，而 `HistoryDao.update_page()` 一度仍硬编码写入 `publication-4`。
- 最新快照已改为参数化写入 `PUBLICATION_ENGINE_VERSION`，该回归当前不再成立。
- 保留此记录是为了说明报告为何必须对持续变化的脏工作区重新取证，不能依赖一次 grep 结果。

### W-2 当前 A4 改动的聚焦测试已恢复通过，但完整测试仍有一项失败

第一次运行曾因旧 engine/schema 断言得到 `145 passed, 5 failed`；并发改动同步测试后，最新结果为：

```text
150 passed
```

聚焦测试证明 `tests/test_render.py tests/test_history_service.py tests/test_api_routes.py` 当前通过。完整测试最新结果为：

```text
630 passed, 1 failed, 1 skipped
```

唯一失败为 `tests/test_export.py::test_rendered_pdf_export_is_not_monochrome_and_hides_helper_text`：默认整体缩放后 PDF 墨迹比例约 `0.089%`，低于原测试的 `0.1%` 下限。这里不能机械降低阈值；应先检查 67% 默认版式的实际 PDF 可读性，再决定这是产品回归还是测试基线变化。

### W-3 当前新增测试污染真实 uploads 目录

`tests/test_render.py::test_batch_render_uses_jianpu_text_title_over_default` 直接构造默认 `RenderActions()`，没有注入 `tmp_path` uploads；测试会写用户缓存。测试中还存在已被前一条断言包含的恒真尾部断言。应改为注入临时 UploadService，并删除恒真条件。

## 七、历史问题复核

| 编号 | 结论 |
|---|---|
| N25 | 仍存在；见 P2-19 |
| N26 | 仍存在；AI `_http.py` 和 OCR HTTP provider 每次使用模块级 `httpx.post/stream`，无客户端连接池复用 |
| T1/T2 | 集成/E2E 缺口仍存在，但鉴权本身有专门测试，原报告对此表述过头 |
| R1 | 主要修复有效；“role 自由字符串必然造成错配”未证实 |
| R2 | LatestAsyncGate 主体有效；`loadSvg` 在 `nextTick` 后缺少第二次 generation 检查 |
| N10/N11/N13-N19 | 本次只做针对性抽查，不能写成整组全部重新证明；已抽查项目未见回归 |
| body.userSelect | 仍未修；见 P2-29 |
| Settings/Task PRAGMA | 配置不一致；原报告忽略 sqlite 默认 timeout，需要修正文案 |
| JAVA_HOME | AGENTS.md 契约与实现仍不一致；见 V-4 |

## 八、建议修复顺序

1. 先修 P1-1、P1-2：都是确定复现且修改面小的渲染断链。
2. 修 P1-7、P1-8：两项都可能覆盖或串写用户数据，必须加批次 identity/epoch 测试。
3. 修 P1-3、P2-28：收紧本地文件和 Electron 导航/bridge 边界。
4. 修 P1-5、P1-6：为 Audiveris 建立有界进程生命周期，并给打包 JDK 做布局验收。
5. 修 P1-4、P1-9、P2-22、P2-23：统一 MIDI channel、tick、BPM 和播放器时间模型。
6. 修 P2-7 至 P2-12：统一 SQLite 连接策略、SSE subscriber 模型和上传/渲染临时文件生命周期。
7. 对 V-1 做真实 OCR 样本矩阵；对 V-2/V-3 做 Windows 发布流水线验收。
8. 完成当前 A4 工作区后处理 W-2/W-3，并重新运行完整 632 项测试，再声称全量测试通过。

## 九、验证记录

本次已执行的关键检查：

```bash
# venv 确认
.venv/Scripts/python.exe -c "import sys; print(sys.executable)"

# P1 最小复现
SCORE_TRANS_API_AUTH_DISABLED=1 .venv/Scripts/python.exe <render/file probes>

# 当前测试数量
.venv/Scripts/python.exe -m pytest --collect-only -q
# 结果：632 tests collected

# 当前未提交 A4 改动的聚焦测试
SCORE_TRANS_API_AUTH_DISABLED=1 .venv/Scripts/python.exe -m pytest -q \
  tests/test_render.py tests/test_history_service.py tests/test_api_routes.py
# 结果：150 passed

# 后端完整测试
SCORE_TRANS_API_AUTH_DISABLED=1 .venv/Scripts/python.exe -m pytest -q
# 结果：630 passed, 1 failed, 1 skipped

# 前端类型检查
cd desktop && pnpm typecheck
# 结果：通过
```

由于工作区在复核过程中持续接收另一组未提交改动，本报告没有把原始 `623 passed, 1 skipped` 继续当作当前证据。当前完整测试集仍有一项 PDF 墨迹比例断言失败，因此没有声称完整测试集通过。
