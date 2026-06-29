# Score Trans

五线谱与简谱互转的 Windows 本地桌面原型。

## 功能

- 导入图片或 PDF，通过 Audiveris 调用 OMR，生成 MusicXML。
- 导入 MusicXML，转换为简谱文本。
- 输入简谱文本，生成基础 MusicXML。
- 调用 MuseScore Studio CLI，把 MusicXML 导出为 PDF、PNG、MIDI 等格式。

## 架构

当前桌面界面只保留 Electron + Vue3，Python 侧只保留 FastAPI 后端、领域逻辑和外部工具编排：

```text
backend/score_trans/
  api/          FastAPI 路由层：只声明 HTTP 接口并委托 exec
  exec/         执行层：识别、转换、渲染、导出、历史、设置等业务编排
  services/     服务层：按模块放文件、渲染、OCR、外部工具等可复用服务
  dao/          数据访问层：SQLite 建表、迁移、查询和 row mapping
  models/       数据参数层：DTO、配置、实体、简谱结构模型
  domain/       纯简谱/MusicXML 算法入口，不做 I/O
desktop/        Electron + Vue3 桌面前端
```

Python 版 PySide 图形界面已删除，避免与 Electron/Vue 前端互相干扰。

## 环境

建议 Python 3.11 或 3.12。当前核心转换模块也兼容 Python 3.13。

安装依赖：

```powershell
uv venv .venv --python 3.13
uv pip install -e ".[test]" --python .venv\Scripts\python.exe
```

启动后端 API：

```powershell
$env:PYTHONPATH="src"
.venv\Scripts\python.exe -m uvicorn score_trans.api.app:create_app --factory --reload --host 127.0.0.1 --port 8004
```

启动桌面前端开发环境：

```powershell
cd desktop
$env:VITE_BACKEND_URL="http://127.0.0.1:8004"
pnpm dev
```

界面里可以设置：

- `简谱调`：默认 `C`，例如可填 `D`、`G`、`F`。
- `起始小节号`：留空时使用 MusicXML 自带小节号；填写 `118` 这类整数时会从该数字开始重新显示。
- `识别并导出简谱`：对当前图片/PDF 跑 Audiveris，随后生成 MusicXML、简谱文本和简谱 SVG。
- `导出简谱谱面 SVG`：把 MusicXML/MXL 解析成结构化简谱谱面，包含小节线、拍内辅助线、减时线、附点、延音线、连音线和纵向排列的和弦音。
- `识别预处理`：图片输入会在调用 Audiveris 前自动裁白边、增强对比并放大到更适合 OMR 的尺寸。默认目标长边为 `3600` 像素；识别异常时可在设置页关闭或启用黑白化。

简谱 SVG 默认使用出版模式：

- 根据小节内容动态分配宽度，密集十六分音符小节会自动变宽。
- 默认隐藏拍内虚线和横向网格，避免导出版像编辑器。
- 和弦音从高到低纵向排列，不再使用笨重的竖向框线。
- 连续八分/十六分音符会在小节内尽量合并成共享减时线，休止符也参与连线以减少碎片感。
- 如需调试拍位，可在代码里使用 `RenderOptions(show_beat_guides=True, show_staff_guides=True)`。

运行测试：

```powershell
python -m pytest
```

使用项目虚拟环境运行：

```powershell
.venv\Scripts\python.exe -m pytest
```

### API 调用方式

后端能力通过 FastAPI 暴露，推荐从桌面前端调用。开发或调试时也可以直接请求接口：

- `POST /files/upload`：上传输入文件，返回 `file_id`
- `POST /recognize`：图片/PDF -> MusicXML
- `POST /convert/musicxml-to-jianpu`：MusicXML -> 简谱文本
- `POST /convert/jianpu-to-musicxml`：简谱文本 -> MusicXML
- `POST /render/jianpu-svg`：MusicXML -> 简谱 SVG
- `POST /pipeline`：一键完成识别+转换+渲染
- `POST /ai/transcribe`：图片/PDF -> AI 简谱草稿；PDF 会先转为逐页图片

## 外部工具配置

Audiveris 和 MuseScore 需要单独安装。
本项目已经把 Audiveris 源码放在 `third_party/audiveris`，默认会优先使用：

```text
third_party\audiveris\gradlew.bat :app:run
```

注意：当前 Audiveris 源码版要求 **JDK 25**。本项目默认使用：

```text
E:\ENV\JAVA\JDK25
```

