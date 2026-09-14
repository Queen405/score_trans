"""Publish immutable release snapshots and resume interrupted delivery."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
REF = os.environ.get("GITHUB_REF", "")
SOURCE_SHA = os.environ.get("GITHUB_SHA", "")
REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "Queen405/score_trans")
COS_BUCKET = os.environ.get("COS_BUCKET") or "score-trans-1320022301"
COS_REGION = os.environ.get("COS_REGION") or "ap-beijing"
COS_PREFIX = os.environ.get("COS_PREFIX") or "download"
GH_TOKEN = os.environ.get("GH_TOKEN", "")
SECRET_ID = os.environ.get("TENCENTCLOUD_SECRET_ID", "")
SECRET_KEY = os.environ.get("TENCENTCLOUD_SECRET_KEY", "")
CHECKSUMS = "SHA256SUMS.txt"
METADATA = "release-metadata.json"


def version_tuple(version: str) -> tuple[int, ...]:
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Release version must be x.y.z")
    return tuple(map(int, version.split(".")))


def installer_names(version: str) -> list[str]:
    version_tuple(version)
    return [f"Score Trans Setup {version}.exe", f"Score Trans-{version}-arm64.dmg"]


def installer_url(name: str) -> str:
    return (
        f"https://{COS_BUCKET}.cos.{COS_REGION}.myqcloud.com/{COS_PREFIX}/{quote(name)}"
    )


def validate(root: Path = ROOT, ref: str = REF) -> dict:
    package = json.loads((root / "desktop/package.json").read_text("utf-8"))
    manifest = json.loads((root / "desktop/latest.json").read_text("utf-8"))
    version = package["version"]
    version_tuple(version)
    if manifest["version"] != version:
        raise ValueError("package.json and latest.json versions differ")
    if ref.startswith("refs/tags/") and ref != f"refs/tags/v{version}":
        raise ValueError(f"Tag must be v{version}; got {ref}")
    windows, mac = installer_names(version)
    return {**manifest, "url": installer_url(windows), "urlMac": installer_url(mac)}


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def prepare_assets(directory: Path, manifest: dict, source_sha: str = "") -> list[Path]:
    names = installer_names(manifest["version"])
    for name in names:
        asset = directory / name
        if not asset.is_file() or asset.stat().st_size == 0:
            raise ValueError(f"Missing or empty installer: {asset}")
    actual = {p.name for p in directory.iterdir() if p.suffix in {".exe", ".dmg"}}
    if actual != set(names):
        raise ValueError(f"Unexpected installer set: {actual}")
    write_json(directory / "latest.json", manifest)
    assets = [*(directory / name for name in names), directory / "latest.json"]
    if source_sha:
        write_json(
            directory / METADATA,
            {
                "version": manifest["version"],
                "tag": f"v{manifest['version']}",
                "source_sha": source_sha,
            },
        )
        assets.append(directory / METADATA)
    (directory / CHECKSUMS).write_text(
        "".join(f"{digest(asset)}  {asset.name}\n" for asset in assets),
        encoding="utf-8",
    )
    return [*assets, directory / CHECKSUMS]


def verify_snapshot(directory: Path, tag: str, source_sha: str) -> dict:
    manifest = json.loads((directory / "latest.json").read_text("utf-8"))
    if tag != f"v{manifest['version']}":
        raise ValueError("Snapshot version does not match tag")
    names = set(installer_names(manifest["version"])) | {"latest.json"}
    metadata = directory / METADATA
    if metadata.exists():
        info = json.loads(metadata.read_text("utf-8"))
        if info != {
            "version": manifest["version"],
            "tag": tag,
            "source_sha": source_sha,
        }:
            raise ValueError("Snapshot provenance differs from current tag")
        names.add(METADATA)
    hashes: dict[str, str] = {}
    for line in (directory / CHECKSUMS).read_text("utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if not match or match[2] not in names or match[2] in hashes:
            raise ValueError("Invalid snapshot checksum entry")
        hashes[match[2]] = match[1]
    if hashes.keys() != names:
        raise ValueError("Incomplete snapshot checksums")
    for name, expected in hashes.items():
        asset = directory / name
        if not asset.is_file() or not asset.stat().st_size or digest(asset) != expected:
            raise ValueError(f"Snapshot checksum mismatch: {name}")
    windows, mac = installer_names(manifest["version"])
    if (manifest.get("url"), manifest.get("urlMac")) != (
        installer_url(windows),
        installer_url(mac),
    ):
        raise ValueError("Snapshot COS destination differs from release configuration")
    return manifest


def gh(*args: str) -> subprocess.CompletedProcess:
    for attempt in range(3):
        try:
            return subprocess.run(
                ["gh", *args],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=True,
                timeout=900,
            )
        except subprocess.CalledProcessError as exc:
            transient = re.search(
                r"HTTP (429|5\d\d)|connection reset|TLS handshake timeout|dial tcp",
                exc.stderr or "",
                re.IGNORECASE,
            )
            if not transient or attempt == 2:
                raise
            time.sleep(attempt + 1)
    raise AssertionError("Unreachable GitHub retry state")


def gh_json(endpoint: str, *, missing_ok: bool = False) -> dict | None:
    try:
        return json.loads(gh("api", endpoint).stdout)
    except subprocess.CalledProcessError as exc:
        if missing_ok and re.search(r"\bHTTP 404\b", exc.stderr or ""):
            return None
        raise


def release_info(tag: str) -> dict | None:
    return gh_json(f"repos/{REPOSITORY}/releases/tags/{quote(tag)}", missing_ok=True)


def tag_sha(tag: str) -> str:
    if not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        raise ValueError("Tag must be vX.Y.Z")
    info = gh_json(f"repos/{REPOSITORY}/commits/{quote(tag)}")
    assert info is not None
    return info["sha"]


def cos(phase: str, directory: Path | None = None) -> dict:
    args = ["node", str(ROOT / "desktop/scripts/upload-cos.mjs"), f"--phase={phase}"]
    if directory is not None:
        args += [
            f"--manifest={directory / 'latest.json'}",
            f"--checksums={directory / CHECKSUMS}",
        ]
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
            timeout=1800,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"COS {phase} failed: {(exc.stderr or '').strip()}") from exc
    return json.loads(result.stdout)


def preflight() -> None:
    for name, value in (
        ("GH_TOKEN", GH_TOKEN),
        ("TENCENTCLOUD_SECRET_ID", SECRET_ID),
        ("TENCENTCLOUD_SECRET_KEY", SECRET_KEY),
    ):
        if not value:
            raise ValueError(f"{name} must be configured for publishing")
    cos("preflight")


def download_snapshot(info: dict, directory: Path, tag: str, sha: str) -> dict:
    names = {asset["name"] for asset in info["assets"]}
    expected = set(installer_names(tag[1:])) | {"latest.json", CHECKSUMS}
    if METADATA in names:
        expected.add(METADATA)
    if names != expected:
        raise ValueError(
            "Release snapshot missing assets or contains unexpected assets"
        )
    gh("release", "download", tag, "--repo", REPOSITORY, "--dir", str(directory))
    return verify_snapshot(directory, tag, sha)


def stage(
    directory: Path, manifest: dict, tag: str, sha: str, info: dict | None
) -> None:
    assets = prepare_assets(directory, manifest, sha)
    expected = {asset.name for asset in assets}
    if info:
        if not info["draft"] or CHECKSUMS in {a["name"] for a in info["assets"]}:
            raise ValueError("Refusing to replace a completed release snapshot")
        if not {a["name"] for a in info["assets"]} <= expected:
            raise ValueError("Unexpected assets in incomplete draft")
    else:
        gh(
            "release",
            "create",
            tag,
            "--repo",
            REPOSITORY,
            "--verify-tag",
            "--draft",
            "--title",
            tag,
            "--notes",
            manifest.get("notes", ""),
        )
    # The checksums file is the completion marker and is uploaded separately LAST.
    gh(
        "release",
        "upload",
        tag,
        "--repo",
        REPOSITORY,
        *map(str, assets[:-1]),
        "--clobber",
    )
    gh("release", "upload", tag, "--repo", REPOSITORY, str(assets[-1]), "--clobber")


def finish(directory: Path, tag: str, info: dict) -> None:
    cos("artifacts", directory)
    if info["draft"]:
        gh(
            "release",
            "edit",
            tag,
            "--repo",
            REPOSITORY,
            "--draft=false",
            "--latest=false",
        )
    # Protect both pointers if a newer GitHub release already exists.
    latest = gh_json(f"repos/{REPOSITORY}/releases/latest", missing_ok=True)
    if latest and version_tuple(latest["tag_name"].removeprefix("v")) > version_tuple(
        tag[1:]
    ):
        print(f"{tag}: archived; a newer GitHub Latest already exists")
        return
    result = cos("promote", directory)
    if result["status"] != "older":
        gh("release", "edit", tag, "--repo", REPOSITORY, "--latest")
    print(f"{tag}: {result['status']}")


def publish(directory: Path) -> None:
    if not REF.startswith("refs/tags/"):
        raise ValueError("Publishing requires a version tag")
    manifest = validate()
    tag = f"v{manifest['version']}"
    preflight()
    sha = tag_sha(tag)
    if SOURCE_SHA and SOURCE_SHA != sha:
        raise ValueError("Workflow commit differs from release tag")
    info = release_info(tag)
    if info and (not info["draft"] or CHECKSUMS in {a["name"] for a in info["assets"]}):
        resume(tag)
        return
    stage(directory, manifest, tag, sha, info)
    # Read back the canonical snapshot before any COS write or publication.
    resume(tag)


def resume(tag: str) -> None:
    preflight()
    sha = tag_sha(tag)
    info = release_info(tag)
    if info is None:
        raise ValueError("No release snapshot to resume; run a normal tag build first")
    with tempfile.TemporaryDirectory(prefix="score-trans-release-") as temporary:
        directory = Path(temporary)
        download_snapshot(info, directory, tag, sha)
        finish(directory, tag, info)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["validate", "publish", "resume"])
    parser.add_argument("--assets", type=Path, default=Path("release-assets"))
    parser.add_argument("--tag")
    args = parser.parse_args()
    if args.command == "validate":
        sys.stdout.buffer.write(
            json.dumps(validate(), ensure_ascii=False).encode("utf-8") + b"\n"
        )
    elif args.command == "resume":
        if not args.tag:
            parser.error("resume requires --tag vX.Y.Z")
        resume(args.tag)
    else:
        publish(args.assets)
