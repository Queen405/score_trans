# 语法检查小节号 / 行号修复 —— v1 实施方案

> 定稿日期：2026-09-04
> 状态：**v1 已实施**（2026-09-04，1011 passed / 1 skipped / 1 xfailed，Ruff 全绿）
> 实施偏差见 §5.6；实施结果见 §9。
> 前置诊断（根因、实测数据）见本文档第 1–2 节，与 `docs/multi-part-audit-2026-09.md` 互补。

---

## 0. 已拍板的 4 个决策

| # | 决策点 | 结论 |
|---|--------|------|
| 1 | F3 小节编号语义 | **B — 按页连续**（每页取该页各声部小节数最大值累加，页内各声部共用起始号）。与渲染路径 `exec/render/actions.py:537-543`、编辑器 gutter `jianpuPageSections.ts:440-455` 完全一致 |
| 2 | 「各声部小节数量不一致」严重级别 | **降为 `warning`**（不再阻塞流程，前端 `hideWarnings` 可隐藏） |
| 3 | 页内缺 `@part`（F6） | **报错**，而不是静默并入上一页声部 |
| 4 | F4 / F5 / F6 | **拆为后续任务**，v1 不做 |

---

## 1. v1 范围（F1 + F2 + F3）

| 编号 | 内容 | 一句话 |
|------|------|--------|
| **F1** | 小节数一致性校验按页分组 + 降级 warning + 锚点/消息改进 | 消除多页文档上的纯误报 error |
| **F2** | `@page` 切断声部正文，页眉配置归本页第一声部 | 第 2 页的调号/拍号不再被吞掉、不再被误判为"写在音符后面" |
| **F3** | 诊断的小节号统一为「按页连续」 | 错误/警告/gutter/渲染谱面四者号一致 |

后续任务（v2，本次不做）：F4 更新过时文档 §12.2 的 `start=auto`；F5 合并三处重复的小节数校验实现；F6 页内缺 `@part` 时报错。

---

## 2. 根因回顾（实测确认）

三个缺陷只在**带 `@page` / `@part` 标记的文档**上触发；单页无标记的普通谱子（含文中途换调/换拍/变速）实测完全正常。

- **D1**：`_validate_part_measure_counts`（`jianpu_text.py:432-446`）把整篇文档所有 part 的小节数拉平比较。但每页每声部都是独立 part、各自从 1 编号 → 任何多页文档必然误报。
- **D2**：`parse_jianpu_parts`（`jianpu_text.py:668`）的 `end` 只切到下一个 `@part`，无视 `@page` → 第 2 页写在 `@part` 之前的配置被算进上一页最后一个声部。
- **D3**：诊断里三套编号互不一致（警告用 `display_number` 每页重开 / 错误用 `_read_new_syntax.current_measure` 全篇累计 / 渲染与 gutter 按页连续）。

实测数据（脚本已清理，可随时重跑）：

| 用例 | 现状 | v1 期望 |
|------|------|---------|
| A 单声部两页，配置在 `@part` 后 | `[error] 各声部小节数量不一致：旋律=3、旋律=2` | 0 条 |
| B/K 第 2 页配置在 `@part` 前，上一页已收尾 | 2 条误报「少拍」+ 1 条误报 error | 0 条 |
| C 同上但上一页末小节无小节线 | 2 条误报 error，行号落在第 7、8 行配置行 | 0 条 |
| G 多声部第 2 页第 2 声部报错 | 真值第 2/3 小节 → 报成第 5/6 小节 | 报第 4/5 小节（按页连续） |

---

## 3. F1 — 小节数校验按页分组 + 降级 warning

**文件**：`backend/score_trans/domain/parse/jianpu_text.py`

### 3.1 新增两个 helper（放在 `_validate_part_measure_counts` 之前）

