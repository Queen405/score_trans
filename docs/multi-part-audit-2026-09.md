# 多声部功能调研报告

> 调研日期：2026-09-04
> 调研范围：多声部文本编辑、简谱文本解析/生成、MusicXML 解析/生成、SVG 渲染、前端编辑器与播放
> 方法：代码走查 + **实测验证**（临时脚本跑通后已清理，未改动任何业务代码）
>
> **修复进度（2026-09-04）**：§2.1/§2.2/§2.3/§2.8 四个 P0 已由 `multi-part-fix-plan.md` 的 F1/F2-A/F3/F4 修复（守护测试 `tests/test_multi_part_roundtrip.py`）。§2.4(F5)/§2.5(F6)/§2.6(F7)/§2.9(F8) 仍开放。下表与正文保留原始调研结论作为问题溯源。

---

## 0. 结论速览

多声部整体是**"能跑通主路径，但存在 3 处不可逆数据损坏"**的状态。基础能力（N 个声部解析、上下分行排版、同步换行、声部名标记）已经具备，但有几条链路会产生**静默的、不可逆的信息丢失**——用户不会收到任何报错。

| 等级 | 问题 | 状态 |
|------|------|------|
| **P0** | 多 voice 经简谱文本中转后彻底塌缩为单声部 | ✅ 实测确认 |
| **P0** | 回写 MusicXML 时低音谱号丢失（F→G），大谱表结构丢失 | ✅ 实测确认 |
| **P0** | part_name 被改写（Piano→Piano(staff 1)），单声部时直接丢失 | ✅ 实测确认 |
| **P0** | 从 MusicXML 渲染时只画第一个声部（`execute_page` 走 `build_score`） | ✅ 实测确认（方案阶段发现，原报告低估为 P1） |
| P1 | 各声部小节数校验分层不一致，错误定位指向文档开头 | ✅ 实测确认 |
| P1 | 渲染层硬编码垂直常量，改样式即错位 | 代码走查 |
| P1 | 跨声部连音线/延音线无法绘制 | 代码走查 |
| P1 | tempo 宽度预留只算第一个声部 | 代码走查 |
| P1 | convert 单值接口 `build_score()` 静默丢弃其余声部 | 代码走查 |
| P2 | 前端无多声部编辑 UI，只能手写文本标记 | 代码走查 |
| P2 | API 未暴露 part 相关参数 | 代码走查 |

---

## 1. 多声部是怎么实现的

### 1.1 数据模型：声部是"隐式的"

`backend/score_trans/models/score.py`

- **没有 `Part` 数据类**。"一个声部" = **一个 `JianpuScore`**（L240-258）。
- 多声部 = `list[JianpuScore]`，靠 `part_index` / `part_name` / `part_count`（L252-256）这几个**元数据字段**标注。
- `Measure`（L133-238）**没有 voice 容器**。`Event.voice` / `Event.staff`（L98-99）是**逐音符**的字符串字段。

这个设计是所有问题的根源：**声部是列表顺序 + 音符级标签，而不是结构化的层级**。

### 1.2 简谱文本语法

```
// @part 1 name="右手"
1=C
4/4
1 2 3 4 |

// @part 2 name="左手"
1=C
4/4
w1 w1 |
```

- 标记正则：`_PART_MARKER_RE`（`domain/parse/jianpu_text.py:141-149`）
- 切分函数：`parse_jianpu_parts`（L579-719），用 `finditer` 找全部标记后按位置切片
- **支持任意 N 个声部**（循环实现，未硬编码 2）——实测 3 声部正常
- 另有 `// @page` 分页标记（L150-158），分页 × 分谱正交

### 1.3 渲染排版

`services/render/engraving/renderer.py`（2783 行）

- 归一化：`_normalize_parts()`（L552）按 `part_index` 分组
- 排版形态：**上下分行**，每个声部独占一条 staff 行，`staff_y = y + part_index * (base_staff_height + part_gap)`
- 小节对齐：`_build_cells()`（L646）按**小节索引**对齐，cell 宽度取各声部最大值（L664）
- 自动换行：`_break_systems()`（L941）以 cell 为单位整体折行，**所有声部同步换行** ✅
- 声部标签：`_part_name()`（L2561），仅首个 cell 绘制

排版主干逻辑是**正确的**，问题集中在细节（见 §2.5–2.7）。

