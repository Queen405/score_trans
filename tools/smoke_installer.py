"""Silent install/reinstall/uninstall checks, restricted to disposable CI runners."""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from smoke_package import ROOT, smoke

CI = os.environ.get("GITHUB_ACTIONS", "")
RUNNER_ENVIRONMENT = os.environ.get("RUNNER_ENVIRONMENT", "")
RUNNER_TEMP = os.environ.get("RUNNER_TEMP", "")


def main() -> None:
    if CI != "true" or RUNNER_ENVIRONMENT != "github-hosted" or not RUNNER_TEMP:
        raise RuntimeError("Installer test requires a disposable GitHub-hosted runner")
    installers = list((ROOT / "desktop/dist-electron").glob("*.exe"))
    if len(installers) != 1:
        raise RuntimeError(f"Expected one installer, got {installers}")
    install = Path(RUNNER_TEMP) / "安装测试_ScoreTrans"
    if install.exists():
        raise RuntimeError(f"Installer test directory already exists: {install}")
    user_data = Path.home() / ".score_trans"
    user_data.mkdir(exist_ok=True)
    marker = user_data / "installer-test-preserve.txt"
    marker.write_text("preserve user data", encoding="utf-8")
    # NSIS /D= consumes the remainder of the command line and must be unquoted.
    # The install path must not contain spaces: electron-builder's multiUser.nsh
    # re-parses /D via StdUtils::GetParameter, which splits on spaces and would
    # truncate the path. Chinese characters still exercise non-ASCII path handling.
    command = f'"{installers[0]}" /S /D={install}'
    subprocess.run(command, check=True, timeout=300)
    if not (install / "Score Trans.exe").is_file():
        raise RuntimeError("Installer did not create the application executable")
    smoke(install / "resources")
    subprocess.run(command, check=True, timeout=300)
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


if __name__ == "__main__":
    main()
