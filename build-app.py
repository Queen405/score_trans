"""Score Trans 一键打包脚本

将 Python 后端、Audiveris（含 JRE）、Electron 前端打包为独立的 Windows 安装包。

用法:
    python build-app.py                    # 完整构建
    python build-app.py --skip-backend     # 跳过后端（仅前端+打包）
    python build-app.py --skip-jre         # 跳过 JRE 下载（使用已有 JRE）
    python build-app.py --skip-electron    # 跳过 Electron 构建（仅后端）
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from urllib.request import urlretrieve

PROJECT_ROOT = Path(__file__).resolve().parent
BUILD_RESOURCES = PROJECT_ROOT / "build-resources"
BACKEND_DIST = BUILD_RESOURCES / "backend"
THIRD_PARTY = BUILD_RESOURCES / "third_party"
JRE_DIR = THIRD_PARTY / "jre"
AUVERERIS_DIR = THIRD_PARTY / "audiveris"

JDK_URL = (
    "https://api.adoptium.net/v3/binary/latest/25/ga/windows/x64/jdk/hotspot/normal/eclipse"
)
JDK_ZIP = BUILD_RESOURCES / "jdk.zip"

# 本地 JDK 25 路径（开发机已安装时直接复用）
LOCAL_JDK = Path(os.environ.get("SCORE_TRANS_JAVA_HOME", r"E:\ENV\JAVA\JDK25"))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(cmd: list[str], cwd: str | Path | None = None, env: dict | None = None, **kwargs) -> None:
    """Run a command, streaming stdout/stderr, and raise on failure."""
    merged_env = {**os.environ, **(env or {})}
    print(f"\n>>> {' '.join(cmd)}")
    result = subprocess.run(
        cmd, cwd=str(cwd) if cwd else None, env=merged_env, **kwargs
    )
    if result.returncode != 0:
        print(f"\n[ERROR] 命令失败 (exit {result.returncode}): {' '.join(cmd)}")
        sys.exit(1)


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


# ---------------------------------------------------------------------------
# Step 1 — Build Python backend (PyInstaller)
# ---------------------------------------------------------------------------

def build_backend() -> None:
    print("\n" + "=" * 60)
    print("[1/5] 打包 Python 后端 (PyInstaller) ...")
    print("=" * 60)

    python = sys.executable

    # Ensure PyInstaller is installed
    try:
        subprocess.run(
            [python, "-m", "PyInstaller", "--version"],
            capture_output=True, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("    安装 PyInstaller ...")
        run([python, "-m", "pip", "install", "pyinstaller>=6"])

    # Clean previous build (only PyInstaller's own output, not build-resources)
    for d in [PROJECT_ROOT / "build", PROJECT_ROOT / "dist"]:
        if d.exists():
            shutil.rmtree(d)

    # Run PyInstaller
    run(
        [python, "-m", "PyInstaller", "pyinstaller.spec", "--noconfirm"],
        cwd=PROJECT_ROOT,
    )

    # Copy output to build-resources/backend (using copy2 to resolve symlinks)
    pyinstaller_out = PROJECT_ROOT / "dist" / "backend"
    if BACKEND_DIST.exists():
        shutil.rmtree(BACKEND_DIST)
    shutil.copytree(pyinstaller_out, BACKEND_DIST, copy_function=shutil.copy2)

    # Copy .env (env.example as default config) into the backend bundle
    env_example = PROJECT_ROOT / "backend" / "score_trans" / "config" / "env.example"
    env_target = BACKEND_DIST / ".env"
    if env_example.exists():
        shutil.copy2(env_example, env_target)
        print(f"    .env 已复制: {env_target}")

    exe = BACKEND_DIST / "backend.exe"
    size_mb = exe.stat().st_size / (1024 * 1024) if exe.exists() else 0
    print(f"    后端打包完成: {exe}  ({size_mb:.1f} MB)")


# ---------------------------------------------------------------------------
# Step 2 — Set up third_party/audiveris
# ---------------------------------------------------------------------------

def setup_audiveris() -> None:
    print("\n" + "=" * 60)
    print("[2/5] 配置 Audiveris ...")
    print("=" * 60)

    src = PROJECT_ROOT / "third_party" / "audiveris"
    if not src.exists():
        print("    [WARNING] third_party/audiveris 不存在，跳过")
        return

    ensure_dir(THIRD_PARTY)
    dst = AUVERERIS_DIR
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)

    gradlew = dst / "gradlew.bat"
    print(f"    Audiveris 已复制: {dst}")
    print(f"    gradlew.bat 存在: {gradlew.exists()}")

    # 清理 Audiveris 无用文件以减小体积
    _cleanup_audiveris(dst)

    # 预缓存 Gradle 发行版，避免用户环境下 SSL 证书问题导致下载失败
    _cache_gradle(dst)


def _cleanup_audiveris(audiveris_dir: Path) -> None:
    """删除 Audiveris 中不需要的文件以减小打包体积。"""
    removed_mb = 0.0

    # 1. 删除 Gradle 构建缓存和 Eclipse 编译输出
    for name in ["app/build", "app/bin", ".gradle"]:
        target = audiveris_dir / name
        if target.exists():
            size = sum(f.stat().st_size for f in target.rglob("*") if f.is_file())
            shutil.rmtree(target)
            removed_mb += size / (1024 * 1024)

    # 2. 删除文档文件
    for name in ["README.md", "LICENSE", "CHANGELOG.md", ".gitignore"]:
        target = audiveris_dir / name
        if target.exists():
            size = target.stat().st_size
            target.unlink()
            removed_mb += size / (1024 * 1024)

    # 3. 删除源码中的测试目录（运行时不需要）
    test_dir = audiveris_dir / "app" / "src" / "test"
    if test_dir.exists():
        size = sum(f.stat().st_size for f in test_dir.rglob("*") if f.is_file())
        shutil.rmtree(test_dir)
        removed_mb += size / (1024 * 1024)

    if removed_mb > 0:
        print(f"    清理 Audiveris 无用文件: {removed_mb:.1f} MB")


def _cache_gradle(audiveris_dir: Path) -> None:
    """将本地 Gradle 发行版复制到应用中，避免用户环境下 SSL 证书问题导致下载失败。
    只保留解压目录和标记文件，去掉 ZIP 以减小体积。"""
    import re
    gradle_dist_dir = audiveris_dir / "gradle" / "wrapper"
    wrapper_props = gradle_dist_dir / "gradle-wrapper.properties"
    if not wrapper_props.exists():
        print("    [WARNING] gradle-wrapper.properties 不存在，跳过 Gradle 缓存")
        return

    props_text = wrapper_props.read_text(encoding="utf-8")
    version = None
    for line in props_text.splitlines():
        if line.startswith("distributionUrl="):
            url = line.split("=", 1)[1].strip().replace("\\:", ":")
            m = re.search(r"gradle-([\d.]+)-bin\.zip", url)
            if m:
                version = m.group(1)
            break

    if not version:
        print("    [WARNING] 无法从 wrapper 配置提取 Gradle 版本")
        return

    print(f"    Gradle 版本: {version}")

    # 查找本地 Gradle 缓存（~/.gradle/wrapper/dists/gradle-X.Y-bin/<hash>/）
    local_gradle_cache = Path.home() / ".gradle" / "wrapper" / "dists" / f"gradle-{version}-bin"
    if not local_gradle_cache.exists():
        print(f"    [WARNING] 未找到本地 Gradle {version} 缓存，用户首次运行时需联网下载")
        return

    # 在 hash 子目录中查找解压目录
    gradle_extracted_src = None
    hash_dir = None

    for hd in local_gradle_cache.iterdir():
        if not hd.is_dir():
            continue
        hash_dir = hd
        ext_candidate = hd / f"gradle-{version}"
        if ext_candidate.exists() and (ext_candidate / "bin").is_dir():
            gradle_extracted_src = ext_candidate

    if not gradle_extracted_src:
        print(f"    [WARNING] 未找到本地 Gradle {version} 解压目录，用户首次运行时需联网下载")
        return

    if not hash_dir:
        print(f"    [WARNING] 未找到 Gradle 缓存 hash 目录")
        return

    hash_name = hash_dir.name
    app_gradle_home = THIRD_PARTY / "gradle_home"
    cache_dir = app_gradle_home / "wrapper" / "dists" / f"gradle-{version}-bin" / hash_name
    ensure_dir(cache_dir)

    # 复制解压目录
    print(f"    本地 Gradle 解压目录: {gradle_extracted_src}")
    gradle_extracted_dst = cache_dir / f"gradle-{version}"
    if not gradle_extracted_dst.exists():
        shutil.copytree(gradle_extracted_src, gradle_extracted_dst, copy_function=shutil.copy2)
    print(f"    Gradle 已复制: {gradle_extracted_dst}")

    # 创建标记文件（让 wrapper 认为已下载完成）
    for suffix in [".ok", ".lck"]:
        marker = cache_dir / f"gradle-{version}-bin.zip{suffix}"
        if not marker.exists():
            marker.touch()

    # 去掉 wrapper 的 SHA-256 校验和 URL 验证（没有 ZIP 文件）
    wrapper_props_target = audiveris_dir / "gradle" / "wrapper" / "gradle-wrapper.properties"
    if wrapper_props_target.exists():
        props = wrapper_props_target.read_text(encoding="utf-8")
        changed = False
        if "distributionSha256Sum=" in props:
            props = props.replace("distributionSha256Sum=", "#distributionSha256Sum=")
            changed = True
        if "validateDistributionUrl=true" in props:
            props = props.replace("validateDistributionUrl=true", "validateDistributionUrl=false")
            changed = True
        if changed:
            wrapper_props_target.write_text(props, encoding="utf-8")
            print("    已禁用 Gradle SHA-256 校验和 URL 验证")

    print(f"    Gradle 缓存目录: {cache_dir}")


# ---------------------------------------------------------------------------
# Step 3 — Bundle JRE
# ---------------------------------------------------------------------------

def download_jre() -> None:
    """Copy or download JDK 25 into build-resources/third_party/jre/."""
    print("\n" + "=" * 60)
    print("[3/5] 配置 JRE (JDK 25) ...")
    print("=" * 60)

    if JRE_DIR.exists():
        print(f"    JRE 已存在: {JRE_DIR}，跳过下载")
        return

    ensure_dir(JRE_DIR)

    # 优先复用本地 JDK 25
    java_home = str(LOCAL_JDK)
    if Path(java_home).exists() and (Path(java_home) / "bin" / "java.exe").exists():
        print(f"    复用本地 JDK 25: {java_home}")
        shutil.copytree(java_home, JRE_DIR / "jdk", copy_function=shutil.copy2)
        print(f"    JRE 已复制: {JRE_DIR / 'jdk'}")
        return

    # 其次检查 JAVA_HOME 环境变量
    env_java = os.environ.get("JAVA_HOME", "")
    if env_java and (Path(env_java) / "bin" / "java.exe").exists():
        print(f"    复用 JAVA_HOME: {env_java}")
        shutil.copytree(env_java, JRE_DIR / "jdk", copy_function=shutil.copy2)
        print(f"    JRE 已复制: {JRE_DIR / 'jdk'}")
        return

    print(f"    下载 JDK 25 ...")
    print(f"    URL: {JDK_URL}")
    ensure_dir(BUILD_RESOURCES)

    def _progress(block_num, block_size, total_size):
        downloaded = block_num * block_size
        if total_size > 0:
            pct = min(100, downloaded * 100 / total_size)
            mb = downloaded / (1024 * 1024)
            total_mb = total_size / (1024 * 1024)
            print(f"\r    下载进度: {pct:.0f}% ({mb:.1f}/{total_mb:.1f} MB)", end="", flush=True)

    try:
        urlretrieve(JDK_URL, str(JDK_ZIP), reporthook=_progress)
    except Exception as exc:
        print(f"\n    [ERROR] JDK 下载失败: {exc}")
        print("    请手动下载 JDK 25 并解压到 build-resources/third_party/jre/jdk/")
        print(f"    下载地址: {JDK_URL}")
        sys.exit(1)

    print("\n    解压 JDK ...")
    extract_dir = ensure_dir(JRE_DIR)
    with zipfile.ZipFile(JDK_ZIP, "r") as zf:
        zf.extractall(extract_dir)

    JDK_ZIP.unlink(missing_ok=True)

    # Find the extracted directory (e.g., jdk-21.0.x+y)
    extracted_dirs = [d for d in extract_dir.iterdir() if d.is_dir() and d.name.startswith("jdk")]
    if extracted_dirs:
        jdk_inner = extracted_dirs[0]
        # Flatten: move contents up so JRE_DIR = JRE_DIR/<jdk-version>/
        # We keep the subdirectory; the settings will store the full path
        print(f"    JRE 已解压: {jdk_inner}")
    else:
        print(f"    [WARNING] 解压后未找到 JDK 目录，请检查 {extract_dir}")


# ---------------------------------------------------------------------------
# Step 4 — Build Electron frontend
# ---------------------------------------------------------------------------

def build_electron_frontend() -> None:
    print("\n" + "=" * 60)
    print("[4/5] 构建 Electron 前端 ...")
    print("=" * 60)

    desktop = PROJECT_ROOT / "desktop"
    pnpm = _find_pnpm()
    run([pnpm, "install"], cwd=desktop)
    run([pnpm, "build"], cwd=desktop)
    print("    Electron 前端构建完成")


def _find_pnpm() -> str:
    """查找 pnpm 可执行文件，支持多种安装方式。"""
    import shutil
    # 确保常见 node/pnpm 目录在 PATH 中
    extra_dirs = []
    npm_prefix = Path(os.environ.get("APPDATA", "")) / "npm"
    if npm_prefix.exists():
        extra_dirs.append(str(npm_prefix))
    for d in [Path.home() / "AppData" / "Local" / "pnpm", Path(r"E:\ENV\npm")]:
        if d.exists() and str(d) not in os.environ.get("PATH", ""):
            extra_dirs.append(str(d))
    if extra_dirs:
        os.environ["PATH"] = os.pathsep.join(extra_dirs) + os.pathsep + os.environ.get("PATH", "")

    # 1. PATH 中的 pnpm
    found = shutil.which("pnpm")
    if found:
        return found
    # 2. npm 全局安装的 pnpm
    npm_global = shutil.which("npm")
    if npm_global:
        pnpm_candidate = Path(npm_global).parent / "pnpm.cmd"
        if pnpm_candidate.exists():
            return str(pnpm_candidate)
    print("    [ERROR] 找不到 pnpm，请先安装: npm install -g pnpm")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Step 5 — Package with electron-builder
# ---------------------------------------------------------------------------

def package_electron() -> None:
    print("\n" + "=" * 60)
    print("[5/5] 打包 Electron 应用 (electron-builder) ...")
    print("=" * 60)

    desktop = PROJECT_ROOT / "desktop"
    pnpm = _find_pnpm()
    run([pnpm, "electron-builder", "build", "--win", "--config"], cwd=desktop)

    dist = desktop / "dist-electron"
    print(f"\n    打包完成！输出目录: {dist}")
    installers = list(dist.glob("*.exe"))
    for f in installers:
        size_mb = f.stat().st_size / (1024 * 1024)
        print(f"    → {f.name}  ({size_mb:.1f} MB)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Score Trans 一键打包")
    parser.add_argument("--skip-backend", action="store_true", help="跳过 PyInstaller 后端构建")
    parser.add_argument("--skip-jre", action="store_true", help="跳过 JRE 下载")
    parser.add_argument("--skip-electron", action="store_true", help="跳过 Electron 构建和打包")
    args = parser.parse_args()

    print("╔══════════════════════════════════════════╗")
    print("║     Score Trans 应用打包工具              ║")
    print("╚══════════════════════════════════════════╝")
    print(f"项目根目录: {PROJECT_ROOT}")

    if not args.skip_backend:
        build_backend()
    else:
        print("\n[1/5] 跳过后端构建")

    setup_audiveris()

    if not args.skip_jre:
        download_jre()
    else:
        print("\n[3/5] 跳过 JRE 配置")

    if not args.skip_electron:
        build_electron_frontend()
        package_electron()
    else:
        print("\n[4-5/5] 跳过 Electron 构建")

    print("\n" + "=" * 60)
    print("打包流程全部完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
