from __future__ import annotations

from pathlib import Path

from PIL import Image
from score_trans.models.common.errors import ExternalToolError
from score_trans.models.settings.config import ToolConfig
from score_trans.services.recognize import external_tools
from score_trans.services.recognize.external_tools import (
    CommandResult,
    recognize_with_audiveris,
)
from score_trans.services.recognize.image_preprocess import (
    ensure_max_pixel_count,
    ensure_min_resolution,
    is_pdf,
    is_raster_image,
    parse_low_interline,
    retry_scale_from_interline,
    upscale_by_factor,
)


def _write_png(path: Path, width: int, height: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (width, height), "white").save(path, format="PNG")
    return path


def test_is_raster_image_and_pdf_classify_suffixes() -> None:
    assert is_raster_image("scan.PNG")
    assert is_raster_image("photo.jpg")
    assert not is_raster_image("score.pdf")
    assert is_pdf("score.pdf")
    assert not is_pdf("scan.png")


def test_parse_low_interline_extracts_value() -> None:
    msg = (
        "微信图片 With a too low interline value of 10 pixels,\n"
        " either this sheet contains no multi-line staves"
    )
    assert parse_low_interline(msg) == 10


def test_parse_low_interline_returns_none_when_absent() -> None:
    assert parse_low_interline("some other error") is None
    assert parse_low_interline("") is None


def test_retry_scale_from_interline_targets_eighteen() -> None:
    assert retry_scale_from_interline(10) == 1.8
    assert retry_scale_from_interline(9) == 2.0
    assert retry_scale_from_interline(0) == 0.0


def test_ensure_min_resolution_skips_pdf(tmp_path: Path) -> None:
    pdf = tmp_path / "score.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    assert (
        ensure_min_resolution(pdf, tmp_path, min_edge=2500, max_pixels=20_000_000)
        is None
    )


def test_ensure_min_resolution_returns_none_when_large_enough(tmp_path: Path) -> None:
    png = _write_png(tmp_path / "big.png", 2600, 1000)
    assert (
        ensure_min_resolution(png, tmp_path, min_edge=2500, max_pixels=20_000_000)
        is None
    )


def test_ensure_min_resolution_returns_none_when_disabled(tmp_path: Path) -> None:
    png = _write_png(tmp_path / "small.png", 800, 600)
    assert (
        ensure_min_resolution(png, tmp_path, min_edge=0, max_pixels=20_000_000) is None
    )


def test_ensure_min_resolution_upscales_small_image(tmp_path: Path) -> None:
    png = _write_png(tmp_path / "src" / "small.png", 1206, 1720)
    out = tmp_path / "out"
    result = ensure_min_resolution(png, out, min_edge=2500, max_pixels=20_000_000)
    assert result is not None
    assert result.exists()
    with Image.open(result) as img:
        assert max(img.width, img.height) >= 2500
        assert img.width == 1737 or img.height == 2500
    assert result.name == "small.png"


def test_ensure_min_resolution_caps_by_max_pixels(tmp_path: Path) -> None:
    png = _write_png(tmp_path / "src" / "small.png", 1000, 1000)
    out = tmp_path / "out"
    result = ensure_min_resolution(png, out, min_edge=4000, max_pixels=4_000_000)
    assert result is not None
    with Image.open(result) as img:
        assert img.width * img.height <= 4_000_000
        assert max(img.width, img.height) >= 1000


def test_ensure_max_pixel_count_scales_to_ninety_five_percent_budget(
    tmp_path: Path,
) -> None:
    png = _write_png(tmp_path / "src" / "large.png", 2000, 1000)
    out = tmp_path / "out"

    result = ensure_max_pixel_count(png, out, max_pixels=1_000_000)

    assert result is not None
    with Image.open(result) as img:
        assert img.width * img.height <= 950_000
        assert img.width * img.height >= 949_000


def test_ensure_max_pixel_count_skips_when_limit_is_zero(tmp_path: Path) -> None:
    png = _write_png(tmp_path / "src" / "large.png", 2000, 1000)

    assert ensure_max_pixel_count(png, tmp_path / "out", max_pixels=0) is None


def test_max_pixel_count_setting_zero_remains_unlimited() -> None:
    assert (
        external_tools._max_pixels_or_default(ToolConfig(audiveris_max_pixel_count="0"))
        == 0
    )


def test_upscale_by_factor_grows_dimensions(tmp_path: Path) -> None:
    png = _write_png(tmp_path / "src" / "small.png", 1000, 500)
    out = tmp_path / "out"
    result = upscale_by_factor(png, out, factor=2.0, max_pixels=20_000_000)
    with Image.open(result) as img:
        assert (img.width, img.height) == (2000, 1000)


