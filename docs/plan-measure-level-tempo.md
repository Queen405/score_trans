# 方案：小节级速度（tempo）与播放器倍率

> 本文由只读调研产出，未改动任何既有代码。所有行号基于 `v1.0.0`（`1c865f2`）。

## 1. 目标与非目标

### 目标

1. 简谱文本支持小节级变速：`tempo=80` 写在目标小节第一个音符之前，对该小节及以后生效。
2. 识别链路（Audiveris / AI）产出的简谱若无速度，显式写入 `tempo=120`；编辑页"重置"走同一链路，同样带 120。
3. 速度的唯一来源是简谱文本，同时驱动 MusicXML、MIDI 与 SVG 谱面。
4. 播放器去掉 BPM 数字框与重置按钮，改为固定倍率 `0.5x / 0.8x / 1x / 1.5x / 2x`，默认 1x。120→80 在 0.5x 下等效 60→40。
5. 速度标记显示在谱面：首屏 meta 显示 `♩=120`，变速小节显示 `♩=80`。

### 非目标

- **不改写用户手工输入或粘贴的文本**。缺失 `tempo` 时按 120 播放，但不回写编辑器。
- 不做渐快/渐慢（accelerando / ritardando），只做阶跃变速。
- 不顺带修复 MIDI 的逐小节 `time_signature`（见 §8 可选项）。

## 2. 已验证的前提（实测结论）

| # | 结论 | 验证方式 |
|---|------|---------|
| V1 | `mido` 写多个 `set_tempo`，`@tonejs/midi` 能正确换算成绝对秒时间。120→80 时音符间隔 0.5s→0.75s、时长 0.5s→0.75s | 生成双 tempo MIDI 并用 Node 读回 |
| V2 | 播放器"读 MIDI 秒时间 + 全局倍率"成立。`usePlayer` 的缩放本质是 `transport.bpm` 的比值，把 `bpm` 换成 `rate` 后 `nominalToReal = n / rate` | 读 `usePlayer.ts:179-183, 253-259` |
| V3 | 识别与重置是同一后端调用。`ConvertView.resetAll()` 调 `/convert/musicxml-to-jianpu` | `ConvertView.vue:1878` |
| V4 | 多页识别**每一页各写一份完整谱头**。默认 120 必须只在整篇文档顶部补一次，否则第 2 页会把第 1 页改的 80 重置回 120 | `scores_to_jianpu_document` 实测输出 |
| V5 | `tempo=120` 放在文档最顶部（在 `// @page 1` 之前）可正常解析 | 实测两种插入位置均通过 |
| V6 | 逐小节属性带基础设施已存在：`renderer.py:381-388` 绘制、`569-583` 判定变化、`1034-1036` 首屏 meta 已含 `♩=` | 代码阅读 |
| V7 | 全后端只有 `parse/jianpu_text.py` 与 `parse/musicxml.py` 两处构造 `Measure(` | grep |
| V8 | 基线干净：pytest 946 通过 / 1 失败，`pnpm test:utils` 172 通过 / 1 失败，两处失败同源（沙箱符号链接权限） | 实测 |

## 3. 必须避开的四个坑（实测确认）

以下四点都源于同一事实：**`tempo=` 目前被四处代码当成"整行元数据头"处理，而 `1=G` / `4/4` 不是。**

### 坑 1（致命）行内 `tempo=80` 抛语法错误

`parse/jianpu_text.py:1180` 的 `=` 头部分支先接管整行并执行 `int(value)`：

```
tempo=80 5 6 7 1 |      →  JianpuSyntaxError: tempo 必须是整数：80 5 6 7 1 |
1=G 3/4 5 6 7 |         →  正常（_is_key_name("G 3/4 ...") 为假，漏到 token 循环）
```

而写出器 `_measure_lead_info`（`write/jianpu_text.py:186-204`）正是**行内**输出 lead token 的。若让 tempo 照搬变调变拍的行内形式，写出器会产出自己读不回来的文本。

**决定：规范输出采用独占行。** 依据：

- `tests/test_rekey.py:392` 已把"独占行 `1=D` 夹在两小节之间"作为既有受测形态，有先例。
- 独占行只需修坑 4 一处；行内需修四处。

