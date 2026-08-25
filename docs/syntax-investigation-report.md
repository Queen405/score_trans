# 简谱语法渲染与编辑 —— 代码逻辑调研报告

> 本报告基于对项目全部语法相关代码的逐行阅读，梳理"简谱文本语法"的**实际**解析、序列化与渲染逻辑。
> 报告用途：用于比照并更新现有语法说明（`desktop/src/renderer/src/views/SyntaxView.vue`），后者已落后于代码。
>
> 关键代码位置：
> - 解析器：`backend/score_trans/domain/parse/jianpu_text.py`（1264 行，核心）
> - 时值 token：`backend/score_trans/domain/jianpu_tokens.py`（161 行）
> - 演奏标记定义：`backend/score_trans/domain/performance_marks.py`（743 行）
> - 常量（力度/微音程/调号）：`backend/score_trans/domain/constants.py`
> - 音高序列化（写回文本）：`backend/score_trans/domain/accidentals.py`
> - 文本序列化器：`backend/score_trans/domain/write/jianpu_text.py`（733 行）
> - 数据模型：`backend/score_trans/models/score.py`
> - 渲染引擎：`backend/score_trans/services/render/engraving/`（renderer.py 1899 行 + geometry/style/scene/svg_backend/fonts/qa）
> - 前端语法高亮：`desktop/src/renderer/src/utils/jianpuSyntax.ts`
> - 前端编辑器：`desktop/src/renderer/src/components/JianpuEditor.vue`
> - 前端渲染预览：`desktop/src/renderer/src/components/PublicationPreview.vue`
> - 前端语法说明（待更新）：`desktop/src/renderer/src/views/SyntaxView.vue`

---

## 一、谱面元信息（文档头部）

### 1.1 支持的字段

代码在 `_read_new_syntax()` 中逐行解析头部，规则如下（`jianpu_text.py:546-640`）：

| 语法 | 含义 | 解析规则 |
|------|------|----------|
| `1=C` | 调号 | 正则 `1\s*=\s*([A-G](?:#|b)?)`，值必须是合法音名 |
| `4/4` | 拍号 | 正则 `\d+/\d+`，分子分母都必须 > 0 |
| `title=名称` | 谱名 | `key=value` 形式，`title` 键 |
| `tempo=120` | 速度（BPM） | `tempo=` 后接整数 |
| `instrument=erhu` | 乐器模式 | 值必须属于 `ACCEPTED_INSTRUMENT_PROFILES`，否则报错 |

### 1.2 乐器模式

`models/common/types.py:8-25`：

- **支持的 4 种**：`general`（普通）、`erhu`（二胡）、`ruan`（阮）、`guzheng`（古筝）
- **别名**：`zhongruan`（中阮）会被 `normalize_instrument_profile()` 归一化为 `ruan`
- **接受值**（`ACCEPTED`）：上述 4 种 + `zhongruan`
- 不支持的值会抛出 `ValueError`，提示可用模式

### 1.3 头部位置约束

- 调号 `1=` 和拍号 `\d+/\d+` 只在**首个谱面 token 之前**作为头部字段生效（`saw_score_tokens` / `saw_key` / `saw_time` 标志）。
- 一旦出现音符等谱面 token，后续行中的 `1=G` 或 `3/4` **不再被当作头部字段**，而是被当作**普通 token** 加入 token 流——这就是"中途转调/变拍"的机制（见第六节）。
- `title=`、`tempo=`、`instrument=` 没有此限制，但实际使用中通常写在头部。

### 1.4 已废弃写法

- 代码**不再支持** `key=C` 或 `time=4/4` 形式。`_read_new_syntax` 中对 `key=` / `time=` 的处理已被移除。
- 现有语法说明中仍提到 `key=C / time=4/4` 为"已废弃写法"，但代码实际不会解析它们——遇到 `=` 且 key 不是 `1`/`title`/`tempo`/`instrument` 的行，会被当作普通 token 流处理。

### 1.5 BOM 与空白

- 文本开头的 BOM (`\ufeff`) 会被 `lstrip` 移除（`parse_jianpu_score` 第 282 行、`parse_jianpu_parts` 第 173 行）。

---

## 二、音符与音高

### 2.1 音级

`_parse_pitch()`（`jianpu_text.py:1031-1092`）：

- **音级数字** `1`–`7`：分别对应 do、re、mi、fa、sol、la、si。
- **休止符** `0`：在 `_parse_event_token` 中单独处理，`work == "0"` 时创建 `kind="rest"` 事件。
- 不在 `1`–`7`/`0` 范围内的值会抛出语法错误，提示使用新语法。

### 2.2 八度记号

- **高八度**：在数字后加撇号 `'`，如 `1'`。多个撇号 = 多个八度（`1''` = 高两个八度）。
- **低八度**：在数字后加逗号 `,`，如 `1,`。多个逗号 = 多个八度。
- 八度值 = `'` 的数量 − `,` 的数量。
- 八度记号**只能后置**（在数字之后）。代码先统计 `'`/`,`，再 `replace` 移除。

### 2.3 变音记号

`_parse_pitch()` 支持的变音记号（`jianpu_text.py:1031-1092`）及 `constants.py`：

#### 前缀变音（在数字之前）

| 前缀 | 含义 | alter 值 |
|------|------|----------|
| `tqf` | 四分之三降 | -3/2 |
| `tqs` | 四分之三升 | +3/2 |
| `qf` | 四分之一降（半降） | -1/2 |
| `qs` | 四分之一升（半升） | +1/2 |
| `bb` | 重降 | -2 |
| `x` | 重升 | +2 |
| `n` 或 `♮` | 还原 | 0 |
| `#` | 升 | +1 |
| `b` | 降 | -1 |