```python
def _iter_page_part_groups(
    parts: list[ParsedJianpuPart],
) -> Iterator[tuple[int, list[ParsedJianpuPart]]]:
    """按 page_index 把连续的 part 分组，返回 (page_index, group)。

    F1 / F3 共用：多页文档中每页的声部是独立编号的，任何跨页比较都无意义。
    """
    index = 0
    while index < len(parts):
        page_index = parts[index].page_index
        end = index
        while end < len(parts) and parts[end].page_index == page_index:
            end += 1
        yield page_index, parts[index:end]
        index = end


def _part_marker_token(text: str, part_index: int) -> _Token:
    """第 part_index 个 @part 标记对应的 token（parts 与标记同序）。"""
    markers = list(_PART_MARKER_RE.finditer(text))
    match = markers[part_index] if part_index < len(markers) else None
    if match is None:
        return _Token(value="", line=1, column=1, start_utf16=0, end_utf16=0)
    return _marker_token(text, match.start(), match.end())
```

### 3.2 改写 `_validate_part_measure_counts`（432-446）

```python
def _validate_part_measure_counts(text: str, parts: list[ParsedJianpuPart]) -> None:
    for page_index, group in _iter_page_part_groups(parts):
        if len(group) <= 1:
            continue                      # 与 exec 层 len(scores) <= 1 对齐
        counts = [len(part.score.measures) for part in group]
        if len(set(counts)) <= 1:
            continue
        details = "、".join(
            f"{part.part_name or f'声部{part.part_index + 1}'}={counts[index]}"
            for index, part in enumerate(group)
        )
        prefix = f"第 {page_index + 1} 页" if len({p.page_index for p in parts}) > 1 else ""
        raise JianpuSyntaxError(
            _part_marker_token(text, group[0].part_index),
            f"{prefix}各声部小节数量不一致：{details}",
            severity="warning",
        )
```

要点：
- 只报**第一个**出问题的页（`raise` 直接中断），与现状一致，避免刷屏。
- 单页文档不加"第 N 页"前缀，保持消息向后兼容（现有断言用的是 `in`）。
- 锚点改为**出问题那一页的第一个 `@part` 标记**，不再是文档第一个。

### 3.3 给 `JianpuSyntaxError` 加 severity（76-97）

```python
def __init__(
    self,
    token: _Token,
    message: str,
    *,
    severity: SyntaxSeverity = "error",
) -> None:
    self.token = token
    self.severity = severity
    self.detail = message
    super().__init__(f"第 {token.line} 行第 {token.column} 列：{message}")

def diagnostic(self) -> SyntaxDiagnostic:
    ...
    return SyntaxDiagnostic(
        ...,
        severity=self.severity,      # ← 新增
        measure=self.token.measure,
    )
```

需从 `...models.syntax.schemas` 导入 `SyntaxSeverity`（`domain/` 可导入 `models/`，符合架构规则）。

---

## 4. F2 — `@page` 切断声部正文

**文件**：`backend/score_trans/domain/parse/jianpu_text.py` 的 `parse_jianpu_parts`

### 4.1 正文区间切到 page 边界（替换 668 行）

```python
end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
next_page = next(
    (pm.start() for pm in page_markers if start < pm.start() < end),
    None,
)
if next_page is not None:
    end = next_page
```

### 4.2 页眉归属下一个声部

被切下来的 `[end, markers[i+1].start())` 区间（page marker 行 + 页眉配置行）应前置到**下一个声部的正文**。

实现要点：**不能拼接字符串**（会破坏 UTF-16 偏移映射），而是把下一个声部的正文**起点前移**到页眉起点：

```python
# 循环外维护
pending_header_start: int | None = None

# 循环内，算出 start 之后：
if pending_header_start is not None:
    start = min(start, pending_header_start)
    pending_header_start = None

# 循环内，end 被 page 截断之后：
if next_page is not None:
    header_start = next_page
    newline = text.find("\n", header_start)
    pending_header_start = len(text) if newline < 0 else newline + 1
```