如果 JDK25 路径不同，可以设置：

```powershell
$env:SCORE_TRANS_JAVA_HOME="你的JDK25路径"
```

检查 Audiveris 开发环境：

```powershell
$env:http_proxy="http://127.0.0.1:7897"
$env:https_proxy="http://127.0.0.1:7897"
.\scripts\check_audiveris.ps1
```

脚本和 Python 应用都会把 `http_proxy` / `https_proxy` 自动转换为 Java/Gradle 可用的代理参数。

可以在界面中填写路径，也可以使用环境变量：

```powershell
$env:SCORE_TRANS_AUDIVERIS="D:\CODE\MyProjects\score_trans\third_party\audiveris\gradlew.bat"
$env:SCORE_TRANS_JAVA_HOME="E:\ENV\JAVA\JDK25"
$env:SCORE_TRANS_MUSESCORE="C:\Program Files\MuseScore 4\bin\MuseScore4.exe"
$env:SCORE_TRANS_OMR_PREPROCESS="1"
$env:SCORE_TRANS_OMR_PREPROCESS_LONG_EDGE="3600"
$env:SCORE_TRANS_OMR_PREPROCESS_BINARIZE="0"
```

默认 Audiveris 命令：

```text
audiveris -batch -export -output <output_dir> <input_file>
```

默认 MuseScore 命令：

```text
musescore -o <output_file> <musicxml_file>
```

如果你的本地版本命令参数不同，可以在 `backend/score_trans/services/recognize/external_tools.py` 里调整命令模板。

## OCR 文字层

OCR provider 只会从环境变量读取 API key，不会在代码或配置文件中硬编码：

```powershell
$env:SCORE_TRANS_OCR_API_KEY="你的 OCR API key"
$env:SCORE_TRANS_OCR_BASE_URL="https://api.siliconflow.cn/v1"
$env:SCORE_TRANS_OCR_MODEL="deepseek-ai/DeepSeek-OCR"
```

默认 provider 使用 OpenAI-compatible 的 `chat/completions` 请求格式，适配 SiliconFlow / DeepSeek OCR。最终渲染会同步读取 OMR 生成的 MusicXML 和 OCR 文字层；如果 OCR 返回 `bbox`，文字会按原页面坐标叠回 SVG，并保持原页面尺寸。测试和离线开发可以使用 `MockOCRProvider`，或者把 `OpenAICompatibleOCRProvider(dry_run=True)` 用于只构造请求、不发起网络调用。

图片页执行“识别并自动填充”或“批量识别全部”时会同时跑 OMR 和 OCR，生成的 SVG 会把 OCR 文字原样放回 bbox 对应位置。普通“SVG”渲染如果当前页有原始图片，也会带上 OCR 文字层；没有配置 OCR key 时会直接提示配置错误，避免静默漏字。

## AI 视觉转写

“AI 视觉转写”是一条独立于 Audiveris 的快速草稿流程：上传图片或 PDF 后，后端会把 PDF 用 PyMuPDF 渲染成逐页 PNG，再通过 LangChain 调用 OpenAI-compatible 视觉模型，直接生成项目简谱语法文本。图片输入会沿用原始 `file_id`；PDF 输入会把每页 PNG 注册成新的 `file_id`，前端会展开成多个可编辑页面。

配置可以在设置页填写，也可以使用环境变量：

```powershell
$env:SCORE_TRANS_AI_API_KEY="你的视觉模型 API key"
$env:SCORE_TRANS_AI_BASE_URL="https://api.siliconflow.cn/v1"
$env:SCORE_TRANS_AI_MODEL="Qwen/Qwen3-VL-8B-Instruct"
```

AI 输出会先按项目简谱语法校验和规范化；如果某页存在语法错误或小节超拍，界面会保留草稿并显示 warning，方便人工校对。

## 简谱文本语法（Jianpu Text Syntax）

本项目使用纯文本描述简谱，经解析后渲染为 SVG 谱面或转写为 MusicXML。语法设计目标是：**看到什么符号，就输入什么符号**，让乐谱编辑像打字一样自然。

---

### 1. 谱面基本信息

写在正文前的元数据行，控制整首曲子的调号、拍号、标题和速度。

