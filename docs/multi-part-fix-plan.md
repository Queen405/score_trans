# 多声部问题修复方案

> 配套文档：[multi-part-audit-2026-09.md](multi-part-audit-2026-09.md)（问题清单与实测证据）
> 当前基线：`996 passed, 1 skipped, 8 xfailed`（CI 绿色）
> 守护测试：`tests/test_multi_part_roundtrip.py`

---

## 0. 方案总览

### 修复项清单

| 编号 | 问题 | 等级 | 改动量 | 验收（翻绿的测试） |
|------|------|------|--------|-------------------|
| **F1** | MusicXML 渲染只画第一个声部 | P0 | 小 | 新增 `test_render_musicxml_keeps_all_parts` |
| **F2** | 复调 voice 塌缩（小节 4 拍膨胀成 8 拍） | P0 | 中 | `test_polyphonic_measure_span_does_not_grow`<br>`test_polyphonic_note_start_positions_survive_roundtrip`<br>`test_voice_assignment_survives_jianpu_text_roundtrip`<br>`test_polyphonic_musicxml_output_keeps_voice_elements` |
| **F3** | 低音谱号 / 大谱表结构丢失 | P0 | 中 | `test_grand_staff_output_keeps_bass_clef`<br>`test_grand_staff_output_keeps_staves_element` |
| **F4** | 声部名被改写 / 单声部丢失 | P0 | 小 | `test_grand_staff_split_preserves_original_part_name`<br>`test_single_part_name_survives_jianpu_text_roundtrip` |
| F5 | 小节数校验三处重复、定位差 | P1 | 小 | 新增定位断言 |
| F6 | 渲染层硬编码垂直常量 | P1 | 中 | 新增样式缩放测试 |
| F7 | 跨声部连音线无法绘制 | P1 | 大 | 新增多声部 spanner 测试 |
| F8 | 前端无多声部编辑 UI | P2 | 大 | — |

### 建议的实施顺序

```
F1（最快止血，独立无依赖）
   ↓
F4 → F3（同属"元数据保留"，改数据模型，放在一起做）
   ↓
F2（最复杂，涉及语法设计决策，需先拍板方案）
   ↓
F5 → F6 → F7（一致性与健壮性）
   ↓
F8（体验层）
```

**F1 建议立刻做**：改动约 10 行，零依赖，修掉的是"多声部谱子只显示一声部"这种用户一眼能看见的问题。

---

## 1. F1 — 修复 MusicXML 渲染只画第一个声部

### 根因

`exec/render/actions.py` 中 `RenderMusicXmlJianpuAction` 有两条路径：

```python
# L151 execute_a4_pages —— 正确：取全部声部
scores = self.build_scores(...)
_validate_multi_part_measure_counts(scores)
return self.render_service.render_scores_a4_svg_pages(scores, ...)

# L89 execute / L118 execute_page —— 错误：只取第一个
score = self.build_score(...)          # convert/actions.py:65 → scores[0]
return self.render_service.render_score_svg(score, ...)   # 单数 API
```

`exec/render/actions.py:688` 的最终渲染流程调用 `execute_page`，因此多声部 MusicXML 从这里渲染出来**只剩第一声部**。

### 修复设计

需要确认一件事：**`render_score_svg`（单数）与 `render_scores_a4_svg_pages`（复数）的输出契约不同**——前者接收固定页面尺寸（`page_width` / `page_height`），后者是 A4 分页。所以不能简单把 `execute_page` 换成 `execute_a4_pages`。

推荐做法：在 `PublicationRenderService` 上**新增一个多声部的定尺寸渲染方法**，与单声部的 `render_score_page_svg` 对称：

```python
# services/render/render_service.py
def render_scores_page_svg(
    self,
    scores: list[JianpuScore],      # 复数
    output_path: str | Path,
    *,
    page_width: float,
    page_height: float,
    **kwargs,
) -> Path:
    """多声部版本，与 render_score_page_svg 对称。"""
```

然后：

