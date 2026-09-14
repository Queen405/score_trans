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
    assets = release.prepare_assets(tmp_path, manifest)
    assert len(assets) == 4
    assert len((tmp_path / "SHA256SUMS.txt").read_text().splitlines()) == 3
    assert json.loads((tmp_path / "latest.json").read_text())["version"] == "1.2.3"


def test_release_waits_for_quality_and_both_platforms() -> None:
    workflow = yaml.load(
        (ROOT / ".github/workflows/package.yml").read_text(), Loader=yaml.BaseLoader
    )
    assert set(workflow["jobs"]["release"]["needs"]) == {"quality", "windows", "mac"}
    assert (
        "tag" not in workflow["jobs"]
    )  # Tag writes share the serialized delivery job.
    assert "github.event.repository.default_branch" in workflow["jobs"]["release"]["if"]
    assert "auto-publish" in workflow["jobs"]["release"]["with"]["mode"]
    for platform in ("windows", "mac"):
        source = (ROOT / f".github/workflows/build-{platform}.yml").read_text()
        build = yaml.load(source, Loader=yaml.BaseLoader)
        assert "push" not in build["on"]
        assert "gh release" not in source
        assert "tools/smoke_" in source
        assert "build-app.py" in source
        assert "--frozen-lockfile" in source


class FakeGitHub:
    def __init__(self, sanitize_names=False):
        self.sanitize_names = sanitize_names
        self.info = None
        self.assets = {}
        self.calls = []
        self.fail_action = None

    def run(self, *args):
        import subprocess

        self.calls.append(args)
        action = args[1]
        if action == self.fail_action:
            self.fail_action = None
            raise subprocess.CalledProcessError(1, args)
        if action == "create":
            self.info = {"draft": True, "assets": []}
        elif action == "upload":
            for arg in args:
                path = Path(arg)
                if path.is_file():
                    name = (
                        path.name.replace(" ", ".")
                        if self.sanitize_names
                        else path.name
                    )
                    self.assets[name] = path.read_bytes()
            self.info["assets"] = [{"name": name} for name in self.assets]
        elif action == "download":
            directory = Path(args[args.index("--dir") + 1])
            for name, payload in self.assets.items():
                (directory / name).write_bytes(payload)
        elif action == "edit" and "--draft=false" in args:
            self.info["draft"] = False
        return subprocess.CompletedProcess(args, 0, "")


@pytest.fixture(params=[False, True], ids=["original-names", "github-sanitized-names"])
def delivery(tmp_path: Path, monkeypatch, request):
    remote = FakeGitHub(sanitize_names=request.param)
    manifest = {"version": "1.2.3", "notes": "test"}
    windows, mac = release.installer_names("1.2.3")
    manifest.update(
        url=release.installer_url(windows), urlMac=release.installer_url(mac)
    )
    for name in (windows, mac):
        (tmp_path / name).write_bytes(name.encode())
    monkeypatch.setattr(release, "REF", "refs/tags/v1.2.3")
    monkeypatch.setattr(release, "SOURCE_SHA", "a" * 40)
    monkeypatch.setattr(release, "validate", lambda: manifest)
    monkeypatch.setattr(release, "preflight", lambda: None)
    monkeypatch.setattr(release, "tag_sha", lambda _: "a" * 40)
    monkeypatch.setattr(release, "gh", remote.run)
    monkeypatch.setattr(release, "release_info", lambda _: remote.info)
    monkeypatch.setattr(release, "gh_json", lambda *_, **__: None)
    return tmp_path, remote


@pytest.mark.parametrize("failed_phase", ["artifacts", "promote"])
def test_delivery_failure_resumes_canonical_snapshot(
    delivery, monkeypatch, failed_phase
):
    directory, remote = delivery
    phases = []

    def fail_once(phase, *_):
        phases.append(phase)
        if phases.count(failed_phase) == 1 and phase == failed_phase:
            raise RuntimeError("simulated delivery interruption")
        return {"status": "promoted"}

    monkeypatch.setattr(release, "cos", fail_once)
    with pytest.raises(RuntimeError, match="interruption"):
        release.publish(directory)
    assert not remote.info["draft"]
    original = dict(remote.assets)
    # Rebuilt bytes cannot replace a completed snapshot.
    (directory / "Score Trans Setup 1.2.3.exe").write_bytes(b"different rebuild")
    release.publish(directory)
    assert remote.assets == original
    assert not remote.info["draft"]
    assert len([c for c in remote.calls if c[1] == "upload"]) == 2