| 指令 | 说明 | 示例 |
|------|------|------|
| `1=` | **调号**。用大调主音表示，如 `C`、`G`、`F`、`D`、`Bb`。 | `1=C` |
| `4/4` | **拍号**。分子为每小节拍数，分母为以几分音符为一拍。 | `3/4`、`6/8` |
| `title=` | **标题**。可包含空格，不需要引号。 | `title=小星星` |
| `tempo=` | **速度**。整数 BPM。 | `tempo=120` |
| `instrument=` | **乐器模式**（可选）。决定可用的演奏技巧标记：`general`（普通）、`erhu`（二胡）、`ruan`（阮）、`guzheng`（古筝）。 | `instrument=erhu` |

**示例 — 一首完整曲头：**

```text
title=小星星变奏曲
1=C
4/4
tempo=100
instrument=erhu
```

> **注意**：调号 `1=` 与拍号 `4/4` 也可写在小节之前做中途转调/变拍（如 `1=G`、`3/4`），对后续小节生效；旧写法 `key=C`、`time=4/4` 已废弃，请改用 `1=C`、`4/4`。

---

### 2. 音符（音级与八度）

用数字 `1`–`7` 表示七个音级，对应 do、re、mi、fa、sol、la、si。

| 符号 | 说明 | 渲染效果 |
|------|------|----------|
| `1` `2` `3` `4` `5` `6` `7` | 基本音级（中音区） | 数字音符 |
| `1'` `2'` | 单引号 `'` 表示**高八度**，可叠加 | 数字 + 上圆点 |
| `1,` `2,` | 逗号 `,` 表示**低八度**，可叠加 | 数字 + 下圆点 |
| `1''` `1,,` | 双引号/双逗号表示**再高/低一个八度** | 两个上/下圆点 |

**示例：**

```text
1 2 3 | 1' 2' 3' | 1, 2, 3, |
```

---

### 3. 临时升降号

写在音级前面或后面，表示临时变音。

| 符号 | 说明 | 示例 |
|------|------|------|
| `#` | 升半音 | `#4`（fa → #fa） |
| `b` | 降半音 | `b7`（si → ♭si） |
| `x` | 重升（全音） | `x4`（fa → xfa） |
| `bb` | 重降（全音） | `bb7`（si → 𝄫si） |
| `n` 或 `♮` | 还原 | `n4`（还原4） |

> 升降号可前置或后置，效果相同：`#5` 与 `5#` 等价。还原号 `n`/`♮` 只能前置，如 `n4`。

---

### 4. 休止符

| 符号 | 说明 |
|------|------|
| `0` | 休止符，默认时值为一拍（四分休止） |
| `w0` | 全休止（4 拍） |
| `h0` | 二分休止（2 拍） |
| `q0` | 八分休止（½ 拍） |
| `s0` | 十六分休止（¼ 拍） |

> 休止符 `0` 与音符 `1`–`7` 的时值规则完全相同，可加任意时值前缀（`w/h/q/s/d`）、附点或延长线。

---

### 5. 时值控制

默认每个音符/休止符的时值等于 **一拍**（以四分音符为一拍时）。通过以下方式改变时值：

#### 5.1 时值前缀（推荐新写法）

在音符前加字母前缀，直接指定音符类型：

| 前缀 | 含义 | 对应拍数（以 4/4 为例） | 示例 |
|------|------|------------------------|------|
| *(无)* | 四分音符 | 1 拍 | `1` `3` `5` |
| `q` | 八分音符（quaver） | ½ 拍 | `q1` `q3` `q5` |
| `s` | 十六分音符（semiquaver） | ¼ 拍 | `s1` `s2` |
| `d` | 三十二分音符（demisemiquaver） | ⅛ 拍 | `d1` |
| `h` | 二分音符（half note） | 2 拍 | `h1` |
| `w` | 全音符（whole note） | 4 拍 | `w1` |

**示例 — 一小节混合时值：**

```text
q1 q2 q3 q4 | s1 s1 s1 s1 q2 q3 |
```

#### 5.2 附点

在音符后加 `.`，时值延长 **自身的一半**。

| 写法 | 说明 | 总拍数 |
|------|------|--------|
| `5.` | 附点四分音符 | 1 + ½ = 1.5 拍 |
| `h5.` | 附点二分音符 | 2 + 1 = 3 拍 |
| `q5.` | 附点八分音符 | ½ + ¼ = ¾ 拍 |

#### 5.3 延音线（Tie）

用波浪号 `~` 将两个同音高的音符连成一体，**总时值为两者之和**，谱面显示为延音弧线。

