# 简谱引擎架构

## 边界与入口

这是独立的识别处理管线，不是 HTTP MVC 服务。借用 MVC 的职责划分：models 是数据契约，pipeline 是流程控制，rendering/provenance 是输出投影；CV 和 LLM 各自为有边界的处理模块。只有 CLI 和 I/O 层接触文件输出，只有 recognition 发起模型请求。

应用入口是 `pipeline.runner.run(config, llm_client=None)`，返回 `TransJpResult`。CLI 解析参数、记录日志并转换退出码。旧 `cli.run` 保留将 `EngineError` 转为 `SystemExit` 的兼容行为，新 Python 调用方应使用 pipeline 入口，异常可由调用方处理。

顶层旧文件是兼容导入适配器；新实现不得从它们反向导入。不为尚不存在的能力预建空的 detector/classifier 文件。相关算法先聚合为内聚模块，后续按实际复杂度拆分。

## 分层职责与允许依赖

同层模块可以互相调用；下表列出的才是允许的跨层依赖。`tests/test_architecture.py` 用 AST 检查静态依赖、禁止导入 `score_trans`、禁止纯算法层做文件 I/O 或退出进程。

| 层 | 主要内容 | 允许依赖 |
|---|---|---|
| models | contracts、geometry、raster、notation、errors；仅标准库 | 无 |
| raster | runs、sections、filaments、projections | models |
| preprocess | 放大、Otsu、保守去倾斜 | models、raster |
| structure | 行分割、候选墨迹、数字带、分段基线 | models、raster |
| symbols | 可绘制简谱语法解析 | models、raster |
| recognition | prompt、HTTP 客户端、JSON 规范化、并发行转写 | models |
| matching | 保序匹配、声部、附属符号、同一行连线 | models、raster、symbols |
| validation | 时值、几何诊断 | models、symbols |
| rendering | 字形路径、几何图元、SVG/PNG 内存渲染 | models |
| provenance | SourceMap v1、source_id、文本锚点 | models |
| io | 读图、裁剪图落盘、响应捕获、回放、资产、产物写入 | models |
| pipeline | 组合根和阶段计时，注入模型客户端和字形资产 | 除 symbols/raster 外的上述门面 |

NumPy/Pillow 属于图像计算依赖；PyMuPDF 只负责把同一份 SVG 栅格化。渲染器通过参数得到字形字典，不直接打开字体或资产文件。测试中的 desktop 契约验证可导入后端 DTO，生产引擎不能。

## 数据流

1. **输入和归一化**：读取 RGB；透明输入合成到白底；保留源图像素坐标。长边不足目标值时最多放大 4 倍，记录实际 x/y 比例，避免整数 resize 造成坐标误差。
2. **去倾斜**：缩小探测图的长横线估计全局斜率。至少三条长线方向一致才启用垂直 shear；证据不足不变换。不是任意旋转或透视校正。`Transform` 保存比例、斜率、偏移，负责工作图回原图。
3. **行与局部结构**：水平投影分割逻辑行，输出 RowSegment；I/O 层保存裁剪图。对原始行灰度 Otsu 二值化，不给定位图做中值滤波，避免擦掉点和细线。CV 在 LLM 调用前生成 RowAnalysis。
4. **候选与语义识别**：structure 生成 CandidateRegistry（算法版本 3），排除相邻数字上方/下方的小型点状基线带，保留原始 components 供附属符号定位。rendering 在内存生成最多 24 格/页的图册，io 保存。RowRecognitionRequest 包含原行图、图册路径和注册表；在线 LlmClient 发送多张 PNG，原行最长边限制 2000，图册不缩放。v2 token 引用 candidate_ids；原始响应和规范化响应分别保存。LegacyRowTranscriberAdapter 兼容单图注入客户端，不能作为 v2 坐标回退。
5. **匹配**：复制 token 后附加几何。v2 直接查询当前行注册表，校验编号、类型、主体数量、互斥墨迹、声部、小节顺序；冲突关联的 token 均留空，不进行坐标回退。和弦按高到低绑定多主体。附属符号受真实主体、相邻未认领主体及小节边界约束；共享线允许复用，点/升降号/延长线多归属时留空。v1 保留原始可选 x/w/y/h，仅接受距离不超过 0.6 倍字高、次优差距至少 0.5 倍字高的双向唯一最近匹配，不补位、不裁剪、不全行拉伸。
6. **校验和输出**：无效或越界几何在 SVG/SourceMap 生成前统一拒绝；时值冲突仅报诊断；生成 UTF-16 锚点、SourceMap、路径 SVG、原图预览。完整管线不使用矩形/源码回退。

## 栅格与几何

