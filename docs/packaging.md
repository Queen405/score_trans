# 打包指南

本文档描述 Score Trans 的完整打包流程、关键注意事项和常见问题。AI 代理阅读本文档后应能正确完成打包。

---

## 概述

打包使用项目根目录的 `build-app.py` 一键脚本，将 Python 后端、Audiveris（含 JRE）、Electron 前端打包为 Windows NSIS 安装包。

```
build-app.py 五个阶段：
  [1/5] PyInstaller 打包 Python 后端 → build-resources/backend/
  [2/5] 复制 Audiveris + 清理 + 缓存 Gradle → build-resources/third_party/audiveris/
  [3/5] 配置 JRE (JDK 25) → build-resources/third_party/jre/
  [4/5] pnpm build 构建 Electron 前端 → desktop/out/
  [5/5] electron-builder 生成 NSIS 安装包 → desktop/dist-electron/Score Trans Setup 0.1.0.exe
```

最终产物：`desktop/dist-electron/Score Trans Setup 0.1.0.exe`（约 450-470 MB）

---

## 前置条件

| 依赖 | 要求 | 检查方式 |
|------|------|----------|
| Python | 3.13+，已创建 `.venv` | `.venv/Scripts/python.exe --version` |
| PyInstaller | 6.20+（脚本会自动安装） | `.venv/Scripts/python.exe -m PyInstaller --version` |
| pnpm | 11+ | `pnpm --version` |
| JDK 25 | 用于 Audiveris 运行时打包 | `E:\ENV\JAVA\JDK25\bin\java.exe` 存在 |
| Gradle 9.1.0 | 用于 Audiveris 编译（本地缓存即可） | `~/.gradle/wrapper/dists/gradle-9.1.0-bin/` 存在 |

### 首次准备

```bash
# 1. 创建 Python 虚拟环境
uv venv .venv --python 3.13
uv pip install -e ".[test]" --python .venv/Scripts/python.exe

# 2. 安装前端依赖
cd desktop && pnpm install && cd ..

# 3. 确保 Audiveris 已编译过至少一次（生成 app/build/）
cd third_party/audiveris
set JAVA_HOME=E:\ENV\JAVA\JDK25
gradlew.bat :app:compileJava
cd ..\..
```

---

## 打包命令

```bash
# 完整打包（首次或后端代码有变更时使用）
.venv/Scripts/python.exe build-app.py

# 跳过 JRE 下载（build-resources/third_party/jre 已存在时）
.venv/Scripts/python.exe build-app.py --skip-jre

# 仅重新打包前端（后端和第三方资源未变时）
.venv/Scripts/python.exe build-app.py --skip-backend --skip-jre
# 然后单独执行 electron-builder:
cd desktop && pnpm electron-builder build --win --config
```

---

## 关键注意事项

### 1. Audiveris 的 `app/build/` 必须保留

**这是最重要的注意事项。** `_cleanup_audiveris()` 函数中，`app/build` 目录**不能删除**。

`app/build/` 包含：
- `generated-src/org/audiveris/omr/ProgramId.java` — Gradle `generateProgramId` 任务预生成的源文件
- `commit.properties` — Git commit 缓存（值为 `source-zip`）
- `classes/` — 编译好的 `.class` 文件（约 2184 个）

**如果删除 `app/build/`：**
用户机器首次运行时，Gradle 的 `generateProgramId` 任务会重新生成 `ProgramId.java`。该任务在部分环境下会生成**损坏的文件**（只有 `package` 声明和 `}`，缺少中间的 `class` 定义），导致 `:app:compileJava` 失败，报错 "Audiveris 执行失败"。

**原理：**
- `checkCommit` 任务读取 `build/commit.properties` 缓存。如果缓存存在且 commit 值匹配（都是 `source-zip`），则不设置 `commitChanged` 属性。
- `generateProgramId` 任务有 `onlyIf { project.hasProperty('commitChanged') }`，不设置则跳过。
- 保留 `commit.properties` → `generateProgramId` 跳过 → 使用预生成的 `ProgramId.java`（完整正确）。

**正确的清理策略：**
```python
# _cleanup_audiveris() 中：
# ✅ 正确：保留 app/build，删除 .gradle 和 app/bin
for name in ["app/bin", ".gradle"]:
    ...

# ❌ 错误：删除 app/build 会导致 ProgramId.java 损坏
for name in ["app/build", "app/bin", ".gradle"]:
    ...
```

### 2. `.gradle/` 必须删除

`_cleanup_audiveris()` **必须删除** `.gradle/` 目录。

`.gradle/` 中的 `executionHistory.bin` 包含**开发机的绝对路径**（如 `D:\CODE\MyProjects\score_trans\...`）。如果保留，用户机器上路径不匹配会导致 Gradle 缓存失效、行为异常。

