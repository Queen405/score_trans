# 打包指南

本地与 CI 共用根目录 `build-app.py`。该脚本必须提交到 Git，不能只保存在开发机。

## 运行依赖

安装包包含 Electron、PyInstaller 冻结后端、字体与配置基线、Audiveris 完整
Java 分发目录以及裁剪后的 JDK 25。用户无需安装 Python、Java 或 Gradle。
OCR/AI 云服务仍需要用户配置凭据和网络；本地 Audiveris 图片识别不依赖这些服务。

Audiveris 在构建机执行 `clean :app:installDist`，输出
`third_party/audiveris/app/build/install/app/`，包含 `lib/audiveris.jar`、第三方依赖 JAR
和启动脚本。程序 JAR 自带 `res/` 与类路径资源。

运行识别时后端直接调用内置 Java，以 `lib/*` 为 classpath 启动 `Audiveris`，
传递用户配置的最大堆和逐项 CLI 参数。安装后不执行 Gradle、不重新编译、不写入
应用安装目录。开发环境和用户显式指定的 Gradle wrapper 仍保留兼容支持。

## 构建

准备 Python 3.13、项目锁定的 pnpm、Node.js 22、完整 JDK 25：

```powershell
$env:SCORE_TRANS_JAVA_HOME = 'E:/ENV/JAVA/JDK25'
uv sync --extra build --locked
uv run python build-app.py
```

JDK 优先从 `SCORE_TRANS_JAVA_HOME`，其次 `JAVA_HOME`，最后 Windows 开发默认路径读取。
构建阶段校验 JDK 25，不自动下载不固定版本的 JDK。CI 使用 setup-java 准备 JDK。

可用参数：

- `--skip-electron`：只生成完整 `build-resources/`，用于 CI 后续 electron-builder。
- `--skip-backend`、`--skip-audiveris`、`--skip-jre`：明确复用已有阶段产物，仅适合本地迭代。
  CI 不使用这些复用开关。复用后仍会运行最终资源/功能校验。

流程：

1. 校验版本、公开默认配置（含 provider 一致性）。
2. PyInstaller 打包后端，复制 `env.example` 为 `.env`、复制 `published_defaults.json`。
3. 干净编译 Audiveris 分发，复制依赖 JAR 和许可证文件。
4. 复制同一 JDK，裁剪开发资源，删除历史 `.trash-*` 目录与旧 Gradle 缓存。
5. `pnpm install --frozen-lockfile`，构建前端并运行 electron-builder（`--publish never`）。
6. 对最终 Electron 资源目录运行后端、识别和导出冒烟测试。

文件缺失、配置不一致、构建失败、资源清理失败、冒烟失败都必须使打包命令失败。
不要为了继续打包而把删除操作全局替换为目录重命名。

## 资源布局

```text
resources/
  backend/
    backend.exe (macOS: backend)
    _internal/              # Python 运行时、依赖、字体、提示词等
    .env
    published_defaults.json
  third_party/
    audiveris/
      bin/
      lib/audiveris.jar
      lib/<dependency>.jar
    jre/jdk/
      bin/java.exe (macOS: java)
      lib/modules
      legal/
```

`SettingsService` 默认选择分发 JAR；旧 settings.db 的无效路径自动回退到内置路径。
用户数据仍在用户目录中；安装目录不是数据目录。升级不覆盖已存在的数据库设置。

## 验证

```powershell
uv run python tools/smoke_package.py desktop/dist-electron/win-unpacked/resources
```

macOS 资源目录为 `desktop/dist-electron/mac-arm64/Score Trans.app/Contents/Resources`。

冒烟测试使用全新用户数据目录、中文/空格/逗号工作路径、空 Gradle 缓存、不可用的
HTTP/HTTPS 代理，验证健康检查、SVG、PDF、MIDI 与真实图片识别（必须输出音符）。
固定乐谱由测试脚本使用项目自带 OFL 字体生成，不下载外部样例。
这些代理设置是防止依赖下载的检查，不等于操作系统级网络隔离。

Windows CI 额外运行 `tools/smoke_installer.py`，静默安装到含中文与空格的目录，
对安装后的资源执行冒烟测试，覆盖安装后卸载，并验证用户数据保留。此脚本仅允许
在一次性的 GitHub-hosted runner 上运行，避免覆盖开发者已安装的程序或注册表项。

发布入口与版本规则见 [RELEASE.md](../RELEASE.md)。交互式安装向导、不同历史版本
迁移、SmartScreen/Gatekeeper 提示仍需人工发布验收。