def test_recognize_with_audiveris_preventive_upscale_passes_upscaled_path(
    monkeypatch, tmp_path: Path
) -> None:
    source = _write_png(tmp_path / "src" / "scan.png", 1206, 1720)
    output_dir = tmp_path / "omr"
    captured: list[str] = []

    def fake_run(args, cwd=None, env=None) -> CommandResult:
        captured.append(args[-1])
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "scan.musicxml").write_text("<score-partwise/>", encoding="utf-8")
        return CommandResult(args=args, stdout="", stderr="")

    monkeypatch.setattr(external_tools, "_run", fake_run)

    recognize_with_audiveris(
        source,
        output_dir,
        ToolConfig(audiveris_path="audiveris"),
    )

    assert len(captured) == 1
    passed_path = Path(captured[0])
    assert passed_path != source.resolve()
    assert passed_path.name == "scan.png"
    assert "_preprocess" in passed_path.parts
    with Image.open(passed_path) as img:
        assert max(img.width, img.height) >= 2500


def test_recognize_with_audiveris_caps_large_png_before_running(
    monkeypatch, tmp_path: Path
) -> None:
    source = _write_png(tmp_path / "src" / "large.png", 2000, 1000)
    output_dir = tmp_path / "omr"
    captured: list[str] = []

    def fake_run(args, cwd=None, env=None) -> CommandResult:
        captured.append(args[-1])
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "large.musicxml").write_text(
            "<score-partwise/>", encoding="utf-8"
        )
        return CommandResult(args=args, stdout="", stderr="")

    monkeypatch.setattr(external_tools, "_run", fake_run)

    recognize_with_audiveris(
        source,
        output_dir,
        ToolConfig(
            audiveris_path="audiveris",
            audiveris_max_pixel_count="1000000",
        ),
    )

    passed_path = Path(captured[0])
    assert passed_path != source.resolve()
    with Image.open(passed_path) as img:
        assert img.width * img.height <= 950_000


def test_recognize_with_audiveris_skips_upscale_when_disabled(
    monkeypatch, tmp_path: Path
) -> None:
    source = _write_png(tmp_path / "src" / "scan.png", 800, 600)
    output_dir = tmp_path / "omr"
    captured: list[str] = []

    def fake_run(args, cwd=None, env=None) -> CommandResult:
        captured.append(args[-1])
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "scan.musicxml").write_text("<score-partwise/>", encoding="utf-8")
        return CommandResult(args=args, stdout="", stderr="")

    monkeypatch.setattr(external_tools, "_run", fake_run)

    recognize_with_audiveris(
        source,
        output_dir,
        ToolConfig(audiveris_path="audiveris", audiveris_auto_upscale=False),
    )

    assert captured == [str(source.resolve())]


def test_recognize_with_audiveris_retries_after_low_interline(
    monkeypatch, tmp_path: Path
) -> None:
    source = _write_png(tmp_path / "src" / "scan.png", 2500, 1800)
    output_dir = tmp_path / "omr"
    attempts: list[str] = []
    call_count = {"n": 0}

    def fake_run(args, cwd=None, env=None) -> CommandResult:
        call_count["n"] += 1
        attempts.append(args[-1])
        if call_count["n"] == 1:
            raise ExternalToolError(
                "外部程序执行失败",
                stdout="With a too low interline value of 10 pixels",
                stderr="BUILD FAILED",
            )
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "scan.musicxml").write_text("<score-partwise/>", encoding="utf-8")
        return CommandResult(args=args, stdout="", stderr="")

    monkeypatch.setattr(external_tools, "_run", fake_run)

    recognize_with_audiveris(
        source,
        output_dir,
        ToolConfig(audiveris_path="audiveris"),
    )

    assert call_count["n"] == 2
    first_path = Path(attempts[0])
    second_path = Path(attempts[1])
    assert first_path == source.resolve()
    assert second_path != source.resolve()
    assert "_preprocess" in second_path.parts
    with Image.open(second_path) as img:
        assert max(img.width, img.height) > 2500


def test_recognize_with_audiveris_no_retry_when_interline_absent(
    monkeypatch, tmp_path: Path
) -> None:
    source = _write_png(tmp_path / "src" / "scan.png", 2500, 1800)
    output_dir = tmp_path / "omr"
    call_count = {"n": 0}

    def fake_run(args, cwd=None, env=None) -> CommandResult:
        call_count["n"] += 1
        raise ExternalToolError("外部程序执行失败", stdout="some other error")

    monkeypatch.setattr(external_tools, "_run", fake_run)

    raised = False
    try:
        recognize_with_audiveris(
            source,
            output_dir,
            ToolConfig(audiveris_path="audiveris"),
        )
    except ExternalToolError:
        raised = True

    assert raised
    assert call_count["n"] == 1