这样 `part_text = text[start:end]` 天然包含「page marker 行 + 页眉 + 原正文」，
`_strip_page_marker_lines` 会把 page marker 行清成等长空格 → **偏移与行号全部自动对齐**，
`base_utf16 = _utf16_length(text[:start])` 也自动正确。这是本方案改动最小的关键。

### 4.3 放宽 prefix 检查（626-632）

第一个 `@part` 之前的纯配置行（调号/拍号/tempo/title/instrument）应允许：

```python
_CONFIG_ONLY_LINE = re.compile(
    r"^(?:1\s*=\s*[A-Ga-g](?:bb|[#b])?|\d+\s*/\s*\d+"
    r"|(?:title|tempo|instrument|key|time)\s*=\s*\S.*)$"
)

def _is_config_line(stripped: str) -> bool:
    if not stripped or stripped.startswith("//"):
        return True
    return bool(_CONFIG_ONLY_LINE.match(stripped))
```

prefix 检查改为：剔除 page marker 行后，**存在非配置行**才报
`第一个分谱标记之前不能包含简谱正文`。

> 现有测试 `tests/test_syntax_validation.py:283` 用的 prefix 是 `1 2 |`（真正文），放宽后**仍然报错**，不受影响。

### 4.4 最后一个声部之后的页眉（v1 不处理）

若 `// @page N` 之后没有任何 `@part`，`pending_header_start` 无处归属 → v1 静默丢弃（保持现状）。
**F6（v2）会改成显式报错**。

---

## 5. F3 — 统一为「按页连续」编号

### 5.1 `ParsedJianpuPart` 新增字段（96-108）

```python
measure_number_base: int = 1   # 本声部在整篇文档中的连续起始小节号
```

带默认值 → 不破坏 `parse_jianpu_parts` 的其它调用方。

### 5.2 新增编号计算（三处复用同一份逻辑）

```python
def _assign_measure_number_bases(
    parts: list[ParsedJianpuPart],
    *,
    initial_measure_number: int = 1,
) -> None:
    """按页推进连续小节号：规则与 exec/render/actions.py:537-543 完全一致。

    每页取该页各声部「小节数（含 repeat_count）」的最大值累加；
    页内所有声部共用同一个起始号。
    """
    cursor = initial_measure_number
    for _page_index, group in _iter_page_part_groups(parts):
        span = max(
            (
                sum(measure.repeat_count for measure in part.score.measures)
                for part in group
            ),
            default=0,
        )
        for part in group:
            part.measure_number_base = cursor
        cursor += span
```

> 注意用 `sum(repeat_count)` 而不是 `len(measures)` —— 渲染路径用的是
> `sum(getattr(m, "repeat_count", 1) for m in score.measures)`，必须对齐。

### 5.3 警告侧：`_measure_duration_diagnostics`（344-391）

```python
measure_number = part.measure_number_base + (measure.display_number or measure_index) - 1
...
measure=str(measure_number),
```

### 5.4 错误侧：`_read_new_syntax` 感知声部边界

`_read_new_syntax` 现在在**整篇文档**上跑，`current_measure` 全程累计。改为接受可选的区间参数：

```python
def _read_new_syntax(
    text: str,
    measure_spans: list[tuple[int, int, int]] | None = None,
) -> tuple[JianpuOptions, list[_Token], list[str]]:
```

`measure_spans` 为 `(start_utf16, end_utf16, base)` 列表（升序、不重叠）。在逐行循环体开头同步：

```python
def _sync_measure_base(line_utf16_start: int) -> None:
    nonlocal current_measure, span_index
    if not spans:
        return
    while span_index < len(spans) and line_utf16_start >= spans[span_index][1]:
        span_index += 1
    if span_index < len(spans) and line_utf16_start >= spans[span_index][0]:
        current_measure = spans[span_index][2]
```

**为什么用行首偏移就够**：part 边界与 page 边界都出现在标记行之后，而标记行是 `//` 注释，
会被 `if not stripped: continue` 跳过 → 边界必然落在行首。

### 5.5 `validate_jianpu_text` 里的装配（230-316）

