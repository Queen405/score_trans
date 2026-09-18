from __future__ import annotations

import json
import numpy as np
from PIL import Image, ImageDraw
import pytest
from trans_jp.models.geometry import Transform
from trans_jp.models.contracts import CliConfig, LlmConfig, CompletionResult
from trans_jp.models.errors import EngineError
from trans_jp.pipeline.runner import run
from trans_jp.preprocess.deskew import normalize_skew
from trans_jp.preprocess.image import prepare_work_image, to_binary, otsu_binarize
from trans_jp.structure.row_segmenter import segment
from trans_jp.raster.filaments import detect_filaments
from trans_jp.cli import main


@pytest.mark.parametrize("slope", [0.045, -0.045])
def test_deskew_preserves_inverse_coordinates(slope):
    image = Image.new("RGB", (600, 260), "white")
    draw = ImageDraw.Draw(image)
    for y in [40, 95, 150, 205]:
        draw.line((25, y, 560, y + slope * 535), fill="black", width=2)
    corrected, transform = normalize_skew(image, image.size)
    assert abs(transform.slope - slope) < 0.005
    lines = detect_filaments(
        otsu_binarize(np.array(corrected.convert("L"))), "horizontal", 20
    )
    long = [line for line in lines if line.bounds.width > 400]
    assert len(long) == 4
    for line in long:
        assert abs(line.slope) < 0.005
        for x, y in line.points:
            original_x, original_y = transform.point(x, y)
            nearest = min(
                abs(original_y - (base + slope * (original_x - 25)))
                for base in [40, 95, 150, 205]
            )
            assert nearest <= 2


def test_short_noise_does_not_trigger_page_deskew():
    image = Image.new("RGB", (600, 260), "white")
    draw = ImageDraw.Draw(image)
    for x in range(20, 580, 40):
        draw.line((x, 40, x + 12, 42), fill="black", width=2)
    _, transform = normalize_skew(image, image.size)
    assert transform.slope == 0


def test_row_metadata_uses_actual_scale_not_rounded_nominal_scale(tmp_path):
    image = Image.new("RGB", (801, 221), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((100, 70, 500, 95), fill="black")
    work, _ = prepare_work_image(image, 2500)
    transform = Transform(work.width / image.width, work.height / image.height)
    rows = segment(to_binary(work), work, tmp_path, transform=transform)
    assert len(rows) == 1
    row = rows[0]
    assert abs(row.y_top - row.work_y_top / transform.scale_y) <= 0.5
    assert abs(row.y_bottom - (row.work_y_top + row.height) / transform.scale_y) <= 0.5


def test_engine_failure_is_typed_and_cli_keeps_exit_codes(tmp_path):
    blank = tmp_path / "blank.png"
    Image.new("RGB", (200, 200), "white").save(blank)
    with pytest.raises(EngineError) as error:
        run(
            CliConfig(
                blank, tmp_path / "out", LlmConfig("x", "x", "x"), min_image_edge=0
            )
        )
    assert error.value.exit_code == 2
    assert (
        main(
            [
                "--input",
                str(blank),
                "--output-dir",
                str(tmp_path / "cli"),
                "--api-key",
                "x",
                "--base-url",
                "x",
                "--model",
                "x",
                "--min-image-edge",
                "0",
            ]
        )
        == 2
    )


def test_pipeline_empty_geometry_never_falls_back_to_source_text(tmp_path):
    image = Image.new("RGB", (400, 180), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((10, 30, 50, 70), fill="black")
    source = tmp_path / "source.png"
    image.save(source)

    class Client:
        def transcribe_row_with_retry(self, image_path, prompt, **kwargs):
            return CompletionResult(
                json.dumps(
                    {
                        "row_type": "notation",
                        "row_text": "1",
                        "tokens": [{"text": "1", "role": "note", "x": 0.95, "w": 0.01}],
                    }
                ),
                "stop",
            )

    result = run(
        CliConfig(
            source,
            tmp_path / "out",
            LlmConfig("", "", ""),
            min_image_edge=0,
            debug=True,
        ),
        Client(),
    )
    assert not result.source_map["sheets"][0]["elements"]
    assert result.text_anchors[0]["valid"]
    assert "<text" not in result.overlay_svg and "<rect" not in result.overlay_svg
    assert result.warnings


def test_invalid_input_and_unwritable_output_exit_codes(tmp_path):
    bad = tmp_path / "bad.png"
    bad.write_text("not an image", encoding="utf-8")
    args = [
        "--input",
        str(bad),
        "--output-dir",
        str(tmp_path / "out"),
        "--api-key",
        "x",
        "--base-url",
        "x",
        "--model",
        "x",
    ]
    assert main(args) == 1
    destination = tmp_path / "not-a-directory"
    destination.write_text("occupied", encoding="utf-8")
    args[3] = str(destination)
    assert main(args) == 4
