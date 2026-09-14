"""Validate release inputs and publish only a complete set of installers."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = os.environ.get("GITHUB_REF", "")
REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "Queen405/score_trans")
COS_BUCKET = os.environ.get("COS_BUCKET", "score-trans-1320022301")
COS_REGION = os.environ.get("COS_REGION", "ap-beijing")


def _installer_url(version: str) -> str:
    """Build the Tencent COS direct-download URL for the Windows installer."""
    return (
        f"https://{COS_BUCKET}.cos.{COS_REGION}.myqcloud.com"
        f"/download/Score%20Trans%20Setup%20{version}.exe"
    )


def _installer_url_mac(version: str) -> str:
    """Build the Tencent COS direct-download URL for the macOS installer."""
    return (
        f"https://{COS_BUCKET}.cos.{COS_REGION}.myqcloud.com"
        f"/download/Score%20Trans-{version}-arm64.dmg"
    )


def validate(root: Path = ROOT, ref: str = REF) -> dict:
    package = json.loads((root / "desktop/package.json").read_text("utf-8"))
    manifest = json.loads((root / "desktop/latest.json").read_text("utf-8"))
    version = package["version"]
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Release version must be x.y.z")
    if manifest["version"] != version:
        raise ValueError("package.json and latest.json versions differ")
    if ref.startswith("refs/tags/") and ref != f"refs/tags/v{version}":
        raise ValueError(f"Tag must be v{version}; got {ref}")
    return {
        **manifest,
        "url": _installer_url(version),
        "urlMac": _installer_url_mac(version),
    }


def prepare_assets(directory: Path, manifest: dict) -> list[Path]:
    version = manifest["version"]
    names = [
        f"Score Trans Setup {version}.exe",
        f"Score Trans-{version}-arm64.dmg",
    ]
    installers = [directory / name for name in names]
    for asset in installers:
        if not asset.is_file() or asset.stat().st_size == 0:
            raise ValueError(f"Missing or empty installer: {asset}")
    actual = {
        p.name for p in directory.iterdir() if p.suffix in {".exe", ".dmg"}
    }
    if actual != set(names):
        raise ValueError(f"Unexpected installer set: {actual}")
    manifest_path = directory / "latest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    assets = [*installers, manifest_path]
    checksums = directory / "SHA256SUMS.txt"
    lines = []
    for asset in assets:
        with asset.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        lines.append(f"{digest}  {asset.name}\n")
    checksums.write_text("".join(lines), encoding="utf-8")
    return [*assets, checksums]


def publish(directory: Path) -> None:
    if not REF.startswith("refs/tags/"):
        raise ValueError("Publishing requires a version tag")
    manifest = validate()
    assets = prepare_assets(directory, manifest)
    tag = f"v{manifest['version']}"
    query = subprocess.run(
        ["gh", "release", "view", tag, "--json", "isDraft,assets"],
        capture_output=True,
        text=True,
    )
    if query.returncode == 0:
        existing = json.loads(query.stdout)
        if not existing["isDraft"]:
            raise ValueError(
                f"{tag} is already public; refusing to replace published assets"
            )
    else:
        subprocess.run(
            [
                "gh",
                "release",
                "create",
                tag,
                "--verify-tag",
                "--draft",
                "--title",
                tag,
                "--notes",
                manifest.get("notes", ""),
            ],
            check=True,
        )
    subprocess.run(
        ["gh", "release", "upload", tag, *map(str, assets), "--clobber"], check=True
    )
    subprocess.run(
        ["gh", "release", "edit", tag, "--draft=false", "--latest"], check=True
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["validate", "publish"])
    parser.add_argument("--assets", type=Path, default=Path("release-assets"))
    args = parser.parse_args()
    if args.command == "publish":
        publish(args.assets)
    else:
        sys.stdout.buffer.write(
            json.dumps(validate(), ensure_ascii=False).encode("utf-8") + b"\n"
        )