- **Run**：一条扫描线上的连续黑像素区间，end 为排他端点。
- **Section**：相邻扫描线中的相交 run 连接成区域；线段检测限制 run 长度变化，数字交叉处不把整块字形吞进线条。
- **Filament**：沿横线使用竖向 run 测厚，沿竖线使用横向 run 测厚。拟合中心线后检查斜率、残差和覆盖率，再合并近似共线的小间隙。输出端点、厚度、斜率和像素支持率。长横线在数字交叉处允许有限延伸，但必须逐列得到真实墨迹支持。
- **局部投影验证**：竖向 filament 在数字带上下界内检查覆盖率，拒绝短数字竖笔画；不套用五线谱五条线、staff interline 或跨谱表连接规则。
- **数字候选**：只在主体 mask 上擦除长结构线的拟合笔画，不抹整块包围盒。紧凑墨迹按基线分组，再过滤小于同带典型字高的点。基线以分段中位点插值，描述轻微局部弯曲；严重翘曲不在保证范围内。
- **TokenGeometry**：主体、绘制 primitives、命中边界和警告。数字字形保留工作图角点的逆变换，避免去倾斜后又画成水平包围盒；线条保留端点。共用减时线的物理 primitive 相同，但 hit_bounds 按相邻音符分隔。

参数按实测字高归一化：线厚上限约 0.23 倍字高、小间隙约 0.45 倍字高、中心线斜率上限 0.18、像素支持率至少 0.65；小节线局部覆盖率至少 0.72。它们是可测试的初始规则，真实扫描分布仍需更多样本验证。

## 输出、失败与兼容

`jianpu.txt`、`overlay.svg`、`score-link-map.json`、`text_anchors.json` 文件名保持稳定。source_id 始终为 `s0:r{row}:t{token}`，不存在真实 MusicXML 的简谱来源不伪造 locator。几何与文本置信度分开：SourceMap grade 仍是行识别 confidence，filament support 是几何证据，不混为识别准确率。

`matched/partial` 允许绘制有证据的 primitives；`unmatched/ignored/unsupported` 无图元时不进入 SourceMap。文字位置有效性由 TextAnchor.valid 表达，不能因 CV 匹配失败而把本来存在的文本判为无效。缺少文本锚点的可见元素保留几何并输出警告，后续 desktop 按 valid anchors 决定可导航集合。

退出码保持 0 成功、1 图像失败、2 无行、3 全行识别失败、4 输出失败、5 参数错误。内部使用 EngineError，CLI 边界转换。单行模型失败、缺失时值线、缺少声部、和弦数量不一致局部降级；无法定位时不猜位置。复杂演奏法、连音组、跨行连线暂不绘制。

后端接入时注册 SVG 到 `overlay_svg_file_id`，不能走 Audiveris 仅接受 PNG 的 `find_native_overlay()`。后端/desktop 集成和发行打包不属于本次引擎范围。独立 wheel 必须包含 prompt、13 个字形及两份许可证。

## 测试边界

- AST 架构约束、原始 token 不可被匹配过程修改。
- 横/竖线方向、正负斜率、小间隙连接、大间隙隔离、平行多线、精确笔画擦除。
- 局部投影、漏首音、点/数字混淆、粘连、声部重置、和弦、时值符号、弧线。
- 实际尺寸与 inverse transform、SVG 路径颜色/透明度、SourceMap 与文字锚点契约、CLI 退出码。
- 《梁祝》固定人工响应只覆盖三行 60 token，验证位置和输出，不声称在线 LLM 准确率；其他未转写行保持原图。
- `--debug` 展示所有候选线和最终命中边界，记录变换与阶段耗时，便于离线复现。

## v2 回放与质量边界

`manifest.json` 保存源图字节哈希、裁剪像素哈希、work_y_top、Transform、候选算法版本和注册表哈希。
v2 ReplayClient 在写输出前检查源图、参数、行数量、尺寸及全部注册表，再恢复冻结编号；不使用重新计算的编号替代保存的编号。
请求中的模型名称和温度等信息仅用于审计，不参与无网络回放的身份校验。失败行可以与 v2 成功行共存。

`RecognizedToken.x/w` 为可选历史提示；`candidate_ids` 为元组。`RowResult` 增加 schema_version、registry、unresolved_candidates、raw_response、complete。
未定位不删除语义文本；未知音不写成 0。complete 表示转写是否明确缺失，不代表内容正确，也不代表几何全部定位。
合法候选编号可能被模型认错数字，结构校验无法独立证明音高语义；不得将 matched 或候选召回率当作识别准确率。

## v3 主体分类路径

`CliConfig.recognition_mode` 默认为 `bodies`；`notation` 保留 v2。回放根据冻结协议选择路径，不根据 CLI 模式改写旧响应。旧注入单图/多图客户端继续兼容；只有支持 `classify` 的客户端进入 v3。

