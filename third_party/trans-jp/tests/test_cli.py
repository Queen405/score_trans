from __future__ import annotations

import json

import pytest

from trans_jp import cli
from trans_jp.cli import main, run, write_outputs
from trans_jp.schemas import CliConfig, LlmConfig


def _config(input_path, output_dir, **overrides) -> CliConfig:
    params = {
        "input_path": input_path,
        "output_dir": output_dir,
        "llm": LlmConfig(api_key="k", base_url="http://x", model="m"),
        "target_key": "C",
        "title": None,
        "extra_prompt": None,
        "prompt_config": None,
        "concurrency": 2,
        "min_image_edge": 0,
        "debug": False,
    }
    params.update(overrides)
    return CliConfig(**params)


def test_end_to_end_produces_all_outputs(
    synthetic_jianpu_image, tmp_path, mock_llm_client
):
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    result = run(
        _config(synthetic_jianpu_image, output_dir), llm_client=mock_llm_client
    )
    write_outputs(result, output_dir)

    jianpu = (output_dir / "jianpu.txt").read_text(encoding="utf-8")
    assert "1 2 3 4 |" in jianpu

    source_map = json.loads(
        (output_dir / "score-link-map.json").read_text(encoding="utf-8")
    )
    assert source_map["version"] == 1
    assert source_map["sheets"][0]["width"] == 800
    assert len(source_map["sheets"][0]["elements"]) > 0
    first = source_map["sheets"][0]["elements"][0]
    assert first["source_id"].startswith("s0:r")
    assert "hit_path" in first
    assert first["musicxml_locator"]["attribute"] == "id"

    overlay = (output_dir / "overlay.svg").read_text(encoding="utf-8")
    assert overlay.startswith("<svg") or "<svg" in overlay[:200]

    anchors = json.loads((output_dir / "text_anchors.json").read_text(encoding="utf-8"))
    assert {e["source_id"] for e in source_map["sheets"][0]["elements"]} <= {
        a["source_id"] for a in anchors
    }
    assert "<text" not in overlay
    assert (output_dir / "overlay-preview.png").is_file()
    assert all("start_utf16" in a and "end_utf16" in a for a in anchors)

    row_images = sorted((output_dir / "rows").glob("row_*.png"))
    assert len(row_images) == 3


def test_source_ids_match_between_map_and_anchors(
    synthetic_jianpu_image, tmp_path, mock_llm_client
):
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    result = run(
        _config(synthetic_jianpu_image, output_dir), llm_client=mock_llm_client
    )
    map_ids = {e["source_id"] for e in result.source_map["sheets"][0]["elements"]}
    anchor_ids = {a["source_id"] for a in result.text_anchors}
    assert map_ids and map_ids <= anchor_ids


def test_no_rows_exits_with_code_2(tmp_path, mock_llm_client):
    from PIL import Image

    blank = tmp_path / "blank.png"
    Image.new("RGB", (400, 300), "white").save(blank)
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    with pytest.raises(SystemExit) as exc_info:
        run(_config(blank, output_dir), llm_client=mock_llm_client)
    assert exc_info.value.code == cli.EXIT_NO_ROWS


def test_all_rows_failed_exits_with_code_3(synthetic_jianpu_image, tmp_path):
    class AlwaysFailClient:
        def transcribe_row_with_retry(self, image_path, prompt, **kwargs):
            raise RuntimeError("api down")

    output_dir = tmp_path / "out"
    output_dir.mkdir()
    with pytest.raises(SystemExit) as exc_info:
        run(
            _config(synthetic_jianpu_image, output_dir),
            llm_client=AlwaysFailClient(),
        )
    assert exc_info.value.code == cli.EXIT_LLM_ALL_FAILED


def test_main_missing_image_returns_code_1(tmp_path):
    code = main(
        [
            "--input",
            str(tmp_path / "missing.png"),
            "--output-dir",
            str(tmp_path / "out"),
            "--api-key",
            "k",
            "--base-url",
            "http://x",
            "--model",
            "m",
        ]
    )
    assert code == cli.EXIT_IMAGE_LOAD_FAILED


def test_main_missing_credentials_returns_arg_error(tmp_path, monkeypatch):
    monkeypatch.delenv("TRANS_JP_API_KEY", raising=False)
    monkeypatch.setattr(cli, "_ENV_API_KEY", "")
    code = main(["--input", "x.png", "--output-dir", "out"])
    assert code != cli.EXIT_OK


def test_extra_prompt_passed_to_llm(synthetic_jianpu_image, tmp_path, mock_llm_client):
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    run(
        _config(synthetic_jianpu_image, output_dir, extra_prompt="注意歌词"),
        llm_client=mock_llm_client,
    )
    assert any("注意歌词" in prompt for _, prompt in mock_llm_client.calls)


def test_whole_image_upscale_before_segmentation(
    synthetic_jianpu_image, tmp_path, mock_llm_client
):
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    run(
        _config(synthetic_jianpu_image, output_dir, min_image_edge=2000),
        llm_client=mock_llm_client,
    )
    from PIL import Image

    with Image.open(output_dir / "rows" / "row_0.png") as img:
        assert max(img.size) >= 2000


def test_source_map_uses_original_coordinates_with_upscale(
    synthetic_jianpu_image, tmp_path, mock_llm_client
):
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    result = run(
        _config(synthetic_jianpu_image, output_dir, min_image_edge=2500),
        llm_client=mock_llm_client,
    )
    sheet = result.source_map["sheets"][0]
    assert sheet["width"] == 800
    assert sheet["height"] == 400
    for element in sheet["elements"]:
        assert element["bounds"]["y"] < 400
        assert element["bounds"]["y"] + element["bounds"]["height"] <= 400
