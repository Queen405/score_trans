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

    # Clean previous build
    for d in [PROJECT_ROOT / "build", PROJECT_ROOT / "dist"]:
        if d.exists():
            shutil.rmtree(d)

    # Run PyInstaller
    run(
        [python, "-m", "PyInstaller", "pyinstaller.spec", "--noconfirm"],
        cwd=PROJECT_ROOT,
    )

    # Copy output to build-resources/backend
    pyinstaller_out = PROJECT_ROOT / "dist" / "backend"
    if BACKEND_DIST.exists():
        shutil.rmtree(BACKEND_DIST)
    shutil.copytree(pyinstaller_out, BACKEND_DIST)

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
        shutil.copytree(java_home, JRE_DIR / "jdk")
        print(f"    JRE 已复制: {JRE_DIR / 'jdk'}")
        return

    # 其次检查 JAVA_HOME 环境变量
    env_java = os.environ.get("JAVA_HOME", "")
    if env_java and (Path(env_java) / "bin" / "java.exe").exists():
        print(f"    复用 JAVA_HOME: {env_java}")
        shutil.copytree(env_java, JRE_DIR / "jdk")
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
    run(["pnpm", "install"], cwd=desktop)
    run(["pnpm", "build"], cwd=desktop)
    print("    Electron 前端构建完成")


# ---------------------------------------------------------------------------
# Step 5 — Package with electron-builder
# ---------------------------------------------------------------------------

def package_electron() -> None:
    print("\n" + "=" * 60)
    print("[5/5] 打包 Electron 应用 (electron-builder) ...")
    print("=" * 60)

    desktop = PROJECT_ROOT / "desktop"
    run(["pnpm", "electron-builder", "build", "--win", "--config"], cwd=desktop)

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
