# 歌词语法重构 — 修复方案

> **执行状态（2026-09-29）：全部完成 ✅**。B1–C1 四批次均已实施并验证：后端全量 pytest 1247 通过、Ruff 全绿；前端 vue-tsc/lint 通过、工具测试 288 项全过、`check:api-types` 通过。详见 [issues.md](issues.md) §〇。
>
> 实施期间的方案外发现：D2 让 `jianpuPageSections.ts`/`jianpuPlayback.ts` 新增对 `jianpuSyntax.ts` 的 import 后，5 个以 data-URL 内联编译模块的 Node 测试脚本（`test-jianpu-page-sections`/`test-history-save-payload`/`test-text-anchor-tracking`/`test-workspace-batch-cleanup`/`test-workspace-persistence`）需同步补充 `jianpuSyntax` 的依赖注入，已按各脚本既有模式修复。


## 一、问题总览

| 编号 | 严重度 | 问题 | 涉及文件 |
|------|--------|------|----------|
| B1 | **Bug** | 英文歌词以 `s`/`h`/`q`/`w` 开头时被截断 | `parse/jianpu_text.py:1294-1298` |
| B2 | **Bug** | `lyric_line_count` 对带换行符的行多算 1 | `write/jianpu_text.py:637` |
| B3 | **Bug** | 测试名与实际测试内容不匹配 | `tests/test_jianpu.py:723` |
| D1 | 设计 | `text.rfind("/")` 可能误匹配后续行的 `/` | 后端 1 处 + 前端 4 处 |
| D2 | 设计 | 前端歌词块定位逻辑重复 4 处 | `jianpuPageSections.ts`, `jianpuPlayback.ts` |
| D3 | 设计 | `JianpuEditor.vue` 每行重算 `lyricBlockLineIndexes` | `JianpuEditor.vue:297` |
| D4 | 设计 | `LyricLineSummary` 三个字段沦为死代码 | `schemas.py:31-33` |
| D5 | 设计 | `validate_jianpu_lyrics` 双重解析文本 | `parse/jianpu_text.py:352-354` |
| D6 | 设计 | `_split_lyric_block` 可能匹配注释中的 `/L:` | `rekey.py:186` |
| C1 | 清理 | 未追踪的调查目录 | `.pytest-lyrics-investigation-20260929/` |

---

## 二、问题详情与修复方案

### B1. 英文歌词以 `s`/`h`/`q`/`w` 开头时被错误截断

**调研结果**

`DURATION_PREFIXES` 定义了 5 个字母前缀（`jianpu_tokens.py:9-18`）：

```
w=4拍  h=2拍  q=1/2拍  s=1/4拍  d=1/8拍(及 dd,ddd…)
```

`consume_duration_prefix` 会把词项首字母当作时值前缀消耗。`_extract_lyric_blocks` 只对 `d` 开头的 ASCII alpha 词项做了保护（`jianpu_text.py:1297`），但 `s`/`h`/`q`/`w` 没有。实测：

```
"so"   → 解析为 "o"   + 1/4拍  (应: "so"   + 1拍)
"he"   → 解析为 "e"   + 2拍   (应: "he"   + 1拍)
"we"   → 解析为 "e"   + 4拍   (应: "we"   + 1拍)
"star" → 解析为 "tar" + 1/4拍  (应: "star" + 1拍)
"do"   → 正确 ("do" + 1拍)    (d 特判生效)
```

中文歌词不受影响（非 ASCII）。`qf`/`qs`（微音程前缀）已由 `duration_prefix` 的 `_ACCIDENTAL_PREFIXES_STARTING_WITH_DURATION` 检查排除，不受影响。

**修复方案**

将 `d` 特判扩展到所有 5 个时值前缀字母：

```python
# jianpu_text.py:1294-1298, 替换为:
duration, word = consume_duration_prefix(raw_word)
# w/h/q/s/d 既是时值前缀又是常见英文歌词词首。
# qf/qs 已被 duration_prefix 排除，不会到达这里。
if (
    word
    and word.isascii()
    and word.isalpha()
    and raw_word[0] in "whqsd"
):
    duration, word = Fraction(1), raw_word
```

**新增测试**

```python
def test_lyric_words_starting_with_duration_letters_are_preserved() -> None:
    score = parse_jianpu_score("1=C\n4/4\n1 2 3 4 |\n/L: so he we star/")
    blocks = [
        (b.text, b.duration)
        for m in score.measures
        for b in m.text_blocks
        if b.role == "lyric"
    ]
    assert blocks == [
        ("so", Fraction(1)), ("he", Fraction(1)),
        ("we", Fraction(1)), ("star", Fraction(1)),
    ]
```