- 微音程前缀（`tqf`/`tqs`/`qf`/`qs`）优先匹配，按长度从长到短。
- **还原号 `n` 和 `♮` 只能前置**（后缀没有 `n`/`♮` 的匹配分支）。

#### 后缀变音（在数字/八度之后）

`_parse_pitch()` 在处理完前缀后，再检查剩余值的**后缀**（`jianpu_text.py:1063-1078`）：

| 后缀 | 含义 |
|------|------|
| `bb` | 重降 |
| `x` | 重升 |
| `#` | 升 |
| `b` | 降 |

- **后缀变音会覆盖前缀变音**的 `accidental` 和 `accidental_text` 值。
- 后缀不支持微音程和还原号。
- 序列化器 `pitch_to_token()`（`accidentals.py:21-28`）默认将变音记号写在数字**之前**（前缀形式），八度记号写在数字**之后**。

### 2.4 变音模式（AccidentalMode）

`accidentals.py` + `models/common/types.py`：

- `auto`（默认）：保持原始拼写
- `sharp`：尽量用 `#` 表示，并尝试转换到等价音级
- `flat`：尽量用 `b` 表示，并尝试转换到等价音级
- 微音程（分母 ≠ 1 的 alter）不受 sharp/flat 模式影响，始终保持原样。

### 2.5 音高排序（和弦内）

- `JianpuPitch.rank = octave * 10 + degree + accidental * 0.1`（`score.py:58-59`）。
- 和弦内音高按 `rank` **降序**排列（高音在上）。

---

## 三、时值与节奏

### 3.1 时值前缀

`jianpu_tokens.py:8-26`，`DURATION_PREFIXES` 字典：

| 前缀 | 时值（拍） | 说明 |
|------|-----------|------|
| `w` | 4 | 全音符 |
| `h` | 2 | 二分音符 |
| _无_ | 1 | 四分音符（默认） |
| `q` | 1/2 | 八分音符 |
| `s` | 1/4 | 十六分音符 |
| `d` | 1/8 | 三十二分音符 |
| `dd` | 1/16 | 六十四分音符 |
| `ddd` | 1/32 | 一百二十八分音符以内…… |
| `dddd` | 1/64 | |
| `ddddd` | 1/128 | 每多一个 `d` 缩短一半 |

- 前缀按**长度从长到短**匹配（`_DURATION_PREFIXES_LONGEST_FIRST`）。
- **特殊规则**：`qf` 和 `qs` 开头的 token 会被当作微音程前缀而非时值前缀（`_ACCIDENTAL_PREFIXES_STARTING_WITH_DURATION`，`jianpu_tokens.py:43`）。`duration_prefix()` 遇到这两个开头直接返回空字符串。

### 3.2 附点

`consume_duration_suffix()`（`jianpu_tokens.py:118-134`）：

- **后缀附点** `.`：每个 `.` 将时值延长原时值的一半。`dotted_duration(base, n) = base * (2 - 1/2^n)`。
- 附点可叠加：`5..` = 附两点 = 原时值 × 1.75。
- **关键约束**：如果在时值前缀之后、音级之前出现 `.`，会抛出错误（`_parse_event_token` 第 1001-1005 行）：附点必须写在音级**之后**，例如 `h4'.` 合法但 `h.4'` 非法。

### 3.3 延长线（增时线）

- **后缀减号** `-`：每个 `-` 延长一拍（即增加 `Fraction(1)`）。
- 可叠加：`1--` = 四分音符 + 2 拍 = 3 拍。
- 序列化时（`duration_affixes`），超过 1 拍的整数部分用 `-` 扩展。

### 3.4 延音线（Tie）

`_parse_event_token()`（`jianpu_text.py:984-1028`）：

- **后缀 `~`**：`tie_start`（延音线起点），如 `1~`。
- **前缀 `~`**：`tie_stop`（延音线终点），如 `~1`。
- 两者可组合：`~1~` 表示既是上一音的终点又是下一音的起点。
- **跨小节自动传播**：如果一个音有 `tie_start`，下一个音即使没有写 `~` 也会自动获得 `tie_stop`（`append_event` 第 421-426 行的 `open_tie` 逻辑）。

### 3.5 连音线（Slur）

`_parse_event_token()`：

- **前缀 `(`**：`slur_start`，如 `(1`。
- **后缀 `)`**：`slur_stop`，如 `1)`。
- 组合：`(1 2)` 实际是 `(1` + 空格 + `2)`，即第一个音 slur_start，最后一个音 slur_stop。
- 跨小节时，连音线会延续到下一行（`_OpenSpanners` + `_finish_spanners` + `_start_spanner_continuations`）。

### 3.6 时值可表示性

- `is_notatable_duration()`：判断时值是否可表示（分母必须是 2 的幂）。
- `safe_duration_affixes()`：对不可精确表示的时值，寻找最接近的可表示近似值。

---

## 四、连音组（Tuplet）

`_parse_tuplet_token()`（`jianpu_text.py:714-829`）及辅助函数。

### 4.1 基本语法

- 用 `$...$` 包裹，如 `$123$`。
- **紧凑写法**（无空格）：`$123$` → 自动拆分为 `1`、`2`、`3`。
- **空格分隔**：`$1 2 3$` → 按空格拆分。
- 拆分逻辑由 `_split_tuplet_body()` 处理：有空白则 `split()`，无空白则用紧凑模式正则 `_COMPACT_TUPLET_EVENT_PATTERN` 逐个匹配。

