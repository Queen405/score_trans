# Score Trans

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS-lightgrey)](https://github.com/Queen405/score_trans)

五线谱与简谱互转的本地桌面应用（Windows / macOS）。支持图片/PDF 导入、Audiveris OMR 识别、AI 视觉转写、MusicXML ↔ 简谱互转，以及出版级简谱 SVG 渲染。

[下载安装包](https://github.com/Queen405/score_trans/releases) · [查看文档](docs/) · [报告问题](../../issues)

<!-- TODO: 替换为真实截图 -->
<!-- ![Score Trans 主界面](docs/images/screenshot.png) -->

## 核心功能

- **OMR 识别**：导入图片或 PDF，通过 Audiveris 生成 MusicXML。
- **AI 视觉转写**：不依赖 Audiveris，直接调用视觉模型生成简谱草稿。
- **双向转换**：MusicXML ↔ 简谱文本互相转换。
- **出版级 SVG**：渲染含小节线、拍内辅助线、减时线、附点、延音线、连音线、和弦的简谱谱面。
- **多格式输出**：导出 MusicXML、简谱 SVG 和 MIDI。
- **民乐支持**：可选二胡、阮、古筝演奏法标记。
- **本地优先**：识别与渲染均在本地完成，数据不上传云端。

## 系统要求

- Windows 10 / 11，或 macOS 11+（Apple Silicon，M1/M2/M3/M4）
- 无需安装 Java / Python，运行时已全部内置
- OCR / AI API key（可选，用于文字层和 AI 转写）

## 下载与安装

### Windows

1. 从 [GitHub Releases](https://github.com/Queen405/score_trans/releases) 下载 `Score Trans Setup X.Y.Z.exe`。
2. 双击运行安装向导。首次启动若出现 SmartScreen 警告，点击「仍要运行」。
3. 安装完成即可使用，本地识别无需任何配置。

### macOS

1. 从 [GitHub Releases](https://github.com/Queen405/score_trans/releases) 下载 `Score Trans-X.Y.Z-arm64.dmg`。
2. 双击打开 dmg，将 **Score Trans** 拖入「应用程序」文件夹。
3. 首次打开会被 Gatekeeper 拦截（应用未签名未公证）。先双击弹窗点「完成」，再打开
   **系统设置 → 隐私与安全性 → 安全性**，点击「仍要打开」。
   - 或在终端执行 `xattr -cr "/Applications/Score Trans.app"` 后双击启动。
4. 放行一次后正常使用，本地识别无需任何配置。

更多环境变量（开发态配置）见 [docs/environment.md](docs/environment.md)。

## 快速开始

1. 打开 Score Trans。
2. 拖入或选择五线谱图片 / PDF。
3. 选择目标简谱调（如 `C`、`G`、`D`）。
4. 点击「识别并导出简谱」。
5. 在编辑器中查看/修正简谱文本，预览 SVG 谱面。
6. 导出 PDF、PNG 或 MIDI。

## 文档

- [简谱文本语法](docs/jianpu-syntax.md)
- [开发环境搭建](docs/development.md)
- [环境变量参考](docs/environment.md)
- [架构说明](docs/architecture.md)
- [文件索引](docs/file-by-file.md)
- [已知问题与路线图](docs/issues.md)

## 技术栈

- **后端**：Python 3.11+ · FastAPI · Uvicorn · SQLite
- **前端**：Electron · Vue 3 · Pinia · Naive UI
- **OMR**：Audiveris
- **导出**：MusicXML、简谱 SVG 和 MIDI

## 参与贡献

提交规范使用中文 conventional commits：

```text
feat: 添加XXX功能
fix: 修复XXX
refactor: 重构XXX
```

欢迎提交 Issue 和 Pull Request。

## 许可证

[MIT](LICENSE)

