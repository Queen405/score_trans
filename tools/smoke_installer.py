"""Strict installer lifecycle checks, restricted to disposable CI runners."""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from smoke_package import ROOT, smoke

CI = os.environ.get("GITHUB_ACTIONS", "")
RUNNER_ENVIRONMENT = os.environ.get("RUNNER_ENVIRONMENT", "")
RUNNER_TEMP = os.environ.get("RUNNER_TEMP", "")
_INSTALL_TIMEOUT = 600
_UNINSTALL_TIMEOUT = 300


def run_bounded(command: str | list[str], timeout: int) -> None:
    """Keep the parent alive until its process tree can be killed on timeout."""
    child = subprocess.Popen(command)
    try:
        code = child.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        subprocess.run(
            ["taskkill", "/PID", str(child.pid), "/T", "/F"],
            capture_output=True,
            timeout=30,
            check=False,
        )
        child.wait(timeout=30)
        raise
    if code:
        raise subprocess.CalledProcessError(code, command)


def _run_installer(command: str, install: Path) -> None:
    # Existing files prove nothing about this invocation, particularly on reinstall.
    run_bounded(command, _INSTALL_TIMEOUT)
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
    _run_installer(command, install)
    desktop_smoke(install / "Score Trans.exe", "reinstalled")
    if marker.read_text("utf-8") != "preserve user data":
        raise RuntimeError("Reinstall changed user data")
    uninstallers = list(install.glob("Uninstall*.exe"))
    if len(uninstallers) != 1:
        raise RuntimeError("Uninstaller missing")
    run_bounded(f'"{uninstallers[0]}" /S _?={install}', _UNINSTALL_TIMEOUT)
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