def test_github_latest_failure_resumes_without_replacing_assets(delivery, monkeypatch):
    directory, remote = delivery
    monkeypatch.setattr(release, "cos", lambda *_: {"status": "promoted"})
    original_run = remote.run

    def fail_latest(*args):
        if "--latest" in args:
            raise RuntimeError("latest interrupted")
        return original_run(*args)

    monkeypatch.setattr(release, "gh", fail_latest)
    with pytest.raises(RuntimeError, match="latest interrupted"):
        release.publish(directory)
    assert not remote.info["draft"]
    monkeypatch.setattr(release, "gh", remote.run)
    release.resume("v1.2.3")
    assert remote.calls[-1][-1] == "--latest"


def test_incomplete_draft_can_be_repaired(delivery, monkeypatch):
    import subprocess

    directory, remote = delivery
    remote.fail_action = "upload"
    monkeypatch.setattr(release, "cos", lambda *_: {"status": "promoted"})
    with pytest.raises(subprocess.CalledProcessError):
        release.publish(directory)
    assert remote.info["draft"]
    assert release.CHECKSUMS not in remote.assets
    release.publish(directory)
    assert not remote.info["draft"]


@pytest.mark.parametrize("latest_source", ["cos", "github"])
def test_older_versions_never_replace_latest(delivery, monkeypatch, latest_source):
    directory, remote = delivery
    phases = []

    def cos(phase, *_):
        phases.append(phase)
        return {"status": "older"}

    monkeypatch.setattr(release, "cos", cos)
    if latest_source == "github":
        monkeypatch.setattr(release, "gh_json", lambda *_, **__: {"tag_name": "v1.3.0"})
    release.publish(directory)
    assert not remote.info["draft"]
    assert not any("--latest" in call for call in remote.calls)
    if latest_source == "github":
        assert "promote" not in phases


def test_snapshot_checksum_and_tag_provenance_are_enforced(delivery, monkeypatch):
    directory, remote = delivery
    monkeypatch.setattr(release, "cos", lambda *_: {"status": "promoted"})
    release.publish(directory)
    monkeypatch.setattr(release, "tag_sha", lambda _: "b" * 40)
    with pytest.raises(ValueError, match="provenance"):
        release.resume("v1.2.3")
    monkeypatch.setattr(release, "tag_sha", lambda _: "a" * 40)
    name = "Score Trans Setup 1.2.3.exe"
    if remote.sanitize_names:
        name = name.replace(" ", ".")
    remote.assets[name] = b"tampered"
    with pytest.raises(ValueError, match="checksum mismatch"):
        release.resume("v1.2.3")


@pytest.mark.parametrize("status", [403, 404, 500])
def test_only_explicit_github_404_is_treated_as_absence(monkeypatch, status):
    import subprocess

    def fail(*args):
        raise subprocess.CalledProcessError(1, args, stderr=f"gh: HTTP {status}")

    monkeypatch.setattr(release, "gh", fail)
    if status == 404:
        assert release.gh_json("example", missing_ok=True) is None
    else:
        with pytest.raises(subprocess.CalledProcessError):
            release.gh_json("example", missing_ok=True)


def test_recovery_and_publish_share_lock_and_configuration():
    workflow = yaml.load(
        (ROOT / ".github/workflows/release.yml").read_text(), Loader=yaml.BaseLoader
    )
    job = workflow["jobs"]["deliver"]
    assert job["concurrency"] == {
        "group": "score-trans-release",
        "cancel-in-progress": "false",
        "queue": "max",
    }
    assert {"COS_BUCKET", "COS_REGION", "COS_PREFIX", "GH_TOKEN"} <= job["env"].keys()
    downloads = [
        step["with"]["name"]
        for step in job["steps"]
        if step.get("uses", "").startswith("actions/download-artifact")
    ]
    assert set(downloads) == {"score-trans-windows-x64", "score-trans-mac-arm64"}
    quality = (ROOT / ".github/workflows/ci.yml").read_text()
    assert "pnpm check:api-types" in quality
    assert "pnpm test:release-tools" in quality


@pytest.fixture
def automatic_delivery(delivery, monkeypatch):
    monkeypatch.setattr(release, "REF", "refs/heads/main")
    monkeypatch.setattr(release, "DEFAULT_BRANCH", "main")
    monkeypatch.setattr(release, "GITHUB_ACTIONS", "true")
    monkeypatch.setattr(release, "RELEASE_JOB", "1")
    return delivery


