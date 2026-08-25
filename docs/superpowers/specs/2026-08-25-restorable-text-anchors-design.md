# 可恢复文本锚点设计

## 目标

用户编辑简谱导致某个来源锚点失效后，只要把相关文本恢复到识别基线，该来源元素就重新可点击并能精确定位。该能力必须跨保存、关闭和历史恢复保持一致。

## 已确认根因

当前 `trackTextAnchors()` 只基于相邻两次编辑增量移动锚点，并跳过 `valid: false` 的锚点。因此失效是不可逆的。保存流程又把编辑后的 `jianpu_text` 和当前锚点一起覆盖进历史页，原始锚点参照文本跨会话丢失。

## 核心设计

每页同时维护两组状态：

- 当前状态：`jianpuText`、`textAnchors`，用于当前编辑器和点击定位。
- canonical 基线：`textAnchorBaselineText`、`textAnchorBaselineAnchors`，仅在重新识别、重置或应用 OMR 修正产生新 canonical generation 时替换，普通用户编辑和保存不得修改。

每次用户编辑不再从上一轮锚点继续追踪，而是从 canonical 基线重新计算当前锚点。这样被删除或跨 token 重构的锚点可以失效，而文本恢复后相同基线范围会自然恢复为有效。

## 差异算法与偏移单位

抽出通用 Myers 最短编辑脚本，输入为序列。现有修正合并继续传入 `Array.from(text)` 的 Unicode 码点序列；锚点重算必须传入 `text.split('')` 的 UTF-16 码元序列，因为 `TextAnchor.start_utf16`、`end_utf16`、字符串 `slice()` 和 textarea selection 都使用 UTF-16 偏移。

算法保留 `MAX_EDIT_DISTANCE = 2048`。纯插入或纯删除走常量结构的快速路径，不受上限影响。一般 diff 超限返回 `null`：

- 修正文本合并维持现有整段替换回退，保持既有行为。
- 锚点重算保留上一轮锚点的完整状态，不从基线重置，也不批量失效。

基线到当前文本的编辑按起始位置倒序应用到基线锚点，复用现有单次编辑规则。因此多个离散编辑只影响各自覆盖的锚点，单 token 替换仍保留来源映射。

## 页面级集成

批次编辑器仍解析 `// @page` 段，但只对 `previousSection.body !== currentSection.body` 的页面重算。其他页不运行 diff。分页标记损坏导致页面段缺失时，当前页锚点全部标记失效，但 canonical 基线继续保留，待结构恢复后可重新计算。

识别结果的锚点最初相对后端 `result.jianpu_text`。前端会先把 `@text` 行剥离后的正文作为 canonical 文本，并用同一个 UTF-16 reconcile 将后端锚点一次性重定位到该正文，消除“`@text` 总在末尾”的隐含假设。

应用 OMR 标记修正时，`data.jianpu_text` 和 `data.text_anchors` 成为新的 canonical 基线；保留的用户编辑通过多段 UTF-16 diff 重算当前锚点，不再使用单段 prefix/suffix 追踪。

## 原图三态交互

原图来源元素分为三态：

1. 有效映射：存在于 canonical 基线且当前锚点有效，提供点击命中。
2. 失效映射：存在于 canonical 基线但当前锚点无效，不提供任何命中路径，避免误导提示。
3. 从未映射：不在 canonical 基线且不是设计上无锚点的结构符号，保留“未能进入识别结果”提示。

`ConvertView` 分别传递 `clickableSourceIds` 和 `mappedSourceIds`；`OriginalPreview` 的 disabled 层只包含第三态。

## 持久化契约

历史页新增：

- `text_anchor_baseline_text: str`
- `text_anchor_baseline_anchors: list[TextAnchor]`

SQLite schema 升至 v9。新建表和 v8→v9 迁移均增加两列，默认分别为 `''` 和 `'[]'`。旧记录加载时，前端以当前 `jianpu_text`/`text_anchors` 作为兼容基线；无法恢复升级前已经丢失的更早基线，但不会破坏现有记录。

`PageCreate`、`PageUpdate`、`BatchSavePage` 的新字段均为可选并默认 `None`，允许升级期间旧前端继续请求；`PageResponse` 字段非可选并提供空默认。创建/保存/更新链路显式贯通字段。`reorder_pages` 继续只更新 `position` 和当前 `jianpu_text`，不得覆盖基线列。

## 验收标准

- 删除一个有来源映射的 token 后来源元素不可点击；恢复原 token 后可再次点击并定位原范围。
- 多处离散编辑不会误杀中间未变化锚点。
- 含 emoji 等星面字符的文本前后编辑，锚点偏移仍按 UTF-16 正确。
- diff 超过 2048 时保留上一轮锚点状态。
- 只重算正文发生变化的页面。
- 失效映射不会显示“未能进入识别结果”的误导点击提示。
- 保存并恢复历史后仍能通过恢复文本恢复锚点。
- v8 数据库迁移到 v9，页面重排不改变基线列。

