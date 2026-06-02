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
src/score_trans/
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

如果你的本地版本命令参数不同，可以在 `src/score_trans/services/recognize/external_tools.py` 里调整命令模板。

## OCR 文字层

OCR provider 只会从环境变量读取 API key，不会在代码或配置文件中硬编码：

```powershell
$env:SCORE_TRANS_OCR_API_KEY="你的 OCR API key"
$env:SCORE_TRANS_OCR_BASE_URL="https://api.siliconflow.cn/v1"
$env:SCORE_TRANS_OCR_MODEL="deepseek-ai/DeepSeek-OCR"
```

默认 provider 使用 OpenAI-compatible 的 `chat/completions` 请求格式，适配 SiliconFlow / DeepSeek OCR。最终渲染会同步读取 OMR 生成的 MusicXML 和 OCR 文字层；如果 OCR 返回 `bbox`，文字会按原页面坐标叠回 SVG，并保持原页面尺寸。测试和离线开发可以使用 `MockOCRProvider`，或者把 `OpenAICompatibleOCRProvider(dry_run=True)` 用于只构造请求、不发起网络调用。

图片页执行“识别并自动填充”或“批量识别全部”时会同时跑 OMR 和 OCR，生成的 SVG 会把 OCR 文字原样放回 bbox 对应位置。普通“SVG”渲染如果当前页有原始图片，也会带上 OCR 文字层；没有配置 OCR key 时会直接提示配置错误，避免静默漏字。

## 简谱输入格式

第一版支持简单文本简谱：

```text
key=C
time=4/4
1 2 3 4 | 5 6 7 1' | 0 - 5. 3/ |
```

规则：

- `1` 到 `7` 表示音级。
- `0` 表示休止符。
- `|` 表示小节线。
- `'` 表示升高八度，`,` 表示降低八度。
- `#1`、`b7` 表示临时升降号。
- `-` 延长前一个音符一个四分音符。
- `.` 表示附点。
- `/` 表示时值减半。
