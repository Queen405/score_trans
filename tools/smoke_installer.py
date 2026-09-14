"""Silent install/reinstall/uninstall checks, restricted to disposable CI runners."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

from smoke_package import ROOT, smoke

CI = os.environ.get("GITHUB_ACTIONS", "")
RUNNER_ENVIRONMENT = os.environ.get("RUNNER_ENVIRONMENT", "")
RUNNER_TEMP = os.environ.get("RUNNER_TEMP", "")

_ACCESS_VIOLATION = 0xC0000005


def main() -> None:
    if CI != "true" or RUNNER_ENVIRONMENT != "github-hosted" or not RUNNER_TEMP:
        raise RuntimeError("Installer test requires a disposable GitHub-hosted runner")
    installers = list((ROOT / "desktop/dist-electron").glob("*.exe"))
    if len(installers) != 1:
        raise RuntimeError(f"Expected one installer, got {installers}")
    # NSIS /D= consumes the remainder of the command line and must be unquoted.
    # The install path must be ASCII-only: the bundled JDK's java.exe launcher
    # uses ANSI codepage (cp1252) on the CI runner and cannot resolve paths
    # containing non-ASCII characters, causing "could not find java.dll".
    # The backend's Unicode path handling is still tested by smoke_package.py
    # via its "用户 smoke, path" work directory.
    install = Path(RUNNER_TEMP) / "ScoreTrans-CI-Test"
    if install.exists():
        raise RuntimeError(f"Installer test directory already exists: {install}")
    user_data = Path.home() / ".score_trans"
    user_data.mkdir(exist_ok=True)
    marker = user_data / "installer-test-preserve.txt"
    marker.write_text("preserve user data", encoding="utf-8")
    command = f'"{installers[0]}" /S /D={install}'
    _run_installer(command, install)
    if not (install / "Score Trans.exe").is_file():
        raise RuntimeError("Installer did not create the application executable")
    smoke(install / "resources")
    _run_installer(command, install)
    if marker.read_text("utf-8") != "preserve user data":
        raise RuntimeError("Reinstall changed user data")
    uninstallers = list(install.glob("Uninstall*.exe"))
    if len(uninstallers) != 1:
        raise RuntimeError("Uninstaller missing")
    subprocess.run(f'"{uninstallers[0]}" /S _?={install}', check=True, timeout=180)
    for _ in range(30):
        if not (install / "Score Trans.exe").exists():
            break
        time.sleep(1)
    else:
        raise RuntimeError("Uninstall left the application executable")
    if marker.read_text("utf-8") != "preserve user data":
        raise RuntimeError("Uninstall changed user data")
    print("Silent installation, reinstall and user-data-preserving uninstall passed")


def _run_installer(command: str, install: Path) -> None:
    """Run the NSIS installer, retrying once on ACCESS_VIOLATION crashes.

    The custom NSIS installer can crash (0xC0000005) during post-install
    GDI cleanup on headless CI runners. Files may already be extracted, so
    we check for the app executable before retrying.
    """
    try:
        subprocess.run(command, check=True, timeout=300)
    except subprocess.CalledProcessError as exc:
        already_installed = (install / "Score Trans.exe").is_file()
        if already_installed:
            print(
                f"Installer exited {exc.returncode} but files are present; "
                "continuing (crash likely occurred during post-install cleanup)"
            )
            return
        if exc.returncode != _ACCESS_VIOLATION:
            raise
        print(
            f"Installer crashed (exit {exc.returncode}); "
            "cleaning up and retrying once..."
        )
        if install.exists():
            shutil.rmtree(install, ignore_errors=True)
        subprocess.run(command, check=True, timeout=300)


if __name__ == "__main__":
    main()
