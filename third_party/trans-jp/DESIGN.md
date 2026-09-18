# trans-jp 引擎设计文档

> 2026-09-17：本文保留初始设计记录；当前实现、依赖规则和输出行为以 [ARCHITECTURE.md](ARCHITECTURE.md) 与 [README.md](README.md) 为准。下文旧的矩形覆盖和扁平模块示例不再是实现入口。

> 简谱图片识别引擎 — 通过视觉大模型逐行识别简谱图片，输出简谱文本 + 来源映射 + SVG 叠加层。

## 1. 概述

`trans-jp` 是 Score Trans 项目中用于**简谱图片识别**的独立引擎，放置在 `third_party/trans-jp/`，与 `third_party/audiveris/`（五线谱 OMR 引擎）平级。后端通过 subprocess 调用本引擎（与调用 Audiveris 完全同构）。

### 1.1 工作流程

```
简谱图片 (PNG/JPG)
  │
  ▼ 图像预处理
  ├── 灰度化 + Otsu 二值化（仅用于分割）
  ├── 中值滤波去噪
  │
  ▼ 行分割
  ├── 水平投影 → 检测行间隙 → 裁剪行图片
  │
  ▼ 逐行 LLM 识别（并发，默认 2 并发）
  ├── 每行图片 → 视觉大模型 → JSON
  │     {row_type, row_text, tokens: [{text, x, w, role}]}
  │
  ▼ 合并 + 产物生成
  ├── 拼接行文本 → jianpu.txt
  ├── 构建 text_anchors.json（source_id → UTF-16 文本位置）
  ├── 生成 score-link-map.json（source_id → 图像 bounds + hit_path）
  └── 生成 overlay.svg（半透明矩形 + 文字标注）
```

### 1.2 与 Audiveris 的对应关系

| 维度 | Audiveris | trans-jp |
|---|---|---|
| 目录 | `third_party/audiveris/` | `third_party/trans-jp/` |
| 技术栈 | Java / Gradle | Python |
| 调用方式 | `java -cp "*" Audiveris @args` | `python -m trans_jp --input ... --output-dir ...` |
| 输入 | 五线谱图片/PDF | 简谱图片 |
| 识别引擎 | OMR（图像分析） | 视觉大模型 API |
| MusicXML | ✓ | ✗（直接输出简谱文本） |
| .omr 文件 | ✓ | ✗ |
| source-link-map.json | ✓（Audiveris 原生导出） | ✓（引擎自行生成） |
| overlay | PNG | SVG |
| source_id 格式 | `s{sheet}:i{inter}` | `s{sheet}:r{row}:t{token}` |

### 1.3 source_id 格式

```
s{sheet_index}:r{row_index}:t{token_index}
```

- `s0:r0:t0` = 第 0 页第 0 行的第 0 个 token
- `s0:r2:t5` = 第 0 页第 2 行的第 5 个 token

当前仅支持单张图片，`sheet_index` 恒为 0；格式中预留 sheet 段，
未来支持多页 PDF 时无需变更 ID 结构，历史数据保持兼容。

与 Audiveris 的 `s{sheet}:i{inter}` 格式平行，前端 `OriginalPreview.vue` 无需修改即可加载。

---

## 2. 目录结构

```
third_party/trans-jp/
├── pyproject.toml                    # 包定义 + CLI 入口 + 依赖
├── DESIGN.md                         # 本文档
├── README.md                         # 用户文档
├── trans_jp/
│   ├── __init__.py
│   ├── __main__.py                   # python -m trans_jp 入口
│   ├── cli.py                        # argparse + 主编排
│   ├── schemas.py                    # 所有 dataclass 数据模型
│   ├── config/
│   │   └── prompt.yaml               # Prompt 模板 + JSON schema + 语法规则（包内资源）
│   ├── image_processor.py            # 灰度 + Otsu 二值化 + 去噪 + 低分辨率放大
│   ├── line_segmenter.py             # 水平投影 → 行分割
│   ├── llm_client.py                 # OpenAI-compatible vision API 客户端
│   ├── prompt_builder.py             # 加载 prompt.yaml + 格式化
│   ├── json_parser.py                # 容错 JSON 解析
│   ├── row_recognizer.py             # 逐行 LLM 调用 + 并发执行
│   ├── text_merger.py                # 拼接行文本 + 构建 text_anchors
│   ├── source_map_builder.py         # score-link-map.json 生成
│   ├── overlay_generator.py          # SVG 叠加层生成
│   └── utf16.py                      # UTF-16 长度计算
├── examples/
│   └── sample_jianpu.png             # 测试用简谱图片
└── tests/
    ├── conftest.py                   # 共享 fixtures
    ├── test_image_processor.py
    ├── test_line_segmenter.py
    ├── test_json_parser.py
    ├── test_row_recognizer.py
    ├── test_text_merger.py
    ├── test_source_map_builder.py
    ├── test_overlay_generator.py
    └── test_cli.py
```

> **包内 prompt 配置**：`prompt.yaml` 必须放在 `trans_jp/config/` 包目录内，
> 通过 `importlib.resources` 读取。setuptools `package-data` 不支持包外路径
> （`../config/*.yaml` 是无效配置），这是初版设计中的一个错误，已修正。

---

## 3. CLI 接口

### 3.1 命令格式

```bash
python -m trans_jp \
  --input <image_path> \
  --output-dir <output_directory> \
  --api-key <api_key> \
  --base-url <api_base_url> \
  --model <model_name> \
  --target-key <target_key> \
  [--title <title>] \
  [--extra-prompt <extra_prompt>] \
  [--prompt-config <yaml_path>] \
  [--max-tokens <int>] \
  [--temperature <float>] \
  [--timeout <float>] \
  [--concurrency <int>] \
  [--min-image-edge <int>] \
  [--debug]
```

`--api-key` / `--base-url` / `--model` 也可通过环境变量
`TRANS_JP_API_KEY` / `TRANS_JP_BASE_URL` / `TRANS_JP_MODEL` 提供
（在 `cli.py` 模块全局作用域读取，命令行参数优先）。

### 3.2 参数说明