---

## 2. 问题清单

### 2.1 【P0】多 voice 经简谱文本中转后彻底塌缩

**这是最严重的问题。**

简谱文本格式**只有 `@part` 一级多声部概念，没有 voice 级概念**。当一个 MusicXML part 内包含多个 voice（复调、钢琴左右手在同一 staff），信息必然丢失。

**实测结果：**

| 步骤 | 结果 |
|------|------|
| MusicXML → 内部模型 | 声部数=1，事件 voice=`['1','1','2']` ✅ 正确识别 |
| 模型 → 简谱文本 | `h1 h3 w5 \|` — **voice 信息完全消失** |
| 文本 → 模型 | voice=`[None, None, None]` |
| 模型 → MusicXML | `<voice>` 元素为空，**3 个音被合并为单声部序列** |

原始音乐是两个独立声部（voice1: C4 二分 + E4 二分；voice2: G4 全音符），经文本中转后变成一个单旋律序列 `1 3 5`，**拍点完全错乱**。

**代码位置：**
- `domain/write/jianpu_text.py:174` — `_events_grouped_by_voice()` 只做排序，**不输出任何 voice token**
- `domain/parse/jianpu_text.py` — 解析端**从不设置** `event.voice`

**影响面：** 所有复调音乐（合唱、钢琴多声部、弦乐重奏）走 `MusicXML → 简谱文本 → MusicXML` 链路时**不可逆损坏**，且**无任何报错**。

> 注意：MusicXML → 模型 → MusicXML **不经文本中转时是正常的**（实测 voice `['1','1','2']` 保留）。问题只出在文本这一环。

### 2.2 【P0】回写 MusicXML 时低音谱号丢失

**实测结果**（钢琴大谱表，原谱号 G2 + F4）：

```
拆出声部数: 2
  part_index=0 part_name='Piano(staff 1)'
  part_index=1 part_name='Piano(staff 2)'

回写后:
  是否含 <staves>: False          ← 大谱表结构丢失
  出现的所有 clef: [G2, G2]        ← 低音谱号 F4 变成 G2！
  谱号集合: {'G'}  (原: {G, F})    ← 丢失
```

**后果：** 左手声部被写成高音谱号，在 MuseScore 中打开时**音高全部错位**；大谱表（Grand Staff）结构消失，变成两个独立的高音谱号分谱。

**代码位置：** `domain/write/musicxml.py:108-110` — clef 恒为 G2，不区分 staff；全文件从不输出 `<staves>` 元素。

**连带问题：** 解析侧 `_split_part_by_staff()`（`domain/parse/musicxml.py:285`）把钢琴拆成两个独立 part，写出时就再也无法还原大谱表了。

### 2.3 【P0】part_name 被改写 / 单声部时丢失

**两个独立的 bug：**

**(a) 拆分时改写名称** — `domain/parse/musicxml.py:347-349`
```
"Piano"  →  "Piano(staff 1)" / "Piano(staff 2)"
```
原名称不可恢复。

**(b) 单声部时不输出 `@part`** — `domain/write/jianpu_text.py:66-68`
```python
if len(scores) <= 1:
    return score_to_jianpu_document(score, ...)   # 不输出 // @part
```

**实测：**
```
输入:  // @part 1 name="主旋律" ... → 解析 part_name='主旋律'
回写:  '1=C\n4/4\n1 2 3 4 |'        ← @part 标记消失
再解析: part_name=''                 ← 丢失
```

