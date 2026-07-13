# 简谱渲染层完全重写设计文档

> **项目**: Score Trans — `services/render/`
> **目标**: 完全重写渲染层,对齐中国主流商业简谱软件(简谱大师/JP-Word/谱谱风)的视觉细节
> **约束**: 严格保留对外 API 边界契约;允许更新测试断言以匹配新视觉
> **日期**: 2026-07-08

---

## 目录

1. [视觉目标规范](#1-视觉目标规范)
2. [API 边界契约(必须保留)](#2-api-边界契约必须保留)
3. [当前架构评估](#3-当前架构评估)
4. [新架构总览](#4-新架构总览)
5. [子模块详细设计](#5-子模块详细设计)
6. [实施阶段(7 阶段)](#6-实施阶段7-阶段)
7. [测试迁移计划](#7-测试迁移计划)
8. [风险矩阵](#8-风险矩阵)
9. [验收标准](#9-验收标准)

---

## 1. 视觉目标规范

### 1.1 坐标系与单位

- **画布**: A4 纵向, 1240×1754 像素 (@150 DPI, 1mm ≈ 5.9px)
- **SVG 坐标**: 原点左上角, Y 轴向下
- **字号单位**: SVG `px`(等效 @150 DPI)
- 所有数值均为 SVG 像素,除非另行标注

### 1.2 页面布局

```
┌──────────────────────────────────────────────┐  ← y=0
│              ↑ top_margin = 96               │
│                                              │
│              曲  名  (42px 居中加粗)           │  ← y ≈ 96
│           ── 副标题 (22px 居中) ──             │  ← y ≈ 140
│         词: XXX  曲: XXX (20px 右对齐)         │  ← y ≈ 172
│                                              │
│  1=C  4/4    ♩=120                           │  ← y ≈ 210 (调拍号行)
│                                              │
│  ────────── 谱区起始 ──────────                │  ← y ≈ 250 (score_top)
│  │ 1  2  3  4  │ 5  6  7  1'│ ...           │  ← 第1行
│  │ (小节号16px) │              │              │
│                                              │  ← 行间留白
│  │ 1  2  3  4  │ 5  6  7  1'│ ...           │  ← 第2行
│  歌词  歌词  歌词  歌词                       │  ← 歌词行
│                                              │
│            ... (更多行) ...                   │
│                                              │
│              1 / N  (页码)                    │  ← y ≈ 1710
│              ↑ bottom_margin = 72             │
└──────────────────────────────────────────────┘  ← y=1754
```

| 参数 | 规范值(px) | 规范值(mm) | 当前值 | 改动 |
|---|---|---|---|---|
| 上页边距 | 96 | 25.4 | 64 | ↑ |
| 下页边距 | 72 | 19.1 | 50 | ↑ |
| 左右页边距 | 85 | 22.5 | 64 | ↑ |
| 底色 | `#ffffff` 纯白 | — | `#fffdf7` 米白 | 改 |
| 标题区高度 | 154 | 40.7 | 126 | ↑ |

### 1.3 标题区

| 元素 | 字体 | 字号(px) | 字重 | 位置 | 颜色 |
|---|---|---|---|---|---|
| 曲名(title) | 宋体 | 42 | 700 | 居中, y = top_margin | `#1a1a1a` |
| 副标题(subtitle) | 宋体 | 22 | 400 | 居中, y = title + 44 | `#4a4a4a` |
| 作词(lyricist) | 宋体 | 20 | 400 | 右对齐, y = subtitle + 32 | `#4a4a4a` |
| 作曲(composer) | 宋体 | 20 | 400 | 右对齐, y = lyricist | `#4a4a4a` |

- 副标题、作词、作曲为可选字段,缺失时不占空间,后续元素上移
- 作词/作曲同行显示,格式: `词: XXX  曲: XXX`,整体右对齐到右页边距
- 标题区总高度 = 154px(含所有字段)或按实际字段动态计算

### 1.4 调拍号行

| 元素 | 字体 | 字号(px) | 字重 | 位置 | 格式 |
|---|---|---|---|---|---|
| 调号 | 宋体 | 24 | 600 | 左对齐, y = title_block_bottom + 20 | `1=C` |
| 拍号 | 宋体 | 24 | 600 | 调号右侧, 空两格 | `4/4` |
| 速度 | 宋体 | 20 | 400 | 右对齐, y 同调号 | `♩=120` |

- 调拍号行位于标题区下方,独占一行
- 转调时,变化小节上方出现新调号 `1=G`(measure-attribute 类)
- 拍号变化时,变化小节上方出现新拍号 `3/4`

### 1.5 行与小节

| 参数 | 规范值(px) | 当前值 | 说明 |
|---|---|---|---|
| 基础行高 | 180 | 160 | 不含上方表情记号栈 |
| 行间留白 | 36 | 0(含于行高) | 行高 = 基础行高 + 行间留白 + 上方栈高度 |
| 每行默认小节数 | 4 | 自动换行 | 可配置 2–6 |
| 小节线粗细 | 1.4 | 1.6 | CSS `.bar { stroke-width: 1.4 }` |
| 小节线颜色 | `#333333` | `#252525` | |
| 反复记号线粗细 | 3.0 | 3.0 | 不变 |
| 反复记号双点 | r=2.8 | r=2.8 | 不变 |
| 小节间最小间距 | 8 | 8(beat_gap) | 不变 |
| 小节最小宽度 | 260 | 250 | 微调 |
| 小节最大宽度 | 1070 | 1112 | = 页宽 - 左右边距 |

#### 行高计算公式

```
实际行高 = max(
    BASE_LINE_HEIGHT (180),
    BASE_LINE_HEIGHT + upper_marks_stack_height,
    content_min_line_height
)
```

- `upper_marks_stack_height`: 该行所有音符上方的表情记号栈累计高度
- `content_min_line_height`: 当前实现已有的动态行高计算(保留 `_content_min_line_height` 算法,更新常量)

#### 每行小节数算法

```
1. 默认 measures_per_line = 4
2. 计算单小节理想宽度 ideal_width
3. 如果 ideal_width * 4 > available_width:
       measures_per_line = max(2, floor(available_width / ideal_width))
4. 如果小节内音符密集(slashes >= 2 的音符 > 4 个):
       measures_per_line = max(2, measures_per_line - 1)
5. 换行: 每行放 measures_per_line 个小节, 最后一行可不满
```

### 1.6 小节号

| 参数 | 规范值 | 当前值 |
|---|---|---|
| 字号(px) | 16 | 20 |
| 字重 | 500 | 600 |
| 颜色 | `#888888` | `#333333` |
| 位置 | 小节左上角, 距小节线 4px, 距最高元素 4px | 当前类似 |
| 显示策略 | 默认 `row_start`(每行首小节) | `all` |
| 格式 | 纯数字 `1`, `5`, `9` | 当前带 `generated` 标记 |

- 可选模式: `all`(每小节)、`row_start`(每行首)、`none`(不显示)
- `row_start` 模式下, 仅每行第一个小节显示编号
- 小节号始终在小节上方, 不得与音符重叠

### 1.7 音符

| 元素 | 字体 | 字号(px) | 字重 | 颜色 |
|---|---|---|---|---|
| 数字 1-7, 0 | 宋体 | 28 | 600 | `#1a1a1a` |
| 临时记号 #/b/×/♭♭/♮ | 宋体 | 18 | 400 | `#1a1a1a` |
| 生成音符(无源 token) | 宋体 | 28 | 600 | `#818181` |

#### 数字视觉宽度

| 数字 | 宽度(px) | 说明 |
|---|---|---|
| `1`, `2` | 16 | 较窄 |
| `3`–`7`, `0` | 14 | 标准 |
| `#`, `b`, `♮` | 12 | 临时记号 |
| `bb`, `×` | 18 | 双字符 |

### 1.8 八度点

| 参数 | 规范值(px) | 当前值 | 说明 |
|---|---|---|---|
| 点半径 r | 2.5 | 2.2 | 微大, 更醒目 |
| 高八度点 Y | note_y - 30 - dot_index * 7 | note_y - 28 - dot_index * 7 | 微调 |
| 低八度点 Y | note_y + 14 + dot_index * 7 | note_y + max(6, offset-12) + dot_index * 7 | 统一公式 |
| 点间距 | 7 | 7 | 不变 |
| 与数字水平偏移 | 居中于数字 | 居中 | 不变 |
| 颜色 | `#1a1a1a` | `#171717` | 微调 |

- 高八度: 数字上方实心点, 1 个点 = 高一个八度, 2 个 = 高两个八度, 最多 3 个
- 低八度: 数字下方实心点, 同理
- 和弦共用八度点时, 避免碰撞(保留当前碰撞检测算法)

### 1.9 减时线(下方横线)

| 参数 | 规范值(px) | 当前值 |
|---|---|---|
| 线粗 | 1.6 | 1.8 |
| 线长 | 26(单音符) / 36(和弦) | 26 / 36 |
| 第1条线 Y | note_y + 12 | note_y + 10 |
| 线间距 | 6 | 6 |
| 线数与对应时值 | 1条=八分, 2条=十六分, 3条=三十二分 | 不变 |
| 颜色 | `#1a1a1a` | `#171717` |
| 与低八度点关系 | 线在点下方, 间距 ≥ 4px | 当前: 推到点下方 12px |

#### 减时线 Y 计算公式(单音符)

```python
base = note_y + 12  # 基准偏移
if octave_down > 0:
    base = max(base, low_octave_dot_y + 8)  # 推到低八度点下方
duration_line_y = base + (level - 1) * 6  # level = 1, 2, 3
```

#### 减时线 Y 计算公式(和弦)

```python
lowest_note_y = top_y + chord_gap * (note_count - 1)
base = lowest_note_y + 22  # 和弦最低音下方
# 若最低音有低八度点, 推到点下方
if any(note.octave_down for note in chord_notes):
    base = max(base, max(low_octave_dot_y) + 8)
duration_line_y = base + (level - 1) * 6
```

### 1.10 增时线(右侧横线)

| 参数 | 规范值(px) | 当前值 |
|---|---|---|
| 线粗 | 1.6 | 1.8 |
| 线长 | 30 | 30 |
| 线 Y | note_y - 9 | note_y - 9 |
| 二分音符 | 1 条 | 1 条 |
| 全音符 | 3 条, 每条间距 32px | 3 条 |
| 颜色 | `#1a1a1a` | `#171717` |

### 1.11 附点

| 参数 | 规范值(px) | 当前值 |
|---|---|---|
| 点半径 r | 2.8 | 3.0 |
| X 位置 | note_cx + 20 + dot_index * 9 | 当前相同 |
| Y 位置 | note_y - 8 | note_y - 8 |
| 颜色 | `#1a1a1a` | `#171717` |

### 1.12 三连音/N连音

| 参数 | 规范值(px) | 当前值 |
|---|---|---|
| 方括号粗细 | 1.2 | 1.2 |
| 方括号 Y | min(token_tops) - 22 | min(token_tops) - 18 |
| 数字字号 | 14 | 13 |
| 数字字重 | 600 | 650 |
| 数字位置 | 括号中点上方 | 当前相同 |
| 方括号缺口 | 16px(中间留空放数字) | 16 |
| 方括号竖线高度 | 7px | 7 |

### 1.13 Beam(符杠)

| 参数 | 规范值(px) | 当前值 |
|---|---|---|
| 线粗 | 1.6 | 1.8(复用 duration-line) |
| 线间距 | 6.0 | 6.0 |
| 半宽(单音符) | 15 | 15 |
| 半宽(和弦) | 18 | 18 |
| 最大层级 | 3 | 3 |
| 颜色 | `#1a1a1a` | `#171717` |
| CSS class | `duration-line beam-line` | 不变 |

### 1.14 连音线/圆滑线/滑音

| 类型 | 位置 | 粗细(px) | 当前值 | 弧高范围(px) |
|---|---|---|---|---|
| Tie(延音线) | 音符下方 | 1.5 | 1.5 | 7–12 |
| Slur(圆滑线) | 音符上方 | 1.3 | 1.3 | 14–26 |
| Slide(滑音) | 基线附近 | 1.45 | 1.45 | 方向感知 |

- Tie: `max(start.bottom, stop.bottom) + 13`, 三次贝塞尔曲线
- Slur: `min(start.top, stop.top) - 24`, 向上弯曲
- Slide: `y - 3` 基线, 方向感知 S 曲线

### 1.15 力度记号

| 参数 | 规范值(px) | 当前值 |
|---|---|---|
| 字体 | 宋体斜体 | 当前斜体 |
| 字号 | 20 | 19(A4) / 22(默认) |
| 字重 | 650 | 650 |
| 颜色 | `#1a1a1a` | `#171717` |
| Y 位置 | note_bottom + 32 | note_bottom + 30 |
| X 位置 | 音符中心 | 音符中心 |
| 渐强/渐弱 | 楔形 `<` / `>`, 跨多音符 | 当前未实现楔形 |

### 1.16 重音/跳音/保持音

| 符号 | 位置 | 大小(px) | 当前实现 |
|---|---|---|---|
| `>` 强音 | 音符上方 | 三角形 ±8×5 | 已有 |
| `^` 顿音 | 音符上方 | 三角形 ±8×5 | 已有 |
| `.` 跳音(staccato) | 音符上方 | 三角形 size=4.5 | 已有 |
| `-` 保持音(tenuto) | 音符上方 | 横线 ±7 | 已有 |

### 1.17 装饰音

| 符号 | 位置 | 字号(px) | 当前实现 |
|---|---|---|---|
| `tr` 颤音 | 音符上方 | 14 | 已有 |
| 倚音(grace) | 音符左侧 | 16(小字) | 未实现 |
| 回音/波音 | 音符上方 | 14 | 已有(text fallback) |

### 1.18 反复记号

| 符号 | 绘制方式 | 当前实现 |
|---|---|---|
| `\|:` 反复开始 | 粗线 + 细线 + 双点 | 已有 |
| `:\|` 反复结束 | 双点 + 细线 + 粗线 | 已有 |
| `D.C.` | 文字 | 已有(text block) |
| `D.S.` | 文字 | 已有 |
| `Fine` | 文字 | 已有 |
| `1.` `2.` 跳跃 | 小节上方方框 + 数字 | 未实现方框, 仅有文字 |

### 1.19 歌词

| 参数 | 规范值(px) | 当前值 |
|---|---|---|
| 字体 | 宋体 | 当前继承 |
| 字号 | 18 | 16(A4) / 18(默认) |
| 颜色 | `#555555` | `#5f5a52` |
| Y 位置 | note_bottom + 22 | note_bottom + 18 |
| 对齐 | 一字一音, 水平居中于音符 | 当前相同 |
| 多段堆叠 | 段间距 24px | 未实现多段堆叠 |
| 连字符 | `-` 连接多音节 | 未实现连字符 |

### 1.20 多声部

| 参数 | 规范值 | 当前值 |
|---|---|---|
| 花括号 | 左侧弧线连接所有声部 | 已有 |
| 声部名 | 竖排文字于花括号左侧 | rotate(-90) |
| 声部间距 | = 行高 | = 行高 |
| 小节对齐 | 同时间小节宽度一致 | 已有 |

### 1.21 页码

| 参数 | 规范值(px) | 当前值 |
|---|---|---|
| 字号 | 16 | 当前用 meta class |
| 位置 | 页面底部居中 | 已有, 仅多页 |
| 格式 | `1 / N` | `1 / N` |
| 显示条件 | **始终显示**(单页也显示 `1 / 1`) | 仅多页显示 |

### 1.22 CSS 类名表(完整)

以下 CSS 类名必须在重写后保留(测试断言依赖):

| CSS class | 用途 | 是否保留 |
|---|---|---|
| `.note` | 音符数字 | ✅ |
| `.note.generated` | 生成音符 | ✅ |
| `.accidental` | 临时记号 | ✅ |
| `.bar` | 小节线 | ✅ |
| `.beat-guide` | 拍引导线 | ✅ |
| `.staff-line` | 谱表引导线 | ✅ |
| `.measure-no` | 小节号 | ✅ |
| `.measure-attribute` | 小节属性(调号/拍号变化) | ✅ |
| `.repeat-count` | 反复次数 | ✅ |
| `.duration-line` | 减时线 | ✅ |
| `.duration-line.beam-line` | 符杠 | ✅ |
| `.extension-line` | 增时线 | ✅ |
| `.tie` | 延音线 | ✅ |
| `.slur` | 圆滑线 | ✅ |
| `.slide` | 滑音 | ✅ |
| `.tuplet-bracket` | 连音方括号 | ✅ |
| `.tuplet-number` | 连音数字 | ✅ |
| `.octave-dot` | 八度点 | ✅ |
| `.rhythm-dot` | 附点 | ✅ |
| `.generated` | 生成标记 | ✅ |
| `.error` | 错误标记 | ✅ |
| `.lyric` | 歌词 | ✅ |
| `.annotation` | 注释文本 | ✅ |
| `.dynamic` | 力度记号 | ✅ |
| `.ornament` | 装饰音 | ✅ |
| `.technical` | 技法记号 | ✅ |
| `.technique-mark` | 技巧标记 | ✅ |
| `.articulation` | 奏法标记 | ✅ |
| `.staccato` | 跳音 | ✅ |
| `.performance-symbol` | 表情符号(线) | ✅ |
| `.performance-symbol-fill` | 表情符号(填充) | ✅ |
| `.performance-mark` | 表情记号容器 | ✅ |
| `.playback-note` | 播放音符容器 | ✅ |
| `.playback-current` | 当前播放 | ✅ |
| `.source-anchor` | 来源锚点 | ✅ |
| `.ocr-overlay` | OCR 叠加 | ✅ |
| `.meta` | 元信息(调拍号) | ✅ |
| `.title` | 标题 | ✅ |
| `.part-name` | 声部名 | ✅ |
| `.staff-line` | 谱表线 | ✅ |

**新增 CSS 类:**

| CSS class | 用途 |
|---|---|
| `.subtitle` | 副标题 |
| `.composer` | 词曲作者 |
| `.tempo` | 速度标记 |
| `.page-number` | 页码(独立 class) |
| `.cresc` | 渐强楔形 |
| `.dim` | 渐弱楔形 |
| `.repeat-volta` | 反复跳跃方框 |

### 1.23 data 属性契约(必须保留)

| 属性 | 所在元素 | 用途 |
|---|---|---|
| `data-note-index` | `.playback-note` | 播放索引 |
| `data-note-token` | `.playback-note` | 原始 token |
| `data-source-id` | `.source-anchor` | 单来源 ID |
| `data-source-ids` | `.source-anchor` | 来源 ID 列表(空格分隔) |
| `data-bbox` | `.source-anchor` | 锚点边界框 `x y w h` |
| `data-mark` | `.performance-mark` | 表情记号 ID |
| `data-direction` | `.slide` | 滑音方向 |
| `data-number` | `.measure` | 小节编号 |
| `data-width` | `.measure` | 小节渲染宽度 |

---

## 2. API 边界契约(必须保留)

### 2.1 包级公开接口

`services/render/__init__.py` 的 `__all__` 必须严格保持:

```python
__all__ = [
    "A4MeasureRange",
    "RenderedA4FilePage",
    "RenderedA4Page",
    "RenderOptions",
    "RenderService",
]
```

### 2.2 公开 dataclass(字段名不可变)

```python
# main.py
@dataclass(slots=True)
class A4MeasureRange:
    source_page_index: int
    start_measure_number: int | None
    end_measure_number: int | None

@dataclass(slots=True)
class RenderedA4Page:
    svg: str
    measure_ranges: list[A4MeasureRange]
    note_index_start: int | None = None
    note_index_end: int | None = None

@dataclass(slots=True)
class RenderedA4FilePage:
    path: Path
    measure_ranges: list[A4MeasureRange]
    note_index_start: int | None = None
    note_index_end: int | None = None
```

### 2.3 RenderOptions(保留全部 31 字段 + 新增字段)

```python
# options.py — 现有 31 字段全部保留, 新增字段带默认值
@dataclass(slots=True)
class RenderOptions:
    # === 现有字段(不改动) ===
    title: str = RENDER_TITLE
    width: int = RENDER_WIDTH
    margin: int = RENDER_MARGIN
    measure_width: int = RENDER_MEASURE_WIDTH
    line_height: int = RENDER_LINE_HEIGHT
    font_family: str = RENDER_FONT
    min_measure_width: int = RENDER_MIN_MEASURE_WIDTH
    max_measure_width: int = RENDER_MAX_MEASURE_WIDTH
    beat_gap: int = RENDER_BEAT_GAP
    staff_space: float = 21.0
    note_min_gap: float = 9.0
    short_note_gap_ratio: float = 1.0
    short_note_slot_width_ratio: float = 1.0
    tuplet_gap_ratio: float = 0.16
    tuplet_slot_width_ratio: float = 0.54
    duration_spacing_ratio: float = 1.0
    chord_gap: float = float(RENDER_CHORD_GAP)
    chord_token_width: float = 42.0
    note_font_size: float = 30.0
    accidental_font_size: float = 18.0
    measure_number_font_size: float = 24.0
    measure_attribute_font_size: float = 18.0
    repeat_count_font_size: float = 22.0
    tuplet_font_size: float = 15.0
    lyric_font_size: float = 18.0
    dynamic_font_size: float = 22.0
    ornament_font_size: float = 15.0
    technical_font_size: float = 13.0
    technique_font_size: float = 16.0
    compact_measure_layout: bool = False
    show_beat_guides: bool = RENDER_SHOW_BEAT_GUIDES
    show_staff_guides: bool = RENDER_SHOW_STAFF_GUIDES
    show_measure_numbers: bool = RENDER_SHOW_MEASURE_NUMBERS
    measure_number_mode: MeasureNumberMode = "all"

    # === 新增字段(全部带默认值, 向后兼容) ===
    subtitle: str | None = None
    composer: str | None = None
    lyricist: str | None = None
    tempo: int | None = None
    measures_per_line: int = 4
    page_bg_color: str = "#ffffff"
    note_color: str = "#1a1a1a"
    measure_number_color: str = "#888888"
    lyric_color: str = "#555555"
    show_page_number: bool = True
```

### 2.4 A4RenderTheme(保留 + 扩展)

```python
# options.py — 现有字段保留, 新增字段带默认值
@dataclass(frozen=True, slots=True)
class A4RenderTheme:
    # === 现有字段(不改动) ===
    note_font_size: float = 26.0
    accidental_font_size: float = 16.0
    measure_number_font_size: float = 20.0
    measure_attribute_font_size: float = 16.0
    repeat_count_font_size: float = 18.0
    tuplet_font_size: float = 13.0
    lyric_font_size: float = 16.0
    dynamic_font_size: float = 19.0
    ornament_font_size: float = 13.0
    technical_font_size: float = 12.0
    technique_font_size: float = 14.0

    # === 新增字段 ===
    subtitle_font_size: float = 22.0
    composer_font_size: float = 20.0
    tempo_font_size: float = 20.0
    page_number_font_size: float = 16.0
    title_font_size: float = 42.0
    meta_font_size: float = 24.0
```

### 2.5 RenderService(8 个方法签名不可变)

| 方法 | 签名 |
|---|---|
| `render_score_svg` | `(score, output_path, title=None, show_measure_numbers=None, measure_number_mode=None) -> Path` |
| `render_score_page_svg` | `(score, output_path, *, page_width, page_height, title=None, show_measure_numbers=None, measure_number_mode=None) -> Path` |
| `render_score_a4_svg_pages` | `(score, output_path, title=None, show_measure_numbers=None, measure_number_mode=None) -> list[RenderedA4FilePage]` |
| `render_scores_a4_svg_pages` | `(scores, output_path, title=None, show_measure_numbers=None, measure_number_mode=None) -> list[RenderedA4FilePage]` |
| `build_scores_a4_svg_pages` | `(scores, title=None, show_measure_numbers=None, measure_number_mode=None, *, page_text_blocks=None) -> list[RenderedA4Page]` |
| `render_scores_a4_svg_page_results` | `(scores, output_path, title=None, show_measure_numbers=None, measure_number_mode=None, *, page_text_blocks=None) -> list[RenderedA4FilePage]` |
| `render_text_svg` | `(input_path, output_path, title="简谱", show_measure_numbers=None, measure_number_mode=None) -> Path` |
| `render_text_page_svg` | `(input_path, output_path, *, page_width, page_height, title="简谱", text_blocks=None, start_measure_number=None, show_measure_numbers=None, measure_number_mode=None) -> Path` |

### 2.6 main.py 公开函数(签名不可变)

```python
render_jianpu_svg(jianpu_text: str | JianpuScore, options: RenderOptions | None = None) -> str
render_jianpu_page_svg(jianpu_text, *, page_width, page_height, title="简谱", text_blocks=None, options=None, start_measure_number=None) -> str
render_score_svg(score: JianpuScore, options: RenderOptions | None = None) -> str
render_score_page_svg(score, *, page_width, page_height, title=None, options=None) -> str
render_jianpu_a4_svgs(jianpu_text: str | JianpuScore, options=None) -> list[str]
render_score_a4_svgs(score: JianpuScore, options=None) -> list[str]
render_scores_a4_svgs(scores: list[JianpuScore], options=None, *, page_text_blocks=None) -> list[str]
render_scores_a4_pages(scores, options=None, *, page_text_blocks=None) -> list[RenderedA4Page]
render_multi_part_scores_a4_pages(scores, options=None, *, page_text_blocks=None) -> list[RenderedA4Page]
```

### 2.7 main.py 文件写入函数(签名不可变)

```python
render_jianpu_file_to_svg(input_path, output_path, title="简谱", show_measure_numbers=None, measure_number_mode=None) -> Path
render_jianpu_page_file_to_svg(input_path, output_path, *, page_width, page_height, title="简谱", text_blocks=None, start_measure_number=None, show_measure_numbers=None, measure_number_mode=None) -> Path
render_score_file_to_svg(score, output_path, title=None, show_measure_numbers=None, measure_number_mode=None) -> Path
render_score_page_file_to_svg(score, output_path, *, page_width, page_height, title=None, show_measure_numbers=None, measure_number_mode=None) -> Path
render_score_a4_pages_to_files(score, output_path, title=None, show_measure_numbers=None, measure_number_mode=None) -> list[RenderedA4FilePage]
render_scores_a4_pages_to_files(scores, output_path, title=None, show_measure_numbers=None, measure_number_mode=None) -> list[RenderedA4FilePage]
render_scores_a4_page_results_to_files(scores, output_path, title=None, show_measure_numbers=None, measure_number_mode=None, *, page_text_blocks=None) -> list[RenderedA4FilePage]
```

### 2.8 main.py A4 常量(保留, 值可调整)

测试直接引用以下常量, 名称必须保留:

```python
A4_PAGE_WIDTH = 1240          # 不变
A4_PAGE_HEIGHT = 1754         # 不变
A4_STAFF_SPACE = 21.0         # 不变
A4_MARGIN = 85                # 改: 64 → 85
A4_LINE_HEIGHT = 180          # 改: 160 → 180
A4_ROW_BOTTOM_EXTENT = 80     # 不变
A4_MIN_MEASURE_WIDTH = 260    # 改: 250 → 260
A4_NOTE_MIN_GAP = 5.6         # 不变
A4_SHORT_NOTE_GAP_RATIO = 0.25  # 不变
A4_SHORT_NOTE_SLOT_WIDTH_RATIO = 0.72  # 不变
A4_TUPLET_GAP_RATIO = 0.12    # 不变
A4_TUPLET_SLOT_WIDTH_RATIO = 0.48  # 不变
A4_DURATION_SPACING_RATIO = 1.0  # 不变
A4_BEAT_GAP = 8               # 不变
A4_CHORD_GAP = 32.0           # 不变
A4_CHORD_TOKEN_WIDTH = 34.0   # 不变
A4_TITLE_BLOCK_HEIGHT = 154   # 改: 116 → 154
A4_BOTTOM_MARGIN = 72         # 改: 50 → 72
```

> **注意**: `test_a4_layout_uses_increased_line_height` 断言 `A4_LINE_HEIGHT == 160`。重写后此值改为 180, 该断言需更新为 `A4_LINE_HEIGHT == 180`。

### 2.9 render_map.write_render_map

```python
def write_render_map(svg_path: Path, page_index: int) -> Path | None
```

- 不改动, 保持完全相同的 SVG 选择器契约 `g.source-anchor[data-source-ids][data-bbox]`

### 2.10 子包 __all__ 契约

- `drawing.__all__` 不得包含 `_render_beat_items`
- `utils.__all__` 不得包含 `_render_articulation`, `_upper_mark_anchor_y`
- 各子包现有 `__all__` 中的导出名称可保留或精简, 但不得新增上述禁止名称

### 2.11 测试引用的私有符号(重写后需保留或同步更新测试)

以下私有符号被测试直接 import, 重写后若保留同名同签名则测试无需改动 import; 若重命名则需同步更新测试 import 行:

```
drawing.spanners: _render_slide_curve, _render_slur_arc, _render_tie_arc
drawing.text: _render_measure_text_blocks, _render_unpositioned_text_blocks
drawing.beat: _render_item
layout.measure: _score_measure_layout, _text_measure_layout
layout.beat: _item_slots
layout.rows: _layout_rows
items.factory: _event_to_item
main: _a4_render_options, _a4_score_top, _paginate_rows
```

**策略**: 保留所有上述符号的同名同签名导出, 内部实现可完全重写。

---

## 3. 当前架构评估

### 3.1 模块概览(现有)

| 子包 | 文件数 | 总行数 | 职责 |
|---|---|---|---|
| `main.py` | 1 | 1156 | 入口编排: 页面骨架、A4 分页、多声部 |
| `options.py` | 1 | 77 | RenderOptions + A4RenderTheme |
| `constants.py` | 1 | 11 | 3 个环境变量常量 |
| `render_service.py` | 1 | — | 8 方法的薄封装 |
| `render_map.py` | 1 | — | SVG→JSON 锚点映射 |
| `svg/` | 2 | 114 | SVG header + CSS |
| `drawing/` | 8 | ~1350 | SVG 绘制原语 |
| `layout/` | 4 | ~382 | 宽度计算 + 换行 |
| `items/` | 3 | ~176 | Event→RenderItem 适配 |
| `parsing/` | 3 | ~165 | Token 解析 |
| `models/` | 3 | ~69 | NoteShape + RenderItem + 布局 |
| `utils/` | 8 | ~393 | 几何/度量/文本/小节线 |

### 3.2 核心算法评估

#### 保留(无需重写)

| 算法 | 位置 | 评估 |
|---|---|---|
| Token 解析 | `parsing/tokens.py` | 稳定, 完整, 无需改动 |
| Event→RenderItem 适配 | `items/factory.py` | 稳定 |
| 拍内分组 + rest 拆分 | `items/grouping.py` | 稳定 |
| NoteShape 数据模型 | `models/shapes.py` | 稳定 |
| RenderItem/BeatLayout/MeasureLayout | `models/layout.py` | 稳定 |
| Spanner 弧线计算 | `drawing/spanners.py` | 算法正确, 仅调参 |
| Beam 层级计算 | `drawing/beams.py` | 算法正确, 仅调参 |
| Performance mark 符号分发 | `drawing/performance_marks.py` | 算法完整, 仅调参 |
| 小节线绘制 | `utils/bars.py` | 仅调参 |
| 拍内槽位分配 | `layout/beat.py` | 算法正确, 仅调参 |
| 小节宽度计算 | `layout/measure.py` | 算法正确, 仅调参 |
| 行换行算法 | `layout/rows.py` | 算法正确, 增加 measures_per_line 策略 |

#### 重写(视觉细节)

| 算法 | 位置 | 改动原因 |
|---|---|---|
| SVG header + CSS | `svg/header.py` | 重写 CSS, 新增页面骨架元素 |
| 页面骨架 | `main.py` 的 `_svg_header`/`_render_a4_page` | 新增副标题/词曲/速度/页码 |
| A4 分页 | `main.py` 的 `_paginate_rows` | 适配新行高 |
| 音符绘制 | `drawing/token.py` | 微调八度点/减时线/附点参数 |
| 行高计算 | `main.py` 的 `_content_min_line_height` | 适配新基础行高 |
| A4 渲染选项 | `main.py` 的 `_a4_render_options` | 注入新主题参数 |

### 3.3 关键视觉常量对照(当前 → 目标)

| 常量 | 当前 | 目标 | 位置 |
|---|---|---|---|
| 页面底色 | `#fffdf7` | `#ffffff` | `svg/header.py` |
| 音符色 | `#171717` | `#1a1a1a` | `svg/header.py` CSS |
| 小节线色 | `#252525` | `#333333` | `svg/header.py` CSS |
| 小节线粗 | `1.6` | `1.4` | `svg/header.py` CSS |
| 减时线粗 | `1.8` | `1.6` | `svg/header.py` CSS |
| 八度点半径 | `2.2` | `2.5` | `drawing/token.py` |
| 附点半径 | `3.0` | `2.8` | `drawing/token.py` |
| 高八度点偏移 | `28` | `30` | `utils/metrics.py` |
| 减时线基准偏移 | `10` | `12` | `utils/geometry.py` |
| 音符字号(A4) | `26` | `28` | `options.py A4RenderTheme` |
| 小节号字号(A4) | `20` | `16` | `options.py A4RenderTheme` |
| 歌词字号(A4) | `16` | `18` | `options.py A4RenderTheme` |
| 力度字号(A4) | `19` | `20` | `options.py A4RenderTheme` |
| 连音数字字号(A4) | `13` | `14` | `options.py A4RenderTheme` |
| A4 页边距 | `64` | `85` | `main.py` |
| A4 行高 | `160` | `180` | `main.py` |
| A4 标题区高 | `116` | `154` | `main.py` |
| A4 底边距 | `50` | `72` | `main.py` |
| 连音方括号 Y | `token_tops - 18` | `token_tops - 22` | `drawing/measure.py` |
| 力度 Y 偏移 | `+30` | `+32` | `drawing/beat.py` |
| 歌词 Y 偏移 | `+18` | `+22` | `drawing/beat.py` |
| Slur 弧高基准 | `-22` | `-24` | `drawing/spanners.py` |

---

## 4. 新架构总览

### 4.1 模块地图

```
services/render/
├── __init__.py              # 不变
├── main.py                  # 入口编排(重写页面骨架, 保留函数签名)
├── options.py               # 扩展(新增字段, 保留旧字段)
├── constants.py             # 扩展(新增商业排版常量)
├── render_service.py        # 不变
├── render_map.py            # 不变
│
├── svg/                     # ★ 重写
│   ├── __init__.py          # 不变
│   ├── header.py            # 重写: 新 CSS + 页面骨架
│   └── theme.py             # ★ 新增: 视觉主题常量集中管理
│
├── engine/                  # ★ 新增: 排版引擎(从 main.py 提取)
│   ├── __init__.py
│   ├── page.py              # 页面模型
│   ├── rows.py              # 行布局(measures_per_line 策略)
│   ├── pagination.py        # A4 分页
│   └── line_height.py       # 行高计算
│
├── drawing/                 # 微调参数(保留函数签名)
│   ├── __init__.py          # 不变
│   ├── token.py             # 微调: 八度点/减时线/附点参数
│   ├── beat.py              # 微调: 力度/歌词 Y 偏移
│   ├── measure.py           # 微调: 连音方括号位置
│   ├── spanners.py          # 微调: slur 弧高
│   ├── beams.py             # 微调: 线粗
│   ├── performance_marks.py # 不变(参数从 theme 读取)
│   └── text.py              # 扩展: 多段歌词堆叠
│
├── layout/                  # 保留(委托给 engine/)
│   ├── __init__.py          # 不变
│   ├── measure.py           # 不变
│   ├── beat.py              # 不变
│   └── rows.py              # 扩展: measures_per_line 策略
│
├── models/                  # 不变
├── parsing/                 # 不变
├── items/                   # 不变
└── utils/                   # 微调参数
    ├── __init__.py          # 不变
    ├── metrics.py           # 微调: 八度点偏移
    ├── geometry.py          # 微调: 减时线基准偏移
    ├── bars.py              # 微调: 小节线参数
    ├── text.py              # 不变
    ├── positioning.py       # 不变
    ├── helpers.py           # 不变
    └── articulations.py     # 不变
```

### 4.2 数据流

```
JianpuScore
  │
  ▼
items/grouping._measure_render_items()     # Event → RenderItem 拍内分组
  │
  ▼
layout/measure._score_measure_layout()      # 计算小节宽度
  │
  ▼
layout/rows._layout_rows()                  # 换行 + 行宽分配
  │                                          # ★ 新增: measures_per_line 策略
  ▼
engine/line_height.compute_line_height()    # ★ 新增: 动态行高
  │
  ▼
engine/pagination.paginate_rows()           # A4 分页
  │
  ▼
main._render_a4_page()                      # 页面骨架
  │
  ├─ svg/header._svg_header()               # ★ 重写: CSS + 标题区
  │
  └─ drawing/measure._render_measure()      # 小节绘制
       │
       ├─ drawing/beat._render_slot_items() # 拍内绘制
       │    └─ drawing/token._render_token()# 音符绘制
       │
       ├─ drawing/beams._render_beams()     # 符杠
       ├─ drawing/measure._render_tuplets() # 连音
       ├─ drawing/spanners._render_spanners()# 连音线
       └─ drawing/text._render_measure_text_blocks() # 歌词
```

### 4.3 主题注入流程

```
svg/theme.py (VisualTheme 数据类)
  │
  ▼
options.py (_a4_render_options 从 theme 读取)
  │
  ▼
main.py (RenderOptions 传给各绘制函数)
  │
  ▼
svg/header.py (CSS 从 RenderOptions 生成)
drawing/*.py (各绘制函数从 RenderOptions 读取参数)
```

---

## 5. 子模块详细设计

### 5.1 `svg/theme.py` (★ 新增)

**职责**: 集中管理商业排版视觉常量, 消除散落在各文件的裸数值。

**设计**:

```python
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class VisualTheme:
    """商业简谱排版视觉主题常量。"""

    # 页面
    page_bg_color: str = "#ffffff"
    page_text_color: str = "#1a1a1a"
    page_measure_number_color: str = "#888888"
    page_lyric_color: str = "#555555"

    # 音符
    note_color: str = "#1a1a1a"
    note_font_weight: str = "600"
    accidental_font_weight: str = "400"

    # 线条
    bar_color: str = "#333333"
    bar_stroke_width: float = 1.4
    duration_line_stroke_width: float = 1.6
    extension_line_stroke_width: float = 1.6
    tie_stroke_width: float = 1.5
    slur_stroke_width: float = 1.3
    slide_stroke_width: float = 1.45
    tuplet_bracket_stroke_width: float = 1.2

    # 圆点
    octave_dot_radius: float = 2.5
    rhythm_dot_radius: float = 2.8
    repeat_dot_radius: float = 2.8

    # 垂直布局
    octave_up_dot_offset: float = 30.0    # 高八度点距音符基线
    octave_down_dot_offset: float = 14.0  # 低八度点距音符基线
    octave_dot_stack_gap: float = 7.0     # 八度点间距
    duration_line_base_offset: float = 12.0  # 减时线基准偏移
    duration_line_level_gap: float = 6.0  # 减时线层级间距
    duration_line_below_dot_gap: float = 8.0  # 减时线距低八度点

    # 和弦
    chord_gap: float = 34.0
    chord_underline_offset: float = 22.0  # 和弦减时线距最低音

    # 连音
    tuplet_bracket_offset: float = 22.0  # 方括号距 token 顶部
    tuplet_bracket_tick: float = 7.0
    tuplet_bracket_gap: float = 16.0

    # 表情记号
    dynamic_y_offset: float = 32.0  # 力度距音符底部
    lyric_y_offset: float = 22.0    # 歌词距音符底部
    above_mark_anchor_offset: float = 13.0
    above_mark_stack_step: float = 16.0
    technique_mark_x_min: float = 15.0
    technique_mark_x_max: float = 24.0
    technique_mark_y_offset_single: float = 21.0
    technique_mark_y_offset_chord: float = 20.0

    # Spanner
    tie_y_offset: float = 13.0       # tie 弧线距音符底部
    tie_min_height: float = 7.0
    tie_max_height: float = 12.0
    slur_y_offset: float = 24.0      # slur 弧线距音符顶部
    slur_min_height: float = 14.0
    slur_max_height: float = 26.0
    slide_y_offset: float = 3.0

    # 页面布局
    title_font_size: float = 42.0
    subtitle_font_size: float = 22.0
    composer_font_size: float = 20.0
    tempo_font_size: float = 20.0
    meta_font_size: float = 24.0
    page_number_font_size: float = 16.0

VISUAL_THEME = VisualTheme()
```

**依赖**: 无(纯数据)。

**被引用**: `svg/header.py`、`main.py`(_a4_render_options)、各 `drawing/*.py` 通过 `RenderOptions` 间接读取。

---

### 5.2 `svg/header.py` (重写)

**职责**: SVG 文档头 + CSS 样式表 + 页面骨架(标题/副标题/词曲/调拍号/页码)。

**现有函数签名(保留)**:

```python
def _svg_header(options: RenderOptions, height: int, title: str, meta: str) -> list[str]
def _svg_page_header(options: RenderOptions, width: int, height: int) -> list[str]
```

**新增函数**:

```python
def _svg_title_block(
    options: RenderOptions,
    width: int,
    title: str,
    meta: str,
    *,
    subtitle: str | None = None,
    composer: str | None = None,
    lyricist: str | None = None,
    tempo: int | None = None,
) -> list[str]
```

**CSS 重写要点**:

1. 底色改为 `#ffffff`
2. 音符色改为 `#1a1a1a`
3. 小节线色改为 `#333333`, 粗细 `1.4`
4. 减时线/增时线粗 `1.6`
5. 新增 `.subtitle`、`.composer`、`.tempo`、`.page-number`、`.cresc`、`.dim`、`.repeat-volta` 类
6. 力度字号统一为 `20px`(A4)
7. 小节号字号改为 `16px`(A4), 颜色 `#888888`
8. 歌词字号改为 `18px`(A4), 颜色 `#555555`

**页面骨架算法**:

```python
def _svg_title_block(options, width, title, meta, *, subtitle, composer, lyricist, tempo):
    lines = []
    y = options.margin  # 85

    # 标题(居中)
    lines.append(f'<text class="title" x="{width/2}" y="{y}" text-anchor="middle">{_esc(title)}</text>')
    y += 44

    # 副标题(居中, 可选)
    if subtitle:
        lines.append(f'<text class="subtitle" x="{width/2}" y="{y}" text-anchor="middle">{_esc(subtitle)}</text>')
        y += 32

    # 词曲作者(右对齐, 可选)
    author_parts = []
    if lyricist:
        author_parts.append(f"词: {lyricist}")
    if composer:
        author_parts.append(f"曲: {composer}")
    if author_parts:
        author_text = "  ".join(author_parts)
        lines.append(f'<text class="composer" x="{width - options.margin}" y="{y}" text-anchor="end">{_esc(author_text)}</text>')
        y += 28

    # 调拍号行(左对齐) + 速度(右对齐)
    y += 12
    lines.append(f'<text class="meta" x="{options.margin}" y="{y}">{_esc(meta)}</text>')
    if tempo:
        lines.append(f'<text class="tempo" x="{width - options.margin}" y="{y}" text-anchor="end">♩={tempo}</text>')

    return lines
```

**页码算法**:

```python
# 在 _render_a4_page 和 _render_layouts 末尾, 恒显页码
if options.show_page_number:
    page_text = f"{page_index + 1} / {page_count}"
    lines.append(
        f'<text class="page-number" x="{width/2:.1f}" '
        f'y="{height - 34}" text-anchor="middle">{page_text}</text>'
    )
```

---

### 5.3 `engine/page.py` (★ 新增)

**职责**: 页面几何模型。

**设计**:

```python
from __future__ import annotations
from dataclasses import dataclass

@dataclass(slots=True)
class PageGeometry:
    width: int
    height: int
    margin: int
    top: int          # 谱区起始 Y
    bottom: int       # 谱区结束 Y
    available_height: int  # bottom - top

    @classmethod
    def a4(cls, margin: int = 85, title_block_height: int = 154) -> PageGeometry:
        width, height = 1240, 1754
        top = margin + title_block_height
        bottom = height - 72  # A4_BOTTOM_MARGIN
        return cls(width, height, margin, top, bottom, bottom - top)
```

---

### 5.4 `engine/line_height.py` (★ 新增)

**职责**: 动态行高计算, 替代 `main.py` 的 `_content_min_line_height`。

**设计**:

```python
from __future__ import annotations
from ..models.layout import MeasureLayout
from ..options import RenderOptions

BASE_LINE_HEIGHT = 180  # A4_LINE_HEIGHT 新值
LINE_GAP = 36           # 行间留白

def compute_line_height(layouts: list[MeasureLayout], options: RenderOptions) -> int:
    """计算满足所有上方表情记号栈的最小行高。"""
    max_upper_extent = 0.0
    for measure in layouts:
        for beat in measure.beats:
            for item in beat.items:
                upper_extent = _upper_marks_stack_height(item)
                max_upper_extent = max(max_upper_extent, upper_extent)
    return max(BASE_LINE_HEIGHT, int(BASE_LINE_HEIGHT + max_upper_extent))

def _upper_marks_stack_height(item) -> float:
    """计算音符上方表情记号栈的累计高度。"""
    # 复用现有 _content_min_line_height 中的 mark_ids 逻辑
    from ...domain.performance_marks import event_mark_ids, get_performance_mark
    mark_ids = event_mark_ids(
        list(item.articulations or ([item.articulation] if item.articulation else [])),
        list(item.ornaments),
        list(item.technical),
    )
    return sum(
        mark.visual_height + mark.stack_gap
        for mark_id in mark_ids
        if (mark := get_performance_mark(mark_id)) is not None
        and mark.placement == "above"
    )
```

**被引用**: `main.py` 的 `_a4_render_options` 和 `_render_a4_page`。

**保留兼容**: `main.py` 中的 `_content_min_line_height` 函数保留同名签名, 内部委托给 `engine.line_height.compute_line_height`。

---

### 5.5 `engine/pagination.py` (★ 新增)

**职责**: A4 分页, 替代 `main.py` 的 `_paginate_rows`。

**设计**:

```python
from __future__ import annotations
from ..models.layout import MeasureLayout
from ..options import RenderOptions

def paginate_rows(
    rows: list[list[MeasureLayout]],
    options: RenderOptions,
    line_height: int,
    *,
    page_height: int = 1754,
    top: int = 0,      # _a4_score_top
    bottom_margin: int = 72,
    row_bottom_extent: int = 80,
    part_count: int = 1,
) -> list[list[list[MeasureLayout]]]:
    if not rows:
        return [[]]

    effective_row_height = line_height * part_count
    baseline_span = max(0, page_height - top - bottom_margin - row_bottom_extent)
    rows_per_page = max(1, int(baseline_span // effective_row_height))

    return [
        rows[i : i + rows_per_page]
        for i in range(0, len(rows), rows_per_page)
    ]
```

**保留兼容**: `main.py` 中的 `_paginate_rows` 函数保留同名签名, 内部委托给 `engine.pagination.paginate_rows`。

---

### 5.6 `layout/rows.py` (扩展)

**职责**: 行换行 + 宽度分配, 新增 `measures_per_line` 策略。

**现有函数签名(保留)**:

```python
def _layout_rows(layouts: list[MeasureLayout], options: RenderOptions) -> list[list[MeasureLayout]]
```

**扩展算法**:

```python
def _layout_rows(layouts, options):
    available = options.width - options.margin * 2

    if options.compact_measure_layout:
        rows = _layout_compact_rows(layouts, options)
    else:
        rows = _layout_simple_rows(layouts, options)

    # ★ 新增: measures_per_line 约束
    if options.measures_per_line and options.measures_per_line > 0:
        rows = _enforce_measures_per_line(rows, options.measures_per_line, available)

    return rows

def _enforce_measures_per_line(rows, mpl, available):
    """将行重新按 measures_per_line 切分, 保持宽度分配。"""
    if mpl <= 0:
        return rows
    result = []
    for row in rows:
        for i in range(0, len(row), mpl):
            chunk = row[i : i + mpl]
            _justify_row(chunk, available, is_last=False)
            result.append(chunk)
    return result
```

> **注意**: `measures_per_line` 约束在 compact 和 simple 两种模式下都生效。当小节理想宽度 × mpl > 可用宽度时, `_justify_row` 会自动压缩。

---

### 5.7 `drawing/token.py` (微调参数)

**保留函数签名**:

```python
def _render_token(token, cx, y, *, generated=False, suppress_duration=False, options=None) -> list[str]
def _render_chord(token, cx, y, *, generated=False, suppress_duration=False, options=None) -> list[str]
def _render_note_shape(note, cx, y, *, generated=False, suppress_duration=False, dot_cx=None, upper_bound=None, lower_bound=None, options=None) -> list[str]
```

**参数变更清单**:

| 参数 | 当前值 | 目标值 | 变更位置 |
|---|---|---|---|
| 八度点半径 | `r=2.2` | `r=2.5` | `_render_note_shape` 中 circle 元素 |
| 附点半径 | `r=3.0` | `r=2.8` | `_render_note_shape` 中 rhythm-dot circle |
| 减时线长度(单音符) | `cx ± 13` = 26 | `cx ± 13` = 26 | 不变 |
| 减时线长度(和弦) | `cx ± 18` = 36 | `cx ± 18` = 36 | 不变 |
| 增时线长度 | 30 | 30 | 不变 |
| 和弦 gap | `options.chord_gap` (A4=32) | `options.chord_gap` (A4=34) | 通过 options 注入 |

**关键**: 减时线 Y 偏移和八度点 Y 偏移的变更在 `utils/metrics.py` 和 `utils/geometry.py` 中(见 5.12, 5.13)。

---

### 5.8 `drawing/beat.py` (微调参数)

**保留函数签名**:

```python
def _render_slot_items(slots, y, options) -> list[str]
def _render_item(item, cx, y, slot_width, *, suppress_duration, suppress_upper_marks, options) -> list[str]
```

**参数变更清单**:

| 参数 | 当前值 | 目标值 | 变更位置 |
|---|---|---|---|
| 力度 Y 偏移 | `bottom + 30` | `bottom + 32` | `_render_item` |
| 歌词 Y 偏移 | `bottom + 18` | `bottom + 22` | `_render_item` |
| bbox 力度扩展 | `+34` | `+34` | 不变 |
| bbox 歌词扩展 | `+22` | `+22` | 不变 |

---

### 5.9 `drawing/measure.py` (微调参数)

**保留函数签名**:

```python
def _render_measure(measure, x, y, width, options, *, draw_start_bar, attribute_text=None, show_measure_number=None, open_tie=None, open_slur=None, open_slide=None) -> tuple[list[str], ...]
```

**参数变更清单**:

| 参数 | 当前值 | 目标值 | 变更位置 |
|---|---|---|---|
| 连音方括号 Y | `min(token_tops) - 18` | `min(token_tops) - 22` | `_render_tuplets` |
| 小节号距最高元素 | `min_top - 20 - 4` | `min_top - 20 - 4` | 不变 |
| 小节属性 Y | `y - 62` | `y - 62` | 不变 |
| content_x | `x + 26` | `x + 26` | 不变 |
| content_width | `width - 56` | `width - 56` | 不变 |

---

### 5.10 `drawing/spanners.py` (微调参数)

**保留函数签名**:

```python
def _render_tie_arc(start, stop, y, options) -> str
def _render_slur_arc(start, stop, y, options) -> str
def _render_slide_curve(start, stop, y, options) -> str
```

**参数变更清单**:

| 参数 | 当前值 | 目标值 | 变更位置 |
|---|---|---|---|
| Slur Y 偏移 | `min(start.top, stop.top) - 22` | `min(start.top, stop.top) - 24` | `_render_slur_arc` |
| Tie Y 偏移 | `max(start.bottom, stop.bottom) + 13` | `max(start.bottom, stop.bottom) + 13` | 不变 |
| Tie 弧高范围 | 7–12 | 7–12 | 不变 |
| Slur 弧高范围 | 14–26 | 14–26 | 不变 |

---

### 5.11 `drawing/beams.py` (微调参数)

**保留函数签名**: 所有函数签名不变。

**参数变更**: 线粗由 CSS 控制(`.duration-line { stroke-width: 1.6 }`), 代码中无需改动。

---

### 5.12 `utils/metrics.py` (微调参数)

**保留函数签名**: 所有函数签名不变。

**参数变更清单**:

| 参数 | 当前值 | 目标值 | 变更位置 |
|---|---|---|---|
| 高八度点偏移 | `note_y - 28 - dot*7` | `note_y - 30 - dot*7` | `_high_octave_dot_y` |
| 低八度点偏移 | `note_y + max(6, LOW_OCTAVE_DOT_OFFSET - 12) + dot*7` | `note_y + 14 + dot*7` | `_low_octave_dot_y` |
| `_note_visual_top` 基准 | `y - 28` | `y - 30` | `_note_visual_top` |
| `_note_visual_bottom` 基准 | `y + 14` | `y + 14` | 不变 |

---

### 5.13 `utils/geometry.py` (微调参数)

**保留函数签名**: 所有函数签名不变。

**参数变更清单**:

| 参数 | 当前值 | 目标值 | 变更位置 |
|---|---|---|---|
| 减时线基准偏移 | `y + 10` | `y + 12` | `_note_duration_line_y` |
| 和弦减时线偏移 | `top_y + gap*(len-1) + 18` | `top_y + gap*(len-1) + 22` | `_duration_line_y` |
| 层级间距 | `6` | `6` | 不变 |

---

### 5.14 `utils/bars.py` (微调参数)

**保留函数签名**: 所有函数签名不变。

**参数变更清单**:

| 参数 | 当前值 | 目标值 | 变更位置 |
|---|---|---|---|
| 粗线 stroke-width | `3.0` | `3.0` | 不变 |
| 细线偏移 | `6` | `6` | 不变 |
| 双点偏移 | `14` | `14` | 不变 |
| 双点 Y(上) | `y - 12` | `y - 12` | 不变 |
| 双点 Y(下) | `y + 20` | `y + 20` | 不变 |
| 双点半径 | `2.8` | `2.8` | 不变 |

> bars.py 无需改动, 所有视觉参数已符合目标规范。

---

### 5.15 `main.py` (重写页面骨架, 保留函数签名)

**保留的函数(签名不变, 内部重写)**:

- `_render_a4_page` — 页面骨架: 调用 `_svg_title_block`, 恒显页码
- `_render_layouts` — 非 A4 页面骨架: 同上
- `_a4_render_options` — 注入新主题参数
- `_content_min_line_height` — 委托给 `engine/line_height.py`
- `_paginate_rows` — 委托给 `engine/pagination.py`
- `_render_multi_part_a4_page` — 多声部页面骨架

**`_a4_render_options` 改动**:

```python
def _a4_render_options(options, *, title=None, theme=A4_RENDER_THEME):
    base = options or RenderOptions(title=title or "简谱")
    mode = base.measure_number_mode
    return RenderOptions(
        # ... 所有现有字段保留 ...
        # ★ 新增字段注入
        subtitle=base.subtitle,
        composer=base.composer,
        lyricist=base.lyricist,
        tempo=base.tempo,
        measures_per_line=base.measures_per_line,
        page_bg_color=base.page_bg_color,
        note_color=base.note_color,
        measure_number_color=base.measure_number_color,
        lyric_color=base.lyric_color,
        show_page_number=base.show_page_number,
    )
```

**`_render_a4_page` 改动**:

```python
def _render_a4_page(rows, options, title, meta, *, page_index, page_count, text_blocks=None):
    out = _svg_header(options, A4_PAGE_HEIGHT, title, meta)
    # ★ 调用新的标题块(含副标题/词曲/速度)
    # out.extend(_svg_title_block(options, A4_PAGE_WIDTH, title, meta, ...))
    y = _a4_score_top(options)
    # ... 小节渲染逻辑不变 ...
    # ★ 恒显页码
    if options.show_page_number:
        out.append(f'<text class="page-number" ...>{page_index + 1} / {page_count}</text>')
    out.extend(_render_positioned_text_blocks(...))
    out.append("</svg>")
    return "\n".join(out)
```

---

### 5.16 `options.py` (扩展)

**变更**: 新增 11 个字段(见 2.3 节), 新增 `A4RenderTheme` 6 个字段(见 2.4 节)。

---

### 5.17 `constants.py` (扩展)

**新增**:

```python
# 商业排版常量
COMMERCIAL_NOTE_COLOR = "#1a1a1a"
COMMERCIAL_BAR_COLOR = "#333333"
COMMERCIAL_MEASURE_NUMBER_COLOR = "#888888"
COMMERCIAL_LYRIC_COLOR = "#555555"
COMMERCIAL_PAGE_BG = "#ffffff"
```

---

### 5.18 不变模块清单

以下模块完全不变, 无需任何改动:

| 模块 | 原因 |
|---|---|
| `parsing/tokens.py` | Token 解析逻辑稳定 |
| `parsing/events.py` | Event→token 序列化稳定 |
| `items/factory.py` | Event→RenderItem 适配稳定 |
| `items/grouping.py` | 拍内分组+rest 拆分稳定 |
| `models/shapes.py` | NoteShape 数据模型不变 |
| `models/layout.py` | RenderItem/BeatLayout/MeasureLayout 不变 |
| `layout/measure.py` | 小节宽度算法稳定 |
| `layout/beat.py` | 拍内槽位算法稳定 |
| `render_service.py` | 薄封装层不变 |
| `render_map.py` | SVG→JSON 映射不变 |
| `utils/text.py` | 转义函数不变 |
| `utils/positioning.py` | 定位函数不变 |
| `utils/helpers.py` | 辅助函数不变 |
| `utils/articulations.py` | 跳音绘制不变 |
| `drawing/performance_marks.py` | 符号分发不变(参数从 CSS 控制) |

---

## 6. 实施阶段(7 阶段)

### 阶段 0: 基线快照(0.5 天)

**目标**: 建立重写前的 golden SVG 快照, 用于人工目视对比。

**步骤**:

1. 准备 8 个代表性测试输入:
   - 单声部 4/4 简单旋律(全/二分/四分/八分/十六分音符)
   - 单声部含三连音、附点、升降记号
   - 单声部含 tie/slur/slide
   - 单声部含歌词、力度、装饰音
   - 单声部含反复记号(|: :| D.C. Fine)
   - 多声部(2 声部, 花括号)
   - 长 score(>20 小节, 触发分页)
   - OCR 叠加页面
2. 对每个输入调用 `render_scores_a4_svgs`, 保存 SVG 输出到临时目录
3. 在浏览器中截图保存为 PNG
4. 记录当前测试通过状态: `pytest tests/test_render.py -q`(当前 86 passed)

**交付物**: 8 个 golden SVG + 8 个 golden PNG + 测试基线记录。

---

### 阶段 1: 视觉主题与 CSS 重写(1 天)

**目标**: 建立主题常量体系, 重写 CSS 样式表。

**步骤**:

1. 新建 `svg/theme.py`: 实现完整 `VisualTheme` 数据类(见 5.1)
2. 重写 `svg/header.py`:
   - `_svg_styles`: 更新所有 CSS 颜色/粗细/字号
   - 新增 `_svg_title_block` 函数
   - `_svg_header` 调用 `_svg_title_block`
   - `_svg_page_header` 保持 standalone 模式
3. 更新 `options.py`:
   - `RenderOptions` 新增 11 个字段
   - `A4RenderTheme` 新增 6 个字段
4. 更新 `constants.py`: 新增商业排版常量
5. 更新 `main.py` 的 `_a4_render_options`: 注入新字段
6. 更新 `main.py` 的 A4 常量值(`A4_MARGIN`, `A4_LINE_HEIGHT`, `A4_TITLE_BLOCK_HEIGHT`, `A4_BOTTOM_MARGIN`, `A4_MIN_MEASURE_WIDTH`)

**测试更新**:

- `test_a4_layout_uses_increased_line_height`: `A4_LINE_HEIGHT == 160` → `== 180`
- `test_a4_render_options_take_every_font_size_from_named_theme`: 新增 theme 字段自动覆盖(字段遍历)
- `test_accidentals_are_rendered_smaller_than_note_digits`: `.accidental { font-size: 18px` → 匹配新值
- `test_a4_compact_render_keeps_dense_symbols_legible`: `.note { font-size: 26px` → `28px`; `.measure-no { font-size: 20px` → `16px`
- 所有 Group 3 中 font-size CSS 字符串断言更新

**验证**:

```bash
.venv/Scripts/python.exe -m pytest tests/test_render.py -q -k "package_exposes or render_options or accidentals_smaller"
```

---

### 阶段 2: 页面骨架与标题区(1 天)

**目标**: 实现新的页面标题区(副标题/词曲/速度/页码恒显)。

**步骤**:

1. 在 `svg/header.py` 实现 `_svg_title_block` 完整算法(见 5.2)
2. 在 `main.py` 的 `_render_a4_page` 中调用 `_svg_title_block`, 替代旧的标题+meta 两行
3. 在 `main.py` 的 `_render_layouts` 中同样替换
4. 在 `main.py` 的 `_render_multi_part_a4_page` 中同样替换
5. 实现页码恒显逻辑(`show_page_number` 控制)
6. 更新 `_a4_score_top`: `margin + A4_TITLE_BLOCK_HEIGHT`(154 而非 116)

**新增测试**:

- `test_render_subtitle_appears_below_title`: 副标题在标题下方渲染
- `test_render_composer_right_aligned`: 词曲作者右对齐
- `test_render_tempo_right_aligned`: 速度右对齐
- `test_page_number_always_shown`: 单页也显示 `1 / 1`
- `test_title_block_height_increased`: `_a4_score_top` 返回值增大

**验证**:

```bash
.venv/Scripts/python.exe -m pytest tests/test_render.py -q -k "title or page_number or subtitle or composer or tempo"
```

---

### 阶段 3: 行布局与分页(1.5 天)

**目标**: 实现 `measures_per_line` 策略 + 新行高 + 分页适配。

**步骤**:

1. 新建 `engine/__init__.py`、`engine/page.py`、`engine/line_height.py`、`engine/pagination.py`
2. `main.py` 的 `_content_min_line_height` 委托给 `engine/line_height.compute_line_height`
3. `main.py` 的 `_paginate_rows` 委托给 `engine/pagination.paginate_rows`
4. `layout/rows.py` 新增 `_enforce_measures_per_line` 逻辑
5. `_layout_rows` 在 compact 和 simple 模式后应用 measures_per_line 约束
6. 更新 `_a4_render_options`: 默认 `measures_per_line=4`

**测试更新**:

- `test_a4_layout_paginates_nine_rows_per_page`: 行高从 160→180, 每页行数可能变化(重算 `[9,9,7]` → 新值)
- `test_a4_full_page_rows_reach_bottom_safe_area`: 行数和底部空间重算
- `test_a4_compact_layout_hits_measure_capacity_targets`: measures_per_line 可能影响行容量
- 新增 `test_measures_per_line_constraint`: 验证每行小节数

**验证**:

```bash
.venv/Scripts/python.exe -m pytest tests/test_render.py -q -k "paginate or row_count or measures_per_line or compact_layout"
```

---

### 阶段 4: 音符与符号视觉微调(1.5 天)

**目标**: 微调所有视觉参数, 对齐商业软件细节。

**步骤**:

1. `utils/metrics.py`:
   - `_high_octave_dot_y`: 偏移 28→30
   - `_low_octave_dot_y`: 统一为 `note_y + 14 + dot*7`
   - `_note_visual_top`: 基准 `y - 28` → `y - 30`
2. `utils/geometry.py`:
   - `_note_duration_line_y`: 基准 `y + 10` → `y + 12`
   - `_duration_line_y` 和弦偏移: `+ 18` → `+ 22`
3. `drawing/token.py`:
   - 八度点半径 `r=2.2` → `r=2.5`
   - 附点半径 `r=3.0` → `r=2.8`
4. `drawing/beat.py`:
   - 力度 Y 偏移 `+30` → `+32`
   - 歌词 Y 偏移 `+18` → `+22`
5. `drawing/measure.py`:
   - 连音方括号 Y `token_tops - 18` → `token_tops - 22`
6. `drawing/spanners.py`:
   - Slur Y 偏移 `-22` → `-24`

**测试更新**(Group 3 中所有像素断言):

- `test_low_octave_dot_sits_close_to_notehead`: `4 ≤ Δ ≤ 10` → 重新验证(new: `14` 基准, 需确认)
- `test_low_octave_duration_line_sits_below_low_dot`: `beam_y > dot_y + 8` → 验证仍成立
- `test_extension_line_sits_at_note_height_not_below_note`: `extension_y < note_y` → 验证
- `test_chord_tie_sits_below_duration_lines`: `tie_y > beam_y + 4` → 验证(new 和弦减时线偏移 +22)
- `test_chord_accent_sits_above_highest_note`: `accent_y < min(note_ys) - 20` → 验证
- `test_tuplet_marks_render_above_tuplet_number`: `number_y - mark_y < 28` → 验证(new 方括号 -22)
- `test_first_row_tuplet_marks_clear_score_meta`: 验证(new 标题区高度)
- `test_measure_number_stays_close_to_measure_top`: `measure_no_y > first_note_y - 64` → 验证
- `test_text_tie_and_slur_arcs_stay_close_to_noteheads`: `"-22" not in svg` → 更正为 `"-24" not in svg` 或移除
- `test_multiple_octave_dots_stack_vertically`: 验证 3+3 分组仍成立
- `test_low_octave_eighth_beam_stays_separated_from_sixteenth_beam`: `beam_ys[1] >= beam_ys[0] + 5.5` → 验证

**验证**:

```bash
.venv/Scripts/python.exe -m pytest tests/test_render.py -q
```

---

### 阶段 5: 多声部与歌词增强(1 天)

**目标**: 增强多声部声部名竖排 + 多段歌词堆叠。

**步骤**:

1. `drawing/text.py` 的 `_render_measure_text_blocks`:
   - 实现多段歌词纵向堆叠(段间距 24px)
   - 同一 `start` 位置的多段歌词从下往上堆叠
2. `main.py` 的 `_render_multi_part_a4_page`:
   - 声部名: 检测中文字符 → 逐字竖排; 英文 → 保留 rotate(-90)
   - 逐字竖排算法: 每个 `<text>` 元素独立 Y 坐标, 间距 = font_size
3. `drawing/text.py` 的 `_render_positioned_text_blocks`: 不变(OCR 叠加)

**测试更新**:

- `test_multi_part_part_name_uses_vertical_rotation`: 若改用逐字竖排, 更新断言
- 新增 `test_multi_verse_lyrics_stack_vertically`: 验证多段歌词堆叠

**验证**:

```bash
.venv/Scripts/python.exe -m pytest tests/test_render.py -q -k "multi_part or lyric or verse"
```

---

### 阶段 6: 回归与验收(1 天)

**目标**: 全量测试通过 + 人工目视确认。

**步骤**:

1. 全量 render 测试: `pytest tests/test_render.py -q`(目标: 全部通过)
2. 组合回归:
   ```bash
   pytest tests/test_convert.py tests/test_jianpu.py tests/test_render.py tests/test_provenance.py tests/test_pipeline.py tests/test_architecture.py -q
   ```
3. Ruff: `ruff format backend/ tests/ && ruff check --fix backend/ tests/`
4. 前端: `cd desktop && pnpm lint && npx vue-tsc --noEmit && pnpm build`
5. 人工目视: 用阶段 0 的 8 个输入重新渲染, 对比 golden PNG 与新输出
6. 商业软件对比: 与简谱大师/JP-Word 截图并排对比

**验收检查清单**:

- [ ] 所有 Group 1(API 边界)测试不变且通过
- [ ] 所有 Group 2(结构)测试通过(CSS 类名/元素存在性不变)
- [ ] 所有 Group 3(视觉)测试更新后通过
- [ ] 所有 Group 4(行为)测试通过或合理调参
- [ ] `test_provenance.py` 全部通过(render-map 契约不变)
- [ ] `test_pipeline.py` 全部通过(A4 页面尺寸不变)
- [ ] 架构测试通过(`__all__` 契约、import 规则)
- [ ] Ruff format + check 通过
- [ ] 前端 lint + typecheck + build 通过
- [ ] 人工目视: 8 个 golden 输出的新版渲染在视觉上明显优于旧版
- [ ] 人工目视: 新版渲染与商业简谱软件截图视觉一致

---

## 7. 测试迁移计划

### 7.1 测试分类与处置

| 组别 | 数量 | 处置策略 |
|---|---|---|
| Group 1: API 边界 | 6 | **不改不动的** |
| Group 2: 结构 | 32 | **大概率不改**(CSS 类名/元素存在性保留) |
| Group 3: 视觉/像素 | 23 | **必须更新**(像素值/字号/坐标断言) |
| Group 4: 行为 | 18 | **可能调参**(分页行数/行容量) |

### 7.2 Group 3 详细更新清单

| 测试函数 | 当前断言 | 目标断言 | 更新原因 |
|---|---|---|---|
| `test_render_new_syntax_repeat_marks_and_semantics` | `stroke-width="3.0"` | `stroke-width="3.0"` | 不变(反复线粗不变) |
| `test_multiple_octave_dots_stack_vertically` | 3+3 分组 | 3+3 分组 | 验证(算法不变) |
| `test_measure_bars_expand_to_cover_extreme_octave_dots` | bar 覆盖点 | bar 覆盖点 | 验证(bar_bounds 算法不变) |
| `test_tuplet_marks_render_above_tuplet_number` | `gap < 28` | `gap < 32` | 方括号 Y 从 -18 改为 -22 |
| `test_first_row_tuplet_marks_clear_score_meta` | `mark_y > meta_y + 8` | 验证 | 标题区高度增大 |
| `test_measure_number_stays_close_to_measure_top` | `> first_note_y - 64` | `> first_note_y - 68` | 行高增大 |
| `test_render_score_page_svg_preserves_requested_page_size` | `1240×1754` | `1240×1754` | 不变 |
| `test_a4_compact_layout_hits_measure_capacity_targets` | 4/3/2/3 行 | 重新计算 | 行高+measures_per_line 变化 |
| `test_a4_compact_layout_tightens_only_consecutive_short_note_spacing` | gap 比例 | 验证 | 参数不变 |
| `test_tuplet_group_spacing_is_tighter_than_plain_same_beat_notes` | `< 50%` | 验证 | 参数不变 |
| `test_a4_layout_paginates_nine_rows_per_page` | `[9,9,7]` | 重新计算 | 行高 160→180 |
| `test_a4_full_page_rows_reach_bottom_safe_area` | 9 行, ≥0 | 重新计算 | 行高+边距变化 |
| `test_a4_compact_render_keeps_dense_symbols_legible` | `26px`/`20px` | `28px`/`16px` | 字号变化 |
| `test_render_jianpu_text_page_runs_ocr_and_preserves_bbox` | `320×480` | `320×480` | 不变(page_svg 不走 A4) |
| `test_render_score_page_svg_places_ocr_text_block_at_bbox` | x/y 范围 | 验证 | OCR 叠加不变 |
| `test_render_score_page_svg_keeps_bboxless_ocr_text_visible` | x>0, y>0 | 验证 | 不变 |
| `test_render_score_page_svg_uses_ocr_measure_number_without_overlay_duplicate` | 88, 89 | 验证 | 不变 |
| `test_musicxml_tremolo_renders_ruan_roll_mark_below_right` | x>note.x, y>note.y | 验证 | 不变 |
| `test_dense_measure_gets_more_width_than_empty_measure` | `> 1.8×` | 验证 | 不变 |
| `test_low_octave_eighth_beam_stays_separated_from_sixteenth_beam` | `≥ +5.5` | 验证 | 减时线基准 +12 |
| `test_text_tie_and_slur_arcs_stay_close_to_noteheads` | `"-22" not in svg` | `"-24" not in svg` 或移除 | slur 偏移 -22→-24 |
| `test_chord_tie_sits_below_duration_lines` | `tie_y > beam_y + 4` | 验证 | 和弦减时线偏移 +22 |
| `test_chord_accent_sits_above_highest_note` | `< min - 20` | 验证 | 不变 |
| `test_low_octave_duration_line_sits_below_low_dot` | `> dot_y + 8` | 验证 | 减时线基准 +12 |
| `test_low_octave_dot_sits_close_to_notehead` | `4 ≤ Δ ≤ 10` | `10 ≤ Δ ≤ 18` | 低八度点偏移 14 |
| `test_extension_line_sits_at_note_height_not_below_note` | `ext_y < note_y` | 验证 | 不变 |
| `test_render_chord_orders_notes_from_high_to_low` | `["7","3","1"]` | 验证 | 不变 |

### 7.3 Group 4 详细处置

| 测试函数 | 处置 |
|---|---|
| `test_spanner_renderers_reject_missing_endpoints` | 不变(ValueError 契约) |
| `test_multi_part_pages_report_ranges_and_note_indices_for_every_part` | 不变 |
| `test_text_measure_layout_groups_tokens_by_declared_eighth_note_beats` | 不变 |
| `test_unpositioned_text_is_checked_before_crossing_page_bottom` | 不变 |
| `test_multi_part_render_rejects_unequal_measure_counts` | 不变 |
| `test_render_jianpu_text_page_ignores_legacy_text_directives` | 不变 |
| `test_render_jianpu_text_page_supports_chord_tokens` | 不变 |
| `test_render_jianpu_text_page_rejects_ai_dotted_duration_prefix_variant` | 不变 |
| `test_render_scores_a4_svgs_continue_across_source_page_boundaries` | 验证(分页可能变) |
| `test_render_scores_a4_pages_report_source_measure_ranges` | 验证(分页可能变) |
| `test_render_batch_a4_assigns_source_ocr_to_first_overlapping_final_page` | 验证 |
| `test_render_batch_a4_saved_page_ocr_overrides_source_suggestion` | 不变 |
| `test_render_batch_a4_places_structured_text_by_semantic_anchor` | 不变 |
| `test_continuous_slide_renders_dangling_segments_across_rows` | 不变 |
| `test_guzheng_directional_slides_keep_direction_across_rows` | 不变 |
| `test_erhu_performance_marks_render_once_with_canonical_ids` | 不变 |
| `test_guzheng_performance_marks_render_with_canonical_ids` | 不变 |
| `test_ruan_performance_marks_reuse_shared_renderers` | 不变 |

### 7.4 跨文件测试

| 文件 | 测试 | 处置 |
|---|---|---|
| `test_provenance.py` | `test_render_map_contains_selector_and_bbox` | 不变(选择器契约不变) |
| `test_provenance.py` | `test_current_text_anchors_are_embedded_in_render_group` | 不变(`_render_item` 签名不变) |
| `test_provenance.py` | `test_unmarked_complete_sextuplet_beams_restore_text_render_and_provenance` | 不变 |
| `test_pipeline.py` | `test_full_pipeline_writes_pipeline_outputs` | 不变 |
| `test_pipeline.py` | `test_full_pipeline_can_hide_measure_numbers` | 不变 |
| `test_pipeline.py` | `test_full_pipeline_runs_ocr_for_image_and_outputs_a4_layout` | 验证(`1240×1754` 不变) |
| `test_pipeline.py` | `test_full_pipeline_rejects_empty_render_output` | 不变 |

---

## 8. 风险矩阵

| 风险 | 概率 | 影响 | 缓解措施 |
|---|---|---|---|
| 行高 160→180 导致分页行数变化, 多处测试断言失败 | 高 | 中 | 阶段 3 首先重算分页预期值, 批量更新断言 |
| `measures_per_line` 约束与 compact 换行算法冲突 | 中 | 中 | `_enforce_measures_per_line` 在换行后执行, 仅切分不重算宽度 |
| 低八度点偏移从 `max(6, offset-12)` 改为固定 `14`, 某些配置下行为变化 | 中 | 低 | `LOW_OCTAVE_DOT_OFFSET` 环境变量仍可覆盖; 默认值调整 |
| Slur 偏移 `-22`→`-24` 导致 slur 弧线与上方表情记号碰撞 | 低 | 低 | 阶段 4 人工目视确认 |
| 多声部声部名逐字竖排在英文声部名时显示不佳 | 中 | 低 | 保留 rotate(-90) 作为英文回退 |
| 前端依赖 `playback-note`/`source-anchor` 的 data 属性 | 低 | 高 | 严格保留所有 data 属性契约(见 1.23) |
| CSS 字号变更导致前端 SVG 缩放显示异常 | 低 | 中 | 前端 SVG 按 viewBox 缩放, 字号是相对的 |
| 测试更新量大(23 个 Group 3 测试) | 高 | 低 | 阶段 4 集中处理, 按类别批量更新 |
| `A4RenderTheme` 新增字段后 `test_a4_render_options_take_every_font_size_from_named_theme` 需自动覆盖 | 低 | 低 | 该测试遍历 `fields(theme)`, 新增字段自动覆盖 |

---

## 9. 验收标准

### 9.1 功能验收

- [ ] 所有现有 API 端点(`/render/*`)功能不变
- [ ] `render_score_svg`/`render_jianpu_svg` 返回有效 SVG 字符串
- [ ] `render_scores_a4_pages` 返回正确数量的 `RenderedA4Page`
- [ ] `RenderedA4Page.svg` 包含完整 SVG 文档
- [ ] `RenderedA4Page.measure_ranges` 正确报告小节范围
- [ ] `RenderedA4Page.note_index_start/end` 正确报告播放索引
- [ ] 多声部渲染: 各声部小节对齐, 花括号连接
- [ ] `write_render_map` 输出正确的 JSON 锚点

### 9.2 视觉验收(人工目视)

- [ ] 页面底色为纯白
- [ ] 标题居中, 字号 42px, 加粗
- [ ] 副标题(如有)居中, 在标题下方
- [ ] 词曲作者(如有)右对齐
- [ ] 调拍号独占一行, 左对齐
- [ ] 速度(如有)右对齐, 与调拍号同行
- [ ] 页码恒显, 底部居中
- [ ] 每行默认 4 小节
- [ ] 小节号字号 16px, 浅灰, 每行首小节显示
- [ ] 音符字号 28px, 字重 600
- [ ] 八度点半径 2.5px, 距数字 30px
- [ ] 减时线粗 1.6px, 距数字 12px
- [ ] 小节线粗 1.4px, 颜色 #333
- [ ] 力度记号斜体, 20px, 音符下方 32px
- [ ] 歌词 18px, 颜色 #555, 音符下方 22px
- [ ] 连音方括号距音符顶部 22px
- [ ] Slur 弧线距音符顶部 24px

### 9.3 测试验收

- [ ] `pytest tests/test_render.py -q`: 全部通过
- [ ] `pytest tests/test_provenance.py -q`: 全部通过
- [ ] `pytest tests/test_pipeline.py -q`: 全部通过
- [ ] `pytest tests/test_architecture.py -q`: 全部通过
- [ ] `pytest tests/test_convert.py tests/test_jianpu.py -q`: 全部通过
- [ ] `ruff format --check backend/ tests/`: 通过
- [ ] `ruff check backend/ tests/`: 通过
- [ ] `cd desktop && pnpm lint`: 通过
- [ ] `cd desktop && npx vue-tsc --noEmit`: 通过
- [ ] `cd desktop && pnpm build`: 通过

### 9.4 契约验收

- [ ] `services/render/__all__` == `{"A4MeasureRange", "RenderedA4FilePage", "RenderedA4Page", "RenderOptions", "RenderService"}`
- [ ] `drawing.__all__` 不含 `_render_beat_items`
- [ ] `utils.__all__` 不含 `_render_articulation`, `_upper_mark_anchor_y`
- [ ] `RenderService` 8 个方法签名不变
- [ ] 3 个 dataclass 字段名不变
- [ ] `RenderOptions` 旧 31 字段 + 新 11 字段全部存在
- [ ] `write_render_map(svg_path, page_index)` 签名不变
- [ ] 所有 CSS 类名保留(见 1.22)
- [ ] 所有 data 属性保留(见 1.23)

---

## 附录 A: 完整参数变更对照表

| 参数 | 位置 | 当前值 | 目标值 |
|---|---|---|---|
| **页面** | | | |
| A4_MARGIN | main.py | 64 | 85 |
| A4_LINE_HEIGHT | main.py | 160 | 180 |
| A4_TITLE_BLOCK_HEIGHT | main.py | 116 | 154 |
| A4_BOTTOM_MARGIN | main.py | 50 | 72 |
| A4_MIN_MEASURE_WIDTH | main.py | 250 | 260 |
| 页面底色 | header.py CSS | #fffdf7 | #ffffff |
| **CSS 颜色** | | | |
| text fill | header.py | #171717 | #1a1a1a |
| .bar stroke | header.py | #252525 | #333333 |
| .measure-no fill | header.py | #333 | #888 |
| .lyric fill | header.py | #5f5a52 | #555555 |
| **CSS 粗细** | | | |
| .bar stroke-width | header.py | 1.6 | 1.4 |
| .duration-line stroke-width | header.py | 1.8 | 1.6 |
| .extension-line stroke-width | header.py | 1.8 | 1.6 |
| **CSS 字号 (A4RenderTheme)** | | | |
| note_font_size | options.py | 26.0 | 28.0 |
| measure_number_font_size | options.py | 20.0 | 16.0 |
| lyric_font_size | options.py | 16.0 | 18.0 |
| dynamic_font_size | options.py | 19.0 | 20.0 |
| tuplet_font_size | options.py | 13.0 | 14.0 |
| **八度点** | | | |
| r (octave-dot) | token.py | 2.2 | 2.5 |
| 高八度点偏移 | metrics.py | 28 | 30 |
| 低八度点偏移 | metrics.py | max(6,offset-12) | 14 |
| _note_visual_top 基准 | metrics.py | y-28 | y-30 |
| **减时线** | | | |
| 基准偏移 | geometry.py | y+10 | y+12 |
| 和弦偏移 | geometry.py | +18 | +22 |
| **附点** | | | |
| r (rhythm-dot) | token.py | 3.0 | 2.8 |
| **连音** | | | |
| 方括号 Y | measure.py | token_tops-18 | token_tops-22 |
| **力度/歌词** | | | |
| 力度 Y 偏移 | beat.py | +30 | +32 |
| 歌词 Y 偏移 | beat.py | +18 | +22 |
| **Spanner** | | | |
| Slur Y 偏移 | spanners.py | -22 | -24 |

---

## 附录 B: 新增文件清单

| 文件 | 类型 | 职责 |
|---|---|---|
| `svg/theme.py` | 新增 | 视觉主题常量集中管理 |
| `engine/__init__.py` | 新增 | 引擎包初始化 |
| `engine/page.py` | 新增 | 页面几何模型 |
| `engine/line_height.py` | 新增 | 动态行高计算 |
| `engine/pagination.py` | 新增 | A4 分页算法 |

---

## 附录 C: 修改文件清单

| 文件 | 改动范围 |
|---|---|
| `main.py` | A4 常量值; `_a4_render_options` 注入新字段; `_render_a4_page`/`_render_layouts`/`_render_multi_part_a4_page` 调用新标题块+页码; `_content_min_line_height` 委托; `_paginate_rows` 委托 |
| `options.py` | RenderOptions +11 字段; A4RenderTheme +6 字段 |
| `constants.py` | +5 商业排版常量 |
| `svg/header.py` | CSS 重写; 新增 `_svg_title_block` |
| `layout/rows.py` | 新增 `_enforce_measures_per_line` |
| `drawing/token.py` | 八度点半径; 附点半径 |
| `drawing/beat.py` | 力度 Y; 歌词 Y |
| `drawing/measure.py` | 连音方括号 Y |
| `drawing/spanners.py` | Slur Y 偏移 |
| `drawing/text.py` | 多段歌词堆叠(可选) |
| `utils/metrics.py` | 高/低八度点偏移; `_note_visual_top` 基准 |
| `utils/geometry.py` | 减时线基准偏移; 和弦偏移 |

---

## 附录 D: 不变文件清单

| 文件 | 原因 |
|---|---|
| `__init__.py` | __all__ 契约不变 |
| `render_service.py` | 薄封装层不变 |
| `render_map.py` | SVG→JSON 映射不变 |
| `parsing/tokens.py` | Token 解析稳定 |
| `parsing/events.py` | Event 序列化稳定 |
| `items/factory.py` | 适配层稳定 |
| `items/grouping.py` | 分组逻辑稳定 |
| `models/shapes.py` | 数据模型不变 |
| `models/layout.py` | 布局模型不变 |
| `layout/measure.py` | 宽度算法稳定 |
| `layout/beat.py` | 槽位算法稳定 |
| `drawing/beams.py` | 参数从 CSS 控制 |
| `drawing/performance_marks.py` | 符号分发不变 |
| `utils/text.py` | 转义不变 |
| `utils/positioning.py` | 定位不变 |
| `utils/helpers.py` | 辅助不变 |
| `utils/articulations.py` | 跳音不变 |
| `utils/bars.py` | 参数已符合目标 |

---

*文档结束*