删除后，用户首次运行时 Gradle 会重建 `.gradle/`，这是正常行为（只需确保安装目录可写）。

### 3. 打包前确保 Audiveris 已编译

打包前，开发机的 `third_party/audiveris/app/build/` 必须存在且内容完整。如果该目录不存在或过期：

```bash
cd third_party/audiveris
set JAVA_HOME=E:\ENV\JAVA\JDK25
gradlew.bat :app:compileJava
```

`build-app.py` 会在复制 Audiveris 后检查生成的
`app/build/generated-src/org/audiveris/omr/ProgramId.java`。如果它来自旧版本并包含已移除的
`TESSDATA_TAG`，打包会立即失败；请先执行上面的 clean 编译，再重新运行打包脚本。清理流程
还会删除残留的 OCR 类、语言数据和原生库，同时保留其他 `app/build` 编译产物。

`build-app.py` 的 `setup_audiveris()` 会将开发机的 `third_party/audiveris/` 整体复制到 `build-resources/third_party/audiveris/`，所以开发机的 `app/build/` 状态直接决定打包结果。

### 4. 安装目录必须可写

Audiveris 通过 `gradlew.bat :app:run` 运行，Gradle 需要：
- 创建 `.gradle/`（项目缓存）
- 可能重编译 `.class` 文件
- 写入 `build/` 目录

因此安装目录不能是 `C:\Program Files\` 等只读路径。NSIS 安装器默认安装到用户目录（`%LocalAppData%\Programs\Score Trans\`），是可写的。如果用户选择安装到只读目录，Audiveris 会失败。

### 5. 路径解析（打包模式）

PyInstaller 打包后，路径解析如下（`backend/score_trans/models/common/paths.py`）：

```
sys.executable = <安装目录>/resources/backend/backend.exe
PROJECT_ROOT    = <安装目录>/resources/
CONFIG_DIR      = <安装目录>/resources/backend/
```

Audiveris、JRE、Gradle 缓存的打包路径：
- Audiveris: `PROJECT_ROOT/third_party/audiveris/gradlew.bat`
- JRE: `PROJECT_ROOT/third_party/jre/jdk/`
- Gradle 缓存: `PROJECT_ROOT/third_party/gradle_home/`

`electron-builder.yml` 中 `extraResources` 将 `build-resources/backend` 和 `build-resources/third_party` 映射到安装包的 `resources/` 目录。

### 6. settings.db 路径回退

`SettingsService.load()` 中的 `_resolve_existing_path()` 会在存储的 `audiveris_path` 或 `java_home` 指向不存在的路径时，自动回退到打包内置的默认路径。这确保了即使 settings.db 中有开发环境的旧路径，在其他机器上也能正常工作。

---

## 打包流程详解

### 阶段 1: PyInstaller 打包后端

```bash
.venv/Scripts/python.exe -m PyInstaller pyinstaller.spec --noconfirm
```

- 入口点：`pyinstaller_entry.py`
- 输出：`dist/backend/backend.exe` + `dist/backend/_internal/`
- 复制到：`build-resources/backend/`
- 同时复制 `env.example` 为 `build-resources/backend/.env`

### 阶段 2: 配置 Audiveris

1. 复制 `third_party/audiveris/` → `build-resources/third_party/audiveris/`
2. `_cleanup_audiveris()`：删除 `app/bin`、`.gradle`、文档文件、测试目录（**保留 `app/build`**）
3. `_cache_gradle()`：复制本地 Gradle 发行版到 `build-resources/third_party/gradle_home/`

### 阶段 3: 配置 JRE

- 优先复用本地 `SCORE_TRANS_JAVA_HOME`（默认 `E:\ENV\JAVA\JDK25`）
- 其次检查 `JAVA_HOME` 环境变量
- 最后从 Adoptium 下载 JDK 25
- 输出：`build-resources/third_party/jre/jdk/`

### 阶段 4: 构建 Electron 前端

```bash
cd desktop
pnpm install
pnpm build  # electron-vite build
```

输出：`desktop/out/`（main、preload、renderer）

### 阶段 5: electron-builder 打包

```bash
cd desktop
pnpm electron-builder build --win --config
```

- 配置：`desktop/electron-builder.yml`
- 目标：NSIS 安装包（非一键安装，允许选择安装目录）
- 输出：`desktop/dist-electron/Score Trans Setup 0.1.0.exe`

---

## 验证打包结果

### 基本检查

```python
# 验证关键文件存在
from pathlib import Path
pkg = Path("desktop/dist-electron/win-unpacked/resources")

# 1. 后端
assert (pkg / "backend/backend.exe").exists()
assert (pkg / "backend/.env").exists()

# 2. Audiveris
audiveris = pkg / "third_party/audiveris"
assert (audiveris / "gradlew.bat").exists()

