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
import hashlib
import json
import os
import re
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

JDK_URL = "https://api.adoptium.net/v3/binary/latest/25/ga/windows/x64/jdk/hotspot/normal/eclipse"
JDK_ZIP = BUILD_RESOURCES / "jdk.zip"

# 本地 JDK 25 路径（开发机已安装时直接复用）
LOCAL_JDK = Path(os.environ.get("SCORE_TRANS_JAVA_HOME", r"E:\ENV\JAVA\JDK25"))

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

    # Copy published_defaults.json into the backend bundle
    defaults_src = _PUBLISHED_DEFAULTS_SRC
    defaults_target = BACKEND_DIST / "published_defaults.json"
    if defaults_src.exists():
        shutil.copy2(defaults_src, defaults_target)
        print(f"    published_defaults.json 已复制: {defaults_target}")

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

    _validate_audiveris_program_id(dst)

    gradlew = dst / "gradlew.bat"
    print(f"    Audiveris 已复制: {dst}")
    print(f"    gradlew.bat 存在: {gradlew.exists()}")

    # 清理 Audiveris 无用文件以减小体积
    _cleanup_audiveris(dst)
    _assert_no_tesseract_artifacts(dst)

    # 预缓存 Gradle 发行版，避免用户环境下 SSL 证书问题导致下载失败
    _cache_gradle(dst)


def _validate_audiveris_program_id(audiveris_dir: Path) -> None:
    """Reject a stale generated ProgramId from a pre-removal Audiveris build."""
    program_id = (
        audiveris_dir
        / "app"
        / "build"
        / "generated-src"
        / "org"
        / "audiveris"
        / "omr"
        / "ProgramId.java"
    )
    if not program_id.is_file():
        raise RuntimeError(
            "Audiveris app/build/generated-src/ProgramId.java is missing. "
            "Run `./gradlew clean :app:compileJava --no-daemon` before packaging."
        )
    try:
        contents = program_id.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"无法读取 Audiveris ProgramId.java: {program_id}") from exc
    if "TESSDATA_TAG" in contents:
        raise RuntimeError(
            "Audiveris ProgramId.java still contains TESSDATA_TAG. "
            "Run `./gradlew clean :app:compileJava --no-daemon` after removing Tesseract."
        )


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


def _cleanup_audiveris(audiveris_dir: Path) -> None:
    """删除 Audiveris 中不需要的文件以减小打包体积。"""
    removed_mb = 0.0

    # 1. 删除 .gradle（含开发机绝对路径，会导致用户机器缓存失效）和 Eclipse 输出。
    #    保留 app/build：含预生成的 ProgramId.java、commit.properties 缓存和编译好的
    #    .class 文件。删除后用户机器需重新运行 generateProgramId，该任务在部分
    #    环境下会生成损坏的 ProgramId.java（只有 package 和 }，缺少 class 定义）。
    for name in ["app/bin", ".gradle"]:
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

    # 4. Remove stale OCR classes/resources/data while preserving other app/build output.
    for path in sorted(
        _tesseract_artifacts(audiveris_dir),
        key=lambda item: len(item.parts),
        reverse=True,
    ):
        if not path.exists():
            continue
        if path.is_dir():
            size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
            shutil.rmtree(path)
        else:
            size = path.stat().st_size
            path.unlink()
        removed_mb += size / (1024 * 1024)

    if removed_mb > 0:
        print(f"    清理 Audiveris 无用文件: {removed_mb:.1f} MB")


