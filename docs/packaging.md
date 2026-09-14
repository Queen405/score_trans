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

Windows NSIS 使用 `useZip: true` 时必须同时设置 `differentialPackage: false`。
electron-builder 25.1.8 默认开启差分包，会生成 7z 载荷，但 `useZip` 仍选择 ZIP
解压器，导致 `Error opening ZIP file`；错误弹窗会使静默安装一直等到超时。
当前更新流程下载完整安装器，不依赖差分包或 blockmap。
`pnpm test:utils` 中的归档测试会调用锁定的打包器生成小文件归档，
检查真实文件头与安装器解压方式一致，避免只检查配置而漏掉打包器的覆盖行为。

Windows 安装阶段即时记录 PID、时间、耗时和退出码，每 30 秒采集安装目录的
文件数量、总大小和最近变更文件。超时清理前，tools/installer_diagnostics.py
额外采集本次安装器进程树及其窗口/控件文本（包含隐藏的错误弹窗）。
诊断使用独立的 Python 子进程，正常采集预算最多 10 秒；若采集超时，
分别限时 5 秒清理诊断进程树和回收父进程，并保留已经产生的输出。
采集或清理失败不会覆盖原始安装错误，不会将超时安装判定为成功。

这些记录写入 desktop/smoke-reports/install.jsonl、reinstall.jsonl、uninstall.jsonl，
并同步输出到 installer.log。可在失败的 Actions 运行摘要页下载
package-diagnostics-windows 附件；重点检查 timeout 后的 snapshot 或 diagnostic-error，
其中 output 保留诊断子进程输出。未记录的阶段表示尚未执行到该步骤。

macOS 使用 tools/smoke_mac.py，挂载实际 DMG，以 ditto 复制 .app 到临时目录，
测试复制后的 resources 与 Contents/MacOS/Score Trans，并在 finally 中卸载镜像。

tools/smoke_package.py 验证健康检查、SVG、PDF、MIDI 与真实图片识别，
包含中文、空格、逗号工作路径，不依赖外部乐谱样例。
安装目录使用可被内置 Java 正常识别的路径；不覆盖 HOME/USERPROFILE。

Windows 非 UTF-8 代码页下，Java 启动器可能把命令行中的中文转换为 `?`。
打包版 Audiveris 的应用参数通过临时 UTF-8 参数文件传递，每行一个原始参数，
保留路径中的中文、空格和逗号。`-Dfile.encoding=UTF-8` 与 `--disable-@files`
确保由 Audiveris 的 args4j 读取文件，避免 Java 启动器提前展开。
以输出目录作为工作目录，仅将相对 ASCII 参数文件名放入命令行；
成功或失败均清理临时文件。中文工作路径的真实识别冒烟检查继续保留。

desktop/scripts/smoke-desktop.mjs 使用锁定的 playwright-core 驱动实际打包程序，
不下载浏览器、不启动开发服务器。检查主界面、preload、版本 IPC、
渲染进程到后端的认证调用，以及 Electron/后端进程和端口的正常关闭。
启动与检查预算 90 秒，退出等待 15 秒，外层看门狗 120 秒。
只在一次性 GitHub-hosted runner 上运行。

桌面冒烟的 Windows 子进程检查使用 `tools/installer_diagnostics.py --processes-only`
调用原生进程快照 API，由外层 Python 通过 `--python` 传入当前虚拟环境解释器；
不依赖 PowerShell/WMI。macOS 继续使用 `ps`。两端都要求只有一个直属后端子进程，
并继续检查应用退出后后端进程与端口均已关闭。
查询预算 10 秒，输出直接写入文件，超时仅清理查询进程树。
每个冒烟阶段的目录保存 `process-query.json`、`process-query.stdout.log` 和
`process-query.stderr.log`，分别提供状态、查询结果和错误输出；这些文件随现有
诊断附件上传。`result.json` 同时记录触发冒烟失败的错误信息。

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
