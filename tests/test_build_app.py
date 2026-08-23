from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "build_app", Path(__file__).parents[1] / "build-app.py"
)
assert _SPEC is not None and _SPEC.loader is not None
build_app = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = build_app
_SPEC.loader.exec_module(build_app)


def _write_wrapper(path: Path, checksum: str) -> None:
    path.parent.mkdir(parents=True)
    path.write_text(
        "\n".join(
            [
                "distributionUrl=https\\://services.gradle.org/distributions/gradle-9.1.0-bin.zip",
                f"distributionSha256Sum={checksum}",
                "validateDistributionUrl=true",
            ]
        ),
        encoding="utf-8",
    )


def test_gradle_cache_is_verified_before_it_is_copied(
    tmp_path: Path, monkeypatch
) -> None:
    archive = b"trusted Gradle archive"
    checksum = hashlib.sha256(archive).hexdigest()
    audiveris = tmp_path / "audiveris"
    wrapper = audiveris / "gradle" / "wrapper" / "gradle-wrapper.properties"
    _write_wrapper(wrapper, checksum)
    cache_source = (
        tmp_path
        / "home"
        / ".gradle"
        / "wrapper"
        / "dists"
        / "gradle-9.1.0-bin"
        / "source-hash"
    )
    (cache_source / "gradle-9.1.0" / "bin").mkdir(parents=True)
    (cache_source / "gradle-9.1.0-bin.zip").write_bytes(archive)
    monkeypatch.setattr(
        build_app.Path, "home", classmethod(lambda cls: tmp_path / "home")
    )
    monkeypatch.setattr(build_app, "THIRD_PARTY", tmp_path / "third_party")

    build_app._cache_gradle(audiveris)

    copied_archive = next(
        (tmp_path / "third_party" / "gradle_home").rglob("gradle-9.1.0-bin.zip")
    )
    assert copied_archive.read_bytes() == archive
    assert "distributionSha256Sum=" + checksum in wrapper.read_text(encoding="utf-8")
    assert "validateDistributionUrl=true" in wrapper.read_text(encoding="utf-8")


def test_gradle_cache_rejects_a_tampered_archive(tmp_path: Path, monkeypatch) -> None:
    audiveris = tmp_path / "audiveris"
    wrapper = audiveris / "gradle" / "wrapper" / "gradle-wrapper.properties"
    _write_wrapper(wrapper, hashlib.sha256(b"trusted").hexdigest())
    cache_source = (
        tmp_path
        / "home"
        / ".gradle"
        / "wrapper"
        / "dists"
        / "gradle-9.1.0-bin"
        / "source-hash"
    )
    (cache_source / "gradle-9.1.0" / "bin").mkdir(parents=True)
    (cache_source / "gradle-9.1.0-bin.zip").write_bytes(b"tampered")
    monkeypatch.setattr(
        build_app.Path, "home", classmethod(lambda cls: tmp_path / "home")
    )
    monkeypatch.setattr(build_app, "THIRD_PARTY", tmp_path / "third_party")

    with pytest.raises(RuntimeError, match="SHA-256 不匹配"):
        build_app._cache_gradle(audiveris)


def test_cleanup_audiveris_removes_stale_tesseract_artifacts(tmp_path: Path) -> None:
    audiveris = tmp_path / "audiveris"
    stale_paths = [
        audiveris
        / "app"
        / "build"
        / "classes"
        / "java"
        / "main"
        / "org"
        / "audiveris"
        / "omr"
        / "text"
        / "tesseract"
        / "TesseractOCR.class",
        audiveris
        / "app"
        / "build"
        / "resources"
        / "main"
        / "org"
        / "audiveris"
        / "omr"
        / "text"
        / "tesseract"
        / "Languages.properties",
        audiveris / "app" / "dev" / "tessdata" / "eng.traineddata",
    ]
    for path in stale_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"stale")

    build_app._cleanup_audiveris(audiveris)

    assert all(not path.exists() for path in stale_paths)


def test_validate_audiveris_program_id_rejects_tesseract_metadata(
    tmp_path: Path,
) -> None:
    audiveris = tmp_path / "audiveris"
    program_id = (
        audiveris
        / "app"
        / "build"
        / "generated-src"
        / "org"
        / "audiveris"
        / "omr"
        / "ProgramId.java"
    )
    program_id.parent.mkdir(parents=True, exist_ok=True)
    program_id.write_text(
        'public static final String TESSDATA_TAG = "4.1.0";\n',
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="TESSDATA_TAG"):
        build_app._validate_audiveris_program_id(audiveris)


def test_package_assertion_rejects_tesseract_artifacts(tmp_path: Path) -> None:
    audiveris = tmp_path / "audiveris"
    stale = audiveris / "app" / "build" / "libs" / "leptonica.dll"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_bytes(b"stale")

    with pytest.raises(RuntimeError, match="Tesseract artifacts"):
        build_app._assert_no_tesseract_artifacts(audiveris)
