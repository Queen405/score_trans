# Audiveris 项目调研报告

> 调研日期：2026-06-30
> 调研对象：[Audiveris/audiveris](https://github.com/Audiveris/audiveris) —— 开源 OMR（光学乐谱识别）引擎
> 调研目的：为 Score Trans 项目的 OMR 集成提供技术参考与背景知识
> 信息来源：GitHub 仓库、官方 Handbook（audiveris.github.io/audiveris）、Context7 文档库、本项目集成源码

---

## ⚠️ 重要安全提示

> **`https://audiveris.com`（注意是 `.com`）是钓鱼/欺诈站点，与本项目毫无关系。**
> 该站点外观仿冒 Audiveris 官方，但链接会跳转到加密货币、体育博彩等页面。
> 正确的官方资源是：
> - 仓库：`https://github.com/Audiveris/audiveris`
> - 文档：`https://audiveris.github.io/audiveris/`

---

## 1. 项目概览

| 指标 | 数值 |
|---|---|
| 定位 | 开源光学乐谱识别（OMR）引擎 |
| GitHub | `Audiveris/audiveris` |
| Stars / Forks | 2.6k / 377 |
| 提交数 | 5,972 |
| 许可证 | **AGPL-3.0**（注意：传染性开源协议，分发或网络服务均需开源） |
| 主语言 | Java 96.0%、XSLT 3.6%、其他 0.4% |
| 最新稳定版 | **5.10.2**（2026-03-27，"Bug fix for biased notes"） |
| 历史版本数 | 23 个 release |
| 平台支持 | Windows / Linux / macOS |
| 架构限制 | **仅 64 位**（deeplearning4j 依赖所致） |

**核心目标**：把乐谱图像（score image）转写成符号化的音乐数据（symbolic counterpart），从而支持播放、编辑、检索、再出版等后续数字化处理。

---

## 2. 技术架构

### 2.1 双核设计：引擎 + 编辑器

Audiveris 的设计哲学是 **"100% 识别率不可能达成"**，因此采用两个紧密集成的组件：

1. **OMR 引擎（Engine）**：执行自动识别流水线。
2. **OMR 编辑器（Editor）**：让用户在识别前后进行人工干预——既可在转录前预设处理开关（switches）来适配特定乐谱，也可在转录后快速修正少量符号错误。

> 这个"引擎+编辑器"的组合，正是 Score Trans 这类自动化流水线项目只能利用引擎能力、而把纠错压力转嫁到后续 MusicXML→简谱转换或 AI 转录上的根本原因。

### 2.2 分治识别技术

引擎对不同实体采用不同识别手段：

| 实体类型 | 识别技术 |
|---|---|
| 线条（lines） | ad-hoc 方法 |
| 符干束（beams） | 图像形态学闭运算（morphological closing） |
| 文字（texts） | 由 Score Trans Python OCR 服务处理 |
| 符头（note heads） | 模板匹配（template matching） |
| 其他固定尺寸形状 | 神经网络（neural network） |

### 2.3 数据格式

- **核心 OMR 数据**：完全文档化并公开，可通过两种途径访问
  - 基于 XML 的 `.omr` 工程文件（包含五线谱线等物理细节）
  - Java API
- **导出格式**：**MusicXML 4.0**，通过内置 exporter 输出 `.mxl` 文件（MusicXML 的 zip 归档）
  - MusicXML 是音乐应用间符号数据交换的标准，但**缺少 OMR 擅长的物理细节**（如五线谱线定义）
  - 高质量导出依赖高精度 OMR 结果，残余错误不可避免

---

## 3. 处理流水线（约 20 步）

OMR 引擎对每个 sheet（页面）执行约 20 个**有序**步骤。可用 `-step <STEP>` 提前终止，默认跑完全部流程。

| 序 | 步骤 | 作用 |
|---|---|---|
| 1 | `LOAD` | 获取页面灰度图 |
| 2 | `BINARY` | 二值化灰度图 |
| 3 | `SCALE` | 估算五线谱线宽、行距（interline）、beam 厚度 |
| 4 | `GRID` | 检索五线谱线、小节线、系统与声部 |
| 5 | `HEADERS` | 检索谱号、调号、拍号系统头 |
| 6 | `STEM_SEEDS` | 检索符干厚度与种子 |
| 7 | `BEAMS` | 检索符干束 |
| 8 | `LEDGERS` | 检索加线 |
| 9 | `HEADS` | 检索符头 |
| 10 | `STEMS` | 检索连接符头与束的符干 |
| 11 | `REDUCTION` | 消除符头/符干/束的冲突 |
| 12 | `CUE_BEAMS` | 检索提示性符干束 |
| 13 | `TEXTS` | 保留步骤槽位；当前不执行文字识别 |
| 14 | `MEASURES` | 从小节线组合检索原始小节 |
| 15 | `CHORDS` | 把符头聚集成和弦 |
| 16 | `CURVES` | 检索连音线、渐强渐弱、反复段落线 |
| 17 | `SYMBOLS` | 检索固定形状符号 |
| 18 | `LINKS` | 连接并精简符号 |
| 19 | `RHYTHMS` | 处理小节内节奏 |
| 20 | `PAGE` | 连接页面内的系统 |

### 3.1 步骤间的依赖

- **`SCALE` 与 `STEM_SEEDS`** 通过垂直游程长度（vertical run length）的直方图推断缩放数据。
- **`GRID`、`BEAMS`、`STEMS`** 等步骤的行为严重依赖上述缩放数据的准确性。

### 3.2 性能参考（官方 StopWatch 示例）

单页（"chula"）总耗时约 **28.5 秒**，耗时占比 TOP 3：

| 步骤 | 耗时 | 占比 |
|---|---|---|
| HEADS | 6.7s | 23.5% |
| BEAMS | 5.0s | 17.6% |
| GRID | 3.6s | 12.7% |

> 启示：Score Trans 若做超时/性能调优，HEADS/BEAMS/GRID 是主要成本来源；用 `-step` 限制步骤可显著加速调试。

---

## 4. 安装与运行

### 4.1 三种安装方式

**方式 A：官方安装包（5.5 起，推荐普通用户）**
内置 JRE，开箱即用：

| OS | 安装包扩展 |
|---|---|
| Windows | `.msi` |
| Linux | `.deb` |
| macOS | `.dmg` |

**方式 B：Linux Flatpak** —— 从 [Flathub](https://flathub.org/apps/org.audiveris.audiveris) 安装。

**方式 C：源码编译（Score Trans 采用的方式）**

依赖工具：`git` + `gradle`（用 wrapper 自动管理版本）+ `JDK`。

```bash
git clone https://github.com/Audiveris/audiveris.git
cd audiveris
gradle build          # Linux/macOS/Cygwin
# Windows: gradlew.bat build
./gradlew run         # 启动 GUI
```

### 4.2 JDK 版本要求

| 分支 | JDK 要求 |
|---|---|
| `master`（仅用于 release） | **JDK 25**（`gradle.properties` 中 `theMinJavaVersion = 25`） |
| `development`（持续开发） | 可能需要更新的 JDK |

> Score Trans 项目要求 **JDK 25**，对应 master 分支的最低版本。JDK 路径通过 `SCORE_TRANS_JAVA_HOME` 配置。

### 4.3 Git 工作流

- `master`：仅承载 release，稳定。
- `development`：所有持续开发发生于此，定期合并入 master 发版。

---

## 5. 命令行接口（CLI）

### 5.1 语法

```
audiveris [OPTIONS] [--] [INPUT_FILES]
```

输入文件：`.omr`（工程文件）或任意图像（PNG/PDF/TIFF 等）。

### 5.2 主要选项

| 选项 | 说明 |
|---|---|
| `-batch` | 无 GUI 运行（自动化集成必选） |
| `-export` | 导出 MusicXML |
| `-output <dir>` | 指定输出目录 |
| `-step <step>` | 执行到指定步骤为止 |
| `-force` | 强制重新处理 |
| `-save` | 批量模式每步成功后保存 |
| `-swap` | 页面处理后换出（节省内存，适合大谱） |
| `-transcribe` | 转录整本书 |
| `-sheets <int[]>` | 选择页面，如 `1 4-5` |
| `-constant key=value` | 定义应用常量（算法微调） |
| `-playlist <file.xml>` | 从播放列表构建复合书 |
| `-print` | 打印书 |
| `-upgrade` | 升级整本书文件 |
| `-version` / `-help` | 显示版本 / 帮助 |
| `-run <class>` | （高级）在有效 sheet 上运行指定类 |
| `-sample` / `-annotate` | （高级）采样/标注所有符号 |

---

## 6. 与 Score Trans 的集成现状

### 6.1 集成形态

- **内嵌源码**：Audiveris 以源码形式置于 `third_party/audiveris/`，通过 `gradlew.bat` 运行（非预编译 exe）。
- **调用方式**：subprocess，非 Java 原生集成。
- **服务封装**：`services/recognize/audiveris_service.py`（薄封装，9 行）→ `services/recognize/external_tools.py:recognize_with_audiveris()`（实际实现）。
- **数据流定位**：Pipeline 全流程的 OMR 环节，产出 MusicXML 供后续 `MusicXmlToJianpuAction` 消费。

### 6.2 调用实现要点（`external_tools.py`）

```
recognize_with_audiveris()
  ├── _java_env()           # 构造 JAVA_HOME/PATH，处理代理透传、捆绑 Gradle 缓存
  ├── _audiveris_args()     # 拼接 -batch / -step / -force / -export / -output / -constant ...
  └── _run()                # subprocess.run(capture_output, check=True)
```

**命令拼接逻辑（关键）**：自动识别启动入口类型

- 若路径名为 `gradlew` / `gradlew.bat`（本项目默认）：
  ```
  gradlew.bat --no-daemon :app:run -PcmdLineArgs=-batch,...,-export,-output,<dir>,<input>
                     -PaudiverisMaxHeap=<2g>
  ```
- 否则（预编译 `audiveris.exe`）：直接 `audiveris <args>`。

Gradle Wrapper 调用固定追加 `--no-daemon`。该命令行参数优先于 `gradle.properties` 中的 Daemon 配置，
因此不需要修改内置 Audiveris 工程。代价是每次识别都要重新经历 Gradle/JVM 冷启动和配置阶段，
实际增加时间取决于机器与缓存，通常为秒级；OMR 主处理通常占更长时间。这样可以避免 Score Trans
新建长期驻留的 Gradle/JVM。Windows 退出时仍由 Electron 的进程树清理兜底，macOS/Linux 则由
后端子进程的终止信号回收本次调用的 JVM；不对任意外部孙进程作强制级联保证。

**输出回收**：扫描输出目录的 `*.musicxml` → `*.mxl` → `*.xml`，取第一个；若无则抛 `ExternalToolError`。

### 6.3 环境变量映射

本项目通过 `.env` 环境变量封装了 Audiveris 绝大多数能力（详见 [`docs/omr_parameters_manual.md`](omr_parameters_manual.md)）：

| 本项目环境变量 | 映射到 Audiveris | 说明 |
|---|---|---|
| `SCORE_TRANS_AUDIVERIS` | 启动入口 | 默认 `third_party/audiveris/gradlew.bat` |
| `SCORE_TRANS_JAVA_HOME` | `JAVA_HOME` | 必须 JDK 25 |
| `SCORE_TRANS_AUDIVERIS_STEP` | `-step` | 限制流水线步骤 |
| `SCORE_TRANS_AUDIVERIS_FORCE` | `-force` | 强制重处理 |
| `SCORE_TRANS_AUDIVERIS_SAVE` | `-save` | 保存 `.omr` 工程（供 GUI 纠错） |
| `SCORE_TRANS_AUDIVERIS_SWAP` | `-swap` | 换出页面（大谱省内存） |
| `SCORE_TRANS_AUDIVERIS_TRANSCRIBE` | `-transcribe` | 转录整书 |
| `SCORE_TRANS_AUDIVERIS_SHEETS` | `-sheets` | 选择页面 |
| `SCORE_TRANS_AUDIVERIS_CONSTANTS` | `-constant key=value` | 算法常量（`;` 分隔） |
| `SCORE_TRANS_AUDIVERIS_EXTRA_ARGS` | 任意 CLI | shlex 解析后追加（兜底） |
| `SCORE_TRANS_AUDIVERIS_MAX_PIXEL_COUNT` | `-constant maxPixelCount=` | 大图保护 |
| `SCORE_TRANS_AUDIVERIS_MAX_HEAP` | `-PaudiverisMaxHeap` | 1g/2g/3g/4g |

### 6.4 健壮性设计（本项目独有）

- **JDK 路径预校验**：调用前检查 `bin/java.exe` 存在，无效即抛 `ExternalToolError`，不延后到首次调用。
- **代理透传**：自动读取 `https_proxy`/`http_proxy` 并写入 `JAVA_TOOL_OPTIONS`（JVM 下载依赖时需要）。
- **捆绑 Gradle 缓存**：打包时由 `build-app.py` 预填充 `third_party/gradle_home`，避免离线/首次构建卡住。
- **堆内存校验**：`maxHeap` 仅允许 `1g/2g/3g/4g`。
- **参数格式校验**：`EXTRA_ARGS` 用 shlex 解析，引号不匹配时报错。

---

## 7. 局限性与注意事项

### 7.1 识别能力局限

- **100% 识别率不可达**：印刷质量、扫描质量导致残余错误不可避免，这是 OMR 领域的本质问题，非 Audiveris 缺陷。
- **MusicXML 导出损失物理信息**：五线谱线等细节在 MusicXML 中无法表达，意味着"返回符号层、丢失排版层"。
- **文字识别职责分离**：Audiveris 不再执行 `TEXTS` 文字识别；标题、歌词、排练号、和弦名、
  速度文字由 Score Trans Python OCR 服务按图片文字块返回。`f`、`mf` 等标准力度记号属于
  Audiveris OMR 符号分类，仍由 `SYMBOLS`/MusicXML 路径处理。

### 7.2 运行时局限

- **强依赖 JDK 25**：版本敏感，低版本直接失败。
- **仅 64 位**：32 位 JVM 无法运行（deeplearning4j 限制）。
- **内存敏感**：大谱需配合 `-swap` 与较大 `maxHeap`。
- **首次启动慢**：源码模式下 Gradle 首次构建耗时较长（本项目用捆绑缓存缓解）。

### 7.3 协议风险

- **AGPL-3.0 传染性**：若将 Score Trans 作为网络服务对外提供，需注意 Audiveris 的 AGPL 义务（开源衍生作品）。本项目为**本地桌面应用**，分发时需确保符合 AGPL 要求（如随附源码声明、LICENSE 文件）。

---

## 8. 对 Score Trans 的改进建议

| 方向 | 建议 | 优先级 |
|---|---|---|
| 性能 | 用 `-step` 提供"快速预览"模式（如只到 `CHORDS`），先给用户草稿 | 中 |
| 调试 | 暴露 `-save` 的 `.omr` 工程文件下载，便于用户在 Audiveris GUI 中人工纠错后回灌 | 中 |
| 稳定性 | 对 `HEADS`/`BEAMS`/`GRID` 等耗时步骤加超时与进度反馈 | 中 |
| 容错 | 识别失败时，自动降级到 AI 视觉转录（`/ai/transcribe` 已具备能力） | 高 |
| 版本 | 跟踪 `development` 分支关键改进，但 master 仍是最稳选择 | 低 |
| 协议 | 在应用"关于"页明确标注 Audiveris 及其 AGPL-3.0 许可 | 高 |

---

## 9. 参考链接

- 仓库：<https://github.com/Audiveris/audiveris>
- 用户手册：<https://audiveris.github.io/audiveris/>
- 项目结构：<https://github.com/Audiveris/audiveris/blob/master/project-structure.md>
- Wiki：<https://github.com/Audiveris/audiveris/wiki>
- Releases：<https://github.com/Audiveris/audiveris/releases>
- Flatpak：<https://flathub.org/apps/org.audiveris.audiveris>
- 本项目集成源码：
  - `backend/score_trans/services/recognize/external_tools.py`
  - `backend/score_trans/services/recognize/audiveris_service.py`
- 本项目参数手册：[`docs/omr_parameters_manual.md`](omr_parameters_manual.md)