```python
normalized = text.lstrip("\ufeff")
diagnostics: list[SyntaxDiagnostic] = []
try:
    _validate_marker_structure(normalized)
    spans = _measure_number_spans(normalized)        # ← 新增
    _options, token_lines, _lyrics = _read_new_syntax(normalized, spans)
except JianpuSyntaxError as exc:
    ...
```

```python
def _measure_number_spans(text: str) -> list[tuple[int, int, int]]:
    """探测解析，算出每个声部段的连续起始号。解析失败时返回 []（退化为现状行为）。"""
    if not (
        _PART_MARKER_START_RE.search(text) or _PAGE_MARKER_START_RE.search(text)
    ):
        return []          # 无标记文档：整篇一段，base=1，等价于现状
    try:
        parts = parse_jianpu_parts(text)
    except (JianpuSyntaxError, ValueError):
        return []
    _assign_measure_number_bases(parts)
    return [
        (part.body_start_utf16, part.body_end_utf16, part.measure_number_base)
        for part in parts
    ]
```

拿到 `duration_parts` 之后（第 298 行）补一行：

```python
_assign_measure_number_bases(duration_parts)
```

**兼容性**：
- 无标记文档 → `spans == []` → 保持现状的全局累计计数。
  现有测试 `test_validate_jianpu_text_excludes_standalone_page_header_from_warning_range`
  断言 `measure == "3"`，不受影响（只有 `@page` 没有 `@part` → 单 part、base=1）。
- 探测解析失败 → `spans == []` → 退化为现状，随后第二轮 `parse_jianpu_parts` 会重新抛出同一个错误。

### 5.6 实施偏差说明（重要）

实施中发现一个方案未覆盖的边界：**文档本身有语法错误时 `parse_jianpu_parts` 会失败，
`spans` 返回空导致错误侧退化回全局累计 —— 而这恰恰是用户最需要正确小节号的场景**。

因此改为「**事后重打号**」架构：

1. `_read_new_syntax` **不再接受 `measure_spans` 参数**，保持产出整篇累计号。
2. `validate_jianpu_text` 在 token 流产出后调用 `_relabel_measure_numbers`：
   用 spans 把每个 token 的累计号改写为 `base + (累计号 - 段内首个累计号)`。
3. `_measure_number_spans` 分两条路径算 spans：
   - **准确路径**：`parse_jianpu_parts` 成功 → 用 `measure_number_base`；
   - **估算路径**（新增 `_estimate_measure_spans`）：解析失败 → 用
     `_part_bounds_from_markers`（仅依赖标记位置，复用 F2 的 @page 切断与页眉前移规则）
     分段，每段小节数取段内 token 累计号的极差 + 1，同样按页取最大值推进。
4. 错误侧与警告侧由此共用同一份分段表，天然一致。

效果：用例 G（第 2 页左手第 2/3 小节有非法 token）现在报第 3/4 小节（按页连续），
而不是原来的第 5/6 小节。

---

## 6. 需要同步的测试

| 文件 / 行 | 现状 | v1 调整 |
|-----------|------|---------|
| `tests/test_syntax_validation.py:301` | 断言 `line == 1`、消息含 `各声部小节数量不一致：a=2、b=1` | 消息断言仍成立（`in`）；**新增** `severity == "warning"` 断言 |
| `tests/test_syntax_validation.py:283` | prefix 为 `1 2 |`（真正文） | **不变**，放宽后仍报错 |
| `tests/test_api_routes.py:169` | `/render/batch-a4` 报 `各声部小节数量不一致` | **不变**，走 exec 层，v1 不改 |
| `tests/test_jianpu_measure_numbering.py` | 断言每页从 1 开始 | **不变**（那是 `parse_jianpu_score` 的 `display_number`，v1 不动它，只在诊断层加 base） |