### 4.2 紧凑模式正则

`jianpu_text.py:879-895`：

```
紧凑音高:   (?:tqf|tqs|qf|qs|bb|x|n|♮|#|b)?[1-7][',]*(?:bb|x|#|b)?
紧凑音符/休止: (?:tqf|tqs|qf|qs|bb|x|n|♮|#|b)?[0-7][',]*(?:bb|x|#|b)?
紧凑和弦:    \[紧凑音高(?:+紧凑音高)+\]
紧凑事件:    ~?\(?(?:[whqs]|d+)?(?:紧凑和弦|紧凑音符/休止)\.*-*\)?~?
```

### 4.3 显式比例

- `$3:2;s1 s2$`：`实际数:常规数;` 前缀，用分号分隔。
- 每个音的最终时值 = `原始时值 × (常规数 / 实际数)`。

### 4.4 隐式比例

无显式比例时：

1. 如果组内有任何音带时值前缀（`has_explicit_duration`），则 `actual_count = tuplet_duration_unit_count(...)`，`normal_count = _tuplet_normal_notes(actual_count)`。
2. 否则 `actual_count = 音符个数`，`normal_count = _tuplet_normal_notes(actual_count)`。
- `_tuplet_normal_notes(n)` = 不超过 n 的最大 2 的幂（如 3→2, 5→4, 7→4, 6→4）。
- 无显式比例时每个音的时值 = `1 / actual_count`。

### 4.5 连音组内标记

- **独立标记**（单独一个 part）：`^mark` 或 `\dynamic`，作用于后续音符。
- **内联标记**（与音符同 part）：`^mark音符`，如 `^.1`。
- `_consume_tuplet_inline_marks()` 提取前缀标记，剩余部分作为事件体。
- 连续滑音 `^lh` 在连音组内作为 `__slide_from_previous__` 特殊标记处理。

### 4.6 约束

- 连音组不能为空（`_parse_tuplet_token` 第 790-791 行）。
- 无显式比例时至少需要 2 个音符（第 792-793 行）。
- 比例必须是正整数。

---

## 五、和弦

`_parse_event_token()`（`jianpu_text.py:1007-1016`）：

- 语法：`[音高+音高+...]`，如 `[1+3+5]`。
- 用 `+` 分隔各音高。
- 和弦不能为空（`[]` 会报错）。
- 时值前缀适用于整个和弦：`q[1+3+5]`。
- 音高在解析后按 `rank` 降序排列（高音在前/上）。
- 连音线/延音线/连音线记号可包裹和弦：`([1+3+5]`、`[1+3+5]~`。

---

## 六、小节结构与重复

### 6.1 小节线

`parse_jianpu_score` 主循环（`jianpu_text.py:434-531`）：

| Token | 含义 | 处理 |
|-------|------|------|
| `\|` | 小节线 | `flush_measure()`，结束当前小节 |
| `\|\|` | 终止线/双小节线 | `flush_measure()`，结束当前小节 |
| `\|:` | 反复起点 | `flush_measure()` + 设 `next_repeat_start=True` |
| `:\|` | 反复终点 | `flush_measure()` + 给上一小节设 `repeat_end=True` |

### 6.2 重复小节

- `*N`：设置当前小节的 `pending_repeat_count = N`（至少 1）。
- 正则 `re.fullmatch(r"\*\d+", raw)`。
- 小节号增量 = `repeat_count`（`parse_jianpu_score` 第 540-542 行）。

### 6.3 中途转调与变拍

- `1=G` 作为 token 出现在谱面流中时，会被 `_key_signature_value()` 识别，更新 `current_key`。
- `3/4` 作为 token 出现时，会被 `_time_signature_value()` 识别，更新 `current_beats` / `current_beat_type`。
- **约束**：调号和拍号必须写在**当前小节音符之前**（`current_events` 为空时），否则报错（第 438-453 行）。

### 6.4 小节号标签（行首标签剥离）

`_strip_leading_measure_label()`（`jianpu_text.py:674-684`）：

- 行首形如 `数字.` 或 `数字:`/`：` 的标签会被剥离（如 `1. | 1 2 3 |` → `| 1 2 3 |`）。
- **例外**：如果 `数字.` 中数字 ∈ 0-7 且后面只有空/`|`/`||`/`|:`/`:|`，则**不剥离**（当作普通音符处理）。
- `_is_measure_label_token()` 也用于在 token 流中跳过纯标签 token。

### 6.5 小节验证

`_normalize_parsed_measure()`（`jianpu_text.py:1099-1120`）：

- 计算小节实际时值与目标时值（`beats_per_measure × 4 / beat_type`）。
- 少拍时记录 `validation_errors`：`"小节少拍：实际 X，目标 Y"`。
- 超拍时记录：`"小节超拍：实际 X，目标 Y"`。
- 按拍分配事件到 `measure.beats`。

---

## 七、力度标记

### 7.1 全部力度记号

`constants.py:80-97`，`DYNAMICS` 集合（16 种）：

```
p, pp, ppp, pppp, mp, mf, f, ff, fff, ffff, sf, sfz, sfp, fp, fz, rfz
```

### 7.2 语法

