# 打包指南

打包仅在 CI 中运行，入口为 `.github/workflows/package.yml`。`build-app.py` 负责
生成完整的 `build-resources/` 目录（后端 + Audiveris + JRE），随后 CI 工作流调用
electron-builder 完成最终打包。不支持本地打包。

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

## CI 构建流程

CI 工作流使用 `setup-java` 准备 JDK 25，执行 `uv sync --extra build --locked`
安装构建依赖，然后运行 `uv run python build-app.py` 生成 `build-resources/`。
随后工作流单独执行 `pnpm install --frozen-lockfile`、`pnpm build` 和
`pnpm electron-builder build`（`--publish never`）。

`build-app.py` 流程：

1. 校验版本、公开默认配置（含 provider 一致性）。
2. PyInstaller 打包后端，复制 `env.example` 为 `.env`、复制 `published_defaults.json`。
3. 干净编译 Audiveris 分发，复制依赖 JAR 和许可证文件。
4. 复制同一 JDK，裁剪开发资源，删除历史 `.trash-*` 目录与旧 Gradle 缓存。

文件缺失、配置不一致、构建失败、资源清理失败、冒烟失败都必须使打包命令失败。

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

CI 对最终 Electron 资源目录运行冒烟测试：

- macOS：`tools/smoke_package.py "desktop/dist-electron/mac-arm64/Score Trans.app/Contents/Resources"`
- Windows：`tools/smoke_installer.py`（静默安装 → 冒烟 → 重装 → 卸载，验证用户数据保留）

冒烟测试使用全新用户数据目录、中文/空格/逗号工作路径、空 Gradle 缓存、不可用的
HTTP/HTTPS 代理，验证健康检查、SVG、PDF、MIDI 与真实图片识别（必须输出音符）。
固定乐谱由测试脚本使用项目自带 OFL 字体生成，不下载外部样例。
这些代理设置是防止依赖下载的检查，不等于操作系统级网络隔离。

`tools/smoke_installer.py` 仅允许在一次性的 GitHub-hosted runner 上运行，避免覆盖
开发者已安装的程序或注册表项。

发布入口与版本规则见 [RELEASE.md](../RELEASE.md)。交互式安装向导、不同历史版本
迁移、SmartScreen/Gatekeeper 提示仍需人工发布验收。
