# Score Trans

五线谱与简谱互转的 Windows 本地桌面原型。

## 功能

- 导入图片或 PDF，通过 Audiveris 调用 OMR，生成 MusicXML。
- 导入 MusicXML，转换为简谱文本。
- 输入简谱文本，生成基础 MusicXML。
- 调用 MuseScore Studio CLI，把 MusicXML 导出为 PDF、PNG、MIDI 等格式。

## 架构

项目已按轻量 MVVM 重构：

```text
src/score_trans/
  domain/       纯领域模型和 MusicXML/简谱领域入口
  services/     外部工具、文件、渲染、OCR、设置等技术服务
  use_cases/    用户动作：识别、转换、渲染、导出、完整流水线
  viewmodels/   Qt 无关业务状态与命令调度，向 View 暴露 signal
  views/        PySide6 界面，只负责控件、对话框和绑定 ViewModel
  cli/          命令行入口，复用 use cases
```

顶层包只保留应用入口：

- `python -m score_trans` 通过 `__main__.py` 启动 CLI 或桌面界面。
- 命令行脚本入口为 `score_trans.cli.commands:main`。
- 不再保留旧的顶层兼容模块，业务代码必须进入对应的 MVVM 分层目录。

## 环境

建议 Python 3.11 或 3.12。当前核心转换模块也兼容 Python 3.13。

安装依赖：

```powershell
uv venv .venv --python 3.13
uv pip install -e ".[test]" --python .venv\Scripts\python.exe
```

启动桌面软件：

```powershell
.venv\Scripts\python.exe -m score_trans
```

界面里可以设置：

- `简谱调`：默认 `C`，例如可填 `D`、`G`、`F`。
- `起始小节号`：留空时使用 MusicXML 自带小节号；填写 `118` 这类整数时会从该数字开始重新显示。
- `识别并导出简谱`：对当前图片/PDF 跑 Audiveris，随后生成 MusicXML、简谱文本和简谱 SVG。
- `导出简谱谱面 SVG`：把 MusicXML/MXL 解析成结构化简谱谱面，包含小节线、拍内辅助线、减时线、附点、延音线、连音线和纵向排列的和弦音。

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
.venv\Scripts\python.exe -m score_trans
.venv\Scripts\python.exe -m pytest
```

如果暂时不安装包，也可以在项目根目录这样运行命令行转换：

```powershell
$env:PYTHONPATH="src"
python -m score_trans to-musicxml examples\simple_jianpu.txt -o work\simple.musicxml
python -m score_trans to-jianpu work\simple.musicxml
```

结构化 MusicXML/MXL 转简谱，支持目标调和起始小节号：

```powershell
.venv\Scripts\python.exe -m score_trans to-jianpu work\score.mxl --target-key C --start-measure-number 118 -o work\score_jianpu.txt
.venv\Scripts\python.exe -m score_trans render-musicxml work\score.mxl --target-key C --start-measure-number 118 -o work\score_jianpu.svg
```

如果要把页面图里的文字层合进 SVG，可给 `render-musicxml` 传 OCR 页面图：

```powershell
.venv\Scripts\python.exe -m score_trans render-musicxml work\score.mxl --ocr-image work\page.png -o work\score_jianpu.svg
```

图片/PDF 一键识别并导出：

```powershell
.venv\Scripts\python.exe -m score_trans recognize "examples\5.瑞雪迎春 - 分谱.pdf" -o work\converted --target-key C --start-measure-number 118
```

该命令会在输出目录生成：

- `<原文件名>.musicxml` 或 `<原文件名>.mxl`
- `<原文件名>_jianpu.txt`
- `<原文件名>_jianpu.svg`

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
```

默认 Audiveris 命令：

```text
audiveris -batch -export -output <output_dir> <input_file>
```

默认 MuseScore 命令：

```text
musescore -o <output_file> <musicxml_file>
```

如果你的本地版本命令参数不同，可以在 `src/score_trans/tools.py` 里调整命令模板。

## OCR 文字层

OCR provider 只会从环境变量读取 API key，不会在代码或配置文件中硬编码：

```powershell
$env:SCORE_TRANS_OCR_API_KEY="你的 OCR API key"
$env:SCORE_TRANS_OCR_BASE_URL="https://api.siliconflow.cn/v1"
$env:SCORE_TRANS_OCR_MODEL="deepseek-ai/DeepSeek-OCR"
```

默认 provider 使用 OpenAI-compatible 的 `chat/completions` 请求格式，适配 SiliconFlow / DeepSeek OCR。最终渲染会同步读取 OMR 生成的 MusicXML 和 OCR 文字层；如果 OCR 返回 `bbox`，文字会按原页面坐标叠回 SVG，并保持原页面尺寸。测试和离线开发可以使用 `MockOCRProvider`，或者把 `OpenAICompatibleOCRProvider(dry_run=True)` 用于只构造请求、不发起网络调用。

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