**涉及文件**: `backend/score_trans/domain/parse/jianpu_text.py`, `tests/test_jianpu.py`

---

### B2. `lyric_line_count` 对带换行符的行多算 1

**调研结果**

```python
# write/jianpu_text.py:637
lyric_line_count = sum(line.count("\n") + 1 for line in lines if "/L:" in line)
```

`lines = text.splitlines(keepends=True)` 返回的每个元素含换行符。`line.count("\n")` 对带 `\n` 的行为 1，贡献 `1+1=2`，但实际只占 1 行。已验证：

```
文本 "1 2 3 4 |\n/L: 春 风/"     → lyric_line_count = 1  ✓ (末行无 \n)
文本 "1 2 3 4 |\n/L: 春 风/\n"  → lyric_line_count = 2  ✗ (应 1)
```

当前调用链中 `_score_to_jianpu_text` 返回的文本不以 `\n` 结尾，所以不触发。但 `_text_anchors_raw` 被测试直接调用（`test_jianpu_anchors.py:141`），未来也可能被外部调用。

`lyric_line_count` 用于计算 `first_measure_line = len(lines) - len(measures) - tempo_line_count - lyric_line_count`（`:658`），多算 1 会导致锚点行偏移。

**修复方案**

```python
# write/jianpu_text.py:637, 替换为:
lyric_line_count = sum(1 for line in lines if "/L:" in line)
```

**涉及文件**: `backend/score_trans/domain/write/jianpu_text.py`

---

### B3. 测试名与实际测试内容不匹配

**调研结果**

```python
# tests/test_jianpu.py:723
def test_lyric_verse_zero_is_rejected() -> None:
    with pytest.raises(JianpuSyntaxError, match="缺少结束符"):
        parse_jianpu_score("1=C\n4/4\n1 2 3 4 |\n/L: 春")
```

旧测试检查 `L0:` 被拒绝（段号从 1 开始）。新语法不再有段号概念，测试改为检查"缺少结束符"，但函数名未更新。

**修复方案**

```python
def test_lyric_block_without_terminator_is_rejected() -> None:
    with pytest.raises(JianpuSyntaxError, match="缺少结束符"):
        parse_jianpu_score("1=C\n4/4\n1 2 3 4 |\n/L: 春")
```

**涉及文件**: `tests/test_jianpu.py`

---

### D1. `text.rfind("/")` 可能误匹配后续行的 `/`

**调研结果**

后端 `_extract_lyric_blocks`（`:1179`）和前端 4 个文件都用"全文最后一个 `/`"定位歌词块结束符。如果歌词块结束后、后续行中有 `//` 注释，`rfind` 会找到注释中的 `/`，导致：

- 后端报"歌词正文不能包含保留符号 /"（实际问题是歌词块后面有内容）
- 前端 mask 范围扩大到注释行

安全性不受影响（都会报错或 mask），但错误信息误导用户。

**修复方案（后端）**

在 `_extract_lyric_blocks` 中，优先在同一行内找结束符：

```python
# jianpu_text.py:1178-1179, 替换为:
# 优先在同一行内搜索结束符，避免误匹配后续行的 //
newline_after_start = text.find("\n", start_match.end())
same_line_limit = newline_after_start + 1 if newline_after_start >= 0 else len(text)
end = text.rfind("/", start_match.end(), same_line_limit)
if end < 0:
    end = text.rfind("/")  # 同一行没有，回退全文搜索（会触发跨行检查）
```

**修复方案（前端）**

在 `jianpuSyntax.ts` 的 `lyricBlockLineIndexes` 和 `maskJianpuLyricBlocks` 中应用同一逻辑，然后由 D2 的重构让其他文件复用：

```typescript
// jianpuSyntax.ts, 新增辅助函数
function findLyricBlockRange(text: string): { start: number; end: number } {
  const start = text.indexOf('/L:')
  if (start < 0) return { start: -1, end: -1 }
  const lineEnd = text.indexOf('\n', start + 3)
  const searchLimit = lineEnd >= 0 ? lineEnd : text.length
  let end = text.lastIndexOf('/', searchLimit)
  if (end < start + 3) end = text.lastIndexOf('/')  // 回退全文
  return { start, end }
}
```

`lyricBlockLineIndexes` 和 `maskJianpuLyricBlocks` 改用 `findLyricBlockRange`。

