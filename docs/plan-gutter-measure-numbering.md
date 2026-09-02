# 方案 A 完整设计：gutter 小节号对齐小节线语义

> 状态：设计稿，待实施
> 日期：2026-09-02
> 关联问题：简谱文本编辑器在单行内继续写 `|` 后，左侧 gutter 小节号与实际渲染小节号漂移

## 1. 背景与根因

项目内存在两套小节计数算法：

| 位置 | 算法 | 依据 |
|---|---|---|
| 后端解析 / SVG 渲染 | 按**小节线 token** 切分，每个 Measure 一个号，按 `repeat_count` 推进 | `backend/score_trans/domain/parse/jianpu_text.py` `_read_new_syntax` + `flush_measure`；`services/render/engraving/renderer.py` `_assign_score_measure_numbers` |
| 前端 gutter | 按**含 `|` 的行**计数，每行 +1（行尾 `*N` 则 +N） | `desktop/src/renderer/src/utils/jianpuPageSections.ts` `jianpuGutterLabels` / `jianpuMeasureCount` |

单行多小节（如 `1 2 3 4 | 2 3 4 5 |`）在后端是合法语法且正确解析为 2 个小节，
但前端 gutter 只给该行标 1 个号，且**后续所有行号与页摘要（P1 “5-8”）全部漂移**。

## 2. 目标与非目标

**目标**
1. gutter 行号语义与后端解析/渲染完全一致（按小节线计数）。
2. 单行多小节时 gutter 显示区间（如 `5-6`），后续行号恢复正确。
3. 页摘要 `jianpuPageSummaries` 的小节数同步修正。
4. 保持现有输入体验：`|` 自动换行的软引导逻辑（`JianpuEditor.onInput`）不动。

**非目标**
- 不改后端、不改简谱语法、不禁止单行多小节。
- 不处理 `\p |` 这类极端边界的 ±1 漂移（见 §7 风险）。

## 3. 语义规范（移植目标）

渲染小节号的**真值来源**是 `parse_jianpu_score` 的 flush 逻辑 +
`_assign_score_measure_numbers` 的推进规则。核心规则如下。

### 3.1 行级预处理（与 `_read_new_syntax` 对齐）

对每一行（先归一化换行）：

1. `// @page N ...` → 页边界：先收尾 flush，再重置页状态；gutter 显示 `P{N}`。
2. `// @part N name="..."` → part 边界：先收尾 flush，`measureNumber` 重置为
   本页起始号（多 part 并行编号，渲染器按页取各 part 最大跨度推进）；gutter 无标签。
3. 剥离行内注释（`//` 起，含 `$` 内联不特判——与现有 `splitInlineComment` 一致）。
4. 剥离行首小节标签：`272:`（冒号分隔任意数字）或 `10.`（点号分隔且数字 >7）。
   规则与后端 `_strip_leading_measure_label` 一致；行内同类 token（`123:`）同样跳过。
5. `L:` 歌词行、metadata 行（`title=`、`tempo=`、`instrument=`、`1=X`、纯 `\d+/\d+`）
   → 不产生内容、不计数、无标签。

### 3.2 行内 token 切分

使用与后端相同的核心正则（`jianpuSyntax.ts` 的 `TOKEN_PATTERN` 已等价）：

```
/\s+|\$[^$]*\$|\|\||\|:|:\||\||[^\s|]+/g
```

### 3.3 跨行状态机

```
state = {
  measureNumber        // 下一个待分配的小节号
  hasContent           // 自上次 flush 以来是否出现内容 token
  pendingRepeat        // *N 紧跟内容后：下一次 flush 的小节占 N 个号
  skipEmpty            // 上一边界是 :| ：下一次空 flush 跳过
  afterRepeatStart     // 上一边界是 |: ：抑制 backward *N
  repeatAppliedBackward // 刚做过 backward *N：下一次空 flush 整个吞掉（不计数）
  lastAdvance          // 上一个已计数小节占用的号数（backward *N 时要覆盖它）
}
```

**内容 token** = 音符/休止/和弦/连音等；排除：小节线、`*N`、行内调号 `1=X`、
拍号 token、metadata、空白 token。（与后端 `current_events/current_blocks` 非空的语义对齐。）

> 空白陷阱：`jianpuSyntax.ts` 的 `TOKEN_PATTERN` 含 `\s+` 分支（高亮需要保留空白），
> walker 若直接复用会把每个空格当内容 token。**walker 必须自己写正则，不含 `\s+`**：
> `/\$[^$]*\$|\|\||\|:|:\||\||[^\s|]+/g`