- 前缀 `\`：如 `\p`、`\f`、`\sfz`。
- 解析：`raw.startswith("\\")`，取其后部分，必须在 `DYNAMICS` 集合中（第 491-498 行）。
- 不支持的力度会报错，提示使用 `\p`、`\mp`、`\f`、`\ff` 等。
- 力度标记是**前置型**：写在音符之前，作用于紧随其后的音符。
- 在连音组内也可使用（`_tuplet_standalone_mark` + `_consume_tuplet_inline_marks`）。

---

## 八、演奏标记（Performance Marks）

### 8.1 标记体系

`performance_marks.py` 定义了 `PerformanceMark` dataclass，关键字段：

- `id`：规范 ID（全局唯一）
- `token`：语法 token（如 `>`、`lh`、`lg`）
- `category`：`articulation` / `ornament` / `technical` / `spanner`
- `renderer`：渲染器名称（决定图形）
- `placement`：`above` / `left` / `right` / `below-right`
- `profiles`：适用的乐器模式元组
- `measure_scope`：是否可作为小节级标记
- `target`：`pitched`（单音）或 `chord`（必须和弦）
- `syntax`：示例语法字符串

### 8.2 语法形式

- **前置标记**：`^token`，写在音符前，如 `^>1`、`^.1`。
- **小节级标记**：`(^token)`，写在小节开头，如 `(^l)`，对该小节所有音符生效。
- **内联标记**：`^token音符`，如 `^.1`（与音符紧贴）。
- **连续滑音**：`^lh` 写在目标音前，连接前一个音。

### 8.3 全部标记清单

#### 通用标记（general）

| token | id | 类别 | 渲染图形 | 小节级? |
|-------|-----|------|---------|---------|
| `>` | accent | articulation | `>` | 是 |
| `-` | tenuto | articulation | `—` | 否 |
| `.` | staccato | articulation | `●`（实心圆） | 是 |
| `r` | trill-mark | articulation | `tr` | 是 |
| `f` | fermata | articulation | `𝄐` | 是 |

#### 颤弓/轮指/摇指（erhu/ruan/guzheng 专用）

| token | id | 类别 | 渲染图形 | 小节级? |
|-------|-----|------|---------|---------|
| `l` | tremolo | ornament | `≋`（三斜线） | 是 |

- `l` 在 general 模式下**不推荐使用**（`recommended_in_general=False`）。

#### 连线滑音（erhu/ruan/guzheng）

| token | id | 类别 | 说明 |
|-------|-----|------|------|
| `lh` | continuous-slide | spanner | 连接前一个音与目标音；古筝模式自动判断上/下滑 |

- 语法：`3 ^lh 5`（`^lh` 放在目标音前）。
- 古筝模式约束：只能连接两个单音，不能连接和弦；起止音高不能相同。

#### 二胡专用标记（erhu）

| token | id | 类别 | 渲染图形 | placement | target |
|-------|-----|------|---------|-----------|--------|
| `lg` | down-bow | technical | `Π` | above | pitched |
| `tg` | up-bow | technical | `∨` | above | pitched |
| `pg` | throw-bow | technical | （自定义） | above | pitched |
| `1`-`4` | fingering-N | technical | 数字本身 | above | pitched |
| `zr` | natural-harmonic | technical | `○` | above | pitched |
| `rg` | artificial-harmonic | technical | `◇` | above | pitched |
| `bx` | pluck | technical | `+` | above | pitched |
| `sh` | scoop | technical | 短上扬弧 | left | pitched |
| `xh` | plop | technical | 短下落弧 | left | pitched |
| `dh` | finger-pad-slide | technical | 交叠短弧 | right | pitched |
| `ds` | doit | technical | 长上扬线 | right | pitched |
| `dx` | falloff | technical | 长下落线 | right | pitched |
| `hx` | lower-return-slide | technical | 下回钩 | right | pitched |
| `hs` | upper-return-slide | technical | 上回钩 | right | pitched |
| `sc` | upper-trill | ornament | 短上邻音波 | above | pitched |
| `xc` | lower-trill | ornament | 下折点短波 | above | pitched |
| `kx` | open-string | technical | `0` | above | pitched |
| `nx` | inner-string | technical | `内` | above | pitched |
| `wx` | outer-string | technical | `外` | above | pitched |
| `jx` | breath-mark | articulation | `，` | above | pitched |
| `gx` | hook-string | technical | 短竖钩 | above | pitched |

#### 阮/古筝共用标记

| token | id | 类别 | 渲染图形 | placement | target |
|-------|-----|------|---------|-----------|--------|
| `sx` | string-sweep | technical | 三横档斜箭 | right | pitched |
| `zr` | natural-harmonic | technical | `○` | above | pitched |
| `py` | arpeggio | technical | `∿`（竖波浪） | left | **chord** |

#### 古筝专用标记（guzheng）

| token | id | 类别 | 渲染图形 | placement | target |
|-------|-----|------|---------|-----------|--------|
| `sy` | guzheng-sweep-tremolo | technical | 成组短回钩 | above | pitched |
| `st` | guzheng-double-tuo | technical | 双折钩 | above | **chord** |
| `sm` | guzheng-double-mo | technical | 平行短斜线 | above | **chord** |
| `bq` | guzheng-board-front-flower | technical | 小花形 | above | pitched |
| `zb` | guzheng-on-beat-flower | technical | 八向花形 | above | pitched |
| `sg` | guzheng-ascending-scrape | technical | 右上箭头 | right | pitched |
| `xg` | guzheng-descending-scrape | technical | 右下箭头 | right | pitched |
| `cy` | guzheng-vibrato | technical | 三段短波 | above | pitched |
| `zs` | guzheng-ornament-up-slide | technical | 紧凑上行折钩 | right | pitched |
| `zx` | guzheng-ornament-down-slide | technical | 紧凑下行折钩 | right | pitched |
| `sh` | scoop | technical | 短上扬弧 | left | pitched |
| `xh` | plop | technical | 短下落弧 | left | pitched |

#### 阮专用标记（ruan）

| token | id | 类别 | 渲染图形 | placement | target |
|-------|-----|------|---------|-----------|--------|
| `zy` | ornament-note | ornament | 小型装饰音 | above | pitched |

### 8.4 小节级标记

`_measure_level_mark()`（`jianpu_text.py:1162-1172`）：

- 语法：`(^token)`，写在小节第一个音符/休止符之前。
- 只有 `measure_scope=True` 的标记可用：accent `>`、staccato `.`、trill `r`、fermata `f`、tremolo `l`。
- 当前小节已有音符时不能使用（第 481-485 行）。
- 不支持的标记会报错，提示可用 `(^l)`、`(^.)`、`(^>)`、`(^r)`、`(^f)`。

### 8.5 乐器校验

`_validate_instrument_mark_target()`（`jianpu_text.py:1220-1243`）：

- 仅对 `guzheng` 和 `ruan` 模式校验。
- 标记后必须跟随音符（不能跟休止符）。
- `target="chord"` 的标记后必须跟和弦（如 `^st [3+5]`）。

### 8.6 标记归类与去重

`normalize_event_marks()`（`performance_marks.py:637-675`）：

- 将 `articulation`/`ornament`/`technical` 三类标记分别归类。
- `spanner` 类（如 `continuous-slide`）不进入事件标记列表。
- 通过 `canonical_mark_id()` 支持别名归一化（如 `harmonic` → `natural-harmonic`）。

---

## 九、分谱标记（多声部）

`parse_jianpu_parts()`（`jianpu_text.py:168-274`）：

### 9.1 语法

```
// @part 1 name="声部名称"
（声部 1 的简谱正文）
// @part 2 name="声部 2"
（声部 2 的简谱正文）
```

- 正则：`^[ \t]*//[ \t]*@part[ \t]+(\d+)[ \t]+name=("(?:\\.|[^"\\])*")[ \t]*$`
- 名称是 **JSON 字符串**（双引号包裹，内部引号需转义 `\"`）。
- 序号必须**从 1 开始连续**递增。

