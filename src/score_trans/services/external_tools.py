from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .image_preprocessing import prepare_omr_input
from .settings import ToolConfig


class ExternalToolError(RuntimeError):
    pass


@dataclass(slots=True)
class CommandResult:
    args: list[str]
    stdout: str
    stderr: str


def _run(args: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> CommandResult:
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


def recognize_with_audiveris(input_file: Path, output_dir: Path, config: ToolConfig) -> Path:
    input_file = input_file.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    omr_input = prepare_omr_input(input_file, output_dir, config)

    audiveris_path = Path(config.audiveris_path)
    env = _java_env(config)
    if audiveris_path.name.lower() in {"gradlew", "gradlew.bat"}:
        args = [
            str(audiveris_path),
            ":app:run",
            f"-PcmdLineArgs=-batch,-export,-output,{output_dir},{omr_input}",
        ]
        _run(args, cwd=audiveris_path.parent, env=env)
    else:
        args = [
            config.audiveris_path or "audiveris",
            "-batch",
            "-export",
            "-output",
            str(output_dir),
            str(omr_input),
        ]
        _run(args, env=env)

    candidates = (
        sorted(output_dir.rglob("*.musicxml"))
        + sorted(output_dir.rglob("*.mxl"))
        + sorted(output_dir.rglob("*.xml"))
    )
    if not candidates:
        raise ExternalToolError("Audiveris 已执行，但没有找到 MusicXML 输出文件。")
    return candidates[0]


def find_tool(name: str) -> str | None:
    return shutil.which(name)


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