### 3.4 token 处理规则

| token | 动作 |
|---|---|
| `|`、`||` | **flush**：① 有内容 → 计 1 个小节，advance = `pendingRepeat`；② 无内容且 `repeatAppliedBackward` → **整个吞掉，不计数**（清 `repeatAppliedBackward`）；③ 无内容且 `skipEmpty` → 不计数；④ 无内容且非 `skipEmpty` → 计 1 个小节（整小节休止，advance=1）。flush 后 `hasContent=false`、`pendingRepeat=1`、`skipEmpty=false`。**记录该行关闭的小节号区间** |
| `|:` | flush（仅有内容才计数，advance=`pendingRepeat`）；`afterRepeatStart=true` |
| `:|` | flush（仅有内容才计数，advance=`pendingRepeat`）；`skipEmpty=true`；repeat_end 标记不影响计数 |
| `*N` | 无内容 且 已有小节 且 非 `afterRepeatStart` → **backward**：`advance += N - lastAdvance`（覆盖上一小节的反复次数，不是简单 +N-1）；`repeatAppliedBackward=true`；否则 → `pendingRepeat=N` |
| 其他内容 token | `hasContent=true`；`repeatAppliedBackward=false` |
| 行结束 | 状态跨行保留（小节可跨行） |
| 页/part/EOF 结束 | 若 `hasContent` → 收尾 flush 计最后一个小节；**该号的标签挂在最后一个内容 token 所在行**（与中段跨行小节"标签在关闭行"的观感一致） |

> 规则 ② 是 `flush_measure` 里 `repeat_applied_backward` 的早退分支
> （`jianpu_text.py` 793-799 行），典型触发：`1 2 3 4 :\| *2 \|` 中 `*2` 之后的那个 `\|`。
> 规则 `*N` 用 `N - lastAdvance` 而非 `N-1`，因为 backward 是**覆盖**上一小节的
> `repeat_count`（`previous.repeat_count = repeat_count`），不是叠加。

### 3.5 gutter 标签规则

- 单小节行：`5`
- 多小节行：`5-6`（首-末）；若格式化后超过 7 字符（如 `100-163`）→ 显示 `100+`，CSS 截断兜底
- 页标记行：`P{n}`（不变）
- 其他行：空（不变）
- 行号 class 判定 `!label.startsWith('P')` 对区间串依然成立，无需改模板逻辑

## 4. 代码改动清单

### 4.1 `desktop/src/renderer/src/utils/jianpuPageSections.ts`（核心）

新增内部函数 `walkJianpuMeasures(text, initialMeasureNumber)`：

```ts
interface MeasureWalkLine {
  firstMeasure: number | null  // 该行承载的首个小节号
  lastMeasure: number | null   // 该行承载的末个小节号
}
interface MeasureWalkResult {
  lines: MeasureWalkLine[]
  pages: Array<{
    firstMeasureNumber: number
    measureCount: number          // max-across-parts（保留现有语义）
    markerLineIndex: number
    inputFileName: string
    pageNumber: number
  }>
}
```

- 单次遍历同时产出 gutter 标签与页摘要数据，消除 `jianpuMeasureCount` 与
  `jianpuGutterLabels` 两份重复实现。
- token 正则**直接内联在本文件**（约 5 行），不 import `./jianpuSyntax`——
  否则测试 harness 需要额外内联模块（见 §6 坑 1）。

公开 API 保持签名不变：

- `jianpuGutterLabels(text, initialMeasureNumber)` → 由 walk 结果映射为
  `'' | 'P{n}' | '{n}' | '{a}-{b}' | '{a}+'`
- `jianpuPageSummaries(text, initialMeasureNumber)` → 由 walk 的 `pages` 映射
- `jianpuMeasureCount(text)` → 保留导出（walk 的单页计数），语义更新

### 4.2 `desktop/src/renderer/src/components/JianpuEditor.vue`（UI）

- `.editor-gutter` 宽度 `42px → 56px`（容纳 `10-11` 等 5 字符 + 6px 右内边距）。
- 模板与 TS 逻辑**零改动**（`measureLabels` computed 消费同一函数签名）。

### 4.3 不改动的文件

- `backend/**`：不动。
- `JianpuEditor.vue` 的 `onInput` 自动换行、`jianpuSyntax.ts`、播放/高亮逻辑。

## 5. 行为变化对照（需在测试中固定）