### 坑 2 独占行 `tempo=80` 现在是**静默覆盖全局**

`parse/jianpu_text.py:1204` 的 tempo 分支没有 `saw_score_tokens` 判断（对比 `:1182` 的调号与 `:1236` 的拍号都有）。正文中的 `tempo=80` 会直接改写 `options.tempo`，导致**整首**变 80，而不是"从此小节起"。这是现存 bug，本次一并修正。

### 坑 3 速度值必须在解析期校验

实测 `tempo=0` / `-5` / `99999` 目前全部解析通过。`0` 只是靠 `_resolve_bpm` 里 `if score.tempo and ...` 侥幸回退；改成逐小节写 tempo map 后 `mido.bpm2tempo(0)` 会除零崩溃。20–300 的校验必须落在解析器，不能只放在 UI。

### 坑 4 四处"元数据行"判定未锚定行尾

| 位置 | 行内写法下的后果 |
|------|-----------------|
| `parse/jianpu_text.py:1204` | 语法错误（坑 1） |
| `domain/rekey.py:482` `_is_metadata_line` | 整行被判为元数据跳过，该小节不参与转调 |
| `desktop/.../utils/jianpuSyntax.ts:87` `isMetadataLine` | 整行高亮成单一 metadata 颜色，音符配色全丢 |
| `services/ai/transcription/merging.py:63` `strip_header` | **删掉整行**，AI 多页合并时该小节音符一起消失 |

采用独占行后，前三处自然安全；`strip_header` 仍必须改（它会无差别删除全文任意 `tempo=` 开头行）。

## 4. 关键设计决策

### 4.1 默认 120 注入点：只能放在转换应答层

`normalize_jianpu_text`（`domain/jianpu.py:57`）是 `parse → write` 往返，且被前端通过 `/render/normalize-jianpu-text` 调用（`api/render.ts:53`）。**若把注入写在通用写出器里，规范化用户手工文本时会静默插入 `tempo=120`，直接违反非目标。**

注入点必须是 `MusicXmlToJianpuAction.execute_document`（`exec/convert/actions.py:27`）。它同时被以下路径复用，一次改动覆盖全部目标场景：

- `exec/convert/actions.py:149` → `/convert/musicxml-to-jianpu`（编辑器首次文本 + 重置）
- `exec/pipeline/actions.py:83` → OMR/Audiveris 识别主链路
- `exec/export/actions.py:43`、`exec/render/actions.py:53` → 需确认这两处不受注入影响

`/render/normalize-jianpu-text` 与 `/convert/jianpu-to-musicxml` 不注入。

### 4.2 注入算法

1. 照常组装文档（每页保留其**真实识别到的** tempo，没有就不写）。
2. 组装完成后，若整篇文档不含文档级 tempo 头，在**最顶部**插入 `tempo=120` 一行（V5 已验证可解析）。
3. 不逐页补，避免 V4 的重置问题。

### 4.3 播放器：把 BPM 换成倍率

现有模型里 `bpm` 同时承担"目标速度"和"缩放系数"两个职责，这也是 `userBpmOverride` 补丁存在的原因（重载 MIDI 会冲掉用户速度）。改为：

- `scheduleBpm = 排程用常数`（沿用 `midiData.header.tempos[0]?.bpm ?? 120`）
- `transport.bpm.value = scheduleBpm * rate`
- `nominalToReal(n) = n / rate`，`realToNominal(s) = s * rate`
- `triggerAttackRelease` 时长 `note.duration / rate`

倍率与谱面速度解耦后，`userBpmOverride` 可以整个删掉。播放中切倍率只需改 `transport.bpm.value`，**不需要**"保存位置 + 重建调度"。

## 5. 代码改动清单

### 5.1 后端：域模型

| 文件 | 改动 |
|------|------|
| `models/score.py:132-209` | `Measure` 增加 `tempo: int | None = None` 字段，并在自定义 `__init__` 中加同名参数 |

### 5.2 后端：解析