1. `RenderMusicXmlJianpuAction.execute_page()` 改用 `build_scores()` + `render_scores_page_svg()`
2. `RenderMusicXmlJianpuAction.execute()` 同样改用 `build_scores()`（保留方法签名，内部换成复数渲染）
3. `exec/convert/actions.py:190` 的 `build_score()` **保留但改名**为 `first_score()`，语义显式化，避免再被误当成"完整转换"使用（见 F6 备注）

### 涉及文件

- `backend/score_trans/services/render/render_service.py`（新增方法）
- `backend/score_trans/exec/render/actions.py`（L89-147 两处）
- `backend/score_trans/exec/convert/actions.py`（方法改名）

### 验收

新增测试：给 `execute_page` 传两声部 MusicXML，断言输出 SVG 同时包含两个声部的音符，且 `class="measure"` 节点数翻倍。

### 风险

- **低**。渲染引擎本身已支持多声部（`_normalize_parts` / `_draw_system`），只是入口没传进去。
- 注意：`execute_page` 的页面尺寸是外部传入的（可能来自图片尺寸），多声部后内容变高，可能需要按比例调整 `content_scale_percent`，否则会溢出页面。建议先按声部数做一次垂直缩放兜底。

---

## 2. F4 — 修复声部名被改写 / 单声部丢失

### 根因（两处）

**(a) 拆分时改写名称** — `domain/parse/musicxml.py:346-348`

```python
staff_score.part_name = (
    f"{score.part_name}(staff {staff})" if score.part_name else f"staff {staff}"
)
```

**(b) 单声部不输出 `@part`** — `domain/write/jianpu_text.py:66-68`

```python
if len(scores) <= 1:
    return score_to_jianpu_document(score, ...)   # 不输出 // @part
```

### 修复设计

**(a)** staff 归属不应编码进 `part_name`。给 `JianpuScore` 增加独立字段：

```python
# models/score.py
part_staff: str | None = None   # 来源 staff 编号，仅用于溯源
```

`_split_part_by_staff` 改为 `part_name=score.part_name`（原样保留），另设 `part_staff=staff`。

> 连带收益：`_extract_instrument_profile`（L373-383）靠 part-name 推断乐器（erhu / ruan / guzheng），名称不再被污染后，乐器画像失配问题一并解决。

**(b)** `scores_to_jianpu_document` 去掉 `len(scores) <= 1` 的短路，改为**始终输出 `@part` 标记**：

```python
def scores_to_jianpu_document(scores, *, accidental_mode="auto"):
    if not scores:
        return score_to_jianpu_document(JianpuScore(), accidental_mode=accidental_mode)
    # 移除 len(scores) <= 1 的短路分支
    ...
```

### 涉及文件

- `backend/score_trans/models/score.py`（加字段）
- `backend/score_trans/domain/parse/musicxml.py`（L346-348）
- `backend/score_trans/domain/write/jianpu_text.py`（L66-68）

### 验收

`test_grand_staff_split_preserves_original_part_name`、`test_single_part_name_survives_jianpu_text_roundtrip` 两条 xfail 翻绿。

### 风险

- **中**。改动 (b) 会让**所有单声部导出都多出一行 `// @part 1 name="..."`**，属于用户可见的格式变化。
  - 需要同步更新 `docs/jianpu-syntax.md` 的示例
  - 需要检查 `tests/` 中依赖单声部文本快照的用例（预计 `test_export.py`、`test_jianpu.py` 有若干断言需更新）
  - 若担心破坏现有用户文件，可加**兼容开关**，但建议在发布前统一切换并保持单一行为，避免长期存在两条路径

---

## 3. F3 — 修复低音谱号 / 大谱表丢失

### 根因

解析侧 `domain/parse/musicxml.py` **完全没有读取 clef**（全文件 grep `clef` 无任何命中）。写出侧 `domain/write/musicxml.py:108-110` 硬编码：

```python
clef = ET.SubElement(attrs, "clef")
ET.SubElement(clef, "sign").text = "G"
ET.SubElement(clef, "line").text = "2"
```

所以这不是"读了又写丢"，而是**整条链路缺失**，需要新增。