**涉及文件**: `backend/score_trans/domain/parse/jianpu_text.py`, `desktop/src/renderer/src/utils/jianpuSyntax.ts`

---

### D2. 前端歌词块定位逻辑重复 4 处

**调研结果**

| 文件 | 位置 | 当前状态 |
|------|------|----------|
| `jianpuSyntax.ts:20-41` | `lyricBlockLineIndexes` / `maskJianpuLyricBlocks` | 公共函数（定义者） |
| `jianpuPageSections.ts:378-386` | `walkJianpuMeasures` 内联 | 重复 |
| `jianpuPageSections.ts:631-642` | `jianpuGutterLabels` 内联 IIFE | 重复 |
| `jianpuPlayback.ts:254-258` | `findJianpuNoteSpans` 内联 | 重复 |

后三处复制了相同的 `indexOf('/L:')` + `lastIndexOf('/')` + `split('\n')` 逻辑。

**修复方案**

1. 在 `jianpuSyntax.ts` 中确保 `lyricBlockLineIndexes` 和 `maskJianpuLyricBlocks` 使用 D1 的 `findLyricBlockRange`（已暴露为 public）。

2. `walkJianpuMeasures` 替换内联为：

```typescript
import { lyricBlockLineIndexes } from './jianpuSyntax'
// ...
const lyricLines = lyricBlockLineIndexes(normalized)
```

3. `jianpuGutterLabels` 删除 IIFE，替换为：

```typescript
const lyricLines = lyricBlockLineIndexes(normalized)
```

4. `findJianpuNoteSpans` 替换内联 mask 为：

```typescript
import { maskJianpuLyricBlocks } from './jianpuSyntax'
// ...
text = maskJianpuLyricBlocks(text)
```

**涉及文件**: `desktop/src/renderer/src/utils/jianpuSyntax.ts`, `desktop/src/renderer/src/utils/jianpuPageSections.ts`, `desktop/src/renderer/src/utils/jianpuPlayback.ts`

---

### D3. `JianpuEditor.vue` 每行重算 `lyricBlockLineIndexes`

**调研结果**

```typescript
// JianpuEditor.vue:297 (在 computed .map 回调内)
if (lyricBlockLineIndexes(props.modelValue).has(lineIndex)) {
  return [{ text: line, type: 'lyrics' as const }]
}
```

`highlightedLines` 的 `computed` 对每行调用 `lyricBlockLineIndexes(props.modelValue)`，每次重建整个 Set。对于 N 行文本，计算 N 次相同的 Set。

**修复方案**

提取到 `computed` 内部、`map` 之前，只算一次：

```typescript
// 在 highlightedLines computed 内部, map 之前:
const lyricLines = lyricBlockLineIndexes(props.modelValue)
// 在 map 回调中:
if (lyricLines.has(lineIndex)) { ... }
```

**涉及文件**: `desktop/src/renderer/src/components/JianpuEditor.vue`

---

### D4. `LyricLineSummary` 三个字段沦为死代码

**调研结果**

`schemas.py:31-33` 定义了 `available_notes`/`missing_words`/`extra_words`，但 `validate_jianpu_lyrics` 硬编码为 `None`/`0`（`jianpu_text.py:365-367`）。前端 grep 确认仅在 `openapi.ts`（自动生成）中引用，无组件使用。

旧语法按音符顺序对齐歌词，所以能计算"可用音符数"和"缺失/多余歌词数"。新语法按小节对齐，这些概念不再适用。

**修复方案**

1. 从 `LyricLineSummary` 移除三个字段：

```python
# schemas.py
class LyricLineSummary(BaseModel):
    verse: int
    words: int
```

2. 更新 `validate_jianpu_lyrics` 简化构造：

```python
summaries.append(LyricLineSummary(
    verse=line.verse,
    words=word_count,
))
```

3. 更新测试（删除对这些字段的断言，已有部分测试在 diff 中做了）。

4. **移除前端死代码**:`JianpuEditor.vue:197-200` 引用了这三个字段（条件 `line.available_notes !== null` 永远为 false，因为后端硬编码为 None)。需要删除这段代码，否则移除字段后 TypeScript 编译会报错：

```typescript
// JianpuEditor.vue:194-203, 替换为:
const lyricSummary = computed(() => syntaxStore.lyrics.map((line) => {
  const label = line.verse === 1 ? 'L' : `L${line.verse}`
  return `${label}: ${line.words} ${t('components.syntaxDiagnosticPanel.lyricWords')}`
}).join('　·　'))
```

