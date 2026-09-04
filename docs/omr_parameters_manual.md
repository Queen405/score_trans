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

> 这些参数属于环境变量级配置，由 `.env` 控制，不进入发布默认配置基线（`published_defaults.json`），也不写入用户数据库种子。`SettingsService.load()` 直接从环境变量读取，不经 `SettingsDao`。如需修改，编辑 `.env` 文件。

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
| `SCORE_TRANS_AUDIVERIS_AUTO_UPSCALE` | `1` | 布尔 | 自动放大低分辨率光栅图（目标长边见下） |
| `SCORE_TRANS_AUDIVERIS_MIN_IMAGE_EDGE` | `2500` | 整数 | 自动放大的目标长边像素数 |
| `SCORE_TRANS_AUDIVERIS_MAX_PIXEL_COUNT` | `4500000` | 整数 | 大图保护上限，超过则先缩放 |
| `SCORE_TRANS_AUDIVERIS_MAX_HEAP` | `3g` | 字符串 | Audiveris JVM 堆上限，仅 `1g`/`2g`/`3g`/`4g` |

### 2.3 PDF 渲染参数（OMR 输入阶段）

| 参数名 | 默认值 | 类型 | 作用 |
|---|---|---|---|
| `SCORE_TRANS_PDF_RENDER_DPI` | `300` | 整数 | PDF 渲染为 PNG 时的分辨率 |



## 3. Audiveris CLI 参数对照

Score Trans 并不直接暴露 Audiveris 的命令行界面，而是把相关选项封装成了 `.env` 中的环境变量。实际运行时，后端会按以下规则拼接出 Audiveris CLI 参数：

```python
args = ["-batch"]
if config.audiveris_step:    args += ["-step", step]
if config.audiveris_force:   args += ["-force"]
if config.audiveris_save:    args += ["-save"]
if config.audiveris_swap:    args += ["-swap"]
if config.audiveris_transcribe: args += ["-transcribe"]
if config.audiveris_sheets:  args += ["-sheets", sheets]
for c in constants:          args += ["-constant", c]
args += extra_args
args += ["-export", "-output", output_dir, input_file]
```

### 3.1 已映射的 Audiveris CLI 参数

| Audiveris CLI 参数 | 对应环境变量 | 默认值 | 说明 |
|---|---|---|---|
| `-batch` | 固定启用 | — | 批处理模式，不启动 GUI |
| `-step <STEP>` | `SCORE_TRANS_AUDIVERIS_STEP` | 空 | 只执行到指定处理步骤 |
| `-force` | `SCORE_TRANS_AUDIVERIS_FORCE` | 未启用 | 强制重新识别 |
| `-save` | `SCORE_TRANS_AUDIVERIS_SAVE` | 未启用 | 保存 `.omr` 工程文件 |
| `-swap` | `SCORE_TRANS_AUDIVERIS_SWAP` | 未启用 | 交换声部 |
| `-transcribe` | `SCORE_TRANS_AUDIVERIS_TRANSCRIBE` | 未启用 | 输出内部转录结果 |
| `-sheets <SPEC>` | `SCORE_TRANS_AUDIVERIS_SHEETS` | 空 | 指定处理的乐谱页 |
| `-constant <KEY=VALUE>` | `SCORE_TRANS_AUDIVERIS_CONSTANTS` | 空 | 设置 Audiveris 内部常量 |
| `-export` | 固定启用 | — | 导出 MusicXML |
| `-output <DIR>` | 由代码生成 | `work/audiveris/...` | 输出目录 |
| 任意参数 | `SCORE_TRANS_AUDIVERIS_EXTRA_ARGS` | 空 | 兜底追加 |

### 3.2 实际命令示例

以 Gradle Wrapper 启动方式为例，若设置了 `SCORE_TRANS_AUDIVERIS_STEP=BINARY` 和 `SCORE_TRANS_AUDIVERIS_FORCE=1`，后端会生成类似命令：

```bash
gradlew.bat --no-daemon :app:run -PcmdLineArgs=-batch,-step,BINARY,-force,-export,-output,work/audiveris/xxx,page.png
```

若使用独立可执行文件，则类似：

```bash
audiveris -batch -step BINARY -force -export -output work/audiveris/xxx page.png
```

### 3.3 支持的 `-step` 取值

Audiveris 的完整处理流水线包含多个步骤，可用 `-step` 提前终止：