### 修复设计

**第一步：数据模型**（`models/score.py`）

```python
@dataclass(slots=True)
class JianpuScore:
    ...
    clef_sign: str | None = None      # "G" / "F" / "C"，None 表示未指定
    clef_line: int | None = None      # 2 / 4 / 3
    staves: int = 1                   # 该声部在原始谱中的 staff 总数
```

**第二步：解析侧**（`domain/parse/musicxml.py`）

在读取 `<attributes>` 的位置（`_read_measure_events` 附近，L592 读取 voice/staff 的同一处）补充：

```python
# 读取 <clef number="N"> 与 <staves>
for clef_el in attributes.findall("clef"):
    number = clef_el.get("number") or "1"
    sign = _text(clef_el.find("sign"))
    line = _text(clef_el.find("line"))
    clefs_by_number[number] = (sign, int(line) if line else None)
staves_el = attributes.find("staves")
```

按 part 粒度收集：每个 part 记录 `clefs: dict[str, tuple[str, int]]` 与 `staves: int`。

**第三步：拆分时分配**（`_split_part_by_staff`）

拆成多个 score 后，按各自的 staff 编号取对应谱号：

```python
staff_score.clef_sign, staff_score.clef_line = clefs_by_staff.get(staff, (None, None))
staff_score.staves = len(sorted_staffs)
```

**第四步：写出侧**（`domain/write/musicxml.py:107-110`）

```python
if index == 1:
    clef = ET.SubElement(attrs, "clef")
    ET.SubElement(clef, "sign").text = score.clef_sign or "G"
    ET.SubElement(clef, "line").text = str(score.clef_line or 2)
```

同时在 `<attributes>` 中按需输出 `<staves>`：

```python
if index == 1 and score.staves > 1:
    ET.SubElement(attrs, "staves").text = str(score.staves)
```

> 注意：`<staves>` 要输出，各 part 还需要携带 `number` 属性的 clef，否则 MuseScore 无法还原大谱表。若要**完整**还原大谱表，本质上是把两个 staff 合并回**一个 part** 输出——这比"保留谱号"复杂得多，建议作为 F3 的**第二阶段**单独评估。
>
> 第一阶段（本方案）的目标收敛为：**保证左手声部拿到 F 谱号**，这样即使拆成两个分谱，音高显示也是正确的——这是当前最影响可用性的问题。

### 涉及文件

- `backend/score_trans/models/score.py`
- `backend/score_trans/domain/parse/musicxml.py`（新增 clef/staves 读取）
- `backend/score_trans/domain/parse/musicxml.py`（`_split_part_by_staff` 分配）
- `backend/score_trans/domain/write/musicxml.py`（L107-110）

### 验收

`test_grand_staff_output_keeps_bass_clef` 翻绿。
`test_grand_staff_output_keeps_staves_element` 需视第二阶段是否实施决定——若只做第一阶段，可把该用例改为断言"各声部带正确 clef"并移除 staves 断言，或继续保留 xfail 作为二期待办。

### 风险

- **中**。新增字段是安全的（有默认值），但 clef 解析要处理多种形态：无 `number` 属性（单 staff）、有 `number`、`clef` 出现在非首小节（中途换谱号）。中途换谱号的情况本方案**不处理**（超出当前数据模型能力），建议遇到时沿用首小节的谱号。

---

## 4. F2 — 修复复调 voice 塌缩【需先拍板】

这是最复杂的一项，且涉及**语法设计决策**。实测的损坏程度：

```
原始：voice1 [C4 @0拍 2拍] [E4 @2拍 2拍]  ‖  voice2 [G4 @0拍 4拍]   小节跨度 = 4 拍
往返：           [C4 @0] [E4 @2] [G4 @4]                              小节跨度 = 8 拍
```

并行的两个声部被串行化，小节时长翻倍，**且无任何报错**。

### 方案 A：止损（推荐先做）

检测到声部内存在多个 voice 时，**拒绝转换并明确报错**，而不是静默拍平。