| 场景 | 旧行为 | 新行为 |
|---|---|---|
| `1 2 3 4 \| 2 3 4 5 \|` 单行 | 标 `1`，后续漂移 | 标 `1-2`，后续正确 |
| `1 2 3 4 *3 \|`（前向反复） | 该行 +3 | 该行 +3（不变） |
| `1 2 3 4 \| *3`（后向反复） | 该行 +3 | 该行 +3（不变） |
| `\|: 1 2 3 4 :\|` | 标 1 | 标 1（不变） |
| `1 2 3 4 :\| *2 \|`（backward 后空小节） | 占 2 个号 | 占 1 个号（repeat=2）（对齐后端 `repeat_applied_backward` 吞并） |
| `1 2 *2 \| *3`（backward 覆盖已有反复） | `+= 3-1` | `+= 3-2`，总计 3（覆盖而非叠加） |
| `:|` 后独立 `\|` 行（空小节） | 占 1 个号 | 跳过（对齐后端 skipEmpty） |
| 孤立 `\|` 行（非 `:|` 后、非 `*N` 后） | 占 1 个号 | 占 1 个号（整小节休止，不变） |
| 末小节无 barline（`... 1 2 3 4` EOF） | 不计数、无标签 | 计数并入页摘要；标签挂最后内容行 |
| 页摘要 P1 “5-8” | 多小节行时偏小 | 修正 |
| `* 3`（带空格） | 前端接受 | 不再接受（对齐后端 `\*\d+`） |

## 6. 实现注意事项（坑）

1. **测试 harness 模块内联**：`test-jianpu-page-sections.mjs` 用
   `ts.transpileModule` 直接编译并 import `jianpuPageSections.ts`。新代码若
   import 其他 util（如 `./jianpuSyntax`），必须像 `textDiff.ts` 那样在测试脚本里
   重写 import 为 data URL。**规避**：token 正则内联在 `jianpuPageSections.ts`。
2. **`*N` 空格形式**：旧实现 `\*\s*(\d+)` 允许空格；新实现用后端规则 `\*\d+`。
   检查现有测试是否依赖空格形式，若有则更新断言。
3. **性能**：每次 keystroke 全量 walk，O(文本长度)，与现状同阶，无回归风险。
4. **多 part 编号**：`// @part` 重置为**本页起始号**（不是全局连续），与渲染器
   `_assign_display_measure_numbers` 的按页并行编号一致；页跨度取各 part 最大值
   （保留现有 `Math.max(0, ...partCounts)` 语义）。
5. **页边界 = 收尾 flush**：`// @page` 出现时先把上一页的悬空小节 flush 掉
   （后端每页独立 parse，末尾有 final flush，见 `parse_jianpu_score` 末尾
   `if current_events or current_blocks ... flush_measure()`）。
6. **双重遍历**：`jianpuGutterLabels` 与 `jianpuPageSummaries` 是 Vue 里两个独立
   computed，同一段文本会被 walk 两次。加一个模块级 memo（key = 文本 + 起始号，
   只缓存最近一次结果）即可，无需改 API。
7. **part 模型已核实**：`parse_jianpu_parts` 中每个 part 的文本止于下一个 `// @part`
   标记，而每页都会重新从 `@part 1` 起编，因此 part 天然按页切分；渲染器
   `_assign_display_measure_numbers` 也按页让各 part 从同一号并行编号、页跨度取各 part
   最大值。方案沿用该模型（后端另有 `_validate_part_measure_counts` 要求各 part 小节数
   一致，合法输入下 max 恒等于任一 part）。

## 7. 风险与取舍

- **TS 复刻 vs 后端真值的长期漂移（主要风险）**：walker 是 `_read_new_syntax`/
  `flush_measure` 的简化复刻，两端各自演化就会漂移；本方案把复刻面收窄到 7 条规则，
  但仍是唯一的高风险点。缓解：§8.1 双向锚定金样例（后端 pytest + 前端 node test 同一组
  样例），任一侧语义变化都会先红一侧测试；用户可见后果仅限 gutter 显示，
  不影响渲染/播放/导出。
- **残余 ±1 边界**：`\p |`（力度标记独占一小节）、谱首孤立 `*N` 等罕见写法，
  walker 与后端可能差 1；可接受，不为此增加状态复杂度。
- **区间标签宽度**：7 字符截断为 `100+`，gutter 56px 下不溢出。
- **“一行写完整谱”**：gutter 显示 `1-64`，导航价值低但数值正确；现有 `|` 自动
  换行软引导保证正常输入仍是一行一小节，可接受。