| 写法 | 说明 |
|------|------|
| `5~` | 当前音为延音起点 |
| `~5` | 当前音为延音终点 |

**示例 — 一个跨小节的二分音符：**

```text
1 2 3 5~ | ~5 3 2 1 |
```

> 只有**同音高**的音符才能连延音线；不同音高请使用连音线 `()`。

#### 5.4 连音组（Tuplet）

用 `$ ... $` 把一组音符括起来，组内所有音**平均分配 1 拍**的总时值。

| 写法 | 说明 | 每个音的时值 |
|------|------|-------------|
| `$123$` | 三连音，3 个音共占 1 拍 | ⅓ 拍 |
| `$1234$` | 四连音，4 个音共占 1 拍 | ¼ 拍 |
| `$1 2 3 4 5$` | 五连音，组内用空格分隔也可 | ⅕ 拍 |

> 连音组至少需要 2 个音。组内可以带升降号、八度标记和时值无关（连音组忽略组内前缀，统一按组长度均分 1 拍）。组外禁止出现 `27`、`356` 这类连续多位数字——它们不是音高。

---

### 6. 小节与曲式结构

| 符号 | 说明 | 渲染效果 |
|------|------|----------|
| `|` | 小节线 | 竖线分隔 |
| `||` | 终止线（双竖线） | 细线 + 粗线 |
| `|:` | 反复起始 | 左粗右细 + 两个圆点 |
| `:|` | 反复结束 | 左细右粗 + 两个圆点 |
| `*N` | 反复次数，写在 `:|` 之前，表示该段重复 N 遍 | 小节号相应增加 |

**示例 — 带反复与重复次数的乐段：**

```text
|: 1 2 3 4 | 5 6 5 4 *2 :||
```

> 上例中 `*2` 表示 `5 6 5 4` 这一小节重复 2 遍。行首出现 `1.` `2.` `12:` 等小节编号会自动忽略，方便你从现有乐谱直接复制粘贴。

---

### 7. 和弦

用方括号 `[ ]` 把多个音级括起来，音级之间用 `+` 分隔。和弦音在谱面中**纵向排列**，最高音在上。

| 写法 | 说明 |
|------|------|
| `[1+3+5]` | C 大调和弦（do + mi + sol） |
| `[5+7+2']` | G 大调和弦 |
| `q[1+3+5]` | 八分音符和弦 |

**示例：**

```text
1 2 [1+3+5] | 6 [6+1'+3'] 5 [5+7+2'] |
```

---

### 8. 连音线（Slur）

用圆括号 `(` `)` 标记连音（圆滑奏）范围，谱面显示为弧线连接括号内的所有音符。

| 写法 | 说明 |
|------|------|
| `(5 6 7 1')` | 四个音一组连音 |
| `(q1 q2 q3 q4)` | 带时值的连音组 |

> 连音线可以跨小节，但不能嵌套。

---

### 9. 力度与演奏法标记

#### 9.1 力度标记

在音符前写 `\` 加力度符号，作用于其后的第一个音符。

| 写法 | 含义 | 渲染效果 |
|------|------|----------|
| `\p` | 弱（piano） | *p* |
| `\mp` | 中弱（mezzo-piano） | *mp* |
| `\mf` | 中强（mezzo-forte） | *mf* |
| `\f` | 强（forte） | *f* |
| `\ff` | 很强（fortissimo） | *ff* |
| `\pp` | 很弱（pianissimo） | *pp* |
| `\fff` | 极强（fortississimo） | *fff* |
| `\fp` | 强后弱（fortepiano） | *fp* |
| `\sfz` | 突强（sforzando） | *sfz* |

**示例：**

```text
\p 1 2 3 4 | \f 5 6 5 4 |
```

#### 9.2 演奏法标记

在音符前写 `^` 加标记，作用于其后的第一个音符。

| 写法 | 含义 | 渲染效果 |
|------|------|----------|
| `^.` | 断奏（staccato） | 圆点 |
| `^>` | 重音（accent） | `>` 记号 |
| `^-` | 保持（tenuto） | 横线 |
| `^r` | 颤音（trill） | *tr* |
| `^f` | 延音记号（fermata） | fermata 形状 |
| `^l` | 轮指（tremolo） | 三道斜线 |

**示例：**

```text
1 ^.2 ^>3 ^-4 | ^r5 4 3 2 |
^l 5 ^l 6 | ^l 7 1' |
```

#### 9.3 小节级简写

如果一整小节的音符都要加同一种演奏法，可在小节开头用括号简写，作用于该小节内所有音符与和弦（休止符不继承）：

| 写法 | 含义 |
|------|------|
| `(^l)` | 整小节震音/轮指 |
| `(^.)` | 整小节跳音 |
| `(^>)` | 整小节重音 |
| `(^r)` | 整小节颤音 |
| `(^f)` | 整小节延音记号 |

```text
(^l) 1 2 3 4 | (^.) q1 q2 q3 q4 |
```

> 这只是简写，等价于逐音写 `^l`、`^.`。在二胡/阮/古筝等乐器模式下，整小节轮指/摇指/震音常用 `(^l)` 表示。详见应用内「语法参考 → 演奏技巧」。

---

### 10. 歌词

用 `L:` 开头的一行定义歌词，单词用空格分隔，每个单词自动与对应小节的音符对齐。

**示例：**

```text
1=C
4/4
1 1 5 5 | 6 6 h5 |
L: 一 闪 一 闪 亮 晶 晶
```

> 歌词与音符按顺序一一对应；休止符不分配歌词。若歌词数量少于音符，多余的音符不显示歌词；若歌词数量多于音符，多余的词会被忽略。

---

### 11. 注释

用 `//` 表示行内注释，从 `//` 开始到当前行末尾的内容会被解析时忽略。