同时需要检查 `components/SyntaxDiagnosticPanel.vue` 和 `stores/syntaxDiagnostics.ts` 是否有类似引用。已确认无其他组件使用这些字段，但 i18n 翻译文件（`i18n/locales/zh-CN/components.ts:118-120` 和 `i18n/locales/en-US/components.ts:120-122`）保留了 `lyricNotes`/`lyricMissing`/`lyricExtra` 翻译键。这些键在移除死代码后不再使用，建议一并清理。

5. 运行 `pnpm generate:api-types` 更新前端 `openapi.ts`，然后运行 `pnpm check:api-types` 确认契约一致。

**涉及文件**: `backend/score_trans/models/syntax/schemas.py`, `backend/score_trans/domain/parse/jianpu_text.py`, `tests/test_syntax_validation.py`, `desktop/src/renderer/src/components/JianpuEditor.vue`, `desktop/src/renderer/src/i18n/locales/zh-CN/components.ts`, `desktop/src/renderer/src/i18n/locales/en-US/components.ts`, `desktop/src/renderer/src/models/openapi.ts`（自动生成）

---

### D5. `validate_jianpu_lyrics` 双重解析文本

**调研结果**

```python
# jianpu_text.py:352-354
options, token_lines, lines = _read_new_syntax(text)  # 第一次: _extract_lyric_blocks
score = parse_jianpu_score(text)                        # 第二次: 内部再调 _read_new_syntax
```

文本被完整解析两次，`_extract_lyric_blocks` 执行两次。

**修复方案**

直接调用 `_parse_score_tokens`，复用第一次解析的结果：

```python
def validate_jianpu_lyrics(text: str) -> tuple[list[LyricLineSummary], list[SyntaxDiagnostic]]:
    try:
        normalized = text.lstrip("\ufeff")
        options, token_lines, lines = _read_new_syntax(normalized)
        score = _parse_score_tokens(options, token_lines, lines)
    except (JianpuSyntaxError, ValueError):
        return [], []
    # ... 后续不变
```

`_parse_score_tokens` 有 `title=None` 和 `initial_tempo=DEFAULT_TEMPO` 默认值，签名兼容。注意：`parse_jianpu_score` 内部也做 `normalized = text.lstrip("\ufeff")`，所以需要保持 BOM strip。

**涉及文件**: `backend/score_trans/domain/parse/jianpu_text.py`

---

### D6. `_split_lyric_block` 可能匹配注释中的 `/L:`

**调研结果**

```python
# rekey.py:186
start = text.find("/L:")  # 字面匹配，不检查行首
```

`// /L: test` 注释中的 `/L:` 会被匹配。但 `rekey_text` 开头 `parse_jianpu_score(text)` 会先校验语法，有语法错误的文本会返回 `parse_error`，不会到达 `_split_lyric_block`。所以安全性不受影响，但逻辑不够健壮。

**修复方案**

```python
def _split_lyric_block(text: str) -> tuple[str, str]:
    start = text.find("/L:")
    if start < 0:
        return text, ""
    # 确保 /L: 在行首（前面只有空白），避免匹配注释中的 /L:
    line_start = text.rfind("\n", 0, start) + 1
    if text[line_start:start].strip():
        return text, ""
    return text[:start], text[start:]
```

**涉及文件**: `backend/score_trans/domain/rekey.py`

---

### C1. 未追踪的调查目录

**调研结果**

`.pytest-lyrics-investigation-20260929/` 是 pytest 的临时缓存目录（含 test_a4_content_scale_preserve0 等），出现在 `git status` 的 Untracked files 中。

**修复方案**

在 `.gitignore` 中添加：

```
.pytest-*/
```

**涉及文件**: `.gitignore`

---

## 三、实施顺序

```
第 1 批（后端 Bug，互相独立，可并行）:
  B1  英文歌词截断        — jianpu_text.py + test_jianpu.py
  B2  lyric_line_count    — write/jianpu_text.py
  B3  测试名              — test_jianpu.py

第 2 批（后端设计改进，依赖 B1/B2 完成）:
  D1  rfind 脆弱性(后端)  — parse/jianpu_text.py
  D4  死字段              — schemas.py + jianpu_text.py + test_syntax_validation.py
  D5  双重解析            — parse/jianpu_text.py（与 D1 同函数，顺序应用）
  D6  _split_lyric_block — rekey.py

第 3 批（前端，依赖 D1 后端完成）:
  D1  rfind 脆弱性(前端)  — jianpuSyntax.ts
  D2  重复逻辑            — jianpuPageSections.ts + jianpuPlayback.ts
  D3  Editor 性能         — JianpuEditor.vue

第 4 批（清理）:
  C1  .gitignore
  D4  pnpm generate:api-types
```