## 8. 测试计划

`desktop/scripts/test-jianpu-page-sections.mjs` 新增用例（沿用现有
`node:test` + transpile-import 模式）：

1. 单行多小节：`1 2 3 4 | 2 3 4 5 |` → `1-2`，下一行从 3 开始。
2. 区间显示：跨 initialMeasureNumber（如起始 5 → `5-6`）。
3. 前向反复：`1 2 3 4 *3 |` 行占 3 个号。
4. 后向反复：`1 2 3 4 | *3` 行占 3 个号。
5. 反复结构：`|: 1 2 3 4 :|` + 下一行 `| 5 6 7 8 |`（skipEmpty 生效，后者标 2）。
6. 末小节无 barline：计数入页摘要、标签挂最后内容行。
7. **backward 吞并**：`1 2 3 4 :| *2 |` → 只占 1 个号（旧实现占 2）。
8. **backward 覆盖**：`1 2 *2 | *3` → 总计 3 个号（非 1+2+3）。
9. `// @page` + `// @part` 混合：part 重置、页跨度取 max。
10. 行内注释、行首 `272:` 标签剥离。
11. 孤立 `|` 行（整小节休止）占号；`:|` 后孤立 `|` 不占号。
12. 超长区间截断：构造 >99 小节的行 → `1+` 形式。
13. 回归：现有全部用例通过（尤其是 `filter(Boolean)` 的数量断言，374/426 行附近——
    末小节开始计号会新增标签，数量断言需同步更新）。

新增用例必须覆盖上面三处语义缺口（backward 吞并、backward 覆盖、末小节无 barline）。

**实施顺序建议：先写 §8.1 的金样例（后端侧实测取数 → 前端侧断言），再写 walker。**
金样例同时充当需求规格，能避免"照着自认为的规则实现、实现完才发现规则记错"。

### 8.1 双向锚定金样例（防止 TS 复刻与后端长期漂移）

walker 是后端语义的复刻，两端都可能各自演化。做法是**同一组金样例在两侧各写一份断言**：

1. 样例集（覆盖反复结构，建议 5-8 条）：
   - `1 2 3 4 | 2 3 4 5 |`、`1 2 3 4 | 2 3 4 5 | 3 4 5 6 |`（单行多小节）
   - `1 2 3 4 *3 |`、`1 2 3 4 | *3`（前向/后向反复）
   - `|: 1 2 3 4 :| | 5 6 7 8 |`、`1 2 3 4 :| *2 |`（反复 + 空小节吞并）
   - `1 2 *2 | *3`（backward 覆盖）
   - `1 2 3 4 |` + 末行无 barline
   - `// @page` + `// @part` 混排
2. **后端锚**：新增 `tests/test_jianpu_measure_numbering.py`，对每条样例断言
   `parse_jianpu_score(...)` 后各 measure 的 `display_number` 序列与 `repeat_count`。
   后端语义若变，这里先红。
3. **前端锚**：`test-jianpu-page-sections.mjs` 用**完全相同的样例文本**断言 gutter
   标签序列与页摘要。前端 walker 若漂，这里红。
4. 两侧样例文本放在注释里互相指认（`tests/` ↔ `desktop/scripts/`），改动一边时必须同步另一边。

## 9. 验收步骤

```bash
cd desktop
pnpm test:utils          # 含新增用例
pnpm lint
pnpm typecheck
```

手工验收（`pnpm dev`）：

1. 编辑器输入 `1 2 3 4 | 2 3 4 5 |`（禁止自动换行干扰：粘贴整行）→ gutter 显示 `1-2`，下一行从 3 开始。
2. 渲染 SVG，比对 gutter 号与 SVG 小节号一致。
3. 含 `|: :| *N` 的谱子页摘要范围正确。
4. 暗色主题下 gutter 宽度无溢出、无换行。

## 10. 实施顺序与规模

| 步骤 | 内容 | 预估 |
|---|---|---|
| 1 | `jianpuPageSections.ts`：实现 `walkJianpuMeasures` 并重写三个公开函数 | ~150 行 |
| 2 | `JianpuEditor.vue`：gutter 宽度 56px | 1 行 CSS |
| 3 | 测试：新增 §8 用例 + 更新受影响旧断言 | ~20 个断言 |
| 4 | 验收：test:utils / lint / typecheck / 手工 | — |

一个专注批次可完成；无后端改动、无 API 契约变化、无数据迁移。