### 9.2 约束

- 第一个 `@part` 标记之前不能包含简谱正文（第 214-215 行）。
- 标记格式无效会报错，提示正确格式。
- 名称不是有效 JSON 字符串会报错。

### 9.3 渲染

- 多声部时，渲染器在系统左侧绘制花括号/方括号（`system-bracket`）。
- 每个声部左侧显示声部名称。
- 声部间用 `part_gap` 间距分隔。

---

## 十、分页标记（多页输入）

`parse_jianpu_parts()` + `_find_page_markers()`（`jianpu_text.py:107-157`）：

### 10.1 语法

```
// @page 1
（第 1 页简谱正文）
// @page 2 name="原始文件名.pdf"
（第 2 页简谱正文）
```

- 正则：`^[ \t]*//[ \t]*@page[ \t]+(\d+)(?:[ \t]+name=("(?:\\.|[^"\\])*"))?[ \t]*$`
- `name` 可选，是 JSON 字符串，表示原始输入文件名。
- 序号必须**从 1 开始连续**递增。

### 10.2 与分谱标记的组合

- `@page` 标记可以出现在 `@part` 标记之间。
- 每页内的 `@part` 序号在该页内从 1 重新计数。

### 10.3 前端处理

`jianpuPageSections.ts`：

- `parseJianpuPageMarker()`：解析单行分页标记。
- `parseJianpuPageSections()`：将全文按 `@page` 标记拆分为多个 section。
- `jianpuPageSummaries()`：计算每页的小节号范围。
- `jianpuGutterLabels()`：为编辑器行号槽生成标签（`P1`/`P2`... 或小节号）。
- `composeJianpuPageText()` / `serializeJianpuPageSections()`：将多页数据组装回带标记的文本。

---

## 十一、歌词

`_apply_lyrics()`（`jianpu_text.py:1123-1142`）+ `_read_new_syntax`（第 570-571 行）：

### 11.1 语法

- `L: 词1 词2 词3` —— 以 `L:` 开头的行，空格分隔各词。
- 按有效音符（`kind == "note"`）顺序一一匹配。
- **休止符不分配歌词**（跳过 `kind == "rest"`）。

### 11.2 存储

- 每个音符事件的 `lyric` 字段存储对应歌词。
- 同时创建 `TextBlock(role="lyric")` 附加到小节。

---

## 十二、注释

`_strip_inline_comment()`（`jianpu_text.py:667-671`）：

- `//` 开始到行尾为注释，被剥离后不进入解析。
- `@part` 和 `@page` 标记本质上是特殊注释行，在注释剥离**之前**被先提取。

---

## 十三、渲染引擎（语法渲染）

### 13.1 引擎概述

`engraving/renderer.py` 的 `PublicationRenderer`（引擎版本 `publication-3`）：

- 直接消费 `JianpuScore` 数据模型，不依赖 token 层。
- 输出 SVG，使用内嵌字体路径（`NotoSerifCJKsc` + `Bravura`）。
- 支持单页渲染、A4 分页渲染、多页文件输出。

### 13.2 页面布局

`PublicationStyle`（`style.py`）：

- 默认 A4：1240×1754 viewBox 单位。
- 边距：左 82、右 82、上 72、下 64。
- 内容宽度 = 页宽 − 左右边距。
- 系统间距 `system_gap=32`，声部间距 `part_gap=34`。

### 13.3 系统与分页

- `_build_cells()`：将各声部的小节对齐为 cell。
- `_break_systems()`：按内容宽度断行，使用"坏度"（badness）评估最佳断点。
- `_paginate()`：按页面高度分页。
- 末行填充阈值 `last_line_fill_threshold=0.72`：末行自然宽度低于此比例时不拉伸。

