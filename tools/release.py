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
DEFAULT_BRANCH = os.environ.get("DEFAULT_BRANCH", "")
RELEASE_JOB = os.environ.get("SCORE_TRANS_RELEASE_JOB", "")
GITHUB_ACTIONS = os.environ.get("GITHUB_ACTIONS", "")
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


def installer_assets(directory: Path, version: str) -> list[Path]:
    names = installer_names(version)
    for name in names:
        asset = directory / name
        if not asset.is_file() or asset.stat().st_size == 0:
            raise ValueError(f"Missing or empty installer: {asset}")
    actual = {p.name for p in directory.iterdir() if p.suffix in {".exe", ".dmg"}}
    if actual != set(names):
        raise ValueError(f"Unexpected installer set: {actual}")
    return [directory / name for name in names]


def prepare_assets(directory: Path, manifest: dict, source_sha: str = "") -> list[Path]:
    installers = installer_assets(directory, manifest["version"])
    write_json(directory / "latest.json", manifest)
    assets = [*installers, directory / "latest.json"]
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


def snapshot_asset_names(info: dict, tag: str) -> dict[str, str]:
    """Map GitHub's sanitized filenames back to the canonical COS snapshot."""
    expected = [*installer_names(tag[1:]), "latest.json", CHECKSUMS, METADATA]
    aliases = {
        alias: name for name in expected for alias in (name, name.replace(" ", "."))
    }
    mapping = {}
    for asset in info["assets"]:
        remote = asset["name"]
        canonical = aliases.get(remote)
        if canonical is None or canonical in mapping.values():
            raise ValueError("Unexpected or duplicate release snapshot asset")
        mapping[remote] = canonical
    return mapping


def download_snapshot(info: dict, directory: Path, tag: str, sha: str) -> dict:
    mapping = snapshot_asset_names(info, tag)
    names = set(mapping.values())
    expected = set(installer_names(tag[1:])) | {"latest.json", CHECKSUMS}
    if METADATA in names:
        expected.add(METADATA)
    if names != expected:
        raise ValueError(
            "Release snapshot missing assets or contains unexpected assets"
        )
    gh("release", "download", tag, "--repo", REPOSITORY, "--dir", str(directory))
    for remote, canonical in mapping.items():
        if remote != canonical:
            target = directory / canonical
            if target.exists():
                raise ValueError("Snapshot download filename collision")
            (directory / remote).rename(target)
    return verify_snapshot(directory, tag, sha)


def stage(
    directory: Path, manifest: dict, tag: str, sha: str, info: dict | None
) -> None:
    assets = prepare_assets(directory, manifest, sha)
    expected = {asset.name for asset in assets}
    if info:
        if not info["draft"] or CHECKSUMS in {a["name"] for a in info["assets"]}:
            raise ValueError("Refusing to replace a completed release snapshot")
        if not set(snapshot_asset_names(info, tag).values()) <= expected:
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
    # GitHub has the complete public snapshot before COS uploads begin.
    # Latest pointers are only updated after both public COS installers verify.
    cos("artifacts", directory)
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


def ensure_release_tag(tag: str, sha: str) -> None:
    """Create an annotated tag once; never move an existing version tag."""
    if not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        raise ValueError("Tag must be vX.Y.Z")
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("GITHUB_SHA must be a full commit SHA for automatic tagging")
    existing = gh_json(f"repos/{REPOSITORY}/git/ref/tags/{tag}", missing_ok=True)
    if existing is None:
        # GITHUB_TOKEN-created tags do not trigger another push workflow.
        # Delivery continues here using artifacts from the same successful build.
        created = json.loads(
            gh(
                "api",
                f"repos/{REPOSITORY}/git/tags",
                "--method",
                "POST",
                "-f",
                f"tag={tag}",
                "-f",
                f"message=Release {tag}",
                "-f",
                f"object={sha}",
                "-f",
                "type=commit",
            ).stdout
        )
        tag_object = created["sha"]
        if not isinstance(tag_object, str) or not re.fullmatch(
            r"[0-9a-f]{40}", tag_object
        ):
            raise ValueError("GitHub returned an invalid tag object SHA")
        gh(
            "api",
            f"repos/{REPOSITORY}/git/refs",
            "--method",
            "POST",
            "-f",
            f"ref=refs/tags/{tag}",
            "-f",
            f"sha={tag_object}",
        )
    actual = tag_sha(tag)
    if actual != sha:
        raise ValueError(
            f"{tag} already points to {actual}, but this build is {sha}. "
            "Keep the existing tag and release assets; bump the version for a new build."
        )


def publish(directory: Path, *, auto_tag: bool = False) -> None:
    if auto_tag:
        if (
            GITHUB_ACTIONS != "true"
            or RELEASE_JOB != "1"
            or not DEFAULT_BRANCH
            or REF != f"refs/heads/{DEFAULT_BRANCH}"
        ):
            raise ValueError(
                "Automatic publishing requires the default-branch release job"
            )
        if not re.fullmatch(r"[0-9a-f]{40}", SOURCE_SHA):
            raise ValueError(
                "GITHUB_SHA must be a full commit SHA for automatic tagging"
            )
    elif not REF.startswith("refs/tags/"):
        raise ValueError("Publishing requires a version tag")
    manifest = validate()
    tag = f"v{manifest['version']}"
    # No tag or release is written until both platform installers are present.
    installer_assets(directory, manifest["version"])
    preflight()
    if auto_tag:
        ensure_release_tag(tag, SOURCE_SHA)
    sha = tag_sha(tag)
    if SOURCE_SHA and SOURCE_SHA != sha:
        raise ValueError("Workflow commit differs from release tag")
    info = release_info(tag)
    if info and (not info["draft"] or CHECKSUMS in {a["name"] for a in info["assets"]}):
        resume(tag)
        return
    stage(directory, manifest, tag, sha, info)
    # Read back the canonical snapshot before publication and COS delivery.
    resume(tag)


def resume(tag: str) -> None:
    preflight()
    sha = tag_sha(tag)
    info = release_info(tag)
    if info is None:
        raise ValueError(
            "No release snapshot to resume; run a default-branch or tag build first"
        )
    with tempfile.TemporaryDirectory(prefix="score-trans-release-") as temporary:
        directory = Path(temporary)
        download_snapshot(info, directory, tag, sha)
        finish(directory, tag, info)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", choices=["validate", "publish", "auto-publish", "resume"]
    )
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
        publish(args.assets, auto_tag=args.command == "auto-publish")
