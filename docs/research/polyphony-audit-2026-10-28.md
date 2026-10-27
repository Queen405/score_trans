# 复调识别专项实测：Spanish Romance 与 Bach BWV 772

日期：2026-10-28。工作区 HEAD：`312ddb05178e1bc50ac542232d92b4bc8b08a967`。

## 结论

当前项目**具有实际可用的基础复调表示能力，但不能认为复调图片识别与后续输出已经整体正确**。

- 正确识别的 MusicXML 中，多 voice 的起点、时值、音高能够保留下来；对本次三张图片的 852 个 OMR 音符事件，Python 解析及 MusicXML 再导出均未新增这些字段的误差。
- 指定吉他谱的主要识别错误集中在第 17–20 小节；巴赫的主要问题集中在第 9–10、15、22 小节。
- 用户当前设置是 `flatten`。它会把同谱表并行声部串接，不能用于保持这张吉他谱的复调语义。`auto/preserve` 对正确输入可保持全部 398 个声部音符事件，但不会自动修复错误 OMR。
- 连续三连音的括弧位置、特殊和弦的每音时值、MIDI 的同音重叠与延音线仍有独立问题。
- 现有相关自动化测试 448 项通过；真实谱图、文本往返和实际声部语义仍存在覆盖缺口。

本次为调研和验证，未修改产品业务源码、用户设置或现有谱图。新增的是本报告和 `build/polyphony-audit-20261028/` 内的脚本、输入副本、识别产物、分析数据及可视化。

## 1. 环境与样本来源

所有研究脚本通过 **Bash** 执行，Python 固定使用 `.venv/Scripts/python.exe`。实际 `sys.prefix` 指向项目 `.venv`，基础解释器为 `E:/ENV/Miniconda`。没有使用系统 Python 替代 venv。

JDK：验证 `E:/ENV/JAVA/JDK25/bin/java.exe` 存在。OMR 使用项目当前 `third_party/audiveris/gradlew.bat`，通过正式 `AudiverisService.recognize()` 调用，重新编译运行当前源码；不是复用此前缓存的 MXL，也不是使用较旧的安装目录 JAR。

参数：3 GB Java 堆、自动放大开启、最小长边 2500、像素上限 45000000、`implicitTuplets=true`、保存 OMR 和导出 overlay。像素上限来自当前应用保存的设置。指定图片会先从 1653×2339 放大到约 1767×2500。

初次沙箱执行遇到 Gradle 网络权限限制，取得工具批准后重跑成功。额外测试最初因用户数据库只读发生 9 项环境失败，改为项目内隔离的数据/缓存目录后 202 项全部通过；没有把这些环境失败计为产品缺陷。

### 指定图片

实际原文件：

`D:/tmp/score_trans/cache/uploads/aebc3e70bfc2/spanish_romance_guitar_a4_page_001.png`

另一个上传缓存副本 `db6d9b065435` 内容相同。尺寸 1653×2339，SHA-256：

`edd3c39d2c87be90f6dced16518eee16c0756554a005c2cd64814c401d91f462`