| 参数 | 必填 | 默认值 | 说明 |
|---|---|---|---|
| `--input` | 是 | — | 输入简谱图片路径（PNG/JPG） |
| `--output-dir` | 是 | — | 输出目录路径 |
| `--api-key` | 是 | — | LLM API 密钥 |
| `--base-url` | 是 | — | LLM API 基地址（OpenAI 兼容） |
| `--model` | 是 | — | 模型名称 |
| `--target-key` | 否 | `C` | 目标调号（如 C, G, F） |
| `--title` | 否 | `None` | 曲名提示 |
| `--extra-prompt` | 否 | `None` | 额外识别要求（注入 prompt 模板 `{extra_prompt}` 占位符） |
| `--prompt-config` | 否 | 内置默认 | Prompt YAML 配置路径，可指向后端 `ai_prompt.yaml` |
| `--max-tokens` | 否 | `4096` | LLM 最大输出 token 数 |
| `--temperature` | 否 | `0.1` | LLM 温度参数 |
| `--timeout` | 否 | `120.0` | 单次 LLM 请求超时（秒） |
| `--concurrency` | 否 | `2` | 并发行识别数 |
| `--min-image-edge` | 否 | `2500` | 行图片发送给 LLM 前的目标长边像素数（0 表示不放大；仅放大行图片，source map 坐标仍基于原图，token 位置是相对比例不受影响） |
| `--debug` | 否 | `False` | 启用调试日志 |

### 3.3 输出文件

```
<output_dir>/
├── jianpu.txt              # 完整简谱文本（UTF-8）
├── score-link-map.json     # SourceMap（与 Audiveris 同格式）
├── overlay.svg             # SVG 叠加层
├── text_anchors.json       # TextAnchor 列表
├── rows/                   # 分割的行图片（调试用）
│   ├── row_0.png
│   ├── row_1.png
│   └── ...
└── trans-jp.log            # 执行日志
```

### 3.4 退出码

| 退出码 | 含义 |
|---|---|
| 0 | 成功 |
| 1 | 图片加载失败 |
| 2 | 行分割未找到任何行 |
| 3 | LLM API 调用全部失败 |
| 4 | 输出目录写入失败 |
| 5 | 参数错误 |

---

## 4. 数据模型（`schemas.py`）

所有数据模型使用 `@dataclass(slots=True)`，与项目后端约定一致。

### 4.1 RowSegment

```python
@dataclass(slots=True)
class RowSegment:
    """检测到的一行简谱区域。"""

    index: int  # 行号（从 0 开始）
    y_top: int  # 在原图中的上边缘 y 坐标（像素）
    y_bottom: int  # 在原图中的下边缘 y 坐标（像素）
    image_path: Path  # 裁剪后的行图片路径
    width: int  # 行图片宽度（像素）
    height: int  # 行图片高度（像素）
```

### 4.2 RecognizedToken

```python
@dataclass(slots=True)
class RecognizedToken:
    """LLM 识别到的一个符号。"""

    index: int  # 在当前行中的序号（从 0 开始）
    text: str  # token 文本（row_text 的连续子串）
    x: float  # 左边缘水平比例（0.0-1.0，相对于行图片宽度）
    w: float  # 宽度比例（0.0-1.0）
    role: str  # 角色（见 §5.3 token role 定义）
    y: float | None = None  # 可选：上边缘垂直比例（相对于行高），缺省为整行
    h: float | None = None  # 可选：高度比例（相对于行高），缺省为整行
```

`y`/`h` 为预留的可选字段：当前 prompt 只要求 LLM 输出水平位置，
token 的垂直范围默认占满整行高度。未来若需要更精细的垂直定位
（如区分上下排声线），可在 prompt 中要求 LLM 输出 y/h，
source map 与 overlay 已支持该字段，向后兼容。

### 4.3 RowResult

```python
@dataclass(slots=True)
class RowResult:
    """一行的识别结果。"""

    row: RowSegment
    row_type: str  # header / notation / lyrics / other
    jianpu_text: str  # 当前行的简谱文本
    tokens: list[RecognizedToken]  # 识别到的 token 列表
    key: str | None  # 检测到的调号（如 "C"）
    meter: str | None  # 检测到的拍号（如 "4/4"）
    tempo: str | int | None  # 检测到的速度
    title: str | None  # 检测到的标题
    warnings: list[str]  # 警告信息
    confidence: float | None  # 整体置信度（0.0-1.0）
```

### 4.4 TransJpResult

```python
@dataclass(slots=True)
class TransJpResult:
    """完整识别结果。"""

    jianpu_text: str
    rows: list[RowResult]
    source_map: dict  # score-link-map.json 内容
    overlay_svg: str  # overlay.svg 内容
    text_anchors: list[dict]  # text_anchors.json 内容
    warnings: list[str]
```

### 4.5 LlmConfig / CliConfig

```python
@dataclass(slots=True)
class LlmConfig:
    api_key: str
    base_url: str
    model: str
    max_tokens: int = 4096
    temperature: float = 0.1
    timeout: float = 120.0


@dataclass(slots=True)
class CliConfig:
    input_path: Path
    output_dir: Path
    llm: LlmConfig
    target_key: str = "C"
    title: str | None = None
    extra_prompt: str | None = None
    prompt_config: Path | None = None
    concurrency: int = 2
    min_image_edge: int = 2500
    debug: bool = False
```

`schemas.py` 同时提供 `make_source_id(row, token, sheet=0)` 生成
`s{sheet}:r{row}:t{token}` 格式的 source_id，`text_merger` 与
`source_map_builder` 共用，保证两侧 ID 一致。

---

## 5. Prompt 设计

### 5.1 配置文件

`config/prompt.yaml` 是引擎的核心配置，包含以下字段：

| 字段 | 说明 |
|---|---|
| `system_message` | LLM 系统消息，定义角色 |
| `row_prompt_template` | 行级识别的 prompt 模板 |
| `row_transcription_rules` | 行级转写要求 |
| `syntax_rules` | 完整简谱语法规则（从项目 `ai_prompt.yaml` 复制） |
| `hard_constraints` | 硬性约束（从项目 `ai_prompt.yaml` 复制） |
| `json_schema` | 期望的 JSON 输出格式 |
| `title_hint_template` | 标题提示模板 |
| `extra_prompt_template` | 额外要求模板 |

