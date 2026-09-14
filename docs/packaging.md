# 打包指南

打包仅在 CI 中运行，入口为 .github/workflows/package.yml。
build-app.py 生成 build-resources/（冻结后端、Audiveris 分发、裁剪 JDK 25），
随后 electron-builder 创建 Windows x64 NSIS 和 macOS arm64 DMG。

## 构建与质量门禁

- uv sync --extra build --locked 安装构建依赖；Java 来自 setup-java。
- 前端使用 pnpm install --frozen-lockfile，执行构建后再打包。
- 质量门禁包含 Python 测试/lint/格式、前端 lint/类型/工具测试，
  pnpm check:api-types 和 pnpm test:release-tools。
- OpenAPI 导出和 COS 上传脚本必须随仓库检出，不能放入忽略规则。
- 平台安装与冒烟失败时不上传可发布安装包；诊断产物始终尝试保存 14 天。

## 最终产物验证

Windows 使用 tools/smoke_installer.py，静默安装后检查最终 resources，
再启动实际 Score Trans.exe；重装后再次启动，最后卸载并检查用户数据保留。
安装器退出码非零或超时直接失败，禁止使用旧文件存在或 7z 解包结果放行。
安装/重装超时 600 秒，卸载超时 300 秒；只清理本次启动的进程树。

macOS 使用 tools/smoke_mac.py，挂载实际 DMG，以 ditto 复制 .app 到临时目录，
测试复制后的 resources 与 Contents/MacOS/Score Trans，并在 finally 中卸载镜像。

tools/smoke_package.py 验证健康检查、SVG、PDF、MIDI 与真实图片识别，
包含中文、空格、逗号工作路径，不依赖外部乐谱样例。
安装目录使用可被内置 Java 正常识别的路径；不覆盖 HOME/USERPROFILE。

desktop/scripts/smoke-desktop.mjs 使用锁定的 playwright-core 驱动实际打包程序，
不下载浏览器、不启动开发服务器。检查主界面、preload、版本 IPC、
渲染进程到后端的认证调用，以及 Electron/后端进程和端口的正常关闭。
启动与检查预算 90 秒，退出等待 15 秒，外层看门狗 120 秒。
只在一次性 GitHub-hosted runner 上运行。

SCORE_TRANS_ELECTRON_USER_DATA_DIR 可指定绝对 Electron 用户目录；
冒烟测试预先写入 storage-paths.json，将业务数据和缓存隔离到临时目录。
该变量不改变默认用户存储行为，不暴露认证 token。
日志、结果与截图写入 desktop/smoke-reports/，禁止保存含认证头的网络追踪。

## 发布与恢复

发布工作流统一生成清单与校验文件，先验证 GitHub 草稿和公开 COS 安装包，
再公开归档并按版本规则推广更新。旧版本可以归档，不能覆盖最新版。
失败后从默认分支运行 Package and release，选择 resume 和既有 tag，
复用原始快照恢复，不重打包、不覆盖公开资产。

COS 上传工具默认只上传版本化安装包；不要在公开 Release 后手动写 latest.json。
配置、恢复条件和隔离环境演练要求见 [RELEASE.md](../RELEASE.md)。

签名、公证、交互式安装以及跨历史版本迁移仍需独立发布验收。