def test_auto_publish_tags_build_before_release_then_uploads_both_to_cos(
    automatic_delivery, monkeypatch
):
    directory, remote = automatic_delivery
    tagged = []
    phases = []

    def tag(name, sha):
        assert remote.info is None
        assert not phases
        tagged.append((name, sha))

    def cos(phase, snapshot):
        assert tagged == [("v1.2.3", "a" * 40)]
        assert not remote.info["draft"]  # User requested GitHub publication first.
        release.verify_snapshot(snapshot, "v1.2.3", "a" * 40)
        assert all(
            (snapshot / name).is_file() for name in release.installer_names("1.2.3")
        )
        phases.append(phase)
        return {"status": "promoted"}

    monkeypatch.setattr(release, "ensure_release_tag", tag)
    monkeypatch.setattr(release, "cos", cos)
    release.publish(directory, auto_tag=True)
    assert phases == ["artifacts", "promote"]
    assert remote.calls[-1][-1] == "--latest"
    assert json.loads(remote.assets[release.METADATA])["source_sha"] == "a" * 40


@pytest.mark.parametrize(
    "name,value",
    [
        ("REF", "refs/heads/feature"),
        ("REF", "refs/tags/v1.2.3"),
        ("DEFAULT_BRANCH", ""),
        ("GITHUB_ACTIONS", "false"),
        ("RELEASE_JOB", ""),
        ("SOURCE_SHA", ""),
        ("SOURCE_SHA", "abc123"),
    ],
)
def test_auto_publish_rejects_untrusted_source_before_any_remote_write(
    automatic_delivery, monkeypatch, name, value
):
    directory, remote = automatic_delivery
    monkeypatch.setattr(release, name, value)
    monkeypatch.setattr(
        release, "preflight", lambda: pytest.fail("No remote access expected")
    )
    with pytest.raises(ValueError):
        release.publish(directory, auto_tag=True)
    assert remote.calls == []


def test_auto_publish_missing_mac_cannot_create_a_tag(automatic_delivery, monkeypatch):
    directory, remote = automatic_delivery
    (directory / "Score Trans-1.2.3-arm64.dmg").unlink()
    monkeypatch.setattr(
        release,
        "ensure_release_tag",
        lambda *_: pytest.fail("Tag created before assets validated"),
    )
    with pytest.raises(ValueError, match="Missing or empty"):
        release.publish(directory, auto_tag=True)
    assert remote.calls == []


def test_auto_publish_preflight_failure_cannot_create_a_tag(
    automatic_delivery, monkeypatch
):
    directory, remote = automatic_delivery

    def preflight():
        raise ValueError("Tencent COS credentials are required")

    monkeypatch.setattr(release, "preflight", preflight)
    monkeypatch.setattr(
        release,
        "ensure_release_tag",
        lambda *_: pytest.fail("Tag created before preflight"),
    )
    with pytest.raises(ValueError, match="credentials"):
        release.publish(directory, auto_tag=True)
    assert remote.calls == []


def test_auto_publish_conflicting_tag_cannot_create_a_release(
    automatic_delivery, monkeypatch
):
    directory, remote = automatic_delivery
    monkeypatch.setattr(
        release, "gh_json", lambda *_, **__: {"ref": "refs/tags/v1.2.3"}
    )
    monkeypatch.setattr(release, "tag_sha", lambda _: "b" * 40)
    with pytest.raises(ValueError, match="already points to"):
        release.publish(directory, auto_tag=True)
    assert remote.calls == []
    assert remote.info is None


def test_tag_creation_writes_annotated_tag_then_ref_for_exact_commit(monkeypatch):
    import subprocess

    calls = []
    monkeypatch.setattr(release, "gh_json", lambda *_, **__: None)

    def run(*args):
        calls.append(args)
        if args[1].endswith("/git/tags"):
            return subprocess.CompletedProcess(args, 0, json.dumps({"sha": "b" * 40}))
        return subprocess.CompletedProcess(args, 0, "{}")

    def resolve(tag):
        assert len(calls) == 2
        assert tag == "v1.2.3"
        return "a" * 40

    monkeypatch.setattr(release, "gh", run)
    monkeypatch.setattr(release, "tag_sha", resolve)
    release.ensure_release_tag("v1.2.3", "a" * 40)
    assert calls[0] == (
        "api",
        f"repos/{release.REPOSITORY}/git/tags",
        "--method",
        "POST",
        "-f",
        "tag=v1.2.3",
        "-f",
        "message=Release v1.2.3",
        "-f",
        "object=" + "a" * 40,
        "-f",
        "type=commit",
    )
    assert calls[1] == (
        "api",
        f"repos/{release.REPOSITORY}/git/refs",
        "--method",
        "POST",
        "-f",
        "ref=refs/tags/v1.2.3",
        "-f",
        "sha=" + "b" * 40,
    )