对应仓库 PDF：`examples/其他/spanish_romance_guitar_a4.pdf`，全曲一页 32 小节。原出版来源是 [Mutopia Spanish Romance，ID 795](https://www.mutopiaproject.org/cgibin/piece-info.cgi?id=795)，授权 CC BY-SA 2.5。下载了对应 LilyPond 与 MIDI 作为参照。

### 网上补充样本

经 Exa 搜索取得 [Mutopia Bach Invention 1，BWV 772，ID 40](https://www.mutopiaproject.org/cgibin/piece-info.cgi?id=40)，授权 CC BY-SA 3.0。下载 A4 PDF、LilyPond、MIDI，将两页分别按 200 DPI 转为 PNG，分别调用正式 OMR。第一页为原谱第 1–12 小节，第二页为第 13–22 小节。

三次成功运行耗时约为：吉他 32.7 秒、巴赫第一页 50.0 秒、第二页 35.0 秒。它们包含 Gradle 启动开销，不能作为纯识别性能基准。

## 2. 验证方法及统计边界

验证链：

`原图 → Audiveris MXL → 独立读取 XML 时间游标 → 项目 JianpuScore → 简谱文本 → 重新解析 → SVG/MIDI/MusicXML`

原始 XML 独立解析使用 `divisions`、`backup`、`forward`、`chord` 计算位置，与产品解析器分开实现。精确匹配键为：

`(谱面小节序号, 谱表, 小节内起点, 时值, MIDI 编号表示的书写音高)`

所有时值用 Fraction，不用浮点近似。使用多重集合，保留不同声部在同一时间奏同音、但时值不同的事件。

**精确率 = 完全匹配事件 / 识别事件；召回率 = 完全匹配事件 / 参考事件。** 不是只判断音高，也不是整个系统的泛化准确率。统计不把休止符、力度、连奏线、装饰音、指法、文字、声部编号重命名纳入逐音分数。声部正确性另以首小节明细、分层结构及往返测试核验。

吉他参考数据根据同版 LilyPond 的 melody/middlevoice/bass 三层建立，共 398 个书写音符事件。旋律与中声部每拍首音共用符头，但属于不同持续时值的声部事件，因此不能简单去重。出版 MIDI 对同起点同音做了合并，且吉他实音比书写音低八度；校正八度后，308 个唯一“起点+音高”全部与手工参考吻合。MIDI 此交叉检查不单独证明三层时值，时值来自 LilyPond 和谱图。

巴赫参考从出版 MIDI 提取，并按谱面小节及 LilyPond 的延音线分段：尤其第 16–18 小节低音 `half ~ sixteenth`，MIDI 会合成一个 9/4 拍音，需要还原成 2 拍与 1/4 拍两个书写事件。避免把合法延音拆分误判为 OMR 错误。

## 3. 图片识别结果

| 样本 | 参考事件 | OMR 音符事件 | 完全匹配 | 精确率 | 召回率 | 逐音不一致的小节 |
|---|---:|---:|---:|---:|---:|---|
| Spanish Romance 全页 | 398 | 387 | 359 | 92.76% | 90.20% | 17、18、19、20 |
| Bach 第 1 页 | 260 | 256 | 230 | 89.84% | 88.46% | 9、10 |
| Bach 第 2 页 | 207 | 209 | 205 | 98.09% | 99.03% | 原谱 15、22（页内 3、10） |

吉他 28/32 小节、巴赫 18/22 小节在上述逐音字段上完全一致。这里的“一致”不意味着所有表情符号和视觉布局也正确。

### 3.1 吉他：正确的第一小节是什么

以四分音符为一拍，第一小节应为：

| 声部 | 音高与起点 | 持续时间 |
|---|---|---|
| 旋律 | B5，起点 0、1、2 | 每音 1 拍 |
| 中声部 | 每拍 B5、B4、G4，拍内起点 0、1/3、2/3 | 每音 1/3 拍 |
| 低音 | E3，起点 0 | 3 拍 |

OMR 正确输出 voice 1、2、3，时值 divisions=6，旋律 duration=6、中声部 duration=2、低音 duration=18，并用 backup 返回同小节开头。项目解析也正确保留。第 1–15 小节的所有音符字段均一致，说明基础三声部、持续低音、隐含三连音并非整体不支持。

### 3.2 吉他：第 17–20 小节

| 小节 | 参考/识别/匹配 | 具体问题 |
|---|---|---|
| 17 | 13 / 14 / 1 | 本应新调 E 大调、三声部齐起；识别出额外 2 拍高音，中声部变普通八分音符，低音从第 2 拍才开始，最多出现五个 voice；事件末端达到 13/2 拍 |
| 18 | 13 / 13 / 8 | 节奏仍正常，但 G♯5 被记为 G5，三个 G♯4 被记为 G4，合计五个事件错半音 |
| 19 | 13 / 9 / 2 | 两个 D♯5 变 D5，伴奏三连音丢失，音符减少且部分时值变长，小节末端超过 3 拍 |
| 20 | 13 / 5 / 2 | 原本三层变成两层，大量伴奏消失；C𝄪5（等音 D5）未正确处理，出现错误音高与超拍 |

原谱换调在第 17 小节，但输出 XML 的新调号直到第 20 小节才出现；第 17 小节个别 G♯ 能识别成临时升号，不代表正确理解了全局调号。该错位与第 18–19 小节系统性缺升号相符。

Audiveris 日志同时报告 `MeasureStack#17/#19/#20 no correct rhythm`。引擎仍导出了 MXL，因此“进程成功、输出存在”不是正确性保证。

额外观察：输出中出现原谱没有的 `pp` 力度。这未纳入逐音评分，但说明符号误检也存在。

### 3.3 巴赫：第 9–10 小节

第 9 小节下谱表在小节内从低音谱号切换到高音谱号。OMR 没有正确应用该变化，后续音高继续按低音谱号解释。

- 第 9 小节：20 个参考音符只匹配 2 个，输出 16 个；上声部后半句提前 1/4 拍，下声部音高和节奏同时出错。
- 第 10 小节：20 个参考事件匹配 8 个；上声部正常，下声部 12 个音符全部音高错误。例如 E4（64）识别成 G2（43），这不是固定八度转调。
- 到下一行第 11 小节，显式谱号重新出现后恢复正确。

这是谱号上下文识别问题，后端保留声部并不能修正已经错误的 `<pitch>`。

### 3.4 巴赫：第 15、22 小节

- 第 15 小节下声部后段：本应 C♯4 的十六分音符被识别成两个 C4，时值分别 1/3、1/6；最后 E4 从 15/4 拍推到第 4 拍，发生超拍。这与错误三连音推断/节奏重构有关，尚未以开关对照确定是哪一个 Audiveris 子阶段造成。
- 第 22 小节终止和弦：参考上下谱表合计 5 音，OMR 输出 6 音，多出上谱表 F4（65）。其余五个和弦音正确。
- 第 16–18 小节延音书写分段本身不是 OMR 错误；本次参考已做相应处理。

## 4. 后端转换和模式对照

### 4.1 MusicXML 解析与再导出

| 样本 | XML → 模型的逐音字段保持 | 模型 → MusicXML → 模型 |
|---|---:|---:|
| 吉他 | 387/387 | 387/387 |
| 巴赫第一页 | 256/256 | 256/256 |
| 巴赫第二页 | 209/209 | 209/209 |

这说明本批真实样本的主要音高/时值错误首先发生在 OMR，而不是 Python 的 backup/forward 游标处理。但是它也意味着错误 OMR 可以原样传到后续流程。

相关代码：`backend/score_trans/domain/parse/musicxml.py` 的 `_parse_measure_events`、`_split_part_by_staff`，以及 `domain/voices.py` 的时间区间重叠判据。

### 4.2 当前设置 flatten 的实际影响

只读查询当前桌面数据目录的 settings.db，得到 `polyphony_mode=flatten`。发布默认 JSON 和前端初始值均为 auto；设置加载后会覆盖初始值，RecognizeView/ConvertView 会把该值发给后端。因此不能只看源码默认值推断当前用户实际使用 auto。

`domain/write/jianpu_text.py` 中，flatten 明确不生成 `&`，按原声部顺序串行输出。第一小节会变成：

```text
7' 7' 7' $7'75$ $7'75$ $7'75$ h3,. |
```

正确 auto 文本则是：

```text
7' 7' 7' & $7'75$ $7'75$ $7'75$ & h3,. |
```

第一条重新解析后，伴奏从第 3 拍开始、低音从第 6 拍开始，原来的 3 拍并行音乐串成末端 9 拍的事件流。小节元数据仍可标成 3 拍，进一步造成实际事件与拍号不一致。

实际吉他 OMR 文本 flatten 往返后，387 个音符仍都存在，但只有 100 个保留原来的小节内起点/时值/音高。这不是“少了一些和弦”的轻微退化。

为排除 OMR 的影响，额外由原谱参考建立**控制用**正确 MusicXML，明确不把它当作识别结果：

| 模式 | 参考事件 | 往返完全一致 | 第一小节行为 |
|---|---:|---:|---|
| auto | 398 | 398 | 三层在相应拍点同时进入 |
| preserve | 398 | 398 | 同上 |
| flatten | 398 | 92 | 伴奏推到第 3 拍、低音推到第 6 拍 |

### 4.3 auto/preserve 也不能掩盖错误 OMR

对实际吉他 MXL 生成 auto/preserve 文本，再调用正式简谱解析器，二者均报错：

`第 19 行第 21 列：第 1 声线超拍：实际 13/2，小节时值 3。`

文本第 19 行对应谱面第 17 小节。正确的逐声部容量校验阻止了继续解析，但缺少前置的 OMR 质量处理，导致转换器能够生成其自身解析器不接受的文本。

注意：**不能据此说初次 pipeline 必然失败。** `exec/pipeline/actions.py` 先从 scores 写文本，再直接用同一 scores 渲染 SVG，并没有先重新解析文本。因此初始预览可生成三页，随后文本编辑、重渲染或按文本导出时才暴露问题。flatten 时，初始结构化预览与文本再解析后的预览也可能不一致。

巴赫第一页三种模式的逐音字段均保持 256/256，因为拆成上下两个谱表后，每谱表基本是一条声线。它不能作为 flatten 适用于同谱表复调的证据。

巴赫第二页三种模式均仅保持 206/209：第 15 小节的异常分数时值在文本化后由 1/3、1/6 变成 1/2、1/4，最后音进一步后移。问题涉及不完整连音组/时值表示路径；`safe_duration_affixes()` 有近似回退机制，但没有为此次个案完成更细的函数级因果隔离。

## 5. 排版与播放的独立问题

### 5.1 三连音弧线逐组上移：已复现

即使使用完全正确的控制 MusicXML，第一小节的三组三连音弧线也会逐组上移，第三组靠到上方旋律行。真实 MXL 的直接渲染同样出现。

原因在 `services/render/engraving/renderer.py::_draw_tuplets`：按每个不同 span 的出现顺序生成 group_order，然后从 y 减去 `group_order * tuplet_stack_gap`。这把时间上相邻、并不嵌套的三组也当成需要不断向上堆叠的对象。默认每组相差 16，第三组额外上移 32。

建议按真正重叠/嵌套关系确定层级，同一声部时间上分离的组使用相同层级。证据包括 `romance-control-auto-1.png`、`spanish_romance_guitar_a4_page_001/raw-render-1.png`。

SVG 的同起点 x 坐标抽查：控制页 181 组、真实第一页 126 组，按音符内部 translate 提取均无超过 1 的差异。这只验证局部坐标数据，不代表所有图形外观都正确。几何诊断产生数百条一般 `geometry-overlap`（包含符尾/连线包围盒），未将其直接计为数百个排版缺陷。

### 5.2 同音不同持续时间的 MIDI：存在兼容性风险

控制谱第一拍 B5 同时属于 1 拍旋律和 1/3 拍伴奏。导出 MIDI 为同一 channel 0、同一 note 83：

```text
0 拍：note_on 83
0 拍：note_on 83
1/3 拍：note_off 83
1 拍：note_off 83
```

`ExportService.export_midi_scores()` 对每个 pitch 独立发开关音，未做同通道同音重叠的合并或通道分配。不同 MIDI 音源处理重复 note_on 的方式可能不同，因此不能保证长音不会被早到的 note_off 截短。这里验证了 MIDI 字节事件，**没有完成真实音源听感测试，不能断言每一种播放器必然截断**。

### 5.3 延音线在 MIDI 中再次触发：已确认事件行为

巴赫第 16 小节下声部 D4 的半音符与十六分音符有延音线，参考 MIDI 连续发声。项目导出在连接点实际发出 `note_off 62` 紧接 `note_on 62`。导出代码没有依据 tie_start/tie_stop 合并持续区间。

本次页内导出的连接点位于 14.25 拍，而正常局部位置应为 14 拍；额外 0.25 拍来自前一个异常小节的扩展。这进一步展示了局部超拍如何影响之后的整体时间线。

### 5.4 特殊和弦模型存在信息损失：最小控制复现

[MusicXML 4.0 的 chord 规范](https://www.w3.org/2021/06/musicxml40/musicxml-reference/elements/chord/)允许和弦后续成员比首音短，如弦乐多重停止。

最小输入：C4 持续 4 拍，带 `<chord/>` 的 E4 持续 2 拍。当前解析将二者合成一个 `Event(duration=4, pitches=[E4,C4])`，E4 的独立 2 拍时值丢失。后续成员上的 tie_start 也未保留。

根因是 chord 分支把 pitch 合入 last_event 后直接 continue；Event 只有一个公共 duration/tie 状态。这是**额外构造的边界案例，不是本批谱图中的实际错误**，但不能据此宣称模型对所有复调/复音和弦无损。

## 6. 测试覆盖及修复优先级

运行并通过：

- `test_polyphonic_layout.py`、`test_convert.py`、`test_jianpu.py`：246 项。
- `test_voices.py`、`test_render.py`、`test_export.py`、`test_playback_timeline.py`、`test_repeat_playback.py`：隔离数据目录后 202 项。

合计 448 项，不是全仓库完整测试。图像识别实验是另外三次真实执行，不是 mocked OMR。

建议顺序：

1. **高优先级：避免真复调使用 flatten。** 明确该模式为有损串接；检测到时间重叠时提示或要求显式选择。用户当前设置建议改 auto，但本次未自动改动。
2. **高优先级：在 OMR 输出与文本生成之间做结构质量诊断。** 按谱表/声部检查事件末端、容量、缺失节奏、突增 voice，并把日志中的 no correct rhythm 绑定到可见小节；对无法保持语义的输出不要仅显示成功。
3. **高优先级：补真实谱图的回归基准。** 固定本次图、参考事件和明确的错误小节，检查 OMR → 文本 → 重解析的一致性。不要只做 SVG 字符串测试。
4. **中优先级：修复换调、换谱号附近的引擎识别。** 用吉他 17–20 和巴赫 9–10 作最小裁剪样本，再对 implicitTuplets、分辨率及符号识别阶段做有控制的对照。不能仅调大图后宣称解决。
5. **中优先级：修复三连音括弧堆叠和不可表达时值的静默近似。** 不完整连音组应有明确诊断和保留原始数据的策略。
6. **中优先级：MIDI 使用明确的声部事件调度。** 合并有效延音链；定义同通道同音重叠策略，分别验证 MIDI 消息与实际音源。
7. **后续：补每音独立时值/延音的表示，或将这种 chord 拆成明确声部。** 避免把合法 MusicXML 过早压缩成单 duration 的和弦事件。

## 7. 复现与交付文件

所有产物目录：[build/polyphony-audit-20261028](../../build/polyphony-audit-20261028/)。

主要文件：

- `inputs/`：指定 PNG 副本、网络 PDF/PNG、原版 LilyPond/MIDI。
- `run_omr.py`：通过正式服务运行识别。
- `download_samples.py`：固定来源下载与第一页栅格化。
- `analyze.py`：参考数据、独立 XML 解析、逐音对照、三模式往返、导出。
- `controls.py`：正确吉他谱对照、出版 MIDI 交叉检查、特殊和弦和 MIDI 控制实验。
- `render_raw.py`：直接从 OMR 模型渲染与导出，模拟 pipeline 的结构化路径。
- `summary.json`：机器可读摘要。
- 每个样本子目录的 `analysis.json`、`truth.json`、`.mxl`、`.omr`、`.log`、`.jianpu`、`.svg`、`.mid`：逐小节差异与原始证据。
- `controls.json`、`alignment.json`、`tie-midi-evidence.json`：附加实验。
- `manifest.json`：输入哈希；`source-snapshot/` 与 `source-snapshot.json`：关键 Python 源码快照及哈希。
- `pytest.log`、`pytest-extra.log`、`pytest-extra-isolated.log`：测试记录（含环境失败原始日志）。

在项目根目录 Bash 中复现分析：

```bash
export SCORE_TRANS_API_AUTH_DISABLED=1
export SCORE_TRANS_DATA_DIR=D:/CODE/MyProjects/score_trans/build/polyphony-audit-20261028/data
export SCORE_TRANS_CACHE_DIR=D:/CODE/MyProjects/score_trans/build/polyphony-audit-20261028/cache
.venv/Scripts/python.exe build/polyphony-audit-20261028/analyze.py
.venv/Scripts/python.exe build/polyphony-audit-20261028/controls.py
.venv/Scripts/python.exe build/polyphony-audit-20261028/render_raw.py
```

重新识别建议在 run_omr.py 中选择新的输出目录，以免引擎保存产物与旧结果混用。首次下载 Gradle/依赖需要联网权限。

## 8. 限制

- 本次是两首乐曲、三张清晰印刷谱图，不能外推手写谱、扫描噪声、管弦乐总谱、交叉谱表等整体准确率。
- 没有测试云端 AI 转录、Python 文字 OCR、完整 Electron 交互与真实音源听感；没有把“逐音字段相同”扩展成“所有音乐符号相同”。
- 简谱测试统一使用 target_key=C，保持书写音高；吉他实音低八度问题在出版 MIDI 交叉检查中显式处理，不算 OMR 音高错误。
- 工作区开始时已有未提交修改，研究期间又出现反复跳房子/实时预览相关的外部修改。本报告未覆盖它们；已检查 renderer 的相关增量为 ending span 限制，不涉及本报告定位的三连音函数。关键源码快照用于说明测试环境，不能将整次实验标成干净 HEAD 的基准。
- build 目录通常被 Git 忽略，若需长期保留实验应另行归档。报告本身位于 docs/research。