| 文件 | 改动 |
|------|------|
| `domain/parse/jianpu_text.py:1204-1218` | tempo 分支加 `saw_score_tokens` 判断：已见谱面 token 则像 `:1234-1249` 拍号那样压入 standalone token；否则仍作文档头。同时加 20–300 校验与中文报错 |
| `domain/parse/jianpu_text.py:963-990` | 在调号/拍号处理之后增加 tempo token 分支：必须出现在当前小节首个音符之前，否则报同风格错误（对齐 `:982-986`） |
| `domain/parse/jianpu_text.py:1265-1296` | 确认 token 正则能切出独立的 `tempo=80`（`[^\s|]+` 已覆盖，无需改） |
| `domain/parse/musicxml.py:378-395` | `_extract_part_tempo` 由"取全曲第一个"改为逐小节采集 `<sound tempo>`；`metronome/per-minute` 作为兜底 |
| `domain/parse/musicxml.py:185` | 文档头 tempo 仍写 `JianpuScore.tempo` |

### 5.3 后端：写出

| 文件 | 改动 |
|------|------|
| `domain/write/jianpu_text.py:186-204` | `_measure_lead_info` 增加 tempo lead token |
| `domain/write/jianpu_text.py:293` | 独占行输出：tempo 变化改为在目标小节前单独成行，而非拼进 `body` |
| `domain/write/jianpu_text.py:341` | `_text_anchors_raw` 的 `_lead_skip_length` 需同步（已参数化，应自动跟随，需测） |
| `domain/write/musicxml.py:316-339` | 首小节 metronome TextBlock 逻辑推广到逐小节（当前硬编码 `measure_index == 1`） |
| `domain/write/musicxml.py:346-385` | `<sound tempo>` 已随 metronome TextBlock 写出，无需改 |

### 5.4 后端：注入与 AI 链路

| 文件 | 改动 |
|------|------|
| `exec/convert/actions.py:27` | 注入默认 120（§4.1 / §4.2） |
| `services/ai/transcription/merging.py:63-76` | `strip_header` 只剥离文档头区块，保留正文中的 `tempo=` |
| `services/ai/transcription/normalization.py:21-58` | `ensure_jianpu_header` 对齐同一套 120 默认值 |
| `domain/rekey.py:476-490` | `_is_metadata_line` 的 tempo 正则锚定行尾（防御性，防止日后改行内） |

### 5.5 后端：MIDI 导出与移除 `midi_tempo`

| 文件 | 改动 |
|------|------|
| `services/export/export_service.py:184-273` | 遍历小节构建 tempo map：每遇有效速度变化就在 track 0 追加 `set_tempo`（delta time = 0），首值缺失取 `MIDI_DEFAULT_BPM` |
| `services/export/export_service.py:24-29` | 删除 `_resolve_bpm` |
| `models/export/schemas.py:36,43` | 删除 `midi_tempo` |
| `exec/export/actions.py:52,66,101,110` | 删除传参 |
| `models/common/types.py:67-69` | 删除 `MidiTempo` |

> 前端无 `midi_tempo` 调用点，风险低。删后需 `pnpm generate:api-types` 重新生成 `models/openapi.ts`（`:1548,:1572`）。顺带消掉 `docs/code-review-report-2026-08-24.md` P2-4 记录的 `midi_tempo=0` 无约束问题。

### 5.6 后端：SVG

| 文件 | 改动 |
|------|------|
| `services/render/engraving/renderer.py:569-583` | `_measure_attributes_changed` 增加 `current.tempo != previous.tempo` |
| `services/render/engraving/renderer.py:381-388` | 属性串追加 `  ♩=80` |
| `services/render/engraving/renderer.py:1034-1036` | 首屏 meta 的 `♩=` 已存在，缺失时补 120 |

⚠️ `_intrinsic_measure_width`（`:613`）只按音符墨迹算宽，**属性文本不参与**。`1=G  3/4  ♩=80` 在窄小节会压到第一个音符。需二选一：给属性文本参与宽度计算，或把速度标记移到小节线上方的 `y-9` 标注带（与小节号同带）。

### 5.7 前端

