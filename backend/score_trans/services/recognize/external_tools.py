from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from ...models.common.errors import ExternalToolError
from ...models.common.paths import PROJECT_ROOT
from ...models.settings.config import ToolConfig


@dataclass(slots=True)
class CommandResult:
    args: list[str]
    stdout: str
    stderr: str


def _run(
    args: list[str], cwd: Path | None = None, env: dict[str, str] | None = None
) -> CommandResult:
    try:
        completed = subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
    except FileNotFoundError as exc:
        raise ExternalToolError(f"找不到外部程序：{args[0]}") from exc
    except PermissionError as exc:
        raise ExternalToolError(
            f"无法执行外部程序（权限被拒绝或路径无效）：{args[0]}\n"
            f"请检查设置中的路径是否正确。"
        ) from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr or ""
        stdout = exc.stdout or ""
        raise ExternalToolError(
            f"外部程序执行失败：{' '.join(args)}\n\nSTDOUT:\n{stdout}\n\nSTDERR:\n{stderr}"
        ) from exc
    return CommandResult(args=args, stdout=completed.stdout, stderr=completed.stderr)


def recognize_with_audiveris(
    input_file: Path, output_dir: Path, config: ToolConfig
) -> Path:
    input_file = input_file.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    audiveris_path = Path(config.audiveris_path)
    env = _java_env(config)
    audiveris_args = _audiveris_args(input_file, output_dir, config)
    if audiveris_path.name.lower() in {"gradlew", "gradlew.bat"}:
        args = [
            str(audiveris_path),
            ":app:run",
            f"-PcmdLineArgs={','.join(audiveris_args)}",
            f"-PaudiverisMaxHeap={_validated_max_heap(config)}",
        ]
        _run(args, cwd=audiveris_path.parent, env=env)
    else:
        args = [config.audiveris_path or "audiveris", *audiveris_args]
        _run(args, env=env)

    candidates = (
        sorted(output_dir.rglob("*.musicxml"))
        + sorted(output_dir.rglob("*.mxl"))
        + sorted(output_dir.rglob("*.xml"))
    )
    if not candidates:
        raise ExternalToolError("Audiveris 已执行，但没有找到 MusicXML 输出文件。")
    return candidates[0]


def _audiveris_args(
    input_file: Path, output_dir: Path, config: ToolConfig
) -> list[str]:
    args = ["-batch"]
    if config.audiveris_step.strip():
        args.extend(["-step", config.audiveris_step.strip()])
    if config.audiveris_force:
        args.append("-force")
    if config.audiveris_save:
        args.append("-save")
    if config.audiveris_swap:
        args.append("-swap")
    if config.audiveris_transcribe:
        args.append("-transcribe")
    if config.audiveris_sheets.strip():
        args.extend(["-sheets", config.audiveris_sheets.strip()])
    for constant in _split_audiveris_constants(config.audiveris_constants):
        args.extend(["-constant", constant])
    args.extend(_split_extra_args(config.audiveris_extra_args))
    args.extend(["-export", "-output", str(output_dir), str(input_file)])
    return args


def _split_audiveris_constants(raw: str) -> list[str]:
    return [item.strip() for item in raw.replace("\n", ";").split(";") if item.strip()]


def _split_extra_args(raw: str) -> list[str]:
    if not raw.strip():
        return []
    try:
        return shlex.split(raw)
    except ValueError as exc:
        raise ExternalToolError(
            "SCORE_TRANS_AUDIVERIS_EXTRA_ARGS 格式错误，请检查引号是否成对。"
        ) from exc


_VALID_HEAPS = {"1g", "2g", "3g", "4g"}


def _validated_max_heap(config: ToolConfig) -> str:
    heap = config.audiveris_max_heap.strip().lower()
    if heap not in _VALID_HEAPS:
        raise ExternalToolError(
            f"SCORE_TRANS_AUDIVERIS_MAX_HEAP 值无效：{config.audiveris_max_heap!r}。"
            f"可选值：{', '.join(sorted(_VALID_HEAPS))}。"
        )
    return heap


def _java_env(config: ToolConfig) -> dict[str, str] | None:
    if not config.java_home:
        return None
    java_home = Path(config.java_home)
    java_exe = java_home / "bin" / "java.exe"
    if not java_exe.exists():
        raise ExternalToolError(f"配置的 Java 路径无效：{java_home}")
    env = os.environ.copy()
    env["JAVA_HOME"] = str(java_home)
    env["PATH"] = str(java_home / "bin") + os.pathsep + env.get("PATH", "")
    # 使用捆绑的 Gradle 缓存（打包时由 build-app.py 预填充）
    bundled_gradle_home = PROJECT_ROOT / "third_party" / "gradle_home"
    if bundled_gradle_home.exists():
        env["GRADLE_USER_HOME"] = str(bundled_gradle_home)
    _apply_java_proxy_options(env)
    return env


def _apply_java_proxy_options(env: dict[str, str]) -> None:
    proxy_url = (
        env.get("https_proxy")
        or env.get("HTTPS_PROXY")
        or env.get("http_proxy")
        or env.get("HTTP_PROXY")
    )
    if not proxy_url:
        return

    parsed = urlparse(proxy_url if "://" in proxy_url else f"http://{proxy_url}")
    if not parsed.hostname or not parsed.port:
        return

    proxy_options = (
        f"-Dhttp.proxyHost={parsed.hostname} -Dhttp.proxyPort={parsed.port} "
        f"-Dhttps.proxyHost={parsed.hostname} -Dhttps.proxyPort={parsed.port}"
    )
    current = env.get("JAVA_TOOL_OPTIONS", "")
    if "-Dhttp.proxyHost" not in current and "-Dhttps.proxyHost" not in current:
        env["JAVA_TOOL_OPTIONS"] = f"{current} {proxy_options}".strip()
