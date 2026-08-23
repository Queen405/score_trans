# 简谱排版引擎布局升级：调研报告与完整实施方案

> **项目**: Score Trans — `backend/score_trans/services/render/`
> **前置会话**: <https://opncd.ai/share/E8xYjnzZ>(开源简谱渲染布局调研)
> **目标**: 在现有 `engraving.PublicationRenderer`(`publication-2`)基础上,把**页面布局结构**提升到主流商业简谱软件(JP-Word / 简谱大师 / 谱谱风 / 番茄简谱)的合理性与美观度
> **约束**: 保留对外 API 边界契约(`render_service.py` 8 方法、`main.py` 公开函数签名、render-map JSON 结构);允许为新增能力追加带默认值的可选参数
> **日期**: 2026-08-21

---

## 目录

1. [背景与目标](#1-背景与目标)
2. [调研结论(开源项目布局机制)](#2-调研结论开源项目布局机制)
3. [商业简谱排版通则(布局规范汇总)](#3-商业简谱排版通则布局规范汇总)
4. [现状评估与差距分析](#4-现状评估与差距分析)
5. [设计原则](#5-设计原则)
6. [详细方案(模块级)](#6-详细方案模块级)
7. [测试与视觉 QA 策略](#7-测试与视觉-qa-策略)
8. [阶段计划](#8-阶段计划)
9. [风险矩阵](#9-风险矩阵)
10. [验收标准](#10-验收标准)
11. [附录](#11-附录)

---

## 1. 背景与目标

### 1.1 工作脉络

| 时间 | 事项 |
|---|---|
| 2026-07-08 | 旧渲染重写设计（基于已删除的 drawing 架构，现仅作历史记录） |
| 2026-07-18 | `docs/jianpu-render-compatibility-audit.md`:旧渲染器源码已于 `15e21b6` 删除,`engraving.PublicationRenderer` 成为唯一实现;第一次设计文档的模块地图实际已被**取代**(未走 `engine/` + `svg/theme.py` 路线,而是净室重写为 `engraving/`) |
| 2026-07-19 ~ 08-20 | 兼容清理落地;审计所列 P1(跨系统连音线续接)已修;后端 430 测试全绿 |
| 2026-08-21 | 前置会话:调研开源简谱渲染项目的页面布局机制,并对照阅读了本仓库 `engraving/renderer.py` 的断行/分页/间距/连音线实现 |
| **本轮** | **输出严肃调研结论 + 完整详细的布局升级方案(本文档)** |

### 1.2 目标定义

只做**布局结构**升级,不做编辑器交互、不改识别/转换链路:

1. **合理性**:间距符合时值比例直觉;断行/分页符合出版惯例;无溢出、无重叠、无歧义。
2. **美观性**:对齐商业简谱的视觉秩序(标题区、行距节奏、歌词层次、记号避让)。
3. **确定性**:同输入同输出(现有字体内嵌机制已保证,不得破坏)。
4. **契约稳定**:API 签名、CSS 类名、`data-*` 属性、render-map 结构向后兼容(新增允许,删除/改名禁止)。

---

## 2. 调研结论(开源项目布局机制)

调研对象来自前置会话的筛选,并按"页面布局结构"重点重新核查了其中布局机制最完整的两家的**源码级实现**。

### 2.1 jodi-ivan/numbered-notation-xml(Go,478 首赞美诗生产级)

> <https://github.com/jodi-ivan/numbered-notation-xml> — MusicXML → 数字谱(not angka,与简谱同源),布局逻辑完全自研,输出 SVG,带 golden-file 快照测试。

**布局架构**(核查 `internal/staff/staff.go`、`internal/numbered/numbered.go` 及包结构):

- **逐 token 顺序布局**:每个音符被展开为一个或多个 `NoteRenderer`(符头数字 + 增时/附点 token + 小节线 token),`x` 坐标按 token 顺序递增(`x += increment`),**不做全局时间比例定位**;小节宽度 = 内容自然宽度之和。
- **长音表示**:`GetLengthNote`/`SplitNote` 把多拍长音拆成"数字 + 每拍一个增时 token"(附点化处理,按拍号 beat_type 选择 token 类型)——即**增时线按拍位分布**,而不是固定像素间距。
- **连线合并可读性**:跨拍 tie 的两音在常见拍号下合并为一个附点音符显示(`MergeNotes`),简化视觉。
- **小节内跨行**:measure 可在指定音符处拆行(`IsNewLine` / `Multiline` / `NextLineRenderer`),即**允许小节中间断行**,行尾/行首做续接处理。
- **歌词引擎**:音节匹配(`SyllableMatch.LoadOtherVerse`)把多段歌词逐音节对齐到音符;连字符(hyphen)从行首起算;右对齐末行处理;verse footnotes。
- **呼吸记号与符杠交互**:beam 在呼吸记号处断开;附点节奏在多附点情形重新分配(`AdjustMultiDottedRenderer`)。
- **页眉/署名**:credits 换行与碰撞修复、副标题、脚注;反复号左右 repeat barline、rehearsal 圈号。
- **测试**:`goldenfiles.zip` 作为 SVG 快照金样,渲染结果与金样比对。

**对本项目的启示**:token 级增量布局 + 增时按拍分布 + 小节内断行 + 多段歌词音节对齐 + 快照测试,都是当前 `publication-2` 缺失或较粗的机制。

### 2.2 lodebar2026/jpeditor(TypeScript,JP-Word 排版克隆)

> <https://github.com/lodebar2026/jpeditor> — `.jpwabc`(JP-Word)在线排版编辑器,SVG 实时预览。

**布局机制**(README 及功能描述):

- **度量一致性**:用浏览器 `getBBox` / `getComputedTextLength` 测量,**测量与渲染同一引擎**,天然一致(对照:本项目用 fontTools 量 hmtx,渲染用同一字体轮廓转 path,同样自洽——这一点我们已对齐)。
- **乐句分析断行**:MusicXML/OMR 导入时按乐句自动断行——综合**歌词标点、音乐信号(延长号/终止线/长音/休止/连线)与重复旋律结构**,在小节边界找乐句断点,并凑成疏密适中的行。
- **简谱+五线谱混排**、OMR 导入、导出 PDF/PNG/MIDI/PPTX(超出本项目范围,仅记录)。

**对本项目的启示**:断行不只是"填满行宽",还应**感知乐句**(歌词标点 + 长音/休止/延长号 + 结构重复),这是"美观"与"能看"的分水岭。

### 2.3 flufy3d/JianpuRender(TypeScript)

> <https://github.com/flufy3d/jianpurender> — 轻量 TS 库,JSON/MusicXML → SVG/Canvas。

- 数据模型直接是 `{start, length, pitch}` 事件序列 + key/time signature 表;渲染管线 `jianpu_model → jianpu_svg_render`,`noteHeight` 为基准单位缩放。
- 主打交互(高亮、播放同步),布局为顺序排版,无复杂断行。**启示有限**,其"以 noteHeight 为唯一缩放基准"的参数化方式可借鉴到主题系统。

### 2.4 Your-Jianpu(Haskell)与 Your-Jianpu-ts(TypeScript 移植)

> <https://github.com/speedyOrc-C/Your-Jianpu> / <https://github.com/Linho1219/Your-Jianpu-ts>

- 目标是**印刷质量** SVG;自定义标记语言/数据结构 → SVG。
- 文字宽度借助 Chrome(经 Node.js)测量——再次印证"**精确字体度量是布局正确性的前提**"(本项目以内嵌字体 + fontTools 解决,已满足)。
- 均已归档,布局算法公开资料少,主要作为"印刷质量目标"的参照系。

### 2.5 其他(参考级)

| 项目 | 布局要点 |
|---|---|
| felixhao28/react-jianpu | `sectionsPerLine={4}` + `alignSections`:**固定每行小节数 + 行内对齐**的经典歌曲排版;歌词逐音符 `hyphen` 标记 |
| CHChang810716/react-numbered-mus | 简单 SVG 顺序渲染,参考有限 |
| Linho1219/OpenFanqieCore | 番茄简谱格式的解析器(非完整布局引擎) |

### 2.6 调研总结:布局机制的四个层次

综合各项目,简谱页面布局可分解为四层,越往下各项目差异越大、也是"质量"所在:

| 层 | 内容 | 业界做法分布 |
|---|---|---|
| L1 页面骨架 | 页边距、标题区(曲名/副标题/词曲/调拍号/速度)、页码、多页页眉 | 各家趋同(商业软件最成熟) |
| L2 断行/分页 | 每行小节数(固定/自动)、两端对齐拉伸、末行处理、小节内断行、乐句断行、孤行控制 | 自动+拉伸为主流;乐句断行仅 jpeditor;小节内断行仅 numbered-notation-xml |
| L3 小节内间距 | 时值比例 vs 顺序等距、最小间距、增时按拍分布、附点避让、连音压缩 | 顺序增量(Go 项目)/ 时间比例(本项目)/ 固定格(react-jianpu) |
| L4 记号占位 | 八度点、减时线(符杠分组)、歌词(多段)、力度、表情栈、连音线、房子(volta)、楔形 | 商业软件最全;开源普遍残缺 |

---

## 3. 商业简谱排版通则(布局规范汇总)

来自 JP-Word / 简谱大师 / 谱谱风 / 番茄简谱的通行版面（当前 engraving 引擎的视觉参考）:

### 3.1 页面与标题区

- A4 纵向;上边距 ≈25mm,左右 ≈22mm,下边距 ≈19mm;白底。
- 曲名:居中、宋体、最大字(≈42px@150DPI)、加粗;副标题:居中、次之。
- 词/曲/编:右对齐,可两行或一行并列;位于标题区右下。
- 调号拍号行:`1=C  4/4` 左对齐,独占一行;速度 `♩=120` 同行右侧或上方表情术语位。
- 页码:底部居中,始终显示(单页也显示),格式 `1` 或 `1 / N`。
- 后续页:无完整标题区,可有简短页眉(曲名小字)或仅有页码。

### 3.2 行(系统)与小节

- 歌曲类常见**每行 4 小节**(2–6 可配);行内**两端对齐**(拉伸至版心宽);末行可不满(左齐)。
- 小节宽度**按内容密度分配**(音符多的小节更宽),不是等宽。
- 行首**不画**普通小节线(反复开始线除外);行末小节线正常。
- 行距:行高由内容决定(音符本体 + 上方记号栈 + 下方减时线/歌词/力度),行间留白均匀且大于行内净高的一半。
- 转调/变拍:在变化小节上方标注 `1=G`、`3/4`。

### 3.3 音符与节奏

- 数字 1–7(0 为休止),宋体加粗,字面大小约为一行的视觉中心。
- 高/低八度点:数字正上/正下方,逐点外扩,最多 3 点。
- **减时线**(八分=1 条、十六分=2 条……):数字下方,**按拍分组连通**,组间断开;跨拍的切分用连线(tie)表达而非硬并符杠;半拍不足者用钩(hook)。
- **增时线**:长音右侧短横,**按拍位均匀分布**于该音持续的时长内(二分 1 条、全音符 3 条),不是固定像素间距。
- 附点:数字右侧偏上;与增时线同时存在时,附点在最末增时线之后。
- 三连音等:上方方括号 + 数字,括号中间留空放数字。

### 3.4 歌词

- **一字一音**,水平居中于音符;歌词整体位于减时线/力度之下。
- **多段歌词垂直堆叠**,段间距均匀;段首可加段号 `1.` `2.`。
- 一字多音(转音):该字下方画延音横线贯穿所经音符;多音节词用连字符 `-` 连接。

### 3.5 表情、力度与反复

- 表情/速度术语:行上方靠左;力度记号(`mp` 等):音符下方、歌词之上。
- **渐强/渐弱**:楔形 `<` / `>`,跨多音符,置于谱下。
- 延长号、跳音、重音、保持音:音符上方;装饰音(`tr` 等)上方;滑音:音符间斜线。
- **反复**:‖: 与 :‖ 粗细双线 + 双点;**跳跃(volta/房子)**:上方横线 + 左端竖线下挂 + 数字 `1.` `2.`,可跨多个小节、跨行续接(开端不封口);D.C./D.S./Fine 置于小节线上方。
- 多声部:左侧**花括号**相连,声部名于括号左侧(竖排或短名横排),各声部小节线对齐。

---

## 4. 现状评估与差距分析

### 4.1 当前引擎架构(`engraving/`,publication-2)

```
JianpuScore[](多页/多声部)
  → _normalize_parts()          按 part_index 分声部
  → _build_cells()              同序号小节跨声部对齐为"单元格列",宽度=各声部固有宽度最大值
  → _break_systems()            在列边界断行:badness = |1 - 行宽/版心|³ ×1000 + 孤行罚分;
                                 行内各列等比缩放至版心宽(末行 <72% 则保持自然宽)
  → _paginate()                 顺序装页(页1留标题区 132px,后续页 54px 页眉)
  → _page_chrome()              页1:居中大标题 + 左侧调拍号速度行;后续页:左侧小字标题;页码底部居中(纯数字)
  → _draw_system()              多声部花括号(直线+小钩)、声部名、逐列绘制
  → _draw_measure()             小节内:按 start/duration 时间比例定位 + 最小间距挤压 + 溢出左移 + 连音压缩
  → _draw_event()               数字/变音记号/八度点/和弦纵向堆叠(25px)/减时线/增时线/附点/歌词/力度/记号栈
  → 连音线/圆滑线/滑音(tie 下、slur 上、跨系统跨页续接)
  → 场景图 → SVG(内嵌 NotoSerifCJKsc + Bravura,文字转 path,SHA-256 校验,渲染确定性)
```

**已有优势(保留)**:

- 布局确定性与度量自洽(内嵌字体 + hmtx 测量 + 轮廓转 path)。
- TeX 式 badness 断行 + 行宽两端对齐 + 末行阈值,基础断行质量在开源之上。
- 多声部按小节列对齐;跨系统/跨页连音线续接(2026-07 审计 P1 已修)。
- 完整 source anchor / render-map / 播放索引机制。
- 拍号/调号变化标注、反复小节线、终止线、连音符括号、显式 beams(begin/continue/end/hook)。

### 4.2 差距分析(布局结构逐项)

> 严重度:**A**=影响出版可用性;**B**=明显不美观/不合惯例;**C**=打磨项。

| # | 领域 | 现状(代码位置) | 目标(§3 通则) | 严重度 |
|---|---|---|---|---|
| G1 | 标题区 | `_page_chrome`:仅曲名(居中 40px)+ `1=C 4/4 ♩=…` 左行;无副标题/词曲/编曲;后续页为小字曲名 | 副标题居中小火;词曲右对齐;速度/表情位置规范;标题区高度按实际字段计算 | A |
| G2 | 页码 | 底部居中纯数字 `1` | 建议 `1 / N`,始终显示(已满足) | C |
| G3 | 每行小节数 | 仅自动 badness 断行 | 支持固定 N(2–6)/自动/乐句三种策略;歌曲默认 4 | B |
| G4 | 小节内断行 | 不支持;超宽小节被压进 `content_width`(`_intrinsic_measure_width` 截断) | 超宽小节可在拍位断开,行尾/行首续接(连音线/减时线/增时线) | A(长小节曲) |
| G5 | 行首小节线 | 每行首列强制画普通小节线(`draw_start_bar=cell_index==0`) | 行首不画普通小节线(反复开始线保留) | B |
| G6 | 事件间距 | 时间比例定位 + 最小间距挤压 + 溢出**整体左移**(末事件超出时全行左移,可能左溢入小节线) | 时间比例为底,**弹性分配余量**(长时值多承担拉伸),碰撞消除以右侧为准 | B |
| G7 | 增时线 | 固定 `x+17`、18px 等距,数量=拍数-1;不随小节余量伸展;与附点同在 x+17 会叠 | **按拍位分布**于持续时长,随行宽弹性伸展;附点在末线之后 | A |
| G8 | 减时线分组 | 按"事件紧邻(start+duration 连续)"连通 + 显式 beams;无拍边界意识 | **按拍分组**为主(拍边界断开),显式 beams 优先;休止/换气处断开 | B |
| G9 | 行高 | `base_staff_height=92` + 固定 extra(上 24/下 28),不看实际记号栈/歌词行数 | **按内容计算行高**(上方栈、八度点、连音符、房子、下方减时线、歌词段数、楔形) | A |
| G10 | 歌词 | 每事件 1 行歌词(y+44);无多段、无段号、无连字符、无一字多音横线;宽度计入固有宽度(好) | 多段垂直堆叠 + 段号 + 连字符 + 转音横线;行高随段数 | A(带词曲) |
| G11 | 力度/表情 | 力度文本 y+63;无渐强/渐弱楔形(模型已有 `direction_kind="wedge"` 数据);未定位文本块被置于**谱下居中**(`_draw_measure_text`) | 力度在减时线下、歌词上;楔形跨音符;表情/速度术语在**谱上方** | A |
| G12 | 反复跳跃 | `ending-line` 仅覆盖**单小节**、无竖线下挂、无跨小节/跨行续接;D.C./Fine 依赖未定位文本(谱下) | volta 括号跨小节、跨行开端续接、左端竖钩;D.C./D.S./Fine 在谱上方小节线处 | A |
| G13 | 多声部 | 直线+双小钩代替花括号;声部名横排于左侧(x-18,end 锚) | 花括号(曲线路径);声部名竖排或短名;括号钩形规范 | B |
| G14 | 主题/配置 | `PublicationStyle` 全固定;`RenderOptions` 仅 6 个字段映射;无密度/字号/页边距预设 | 风格预设(出版/紧凑)+ 关键参数可配,映射收敛在 `_style_from_options` | B |
| G15 | render-map | 仅事件主体注册锚点(审计 P3 未决) | 明确契约;若"全元素定位",派生记号(减时线/连音线/volta)注册 source role | C(需前端协同) |
| G16 | 碰撞保证 | 无全局重叠检测;记号栈/八度点/歌词在密集小节可能相碰 | 布局后全局碰撞检测 + QA 报告,测试断言 0 意外碰撞 | B |
| G17 | 模型能力 | `Event.lyric` 单槽;无副标题/词曲字段(`JianpuScore.text_blocks` 有 role 可用);多段歌词无数据源 | 明确数据契约:多段歌词/标题区字段从 text_blocks(role)或新可选字段流入 | A(前置) |

### 4.3 结论

当前引擎的**骨架**(列对齐、badness 断行、装页、确定性渲染)是对的;差距集中在 **L3 小节内间距的弹性模型**、**L4 记号占位与行高计算**、**L1 标题区完整度**,以及两项"商业软件都有而我们没有"的结构能力:**小节内断行(G4)** 与 **多段歌词/歌词引擎(G10)**。

---

## 5. 设计原则

1. **布局优先**:本轮只动布局/占位/骨架,不动识别、解析(除明确的数据契约对接)、播放、编辑器。
2. **契约稳定**:`render_service.py` 8 方法与 `main.py` 公开函数签名不变;新增参数一律带默认值;CSS 类名与 `data-*` 只增不减;render-map 结构向后兼容。
3. **确定性**:任何新布局量必须来自 `PublicationStyle`/字体度量,不得引入机器相关量;同输入字节级同输出。
4. **小步可验**:每个模块独立交付、独立金样;视觉变更必须经 `work/render-qa` 快照评审。
5. **数据契约先行**:多段歌词、标题区字段、楔形等,先定义"数据从哪来"(模型/text_blocks/可选参数),再写渲染。
6. **文档同步**:本文档取代旧渲染设计中的模块地图；实施后以本文档和当前 engraving 代码为准。

---

## 6. 详细方案(模块级)

> 落点文件默认在 `backend/score_trans/services/render/engraving/` 下,记为 `engraving/*`。
> 每个模块给出:目标 / 算法或布局规则 / 落点 / 依赖。

### M1 弹性间距模型(对应 G6)

- **目标**:小节内间距既保时值比例直觉,又杜绝溢出与整体左移。
- **算法(两遍布局)**:
  1. **理想位**:与现行一致,`x_ideal = inner_left + (start/duration) × (inner_right - inner_left)`。
  2. **碰撞消除**:从左到右,`x_i = max(x_ideal_i, x_{i-1} + right_extent_{i-1} - left_extent_i + min_gap)`(`min_gap` 默认 6,沿用)。
  3. **余量弹性分配**(新增):若末事件右边界 < inner_right,把剩余空间按**时值权重** `w_i = sqrt(duration_i)` 分配给各事件右侧间隙(平方根压缩动态范围,避免全音符吃掉全部余量);若 > inner_right(过满),按 `1/w_i` 反向压缩,但任何间隙不得小于 `min_gap × 0.5`;仍过满则触发 M4 的小节内断行。
- **落点**:`renderer.py::_event_positions`(重写为纯函数,便于单测)。
- **依赖**:无。

### M2 增时线与附点布局(对应 G7)

- **目标**:增时线按拍位分布并随行宽弹性伸展;附点位置规范。
- **规则**:
  1. 时长 D 拍(D>1)的事件,增时线数量 = ⌈D⌉−1,分布在事件右侧 `(0, D−1)` 拍对应的区间内,**等分且随弹性间距伸展**;线间距 clamp 到 `[16, 34]`px,线长 11px 不变。
  2. 附点(`dotted`):位于"最后一个节奏 token(数字或最末增时线)右侧 +9px、y−7";多附点以 7px 递增;不得与下一事件左缘相撞(撞线则随 M1 的 min_gap 一并推开)。
  3. 休止符长音同样按拍分布(`0 - - -`)。
- **落点**:`renderer.py::_draw_duration`、`_event_visual_extents`(right 计算改为由布局器传入的实际 dash 终点,而非固定 `28+18×n`)。
- **依赖**:M1(需要弹性后的实际间距)。

### M3 减时线分组(对应 G8)

- **目标**:符杠按拍分组,显式 beams 优先,休止/换气断开。
- **规则**:
  1. 显式 `event.beams`(begin/continue/end/hook)优先,维持现状。
  2. 无显式 beams 时,自动组 = 同一拍(`beat_duration = 4/beat_type` 拍)内、同 voice/staff、时间上相邻的短音符;**拍边界必断**;跨拍切分已由 tie 表达,不并组。
  3. 休止符与换气记号(breath-mark)打断自动组;组内不足 2 个事件时退化为单音符下线(现状行为)。
  4. 多层级(十六分)在拍内子组再细分。
- **落点**:`renderer.py::_draw_rhythm_lines`、`_rhythm_events_connect`(增加拍边界判定)。
- **依赖**:无。

### M4 断行引擎升级(对应 G3、G4、G5)

- **M4a 行策略**:`PublicationStyle.line_breaking: Literal["auto","fixed","phrase"] = "auto"`;`measures_per_line: int = 4`(fixed 时生效,允许 2–6)。
  - `auto`:现行 badness 断行(保留,调参:孤行罚分系数提成 style 常量)。
  - `fixed`:每行恰好 N 列(末行/强制断行除外),再按现行等比拉伸两端对齐;N 不可行(单列超宽)时自动降级 auto 并记 warning。
  - `phrase`:见 M12(P2 阶段)。
- **M4b 小节内断行**(新增结构能力):
  - 触发:某列固有宽度 > `content_width × 0.98`(或在 fixed 策略下 > 分配宽度)。
  - 断点:列内**拍边界**候选集(避开 tie/slur/连音符内部、避开减时线组中),用与 M1 相同的 badness 选最佳断点;断开处:行尾不画右侧小节线,行首不画左侧小节线,**增时线/减时线/连音线按既有 spanner 续接机制延伸**(复用 `_OpenSpanners` 跨系统续接代码路径)。
  - 实现:`_Cell` 从"整小节"泛化为"小节切片"(measure + start/end 拍区间);`_break_systems` 在切片层面工作。渲染侧 `_draw_measure` 接受切片(只画区间内事件,行尾/行首 suppress 小节线)。
  - 风控:该能力以 `allow_mid_measure_break: bool = True` 开关交付,默认开;出险可关。
- **M4c 行首小节线**:行首仅当该小节 `repeat_start` 时画反复开始线;普通起始线不再绘制(`_draw_measure` 的 `draw_start_bar` 语义修正)。
- **落点**:`renderer.py::_Cell/_System/_build_cells/_break_systems/_best_break/_draw_measure`;`style.py`。
- **依赖**:M1(切片内间距复用)。

### M5 内容驱动的行高与垂直节奏(对应 G9)

- **目标**:行高 = f(内容),行距均匀。
- **算法**:
  1. 对每行(逐声部)计算:
     - `top_extent` = max(音符顶/八度高点/记号栈高/连音符括号/圆滑线弧顶/volta 线/上方表情文本)。
     - `bottom_extent` = max(八度低点/减时线最深级/tie 弧底/力度/楔形/歌词段数 × 段高/未定位文本行数)。
  2. `system_height = top_extent + staff_core(≈69) + bottom_extent + padding(上 18 / 下 22)`。
  3. `system_gap = max(style.system_gap_min(44), style.system_gap(54))`;当下方含歌词时 +`lyric_gap`。
  4. 分页沿用装页算法,但 `used` 以真实 system_height 累计;页 1 标题区高度改由 M9 计算值。
- **落点**:`renderer.py::_system_extra_height`(重写为精确测量而非固定 24/28)、`_paginate`;新增 `engraving/metrics.py` 集中各类 extent 计算(从 `_event_visual_extents`/`_event_notation_top` 提炼)。
- **依赖**:M6/M7/M8 提供各自 extent。

### M6 歌词引擎(对应 G10、G17)

- **数据契约(先行)**:
  - 渲染输入侧:`Event` 增加 `lyrics: list[str | None]`(按段索引,空位 None),旧 `lyric` 字段保留并映射为 `lyrics[0]`(模型层加字段,带默认值,兼容现有构造点)。
  - 数据来源:(a) 简谱文本解析(domain 层)已有的单行歌词 → `lyrics[0]`;(b) 多段歌词经由 `JianpuScore.text_blocks`(role="lyric")或后续 domain 扩展流入——本阶段渲染层只对 `lyrics` 建模,domain 对接列为配套任务,**渲染层在数据缺失时退化为现状**。
- **布局规则**:
  1. 每段歌词一行:首段位于减时线/力度之下(`y+44` 起),段间距 `lyric_verse_gap=22`。
  2. 一字一音,居中于事件中心(现状);字宽计入 `_event_visual_extents`(取各段最宽者)。
  3. 段号:在行首列左侧(`x−14`,end 锚)绘 `1.` `2.`(仅多段时)。
  4. 连字符:同一事件歌词含 `-` 分节标记(或相邻事件同一词)时,在两事件中心之间绘居中连字符。
  5. 一字多音:某段一个字对应连续多个事件时,字下画延音横线(从字中心到末事件中心,y 与该段歌词基线 +6)。
- **落点**:`renderer.py::_draw_event`(歌词部分提炼为 `_draw_lyrics`)、`metrics.py`、`models/score.py::Event`(加字段)。
- **依赖**:M5(行高)、G17 数据契约。

### M7 力度与表情层(对应 G11)

- **规则**:
  1. 力度(`mp`/`f` 等):位于减时线之下、歌词之上(独立槽位 `y+dynamic_offset`,不再与歌词争 y+44/63 固定值;offset 由 M5 的行高栈计算)。
  2. **渐强/渐弱楔形**:消费 `Measure.text_blocks` 中 `direction_kind="wedge"` 的块(模型已带 `direction_attributes`,N5 已保往返),按 `spread` 属性(或默认 2 拍)换算跨度,绘两条收敛直线成 `<`/`>`,置于力度槽;跨系统按既有 spanner 续接思路截断。
  3. 表情/速度术语(text_blocks role="expression" 或 placement="above"):置于**谱上方**表达式槽(取代现行 `_draw_measure_text` 的"谱下居中"兜底);未定位且无 role 的文本保留兜底,但改到上方。
  4. 上方栈顺序(自下而上):记号(跳音/重音/保持音) → 装饰音 → 延长号 → 圆滑线弧 → 连音符括号 → 表情/速度文本 → volta 线;各槽位高度进 `top_extent`。
- **落点**:`renderer.py::_draw_marks/_draw_measure_text`,新增 `_draw_hairpins`;`metrics.py`。
- **依赖**:M5。

### M8 反复与跳跃(对应 G12)

- **volta(房子)**:
  1. 数据结构:利用 `Measure.ending_start/ending_stop/ending_discontinue`;渲染状态按系统维护(open volta),与 `_OpenSpanners` 同生命周期。
  2. 绘制:横线位于上方栈顶(volta 槽,y 由 M5 给),从 `ending_start` 小节左缘 +2 到 `ending_stop` 小节右缘 −2;左端竖线下挂 8px;数字 `1.`/`2.` 在左端内侧;`ending_discontinue` 或跨行/跨页时右端**不封口**(开端续接,行首从版心左缘起线)。
  3. 跨系统:行尾未闭合则画到版心右缘(开口),下行行首继续;语义闭合在 `ending_stop` 小节。
- **D.C./D.S./Fine**:作为上方表情槽文本,锚定在对应小节线右侧(来自 text_blocks,role="expression"/placement 上方)。
- **反复次数**:`repeat_count>1` 时在反复结束线上方小字标注(现有 `repeat-count` 类契约保留)。
- **落点**:`renderer.py` 新增 `_draw_voltas`(仿 `_OpenSpanners` 的 `_OpenVoltas`)、`_page_chrome` 不变。
- **依赖**:M5(volta 槽高度)。

### M9 标题区与页面骨架(对应 G1、G2、G17)

- **数据契约**:
  - `JianpuScore` 已有 `text_blocks`(role: title/instrument/lyric/expression/footer/other)。**约定映射**(渲染层实现 + 文档化):
    - 曲名 = `title` 参数 / `score.title`(现状);
    - 副标题 = 首个 role="other" 且位于页面上部的块(或后续 domain 显式字段);
    - 词/曲 = role="other" 中含 `词:`/`曲:` 前缀的块,或 role="lyric" 的署名块;
    - 速度 = `score.tempo` → `♩=N`;
    - 页脚 = role="footer"(底部居中,页码上方)。
  - 同时在 `RenderOptions` 增加可选 `subtitle/composer/lyricist`(str|None,默认 None),显式传入优先于 text_blocks 推断。
- **布局**(页 1,自上而下,高度动态累加):
  1. 曲名:居中 40px(现值,可配 42),`margin_top` 起。
  2. 副标题:居中 22px,+44。
  3. 词曲:右对齐 20px,一行(`词:X  曲:Y`)或两行,+32。
  4. 调拍号速度行:左 `1=C  4/4`(20px),右 `♩=120`;+36。
  5. `title_block_height = 实际累加 + 24`(替代固定 132)。
- **后续页**:左上小字曲名(现状,18px),右上页内序号可关;页眉高 54 不变。
- **页码**:`{i} / {N}` 底部居中(总页数在 `_paginate` 后已知,渲染时回填);保留单页也显示。
- **落点**:`renderer.py::_page_chrome/_paginate/render_scores`(先排页再渲染 chrome,或两遍:先算页数再画);`options.py`、`main.py::_style_from_options`。
- **依赖**:G17 契约、M5(分页用动态标题高)。

### M10 多声部外观(对应 G13)

- 花括号:以 3 次贝塞尔绘制左花括号 `{`(中点在系统纵中,上下钩),替代"直线+小钩";宽度 14px;`part_count>1` 时启用。
- 声部名:短名横排(现状,中文 ≤4 字时)置于括号左;长名 `rotate(-90)` 竖排居中于声部行高(恢复旧设计契约中的竖排能力)。
- `part_gap` 进入 M5 的行高计算(声部间留白随各自 bottom/top extent 微调)。
- **落点**:`renderer.py::_draw_system`;`metrics.py`。
- **依赖**:M5。

### M11 主题与配置(对应 G14)

- `PublicationStyle` 扩展字段(均带默认值,向后兼容):`lyric_verse_gap`、`dynamic_offset`、`expression_size`、`hairpin_gap`、`volta_height`、`page_number_format("plain"|"of_total")`、`line_breaking`、`measures_per_line`、`allow_mid_measure_break`、`brace_style("curly"|"straight")`、`system_gap_min`、`last_line_fill_threshold`(已有)等。
- 预设:`PublicationStyle.publication()`(现值即出版基准)/`PublicationStyle.compact()`(字号 −15%、间距 −20%,用于预览小图)。
- `RenderOptions` 增补:`measures_per_line`、`line_breaking`、`page_number_format`、`subtitle/composer/lyricist`、`compact: bool`;映射全部收敛于 `main.py::_style_from_options`(A4 之外尺寸按比例缩放逻辑保持不变)。
- **落点**:`style.py`、`options.py`、`main.py`。
- **依赖**:无(但服务化参数需 API 层另行决定是否暴露,本方案不动 API)。

### M12 乐句感知断行(P2,对应 G3/§2.2)

- 候选断点:列边界(默认)+ 强制断行标记。
- 乐句信号打分(每列边界):歌词标点(。,;、!?)> 长音(≥2 拍)≈ 休止(≥1 拍)> 延长号/终止线 > 反复小节线;tie/slur 内部为负分(不可断)。
- 在 `phrase` 策略下:以 M4 的 badness 为主项,叠加"断点非乐句边界"罚分,动态规划选全局最优(复杂度 O(n²),n=列数,可接受)。
- **落点**:`renderer.py::_best_break` 扩展 + 新增 `_phrase_score`。
- **依赖**:M4a、M6(歌词数据)。

### M13 全局碰撞检测与 QA 报告(对应 G16)

- 布局完成后,对 `PublicationScene` 全节点计算近似 BBox(text 节点用字体度量,line/path 用几何),扫描线算法 O(n log n) 找重叠对。
- 白名单:同组内设计性重叠(文字与背景、tie 与数字基线等,按 class 对配置)。
- 输出:`work/render-qa/<case>.report.json`(碰撞清单、行填充率、溢出清单);测试断言"金样语料 0 非白名单碰撞"。
- **落点**:新增 `engraving/qa.py`;测试接入 `tests/test_render.py`。
- **依赖**:各模块稳定后启用(P4)。

### M14 render-map 派生锚点(C,对应 G15)

- 决策建议:采用"音符定位 + 可选全元素定位"双档;实现上为减时线/连音线/volta/连音符括号注册 `data-source-role` 与 BBox 进 `source_boxes`(代码中这些节点大多已带 `_semantic_attrs`,只缺 `register_sources` 调用)。
- 与前端交互契约一起验收(点击高亮目标是否包含派生记号)。
- **落点**:`renderer.py`(各 `_draw_*` 增加 register 调用)、`scene.py`(payload 增加 role 字段,向后兼容)。

---

## 7. 测试与视觉 QA 策略

### 7.1 既有契约

- `tests/test_render.py`(26 项)与 `tests/test_architecture.py` 必须持续通过;仅当视觉变更为**有意变更**时更新断言,并在提交说明中逐条列出。
- 后端全量(当前 430 passed)+ `ruff check`/`ruff format --check` 保持绿。

### 7.2 金样快照(新增,核心手段)

- 语料(corpus):
  1. `examples/simple_jianpu.txt`(现有);
  2. 合成谱(每特性一个):多段歌词、连音+跳房子、全音符/二分长音、切分 tie、十六分减时线组、三连音、多力度+楔形、转调变拍、多声部、超宽小节(触发小节内断行)、多页长曲;
  3. 真实样例:`examples/二胡`、`examples/古筝`、`examples/中阮`、`examples/长笛` 中各取 1 首(经现有链路转 JianpuScore)。
- 流程:渲染 → SVG 规范化(属性排序/数值精度统一)→ 与 `tests/fixtures/render_golden/` 金样 diff;有意变更时 `UPDATE_GOLDEN=1` 重新生成并在 PR 中贴前后对比图(PNG 化经浏览器截图脚本,放 `work/render-qa/`,该目录已存在)。
- 确定性:同输入渲染两次字节一致(已有字体哈希保障,加测试锁死)。

### 7.3 布局不变量(属性测试)

- 页面内所有节点 BBox 不越过版心(左右边距)与页底/页顶禁区;volta/楔形等开口元素除外(白名单)。
- 同一行内任意两事件 BBox 水平不重叠(允许多少?0)。
- 多声部同列小节线 x 坐标完全一致。
- 歌词文本中心与所属事件中心偏差 ≤ 字宽/2 + 1。
- `fixed` 策略:非末行、非强制断行的行列数 == N;非末行行填充率 ≥ 92%(强制断行除外)。
- 小节内断行:被断小节的两片渲染后无内容丢失(事件数守恒)且无 clipping。
- 分页:任何 system 不跨页;页内容底 ≤ `content_bottom`。

### 7.4 评审工作流

- 每阶段交付前在 `work/render-qa/` 生成:语料全量 SVG + PNG + QA 报告(M13);对照 JP-Word/番茄简谱同曲样张做人工 checklist(附录 B)。

---

## 8. 阶段计划

> 每阶段:可独立交付、独立金样;顺序即依赖序。工作量按单人全情投入估算。

### 阶段 P0 — QA 基线与脚手架(0.5–1 天)

- 内容:金样快照机制 + 规范化 diff + `work/render-qa` 输出;语料 v1(simple_jianpu + 4 个合成谱);布局不变量测试框架(先上"页内不越界/同行不重叠"两条);文档头标注状态。
- 验收:基线快照入库;两条不变量在基线上通过;430 测试全绿。

### 阶段 P1 — 布局内核(3–4 天)

- 内容:M1 弹性间距、M2 增时线/附点、M3 减时线拍分组、M4 断行升级(行策略 + 行首小节线修正 + 小节内断行)、M5 行高引擎(先按现有内容类型:记号栈/八度点/减时线/歌词单行/力度)。
- 配套:`metrics.py` 抽取;`_event_positions` 纯函数化。
- 验收:语料 v2(长音/切分/十六分/超宽小节/多页)快照评审通过;`fixed=4` 策略不变量通过;小节内断行开关回归通过;既有 26 项渲染测试按变更清单更新后通过。

### 阶段 P2 — 歌词与表情(2–3 天)

- 内容:G17 数据契约(Event.lyrics + text_blocks 映射约定)、M6 歌词引擎、M7 力度/表情/楔形、M8 volta 与 D.C./Fine。
- 配套:domain 解析侧对接任务单独立项(渲染层以合成数据 + text_blocks 注入测试)。
- 验收:多段歌词/连字符/转音线快照;楔形跨音符快照;volta 跨小节与跨行续接快照;不变量全过。

### 阶段 P3 — 页面骨架与主题(1.5–2 天)

- 内容:M9 标题区(副标题/词曲/速度行/页脚/页码 `i / N`/动态标题高)、M10 花括号与声部名、M11 主题预设与 RenderOptions 扩展。
- 验收:带全字段标题区快照;后续页眉快照;compact 预设快照;公开 API 签名兼容检查(架构测试)。

### 阶段 P4 — 智能与打磨(2–3 天,可视验收情况裁剪)

- 内容:M12 乐句断行、M13 碰撞检测并入测试门禁、M14 render-map 决策落地、与商业样张对照的 polish 清单(附录 B)。
- 验收:乐句断行金样;语料 0 非白名单碰撞;附录 B checklist 全勾;文档收尾(architecture.md/file-by-file.md/issues.md 同步)。

**总工作量估算**:9–13 天(不含 domain 解析侧多段歌词对接,该任务视文本语法决策另计)。

---

## 9. 风险矩阵

| 风险 | 等级 | 影响 | 缓解 |
|---|---|---|---|
| SVG 字符串断言脆弱,视觉变更引发大面积测试红 | 高 | 进度 | P0 先建金样机制;变更清单制;断言从"精确字符串"逐步迁到"结构/不变量" |
| 小节内断行复杂度高(切片 + 续接 + 间距重算) | 中高 | P1 延期 | 开关交付(`allow_mid_measure_break`);先做拍位断点 + 复用 spanner 续接;最坏情况降级为"超宽小节压缩 + 警告" |
| 多段歌词无数据源,渲染层空转 | 中 | M6 空转 | 数据契约先行;text_blocks 注入路径;domain 对接独立排期,不阻塞渲染层交付 |
| 标题区 role 启发式误判(OCR 文本杂乱) | 中 | 误排版 | 显式参数优先;启发式仅取高置信前缀(词:/曲:);误判可关(`title_block="simple"`) |
| 字体字形覆盖(新增楔形/花括号路径) | 低 | 视觉 | 楔形/花括号用几何 path 不依赖字体;新增文本字符需过 `_glyph` 覆盖测试 |
| 性能(金样语料 + 碰撞检测拉长测试时长) | 低 | CI 时长 | 碰撞检测扫描线 O(n log n);金样集控制在 ~20 例;字体度量 lru_cache 已有 |
| 范围蠕变(顺手改编辑器/API) | 中 | 失控 | 本方案边界见 §5;任何 API 暴露另立任务 |
| 旧渲染设计与本方案并存造成混淆 | 低 | 文档 | 旧设计已归档，布局工作以本方案为准 |

---

## 10. 验收标准

**功能验收(可测)**:

1. 语料库(≥15 例)渲染:0 越界、0 非白名单碰撞、字节级确定性。
2. `fixed=4` 策略:非末行行均为 4 小节且填充率 ≥92%;`auto` 策略无孤行(末行 1 小节)除非强制。
3. 超宽小节(>版心 1.2×)在拍位断开,两片事件守恒,连音线/增时线续接正确。
4. 多段歌词(3 段)垂直堆叠段间距一致,段号、连字符、转音横线符合 §3.4。
5. volta 跨 3 小节 + 跨行开口续接;D.C./Fine 位于谱上方。
6. 楔形渐强跨 ≥3 事件,位于力度槽。
7. 标题区:含副标题/词曲/速度的全字段页面无重叠,高度动态;页码 `i / N`。
8. 既有 26 项渲染测试 + 后端全量 + ruff 全绿;API 签名 diff 为空(架构测试)。

**视觉验收(人工,附录 B checklist)**:对照 JP-Word/番茄简谱样张,标题区、行距节奏、歌词层次、记号避让四大项全勾。

---

## 11. 附录

### 附录 A:参考项目与资料

| 项目/资料 | 用途 | 链接 |
|---|---|---|
| jodi-ivan/numbered-notation-xml | 布局引擎源码(token 顺序布局、小节内断行、歌词引擎、快照测试) | <https://github.com/jodi-ivan/numbered-notation-xml> |
| lodebar2026/jpeditor | 乐句断行、JP-Word 排版惯例、度量一致性 | <https://github.com/lodebar2026/jpeditor> |
| flufy3d/JianpuRender | 数据模型与渲染管线、基准尺寸参数化 | <https://github.com/flufy3d/jianpurender> |
| speedyOrc-C/Your-Jianpu · Linho1219/Your-Jianpu-ts | 印刷质量目标、字体测量 | <https://github.com/speedyOrc-C/Your-Jianpu> · <https://github.com/Linho1219/Your-Jianpu-ts> |
| felixhao28/react-jianpu | 固定每行小节数 + 对齐、歌词 hyphen | <https://github.com/felixhao28/react-jianpu> |
| Linho1219/OpenFanqieCore | 番茄简谱格式 | <https://github.com/Linho1219/OpenFanqieCore> |
| 仓库文档 | `docs/jianpu-render-compatibility-audit.md`、`docs/jianpu-syntax.md` | 本地 |

### 附录 B:视觉评审 checklist(对照商业样张)

- [ ] 标题区:曲名层级、词曲右对齐、调拍号行位置、页码格式
- [ ] 行:每行小节数观感、两端对齐、末行自然、行距节奏
- [ ] 小节内:长音增时线按拍分布、附点位置、切分 tie、符杠拍分组、连音符括号
- [ ] 歌词:一字一音居中、多段堆叠、段号、连字符、转音横线
- [ ] 记号:力度/表情槽位、楔形、延长/跳音栈、volta 房子、D.C./Fine
- [ ] 多声部:花括号、声部名、小节线对齐
- [ ] 整体:无拥挤/无松散/无重叠,灰度均匀

### 附录 C:当前 PublicationStyle 常量与目标对照(基准值,P3 定稿)

| 常量 | 现值 | 目标 | 说明 |
|---|---|---|---|
| margin_left/right | 82 | 85 | 接近 22.5mm@150DPI |
| margin_top | 72 | 96 | 标题区上方留白(页 1);后续页 54 页眉不变 |
| margin_bottom | 64 | 72 | |
| title_size | 40 | 42 | 曲名 |
| note_size | 30 | 28–30 | 依语料评审定稿 |
| lyric_size | 18 | 18 | 不变 |
| measure_number_size | 15 | 16 | |
| base_staff_height | 92 | 由 M5 计算 | 核心行高不变,上下 extent 动态 |
| system_gap | 54 | min 44,默认 54 | 含歌词时 +lyric_gap |
| title_block_height | 132(固定) | 动态(≈154 全字段) | M9 |
| ideal_event_gap / minimum_event_gap | 42 / 28 | 由 M1 权重模型取代 | |
| last_line_fill_threshold | 0.72 | 0.72(可配) | |
| lyric_verse_gap | — | 22 | M6 新增 |
| volta 槽高 | — | 26 | M8 新增 |

### 附录 D:与旧设计文档的关系

旧的渲染重写设计基于已经删除的 `drawing/` 架构，现已由 `engraving/` 净室实现和本文档取代；当前布局工作以本文档为唯一权威方案。