### 5.2 行级 prompt 模板

```yaml
row_prompt_template: |
  请识别这一行简谱图片中的内容，只返回 JSON，不要输出任何其他内容。

  这是第 {row_index} 行（共 {total_rows} 行）。
  目标调号：1={target_key}
  {title_hint}
  {extra_prompt}

  【简谱语法规则】
  {syntax_rules}

  【行级识别要求】
  {row_transcription_rules}

  【硬性约束】
  {hard_constraints}

  【行类型判断】
  1. "header"：这一行只包含调号(1=C)、拍号(4/4)、速度(tempo=85)、标题(title=曲名)等声明
  2. "notation"：这一行包含音符、休止符、小节线等乐谱内容
  3. "lyrics"：这一行是 L: 开头的歌词
  4. "other"：其他文字标注（如力度术语、演奏说明）

  如果一行同时有头部声明和音符内容，row_type 设为 "notation"，
  并在 row_text 中把头部声明放在音符之前。

  【token 位置要求】
  1. 为每个 token 估计其在图片中的水平位置。
     x = token 左边缘的水平比例（0.0=最左，1.0=最右）
     w = token 宽度比例（0.0-1.0）
  2. tokens 按**从左到右的阅读顺序**排列。
  3. 位置不需要像素级精确，但应接近实际位置以便视觉对照。
  4. 每个 token 的 text 必须是 row_text 中的连续子串。

  【token role 取值】
  - note：音符（含时值前缀、升降号、八度标记、附点、延长线）
  - rest：休止符 0
  - barline：小节线 |、||、|:、:|、反复 *N
  - chord：和弦 [1+3+5]
  - tuplet：连音组 $...$
  - slur：圆滑线 ( )
  - tie：延音线 ~
  - dynamic：力度 \p \f \mf 等
  - articulation：演奏记号 ^> ^- ^. ^r ^f ^l 等
  - header_key：调号 1=C
  - header_meter：拍号 4/4
  - header_tempo：速度 tempo=85
  - header_title：标题 title=曲名
  - lyrics：歌词 L: ...
  - other：其他

  JSON 格式：
  {json_schema}
```

### 5.3 token role 定义

