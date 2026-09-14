"""Strict installer lifecycle checks, restricted to disposable CI runners."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from smoke_package import ROOT, smoke

CI = os.environ.get("GITHUB_ACTIONS", "")
RUNNER_ENVIRONMENT = os.environ.get("RUNNER_ENVIRONMENT", "")
RUNNER_TEMP = os.environ.get("RUNNER_TEMP", "")
_INSTALL_TIMEOUT = 600
_UNINSTALL_TIMEOUT = 300
_REPORTS = ROOT / "desktop/smoke-reports"
_SAMPLE_INTERVAL = 30
_DIAGNOSTIC_TIMEOUT = 10


def _record(phase: str, event: str, **details: object) -> None:
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": phase,
        "event": event,
        **details,
    }
    # ASCII on stdout works with Windows CI code pages; artifacts retain Unicode.
    print(json.dumps(record), flush=True)
    try:
        _REPORTS.mkdir(parents=True, exist_ok=True)
        with (_REPORTS / f"{phase}.jsonl").open("a", encoding="utf-8") as stream:
            print(json.dumps(record, ensure_ascii=False), file=stream)
    except OSError as error:
        print(f"Cannot write installer diagnostics: {error}", flush=True)


def _terminate_tree(child: subprocess.Popen, phase: str, timeout: int = 30) -> None:
    try:
        if sys.platform == "win32":
            result = subprocess.run(
                ["taskkill", "/PID", str(child.pid), "/T", "/F"],
                capture_output=True,
                timeout=timeout,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if result.returncode:
                _record(
                    phase, "cleanup-error", pid=child.pid, returncode=result.returncode
                )
        else:
            child.kill()
    except Exception as error:
        _record(phase, "cleanup-error", pid=child.pid, error=str(error))
    try:
        child.wait(timeout=timeout)
    except Exception as error:
        _record(phase, "cleanup-error", pid=child.pid, error=str(error))


def _collect_diagnostics(
    pid: int,
    install: Path,
    phase: str,
    *,
    windows: bool,
    timeout: float = _DIAGNOSTIC_TIMEOUT,
) -> None:
    command = [
        sys.executable,
        str(ROOT / "tools/installer_diagnostics.py"),
        "--pid",
        str(pid),
        "--install",
        str(install),
    ]
    if windows:
        command.append("--windows")
    try:
        # A venv Python launcher may spawn another Python process on Windows.
        # File output avoids waiting forever for inherited pipes after a timeout.
        with tempfile.TemporaryFile() as output:
            child = subprocess.Popen(
                command,
                stdout=output,
                stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            try:
                code = child.wait(timeout=timeout)
            except Exception as error:
                _terminate_tree(child, phase, timeout=5)
                output.seek(0)
                _record(
                    phase,
                    "diagnostic-error",
                    pid=pid,
                    error=str(error),
                    output=output.read(1_000_000).decode("utf-8", errors="replace"),
                )
            else:
                output.seek(0)
                _record(
                    phase,
                    "snapshot",
                    pid=pid,
                    returncode=code,
                    output=output.read(1_000_000).decode("utf-8", errors="replace"),
                )
    except Exception as error:
        _record(phase, "diagnostic-error", pid=pid, error=str(error))


def run_bounded(
    command: str | list[str],
    timeout: int,
    *,
    install: Path | None = None,
    phase: str = "install",
) -> None:
    """Observe installation without extending its deadline or hiding failures."""
    started = time.monotonic()
    child = subprocess.Popen(command)
    _record(phase, "started", pid=child.pid, timeout_seconds=timeout)
    deadline = started + timeout
    next_sample = started + _SAMPLE_INTERVAL
    try:
        while True:
            now = time.monotonic()
            remaining = deadline - now
            if remaining <= 0:
                raise subprocess.TimeoutExpired(command, timeout)
            wait = (
                min(remaining, max(0.01, next_sample - now)) if install else remaining
            )
            try:
                code = child.wait(timeout=wait)
                break
            except subprocess.TimeoutExpired:
                if not install or time.monotonic() >= deadline:
                    raise subprocess.TimeoutExpired(command, timeout) from None
                _record(
                    phase,
                    "progress",
                    pid=child.pid,
                    elapsed_seconds=round(time.monotonic() - started, 2),
                )
                _collect_diagnostics(
                    child.pid,
                    install,
                    phase,
                    windows=False,
                    timeout=min(
                        _DIAGNOSTIC_TIMEOUT, max(0.01, deadline - time.monotonic())
                    ),
                )
                next_sample += _SAMPLE_INTERVAL
    except subprocess.TimeoutExpired:
        _record(
            phase,
            "timeout",
            pid=child.pid,
            elapsed_seconds=round(time.monotonic() - started, 2),
        )
        if install:
            _collect_diagnostics(child.pid, install, phase, windows=True)
        _terminate_tree(child, phase)
        raise
    _record(
        phase,
        "exited",
        pid=child.pid,
        returncode=code,
        elapsed_seconds=round(time.monotonic() - started, 2),
    )
    if code:
        if install:
            _collect_diagnostics(child.pid, install, phase, windows=True)
        raise subprocess.CalledProcessError(code, command)


def _run_installer(command: str, install: Path, phase: str = "install") -> None:
    # Existing files prove nothing about this invocation, particularly on reinstall.
    run_bounded(command, _INSTALL_TIMEOUT, install=install, phase=phase)
    if not (install / "Score Trans.exe").is_file():
        raise RuntimeError("Installer did not create the application executable")


def desktop_smoke(executable: Path, phase: str) -> None:
    subprocess.run(
        [
            "node",
            str(ROOT / "desktop/scripts/smoke-desktop.mjs"),
            "--executable",
            str(executable),
            "--phase",
            phase,
        ],
        cwd=ROOT / "desktop",
        check=True,
        timeout=130,
    )


def main() -> None:
    if CI != "true" or RUNNER_ENVIRONMENT != "github-hosted" or not RUNNER_TEMP:
        raise RuntimeError("Installer test requires a disposable GitHub-hosted runner")
    installers = list((ROOT / "desktop/dist-electron").glob("*.exe"))
    if len(installers) != 1:
        raise RuntimeError(f"Expected one installer, got {installers}")
    # NSIS /D consumes the unquoted remainder. Keep the JDK launch path ASCII.
    install = Path(RUNNER_TEMP) / "ScoreTrans-CI-Test"
    if install.exists():
        raise RuntimeError(f"Installer test directory already exists: {install}")
    user_data = Path.home() / ".score_trans"
    user_data.mkdir(exist_ok=True)
    marker = user_data / "installer-test-preserve.txt"
    marker.write_text("preserve user data", encoding="utf-8")
    command = f'"{installers[0]}" /S /D={install}'
    _run_installer(command, install)
    smoke(install / "resources")
    desktop_smoke(install / "Score Trans.exe", "installed")
    _run_installer(command, install, "reinstall")
    desktop_smoke(install / "Score Trans.exe", "reinstalled")
    if marker.read_text("utf-8") != "preserve user data":
        raise RuntimeError("Reinstall changed user data")
    uninstallers = list(install.glob("Uninstall*.exe"))
    if len(uninstallers) != 1:
        raise RuntimeError("Uninstaller missing")
    run_bounded(
        f'"{uninstallers[0]}" /S _?={install}',
        _UNINSTALL_TIMEOUT,
        install=install,
        phase="uninstall",
    )
    for _ in range(30):
        if not (install / "Score Trans.exe").exists():
            break
        time.sleep(1)
    else:
        raise RuntimeError("Uninstall left the application executable")
    if marker.read_text("utf-8") != "preserve user data":
        raise RuntimeError("Uninstall changed user data")
    print("Installation, desktop startup, reinstall and preserving uninstall passed")


if __name__ == "__main__":
    main()