@pytest.mark.parametrize("kind", ["tag", "commit"])
def test_existing_tag_at_same_commit_is_reused_without_writes(monkeypatch, kind):
    monkeypatch.setattr(release, "gh_json", lambda *_, **__: {"object": {"type": kind}})
    monkeypatch.setattr(release, "tag_sha", lambda _: "a" * 40)
    monkeypatch.setattr(
        release, "gh", lambda *_: pytest.fail("Existing tag must not be rewritten")
    )
    release.ensure_release_tag("v1.2.3", "a" * 40)


def test_tag_lookup_failure_is_not_treated_as_missing(monkeypatch):
    import subprocess

    calls = []

    def run(*args):
        calls.append(args)
        raise subprocess.CalledProcessError(1, args, stderr="gh: HTTP 403")

    monkeypatch.setattr(release, "gh", run)
    with pytest.raises(subprocess.CalledProcessError):
        release.ensure_release_tag("v1.2.3", "a" * 40)
    assert len(calls) == 1
    assert "POST" not in calls[0]


def test_github_publication_failure_prevents_cos_upload(delivery, monkeypatch):
    directory, remote = delivery
    remote.fail_action = "edit"
    monkeypatch.setattr(
        release, "cos", lambda *_: pytest.fail("COS write before GitHub publication")
    )
    import subprocess

    with pytest.raises(subprocess.CalledProcessError):
        release.publish(directory)
    assert remote.info["draft"]


def test_auto_publish_reuses_completed_snapshot_on_retry(
    automatic_delivery, monkeypatch
):
    directory, remote = automatic_delivery
    monkeypatch.setattr(release, "ensure_release_tag", lambda *_: None)
    phases = []

    def cos(phase, *_):
        phases.append(phase)
        if len(phases) == 1:
            raise RuntimeError("COS interrupted after GitHub publication")
        return {"status": "promoted"}

    monkeypatch.setattr(release, "cos", cos)
    with pytest.raises(RuntimeError, match="interrupted"):
        release.publish(directory, auto_tag=True)
    original = dict(remote.assets)
    (directory / "Score Trans Setup 1.2.3.exe").write_bytes(b"different rebuild")
    release.publish(directory, auto_tag=True)
    assert remote.assets == original
    assert len([call for call in remote.calls if call[1] == "upload"]) == 2


def test_auto_release_downloads_same_run_assets_and_keeps_credentials_in_locked_job():
    workflow = yaml.load(
        (ROOT / ".github/workflows/release.yml").read_text(), Loader=yaml.BaseLoader
    )
    job = workflow["jobs"]["deliver"]
    assert job["env"]["GH_TOKEN"] == "${{ github.token }}"
    assert (
        job["env"]["TENCENTCLOUD_SECRET_ID"] == "${{ secrets.TENCENTCLOUD_SECRET_ID }}"
    )
    assert (
        job["env"]["TENCENTCLOUD_SECRET_KEY"]
        == "${{ secrets.TENCENTCLOUD_SECRET_KEY }}"
    )
    steps = job["steps"]
    checkout = next(
        step for step in steps if step.get("uses", "").startswith("actions/checkout")
    )
    assert checkout["with"]["ref"] == "${{ github.sha }}"
    for step in steps:
        if step.get("uses", "").startswith("actions/download-artifact"):
            assert "auto-publish" in step["if"]
            assert "run-id" not in step["with"]
            assert step["with"]["path"] == "release-assets"
    assert ".venv/bin/python tools/release.py auto-publish" in steps[-1]["run"]


@pytest.mark.parametrize(
    "names",
    [
        ["Score Trans Setup 1.2.3.exe", "Score.Trans.Setup.1.2.3.exe"],
        ["../../unexpected.exe"],
        ["Score.Trans.Setup.1.2.4.exe"],
    ],
)
def test_remote_asset_mapping_rejects_collisions_and_unexpected_names(names):
    with pytest.raises(ValueError, match="Unexpected or duplicate"):
        release.snapshot_asset_names(
            {"assets": [{"name": name} for name in names]}, "v1.2.3"
        )