| role | 说明 | overlay 颜色 |
|---|---|---|
| `note` | 音符（1-7）及其附加的时值前缀(w/h/q/s/d)、升降号(#/b/n)、八度标记('/,)、附点(.)、延长线(-) | `#00aa44` 绿色 |
| `rest` | 休止符 0 | `#888888` 灰色 |
| `barline` | 小节线 \|、\|\|、\|:、:\|、反复次数 *N | `#0066ff` 蓝色 |
| `chord` | 和弦 [1+3+5] | `#00aa44` 绿色 |
| `tuplet` | 连音组 $...$ | `#cc00cc` 紫色 |
| `slur` | 圆滑线 ( ) | `#0088cc` 青色 |
| `tie` | 延音线 ~ | `#0088cc` 青色 |
| `dynamic` | 力力标记 \p \f \mf \ff 等 | `#ff8800` 橙色 |
| `articulation` | 演奏记号 ^> ^- ^. ^r ^f ^l 等 | `#aaaa00` 黄色 |
| `header_key` | 调号 1=C | `#4488ff` 浅蓝 |
| `header_meter` | 拍号 4/4 | `#4488ff` 浅蓝 |
| `header_tempo` | 速度 tempo=85 | `#4488ff` 浅蓝 |
| `header_title` | 标题 title=曲名 | `#4488ff` 浅蓝 |
| `lyrics` | 歌词 L: ... | `#ff66aa` 粉色 |
| `other` | 其他 | `#888888` 灰色 |

### 5.4 JSON 输出格式

```json
{
  "row_type": "notation",
  "key": null,
  "meter": null,
  "tempo": null,
  "title": null,
  "row_text": "1 2 3 4 | 5 6 7 1' |",
  "tokens": [
    {"text": "1", "x": 0.05, "w": 0.04, "role": "note"},
    {"text": "2", "x": 0.12, "w": 0.04, "role": "note"},
    {"text": "3", "x": 0.19, "w": 0.04, "role": "note"},
    {"text": "4", "x": 0.26, "w": 0.04, "role": "note"},
    {"text": "|", "x": 0.33, "w": 0.02, "role": "barline"},
    {"text": "5", "x": 0.40, "w": 0.04, "role": "note"},
    {"text": "6", "x": 0.47, "w": 0.04, "role": "note"},
    {"text": "7", "x": 0.54, "w": 0.04, "role": "note"},
    {"text": "1'", "x": 0.61, "w": 0.06, "role": "note"},
    {"text": "|", "x": 0.70, "w": 0.02, "role": "barline"}
  ],
  "warnings": [],
  "confidence": 0.9
}
```

**header 行示例**:

```json
{
  "row_type": "header",
  "key": "C",
  "meter": "4/4",
  "tempo": 85,
  "title": "欢乐颂",
  "row_text": "title=欢乐颂\n1=C\n4/4\ntempo=85",
  "tokens": [
    {"text": "title=欢乐颂", "x": 0.10, "w": 0.15, "role": "header_title"},
    {"text": "1=C", "x": 0.30, "w": 0.08, "role": "header_key"},
    {"text": "4/4", "x": 0.45, "w": 0.06, "role": "header_meter"},
    {"text": "tempo=85", "x": 0.60, "w": 0.10, "role": "header_tempo"}
  ],
  "warnings": [],
  "confidence": 0.95
}
```

**lyrics 行示例**:

```json
{
  "row_type": "lyrics",
  "key": null,
  "meter": null,
  "tempo": null,
  "title": null,
  "row_text": "L: 春 风 又 绿 江南岸",
  "tokens": [
    {"text": "L:", "x": 0.02, "w": 0.04, "role": "lyrics"},
    {"text": "春", "x": 0.10, "w": 0.04, "role": "lyrics"},
    {"text": "风", "x": 0.16, "w": 0.04, "role": "lyrics"},
    {"text": "又", "x": 0.22, "w": 0.04, "role": "lyrics"},
    {"text": "绿", "x": 0.28, "w": 0.04, "role": "lyrics"},
    {"text": "江南岸", "x": 0.34, "w": 0.12, "role": "lyrics"}
  ],
  "warnings": [],
  "confidence": 0.95
}
```

### 5.5 外部 prompt 配置

`--prompt-config` 可指向后端的 `ai_prompt.yaml`。此时 `prompt_builder.py` 会：

1. 加载外部 YAML
2. 使用外部 YAML 的 `syntax_rules`、`hard_constraints`、`transcription_rules`（如果有）
3. 仍使用 `trans-jp` 自身的 `row_prompt_template` 和 `json_schema`

这样语法规则只有一份源（后端 `ai_prompt.yaml`），`trans-jp` 默认自带副本用于独立运行。

---

## 6. 各模块详细设计

### 6.1 image_processor.py

**职责**: 加载图片，生成灰度图和二值化图。

```
load_image(path: Path) → (original: PIL.Image, binary: numpy.ndarray)
  1. PIL.Image.open(path) → 原图
  2. img.convert("L") → 灰度图
  3. numpy.array(gray) → numpy 数组
  4. Otsu 阈值二值化 → binary (黑=0, 白=255)
  5. PIL.ImageFilter.MedianFilter(size=3) → 去噪
  6. return (original, binary)
```

**Otsu 二值化**:
- 计算灰度直方图
- 遍历所有可能的阈值，找到使类间方差最大的阈值
- 或使用 `cv2.threshold(..., cv2.THRESH_OTSU)` 如果 OpenCV 可用
- 简化实现：`PIL.Image.point(lambda x: 0 if x < threshold else 255, "1")`

**关键决策**:
- 二值化图**仅用于水平投影分析**
- 发送给 LLM 的是从**原图**裁剪的行图片（或轻度增强后的图片）
- LLM 对原图的识别效果通常优于二值化图

### 6.2 line_segmenter.py

**职责**: 将二值化图分割成**逻辑行**（两阶段：墨迹带检测 → 垂直分组）。

> **为什么不能按墨迹带直接切**：简谱的一个"乐谱行"由多个垂直叠放的细带组成——
> 数字带、时值横线带（仅 2-6px 高）、高/低八度点带、力度记号（p/f）、
> 上方的圆滑线弧线。若按墨迹带切成独立行图，LLM 拿到的数字条会丢失
> 时值线、八度点和力度记号，时值识别必然失败；多声部（上下两排并行旋律）
> 也会被拆散。因此必须先检测细带，再按垂直间距分组成逻辑行。

```
segment(binary, original, rows_dir, *, coord_scale=1.0, ...) → list[RowSegment]
  1. row_sums = numpy.sum(binary == 0, axis=1)          # 每行的暗像素数
  2. 平滑滤波（窗口 5）
  3. threshold = max(row_sums) * 0.05                   # 低阈值，确保细带（时值线/点）也被检出
  4. 找 row_sums > threshold 的连续区间 → 细墨迹带
  5. 过滤 < 2px 的噪声细带
  6. group_gap = max(12px, 0.8 × 细带高度中位数)
     相邻细带间距 < group_gap → 合并为同一逻辑行
     （数字+时值线+八度点+力度记号合并；歌词行间距较大时仍独立成行）
  7. 过滤原始高度 < 12px 的逻辑行（隔离噪点）
  8. padding：每行向外扩展 max(6px, 25% 行高)，
     上下各截断在相邻行间隙的中点（保住圆滑线弧线，且不与邻行重叠）
  9. 从工作图裁剪 (0, y_top, width, y_bottom) → rows_dir/row_{index}.png
  10. y_top/y_bottom 除以 coord_scale 换算回原图坐标存入 RowSegment
```

**参数说明**（均为工作图坐标系下的像素值）:

| 参数 | 默认值 | 说明 |
|---|---|---|
| 平滑窗口 | 5 | 移动平均窗口大小（像素） |
| 内容阈值比例 | 0.05 | `max(row_sums) * ratio`，足够低以检出时值线/八度点细带 |
| 最小细带高度 | 2px | 低于此值的细带视为噪点丢弃 |
| 分组间隙比例 | 0.8 | `group_gap = max(最小分组间隙, 0.8 × 细带高度中位数)` |
| 最小分组间隙 | 12px | group_gap 下限 |
| padding 比例 | 0.25 | 每行向外扩展 25% 行高（下限 6px），截断在邻行间隙中点 |
| 最小行高 | 12px | 分组后原始高度低于此值的行过滤（分组**前**过滤，避免 padding 复活噪点） |

**与图像预处理的配合**：`image_processor.prepare_work_image` 在行分割**之前**
对整图做预防性放大（长边 → `--min-image-edge`，默认 2500，上限 4 倍），
低分辨率扫描件的细带高度随之放大，上述绝对像素阈值才能稳定工作；
`coord_scale` 把行坐标映射回原图，保证 source map / overlay 与原图对齐。

### 6.3 llm_client.py

**职责**: 调用 OpenAI 兼容的视觉 LLM API。

```python
class LlmClient:
    def __init__(self, config: LlmConfig, system_message: str):
        self._config = config
        self._system_message = system_message

    def transcribe_row(self, image_path: Path, prompt: str) -> str:
        """Send row image + prompt, return raw LLM content string."""
        image_url = _image_to_data_url(image_path)
        messages = [
            {"role": "system", "content": self._system_message},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            },
        ]
        resp = httpx.post(
            f"{self._config.base_url}/chat/completions",
            json={...},
            headers={...},
            timeout=httpx.Timeout(...),
        )
        resp.raise_for_status()
        return _extract_content(resp.json())

    def transcribe_row_with_retry(
        self, image_path: Path, prompt: str, *, max_retries: int = 1
    ) -> str:
        """Call transcribe_row, retry on failure or truncation."""
        # 复用 _vision.py 的截断重试模式：
        # 1. 如果 finish_reason == "length"，用紧凑 prompt 重试
        # 2. 如果 HTTP 错误，等待后重试一次
```

**`_image_to_data_url`**:
- 复用后端 `utils/media.py` 的模式
- 大图（> 2000px 长边）缩放 + JPEG 85% 压缩
- 小图直接 base64 编码

### 6.4 json_parser.py

**职责**: 容错解析 LLM 返回的 JSON。

```python
def parse_row_response(content: str) -> dict:
    """Parse LLM JSON response, tolerating wrapper text and truncation."""
    # 策略链（复用后端 json_parsing.py 模式）:
    # 1. 剥离 markdown 代码块 ```json ... ```
    # 2. 直接 json.loads
    # 3. 失败 → 正则提取 {...} 再解析
    # 4. 失败 → 截断修复（补全引号和括号）
    # 5. 验证必填字段，填充默认值
    # 6. 规范化 token x/w 到 [0, 1] 范围
    # 7. 确保 tokens 按 index 排序
```

**必填字段验证**:

| 字段 | 默认值 |
|---|---|
| `row_type` | `"notation"` |
| `key` | `None` |
| `meter` | `None` |
| `tempo` | `None` |
| `title` | `None` |
| `row_text` | `""` |
| `tokens` | `[]` |
| `warnings` | `["JSON response missing required fields"]` |
| `confidence` | `None` |

**token 规范化**:
- `x` clamp 到 `[0.0, 1.0]`
- `w` clamp 到 `[0.01, 1.0]`
- `x + w > 1.0` 时 `w = 1.0 - x`
- 缺少 `x`/`w` 的 token 默认等间距分布

### 6.5 prompt_builder.py

**职责**: 加载 prompt 配置，格式化行级 prompt。

```python
class PromptBuilder:
    def __init__(self, prompt_config_path: Path | None = None):
        # 加载 config/prompt.yaml（或 --prompt-config 指定的路径）
        # 如果指定了外部配置且有 syntax_rules/hard_constraints，用外部的
        # 否则用内置默认

    def build_row_prompt(self, *, row_index, total_rows, target_key, title, extra_prompt) -> str:
        # 格式化 row_prompt_template
        # 填入 syntax_rules, row_transcription_rules, hard_constraints, json_schema
        # 填入 title_hint, extra_prompt
```

### 6.6 row_recognizer.py

**职责**: 逐行调用 LLM，支持并发。

```python
def recognize_rows(
    rows: list[RowSegment],
    llm_client: LlmClient,
    prompt_builder: PromptBuilder,
    *,
    target_key: str,
    title: str | None,
    concurrency: int = 2,
    progress_callback=None,
) -> list[RowResult]:
    """Recognize all rows, optionally in parallel."""
    results: list[RowResult | None] = [None] * len(rows)

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        future_to_index = {
            executor.submit(
                _recognize_single_row,
                row,
                llm_client,
                prompt_builder,
                row_index=row.index,
                total_rows=len(rows),
                target_key=target_key,
                title=title,
            ): row.index
            for row in rows
        }
        for future in as_completed(future_to_index):
            index = future_to_index[future]
            try:
                results[index] = future.result()
            except Exception as exc:
                results[index] = _error_row_result(rows[index], str(exc))

    return results
```

**并发策略**:
- `ThreadPoolExecutor` — I/O 密集场景，线程池即可
- 默认 `concurrency=2`
- 单行失败**不中断**整体流程，返回带 warning 的 error RowResult
- 结果**按 `row.index` 有序**返回（不是完成顺序）

**单行识别流程**:

```
_recognize_single_row(row, llm_client, prompt_builder, ...):
  1. prompt = prompt_builder.build_row_prompt(row_index, total_rows, ...)
  2. raw_content = llm_client.transcribe_row_with_retry(row.image_path, prompt)
  3. parsed = json_parser.parse_row_response(raw_content)
  4. 构建 RowResult:
     - row_type = parsed["row_type"]
     - jianpu_text = parsed["row_text"]
     - tokens = [RecognizedToken(i, t["text"], t["x"], t["w"], t["role"]) for i, t in ...]
     - key, meter, tempo, title = parsed[...]
     - warnings = parsed["warnings"]
     - confidence = parsed["confidence"]
```

**错误降级**:

```python
def _error_row_result(row: RowSegment, error_message: str) -> RowResult:
    """Failed row → placeholder with warning."""
    return RowResult(
        row=row,
        row_type="other",
        jianpu_text="",  # 空文本
        tokens=[],  # 无 token
        key=None,
        meter=None,
        tempo=None,
        title=None,
        warnings=[f"行 {row.index} 识别失败: {error_message}"],
        confidence=None,
    )
```

### 6.7 text_merger.py

**职责**: 拼接行文本，构建 text_anchors。

```python
def merge_rows(row_results: list[RowResult]) -> tuple[str, list[dict]]:
    """Merge row texts into complete jianpu text + text anchors."""
    merged_text = ""
    anchors: list[dict] = []

    for row_result in row_results:
        if not row_result.jianpu_text:
            continue

        # 确保行间有换行
        if merged_text and not merged_text.endswith("\n"):
            merged_text += "\n"

        row_start = len(merged_text)
        merged_text += row_result.jianpu_text

        # 在 row_text 中逐 token 查找位置
        search_pos = 0
        for token in row_result.tokens:
            found = _find_token_in_text(token.text, row_result.jianpu_text, search_pos)
            if found is not None:
                start_cp, end_cp = found
                anchors.append(
                    {
                        "source_id": make_source_id(row_result.row.index, token.index),
                        "start_utf16": utf16_length(
                            merged_text[: row_start + start_cp]
                        ),
                        "end_utf16": utf16_length(merged_text[: row_start + end_cp]),
                        "role": token.role,
                        "valid": True,
                    }
                )
                search_pos = end_cp
            else:
                anchors.append(
                    {
                        "source_id": make_source_id(row_result.row.index, token.index),
                        "start_utf16": utf16_length(
                            merged_text[: row_start + search_pos]
                        ),
                        "end_utf16": utf16_length(
                            merged_text[: row_start + search_pos]
                        ),
                        "role": token.role,
                        "valid": False,
                    }
                )

    return merged_text, anchors
```

**`_find_token_in_text`**:

```python
def _find_token_in_text(
    token_text: str, row_text: str, start: int
) -> tuple[int, int] | None:
    """Sequential search for token_text in row_text starting from `start`."""
    pos = row_text.find(token_text, start)
    if pos >= 0:
        return pos, pos + len(token_text)
    return None
```

- 顺序查找：从前一个 token 的结束位置开始搜索下一个 token
- 前提：tokens 按从左到右的阅读顺序排列
- 查找失败时 anchor 标记为 `valid: False`，但 source map 中仍保留位置（overlay 可用）

### 6.8 source_map_builder.py

**职责**: 生成 `score-link-map.json`（与 Audiveris 同格式）。

```python
def build_source_map(
    row_results: list[RowResult],
    image_width: int,
    image_height: int,
    overlay_filename: str = "overlay.svg",
) -> dict:
    elements = []
    for row_result in row_results:
        row = row_result.row
        row_height = row.y_bottom - row.y_top
        for token in row_result.tokens:
            x = max(0.0, token.x) * image_width
            w = max(1.0, token.w) * image_width
            x = min(x, image_width - 1)
            w = min(w, image_width - x)
            elements.append(
                {
                    "source_id": make_source_id(row.index, token.index),
                    "inter_id": token.index,
                    "shape": token.role.upper(),
                    "grade": row_result.confidence or 0.5,
                    "bounds": {
                        "x": x,
                        "y": row.y_top,
                        "width": w,
                        "height": row_height,
                    },
                    "hit_path": (
                        f"M{x},{row.y_top} "
                        f"L{x + w},{row.y_top} "
                        f"L{x + w},{row.y_bottom} "
                        f"L{x},{row.y_bottom} Z"
                    ),
                    "musicxml_locator": {"attribute": "id", "contains": ""},
                }
            )

    return {
        "version": 1,
        "sheets": [
            {
                "sheet_index": 0,
                "width": image_width,
                "height": image_height,
                "overlay_file": overlay_filename,
                "elements": elements,
            }
        ],
    }
```

**输出格式**（与 Audiveris `score-link-map.json` 完全一致）:

```json
{
  "version": 1,
  "sheets": [{
    "sheet_index": 0,
    "width": 1200,
    "height": 800,
    "overlay_file": "overlay.svg",
    "elements": [
      {
        "source_id": "s0:r0:t0",
        "inter_id": 0,
        "shape": "NOTE",
        "grade": 0.9,
        "bounds": {"x": 60, "y": 50, "width": 48, "height": 30},
        "hit_path": "M60,50 L108,50 L108,80 L60,80 Z",
        "musicxml_locator": {"attribute": "id", "contains": ""}
      }
    ]
  }]
}
```

### 6.9 overlay_generator.py

**职责**: 生成 SVG 叠加层，在原图位置上显示识别到的 token。

```python
def generate_overlay_svg(
    row_results: list[RowResult],
    image_width: int,
    image_height: int,
) -> str:
    """Generate transparent SVG overlay showing recognized tokens."""
    # SVG with viewBox="0 0 {width} {height}"
    # For each token:
    #   - Semi-transparent rectangle (color by role)
    #   - Text label (token text) at center
```

**SVG 结构**:

```xml
<svg xmlns="http://www.w3.org/2000/svg"
     viewBox="0 0 1200 800" width="1200" height="800">
  <style>
    rect.token { fill-opacity: 0.12; stroke-width: 1.5; }
    text.token-label { font-size: 14px; font-family: monospace; text-anchor: middle; }
  </style>
  <rect class="token" x="60" y="50" width="48" height="30"
        fill="#00aa44" stroke="#00aa44" opacity="0.5"/>
  <text class="token-label" x="84" y="65" fill="#00aa44">1</text>
  <rect class="token" x="144" y="50" width="48" height="30"
        fill="#00aa44" stroke="#00aa44" opacity="0.5"/>
  <text class="token-label" x="168" y="65" fill="#00aa44">2</text>
  ...
</svg>
```

### 6.10 cli.py

**职责**: CLI 入口，编排全流程。

```python
def main():
    args = parse_args()
    setup_logging(args.output_dir / "trans-jp.log", debug=args.debug)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # 1. 图像预处理
    log.info("开始图像预处理")
    original, binary = image_processor.load_image(args.input)
    img_w, img_h = original.size
    log.info(f"图片尺寸: {img_w}x{img_h}")

    # 2. 行分割
    log.info("开始行分割")
    rows_dir = args.output_dir / "rows"
    rows_dir.mkdir(parents=True, exist_ok=True)
    rows = line_segmenter.segment(binary, original, rows_dir)
    if not rows:
        log.error("行分割未找到任何行")
        sys.exit(2)
    log.info(f"检测到 {len(rows)} 行")

    # 3. 逐行 LLM 识别（并发）
    log.info(f"开始逐行识别（并发: {args.concurrency}）")
    llm = LlmClient(args.llm, system_message)
    prompt_builder = PromptBuilder(args.prompt_config)
    row_results = row_recognizer.recognize_rows(
        rows,
        llm,
        prompt_builder,
        target_key=args.target_key,
        title=args.title,
        concurrency=args.concurrency,
    )
    total_tokens = sum(len(r.tokens) for r in row_results)
    log.info(f"识别完成: {total_tokens} 个 token")

    # 4. 合并文本 + text anchors
    log.info("合并文本")
    merged_text, text_anchors = text_merger.merge_rows(row_results)
    log.info(f"合并文本: {len(merged_text)} 字符, {len(text_anchors)} 个 anchor")

    # 5. 生成 source map
    log.info("生成 source map")
    source_map = source_map_builder.build_source_map(
        row_results,
        img_w,
        img_h,
        "overlay.svg",
    )

    # 6. 生成 overlay SVG
    log.info("生成 overlay SVG")
    overlay_svg = overlay_generator.generate_overlay_svg(
        row_results,
        img_w,
        img_h,
    )

    # 7. 写出产物
    log.info("写出产物")
    (args.output_dir / "jianpu.txt").write_text(merged_text, encoding="utf-8")
    (args.output_dir / "score-link-map.json").write_text(
        json.dumps(source_map, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (args.output_dir / "overlay.svg").write_text(overlay_svg, encoding="utf-8")
    (args.output_dir / "text_anchors.json").write_text(
        json.dumps(text_anchors, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    warnings = [w for r in row_results for w in r.warnings]
    if warnings:
        log.warning(f"识别有 {len(warnings)} 个警告")
        for w in warnings:
            log.warning(f"  {w}")

    log.info("trans-jp 完成")
```

### 6.11 utf16.py

```python
def utf16_length(text: str) -> int:
    """Count UTF-16 code units in a Python string.

    BMP characters = 1 code unit, supplementary characters = 2 code units.
    """
    return len(text.encode("utf-16-le")) // 2
```

与后端 `domain/parse/jianpu_text.py` 的 `_utf16_length` 实现完全一致，保证 text_anchors 的位置编码与前端兼容。

---

## 7. 输出格式

### 7.1 jianpu.txt

纯文本，UTF-8 编码。遵循项目简谱语法。

```
title=欢乐颂
1=C
4/4
tempo=85
1 2 3 4 | 5 6 7 1' |
2 3 4 5 | 6 7 1' 2' |
3 4 5 6 | 7 1' 2' 3' |
L: 春 风 又 绿 江南岸
```

### 7.2 score-link-map.json

```json
{
  "version": 1,
  "sheets": [{
    "sheet_index": 0,
    "width": 1200,
    "height": 800,
    "overlay_file": "overlay.svg",
    "elements": [
      {
        "source_id": "s0:r0:t0",
        "inter_id": 0,
        "shape": "HEADER_TITLE",
        "grade": 0.95,
        "bounds": {"x": 120, "y": 10, "width": 180, "height": 30},
        "hit_path": "M120,10 L300,10 L300,40 L120,40 Z",
        "musicxml_locator": {"attribute": "id", "contains": ""}
      },
      {
        "source_id": "s0:r1:t0",
        "inter_id": 0,
        "shape": "NOTE",
        "grade": 0.9,
        "bounds": {"x": 60, "y": 100, "width": 48, "height": 30},
        "hit_path": "M60,100 L108,100 L108,130 L60,130 Z",
        "musicxml_locator": {"attribute": "id", "contains": ""}
      }
    ]
  }]
}
```

### 7.3 text_anchors.json

```json
[
  {
    "source_id": "s0:r0:t0",
    "start_utf16": 0,
    "end_utf16": 12,
    "role": "header_title",
    "valid": true
  },
  {
    "source_id": "s0:r1:t0",
    "start_utf16": 30,
    "end_utf16": 31,
    "role": "note",
    "valid": true
  }
]
```

### 7.4 overlay.svg

```xml
<svg xmlns="http://www.w3.org/2000/svg"
     viewBox="0 0 1200 800" width="1200" height="800">
  <style>...</style>
  <rect class="token" x="60" y="100" width="48" height="30"
        fill="#00aa44" stroke="#00aa44" opacity="0.5"/>
  <text class="token-label" x="84" y="115" fill="#00aa44">1</text>
  ...
</svg>
```

---

## 8. pyproject.toml

```toml
[project]
name = "trans-jp"
version = "0.1.0"
description = "Jianpu image recognition engine using vision LLM"
requires-python = ">=3.11"
dependencies = [
    "pillow>=10.0",
    "numpy>=1.26",
    "httpx>=0.27",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
test = ["pytest>=8"]

[project.scripts]
trans-jp = "trans_jp.cli:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["."]

[tool.setuptools.package-data]
trans_jp = ["config/*.yaml"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

---

## 9. 测试策略

### 9.1 测试分类

| 测试文件 | 测试内容 | 需要 API? |
|---|---|---|
| `test_image_processor.py` | 灰度化、Otsu 二值化、去噪 | 否 |
| `test_line_segmenter.py` | 合成图片的行分割、边界检测、行裁剪 | 否 |
| `test_json_parser.py` | JSON 解析容错：markdown 块、截断、缺失字段、token 规范化 | 否 |
| `test_row_recognizer.py` | Mock LlmClient，验证 RowResult 构建、并发顺序、失败降级 | 否 |
| `test_text_merger.py` | 行文本拼接、token 位置查找、anchor 构建、UTF-16 计算 | 否 |
| `test_source_map_builder.py` | bounds 计算、hit_path 生成、source_id 格式、越界保护 | 否 |
| `test_overlay_generator.py` | SVG 结构、颜色映射、坐标正确 | 否 |
| `test_cli.py` | 端到端：合成图片 + Mock LlmClient → 验证所有输出文件 | 否 |

### 9.2 conftest.py 共享 fixtures

```python
@pytest.fixture
def synthetic_jianpu_image(tmp_path) -> Path:
    """生成一张带文字的合成简谱图片。"""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (800, 400), "white")
    draw = ImageDraw.Draw(img)
    # 绘制两行简谱内容
    draw.text((50, 20), "1=C  4/4", fill="black")
    draw.text((50, 100), "1 2 3 4 | 5 6 7 1' |", fill="black")
    draw.text((50, 200), "2 3 4 5 | 6 7 1' 2' |", fill="black")
    path = tmp_path / "sample.png"
    img.save(path)
    return path