```python
# domain/write/jianpu_text.py
def _assert_single_voice(score: JianpuScore) -> None:
    voices = {
        (event.voice or "1").strip()
        for measure in score.measures
        for event in measure.events
        if event.kind == "note"
    }
    if len(voices) > 1:
        raise MultiVoiceNotSupportedError(
            f"声部「{score.part_name or '未命名'}」包含 {len(voices)} 个 voice，"
            f"简谱文本暂不支持同声部复调，无法无损转换。"
        )
```

在 `scores_to_jianpu_document` 入口对每个 score 调用。

- **优点**：改动小（约 20 行）、风险低、立即消除静默损坏
- **缺点**：复调作品无法走文本编辑链路（会明确报错，用户至少知道原因）
- **影响面**：主要是古典复调（赋格、合唱同谱）。钢琴大谱表**不受影响**——它有 staff，会被 `_split_part_by_staff` 拆成两个单 voice 声部

### 方案 B：完整支持（长期）

扩展简谱语法，让文本能表达 voice。

语法提案（供讨论）：

```text
// @part 1 name="Flute"
1=C
4/4
// @voice 1
h1 h3 |
// @voice 2
w5 |
```

或行内形式 `[v1]h1 h3 | [v2]w5 |`

需要改动：
1. 语法设计与文档（`docs/jianpu-syntax.md`）
2. 解析器：新增 `@voice` 标记或行内前缀，设置 `event.voice`
3. 生成器：`_events_grouped_by_voice` 之外新增 voice 分段输出
4. **前端**：语法高亮、编辑器支持、播放对齐
5. **往返测试**：voice 归属不变量

- **优点**：功能完整
- **缺点**：工作量大（涉及解析器、生成器、前端、文档），且语法一旦发布就是长期承诺，需要慎重设计

### 建议

**先做 A，把 A 的报错信息写得足够友好，同时观察真实用户遇到复调的频率，再决定是否投入 B。**

如果采用方案 A，需要同步：
- 新增异常类型（放 `models/common/errors.py`）
- API 层捕获并转成友好的错误响应
- 前端 `SyntaxDiagnosticPanel` 展示该诊断
- 文档说明该限制

### 验收（方案 A）

新增测试：断言多 voice 输入抛出明确的 `MultiVoiceNotSupportedError`，且异常信息包含声部名与 voice 数量。

原 4 条 voice 往返 xfail 用例改为断言"抛错"而非"无损往返"，并移出 xfail。

---

## 5. F5 — 统一小节数校验

### 根因

三处重复实现、且层次不一致：

| 位置 | 行为 |
|------|------|
| `domain/parse/jianpu_text.py:432` `_validate_part_measure_counts` | 抛 `JianpuSyntaxError`，定位到**首个 `@part` 标记**（line=1 col=1） |
| `exec/render/actions.py:830` `_validate_multi_part_measure_counts` | 抛 `JianpuValidationError` |
| `domain/parse/musicxml.py` | **完全没有校验** |

### 修复设计

1. 抽出**单一实现**放到领域层，例如 `domain/validation/part_consistency.py`，返回结构化的诊断（声部索引、声部名、小节数、以及**出问题的声部起始行号**）
2. 三处调用点统一改为调用它，各自包装成自己层级的异常类型
3. **MusicXML 解析侧补上校验**（在 `musicxml_to_scores` 末尾）
4. 改进错误定位：把行号指向**小节数最多的那个声部的 `@part` 标记**，而不是文档开头

### 风险

- **低**。纯重构 + 新增校验。
- 注意：给 MusicXML 侧加校验后，**原本能通过的谱子可能开始报错**。建议先以**警告**形式上线（记录到 `score.validation_errors`），观察一个版本后再转为硬错误。

---

## 6. F6 — 渲染层硬编码常量

### 根因

`renderer.py` 中垂直坐标硬编码，不随 `style.base_staff_height`（=92）缩放：

| 位置 | 常量 |
|------|------|
| L504-505 `_measure_bar_offsets` | `top=14.0` / `bottom=66.0` |
| L305, L307 空小节 | `+14.0` / `+69.0` |
| L294 part-name | `staff_y + 30` |
| L258 `system_bottom` | 混用 `base_staff_height` 与 `+69.0` |

