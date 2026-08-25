# MusicXML → 简谱转换完整修复方案（v2，含自审修订）

制定日期：2026-08-25（v2 修订于同日，基于自审）
依据：`jianpu-conversion-audit-2026-08-25.md` + `jianpu-conversion-audit-verification-2026-08-25.md` 中 page_001-004 逐行人工审查结果 + 自审验证。

**v2 修订说明**：v1 共 16 项修复，自审后——删除 1 项误报（原修复 7）、缩小 2 项修法（原修复 1/2）、降级 1 项为远期（原修复 4 方案 A）、新增 Phase 0 输入预处理、补充测试影响/工作量/风险标注/锚点兼容性说明。

## 问题总览（v2）

| 级别 | 问题 | 影响范围 | 根因位置 | 工作量 | 风险 |
|---|---|---|---|---|---|
| P0 | 还原号 `n` 在非 C 调下重导出音高错误 | 158 个音符 | `write/musicxml.py` 未用 `accidental_text` | S | 低 |
| P0 | 三连音结构丢失（`$3:2;` 标记消失） | page_001 L14 | 待诊断（parse 丢 time-modification 或 collect 漏收） | M | 中 |
| P1 | slur 漏 `)` / 漏 `(` | 4 处 | 待验证（疑 chord 成员 slur 丢失） | M | 低 |
| P1 | slur 嵌套（多条并行 slur 同用 `()`） | 3+ 处 | 语法表达力限制 | S(序列化)/L(语法) | 低/高 |
| P1 | 跨连音组 slur 致连音内括号不配对 | 2 处 | `write/jianpu_text.py` tuplet + slur 交互 | S | 低 |
| P1 | measure-level 调号变化未跟随（**需产品决策**） | 2 处 | `_measure_lead_info` | S | 中 |
| P1 | 空小节处理不一致（取决于 print-object） | 全部页 | writer rest 逻辑 | M | 低 |
| P1 | measure rest 展平成畸形长延音 | 2 处 | `safe_duration_affixes` 未 bypass | S | 低 |
| P1 | 多声部交错混入（voice2 串进 voice1） | 全部页 | writer 线性遍历 events | M(B')/L(A) | 中/高 |
| P1 | 小节合并（m9+m10 并成一行） | page_001 L11 | backup 跨 measure 边界 | M | 中 |
| P1 | 空小节被解析器跳过丢位置（**注意锚点兼容**） | 28 个小节 | `flush_measure()` | S | 中 |
| P2 | 过满小节 / 补拍凑数 | 多处 | Audiveris 输入 | S | 低 |
| P2 | 畸形多附点 | 多处 | `_MAX_GENERATED_DOTS` | S | 低 |
| P2 | 32nd 前缀 `d`+降号 `b` 粘连 | page_001 | 前缀设计 | M | 中（兼容性） |
| P2 | staccatissimo 等未知奏法丢弃 | 12 次 | `PERFORMANCE_MARKS` 注册表 | S | 低 |

~~P1 | 6/8 拍号变化不一致~~ **（v2 删除：自审确认为误报。page_002 的 m11 与 m21 都是 6/8，中间无 4/4，m21 不输出是「无变化不输出」的正确行为，Audiveris 的重复 time 标记是输入冗余。）**

---

## Phase 0：输入预处理（v2 新增，先于一切修复）

**动机**：Audiveris 的脏输入是多个下游症状的放大器。先在 `parse/musicxml.py` 读入后加一个 sanitize 层，不动语法层即可缓解三类问题：

1. **去重复音符**：同一 `id` 的 note 出现两次（page_001 2nd-m8 的 D4-A4 重复，中间 `<backup>` 回退）→ 保留一份。这直接消除该处 5 个 `(` 悬空的括号混乱。
2. **截断过满小节**：小节 advance 总时值超过拍号上限（如 9.25/4 拍）→ 截断到上限并记警告。缓解小节合并与补拍。
3. **过滤冗余 attributes**：与当前状态相同的 `<key>`/`<time>` 重复标记（page_002 m21 的 6/8）→ 忽略。避免下游误判。

涉及文件：`backend/score_trans/domain/parse/musicxml.py`（读入后、建模前的 sanitize 函数）
工作量：M ｜ 风险：低（只删冗余，不改语义）

---

## P0 级修复

### 修复 1：还原号 `n` 重导出音高错误（v2 缩小修法）

**问题**：`_parse_pitch()` 把 `n` 存成 `accidental=0` + `accidental_text="♮"`——**信息其实没丢**（`accidental_text` 字段保留着还原标记）。丢的是 `write/musicxml.py` 重导出时没有使用它，音高按调号默认走（Bb 调 `n1` 变回 Bb）。共 158 个音符。

**修复（v2 缩小为单点）**：~~v1 的 NATURAL_OVERRIDE 哨兵值方案废弃~~（`accidental` 是全链路使用的 `Fraction`，塞哨兵会到处加 `isinstance` 判断，风险大）。改为：

**只改 `write/musicxml.py`**：当 event 的 pitch 有 `accidental_text` 为还原（`"n"` 或 `"♮"`）时，导出 MusicXML 强制写 `<accidental>natural</accidental>` 且 `<alter>` 取「调号默认 alter 的还原」（即该 step 在调号下的默认音被显式还原为 0）。不动数据模型、不动解析器、不动简谱文本格式。

涉及文件：
- `backend/score_trans/domain/write/musicxml.py` — 音符导出处（约 pitch 序列化部分）

工作量：S ｜ 风险：低（单文件，行为只增不改）

**验证**：page_002（G调）的 `n7` 重导出后应为 `<step>F</step><alter>0</alter><accidental>natural</accidental>`（当前错误输出 `<alter>1</alter>` 或依赖调号）；page_003（Bb调）的 `n1'` 应为 `<step>B</step><alter>0</alter>`。

### 修复 2：三连音结构丢失（v2 改为「先诊断再修」）

**问题**：page_001 第二轮 m1 是 3:2 三连音（3 个 eighth，`time-modification` + `tuplet start/stop` 齐全），简谱 L14 输出 `s4. sb4. s2.`（附点 16th），无 `$3:2;`。

**v2 修正**：v1 的「必须输出 `$ratio;...$`」是症状重述，不是修法。关键线索：输出值 `s4.`（附点16th ≈ 1/3 拍的吸附值）说明**时值走了 `safe_duration_affixes` 吸附但 tuplet 上下文丢失**。需先诊断丢在哪一环：

**诊断步骤（写最小复现）**：
1. 构造仅含该三连音的最小 XML（F 谱号 + 3:2 tuplet 三个 eighth），跑 `musicxml_path_to_scores()`，检查事件上是否带 tuplet 信息（`time-modification` 是否被 `parse/musicxml.py` 保留）。
2. 若 parse 侧已丢 → 修 `parse/musicxml.py`（嫌疑：谱号切换小节 `<clef>` 变化 + 无 `<key>` 时 attributes 解析分支跳过了 time-modification）。
3. 若 parse 侧保留 → 修 `write/jianpu_text.py` 的 `_collect_tuplet_events`（嫌疑：voice/backup 交错时 tuplet 成员被拆散，不连续导致收集失败）。

涉及文件（按诊断结果二选一）：
- `backend/score_trans/domain/parse/musicxml.py` — time-modification/tuplet 解析
- `backend/score_trans/domain/write/jianpu_text.py` — `_collect_tuplet_events` 约 629 行

工作量：M（含诊断）｜ 风险：中

**验证**：最小复现输出含 `$3:2;...$`；page_001 L14 重跑后出现连音标记；回解析 tuplet 结构保留。

---

## P1 级修复

### 修复 3：slur 漏 `)` / 漏 `(`（v2 标注假设待验证）

**问题**：
- page_001 L8/m6：chord[A6,D6,B5] 有 slur_stop，简谱 `h[6''+2''+7']` 缺 `)`。
- page_001 L7/m5：2 个 slur_start 只 1 个 `)`。
- page_004 L4/m2：chord B4 有 slur_start，简谱 `[7+2] 1')` 缺 `(`。

**v2 修正**：「chord 成员 slur 未被捕获」是**假设**，证据是 4 处漏括号都发生在 chord 边界，但未验证 parser 是否真的丢 chord 成员的 slur。修复前先做一步验证：构造「slur 标在 `<chord/>` 成员 note 上」的最小 XML，检查 event 的 slur_start/slur_stop 是否正确归位。

- 若假设成立 → 修 `parse/musicxml.py`：chord 合并时收集**所有成员**的 notations slur。
- 若假设不成立 → 缺口在 measure 归一化（事件被合并/丢弃时 slur 标记丢失），修对应环节。

无论哪种，**writer 加兜底校验**：输出完整文本后检查 `(` 与 `)` 总数，不等则记 warning 日志（不阻断）。

涉及文件：
- `backend/score_trans/domain/parse/musicxml.py` — chord slur 解析（待验证）
- `backend/score_trans/domain/write/jianpu_text.py` — 兜底校验（`_score_to_jianpu_text` 末尾）

工作量：M ｜ 风险：低

### 修复 4：slur 嵌套（v2 降级方案 A 为远期）

**问题**：XML 用 `slur number="1"/"2"/"4"/"5"` 区分并行 slur，简谱只有 `()` 一种（已验证 `docs/jianpu-syntax.md:213`：「连音线可以跨小节，但不能嵌套」——规定属实）。多条 slur 叠加就嵌套，违反语法规定。

**v2 修正**：~~方案 A（编号 slur 语法）降级为远期演进项~~。理由：语法扩展的 blast radius 覆盖编辑器解析、SVG 渲染、前端高亮、AI 转录输出格式、锚点系统——这是半个产品功能，不是 bug fix。

**近期方案（B，序列化）**：writer 输出前对并行 slur 做序列化——同一时刻只保留最早开始的那条 slur 的 `(` `)`，其余 slur 的起止标记丢弃并记 warning（含被丢弃 slur 的音高/位置，便于排查）。保证语法合法，损失部分连音线。

**远期方案（A，产品演进）**：带编号 slur 语法，需单独立项评估前端/渲染/AI 全链路。

涉及文件：
- `backend/score_trans/domain/write/jianpu_text.py` — slur 输出 617-625 行

工作量：S（B）｜ 风险：低（B）

### 修复 5：跨连音组 slur 致连音内括号不配对

**问题**：slur_start 在第一个三连音组内、slur_stop 在组外。简谱 `$(b6, b7, b6,$ b7,)`——`$` 内 `(` 无 `)`，`)` 在 `$` 外。

**修复**：`_tuplet_to_token` 输出 tuplet body 后校验局部括号配对；不平衡时把悬空的 `(` `)` 移到 `$...$` 之外（组前/组后），保持连音体内部纯净。

涉及文件：
- `backend/score_trans/domain/write/jianpu_text.py` — `_tuplet_to_token` 648-688 行

工作量：S ｜ 风险：低

### 修复 6：measure-level 调号变化未跟随（v2 标注为产品决策）

**问题**：page_002 m5、page_003 m19 有 `<fifths>0`（转 C 调），简谱无 `1=C`，仍按原调映射。

**v2 修正**：原方案默认「跟随 XML key 变化」是对的——**但如果 Audiveris 的中途 key 是误识别（OMR 常见），跟随反而把噪声写进简谱**。page_002/003 的中途 `fifths=0` 后没有再变回原调，无法仅凭 XML 判断真伪（需对照原谱图片）。因此此项是**产品决策**，不是纯技术修复：

- **决策 A（跟随）**：`_measure_lead_info` 检测 measure-level `<key>` 与当前调不同 → 行首输出 `1={新调}`。`parse/musicxml.py` 需把 measure 级 key 变化传给 writer。
- **决策 B（忽略中途变化）**：维持现状（只认首个 key），但在转换日志里 warning 提示「检测到中途调号变化，已忽略」。

**建议**：先做 B（加 warning），积累一批真实数据后再评估是否切 A。

涉及文件：
- `backend/score_trans/domain/write/jianpu_text.py` — `_measure_lead_info` 109-127 行（如选 A）
- `backend/score_trans/domain/parse/musicxml.py` — measure-level key（如选 A）；warning（B 必做）

工作量：S ｜ 风险：中（选 A 可能引入 OMR 噪声）

### 修复 7（v2 重编号，原 8）：空小节处理不一致

**问题**：小节休止的处理取决于 `print-object` 属性和 measure 内容：
- `print-object=no` → 空 `|` 行（解析器跳过丢位置）
- 无 `print-object` → `s0----` 畸形长延音
- 空元素 `<measure/>` → `w0`
- multiple-rest + 音符 → 只取音符丢 rest

**修复（统一为三条规则）**：
1. **隐藏的 measure rest（`print-object=no`）→ 空 `|` 行**（维持现状）。
2. **显示的 measure rest（无 print-object 或 =yes）→ `w0`**，不走 `safe_duration_affixes`（消灭 `s0----`）。
3. **multiple-rest N** → 由 `parse/musicxml.py` 展开为 N 个小节的 measure rest，每小节一个 `w0`（消灭 `h0.` × N 与「音符+多小节休止同小节」的畸形）；multiple-rest 元素本身不再传给 writer。

空元素 `<measure/>` → 输出 `w0`（维持现状）。

涉及文件：
- `backend/score_trans/domain/parse/musicxml.py` — multiple-rest 展开为多小节
- `backend/score_trans/domain/write/jianpu_text.py` — 显示 measure rest 输出 `w0`

工作量：M ｜ 风险：低

### 修复 8（v2 重编号，原 9）：measure rest 展平成长延音

（并入修复 7 的规则 2/3——显示的 measure rest 直接 `w0`；多小节休止在 parse 侧展开成逐小节 measure rest。`jianpu_tokens.py` 无需改，因为 measure rest 在 writer 里 bypass 掉 `safe_duration_affixes`。）

~~独立修复项取消~~，保留涉及文件：
- `backend/score_trans/domain/write/jianpu_text.py` — rest 输出 176-178、603-604 行（bypass 分支）

### 修复 9（v2 重编号，原 10）：多声部交错混入（v2 改推荐方案）

**问题**：全部 XML 都有多 voice，writer 线性遍历 `measure.events`（按 cursor/backup 交错序）把多声部串成一条线 → voice2 混入、小节过满、括号错乱。

**v2 修正**：~~原方案 A（`// @voice` 语法）为推荐~~ 降为远期（同修复 4 的理由：语法扩展波及编辑器/渲染/前端/AI 全链路，是产品功能）。近期推荐改为：

- **方案 B'（推荐，近期）**：writer 在每个 measure 内**按 voice 排序**——voice1 的全部事件在前、voice2 在后（组内保持时序），消除交错混乱。小节仍可能过满（两个声部的时值相加），但 slur 不再被 backup 切碎、括号错位大幅减少。改动只在 `_score_to_jianpu_text` 的遍历前加一次 `events.sort(key=voice)`。
- **方案 B（备选）**：只输出 voice1，voice2+ 丢弃并 warning。单旋律最干净，但丢信息。
- **方案 A（远期）**：`// @voice` 语法，单独立项。

**这是产品决策**：B' 保留全部音符（过满小节靠渲染层横向滚动/换行容忍）；B 最干净但丢伴奏声部。建议先 B' 观察真实使用反馈。

涉及文件：
- `backend/score_trans/domain/write/jianpu_text.py` — `_score_to_jianpu_text` 136-216 行（排序）

工作量：S（B'）/ M（B）｜ 风险：中（B' 小节过满的渲染表现需验证）

### 修复 10（v2 重编号，原 11）：小节合并（m9+m10 并成一行）

**问题**：page_001 m9/m10 间的 `<backup>` 使两小节内容交错，转换器合并到 L11 一行，后续小节编号整体错位。

**修复**：`parse/musicxml.py` 的 measure 边界判定——确认 `<backup>` 只在 measure 内部移动 cursor。若 Phase 0 的「截断过满小节」+ 修复 9 的「按 voice 排序」实施后，此问题的触发条件（过满+交错）已被大幅削弱，可能自然消失。**建议放到 Phase 0 与修复 9 之后复测，若仍复现再修 `_read_measure_structure`。**

涉及文件：
- `backend/score_trans/domain/parse/musicxml.py` — `_read_measure_structure` 约 380-419 行

工作量：M ｜ 风险：中

### 修复 11（v2 重编号，原 12）：空小节被解析器跳过丢位置（v2 补充锚点兼容风险）

**问题**：`flush_measure()` 遇到无 event 的空 `|` 行不创建 `Measure`，重解析丢 28 个小节位置，后续小节编号偏移。

**v2 补充的关键风险**：溯源系统（`reconciliation.py`）的锚点按 `measure_index` 映射到 score-link-map。让空小节进入模型后，**所有后续小节的 index 前移，已保存的叠加层映射会整体错位**。两个应对：
- **方案一（推荐）**：`flush_measure()` 为空小节创建含一个隐藏全休止的 `Measure`（事件非空，现有渲染/溯源逻辑无需改动，`render/main.py:66` 的高度估算 `len(score.measures)` 自然适配）。
- **方案二**：只改解析器保留空 `Measure`，同时给 reconciliation 加 index 兼容映射——复杂，不推荐。

**注意**：即便用方案一，**修复上线前已生成的历史叠加层/render-map JSON 仍会错位**，需要接受旧数据作废或在管线里重新生成。

涉及文件：
- `backend/score_trans/domain/parse/jianpu_text.py` — `flush_measure()` 605-608 行

工作量：S ｜ 风险：中（历史锚点数据兼容）

---

## P2 级修复

### 修复 12（原 13）：过满小节 / 补拍凑数

**问题**：Audiveris 输入小节常过满（7.5~9.25 拍 vs 4 拍），转换器补 `0`/`q0` 凑数。

**修复**：主要靠 **Phase 0 的截断过满小节**解决源头。补拍行为本身保留（保拍号完整性），但补拍时记 warning。注意：`parse/musicxml.py` 的 `_normalize_measure`（约 1042-1050 行）会在重解析时再补休止——writer 不补拍与 parser 补拍之间存在轻微不对称，属可容忍（时值语义一致）。

工作量：S ｜ 风险：低

### 修复 13（原 14）：畸形多附点

**修复**：`jianpu_tokens.py` 的 `_MAX_GENERATED_DOTS` 从 3 降为 2；超过时改用「基础时值 + 延音」组合（3.75 拍 → `h0.-` 而非 `h0...`）。

涉及文件：`backend/score_trans/domain/jianpu_tokens.py` — 32 行、70-95 行
工作量：S ｜ 风险：低（注意现有测试对 3 附点的断言需同步更新）

### 修复 14（原 15）：32nd 前缀 `d` + 降号 `b` 粘连

**问题**：`db7'`、`db3'` 中 `d`(32nd) + `b`(降号) 粘连成 `db`，与 64th `dd` 视觉混淆。

**v2 风险补充**：改前缀是**破坏性语法变更**——已保存的简谱文本、AI 转录输出、文档全部受影响。除非用户实际抱怨，否则**建议只改文档说明（jianpu-syntax.md 注明 `db7'` 读作 d+b7'）**，不动语法。若确要改，需同步：tokenizer、parser、writer、AI prompt 模板、语法文档、兼容旧文本的迁移。

工作量：M（含兼容）｜ 风险：中高（兼容性）

### 修复 15（原 16）：staccatissimo 等未知奏法丢弃

**修复**：`performance_marks.py` 的 `PERFORMANCE_MARKS` 注册表补充：`staccatissimo`（建议 `^!`）、`turn`（`^t`）、`inverted-turn`（`^t'`）。同时 parser 的 mark token 表同步。

涉及文件：`backend/score_trans/domain/performance_marks.py`
工作量：S ｜ 风险：低

---

## 实施顺序（v2）

```
Phase 0   输入预处理（去重/截断/滤冗余）          ← 新增，先做
P0-1      修复 1  还原号（write/musicxml.py 单点）
P0-2      修复 2  三连音（先最小复现诊断）
P1-a      修复 3  slur 漏括号（先验证 chord 假设）+ writer 兜底校验
P1-b      修复 4B slur 序列化 + 修复 5 跨连音组 slur
P1-c      修复 7  空小节/measure rest/multiple-rest 统一
P1-d      修复 9B' voice 排序（产品决策 B'/B）→ 复测修复 10 是否仍复现
P1-e      修复 11 空小节保留（注意历史锚点作废）
P1-f      修复 6  调号变化（先 B: 只加 warning）
P2        修复 12-15
远期      修复 4A 编号 slur 语法、修复 9A @voice 语法、修复 14 前缀变更
```

## 验证方法（v2 补充测试影响）

每批修复后：
1. 对 page_001-004 重跑 `musicxml_to_jianpu()`，逐行对比修复前后。
2. `parse_jianpu_scores()` 回解析，确认无 `JianpuSyntaxError`。
3. `normalize_jianpu_text()` 归一化往返幂等（`norm == norm(norm(text))`）。
4. 括号配对：全文件 `(` 与 `)` 数量相等。
5. 小节数：重解析小节数 == 原始文本小节行数（修复 11 后生效）。
6. 还原号：`n` 音重导出后 `<alter>` 不跟随调号（修复 1 后生效）。
7. **跑全量测试 `python -m pytest tests/test_jianpu.py tests/test_convert.py`**——注意：修复 2/7/11/13 大概率打破现有断言（如 `test_measure_level_signatures_roundtrip_without_empty_measures`、隐含 3 附点行为的用例），**测试更新是每批的必要交付物**，不是可选项。
8. **溯源回归**（修复 11 后必做）：跑一次完整识别管线，确认 score-link-map 的 `measure_index` 与渲染 render-map 对齐，点击叠加层定位正确。

## 不修改的文件

本方案只涉及 `domain/` 层：
- `domain/parse/jianpu_text.py`
- `domain/parse/musicxml.py`
- `domain/write/jianpu_text.py`
- `domain/write/musicxml.py`（v2 新增，修复 1）
- `domain/jianpu_tokens.py`
- `domain/performance_marks.py`

不涉及 `api/`、`exec/`、`services/`。**例外**：若远期采纳修复 4A/9A（语法扩展），将波及 `desktop/` 前端与 `services/render/`——这正是它们被降级为远期的原因。

## 遗留决策点（需用户拍板）

| # | 决策 | 选项 | 推荐 |
|---|---|---|---|
| 1 | 多声部（修复 9） | B' 排序保留 / B 只留 voice1 / A 语法（远期） | 先 B' |
| 2 | 中途调号（修复 6） | B 忽略+warning / A 跟随 | 先 B |
| 3 | 32nd 前缀（修复 14） | 改语法（破坏性）/ 只改文档 | 只改文档 |
| 4 | 历史锚点（修复 11） | 接受旧叠加层作废重生成 / 加兼容映射 | 作废重生成 |