# 3. ProgramId.java（最关键的检查）
pid = audiveris / "app/build/generated-src/org/audiveris/omr/ProgramId.java"
assert pid.exists(), "ProgramId.java MISSING — app/build was wrongly deleted!"
content = pid.read_text()
assert "public abstract class ProgramId" in content, "ProgramId.java corrupted!"
assert len(content) > 500, f"ProgramId.java too small ({len(content)} bytes) — possibly corrupted"

# 4. commit.properties（阻止 generateProgramId 重新运行）
cp = audiveris / "app/build/commit.properties"
assert cp.exists(), "commit.properties MISSING — generateProgramId will regenerate and may corrupt!"

# 5. 编译好的 .class 文件
classes = audiveris / "app/build/classes"
assert classes.exists(), "Compiled classes MISSING"
class_count = sum(1 for f in classes.rglob("*.class"))
assert class_count > 1000, f"Too few .class files: {class_count}"

# 6. .gradle 不应存在（含开发机绝对路径）
assert not (audiveris / ".gradle").exists(), ".gradle should be deleted!"

# 7. JRE
assert (pkg / "third_party/jre/jdk/bin/java.exe").exists()

# 8. Gradle 缓存
assert (pkg / "third_party/gradle_home").exists()
```

### 端到端测试（模拟其他机器）

```bash
# 启动打包的 backend.exe，使用全新数据目录
.venv/Scripts/python.exe -c "
import subprocess, os
env = os.environ.copy()
env['SCORE_TRANS_API_TOKEN'] = 'test-token-32-chars-minxxxxxxxxxxxxx'
env['SCORE_TRANS_DATA_DIR'] = r'C:\tmp\test_data'
env['SCORE_TRANS_CACHE_DIR'] = r'C:\tmp\test_cache'
os.makedirs(env['SCORE_TRANS_DATA_DIR'], exist_ok=True)
os.makedirs(env['SCORE_TRANS_CACHE_DIR'], exist_ok=True)
proc = subprocess.Popen([
    'desktop/dist-electron/win-unpacked/resources/backend/backend.exe',
    '--host', '127.0.0.1', '--port', '19299'
], cwd='desktop/dist-electron/win-unpacked/resources/backend', env=env)
# ... 调用 /recognize API 提交图片，轮询 /tasks/{id} 直到完成
"
```

---

## 常见问题

### 问题：Audiveris 执行失败（ProgramId.java 损坏）

**症状**：识别报错 "Audiveris 执行失败，请查看完整日志定位原因。"

**原因**：`_cleanup_audiveris()` 删除了 `app/build/`，导致用户机器上 `generateProgramId` 重新生成损坏的 `ProgramId.java`。

**修复**：确保 `_cleanup_audiveris()` 中**不删除** `app/build`。

### 问题：Gradle 下载失败（SSL 证书问题）

**症状**：用户首次运行时 Gradle 尝试下载发行版失败。

**修复**：`_cache_gradle()` 已将本地 Gradle 发行版复制到 `build-resources/third_party/gradle_home/`。确保开发机的 `~/.gradle/wrapper/dists/gradle-9.1.0-bin/` 存在。

### 问题：后端代码更新后未重新打包

**症状**：安装包中的后端功能是旧版本。

**修复**：不要使用 `--skip-backend`。后端 Python 代码有任何变更时，必须重新运行 PyInstaller。

### 问题：electron-builder 报 ERR_ELECTRON_BUILDER_CANNOT_EXECUTE

**症状**：electron-builder 打包失败。

**原因**：`win-unpacked/` 中的文件被占用（如 backend.exe 进程仍在运行）。

**修复**：
```bash
taskkill /F /IM backend.exe
taskkill /F /IM "Score Trans.exe"
# 然后重新运行 electron-builder
```

### 问题：安装包体积过大

安装包约 450-470 MB，主要组成：
- Electron 运行时：~180 MB
- JRE (JDK 25)：~200 MB
- Audiveris（含 app/build 编译产物）：~50 MB
- Python 后端（PyInstaller）：~60 MB

不要为了减小体积而删除 `app/build/`，这会导致 ProgramId.java 损坏问题。

---

## 文件索引

| 文件 | 作用 |
|------|------|
| `build-app.py` | 一键打包脚本（5 个阶段） |
| `pyinstaller.spec` | PyInstaller 打包配置 |
| `pyinstaller_entry.py` | PyInstaller 入口点 |
| `desktop/electron-builder.yml` | electron-builder 配置 |
| `desktop/electron.vite.config.ts` | electron-vite 构建配置 |
| `backend/score_trans/models/common/paths.py` | 打包模式路径解析 |
| `backend/score_trans/services/settings/settings_service.py` | 设置加载与路径回退 |
| `backend/score_trans/services/recognize/external_tools.py` | Audiveris 调用逻辑 |
| `third_party/audiveris/app/build.gradle` | Audiveris Gradle 构建（含 generateProgramId 任务） |
