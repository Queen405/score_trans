from __future__ import annotations

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


def test_validate_published_defaults_rejects_non_string_layout_value(
    tmp_path: Path,
) -> None:
    source_config = _REPO_ROOT / "backend" / "score_trans" / "config"
    payload = json.loads(
        (source_config / "published_defaults.json").read_text(encoding="utf-8")
    )
    payload["backend"]["jianpu_content_scale_percent"] = 67

    target_config = tmp_path / "backend" / "score_trans" / "config"
    _write_baseline(target_config / "published_defaults.json", payload)
    target_config.joinpath("env.example").write_text(
        (source_config / "env.example").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    with pytest.raises(
        TypeError,
        match="backend.jianpu_content_scale_percent must be a string",
    ):
        build_app._validate_published_defaults(tmp_path)


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


def test_purge_removes_suffixed_trash(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(build_app, "BUILD_RESOURCES", tmp_path)
    stale = tmp_path / "third_party" / "audiveris.trash-123"
    stale.mkdir(parents=True)
    (stale / "old.jar").write_bytes(b"old")
    build_app._purge_trash_leftovers()
    assert not stale.exists()