### 13.4 事件定位

`_event_positions()`（`renderer.py:833-927`）：

- **理想位置**：按事件起始时间在小节内的比例定位。
- **最小间距**：基于时值的"弹簧"模型（`_duration_spring`），短时值间距按比例缩短。
- **碰撞避让**：基于事件视觉边界（`measure_event_ink`）计算最小间隙。
- **连音组**：组内间距收紧为 `minimum_event_gap × 0.72`。
- **溢出处理**：`_bounded_event_positions()` 在小节过满时投影到边界内。

### 13.5 音符渲染

`_draw_pitch()`（`renderer.py:1075-1169`）：

- **音级数字**：居中绘制，`font-weight: 600`。
- **变音记号**：绘制在音符左侧，垂直对齐到音符顶部 +3。
  - `_accidental_text()`（`renderer.py:2222` 与 `geometry.py:168` 为同一份实现）有两个分支：
    1. **显式记号**（简谱 `#`/`b`/`n`/`x`/`bb`，或 MusicXML `<accidental>` 元素）：直接返回 `pitch.accidental_text`，即 ASCII token 字母，渲染为字母字形（`#`、`b`、`n`、`x`、`bb`）。
    2. **隐式记号**（无显式 token，由 `alter` 与调号推算出的 `pitch.accidental` 值）：按值映射到 Unicode 音乐符号 → `+2→𝄪`，`+1→♯`，`+1/2→↑`，`-1/2→↓`，`-1→♭`，`-2→𝄫`；`0→""`（不绘制）。
  - 实际运行中显式记号占绝大多数，因此 SVG 里出现的都是字母字形，**不出现** ♮♯♭𝄪𝄫；还原号 `n` 渲染为字母 **"n"** 而非还原号符号 ♮。若要让还原号渲染为 ♮，需在显式分支把 `"n"` 映射到 `♮`（U+266E，出版字体已含该字形）。
- **八度点**：
  - 高八度（octave > 0）：音符**上方**排列实心圆点，方向向上。
  - 低八度（octave < 0）：音符**下方**排列实心圆点，方向向下。
  - 间距 `rhythm_dot_step=7`，半径 `octave_dot_radius=2.25`。

### 13.6 时值渲染

`_draw_duration()`（`renderer.py:1172-1204`）：

- **延长线**（duration > 1）：在音符右侧绘制水平短线（`extension-line`），每拍一条，步进 `extension_line_step=18`；有附点时从附点右侧再留出 `duration_dot_clearance=3` 的安全距离。
- **附点**（dotted > 0）：在音符右侧绘制实心圆点（`rhythm-dot`），步进 `rhythm_dot_step=7`。
- **节奏线/横线**（`_draw_rhythm_lines`）：时值 < 1 拍的音符在下方绘制水平线。
  - 八分音符（1/2）：1 条线
  - 十六分音符（1/4）：2 条线
  - 三十二分音符（1/8）：3 条线
  - 六十四分音符（1/16）：4 条线
  - 上限 4 条。
  - 相邻同 voice/staff 的音用连续横线连接（beam）。
- **显式 beam**：支持 `Beam` 对象的 `begin`/`continue`/`end`/`forward-hook`/`backward-hook` 状态。

### 13.7 演奏标记渲染

`_draw_marks()` + `mark_layouts()`（`renderer.py:1207-1257` + `geometry.py:207-260`）：

- **上方**（above）：默认在音符上方堆叠，每个间隔 16 单位。
- **左侧**（left）：x=-24, y=-2。
- **右侧**（right）：x=24, y=-2。
- **右下**（below-right）：x=22, y=20 + index×16。
- **staccato 特殊处理**：渲染为实心倒三角，半径 `staccato_radius=2.4`，而非文本；这样可与高八度实心圆点区分。
- **标签超过 3 字符**时额外下移 20 单位（`vertical_offset`）。
- 渲染图形映射（`_mark_label`/`_mark_glyph`，`geometry.py:184-204` + `renderer.py:1817-1835`）：

| renderer | 图形 |
|----------|------|
| accent | `>` |
| tenuto | `—` |
| staccato | 实心倒三角 |
| trill | `tr` |
| fermata | `𝄐` |
| down-bow | `Π` |
| up-bow | `∨` |
| natural-harmonic | `○` |
| artificial-harmonic | `◇` |
| pluck | `+` |
| open-string | `0` |
| inner-string | `内` |
| outer-string | `外` |
| breath-mark | `，` |
| arpeggio | `∿` |
| three-slash | `≋` |

- 无映射的标记回退到其 `mark_id`。

### 13.8 连接线渲染

`_spanner()`（`renderer.py:1575-1622`）：

- **延音线（tie）**：贝塞尔曲线，弧高 -9，连接两个同音高音符。
- **连音线（slur）**：贝塞尔曲线，弧高 -18，连接范围内的音符。
- **滑音（slide）**：直线，根据 `slide_direction` 倾斜（上滑 delta=-13，下滑 delta=+13）。
- 跨小节时，连接线延续到行尾/下行行首（`continuation` 标记）。

### 13.9 连音组渲染

`_draw_tuplets()`（`renderer.py:1625-1685`）：

- 在连音组上方绘制方括号（`tuplet-bracket`）+ 数字（`tuplet-number`）。
- 括号中间留空以显示数字。

### 13.10 小节渲染

`_draw_measure()`（`renderer.py:286-394`）：

