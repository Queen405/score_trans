from __future__ import annotations

import hashlib
import importlib.util
import json
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


# ---------------------------------------------------------------------------
# Published defaults validation
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parents[1]


def _write_baseline(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_env_example(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def test_validate_published_defaults_passes_for_repo_baseline() -> None:
    payload = build_app._validate_published_defaults(_REPO_ROOT)
    assert payload["version"] == 1
    assert "backend" in payload
    assert "providers" in payload


def test_validate_published_defaults_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="not found"):
        build_app._validate_published_defaults(tmp_path)


def test_validate_published_defaults_rejects_private_field(tmp_path: Path) -> None:
    baseline = (
        tmp_path / "backend" / "score_trans" / "config" / "published_defaults.json"
    )
    _write_baseline(
        baseline,
        {
            "version": 1,
            "backend": {"target_key": "C", "output_dir": ""},
            "providers": {},
            "ocr_api_key": "sk-secret",
        },
    )
    _write_env_example(
        tmp_path / "backend" / "score_trans" / "config" / "env.example",
        ["SCORE_TRANS_OCR_PROVIDER=test", "SCORE_TRANS_OCR_PROVIDER_PROFILES=[]"],
    )
    with pytest.raises(RuntimeError, match="private field"):
        build_app._validate_published_defaults(tmp_path)


def test_validate_published_defaults_rejects_absolute_path(tmp_path: Path) -> None:
    baseline = (
        tmp_path / "backend" / "score_trans" / "config" / "published_defaults.json"
    )
    _write_baseline(
        baseline,
        {
            "version": 1,
            "backend": {"target_key": "C", "output_dir": "C:\\Users\\dev\\out"},
            "providers": {},
        },
    )
    _write_env_example(
        tmp_path / "backend" / "score_trans" / "config" / "env.example",
        ["SCORE_TRANS_OCR_PROVIDER=test", "SCORE_TRANS_OCR_PROVIDER_PROFILES=[]"],
    )
    with pytest.raises(RuntimeError, match="absolute path"):
        build_app._validate_published_defaults(tmp_path)


def test_cross_validate_providers_rejects_id_drift(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    _write_baseline(
        baseline,
        {
            "version": 1,
            "backend": {},
            "providers": {
                "ocr": {
                    "provider": "wrong_id",
                    "base_url": "https://api.example.com/v1",
                    "model": "m",
                    "fallback_model": "f",
                },
            },
        },
    )
    env_example = tmp_path / "env.example"
    _write_env_example(
        env_example,
        [
            "SCORE_TRANS_OCR_PROVIDER=correct_id",
            'SCORE_TRANS_OCR_PROVIDER_PROFILES=\'[{"id":"correct_id","label":"L","provider":"openai_compatible","base_url":"https://api.example.com/v1","model":"m","fallback_model":"f"}]\'',
        ],
    )
    env_vars = build_app._parse_env_example(env_example)
    payload = json.loads(baseline.read_text(encoding="utf-8"))
    with pytest.raises(RuntimeError, match="does not match"):
        build_app._cross_validate_providers(payload["providers"], env_vars)


def test_cross_validate_providers_rejects_missing_id_in_profiles(
    tmp_path: Path,
) -> None:
    env_example = tmp_path / "env.example"
    _write_env_example(
        env_example,
        [
            "SCORE_TRANS_OCR_PROVIDER=baseline_id",
            'SCORE_TRANS_OCR_PROVIDER_PROFILES=\'[{"id":"other_id","label":"L","provider":"openai_compatible","base_url":"https://api.example.com/v1","model":"m"}]\'',
        ],
    )
    env_vars = build_app._parse_env_example(env_example)
    providers = {
        "ocr": {
            "provider": "baseline_id",
            "base_url": "https://api.example.com/v1",
            "model": "m",
        },
    }
    with pytest.raises(RuntimeError, match="not present"):
        build_app._cross_validate_providers(providers, env_vars)


def test_cross_validate_providers_rejects_url_drift(tmp_path: Path) -> None:
    env_example = tmp_path / "env.example"
    _write_env_example(
        env_example,
        [
            "SCORE_TRANS_OCR_PROVIDER=p1",
            'SCORE_TRANS_OCR_PROVIDER_PROFILES=\'[{"id":"p1","label":"L","provider":"openai_compatible","base_url":"https://api.example.com/v1","model":"m","fallback_model":"f"}]\'',
        ],
    )
    env_vars = build_app._parse_env_example(env_example)
    providers = {
        "ocr": {
            "provider": "p1",
            "base_url": "https://wrong.example.com/v1",
            "model": "m",
            "fallback_model": "f",
        },
    }
    with pytest.raises(RuntimeError, match="base_url"):
        build_app._cross_validate_providers(providers, env_vars)


def test_cross_validate_providers_passes_for_repo_files() -> None:
    env_example = _REPO_ROOT / "backend" / "score_trans" / "config" / "env.example"
    baseline = (
        _REPO_ROOT / "backend" / "score_trans" / "config" / "published_defaults.json"
    )
    env_vars = build_app._parse_env_example(env_example)
    payload = json.loads(baseline.read_text(encoding="utf-8"))
    build_app._cross_validate_providers(payload["providers"], env_vars)