@pytest.fixture
def mock_llm_response() -> str:
    """预设的 LLM JSON 响应。"""
    return json.dumps(
        {
            "row_type": "notation",
            "row_text": "1 2 3 4 |",
            "tokens": [
                {"text": "1", "x": 0.05, "w": 0.04, "role": "note"},
                {"text": "2", "x": 0.12, "w": 0.04, "role": "note"},
                {"text": "3", "x": 0.19, "w": 0.04, "role": "note"},
                {"text": "4", "x": 0.26, "w": 0.04, "role": "note"},
                {"text": "|", "x": 0.33, "w": 0.02, "role": "barline"},
            ],
            "warnings": [],
            "confidence": 0.9,
        }
    )


class MockLlmClient:
    """Mock LLM client for testing."""

    def __init__(self, response: str):
        self._response = response

    def transcribe_row_with_retry(self, image_path, prompt, **kwargs):
        return self._response
```

### 9.3 测试要点

**image_processor**:
- 加载 PNG/JPG
- 二值化后前景/背景分明
- 去噪后孤立噪点消除

**line_segmenter**:
- 合成图片有 3 行内容 → 分割出 3 行
- 行间隙正确检测
- 裁剪图片尺寸正确

**json_parser**:
- 纯 JSON 解析
- markdown 代码块剥离
- 截断 JSON 修复
- 缺失字段填充默认值
- token x/w 越界 clamp

**row_recognizer**:
- 单行识别返回正确 RowResult
- 多行并发结果按 index 有序
- 单行失败不影响其他行
- Mock LlmClient 返回正确数据

**text_merger**:
- 两行文本正确拼接
- token 在 row_text 中查找位置
- anchor 的 UTF-16 位置正确
- 查找失败的 token 标记 valid=False

**source_map_builder**:
- bounds 坐标计算正确
- hit_path 格式正确
- source_id 格式 `s{sheet}:r{row}:t{token}`
- x/w 越界保护

**overlay_generator**:
- SVG 结构合法
- 颜色按 role 映射
- 矩形和文字坐标正确

**cli**:
- 端到端：合成图片 + Mock → 4 个输出文件都生成
- jianpu.txt 内容正确
- score-link-map.json 格式正确
- overlay.svg 是合法 SVG
- text_anchors.json 格式正确

---

## 10. 安装与运行

### 10.1 安装

```bash
# 安装到项目 venv（开发模式）
uv pip install -e third_party/trans-jp --python .venv/Scripts/python.exe
```

### 10.2 运行

```bash
# 设置环境变量
export TRANS_JP_API_KEY="sk-xxx"
export TRANS_JP_BASE_URL="https://api.openai.com/v1"
export TRANS_JP_MODEL="gpt-4o"