- **小节线**：normal（细线）、terminal（一细一粗双线）、repeat-start/repeat-end（粗线 + 细线 + 圆点）。
- **小节号**：显示在小节左上角（`measure-no`）。
- **调号/拍号属性**：当小节的 key/beats/beat_type 与前一小节不同时，在左上角显示 `1=G  3/4`（`measure-attribute`）。
- **反复记号**：小节线旁绘制两个实心圆点（`repeat-dot`）。
- **段落线**（ending）：水平线 + 段落编号。

### 13.11 页面装饰

`_page_chrome()`（`renderer.py:760-821`）：

- 第一页：标题居中（`score-title`）+ 元信息 `1=C    4/4    ♩=tempo`（`score-meta`）。
- 后续页：左上角显示标题。
- 页脚：页码居中（`page-number`）。

### 13.12 多声部渲染

`_draw_system()`（`renderer.py:186-284`）：

- 多声部时左侧绘制系统括号（`system-bracket`，花括号形状）。
- 每个声部独立绘制 staff，声部间用 `part_gap` 分隔。
- 第一个 cell 的左侧显示声部名称。

### 13.13 SVG 输出

`svg_backend.py`：

- 文本被转换为 `<path>` 字形（使用 fontTools 提取字形路径）。
- 保留隐藏的 `<text>` 用于无障碍（`aria-label`）。
- 内嵌 CSS 样式（`_CSS`）。
- 每个 source-anchor 组带有 `data-source-ids`、`data-bbox`、`data-note-index` 等语义属性，用于前端交互。

### 13.14 QA 检查

`qa.py`：

- `check_scene_geometry()`：检测页面溢出（`page-overflow`）和事件重叠（`event-overlap`）。

---

## 十四、前端语法编辑

### 14.1 编辑器（JianpuEditor.vue）

- **语法高亮**：基于 `tokenizeJianpuLine()`（`jianpuSyntax.ts`），在 textarea 后方叠加高亮层。
  - Token 类型：`plain`、`comment`、`metadata`、`note`、`rest`、`chord`、`tuplet`、`barline`、`repeat`、`dynamic`、`ornament`、`lyrics`。
  - 注意：前端高亮器是**简化版**，不完全等同于后端解析器。例如它用正则 `^(?:[whqs]|d+)` 判断时值前缀，但不处理 `qf`/`qs` 微音程前缀的特殊情况（有 `MICROTONAL_PREFIX_PATTERN` 补偿）。
- **行号槽**：`jianpuGutterLabels()` 显示小节号或 `P1`/`P2` 分页标记。
- **自动换行**：输入独立 `|` 时自动换行；输入 `|:` 中的 `:` 时撤回之前的自动换行。
- **播放高亮**：根据 `currentNoteIndex` 高亮对应音符。
- **错误高亮**：根据 `errorLine` 高亮错误行并闪烁。
- **分页摘要**：显示每页的小节号范围，可点击跳转。

### 14.2 预览（PublicationPreview.vue）

- 通过 `fetchFileBlob()` 获取 SVG，`sanitizeSvg()` 消毒后插入 DOM。
- 支持缩放平移（`useZoomPan`）。
- 播放高亮：给 `data-note-index` 匹配的 `.playback-note` 元素加 `.playback-current` 类。
- 源高亮：给 `data-source-ids` 匹配的元素加 `.source-current` 类。
- OCR 叠加：可编辑的 OCR 文字块叠加在 SVG 上。

### 14.3 前端语法高亮器的局限

`jianpuSyntax.ts` 的高亮分类逻辑与后端解析器有差异：

- `rest` 分类：前端将 `0` 和 `-` 都分为 `rest`，但后端 `-` 是延长线而非休止符。
- `ornament` 分类：前端将 `^` 和 `(^` 开头都分为 `ornament`，但后端 `^` 后跟的可能是 articulation/ornament/technical/spanner。
- 不区分具体的力度类型或演奏标记类型。
- 前端 `PITCH_PATTERN` 不包含 `bb` 后缀（只 `#b`），与后端不一致。

---

## 十五、文本序列化（写回简谱文本）

`write/jianpu_text.py` 的 `scores_to_jianpu_text()`：

### 15.1 头部生成顺序

```
title=名称        （若有且不为"简谱"）
instrument=模式    （若非 general）
tempo=速度         （若有）
1=调号
拍号/拍型
```

### 15.2 小节生成

- 每个小节一行，以 `|` 结尾。
- 小节内：调号/拍号变更前缀（`1=G`、`3/4`）+ 事件 token + 重复后缀（`*N`）+ 反复后缀（` :|`）。
- 反复起点前缀 `|: `。

### 15.3 事件 token 序列化

`_event_to_token()`（`write/jianpu_text.py:565-594`）：

- 组装顺序：`~`（tie_stop）+ `(`（slur_start）+ 时值前缀 + 音级体 + 附点/延长后缀 + `)`（slur_stop）+ `~`（tie_start）。
- 音级体：和弦用 `[a+b]`，单音用 pitch token。

### 15.4 连音组序列化

`_tuplet_to_token()`（`write/jianpu_text.py:616-656`）：

- 自动判断是否需要显式比例前缀 `实际数:常规数;`。
- 紧凑写法（无空格）vs 空格分隔：当所有 part 匹配紧凑音高模式时用紧凑写法。

### 15.5 变音记号序列化

`pitch_to_token()`（`accidentals.py:21-28`）：

- 格式：`变音记号 + 音级 + 八度记号`。
- 变音记号在前，八度记号在后。
- `auto` 模式保持原样；`sharp`/`flat` 模式尝试转换。

