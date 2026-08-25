# MusicXML → 简谱转换完整修复方案（v3，含两轮自审修订）

制定日期：2026-08-25（v2 自审修订 + v3 复审补漏于同日）
依据：`jianpu-conversion-audit-2026-08-25.md` + `jianpu-conversion-audit-verification-2026-08-25.md` 中 page_001-004 逐行人工审查结果 + 合成 MusicXML 全语法测试 + 两轮自审验证。

**版本修订记录**：
- v2：删除 1 项误报（6/8 拍号不一致）、缩小 2 项修法（还原号/三连音）、降级 2 项为远期（编号 slur/@voice 语法）、新增 Phase 0、补充锚点兼容/测试影响。
- **v3：补回 1 项 P0 遗漏（行首附点音符被吞——原审计头号问题之一，v1/v2 均漏）、补 1 项 P1（休止歌词错位）、修正 multiple-rest 机制（忽略而非展开）、补回跨小节长休止拆分、补 2 项 P2 健壮性（空音符 `?`/非标力度）、新增「显式范围外」声明。**

## 问题总览（v3）

| 级别 | 问题 | 影响范围 | 根因位置 | 工作量 | 风险 |
|---|---|---|---|---|---|
| P0 | 还原号 `n` 重导出音高错误 | 158 个音符 | `write/musicxml.py` 未用 `accidental_text` | S | 低 |
| **P0** | **行首附点音符被吞（v3 补）** | **本批 6 个音符，所有含附点起拍的谱** | **`_strip_leading_measure_label()` 行级规则过激** | **S** | **中（AI 标签兼容）** |
| P0 | 三连音结构丢失（`$3:2;` 消失） | page_001 L14 | 待诊断（parse 丢 time-modification 或 collect 漏收） | M | 中 |
| P1 | slur 漏 `)` / 漏 `(` | 4 处 | 待验证（疑 chord 成员 slur 丢失） | M | 低 |
| P1 | slur 嵌套（并行 slur 同用 `()`） | 3+ 处 | 语法表达力限制 | S(序列化) | 低 |
| P1 | 跨连音组 slur 致连音内不配对 | 2 处 | writer tuplet+slur 交互 | S | 低 |
| P1 | measure-level 调号变化未跟随（产品决策） | 2 处 | `_measure_lead_info` | S | 中 |
| P1 | 空小节处理不一致（取决于 print-object） | 全部页 | writer rest 逻辑 | M | 低 |
| P1 | 跨小节长休止不拆分（v3 补回） | page_001 L8 等 | writer 无结转逻辑 | S | 低 |
| **P1** | **休止符歌词错位（v3 补）** | **带歌词谱面的 L: 流** | **writer 收休止歌词 vs parser 只派给音符** | **S** | **低** |
| P1 | 多声部交错混入 | 全部页 | writer 线性遍历 events | M(B') | 中 |
| P1 | 小节合并（m9+m10 并一行） | page_001 L11 | backup 跨 measure 边界 | M | 中 |
| P1 | 空小节被解析器跳过丢位置（锚点兼容） | 28 个小节 | `flush_measure()` | S | 中 |
| P2 | 过满小节 / 补拍凑数 | 多处 | Audiveris 输入 | S | 低 |
| P2 | 畸形多附点 | 多处 | `_MAX_GENERATED_DOTS` | S | 低 |
| P2 | 32nd 前缀 `d`+降号 `b` 粘连 | page_001 | 前缀设计 | M | 中（兼容性） |
| P2 | staccatissimo 等未知奏法丢弃 | 12 次 | `PERFORMANCE_MARKS` | S | 低 |
| **P2** | **空音符产出非法 `?`（v3 补）** | **畸形输入防线** | **writer `else "?"` 兜底** | **S** | **低** |
| **P2** | **非标力度产出非法 `\x`（v3 补）** | **畸形输入防线** | **writer 原样输出 dynamic** | **S** | **低** |

~~6/8 拍号变化不一致~~（v2 删除：误报。m11 与 m21 都是 6/8 且中间无变化，不输出是「无变化不输出」的正确行为。）

---

## Phase 0：输入预处理（先于一切修复）

**动机**：Audiveris 脏输入是多个下游症状的放大器。在 `parse/musicxml.py` 读入后加 sanitize 层，不动语法层即可缓解三类问题：

1. **去重复音符**：同一 `id` 的 note 出现两次（page_001 2nd-m8 的 D4-A4 重复 + `<backup>` 回退）→ 保留一份。直接消除该处 5 个 `(` 悬空。
2. **截断过满小节**：advance 总时值超拍号上限（9.25/4 拍）→ 截断到上限 + warning。缓解小节合并与补拍。
3. **过滤冗余 attributes**：与当前状态相同的 `<key>`/`<time>` 重复 → 忽略。
4. **忽略 `<multiple-rest>` 元素**（v3 修正：它是纯渲染指令，**不该展开**——page_003 m31 的 multiple-rest 6 对应的 m32-36 已是显式空小节，展开会重复；page_004 m5 的「音符+multiple-rest 同小节」同理只取音符）。空小节语义由各 measure 自身的 rest 决定。

涉及文件：`backend/score_trans/domain/parse/musicxml.py`
工作量：M ｜ 风险：低

---

## P0 级修复

### 修复 1：还原号 `n` 重导出音高错误（v2 缩小修法，维持）

**问题**：`_parse_pitch()` 把 `n` 存成 `accidental=0` + `accidental_text="♮"`——信息没丢，丢的是 `write/musicxml.py` 重导出时没用它，音高按调号默认走（Bb 调 `n1` 变回 Bb）。158 个音符。

**修复**：只改 `write/musicxml.py`——pitch 的 `accidental_text` 为还原（`"n"`/`"♮"`）时，导出强制写 `<accidental>natural</accidental>` 且 `<alter>` 取该 step 调号默认音的还原值。不动数据模型、不动解析器、不动简谱文本。

涉及文件：`backend/score_trans/domain/write/musicxml.py`
工作量：S ｜ 风险：低
附注：文本层 `n`→`♮` 的单向漂移（`n7` 归一化后变 `♮7`）是化妆性差异，可顺手在 writer 归一为始终输出 `n`（一行改动，可选）。

**验证**：page_002 `n7` 重导出 → `<step>F</step><alter>0</alter><accidental>natural</accidental>`；page_003 `n1'` → `<step>B</step><alter>0</alter>`。

### 修复 2：行首附点音符被小节编号标签吞掉（v3 补回，P0）

**问题**：`_strip_leading_measure_label()`（`parse/jianpu_text.py:1007-1017`）把行首 `[0-7].`（无前缀附点音符）误判为小节编号剥掉。实测复现：`1. q2 3 4` 解析得 3 事件（`1.` 消失）、`0. 2 3 4`、`2.`/`3.`/`7.` 同样被吞，**静默丢音不报错**。真实数据命中：微信图1 物理行 4/7/12/13/15、page_005 行 17（共 6 个音符）。**我们自己 writer 就会产出这种形态**（微信图1 L4 `2. (s5 s4) h0`），即「writer 产出 → parser 吞掉」的自产自销 bug，违反往返性。

**修复（行级规则向 token 级对齐）**：token 级判定 `_is_measure_label_token()`（1020-1024 行）已正确倾向音乐解读（`N>7` 且分隔为 `.` 才算标签）。行级 stripper 改为同规则：
1. 分隔符为 `:`/`：` → 一律按标签剥（AI 标签风格，`272:` 测试用例不受影响）。
2. 分隔符为 `.` 且 `N > 7` → 按标签剥。
3. 分隔符为 `.` 且 `0 ≤ N ≤ 7` → **不剥**，按附点音符处理（删掉现行「仅当后跟小节线才保留」的过激 guard）。

**兼容注意**：若 AI 转录输出恰好用 `1.` `2.` … `7.`（≤7 的点号）当小节编号，修复后会被当音符。需同步：AI prompt 指示编号用 `:` 风格或 3 位数（现有测试 `test_ai_output_measure_labels_are_ignored` 用的是 `272:`，兼容）。

涉及文件：
- `backend/score_trans/domain/parse/jianpu_text.py` — `_strip_leading_measure_label()` 1007-1017 行
- AI 转录 prompt（若 AI 会发点号编号）

工作量：S ｜ 风险：中（AI 输出习惯需同步）

**验证**：`1. q2 3 4` 解析得 4 事件；微信图1 6 行全部往返不丢音；`272: ...` 仍被剥。

### 修复 3：三连音结构丢失（先诊断再修，维持 v2）

**问题**：page_001 第二轮 m1 的 3:2 三连音输出成 `s4. sb4. s2.`，无 `$3:2;`。输出值是「1/3 拍的吸附值」→ 时值走了 `safe_duration_affixes` 但 tuplet 上下文丢失。

**诊断步骤（最小复现）**：
1. 构造仅含该三连音的最小 XML（F 谱号 + 3:2 tuplet 三个 eighth），跑 `musicxml_path_to_scores()`，检查事件是否带 tuplet 信息。
2. parse 侧丢 → 修 `parse/musicxml.py`（嫌疑：谱号切换小节 attributes 分支跳过 time-modification）。
3. parse 侧保留 → 修 `write/jianpu_text.py` `_collect_tuplet_events`（嫌疑：voice/backup 交错拆散 tuplet 成员）。

**v3 补充**：诊断时同时核查另一个已复现症状——合成测试里「3 个 plain quarter 的 3:2 连音成员被加附点（`$3:2;1. 2. 3.$`）」，即**即使 tuplet 被检测到，成员时值也可能被 `safe_duration_affixes` 错误吸附**。修复必须确认成员时值按 tuplet 缩放（1/3 拍）而非吸附（0.375 拍），否则修完检测仍有附点残留。

**顺带诊断项（page_002 m21）**：6/8 拍下 A#4 quarter(duration=24) 输出 `q#2`(eighth)。确认 writer 的时值前缀是否按 quarter 基准换算（应无前缀）——若 6/8 下有隐藏的拍单位换算逻辑，与三连音时值同源，一并诊断。

涉及文件：
- `backend/score_trans/domain/parse/musicxml.py` / `write/jianpu_text.py`（按诊断结果）
- `backend/score_trans/domain/jianpu_tokens.py`（若涉及 tuplet 缩放）

工作量：M ｜ 风险：中
**验证**：最小复现输出 `$3:2;1 2 3$`（无附点）；page_001 L14 出现连音标记；回解析 tuplet 保留。

---

## P1 级修复

### 修复 4：slur 漏 `)` / 漏 `(`（假设待验证，维持 v2）

**问题**：page_001 L7/L8/L9 缺 `)`、page_004 L4 缺 `(`——4 处均在 chord 边界。

**修复**：先验证假设（构造「slur 标在 `<chord/>` 成员上」的最小 XML，查 event 的 slur 标记归位）：
- 假设成立 → 修 `parse/musicxml.py`：chord 合并时收集**所有成员**的 slur。
- 不成立 → 缺口在 measure 归一化，修对应环节。

writer 加兜底：输出全文后 `(` 与 `)` 计数不等则 warning。

涉及文件：`parse/musicxml.py`（待验证）、`write/jianpu_text.py`（兜底）
工作量：M ｜ 风险：低

### 修复 5：slur 嵌套（方案 A 维持远期，近期序列化）

**问题**：XML 用 `slur number` 区分并行 slur，简谱只有 `()`（语法文档 213 行明文禁止嵌套）。

**近期（B，序列化）**：writer 同刻只保留最早开始的 slur 的 `()`，其余丢弃 + warning。**远期（A，编号 slur 语法）**：波及编辑器/渲染/前端/AI/锚点全链路，单独立项。

涉及文件：`write/jianpu_text.py` 617-625 行
工作量：S ｜ 风险：低

### 修复 6：跨连音组 slur 致连音内不配对（维持 v2）

**修复**：`_tuplet_to_token` 输出后校验 tuplet body 局部括号配对，悬空的 `(` `)` 移到 `$...$` 外。

涉及文件：`write/jianpu_text.py` `_tuplet_to_token` 648-688 行
工作量：S ｜ 风险：低

### 修复 7：measure-level 调号变化（产品决策，维持 v2）

**问题**：page_002 m5 / page_003 m19 的 `<fifths>0` 未跟随。但无法确认是真实转调还是 Audiveris 误识别。

**建议**：先 B（维持现状 + 转换日志 warning「检测到中途调号变化，已忽略」），积累数据后评估切 A（`_measure_lead_info` 输出 `1={新调}`）。

涉及文件：`parse/musicxml.py`（warning 必做）；`write/jianpu_text.py`（如选 A）
工作量：S ｜ 风险：中（A 可能引入 OMR 噪声）

### 修复 8：空小节 / measure rest / 长休止统一（v3 修正规则）

**问题**：小节休止处理取决于 print-object 与内容形态，四种路径不一致。

**修复（v3 修正为四条规则）**：
1. **隐藏的 measure rest（`print-object=no`）→ 空 `|` 行**（维持现状）。
2. **显示的 measure rest（无 print-object 或 =yes）→ `w0`**，bypass `safe_duration_affixes`（消灭 `s0----`、`h0 h0`）。
3. **`<multiple-rest>` 元素 → 忽略**（v3 修正：不展开。见 Phase 0 第 4 条——空小节语义由各 measure 自身 rest 决定，展开会与显式空小节重复）。
4. **超出小节容量的长休止（普通 rest，如 page_001 的 12 拍 voice2 休止）→ 本小节输出 `w0`，余量结转后续小节**（若后续小节为空则继续 `w0`，非空则截断 + warning）（v3 补回，v1 有 v2 合并时丢失）。

空元素 `<measure/>` → `w0`（维持现状）。

涉及文件：
- `parse/musicxml.py` — multiple-rest 忽略（并入 Phase 0）
- `write/jianpu_text.py` — rest 输出 176-178、603-604 行（规则 2/4）

工作量：M ｜ 风险：低

### 修复 9：休止符歌词错位（v3 新增）

**问题**：writer 收集歌词时不区分事件类型（`write/jianpu_text.py` 204-205 行无 kind 过滤），休止符的歌词进入 `L:` 流；但 parser 分派 `L:` 歌词时只给音符（`parse/jianpu_text.py` 1491-1492 行跳过休止）→ **休止上的歌词回解析后右移到下一个音符**。

**修复（取 writer 侧对齐 parser 语义）**：writer 收集 `L:` 歌词时只取 `kind == "note"` 事件的歌词，休止歌词丢弃 + warning（或按产品需要未来支持休止歌词语法）。

涉及文件：`write/jianpu_text.py` — 歌词收集 204-205 行
工作量：S ｜ 风险：低
**验证**：合成用例「音符歌词 + 休止歌词」往返后，音符歌词位置不变。

### 修复 10：多声部交错混入（v2 推荐方案 B'，维持）

**问题**：writer 按 cursor/backup 交错序线性遍历 `measure.events`，多声部串成一条线。

**方案**：
- **B'（近期推荐）**：measure 内按 voice 排序（voice1 全部在前、voice2 在后，组内保持时序），消除交错。只加一次 `events.sort(key=voice)`。
- **B（备选）**：只输出 voice1，其余丢弃 + warning。
- **A（远期）**：`// @voice` 语法，单独立项。

**产品决策点**（见文末决策表）。

涉及文件：`write/jianpu_text.py` `_score_to_jianpu_text` 136-216 行
工作量：S(B')/M(B) ｜ 风险：中（B' 小节过满的渲染表现需验证）

### 修复 11：小节合并（v2 策略维持：先复测再修）

**问题**：page_001 m9/m10 间 `<backup>` 使两小节内容并到 L11 一行，后续编号错位。

**策略**：Phase 0（截断过满）+ 修复 10（voice 排序）实施后复测——触发条件（过满+交错）被大幅削弱，可能自然消失。仍复现再修 `_read_measure_structure`（backup 只应在 measure 内移动 cursor）。

涉及文件：`parse/musicxml.py` `_read_measure_structure` 约 380-419 行
工作量：M ｜ 风险：中

### 修复 12：空小节被解析器跳过丢位置（v2 机制维持，已验证可行）

**问题**：`flush_measure()` 遇无 event 的空 `|` 行不创建 `Measure`，丢 28 个小节位置。

**修复（机制已验证）**：为空小节创建**含一个 hidden 全休止事件的 `Measure`**（`Event.hidden` 字段存在于 `models/score.py:114`；writer 会跳过 hidden rest → 仍输出空 `|` 行 → **往返完美**）。

**锚点兼容风险（必须知悉）**：空小节进入模型后 `measure_index` 前移，**已生成的历史叠加层/render-map 会整体错位**——需接受旧数据作废重生成，或管线里重跑。

涉及文件：`parse/jianpu_text.py` `flush_measure()` 605-608 行
工作量：S ｜ 风险：中（历史锚点）

---

## P2 级修复

### 修复 13：过满小节 / 补拍（维持）
主要靠 Phase 0 截断；补拍保留但记 warning。工作量 S ｜ 风险低。

### 修复 14：畸形多附点（维持）
`_MAX_GENERATED_DOTS` 3→2，超限改「基础时值+延音」。注意同步更新断言 3 附点的现有测试。工作量 S ｜ 风险低。

### 修复 15：32nd 前缀 `d`+降号 `b` 粘连（维持：建议只改文档）
改前缀是破坏性语法变更（已存文本/AI 输出/文档全受影响）。除非用户实际抱怨，**只改 `jianpu-syntax.md` 注明 `db7'` 读作 d+b7'**。工作量 M（若改）/ S（文档）｜ 风险中高。

### 修复 16：staccatissimo 等未知奏法（维持）
`PERFORMANCE_MARKS` 补 `staccatissimo`(`^!`)、`turn`(`^t`)、`inverted-turn`(`^t'`)，parser mark 表同步。工作量 S ｜ 风险低。

### 修复 17：畸形输入健壮性兜底（v3 新增）

**问题**（合成测试已复现，真实数据 0 触发，属防线缺失）：
- 空音符（`<note>` 无 `<pitch>` 无 `<rest>`）→ writer 产出非法 `?` token（`write/jianpu_text.py` 614-616、710-712 行 `else "?"`）。
- 非标力度（`<other-dynamics>molto</other-dynamics>`）→ writer 原样输出 `\molto`（187-188 行），parser 拒绝。

**修复**：
1. `pitches` 为空的 note 事件 → writer 输出为休止（按事件时值）+ warning，禁止 `?`。
2. `event.dynamic` 不在 `DYNAMICS` 集合 → writer 丢弃该力度 + warning，禁止非法 `\x`。

涉及文件：`write/jianpu_text.py` 614-616、710-712、187-188 行
工作量：S ｜ 风险：低
**验证**：合成畸形 XML 转换后回解析无 `JianpuSyntaxError`。

---

## 显式范围外（v3 新增声明）

以下问题在审计中已确认存在，但**本方案不修复**（原因是简谱编辑器当前无对应语法，修复=语法/产品扩展，与远期项同类）：

| 遗留信息丢失项 | 审计定位 | 处置 |
|---|---|---|
| 方向文字全丢（words/wedge/pedal/metronome/rehearsal/octave-shift/segno/coda 等） | 原审计 P1-D6 | 远期：需先设计简谱表情语法 |
| 多段歌词只留第 1 段 | 原审计 P2-D4 | 远期：L: 语法扩展（如 `L1:`/`L2:`） |
| volta 跳房结构丢失 | 原审计 P2-D2 | 远期 |
| bar-style（终止线等）丢失 | 原审计 P3-D1 | 远期 |
| 歌词音节类型/延长线（syllabic/extend）丢失 | 原审计 P3-D5 | 远期 |
| tie 不合并为延音记号（`1~ ~1` vs `1-`） | 首份报告 P3 | 有意设计（保留分音符时值），不改 |
| parser tie 自动补全差异（stop 计数 16 vs 17 等） | 原审计 #4 | 已知行为（上下文补全），不改 |
| 历史 233 个不可解析 `_jianpu.txt`（旧代码产物） | 回归分析 | 运维项：清理或重跑，非代码修复 |

---

## 实施顺序（v3）

```
Phase 0   输入预处理（去重/截断/滤冗余/忽略 multiple-rest）
P0-1      修复 1  还原号（write/musicxml.py 单点）
P0-2      修复 2  行首附点吞音（strip 规则对齐 + AI prompt 同步）
P0-3      修复 3  三连音（最小复现诊断，含成员附点 + 6/8 时值两个子项）
P1-a      修复 4  slur 漏括号（先验证 chord 假设）+ writer 兜底计数
P1-b      修复 5  slur 序列化 + 修复 6 跨连音组 slur
P1-c      修复 8  空小节/measure rest/长休止统一（含结转）
P1-d      修复 9  歌词错位（writer 过滤休止歌词）
P1-e      修复 10 voice 排序 B'（产品决策）→ 复测修复 11 是否仍复现
P1-f      修复 12 空小节保留（hidden w0；历史锚点作废决策）
P1-g      修复 7  中途调号（先 B：只加 warning）
P2        修复 13-17（含 v3 新增健壮性兜底）
远期      编号 slur 语法、@voice 语法、前缀变更、方向文字/多段歌词等语法扩展
```

## 验证方法（v3）

每批修复后：
1. page_001-004 重跑 `musicxml_to_jianpu()`，逐行对比。
2. `parse_jianpu_scores()` 回解析无 `JianpuSyntaxError`。
3. `normalize_jianpu_text()` 幂等。
4. 括号配对：全文 `(` == `)`。
5. 小节数：重解析小节数 == 原始小节行数（修复 12 后）。
6. 还原号：`n` 音重导出 `<alter>` 不跟随调号（修复 1 后）。
7. **附点起拍**：`1. q2 3 4` 得 4 事件；微信图1 6 行往返不丢音（修复 2 后）。
8. **畸形输入**：空音符/非标力度的 XML 转换后可回解析（修复 17 后）。
9. **全量 pytest**：`python -m pytest tests/test_jianpu.py tests/test_convert.py`——修复 2/3/8/12/14 大概率打破现有断言，**测试更新是每批必要交付物**。
10. **溯源回归**（修复 12 后必做）：跑完整识别管线，score-link-map 的 `measure_index` 与 render-map 对齐，叠加层点击定位正确。

## 不修改的文件

仅 `domain/` 层：`parse/jianpu_text.py`、`parse/musicxml.py`、`write/jianpu_text.py`、`write/musicxml.py`、`jianpu_tokens.py`、`performance_marks.py`。不涉及 `api/`、`exec/`、`services/`。例外：远期语法项（4A/10A/15）将波及 `desktop/` 前端与 `services/render/`——这正是其被列为远期的原因。

## 遗留决策点（需拍板）

| # | 决策 | 选项 | 推荐 |
|---|---|---|---|
| 1 | 多声部（修复 10） | B' 排序保留 / B 只留 voice1 / A 语法（远期） | 先 B' |
| 2 | 中途调号（修复 7） | B 忽略+warning / A 跟随 | 先 B |
| 3 | 32nd 前缀（修复 15） | 改语法（破坏性）/ 只改文档 | 只改文档 |
| 4 | 历史锚点（修复 12） | 旧叠加层作废重生成 / 加兼容映射 | 作废重生成 |
| 5 | AI 小节编号风格（修复 2 连带） | 点号 `1.`（修复后会被当音符）/ 冒号 `1:` | 冒号 |