# 运行
python -m trans_jp \
  --input examples/sample_jianpu.png \
  --output-dir ./.test-work/trans-jp-output \
  --api-key "$TRANS_JP_API_KEY" \
  --base-url "$TRANS_JP_BASE_URL" \
  --model "$TRANS_JP_MODEL" \
  --target-key C \
  --concurrency 2

# 检查输出
cat ./.test-work/trans-jp-output/jianpu.txt
python -m json.tool ./.test-work/trans-jp-output/score-link-map.json
python -m json.tool ./.test-work/trans-jp-output/text_anchors.json
```

### 10.3 测试

```bash
cd third_party/trans-jp
python -m pytest -v
```

---

## 11. 后端集成约定

本节是与 Score Trans 后端集成的契约说明（后端代码不在本引擎范围内）。

### 11.1 稳定性边界

引擎对外的**唯一契约**是输出目录中的 4 个产物文件：

| 文件 | 格式 | 后端消费方式 |
|---|---|---|
| `jianpu.txt` | 项目简谱语法纯文本 | 写入编辑器 / 注册为文本文件 |
| `score-link-map.json` | `models/provenance/schemas.py` 的 `SourceMap` | 注册为 `source_map_file_id` |
| `overlay.svg` | 透明 SVG | 注册为 **`overlay_svg_file_id`** |
| `text_anchors.json` | `TextAnchor` 列表 | 直接反序列化 |

引擎内部不 import `score_trans` 的任何模块；后端只做产物适配。

### 11.2 overlay 注册路径（重要）

后端 `OverlayService.find_native_overlay()` 强制校验 overlay 文件为 `.png`
后缀（`services/overlay/overlay_service.py`），该路径仅适用于 Audiveris
原生 PNG overlay。**trans-jp 的 `overlay.svg` 必须走后端自行生成 SVG 的
注册路径**（与 `_generate_overlay` 一致，写入 `overlay_svg_file_id`），
不能调用 `find_native_overlay`。

### 11.3 进程调用约定

- 开发态：`uv pip install -e third_party/trans-jp` 到项目 venv 后，
  后端用同一 venv 的 `sys.executable -m trans_jp ...` 调用。
- 打包态：约定环境变量 `SCORE_TRANS_TRANS_JP_PYTHON` 指向嵌有 trans-jp 的
  Python 解释器；缺省时回退到 `sys.executable`。
- 后端通过 `--api-key/--base-url/--model` 显式传参（对应
  `SCORE_TRANS_OCR_*` 配置），不依赖引擎进程继承环境变量。

---

## 12. 实现顺序

| 步骤 | 文件 | 内容 |
|---|---|---|
| 1 | `pyproject.toml` + `trans_jp/__init__.py` + `schemas.py` + `utf16.py` | 包定义 + 数据模型 + 工具函数 |
| 2 | `image_processor.py` | 灰度 + Otsu + 去噪 |
| 3 | `line_segmenter.py` | 水平投影 + 行分割 + 行裁剪 |
| 4 | `json_parser.py` | 容错 JSON 解析 |
| 5 | `trans_jp/config/prompt.yaml` | 完整 prompt 配置（含语法规则，包内资源） |
| 6 | `prompt_builder.py` | 加载 YAML + 格式化 |
| 7 | `llm_client.py` | httpx 客户端 + data URL + 重试 |
| 8 | `row_recognizer.py` | 逐行识别 + 并发 |
| 9 | `text_merger.py` | 文本拼接 + anchor 构建 |
| 10 | `source_map_builder.py` | SourceMap JSON 生成 |
| 11 | `overlay_generator.py` | SVG 叠加层 |
| 12 | `cli.py` + `__main__.py` | CLI 编排 |
| 13 | `tests/` | 全部单元测试 + 端到端测试 |
| 14 | 手动验证 | 真实简谱图片 + 真实 API key |

## 2026-09-17 架构重构说明

当前实现采用独立引擎的分层组合根：`pipeline.runner` 是唯一完整流程入口，`cli.py` 仅负责参数和退出码适配。模型 DTO 位于 `models/`；栅格算法位于 `raster/`；结构分析位于 `structure/`；简谱语义解析位于 `symbols/`；视觉模型调用位于 `recognition/`；token/候选匹配位于 `matching/`；输出位于 `rendering/` 与 `provenance/`。

线段检测参考 Audiveris 的 Run → Section → Filament → Projection 思路，但没有复制 Java 实现，也没有引入五线谱 staff 模型。横线检测输出斜率、厚度和支持率，处理数字打断与轻微倾斜；竖线检测在局部 notation band 投影中验证高度和连续性。行结构输出基线曲线，工作图坐标通过可逆 Transform 还原到源图。

新输出仍兼容 `jianpu.txt`、`overlay.svg`、`score-link-map.json` 与 `text_anchors.json`，并提供 `overlay-preview.png`、`overlay-debug.svg`、`overlay-diagnostics.json`。SourceMap 只包含有可靠几何的 token；文本锚点可以包含未定位 token。旧模块路径只保留兼容导入。