### 15.6 溯源锚点

`_text_anchors_raw()`：为每个事件/音高/变音/力度/标记生成 `TextAnchor`（UTF-16 偏移），用于 OCR 溯源。

---

## 十六、现有语法说明与代码的差异（待更新项）

以下是对 `SyntaxView.vue` 中硬编码的语法说明与实际代码逻辑的差异梳理：

### 16.1 完全缺失的章节

1. **分谱标记 `// @part`**：代码支持多声部输入，但语法说明中完全没有提及。
2. **分页标记 `// @page`**：代码支持多页输入（含文件名），语法说明完全没有提及。
3. **跨小节延音线自动传播**：代码中 `open_tie` 逻辑会自动给下一小节首音加 `tie_stop`，未说明。
4. **跨小节连音线/滑音延续**：渲染器支持跨行连接线延续，未说明。

### 16.2 描述不准确或不够详细

1. **已废弃写法 `key=`/`time=`**：说明中标注为"已废弃"，但代码实际已**完全不支持**解析（不报错也不识别，会被当普通 token）。
2. **变音记号后置**：说明中写"也可后置"但未说明后缀只能用 `bb`/`x`/`#`/`b`，不能用微音程和还原号。
3. **附点位置约束**：说明未提及"附点必须在音级之后、不能在时值前缀之后"的约束。
4. **小节号标签剥离**：代码会自动剥离行首 `1.` `2:` 等标签，未说明。
5. **连音线语法**：说明写 `(1 2)` 但实际是前缀 `(` + 后缀 `)` 的组合，不是范围包裹。
6. **中途转调/变拍约束**：说明未提及"必须写在小节音符之前"的约束。
7. **连音组内标记**：说明未提及连音组内可使用力度和演奏标记。
8. **连音组显式比例**：说明有 `$3:2;s1 s2$` 但未说明自动比例推导逻辑。
9. **力度标记数量**：说明列出 16 种，与代码一致，但分组可更清晰。

### 16.3 演奏技巧章节

- 演奏技巧（`performance-marks` 章节）是从后端 API `/notation/instrument-profiles` **动态加载**的，因此始终与代码同步。
- 但前端硬编码的"力度、歌词与注释"章节中列出的 `^.  ^>  ^-`、`^r  ^f  ^l`、`(^l)  (^.)  (^>)  (^r)  (^f)` 是**静态**的，需与后端 `PERFORMANCE_MARKS` 保持一致。
- 后端 `actions.py` 中的组合示例（如 `^. (1 ^. 2)` 连顿弓、`^st [3+5]` 双托等）只在 API 返回，前端说明中未提及。

### 16.4 速查表遗漏

速查表（`quickReferenceEntries`）遗漏了：
- 分谱/分页标记
- 微音程的完整写法（速查表只列了 `qs/qf/tqs/tqf` 但未说明前后缀规则）
- 连音组显式比例
- 小节级标记 `(^...)`
- 连续滑音 `^lh`

### 16.5 前端高亮器与后端不一致

`jianpuSyntax.ts` 的分类逻辑与后端解析器存在差异（见 14.3），可能导致编辑器高亮与实际解析结果不符。这虽不是语法说明的问题，但更新说明时应注意前端高亮器的局限。

---

## 十七、完整语法速查表（基于代码）

```
# ─── 头部 ───
title=名称              谱名
instrument=erhu        乐器模式：general/erhu/ruan/guzheng（zhongruan=ruan）
tempo=120              速度 BPM
1=C                    调号（C/D/E/F/G/A/B，可带 # 或 b）
4/4                    拍号

# ─── 音符 ───
1-7                    音级（do-si）
0                      休止符
1' 2''                 高八度 / 高两个八度
1, 2,,                 低八度 / 低两个八度
#1 b7 x4 bb7           升/降/重升/重降（前缀或后缀）
n4 ♮4                  还原（仅前缀）
qs1 qf2 tqs3 tqf4      微音程（仅前缀）

# ─── 时值 ───
w1 h1 1 q1 s1          全/二分/四分/八分/十六分音符
d1 dd1 ddd1 dddd1      32/64/128/... 分音符
5. 5..                 附点 / 双附点
1- 1--                 延长线（每个 - 延长一拍）
5~  ~1                 延音线起点 / 终点
(1 2)                  连音线（前缀 ( + 后缀 )）
$123$ $1 2 3$          连音组（紧凑 / 空格分隔）
$3:2;s1 s2$            显式比例连音组

# ─── 和弦与小节 ───
[1+3+5] q[1+3+5]       和弦 / 带时值和弦
| || |: :|             小节线 / 终止线 / 反复起 / 反复止
*2 *10                 重复小节 N 次

# ─── 力度 ───
\p \pp \mp \mf \f \ff \sfz \rfz ...   16 种力度（前缀 \）

# ─── 演奏标记 ───
^> ^- ^. ^r ^f         重音/保持/断音/颤音/延音（前缀 ^）
(^l) (^.) (^>) (^r) (^f)   小节级标记（括号包裹）
^lh                    连续滑音（写在目标音前）
^lg ^tg ^pg ^1-4 ^zr ...  二胡专用
^sy ^st ^sm ^bq ^zb ^sg ^xg ^cy ^zs ^zx   古筝专用
^zy ^sx ^py            阮专用

# ─── 歌词与注释 ───
L: 词1 词2 词3         歌词行
// 注释                行内注释
// @page 1 name="文件名"   分页标记
// @part 1 name="声部名"   分谱标记
```

---

*报告完毕。以上内容均基于对项目源码的逐行阅读，可直接用于更新语法说明。*