**连带影响：** `_extract_instrument_profile`（`domain/parse/musicxml.py:373-383）靠 part-name 推断乐器画像（erhu / ruan / guzheng）。名称被改写成 `Piano(staff 1)` 后**乐器画像失配**。

### 2.4 【P1】小节数校验分层不一致

各声部小节数不等时的行为，**每一层都不一样**：

| 层级 | 行为 | 实测 |
|------|------|------|
| 解析层 `parse_jianpu_parts` | **不校验，直接通过** | 通过（part0=1小节, part1=3小节） |
| 校验层 `validate_jianpu_text` | 报错 | `各声部小节数量不一致：右手=1、左手=3` |
| 渲染引擎 `render_scores()` | **不校验，正常渲染** | 输出 6 个 measure 节点 |
| exec 层 `_validate_multi_part_measure_counts` | 拦截 | 调用点 L175 / L291 / L734 / L752 |

**三个问题：**

1. **错误定位差** — 报错位置是 `line=1 column=1 start=0 end=20`，指向**文档开头**而不是出问题的声部，用户很难定位。
2. **引擎宽容 ≠ 安全** — 渲染引擎用 `max(各声部小节数)` 建 cell，缺小节的声部画成**空 staff**（`renderer.py:300-311`）。任何绕过 exec 层直接调引擎的路径会产出视觉上很奇怪的谱面。
3. **三处重复实现且不对称** — `exec/render/actions.py:830`、`domain/parse/jianpu_text.py:432`，而 **MusicXML 解析侧完全没有对应校验**，可以从容通过。

### 2.5 【P1】渲染层硬编码垂直常量

`renderer.py` 中的垂直坐标大量硬编码，**不随 `style.base_staff_height`（=92）缩放**：

| 位置 | 常量 |
|------|------|
| `_measure_bar_offsets` L504-505 | `top=14.0` / `bottom=66.0` |
| 空小节绘制 L305, L307 | `+14.0` / `+69.0` |
| part-name 文本 L294 | `staff_y + 30` |
| `system_bottom` L258 | 混用 `base_staff_height` 与 `+69.0` |

**后果：** 一旦调整样式参数（比如放大谱面），多声部竖排就会错位、重叠。这是 SVG 引擎被标注为"脆弱"的根源之一。

### 2.6 【P1】跨声部连线无法绘制

`renderer.py:153` — `document_spanners = [_OpenSpanners() for _ in parts]`

spanner 按 `part_index` **完全隔离**（L324, L476）。跨声部的连音线（slur）、延音线（tie）、连音组（tuplet）**画不出来**。

连带问题：MusicXML 解析侧 `_split_part_by_staff`（L285）按 staff 拆分后，**跨 staff 的 slur / tuplet 会在拆分处断裂**（同一 group_id 的事件被分进两个 score）。

代码里 `_sync_primary_tuplet`（`domain/parse/musicxml.py:1107-1122`）有一段长注释，说明曾修复过"跨小节残留 tuplet span 混入导致 start/stop 标记丢失"的 bug——说明这块本身就脆弱。

### 2.7 【P1】tempo 宽度预留只算第一个声部

`renderer.py:660-663` — `_build_cells` 只在 `measures[0]`（即 part 0）触发 `_tempo_header_min_width`。

其他声部若有独立的 tempo 变更，**宽度不会被预留**，标记可能被裁切。

### 2.8 【P0】从 MusicXML 渲染时只画第一个声部

> 调研报告初版把这条列为 P1，方案阶段追查调用链后**升级为 P0**——它有一条真实的生产调用路径。

`RenderMusicXmlJianpuAction` 有两条渲染路径：

| 方法 | 取声部 | 渲染 | 结果 |
|------|--------|------|------|
| `execute_a4_pages()` (L151) | `build_scores()` 全部 | `render_scores_a4_svg_pages(scores)` | ✅ 正确 |
| `execute()` (L89) / `execute_page()` (L118) | `build_score()` **只要 scores[0]** | `render_score_svg(score)` 单数 | ❌ 丢弃其余声部 |

`exec/convert/actions.py:65` — `build_score()` 返回 `scores[0] if scores else JianpuScore()`。

**`execute_page` 不是死代码**——`exec/render/actions.py:688` 的最终渲染流程（`FinalRenderResponse`）调用它。因此**通过该路径渲染多声部 MusicXML，只会显示第一个声部，其余全部静默丢失**。

### 2.9 【P2】前端几乎没有多声部支持

| 模块 | 多声部支持 |
|------|-----------|
| `JianpuEditor.vue` | **完全没有**（grep `part` = 0 处命中） |
| `jianpuPageSections.ts` | 只处理 `@page` 分页，`@part` 仅用于切分判断 |
| `jianpuPlayback.ts` | ✅ **唯一支持良好的模块** |
| `SyntaxView.vue:616` | 仅一行语法说明文字 |
| API 参数 | **未暴露** `part_index`，无法选声部 |

**编辑体验：** 用户必须在纯文本框里**手写** `// @part N name="..."` 标记。没有分栏、无声部切换、无声部增删、无声部名编辑、无声部级语法高亮。

