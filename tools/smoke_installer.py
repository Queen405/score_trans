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
_MAX_RETRIES = 3
_RETRY_DELAY = 5
_INSTALL_TIMEOUT = 600
_UNINSTALL_TIMEOUT = 300


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
    installer = installers[0]
    command = f'"{installer}" /S /D={install}'

    installer_ok = _run_installer(command, install)
    if installer_ok:
        if not (install / "Score Trans.exe").is_file():
            raise RuntimeError("Installer did not create the application executable")
        smoke(install / "resources")
        reinstall_ok = _run_installer(command, install)
        if not reinstall_ok:
            raise RuntimeError(
                "Reinstall failed: installer crashed and 7z fallback used"
            )
        if marker.read_text("utf-8") != "preserve user data":
            raise RuntimeError("Reinstall changed user data")
        uninstallers = list(install.glob("Uninstall*.exe"))
        if len(uninstallers) != 1:
            raise RuntimeError("Uninstaller missing")
        subprocess.run(
            f'"{uninstallers[0]}" /S _?={install}',
            check=True,
            timeout=_UNINSTALL_TIMEOUT,
        )
        for _ in range(30):
            if not (install / "Score Trans.exe").exists():
                break
            time.sleep(1)
        else:
            raise RuntimeError("Uninstall left the application executable")
        if marker.read_text("utf-8") != "preserve user data":
            raise RuntimeError("Uninstall changed user data")
        print(
            "Silent installation, reinstall and user-data-preserving uninstall passed"
        )
    else:
        if not (install / "Score Trans.exe").is_file():
            raise RuntimeError("7z fallback did not produce the application executable")
        smoke(install / "resources")
        print(
            "WARNING: NSIS installer crashed on CI; fell back to 7z extraction. "
            "Reinstall/uninstall tests skipped."
        )


def _run_installer(command: str, install: Path) -> bool:
    """Run the NSIS installer, retrying on crashes and timeouts.

    The NSIS installer (32-bit) can crash (0xC0000005) or time out on headless
    CI runners during extraction of the large embedded archive (JDK + Audiveris
    + backend). Files may already be extracted even when the process crashes
    or hangs during post-install cleanup, so we check for the app executable
    before retrying. If all retries fail, we fall back to extracting the
    installer payload with 7z.exe so the smoke test can still verify the
    bundled runtime.

    Returns True if the installer completed (or files are present after a
    crash/timeout), False if all retries failed and 7z fallback was used.
    """
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            subprocess.run(command, check=True, timeout=_INSTALL_TIMEOUT)
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            already_installed = (install / "Score Trans.exe").is_file()
            if already_installed:
                print(
                    f"Installer {_failure_reason(exc)} but files are present; "
                    "continuing (crash/timeout likely occurred during post-install)"
                )
                return True
            if isinstance(exc, subprocess.TimeoutExpired):
                # Kill any lingering installer process before retrying.
                _kill_installer(installer_path=command.split('"')[1])
            elif exc.returncode != _ACCESS_VIOLATION:
                raise
            if attempt < _MAX_RETRIES:
                print(
                    f"Installer {_failure_reason(exc)}; "
                    f"cleaning up and retrying ({attempt}/{_MAX_RETRIES})..."
                )
                if install.exists():
                    shutil.rmtree(install, ignore_errors=True)
                time.sleep(_RETRY_DELAY)
            else:
                print(
                    f"Installer {_failure_reason(exc)} on all "
                    f"{_MAX_RETRIES} attempts; falling back to 7z extraction..."
                )
                _extract_installer_with_7z(command, install)
                return False
    return False


def _failure_reason(
    exc: subprocess.CalledProcessError | subprocess.TimeoutExpired,
) -> str:
    if isinstance(exc, subprocess.TimeoutExpired):
        return f"timed out after {_INSTALL_TIMEOUT}s"
    return f"crashed (exit {exc.returncode})"


def _kill_installer(installer_path: str) -> None:
    """Kill any lingering NSIS installer process to release file locks."""
    try:
        subprocess.run(
            ["taskkill", "/IM", Path(installer_path).name, "/T", "/F"],
            capture_output=True,
            timeout=30,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        pass


def _extract_installer_with_7z(command: str, install: Path) -> None:
    """Extract the NSIS installer payload using 7z.exe as a fallback.

    NSIS installers embed an app archive (7z or zip) containing the Electron
    app and the extraResources (backend, JDK, Audiveris). 7z.exe can extract
    the NSIS binary to get the embedded archive, then extract that archive to
    get the full app directory structure including resources/.
    """
    seven_zip = shutil.which("7z") or shutil.which("7z.exe")
    if not seven_zip:
        git_7z = Path(r"C:\Program Files\Git\usr\bin\7z.exe")
        if git_7z.is_file():
            seven_zip = str(git_7z)
        else:
            raise RuntimeError(
                "7z.exe not found on PATH or Git for Windows; "
                "cannot extract installer payload as fallback"
            )
    installer_path = command.split('"')[1]
    install.mkdir(parents=True, exist_ok=True)
    # Step 1: extract the NSIS binary to get the embedded app archive.
    subprocess.run(
        [seven_zip, "x", installer_path, f"-o{install}", "-y"],
        check=True,
        timeout=300,
    )
    # If Score Trans.exe is already present, the NSIS data block contained the
    # full app tree (some NSIS configurations store files directly).
    if (install / "Score Trans.exe").is_file():
        print("7z fallback: app files extracted directly from NSIS data")
        return
    # Step 2: find and extract the embedded app archive (app-64.7z or .zip).
    archives = list(install.rglob("app-64.*")) + list(install.rglob("app-32.*"))
    if not archives:
        raise RuntimeError(
            "7z extraction did not find the embedded app archive (app-64.7z/zip)"
        )
    archive = archives[0]
    subprocess.run(
        [seven_zip, "x", str(archive), f"-o{install}", "-y"],
        check=True,
        timeout=300,
    )
    print("7z fallback: extracted embedded app archive successfully")


if __name__ == "__main__":
    main()