**新增用例**（v1 必须补，对应第 2 节四个实测场景）：
- `test_page_grouped_measure_counts_accept_multi_page_single_part` → 用例 A，0 条诊断
- `test_page_header_config_belongs_to_next_page_part` → 用例 B/K，0 条诊断，第 2 页拿到 `2/4`
- `test_page_header_config_after_unterminated_measure` → 用例 C，0 条诊断
- `test_cross_page_measure_numbers_are_continuous` → 用例 G，小节号按页连续
- `test_part_measure_count_mismatch_is_warning` → 单页真不一致时仍报，但 `severity == "warning"`

跑测顺序：`python -m pytest tests/test_syntax_validation.py tests/test_jianpu.py tests/test_jianpu_measure_numbering.py tests/test_jianpu_anchors.py tests/test_rekey.py tests/test_export.py -q`，然后全量 `python -m pytest`，最后 `ruff format` + `ruff check`。

---

## 7. 风险与注意

1. **F2 会改变多页文档的解析结果**：第 2 页会真正拿到页眉里的 `2/4` / `1=G`，时值校验结果随之变化（从误报变正确，方向正确，但要留意历史快照对比测试）。
2. **F1 降级为 warning 后**，前端 `SyntaxDiagnosticPanel` 的「隐藏警告」开关会把它一起藏掉；错误计数、是否阻塞流程的行为会变。需确认这是你要的效果。
3. **`_read_new_syntax` 的 `current_measure` 仍然只是"数小节线"**，没有实现 `|:` / `:|` / `*N` 的空小节吞并规则。v1 只修「按页分段 + 起始号」，段内的相对推进误差仍在（例如 `1 2 3 4 :| *2 |` 这种反复结构）。这是**已知遗留**，建议记入 `docs/issues.md`，v2 再让 `_read_new_syntax` 复用 `flush_measure` 的推进逻辑。
4. **前端金样例**：`desktop/scripts/test-jianpu-page-sections.mjs` 与后端是两条独立实现。v1 的编号语义本来就与前端一致（都是按页连续），理论上前端**无需改动**；但仍应跑一次前端脚本确认。

---

## 8. 任务拆分

### v1（本次）
- T1 F1：按页分组校验 + 降级 warning + 锚点/消息改进
- T2 F2：`@page` 切断正文 + 页眉归属 + prefix 放宽
- T3 F3：`measure_number_base` + `_read_new_syntax` 区间感知 + 警告侧改号
- T4 补测试并跑全量 + ruff

### v2（后续，已拆出）
- T5 F4：更新 `docs/jianpu-syntax.md:368` 的 `start=auto` 过时写法；改进"未知属性"报错文案
- T6 F5：合并三处重复的小节数校验（parse 层 / exec 层 / MusicXML 侧缺口）
- T7 F6：页内缺 `@part` 时报错（用户已定：**报错**）
- T8 遗留：`_read_new_syntax` 的 `current_measure` 补齐反复结构（`|:`/`:|`/`*N`）的推进规则

---

## 9. v1 实施结果（2026-09-04）

**改动文件**：
- `backend/score_trans/domain/parse/jianpu_text.py`（+281/-18）
- `tests/test_syntax_validation.py`（+92：4 条新用例 + 1 条既有用例补 severity 断言）

**测试**：全量 `1011 passed, 1 skipped, 1 xfailed`；Ruff format + check 全绿。

**实测验证**（与 §2 的表格对照）：

| 用例 | v1 前 | v1 后 |
|------|-------|-------|
| A 单声部两页 | 误报 error | **0 条** |
| B/K 页眉配置+已收尾 | 2 条误报「少拍」+ 1 条误报 error | **0 条，第 2 页拿到 2/4** |
| C 页眉配置+未收尾 | 2 条误报 error 落在配置行 | **0 条** |
| G 多声部第 2 页报错 | 报第 5/6 小节 | **报第 3/4 小节**（按页连续） |

**遗留（v2）**：F4/F5/F6/T8 见 §8 任务拆分；其中 T8 的「反复结构推进规则」
会让 `1 2 3 4 :| *2 |` 这类段内编号仍有 1 小节误差，属已知且已声明。
