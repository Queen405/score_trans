from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "release_tools", ROOT / "tools/release.py"
)
assert SPEC and SPEC.loader
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


def test_release_rejects_mismatched_tag_and_manifest(tmp_path: Path) -> None:
    desktop = tmp_path / "desktop"
    desktop.mkdir()
    (desktop / "package.json").write_text('{"version":"1.2.3"}')
    (desktop / "latest.json").write_text('{"version":"1.2.3"}')
    with pytest.raises(ValueError, match="Tag must"):
        release.validate(tmp_path, "refs/tags/v1.2.4")
    (desktop / "latest.json").write_text('{"version":"1.2.2"}')
    with pytest.raises(ValueError, match="versions differ"):
        release.validate(tmp_path, "refs/tags/v1.2.3")


def test_release_requires_both_platforms_before_manifest(tmp_path: Path) -> None:
    manifest = {"version": "1.2.3", "url": "https://example.org"}
    (tmp_path / "Score Trans Setup 1.2.3.exe").write_bytes(b"windows")
    with pytest.raises(ValueError, match="Missing"):
        release.prepare_assets(tmp_path, manifest)
    assert not (tmp_path / "latest.json").exists()
    (tmp_path / "Score Trans-1.2.3-arm64.dmg").write_bytes(b"mac")
    (tmp_path / "Score Trans-1.2.3-arm64.zip").write_bytes(b"zip")
    assets = release.prepare_assets(tmp_path, manifest)
    assert len(assets) == 5
    assert len((tmp_path / "SHA256SUMS.txt").read_text().splitlines()) == 4
    assert json.loads((tmp_path / "latest.json").read_text())["version"] == "1.2.3"


def test_release_waits_for_quality_and_both_platforms() -> None:
    workflow = yaml.load(
        (ROOT / ".github/workflows/package.yml").read_text(), Loader=yaml.BaseLoader
    )
    assert set(workflow["jobs"]["release"]["needs"]) == {"quality", "windows", "mac"}
    for platform in ("windows", "mac"):
        source = (ROOT / f".github/workflows/build-{platform}.yml").read_text()
        build = yaml.load(source, Loader=yaml.BaseLoader)
        assert "push" not in build["on"]
        assert "gh release" not in source
        assert "tools/smoke_" in source
        assert "build-app.py --skip-electron" in source
        assert "--frozen-lockfile" in source


def test_failed_upload_never_publishes_release(tmp_path: Path, monkeypatch) -> None:
    import subprocess

    monkeypatch.setattr(release, "REF", "refs/tags/v1.2.3")
    monkeypatch.setattr(release, "validate", lambda: {"version": "1.2.3"})
    monkeypatch.setattr(
        release, "prepare_assets", lambda *_: [tmp_path / "installer.exe"]
    )
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        if args[2] == "view":
            return subprocess.CompletedProcess(args, 0, '{"isDraft":true,"assets":[]}')
        if args[2] == "upload":
            raise subprocess.CalledProcessError(1, args)
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(release.subprocess, "run", run)
    with pytest.raises(subprocess.CalledProcessError):
        release.publish(tmp_path)
    assert all(args[2] != "edit" for args in calls)


def test_successful_upload_publishes_last(tmp_path: Path, monkeypatch) -> None:
    import subprocess

    monkeypatch.setattr(release, "REF", "refs/tags/v1.2.3")
    monkeypatch.setattr(release, "validate", lambda: {"version": "1.2.3"})
    monkeypatch.setattr(
        release, "prepare_assets", lambda *_: [tmp_path / "installer.exe"]
    )
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 1 if args[2] == "view" else 0)

    monkeypatch.setattr(release.subprocess, "run", run)
    release.publish(tmp_path)
    assert [args[2] for args in calls] == ["view", "create", "upload", "edit"]
    assert "--draft" in calls[1]
    assert "--draft=false" in calls[-1]
