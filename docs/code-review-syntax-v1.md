# 代码审查报告 — 语法检查小节号修复 v1（F1+F2+F3）

> 审查时间：2026-09-04
> 审查范围：工作区未提交改动（`backend/score_trans/domain/parse/jianpu_text.py` +281/-18，`tests/test_syntax_validation.py` +92）
> 基线：全量 `1011 passed, 1 skipped, 1 xfailed`；`test_architecture.py` 11 passed；Ruff format + check 全绿

---

## 总体评价：方向正确、实现扎实，可合并

这次改动精准命中了用户报的三个缺陷（跨页误报、页眉归属、三套编号），几个关键设计决策都对：

- **F2 用"起点前移"而非"拼接字符串"**——这是整个方案最妙的一步。`part_text = text[start:end]` 天然包含「page marker 行 + 页眉 + 原正文」，靠 `_strip_page_marker_lines` 的等长空格替换，UTF-16 偏移和行号**自动对齐**，`_remap_part_syntax_error` 的行号换算也因此不用动。实测 T1（第 2 页错误 + 页眉占 2 行）行号、小节号都正确。
- **F3 的「事后重打号」架构是实施中的正确纠偏**——原方案让 `_read_new_syntax` 内联接受 spans，但"文档有语法错误时 `parse_jianpu_parts` 失败"恰恰是用户最需要正确号号的场景。改成 `_relabel_measure_numbers` 事后改写，并让准确路径/估算路径共用同一份分段表，错误侧和警告侧天然一致。这个偏差在 `docs/syntax-measure-numbering-fix-plan.md` §5.6 里有如实记录。
- **F1 的 `_iter_page_part_groups` 注释**把"为什么跨页比较无意义"讲清楚了（每页每声部独立编号），是 F1/F3 共用的正确抽象。
- 4 条新测试精准对应实测场景 A/B/C/G，既有用例的兼容性也逐一核对过（`in` 断言、prefix 真正文仍报错、exec 层不受影响）。

---

## 需要处理的问题

### 🟡 P2 — 估算路径在反复结构下的小节号会偏差，且**传染后续页**（建议记录，v2 处理）

`_estimate_measure_spans`（解析失败时的降级路径）用段内 token 累计号的极差估算小节数：

```python
page_counts.append(max(inside) - min(inside) + 1 if inside else 0)
```

但 `_read_new_syntax` 的累计号会被 `*N` 干扰，且方向不一致：

| 反复写法 | 累计号行为 | 极差估算 vs 准确 `sum(repeat_count)` |
|----------|-----------|--------------------------------------|
| `1 2 3 4 :| *2 |`（backward） | `*2` 推进 +1 | 极差 = 3，**高估 1** |
| `1 2 3 4 *3 |`（forward） | `*3` 不推进 | 极差 = 1，**低估 2** |

没有简单的"排除/不排除 `*N` token"能同时修正两者。实测 T2：

```text
// @page 1 ... // @part 1 name="A"
1=C / 4/4 / 1 2 3 4 :| *2 |        ← 准确：1 小节，repeat_count=2
// @page 2 ... // @part 1 name="A"
1=C / 4/4 / 2 3 4 8 |              ← 8 触发语法错误 → 走估算路径
```

准确：第 1 页 span = 2 → 第 2 页起始号 = 3，`8` 应报**第 3 小节**。
实际：估算把第 1 页 span 算成 3 → `8` 报**第 4 小节**。

**影响范围**：仅限"语法错误 + 反复结构"同时出现的文档，且误差只影响错误之后的页。错误本身的**行号、列号、高亮区间仍正确**，只是小节号偏大。

**建议**：v2 的 T8（补齐 `_read_new_syntax` 的反复推进规则）落地后，让估算路径改数小节线而非用极差。v1 可接受，但应在 `docs/issues.md` 标注。

### 🟢 P3 — `_measure_number_spans` 的异常捕获比第 2 轮解析窄（建议顺手修）

```python
try:
    parts = parse_jianpu_parts(text)
except (JianpuSyntaxError, ValueError):
    parts = []
```

只捕获两种异常。虽然实际只会抛这两种，但 `validate_jianpu_text` 第 2 轮的 `parse_jianpu_parts` 调用有 `except Exception` 兜底（约 274 行，注释明确写"防止内部错误逃逸成 HTTP 500"）。这里应该对齐，避免未来 `parse_jianpu_parts` 引入新异常类型时探测路径逃逸成 500：

```python
except Exception:  # noqa: BLE001 — 与第 2 轮解析的兜底对齐
    parts = []
```

### 🟢 P3 — 多页文档会被完整解析两遍（建议 v2 优化）

`_measure_number_spans`（准确路径）调一次 `parse_jianpu_parts`，`validate_jianpu_text` 第 2 轮又调一次（`duration_text`）。可接受，但可把第一次的 `parts` 复用传下去，省一次完整解析。

### 🟢 P3 — 切分逻辑现在有三份了（v2 F5 记得收编）

F2 之后，"@page 切断 + 页眉前移"的切分逻辑出现在两处：`parse_jianpu_parts` 和 `_part_bounds_from_markers`。加上 F5 原本要合并的"三处小节数校验"，v2 的合并工作时要把这份也一并收编，避免漂移。

### 🟢 P3 — 变量命名误导（既有，本次被放大）

`validate_jianpu_text` 里的 `token_lines` 实际是扁平 `list[_Token]`（`_read_new_syntax` 返回的 `tokens`），这是**既有**命名。但现在它被 `_relabel_measure_numbers(token_lines, ...)` 使用，误导性被放大。建议改名 `flat_tokens`。

---

## 边界用例实测（本次 review 补充验证）

| 用例 | 结果 | 判定 |
|------|------|------|
| T1 第 2 页真实错误 + 页眉占 2 行 | `line=10`、第 3 小节 | ✅ 正确 |
| T2 第 1 页反复 + 第 2 页错误 | 报第 4 小节（准确第 3） | ⚠️ 估算路径偏差，即上面的 P2 |
| T3 无标记 + 反复 | 第 4 小节，与 v1 前一致 | ✅ 既有遗留，非本次引入 |
| 用例 A/B/C/G（方案实测场景） | 全部符合预期 | ✅ |

---

## 结论

**可以合并。** 三个 P0 缺陷全部修复，测试覆盖到位，架构合规。

> **处理决策（2026-09-04，用户拍板）**：P3 异常兜底已顺手修复（`_measure_number_spans` 与第 2 轮解析对齐 `except Exception`）；P2 已记入 `docs/issues.md` R7；其余 P3（重复解析、切分逻辑三份、`token_lines` 命名）保留为 v2 优化项。

- P2（估算路径反复结构偏差）：已记入 `docs/issues.md` R7，v2 随 T8 一并处理
- P3（异常兜底）：**已修复**
- 其余 P3：均为 v2 的优化项，不阻塞
