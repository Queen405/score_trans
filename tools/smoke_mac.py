"""Mount the shipped DMG and test a copied application, preserving bundle metadata."""

from __future__ import annotations

import os
import plistlib
import subprocess
import tempfile
from pathlib import Path

from smoke_installer import desktop_smoke
from smoke_package import ROOT, smoke

CI = os.environ.get("GITHUB_ACTIONS", "")
RUNNER_ENVIRONMENT = os.environ.get("RUNNER_ENVIRONMENT", "")


def main() -> None:
    if CI != "true" or RUNNER_ENVIRONMENT != "github-hosted":
        raise RuntimeError("DMG test requires a disposable GitHub-hosted runner")
    images = list((ROOT / "desktop/dist-electron").glob("*.dmg"))
    if len(images) != 1:
        raise RuntimeError("Expected exactly one DMG")
    with tempfile.TemporaryDirectory(prefix="score-trans-dmg-") as temporary:
        mount = Path(temporary) / "mount"
        attached = subprocess.run(
            [
                "hdiutil",
                "attach",
                str(images[0]),
                "-readonly",
                "-nobrowse",
                "-plist",
                "-mountpoint",
                str(mount),
            ],
            capture_output=True,
            check=True,
            timeout=120,
        )
        try:
            plistlib.loads(attached.stdout)
            applications = list(mount.glob("*.app"))
            if len(applications) != 1:
                raise RuntimeError("Expected exactly one application in DMG")
            target = Path(temporary) / "Installed App" / "Score Trans.app"
            target.parent.mkdir()
            subprocess.run(
                ["ditto", str(applications[0]), str(target)], check=True, timeout=180
            )
            smoke(target / "Contents/Resources")
            desktop_smoke(target / "Contents/MacOS/Score Trans", "dmg-installed")
        finally:
            subprocess.run(["hdiutil", "detach", str(mount)], check=True, timeout=60)


if __name__ == "__main__":
    main()
