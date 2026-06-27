# Score Trans OMR 参数使用手册

> 适用范围：后端 `/recognize` 与 `/pipeline` 接口中使用的 Audiveris OMR（光学乐谱识别）流程。
> 文档版本：2026-06-27 | 对应后端版本：0.1.0

## 1. 概述

Score Trans 的 OMR 流程负责把用户上传的**乐谱图片或 PDF** 转换成 MusicXML，核心调用的是开源 OMR 引擎 [Audiveris](https://github.com/Audiveris/audiveris)。

整个流程可简化为：

```
图片/PDF 输入
  → PDF 转 PNG（仅 PDF 输入时）
  → Audiveris 识别
  → 输出 MusicXML
```

OMR 相关参数全部集中在 `backend/score_trans/config/.env` 中，分为三大类：

| 类别 | 对应 .env 节 | 是否已接入代码 | 说明 |
|---|---|---|---|
| 外部工具路径 | 第 1 节 | ✅ 已接入 | Audiveris、JDK、工作目录等 |
| Audiveris 执行选项 | 第 1 节 | ✅ 已接入 | 控制 Audiveris 内部步骤与输出 |
| PDF 渲染参数 | 第 4 节 | ✅ 已接入 | 控制 PDF→PNG 的分辨率 |

---

## 2. 参数速查表

### 2.1 外部工具路径

| 参数名 | 默认值 | 类型 | 作用 |
|---|---|---|---|
| `SCORE_TRANS_AUDIVERIS` | `third_party/audiveris/gradlew.bat` | 路径字符串 | Audiveris 启动脚本 |
| `SCORE_TRANS_JAVA_HOME` | `E:/ENV/JAVA/JDK25` | 路径字符串 | Audiveris 运行所需的 JDK 25 根目录 |
| `SCORE_TRANS_WORKDIR` | `work` | 路径字符串 | 上传、识别、历史记录等工作目录根 |
| `SCORE_TRANS_OUTPUT_DIR` | 空 | 路径字符串 | 额外输出目录，空则使用工作目录 |

### 2.2 Audiveris 执行选项

| 参数名 | 默认值 | 类型 | 作用 |
|---|---|---|---|
| `SCORE_TRANS_AUDIVERIS_STEP` | 空 | 字符串 | 限制 Audiveris 只执行到某个步骤 |
| `SCORE_TRANS_AUDIVERIS_FORCE` | `0` | 布尔 | 强制重新识别 |
| `SCORE_TRANS_AUDIVERIS_SAVE` | `0` | 布尔 | 保存 Audiveris 内部工程文件 |
| `SCORE_TRANS_AUDIVERIS_SWAP` | `0` | 布尔 | 交换声部 |
| `SCORE_TRANS_AUDIVERIS_TRANSCRIBE` | `0` | 布尔 | 同时输出转录结果 |
| `SCORE_TRANS_AUDIVERIS_SHEETS` | 空 | 字符串 | 指定处理的乐谱页 |
| `SCORE_TRANS_AUDIVERIS_CONSTANTS` | 空 | 字符串 | 设置 Audiveris 内部常量 |
| `SCORE_TRANS_AUDIVERIS_EXTRA_ARGS` | 空 | 字符串 | 直接追加 Audiveris CLI 参数 |

### 2.3 PDF 渲染参数（OMR 输入阶段）

| 参数名 | 默认值 | 类型 | 作用 |
|---|---|---|---|
| `SCORE_TRANS_PDF_RENDER_DPI` | `220` | 整数 | PDF 渲染为 PNG 时的分辨率 |



## 3. 参数详解

### 3.1 外部工具路径

#### `SCORE_TRANS_AUDIVERIS`

- **含义**：Audiveris 的启动入口。
- **默认值**：`third_party/audiveris/gradlew.bat`
- **格式要求**：
  - Windows 下通常为 `gradlew.bat` 或编译后的 `audiveris.exe`。
  - 使用 Gradle Wrapper 时，代码会自动使用 `:app:run` 任务启动。
  - 使用独立可执行文件时，直接作为命令调用。
- **常见配置**：
  ```env
  # 使用源码/Wrapper（开发环境）
  SCORE_TRANS_AUDIVERIS=third_party/audiveris/gradlew.bat

  # 使用已编译的独立可执行文件
  SCORE_TRANS_AUDIVERIS=C:/Tools/Audiveris/bin/audiveris.exe
  ```
- **注意事项**：路径中的反斜杠建议写成正斜杠，或使用双反斜杠，避免转义问题。

#### `SCORE_TRANS_JAVA_HOME`

- **含义**：Audiveris 运行依赖的 JDK 根目录。
- **默认值**：`E:/ENV/JAVA/JDK25`
- **要求**：必须是 **JDK 25**，Audiveris 对 Java 版本要求较严格。
- **校验逻辑**：启动时会检查 `{JAVA_HOME}/bin/java.exe` 是否存在；不存在会抛出 `ExternalToolError`。
- **常见配置**：
  ```env
  SCORE_TRANS_JAVA_HOME=E:/ENV/JAVA/JDK25
  # 或
  SCORE_TRANS_JAVA_HOME=C:/Program Files/Java/jdk-25
  ```

#### `SCORE_TRANS_WORKDIR`

- **含义**：工作目录根路径，用于存放上传文件、识别中间产物、历史记录等。
- **默认值**：`work`
- **效果**：后端会在此目录下创建 `uploads/`、`pipeline/`、`audiveris/`、`history/` 等子目录。
- **建议**：确保该目录所在磁盘有足够空间，Audiveris 识别过程中可能产生较大临时文件。

#### `SCORE_TRANS_OUTPUT_DIR`

- **含义**：额外输出目录。
- **默认值**：空（使用 `SCORE_TRANS_WORKDIR`）
- **效果**：留空时，所有输出都放在工作目录下；否则可作为辅助输出位置。

---

### 3.2 Audiveris 执行选项

这些参数最终会被翻译成 Audiveris 命令行参数。代码中的映射关系如下：

```python
args = ["-batch"]
if audiveris_step:    args += ["-step", step]
if audiveris_force:   args += ["-force"]
if audiveris_save:    args += ["-save"]
if audiveris_swap:    args += ["-swap"]
if audiveris_transcribe: args += ["-transcribe"]
if audiveris_sheets:  args += ["-sheets", sheets]
for c in constants:   args += ["-constant", c]
args += extra_args
args += ["-export", "-output", output_dir, input_file]
```

#### `SCORE_TRANS_AUDIVERIS_STEP`

- **含义**：限制 Audiveris 只执行到某个处理步骤。
- **默认值**：空（执行完整流程）
- **可选值**：
  `LOAD`, `BINARY`, `SCALE`, `GRID`, `HEADERS`, `STEM_SEEDS`, `BEAMS`, `LEDGERS`, `HEADS`, `STEMS`, `REDUCTION`, `CUE_BEAMS`, `TEXTS`, `MEASURES`, `CHORDS`, `CURVES`, `SYMBOLS`, `LINKS`, `RHYTHMS`, `PAGE`
- **使用场景**：
  - 调试某个步骤失败时，可只跑到该步骤查看中间产物。
  - 例如只加载和二值化：`SCORE_TRANS_AUDIVERIS_STEP=BINARY`
- **注意事项**：一般用户保持空即可。

#### `SCORE_TRANS_AUDIVERIS_FORCE`

- **含义**：强制重新识别，忽略已有缓存结果。
- **默认值**：`0`
- **可选值**：`0` / `1`，或 `false` / `true`
- **使用场景**：
  - 修改了参数后重新识别同一文件。
  - 怀疑之前结果异常，想从头再来。
- **注意事项**：开启后会明显增加识别时间。

#### `SCORE_TRANS_AUDIVERIS_SAVE`

- **含义**：保存 Audiveris 内部 `.omr` 工程文件。
- **默认值**：`0`
- **使用场景**：
  - 需要在 Audiveris GUI 中打开工程进行人工修正。
  - 调试复杂乐谱时保留中间状态。

#### `SCORE_TRANS_AUDIVERIS_SWAP`

- **含义**：交换声部（swap voices）。
- **默认值**：`0`
- **使用场景**：
  - 多声部乐谱中，Audiveris 识别的声部顺序与预期相反时使用。

#### `SCORE_TRANS_AUDIVERIS_TRANSCRIBE`

- **含义**：同时输出转录结果。
- **默认值**：`0`
- **使用场景**：
  - 需要 Audiveris 内部转录文本时使用。
  - Score Trans 主要使用 MusicXML 输出，一般不需要开启。

#### `SCORE_TRANS_AUDIVERIS_SHEETS`

- **含义**：指定只处理 PDF/图片中的某些页。
- **默认值**：空（处理全部）
- **格式**：通常用逗号分隔页码或页码范围，例如 `1,3,5-7`。
- **使用场景**：
  - 大型乐谱只想识别其中几页。
  - 测试时减少识别时间。
- **注意事项**：具体语法请参照 Audiveris 官方文档，不同版本可能略有差异。

#### `SCORE_TRANS_AUDIVERIS_CONSTANTS`

- **含义**：设置 Audiveris 内部常量（`-constant key=value`）。
- **默认值**：空
- **格式**：多个常量用分号 `;` 或换行分隔，例如：
  ```env
  SCORE_TRANS_AUDIVERIS_CONSTANTS=minDurDivisor=2;maxPageWidth=4000
  ```
- **使用场景**：
  - 微调 Audiveris 内部算法参数，如最小音符时长、页面宽度阈值等。
- **注意事项**：需要熟悉 Audiveris 内部常量名称，不建议普通用户随意修改。

#### `SCORE_TRANS_AUDIVERIS_EXTRA_ARGS`

- **含义**：直接追加到 Audiveris 命令行的额外参数。
- **默认值**：空
- **格式**：使用类 shell 语法，支持引号，例如：
  ```env
  SCORE_TRANS_AUDIVERIS_EXTRA_ARGS=-run org.audiveris.omr.sheet.Book -option "maxLyricsCount=8"
  ```
- **使用场景**：
  - 需要使用某个 Audiveris 原生参数但 Score Trans 未提供对应环境变量时。
- **注意事项**：
  - 格式错误（如引号不成对）会抛出 `ExternalToolError`。
  - 使用前应先在命令行验证参数是否有效。

---

### 3.3 PDF 渲染参数

#### `SCORE_TRANS_PDF_RENDER_DPI`

- **含义**：PDF 输入在送入 Audiveris 前，先被渲染为 PNG 的分辨率。
- **默认值**：`220`
- **取值范围**：建议 `150` ~ `400`
- **影响**：
  - **DPI 越高**，PNG 越清晰，Audiveris 识别细节越好，但文件越大、识别越慢。
  - **DPI 越低**，速度越快，但可能导致细小符号（如临时升降号、附点）丢失。
- **推荐设置**：
  | 场景 | 推荐 DPI |
  |---|---|
  | 屏幕截图/低质量扫描 | 200 ~ 250 |
  | 普通打印扫描 | 220 ~ 300 |
  | 高质量印刷源 | 300 ~ 400 |
  | 快速测试 | 150 ~ 200 |
- **相关说明**：AI 转录模块（`/ai/transcribe`）内部默认也使用 220 DPI，但可通过 API 参数覆盖。

---


## 4. 实战调优指南

### 4.1 普通扫描乐谱

```env
SCORE_TRANS_PDF_RENDER_DPI=300
SCORE_TRANS_AUDIVERIS_FORCE=0
SCORE_TRANS_AUDIVERIS_STEP=
```

### 4.2 低质量 / 手机拍照乐谱

```env
SCORE_TRANS_PDF_RENDER_DPI=300
SCORE_TRANS_AUDIVERIS_FORCE=1
# 如果有光线不均，建议先用外部工具增强对比度后再上传
```

### 4.3 只识别 PDF 的前几页做测试

```env
SCORE_TRANS_AUDIVERIS_SHEETS=1-3
SCORE_TRANS_PDF_RENDER_DPI=150
```

### 4.4 多声部乐谱声部顺序反了

```env
SCORE_TRANS_AUDIVERIS_SWAP=1
```

### 4.5 需要保留 Audiveris 工程文件人工修正

```env
SCORE_TRANS_AUDIVERIS_SAVE=1
```

---

## 5. 常见问答

**Q1：Score Trans 是否支持上传前自动对图片做预处理？**

A：当前版本**不内置 OMR 图像预处理**。如需增强对比度、裁剪白边、二值化等，请在上传前使用 ImageMagick、Photoshop 等工具处理。

**Q2：识别总是报错找不到 Java？**

A：检查 `SCORE_TRANS_JAVA_HOME` 是否指向 JDK 25 根目录，且该目录下存在 `bin/java.exe`。

**Q3：PDF 识别速度很慢怎么办？**

A：可降低 `SCORE_TRANS_PDF_RENDER_DPI`（如改为 `150`），或限制只识别部分页码 `SCORE_TRANS_AUDIVERIS_SHEETS`。

**Q4：Audiveris 识别的 MusicXML 有错误，怎么调试？**

A：开启 `SCORE_TRANS_AUDIVERIS_SAVE=1` 保留工程文件，用 Audiveris GUI 打开查看；或设置 `SCORE_TRANS_AUDIVERIS_STEP` 分步运行。

**Q5：环境变量中布尔值怎么写？**

A：支持 `0`/`1`、`true`/`false`、`yes`/`no`、`on`/`off`，不区分大小写。

---

## 6. 相关文件

- 配置文件：`backend/score_trans/config/.env`
- 配置示例：`backend/score_trans/config/env.example`
- 配置加载：`backend/score_trans/config/settings.py`
- Audiveris 调用：`backend/score_trans/services/recognize/external_tools.py`
- 识别 Action：`backend/score_trans/exec/recognize/actions.py`
- 项目架构总览：[architecture.md](./architecture.md)
- 已知问题：[issues.md](./issues.md)