---

## 四、验证步骤

每个批次完成后执行：

```bash
# 后端
PYTHONPATH=backend python -m pytest tests/test_jianpu.py tests/test_render.py tests/test_rekey.py tests/test_convert.py tests/test_syntax_validation.py tests/test_live_preview.py tests/test_architecture.py -q
.venv/Scripts/python.exe -m ruff check --fix backend/ tests/
.venv/Scripts/python.exe -m ruff format backend/ tests/

# 前端
cd desktop && npx vue-tsc --noEmit && pnpm lint && node scripts/test-jianpu-page-sections.mjs

# D4 完成后额外步骤
cd desktop && pnpm generate:api-types && pnpm check:api-types
```

---

## 五、风险评估

| 修复 | 风险 | 缓解 |
|------|------|------|
| B1 | 歧义场景 `qstar` 偏向保留原文 | 与 `d` 行为一致；用户可用 `q0 star` 显式分离前缀和歌词 |
| D1 | 跨行歌词块回退到全文搜索 | 回退逻辑保持原有行为，后续 `"\n" in body` 检查仍生效 |
| D4 | **前端 `JianpuEditor.vue:197-200` 引用这三个字段**（但条件永远为 false，是死代码） | 移除字段前必须同步删除 `JianpuEditor.vue` 中的引用和 i18n 翻译键；`openapi.ts` 自动生成 |
| D5 | `_parse_score_tokens` 无 recovery 参数 | `validate_jianpu_lyrics` 不传 recovery，行为与 `parse_jianpu_score` 一致 |

---

## 六、正面确认（无需修复）

以下经审查确认无问题：

- **`renderer.py`** 的 `replace(event, lyric=None, lyrics={})` 修复正确 — `measure_event_layout`（`geometry.py:475-481`）确实把歌词 ink 加入 box，去掉后 bottom 只反映音符 ink
- **`_apply_lyrics`** 的 `allow_truncated` 在 recovery 模式下正确处理截断谱面，`next(..., None)` 有 default 防止 StopIteration
- **MusicXML 往返**正确：`event.lyrics` → `<lyric number=verse>` → `event.lyrics[verse]`
- **live preview** segment 分割正确：歌词块总在最后一个 segment（`_segments` 最后一个 `end=len(text)`）
- **masked text** 保持偏移不变（逐字符替换为空格），设计正确
- **语法验证**全面：空块/多块/跨行/旧语法/保留符号/trailing content 均有检查
- **rekey 拼接**歌词块保留了前导 `\n`，往返正确
- **`consume_duration_prefix`** 对中文歌词（非 ASCII）不受影响
- **空拍** `q0`/`d0` 等正确处理
- **`d` 前缀特判**逻辑正确（覆盖 "do"/"re"/"dream" 等）
- **多流 `&` 对齐**和**小节 `|` 对齐**逻辑正确

---

## 七、方案验证结果

以下验证均通过 Python/Node 脚本实际执行确认：

| 修复 | 验证结果 | 备注 |
|------|----------|------|
| B1 | ✅ 通过 | `so`/`he`/`we`/`star`/`do`/`dream`/`ddream` 均保留为完整歌词；`qf`/`qs` 不受影响；单字母前缀正确报错 |
| B2 | ✅ 通过 | `sum(1 for ...)` 修复后，有/无末尾换行均返回 1 |
| D1 | ✅ 通过 | 优先同一行搜索后，`/L: 春 风/\n// comment` 正确找到歌词块的 `/`(end=17）而非注释的 `/`(end=20) |
| D2 | ✅ 可行 | `walkJianpuMeasures`/`jianpuGutterLabels`/`findJianpuNoteSpans` 的内联逻辑与 `lyricBlockLineIndexes`/`maskJianpuLyricBlocks` 功能等价，可安全替换 |
| D3 | ✅ 可行 | 提取 `lyricBlockLineIndexes` 到 `computed` 内部、`map` 之前，只算一次 |
| D4 | ⚠️ **需调整** | 发现 `JianpuEditor.vue:197-200` 引用这三个字段（但为死代码），需同步删除；i18n 翻译键也需清理 |
| D5 | ✅ 通过 | `_read_new_syntax` + `_parse_score_tokens` 与 `parse_jianpu_score` 结果完全一致（`score1 == score2` 为 True) |
| D6 | ✅ 通过 | 注释中的 `/L:` 被拒绝（start=-1)，行首空白被接受 |