### 修复设计

把这些常量提取到 `services/render/engraving/style.py`，改为**相对于 `base_staff_height` 的比例**：

```python
BAR_TOP_RATIO = 14.0 / 92.0
BAR_BOTTOM_RATIO = 66.0 / 92.0
PART_NAME_OFFSET_RATIO = 30.0 / 92.0
```

然后按 `style.base_staff_height * ratio` 计算。

### 验收

新增测试：用两组不同 `base_staff_height` 渲染同一个多声部谱，断言声部之间的垂直间距按比例缩放且不重叠。

### 风险

- **中**。`test_render.py` 有约 1300 行的脆弱字符串断言，改动几何计算可能导致大量快照类断言失败。建议**先把渲染断言升级为结构化检查**（读取 SVG 元素的坐标属性而非字符串匹配），再做这个重构。

> 备注：`build_score()` 改名（`F1` 第 3 点）可与本项一并处理。

---

## 7. F7 — 跨声部连音线

### 根因

`renderer.py:153` — `document_spanners = [_OpenSpanners() for _ in parts]`，spanner 按 `part_index` 完全隔离（L324, L476）。

解析侧 `_split_part_by_staff` 按 staff 拆分后，跨 staff 的 slur / tuplet 会在拆分处断裂。

### 修复设计

1. 允许 spanner 声明"跨声部"，在 `_route_spanners` 中识别起止在不同 part 的情况
2. 绘制时跨声部连线需要计算跨 staff 的曲线路径

### 风险

- **大**。涉及渲染引擎核心布局逻辑，而该引擎的测试保护很弱（`test_render.py` 主要是字符串断言）。

**强烈建议**：本项推迟到 F6 完成后（渲染测试结构化改造之后）再做，否则极易引入回归且难以发现。

---

## 8. F8 — 前端多声部编辑 UI

现状：`JianpuEditor.vue` 零多声部代码，用户必须手写 `// @part N name="..."`。
唯一支持良好的是播放（`jianpuPlayback.ts` 用 `partStates[]` + 拍点对齐）。

### 建议分两步

**第一步（轻量）**
- 声部导航：解析出声部列表，点击跳转到对应文本区间
- 声部名就地编辑
- 语法诊断面板按声部分组展示错误

**第二步（完整）**
- 分栏编辑：每个声部一栏，上下对齐
- 声部增删、排序
- 声部级试听

### 前置依赖

需要后端先暴露声部结构（F1 修完后 API 应返回 `parts: [{index, name, measure_count, text_range}]`）。

---

## 9. 验证方式

每个修复项完成后：

```bash
# 1. 跑多声部往返测试，确认对应 xfail 翻绿（XPASS 会报错，提醒删除标记）
python -m pytest tests/test_multi_part_roundtrip.py -v

# 2. 翻绿的用例，删除其 @pytest.mark.xfail 装饰器

# 3. 跑全量测试，确认无回归
python -m pytest

# 4. 代码规范
.venv/Scripts/python.exe -m ruff format backend/ tests/
.venv/Scripts/python.exe -m ruff check backend/ tests/
```

**xfail(strict=True) 的运作方式**：缺陷修复后用例会通过，pytest 报 XPASS 并让 CI 失败，强制回来删掉标记——保证"修好了会被看见"，不会出现"修好了但标记还挂着"的情况。

---

## 10. 需要你拍板的两个决策

1. **F2 复调 voice**：方案 A（止损报错）还是 B（完整支持 voice 语法）？
   建议先 A，观察实际遇到的频率再决定是否投 B。

2. **F4 改动 (b)**：单声部也输出 `// @part` 会改变所有单声部导出的文本格式，
   需要同步更新文档和若干测试快照。是否接受这个破坏性变更？

   替代方案：保留"单声部不输出 `@part`"的行为，改为在 `JianpuScore` 上单独传递 `part_name`（不改文本格式），但这样"文本 → 模型"时单声部名依然会丢，只能算部分修复。