def _cache_gradle(audiveris_dir: Path) -> None:
    """将本地 Gradle 发行版复制到应用中，避免用户环境下 SSL 证书问题导致下载失败。
    保留 wrapper 的原始完整性校验配置。"""
    gradle_dist_dir = audiveris_dir / "gradle" / "wrapper"
    wrapper_props = gradle_dist_dir / "gradle-wrapper.properties"
    if not wrapper_props.exists():
        print("    [WARNING] gradle-wrapper.properties 不存在，跳过 Gradle 缓存")
        return

    props_text = wrapper_props.read_text(encoding="utf-8")
    version = None
    expected_sha256 = None
    for line in props_text.splitlines():
        if line.startswith("distributionUrl="):
            url = line.split("=", 1)[1].strip().replace("\\:", ":")
            m = re.search(r"gradle-([\d.]+)-bin\.zip", url)
            if m:
                version = m.group(1)
        elif line.startswith("distributionSha256Sum="):
            expected_sha256 = line.split("=", 1)[1].strip().lower()

    if not version:
        print("    [WARNING] 无法从 wrapper 配置提取 Gradle 版本")
        return
    if not expected_sha256:
        raise RuntimeError("Gradle wrapper 未锁定 distributionSha256Sum，拒绝复用缓存")

    print(f"    Gradle 版本: {version}")

    # 查找本地 Gradle 缓存（~/.gradle/wrapper/dists/gradle-X.Y-bin/<hash>/）
    local_gradle_cache = (
        Path.home() / ".gradle" / "wrapper" / "dists" / f"gradle-{version}-bin"
    )
    if not local_gradle_cache.exists():
        print(
            f"    [WARNING] 未找到本地 Gradle {version} 缓存，用户首次运行时需联网下载"
        )
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
        print(
            f"    [WARNING] 未找到本地 Gradle {version} 解压目录，用户首次运行时需联网下载"
        )
        return

    if not hash_dir:
        print("    [WARNING] 未找到 Gradle 缓存 hash 目录")
        return

    hash_name = hash_dir.name
    app_gradle_home = THIRD_PARTY / "gradle_home"
    cache_dir = (
        app_gradle_home / "wrapper" / "dists" / f"gradle-{version}-bin" / hash_name
    )
    zip_name = f"gradle-{version}-bin.zip"
    gradle_zip_src = hash_dir / zip_name
    if not gradle_zip_src.is_file():
        print("    [WARNING] 本地 Gradle 缓存缺少发行 ZIP，拒绝复制未校验缓存")
        return
    actual_sha256 = _sha256_file(gradle_zip_src)
    if actual_sha256 != expected_sha256:
        raise RuntimeError(
            f"Gradle 缓存 SHA-256 不匹配：期望 {expected_sha256}，实际 {actual_sha256}"
        )

    if cache_dir.exists():
        shutil.rmtree(cache_dir)
    ensure_dir(cache_dir)

    # 复制解压目录
    print(f"    本地 Gradle 解压目录: {gradle_extracted_src}")
    gradle_extracted_dst = cache_dir / f"gradle-{version}"
    if not gradle_extracted_dst.exists():
        shutil.copytree(
            gradle_extracted_src, gradle_extracted_dst, copy_function=shutil.copy2
        )
    shutil.copy2(gradle_zip_src, cache_dir / zip_name)
    print(f"    Gradle 已复制: {gradle_extracted_dst}")

    # 创建标记文件（让 wrapper 认为已下载完成）
    for suffix in [".ok", ".lck"]:
        marker = cache_dir / f"gradle-{version}-bin.zip{suffix}"
        if not marker.exists():
            marker.touch()

    print(f"    Gradle 缓存目录: {cache_dir}")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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

    print("    下载 JDK 25 ...")
    print(f"    URL: {JDK_URL}")
    ensure_dir(BUILD_RESOURCES)

    def _progress(block_num, block_size, total_size):
        downloaded = block_num * block_size
        if total_size > 0:
            pct = min(100, downloaded * 100 / total_size)
            mb = downloaded / (1024 * 1024)
            total_mb = total_size / (1024 * 1024)
            print(
                f"\r    下载进度: {pct:.0f}% ({mb:.1f}/{total_mb:.1f} MB)",
                end="",
                flush=True,
            )

    try:
        urlretrieve(JDK_URL, str(JDK_ZIP), reporthook=_progress)
    except OSError as exc:
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
    extracted_dirs = [
        d for d in extract_dir.iterdir() if d.is_dir() and d.name.startswith("jdk")
    ]
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
        os.environ["PATH"] = (
            os.pathsep.join(extra_dirs) + os.pathsep + os.environ.get("PATH", "")
        )

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
    parser.add_argument(
        "--skip-backend", action="store_true", help="跳过 PyInstaller 后端构建"
    )
    parser.add_argument("--skip-jre", action="store_true", help="跳过 JRE 下载")
    parser.add_argument(
        "--skip-electron", action="store_true", help="跳过 Electron 构建和打包"
    )
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