**播放是例外** — `jianpuPlayback.ts` 用 `partStates[]` 分声部跟踪状态（L331-336），并用 `findTimedNoteSpans` 按**拍点**对齐多声部（L253-257），这块实现是对的。

### 2.10 【P2】语法限制的实测澄清

调研中两条初判有误，实测后纠正：

- ✅ **普通 `//` 注释行在声部内可用** — 实测通过，不会报错
- ✅ **首个 `@part` 前出现正文会报错** — 报文清晰：`第 4 行第 1 列：第一个分谱标记之前不能包含简谱正文`，行为正确

---

## 3. 测试覆盖缺口

### 现有测试

| 文件 | 用例 |
|------|------|
| `tests/test_jianpu.py` | 多声部名 JSON 转义（L326）、转 MusicXML 保声部（L357）、分页+分谱（L371）、分页往返（L398）、每页序号重置（L445）、序号不连续报错（L468） |
| `tests/test_syntax_validation.py` | 首标记前正文报错（L285）、非法 name JSON（L293）、小节数不一致诊断（L303, L364） |
| `tests/test_convert.py` | 多声部 tempo 只在首声部（L731）、多 voice timeline 用 backup/forward（L898）、单 voice 兼容（L952）、多 staff 拆分保留空小节（L1425） |
| `tests/test_render.py` | **仅 1 个**：`test_multi_part_system_contains_all_parts_and_aligned_bars`（L1909） |
| `tests/test_api_routes.py` | 小节数不一致的编码错误（L155） |
| `tests/test_export.py` | 文本导出保多声部（L141）、多页 MIDI 合并声部（L167） |

### 缺口（按重要性排序）

1. **无端到端「MusicXML 多声部 → 简谱文本 → MusicXML」往返测试** — §2.1 的 P0 塌缩问题正是被这个缺口放过的
2. **无「简谱文本 → 模型 → 简谱文本」无损往返测试** — §2.3(b) 的 part_name 丢失同样漏网
3. **无谱号/大谱表保留测试** — §2.2 的低音谱号丢失未被发现
4. 渲染测试只有 2 声部，缺：3+ 声部、不等小节数渲染、跨声部 spanner、tempo 裁切、拍号不一致对齐
5. 渲染断言方式是**字符串匹配**（`"高声部" in svg`、`svg.count('class="measure"')`），非结构化比较，非常脆弱

### 文档缺口

`docs/issues.md` 中**完全没有**多声部功能缺陷的记录——唯一提到 part 的是 L140 建议测试时断言 part ID。本次调研发现的所有问题均无文档跟踪、无测试守护。

---

## 4. 修复建议（按优先级）

**第一批 — 止损 P0 数据损坏**

1. **给 voice 加文本层表达**，或在无法表达时**显式报错**。二选一：
   - 短期：检测到声部内存在多个 voice 时，直接拒绝转文本并提示"该谱含复调声部，暂不支持转为简谱文本"
   - 长期：扩展语法支持 voice 标记（如 `// @voice 2` 或行内 `[v2]1 2 3`）
2. **保存并回写 clef 与 staves**：`JianpuScore` 增加 `clef` / `staves` 字段，解析时保留，写出时还原。至少要保证 F 谱号不丢。
3. **part_name 保留**：`_split_part_by_staff` 不要改写原名称（改用独立字段记录 staff 归属）；`scores_to_jianpu_document` 单声部也输出 `@part`。

**第二批 — 补测试守护（强烈建议先于重构）**

4. 加**往返不变量测试**：`MusicXML → 简谱文本 → MusicXML` 断言声部数、voice 数、谱号、part-name 一致。这会一次性暴露 §2.1/2.2/2.3 三个 P0。
5. 渲染测试补 3 声部、不等小节数、跨声部 spanner 场景，并把断言从字符串匹配升级为结构化检查。

**第三批 — 架构与体验**

6. 统一小节数校验到**一处**（现在是三处重复 + MusicXML 侧缺失），并改进错误定位到具体声部行号。
7. 把渲染层的硬编码垂直常量提取到 `style.py`，按 `base_staff_height` 比例计算。
8. 考虑引入真正的 `Part` 数据类，让声部从"隐式列表顺序"变成"显式结构"。
9. 前端增加多声部编辑 UI：声部列表、分栏编辑、声部名编辑、声部增删。
10. API 暴露 `part_index` 参数，支持单声部导出。
