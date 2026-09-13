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
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
BUILD_RESOURCES = PROJECT_ROOT / "build-resources"
BACKEND_DIST = BUILD_RESOURCES / "backend"
THIRD_PARTY = BUILD_RESOURCES / "third_party"
JRE_DIR = THIRD_PARTY / "jre"
AUVERERIS_DIR = THIRD_PARTY / "audiveris"

# 本地 JDK 25 路径（开发机已安装时直接复用）
LOCAL_JDK = Path(
    os.environ.get("SCORE_TRANS_JAVA_HOME")
    or os.environ.get("JAVA_HOME")
    or r"E:\ENV\JAVA\JDK25"
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run(
    cmd: list[str], cwd: str | Path | None = None, env: dict | None = None, **kwargs
) -> None:
    """Run a command, streaming stdout/stderr, and raise on failure."""
    merged_env = {**os.environ, **(env or {})}
    print(f"\n>>> {' '.join(cmd)}")
    result = subprocess.run(
        cmd, cwd=str(cwd) if cwd else None, env=merged_env, check=False, **kwargs
    )
    if result.returncode != 0:
        print(f"\n[ERROR] 命令失败 (exit {result.returncode}): {' '.join(cmd)}")
        sys.exit(1)


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


# ---------------------------------------------------------------------------
# Published defaults validation
# ---------------------------------------------------------------------------

_PUBLISHED_DEFAULTS_SRC = (
    PROJECT_ROOT / "backend" / "score_trans" / "config" / "published_defaults.json"
)
_ENV_EXAMPLE_SRC = PROJECT_ROOT / "backend" / "score_trans" / "config" / "env.example"

_PRIVATE_NAME_FRAGMENTS = ("api_key", "token", "password", "secret", "credential")
_ABSOLUTE_PATH_RE = re.compile(
    r"^[A-Za-z]:[\\/]"  # Windows drive path (C:\ or C:/)
    r"|^/"  # Unix absolute path
    r"|^~"  # Home directory
    r"|/Users/"  # macOS user directory
    r"|\\\\",  # UNC path
)
_BACKEND_STRING_KEYS = (
    "audiveris_max_heap",
    "audiveris_max_pixel_count",
    "audiveris_auto_upscale",
    "audiveris_min_image_edge",
    "target_key",
    "accidental_mode",
    "measure_number_mode",
    "show_measure_numbers",
    "jianpu_syntax_highlight",
    "jianpu_content_scale_percent",
    "jianpu_system_gap_percent",
    "jianpu_short_note_gap_percent",
    "enable_omr_ocr",
    "output_dir",
)


def _parse_env_example(path: Path) -> dict[str, str]:
    """Parse env.example into a flat KEY -> value mapping.

    Strips surrounding single/double quotes so that JSON profile values
    can be re-parsed downstream.
    """
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        result[key] = value
    return result


def _reject_private_or_path_values(payload: object, trail: str = "") -> None:
    """Recursively reject private field names and absolute-path string values."""
    if isinstance(payload, dict):
        for key, value in payload.items():
            lower = str(key).lower()
            if any(frag in lower for frag in _PRIVATE_NAME_FRAGMENTS):
                raise RuntimeError(
                    f"published_defaults.json contains private field: {trail}.{key}"
                )
            if isinstance(value, str) and _ABSOLUTE_PATH_RE.search(value):
                raise RuntimeError(
                    f"published_defaults.json contains an absolute path or "
                    f"user directory: {trail}.{key}={value!r}"
                )
            _reject_private_or_path_values(value, f"{trail}.{key}")
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            _reject_private_or_path_values(item, f"{trail}[{index}]")


def _cross_validate_providers(providers: dict, env_vars: dict[str, str]) -> None:
    """Ensure baseline provider selections match env.example profiles."""
    for kind in ("ocr", "ai", "assistant"):
        section = providers.get(kind)
        if not isinstance(section, dict):
            raise TypeError(
                f"published_defaults.json providers.{kind} must be an object"
            )
        kind_upper = kind.upper()
        provider_env = f"SCORE_TRANS_{kind_upper}_PROVIDER"
        profiles_env = f"SCORE_TRANS_{kind_upper}_PROVIDER_PROFILES"

        baseline_id = section.get("provider")
        env_provider_id = env_vars.get(provider_env, "")
        if not env_provider_id:
            raise RuntimeError(f"env.example is missing {provider_env}")
        if baseline_id != env_provider_id:
            raise RuntimeError(
                f"baseline providers.{kind}.provider={baseline_id!r} does not match "
                f"env.example {provider_env}={env_provider_id!r}"
            )

        profiles_raw = env_vars.get(profiles_env, "")
        if not profiles_raw:
            raise RuntimeError(f"env.example is missing {profiles_env}")
        try:
            profiles = json.loads(profiles_raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"env.example {profiles_env} is not valid JSON: {exc}"
            ) from exc
        if not isinstance(profiles, list) or not profiles:
            raise RuntimeError(
                f"env.example {profiles_env} must be a non-empty JSON array"
            )

        matched = None
        for profile in profiles:
            if isinstance(profile, dict) and profile.get("id") == baseline_id:
                matched = profile
                break
        if matched is None:
            raise RuntimeError(
                f"baseline providers.{kind}.provider={baseline_id!r} is not "
                f"present in env.example {profiles_env}"
            )

        baseline_url = section.get("base_url")
        if matched.get("base_url") != baseline_url:
            raise RuntimeError(
                f"baseline providers.{kind}.base_url={baseline_url!r} does not "
                f"match profile {baseline_id!r} base_url={matched.get('base_url')!r}"
            )
        baseline_model = section.get("model")
        if matched.get("model") != baseline_model:
            raise RuntimeError(
                f"baseline providers.{kind}.model={baseline_model!r} does not "
                f"match profile {baseline_id!r} model={matched.get('model')!r}"
            )
        if kind == "ocr":
            baseline_fallback = section.get("fallback_model", "")
            if matched.get("fallback_model", "") != baseline_fallback:
                raise RuntimeError(
                    f"baseline providers.ocr.fallback_model={baseline_fallback!r} "
                    f"does not match profile {baseline_id!r} "
                    f"fallback_model={matched.get('fallback_model')!r}"
                )


def _validate_published_defaults(project_root: Path) -> dict:
    """Validate published_defaults.json structure and cross-check providers."""
    path = (
        project_root / "backend" / "score_trans" / "config" / "published_defaults.json"
    )
    if not path.is_file():
        raise RuntimeError(f"published_defaults.json not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"published_defaults.json is invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise TypeError("published_defaults.json must be a JSON object")
    if payload.get("version") != 1:
        raise RuntimeError(
            f"published_defaults.json version must be 1, got {payload.get('version')!r}"
        )

    _reject_private_or_path_values(payload)

    backend = payload.get("backend")
    if not isinstance(backend, dict):
        raise TypeError("published_defaults.json must contain a 'backend' object")
    for key in _BACKEND_STRING_KEYS:
        if not isinstance(backend.get(key), str):
            raise TypeError(f"published_defaults.json backend.{key} must be a string")
    providers = payload.get("providers")
    if not isinstance(providers, dict):
        raise TypeError("published_defaults.json must contain a 'providers' object")

    env_example = project_root / "backend" / "score_trans" / "config" / "env.example"
    if not env_example.is_file():
        raise RuntimeError(f"env.example not found: {env_example}")
    env_vars = _parse_env_example(env_example)
    _cross_validate_providers(providers, env_vars)

    return payload


# ---------------------------------------------------------------------------
# Step 1 — Build Python backend (PyInstaller)
# ---------------------------------------------------------------------------


def build_backend() -> None:
    print("\n" + "=" * 60)
    print("[1/5] 打包 Python 后端 (PyInstaller) ...")
    print("=" * 60)

    # Fail fast: validate published_defaults.json before any expensive build step.
    _validate_published_defaults(PROJECT_ROOT)
    print("    published_defaults.json 校验通过")

    python = sys.executable

    # Ensure PyInstaller is installed
    try:
        subprocess.run(
            [python, "-m", "PyInstaller", "--version"],
            capture_output=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise RuntimeError(
            "Install locked build dependencies with: uv sync --extra build --locked"
        ) from exc

    # Clean previous build (only PyInstaller's own output, not build-resources)
    for d in [
        PROJECT_ROOT / "build" / "pyinstaller",
        PROJECT_ROOT / "dist" / "backend",
    ]:
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

    # Copy published_defaults.json into the backend bundle
    defaults_src = _PUBLISHED_DEFAULTS_SRC
    defaults_target = BACKEND_DIST / "published_defaults.json"
    if defaults_src.exists():
        shutil.copy2(defaults_src, defaults_target)
        print(f"    published_defaults.json 已复制: {defaults_target}")

    exe = BACKEND_DIST / ("backend.exe" if sys.platform == "win32" else "backend")
    size_mb = exe.stat().st_size / (1024 * 1024) if exe.exists() else 0
    print(f"    后端打包完成: {exe}  ({size_mb:.1f} MB)")


# ---------------------------------------------------------------------------
# Step 2 — Set up third_party/audiveris
# ---------------------------------------------------------------------------


def setup_audiveris() -> None:
    """Build a distribution with all runtime jars; never ship a Gradle project."""
    src = PROJECT_ROOT / "third_party" / "audiveris"
    java = LOCAL_JDK / "bin" / ("java.exe" if sys.platform == "win32" else "java")
    if not java.is_file():
        raise RuntimeError(
            f"SCORE_TRANS_JAVA_HOME / JAVA_HOME must point to JDK 25: {java}"
        )
    version = subprocess.run(
        [str(java), "-version"], capture_output=True, text=True, check=True
    )
    if not re.search(r'version "25[.\"]', version.stderr + version.stdout):
        raise RuntimeError(f"Expected JDK 25 at {LOCAL_JDK}: {version.stderr}")
    wrapper = src / ("gradlew.bat" if sys.platform == "win32" else "gradlew")
    if sys.platform != "win32":
        wrapper.chmod(wrapper.stat().st_mode | 0o111)
    env = {**os.environ, "JAVA_HOME": str(LOCAL_JDK)}
    subprocess.run(
        [str(wrapper), "clean", ":app:installDist", "--no-daemon", "--console=plain"],
        cwd=src,
        env=env,
        check=True,
    )
    distribution = src / "app" / "build" / "install" / "app"
    if not (distribution / "lib" / "audiveris.jar").is_file():
        raise RuntimeError(f"Audiveris distribution missing: {distribution}")
    if AUVERERIS_DIR.exists():
        shutil.rmtree(AUVERERIS_DIR)
    shutil.copytree(distribution, AUVERERIS_DIR)
    for notice in ("LICENSE", "LICENSE.txt", "NOTICE", "NOTICE.md"):
        if (src / notice).is_file():
            shutil.copy2(src / notice, AUVERERIS_DIR / notice)
    _assert_no_tesseract_artifacts(AUVERERIS_DIR)


def _tesseract_artifacts(audiveris_dir: Path) -> list[Path]:
    """Return paths that would ship Tesseract or its OCR data."""
    if not audiveris_dir.exists():
        return []
    artifacts: list[Path] = []
    for path in audiveris_dir.rglob("*"):
        name = path.name.casefold()
        if (
            "tesseract" in name
            or "leptonica" in name
            or name == "tessdata"
            or name.endswith(".traineddata")
        ):
            artifacts.append(path)
    return artifacts


def _assert_no_tesseract_artifacts(audiveris_dir: Path) -> None:
    artifacts = _tesseract_artifacts(audiveris_dir)
    if artifacts:
        rendered = ", ".join(str(path) for path in artifacts[:5])
        suffix = " ..." if len(artifacts) > 5 else ""
        raise RuntimeError(
            f"Audiveris package contains Tesseract artifacts: {rendered}{suffix}"
        )


def download_jre() -> None:
    """Bundle the same JDK used to compile Audiveris; fail on missing input."""
    java = LOCAL_JDK / "bin" / ("java.exe" if sys.platform == "win32" else "java")
    if not java.is_file():
        raise RuntimeError(f"Set SCORE_TRANS_JAVA_HOME or JAVA_HOME to JDK 25: {java}")
    if JRE_DIR.exists():
        shutil.rmtree(JRE_DIR)
    shutil.copytree(LOCAL_JDK, JRE_DIR / "jdk", symlinks=False)


# ---------------------------------------------------------------------------
# Pre-packaging cleanup & JDK trim
# ---------------------------------------------------------------------------


def _trim_jdk(jdk_dir: Path) -> None:
    """Strip JDK files Audiveris does not need at runtime.

    Audiveris only needs ``bin/java.exe`` (+ ``javaw.exe``) and ``lib/modules``
    (the runtime image). We drop ``jmods/`` (only for jlink), ``lib/src.zip`` +
    ``lib/ct.sym`` (javac/compilation), ``include/`` (C headers), and the dev
    tools in ``bin/``. ``legal/`` is kept (license notices); ``*.dll`` and
    ``bin/server/`` are kept (java.exe runtime deps). Cuts the bundled JDK by
    ~200 MB.
    """
    jdk = Path(jdk_dir)
    if not (jdk / "bin").is_dir():
        return
    removed = 0.0

    def _rm_dir(d: Path) -> None:
        nonlocal removed
        if d.is_dir():
            size = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
            shutil.rmtree(d)
            removed += size / (1024 * 1024)

    def _rm_file(f: Path) -> None:
        nonlocal removed
        if f.is_file():
            size = f.stat().st_size
            f.unlink(missing_ok=True)
            removed += size / (1024 * 1024)

    _rm_dir(jdk / "jmods")
    _rm_file(jdk / "lib" / "src.zip")
    _rm_file(jdk / "lib" / "ct.sym")
    _rm_dir(jdk / "include")
    keep = {"java.exe", "javaw.exe"}
    for exe in (jdk / "bin").glob("*.exe"):
        if exe.name.lower() not in keep:
            _rm_file(exe)
    if removed > 0:
        print(
            f"    JDK 裁剪(jmods/src.zip/ct.sym/include + bin 开发工具): -{removed:.0f} MB"
        )


def _purge_trash_leftovers() -> None:
    """Remove ``.trash-*/hs_err_pid*/replay_pid*`` the safe-rmtree shim stashes
    inside ``build-resources/``, so electron-builder does not bundle them."""
    if not BUILD_RESOURCES.exists():
        return
    targets = [
        entry
        for entry in BUILD_RESOURCES.rglob("*")
        if ".trash-" in entry.name
        or entry.name.startswith(("hs_err_pid", "replay_pid"))
    ]
    targets.sort(key=lambda e: len(e.parts), reverse=True)
    removed = 0
    for t in targets:
        if t.is_symlink():
            continue
        if t.is_dir():
            shutil.rmtree(t)
        else:
            t.unlink(missing_ok=True)
        removed += 1
    print(f"    清理 .trash/崩溃日志残留: {removed} 项")


def _finalize_third_party() -> None:
    """Trim runtime-irrelevant JDK files and purge safe-rmtree trash before
    electron-builder bundles ``build-resources/`` into the installer."""
    print("\n" + "-" * 60)
    print("[•] 打包前清理与裁剪 ...")
    print("-" * 60)
    _trim_jdk(JRE_DIR / "jdk")
    _purge_trash_leftovers()
    old_gradle = THIRD_PARTY / "gradle_home"
    if old_gradle.exists():
        shutil.rmtree(old_gradle)


# ---------------------------------------------------------------------------
# Step 4 — Build Electron frontend
# ---------------------------------------------------------------------------


def build_electron_frontend() -> None:
    print("\n" + "=" * 60)
    print("[4/5] 构建 Electron 前端 ...")
    print("=" * 60)

    desktop = PROJECT_ROOT / "desktop"
    pnpm = _find_pnpm()
    run([pnpm, "install", "--frozen-lockfile"], cwd=desktop)
    run([pnpm, "build"], cwd=desktop)
    print("    Electron 前端构建完成")


def _find_pnpm() -> str:
    found = shutil.which("pnpm")
    if not found:
        raise RuntimeError(
            "Install the pnpm version specified in desktop/package.json and add it to PATH"
        )
    return found


# ---------------------------------------------------------------------------
# Step 5 — Package with electron-builder
# ---------------------------------------------------------------------------


def package_electron() -> None:
    print("\n" + "=" * 60)
    print("[5/5] 打包 Electron 应用 (electron-builder) ...")
    print("=" * 60)

    desktop = PROJECT_ROOT / "desktop"
    pnpm = _find_pnpm()
    run(
        [
            pnpm,
            "electron-builder",
            "build",
            "--mac" if sys.platform == "darwin" else "--win",
            "--config",
            "--publish",
            "never",
        ],
        cwd=desktop,
    )

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
    parser.add_argument(
        "--skip-backend", action="store_true", help="跳过 PyInstaller 后端构建"
    )
    parser.add_argument(
        "--skip-jre", action="store_true", help="跳过 JRE 复制，复用已有资源"
    )
    parser.add_argument(
        "--skip-electron", action="store_true", help="跳过 Electron 构建和打包"
    )
    parser.add_argument(
        "--skip-audiveris",
        action="store_true",
        help="跳过 Audiveris 配置（使用 build-resources 中已有的 audiveris）",
    )
    args = parser.parse_args()
    from tools.release import validate

    validate()

    print("╔══════════════════════════════════════════╗")
    print("║     Score Trans 应用打包工具              ║")
    print("╚══════════════════════════════════════════╝")
    print(f"项目根目录: {PROJECT_ROOT}")

    if not args.skip_backend:
        build_backend()
    else:
        print("\n[1/5] 跳过后端构建")

    if not args.skip_audiveris:
        setup_audiveris()
    else:
        print("\n[2/5] 跳过 Audiveris 配置")

    if not args.skip_jre:
        download_jre()
    else:
        print("\n[3/5] 跳过 JRE 配置")

    _finalize_third_party()
    if not args.skip_electron:
        build_electron_frontend()
        package_electron()
        from tools.smoke_package import smoke

        resources = PROJECT_ROOT / "desktop" / "dist-electron"
        resources = (
            resources / "mac-arm64" / "Score Trans.app" / "Contents" / "Resources"
            if sys.platform == "darwin"
            else resources / "win-unpacked" / "resources"
        )
        smoke(resources)
    else:
        print("\n[4-5/5] 跳过 Electron 构建")

    print("\n" + "=" * 60)
    print("打包流程全部完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