`models/classification.py` 定义批次请求、单候选分类及批次结果，`CandidateRegistry` 算法版本保持 3。structure 过滤非主体/歧义候选后稳定排序，每批最多 12 个，rendering 为指定编号生成图册。上下文仍是原行 PNG；图册使用完整尺寸。recognition 使用独立主体分类 system prompt，禁止整行文本、坐标、节奏、八度推断；只允许 0–7/barline/unknown。模型自报置信度仅保存，不作为正确率证明。

pipeline 以全局线程池限制批次并发数，避免行并发乘以批次并发。在线每批最多三次 HTTP 尝试（首次加两次重试），429/408/5xx/连接错误可重试，认证和其他 4xx 不重试。截断响应不得修补成已识别主体。批次完成后主线程写原始/规范化响应和 manifest；一批失败不丢弃其他批次。所有批次请求失败或格式无效时保存诊断再抛出 EngineError(3)。

structure 按实测小节线横坐标分区、基线带排序，直接使用确认的候选 ID 组装主体，不依赖 VLM 的小节/声部声明。仅孤立、垂直对齐的单列可生成视觉叠放 token；并行基线仍分别组织，不声称时间同步。重复、互斥、歧义候选拒绝，不用 0 兜底。

matching 的 v3 路径按编号绘制确认的数字主体、小节线及实测共享减时线；不调用完整音乐语法的音高排序来重排垂直数字，也不推断附属符号语义。v2 的完整附属符号识别路径保留。v3 所有音符均为 partial，表示音乐属性未验证，不表示数字一定错了。`RowResult.recognition_scope=bodies_only`，`batch_diagnostics` 独立于几何状态；`complete` 表示是否存在未解决候选，不是音乐完整性或准确性。文本以主体预览提示开头，不默认补调号/拍号，跳过小节时值检查。

manifest v3 在原有源图/候选校验之上，增加 classifier_version、所有批次文件 SHA-256 和行响应 SHA-256。回放检查候选覆盖、重复编号、批次绑定、原始响应/规范化响应一致性、图像哈希和行协议，不允许通过把全部行降为 v1 绕过 v3 manifest。哈希用于意外修改检测，不是对恶意同时篡改数据及 manifest 的安全认证。回放使用原始响应重走同一解析和组装流程。

冻结在线分类 fixture 不包含真实 API 凭据，211 主体基准离线回归锁定首轮结果，避免上线质量依赖测试期间重新采样模型。

## 实验性 melody 属性层

在 v3 几何匹配之后进入 pipeline/melody_recognition。依据主体实测字高补充上下文裁剪，structure 生成附属点/横线/变音候选；matching 提出关系并区分 unknown/confirmed/unsupported；symbols 使用 Fraction 计算局部时值和序列化，不从 pipeline 直接导入 symbols。models/melody 保存跨层 DTO。rendering 生成局部复核图册，recognition 只允许引用候选和主体编号，不接收模型生成坐标。

独占附属符号归属冲突留空，共享减时线按实测主体分别生成 hit_bounds。孤立候选关系可以本地确认；有歧义的连通主体组一次最多 6 个，组过大不拆开独立抢占。批次失败保留 unknown。原始 v3 响应先保存，增强阶段不回写其 token 编号。melody.json 中 source_id 对应原始主体；重新生成文本后计算 UTF-16 锚点。

`--body-responses-dir` 对冻结 v3 做原有哈希检查。已有 melody-manifest 时先校验全套文件，再重放局部响应；禁用复核的冻结产物恢复原来的 review_enabled，不因命令缺省改变。模型读出的元数据为 observed，无法推进有效调号/拍号状态。内部 NoteAttributes.complete 仅表示五项局部属性与时值可生成，不表示音高/节奏语义经过完整校验。melody_complete 为 false，实验入口不影响默认 bodies。

metadata 页请求和局部复核均最多三次尝试；认证错误不重试，截断输出留未知。复核证据、归属关系、工作坐标/原图坐标、分数时值序列化由 io 统一处理。manifest 的哈希用于意外修改检测，不是认证机制。各阶段质量和当前缺口见 MELODY_REVIEW.md。


局部元数据补充：structure/metadata_regions 从实测等号笔画提出局部框，rendering/metadata_atlas 输出编号裁剪，recognition 解析可见 key_text/meter_text。pipeline/local_metadata 保存候选/请求/结果，版本内以可选 sidecar 兼容旧冻结证据；存在局部记录时必须校验请求图像哈希并重放原响应。observed_local 不直接激活调号状态，possible_following_body 仅供核对。无等号的独立拍号检测与可靠生效映射仍待实现。