| 步骤名 | 说明 |
|---|---|
| `LOAD` | 加载输入图像 |
| `BINARY` | 二值化 |
| `SCALE` | 估算谱线间距 |
| `GRID` | 检测谱表系统 |
| `HEADERS` | 识别谱号、调号、拍号 |
| `STEM_SEEDS` | 识别符干种子 |
| `BEAMS` | 识别符杠 |
| `LEDGERS` | 识别加线 |
| `HEADS` | 识别符头 |
| `STEMS` | 识别符干 |
| `REDUCTION` | 合并符头与符干 |
| `CUE_BEAMS` | 识别弱拍符杠 |
| `TEXTS` | 保留步骤槽位，不执行文字 OCR（文字由 Python OCR 服务处理） |
| `MEASURES` | 识别小节 |
| `CHORDS` | 识别和弦 |
| `CURVES` | 识别连音线、圆滑线 |
| `SYMBOLS` | 识别其他符号 |
| `LINKS` | 链接符号关系 |
| `RHYTHMS` | 节奏分析 |
| `PAGE` | 完整页面处理 |

> 默认不指定 `-step` 时，Audiveris 会跑完整个流水线。

### 3.4 `-constant` 常用项

Audiveris 内部有大量可调整的算法常量，格式为 `-constant key=value`。多个常量用 `;` 分隔写入环境变量。

| 常量名 | 示例值 | 说明 |
|---|---|---|
| `minDurDivisor` | `2` | 最小时值除数 |
| `maxPageWidth` | `4000` | 页面最大宽度像素 |
| `maxLyricsCount` | `8` | 最大歌词行数 |
| `beamMinSlope` | `0.05` | 符杠最小斜率 |

> 完整常量列表和含义请参考 [Audiveris 官方文档](https://audiveris.github.io/audiveris/) 或源码中的 `omr/constant` 包。

### 3.5 Audiveris 原生参数速查

除 Score Trans 已映射的参数外，Audiveris 还支持一些原生 CLI 参数。当环境变量无法满足需求时，可通过 `SCORE_TRANS_AUDIVERIS_EXTRA_ARGS` 追加。常见选项包括：

| 原生参数 | 说明 |
|---|---|
| `-help` | 打印帮助信息 |
| `-version` | 打印版本信息 |
| `-run <CLASS>` | 运行指定 Java 类 |
| `-option <KEY=VALUE>` | 设置某些运行期选项 |
| `-debug` | 提高日志详细程度 |
| `-verbose` | 输出更多信息 |

> 建议先在本地命令行运行 `audiveris -help` 或 `gradlew.bat :app:run -PcmdLineArgs=-help` 查看当前版本支持的完整参数列表。

---

## 4. 参数详解

### 4.1 外部工具路径

#### `SCORE_TRANS_AUDIVERIS`

- **含义**：Audiveris 的启动入口。
- **默认值**：`third_party/audiveris/gradlew.bat`
- **格式要求**：
  - Windows 下通常为 `gradlew.bat` 或编译后的 `audiveris.exe`。
  - 使用 Gradle Wrapper 时，代码会自动使用 `:app:run` 任务启动。
  - Wrapper 调用固定追加 `--no-daemon`，优先级高于 `gradle.properties`，避免识别后留下长期 Gradle JVM。
  - 该参数会带来秒级的 Gradle/JVM 冷启动开销，实际耗时取决于机器与缓存；换取退出后的资源释放。
  - macOS/Linux 同样不创建长期 Daemon；现有后端终止信号负责回收本次调用的 JVM，但不保证任意外部孙进程级联退出。
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

### 4.2 Audiveris 执行选项

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
  `TEXTS` 即使被执行也只是兼容性空操作，不会生成歌词、标题或其他普通文字的 MusicXML
  元素。

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
- **默认值**：`300`
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
- **相关说明**：AI 转录模块（`/ai/transcribe`）内部默认也使用 300 DPI，但可通过 API 参数覆盖。

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

A：**支持**。`SCORE_TRANS_AUDIVERIS_AUTO_UPSCALE`（默认 `1`）会在调用 Audiveris 前对低分辨率光栅图自动放大到 `SCORE_TRANS_AUDIVERIS_MIN_IMAGE_EDGE`（默认 `2500`）像素长边；`SCORE_TRANS_AUDIVERIS_MAX_PIXEL_COUNT`（默认 `4500000`）则对超大图先缩放再做大图保护。PDF 输入按 `SCORE_TRANS_PDF_RENDER_DPI` 渲染为 PNG 后同样经过该链路。

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
- 发布默认基线：`backend/score_trans/config/published_defaults.json`
- 配置加载：`backend/score_trans/config/settings.py`
- 默认种子加载：`backend/score_trans/services/settings/defaults.py`
- Audiveris 调用：`backend/score_trans/services/recognize/external_tools.py`
- 识别 Action：`backend/score_trans/exec/recognize/actions.py`
- 项目架构总览：[architecture.md](./architecture.md)
- 已知问题：[issues.md](./issues.md)