| 文件 | 改动 |
|------|------|
| `composables/usePlayer.ts` | `bpm` → `rate`（§4.3）；删除 `userBpmOverride` 与 `resetBpm`；对外暴露 `rate`、`setRate` |
| `components/JianpuPlayer.vue:62-92` | BPM 数字框 + 重置按钮 → 固定倍率选择器 `0.5x/0.8x/1x/1.5x/2x` |
| `utils/jianpuSyntax.ts:86-91` | `isMetadataLine` 的 tempo 正则锚定行尾 |
| `views/SyntaxView.vue:492` | 语法条目补"可写在小节前做变速" |
| `models/openapi.ts` | 重新生成 |

倍率按"当前会话保持"：不写 localStorage，切批次 / 重启回 1x（与现有 BPM 行为一致，无新增持久化）。

## 6. 测试计划

### 6.1 必须新增

**解析（`tests/test_jianpu.py` 或新增 `tests/test_tempo.py`）**

- 文档头 `tempo=120` → `score.tempo == 120`
- 独占行 `tempo=80` 在第 2 小节前 → m1 有效 120、m2/m3 有效 80
- 行内 `tempo=80 5 6 7 |` → 明确拒绝并给出可用诊断（先按§3 决定：若最终支持行内则改为断言通过）
- `tempo=80` 写在音符之后 → 报"必须写在小节第一个音符之前"
- 边界：`0` / `19` / `-5` / `301` / `99999` / `abc` / `120.5` → 20–300 外全部拒绝
- 与变调变拍同小节：`1=G` + `3/4` + `tempo=80` 共存的优先级与顺序

**往返**

- `parse(write(x)) == x` 幂等（含逐小节变速）
- 含变速的简谱 → MusicXML → 再解析，速度序列保持一致

**MIDI（`tests/test_export.py`）**

- 120→80 的简谱导出 MIDI 后，`set_tempo` 事件为 2 个且 tick 位置正确
- 无 `tempo` 时首值回退 `MIDI_DEFAULT_BPM`

**前端（`scripts/test-*.mjs`）**

- `nominalToReal` / `realToNominal` 在 5 个倍率下的换算表
- 含双 tempo 的 MIDI：倍率 0.5x 时长为 1x 的 2 倍

### 6.2 需要更新

| 位置 | 原因 |
|------|------|
| `tests/test_convert.py:59` | 桩对象返回 `"1=C\n4/4\n1 |"`，注入后应答变为 `tempo=120\n...`。改桩或改断言 |
| `tests/test_export.py:209-315` | 5+ 处用例直接测 `midi_tempo`，随参数一并删除 |

### 6.3 回归重点

- `tests/test_render.py`（2589 行，SVG 字符串断言脆弱）
- `tests/test_convert.py`（1527 行，含谱头往返）
- `tests/test_rekey.py`（独占行变调是既有受测形态，务必不回归）

## 7. 实施顺序与规模

分三批，每批独立可验证：

**第一批 — 域模型与文本语法（核心，风险最高）**

1. `Measure.tempo` 字段
2. 解析器：头部分支 gate、token 分支、20–300 校验
3. 写出器：独占行 lead + 幂等往返
4. `strip_header` / `rekey._is_metadata_line` / `jianpuSyntax.isMetadataLine`
5. 注入默认 120（识别 + 重置）
6. 跑通 §6.1 全部分组测试与 §6.2

**第二批 — 播放链路（风险最低，V1/V2 已验证）**

7. MIDI tempo map
8. 移除 `midi_tempo` + 重新生成 openapi types
9. `usePlayer` 改 rate、`JianpuPlayer` 换倍率选择器

**第三批 — 谱面与文档**

10. SVG 属性带 + 压字问题
11. `docs/jianpu-syntax.md:16,29,421`
12. 关闭 `docs/issues.md:71` 的 N15（正是"只把第一个 tempo 读入 `originalBpm`"）

规模估计：第一批约 400–600 行改动 + 测试，第二批约 150 行，第三批约 100 行。

## 8. 可选顺带项

- MIDI 的 `time_signature` 同样只在开头写一次，逐小节变拍在导出 MIDI 里不生效。与 tempo map 在同一个小节循环内，改动近乎免费。
- `ensure_jianpu_header` 目前只在 `tempo is not None` 时补，AI 转录未识别出速度时同样缺 120，可对齐。