```text
1=C
4/4
1 2 3 4 | 5 6 7 1' | // 这是一段行内注释
```

> 注意：`#` 是升号（如 `#4`），**不是**注释符。需要注释请一律使用 `//`。

---

### 12. 完整示例

下面是一段完整的《小星星》简谱文本：

```text
title=小星星
1=C
4/4
tempo=100

1 1 5 5 | 6 6 h5 | 4 4 3 3 | 2 2 h1 |
L: 一 闪 一 闪 亮 晶 晶 满 天 都 是 小 星 星

5 5 4 4 | 3 3 h2 | 5 5 4 4 | 3 3 h2 |
L: 太 阳 慢 慢 向 西 沉 乌 鸦 回 家 一 群 群

1 1 5 5 | 6 6 h5 | 4 4 3 3 | 2 2 h1 |
L: 一 闪 一 闪 亮 晶 晶 满 天 都 是 小 星 星
```

**更复杂的示例 — 混合时值与装饰：**

```text
title=练习曲
1=G
4/4

\mf 1 2 3 4 | q5 q5 q3 q1 q5 q5 q3 q1 | h2. q3 q4 | w1 |
L: 春 眠 不 觉 晓 处 处 闻 啼 鸟 飞 飞 飞 去 去 去

\p (5 6 5 4) | 3 2 1 ~1 | 2 3 4 3 | h2 h0 |
L: 夜 来 风 雨 声 花 落 知 多 少 安 睡 吧
```

---

### 13. 语法速查表

| 符号 | 功能 |
|------|------|
| `1`–`7` | 音级 do–si |
| `0` | 休止符 |
| `'` `,` | 升高/降低八度 |
| `#` `b` `x` `bb` `n` | 升、降、重升、重降、还原 |
| `q` `s` `d` `h` `w` | 八分、十六分、三十二分、二分、全音符 |
| `.` | 附点（写在音级后） |
| `-` | 延长线（每个延长一拍） |
| `~` | 延音线 |
| `( )` | 连音线（圆滑奏） |
| `$...$` | 连音组（三连音、四连音等，组内共占 1 拍） |
| `[a+b+c]` | 和弦 |
| `|` `||` `|:` `:|` `*N` | 小节线、终止线、反复起止、反复次数 |
| `\p` `\f` `\sfz` 等 | 力度 |
| `^.` `^>` `^-` `^r` `^f` `^l` | 演奏法（断奏、重音、保持、颤音、延音、轮指） |
| `(^l)` `(^.)` 等 | 小节级演奏法简写 |
| `L:` | 歌词行 |
| `//` | 行内注释（`#` 是升号，不是注释） |
| `1=` `4/4` `title=` `tempo=` `instrument=` | 调号、拍号、标题、速度、乐器模式 |

> **旧写法迁移提示**：本项目已弃用旧版 `key=`/`time=` 头部与 `/` 减时线。请改用 `1=C`、`4/4` 头部，并用 `q`、`s`、`d`、`h`、`w` 时值前缀代替 `/`（例如旧写法 `3/` 改为 `q3`，`6//` 改为 `s6`）。
