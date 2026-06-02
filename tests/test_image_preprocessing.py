from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from score_trans.models.settings.config import ToolConfig
from score_trans.services.recognize import external_tools
from score_trans.services.recognize.external_tools import CommandResult, recognize_with_audiveris
from score_trans.services.recognize.image_preprocessing import ImagePreprocessOptions, prepare_omr_input, preprocess_score_image


def _sample_score_image(path: Path, *, size: tuple[int, int] = (120, 180)) -> None:
    image = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(image)
    for system_y in (52, 112):
        for offset in range(0, 20, 4):
            draw.line((28, system_y + offset, size[0] - 28, system_y + offset), fill=(0, 0, 0), width=1)
        draw.ellipse((54, system_y + 7, 61, system_y + 14), fill=(0, 0, 0))
    image.save(path)


def test_preprocess_score_image_crops_and_upscales_for_omr(tmp_path: Path) -> None:
    source = tmp_path / "page.png"
    target = tmp_path / "page_omr.png"
    _sample_score_image(source)

    preprocess_score_image(source, target, ImagePreprocessOptions(target_long_edge=360))

    with Image.open(source) as original, Image.open(target) as processed:
        assert processed.size[0] > original.size[0]
        assert max(processed.size) == 360
        assert processed.info.get("dpi") is not None
        assert min(processed.convert("L").getextrema()) < 20


def test_prepare_omr_input_skips_non_images(tmp_path: Path) -> None:
    source = tmp_path / "score.musicxml"
    source.write_text("<score-partwise/>", encoding="utf-8")

    prepared = prepare_omr_input(source, tmp_path / "out", ToolConfig())

    assert prepared == source


def test_recognize_with_audiveris_uses_preprocessed_image(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "scan.png"
    output_dir = tmp_path / "omr"
    _sample_score_image(source)
    calls: list[list[str]] = []

    def fake_run(args, cwd=None, env=None) -> CommandResult:
        calls.append(args)
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "scan_omr.mxl").write_text("<score-partwise/>", encoding="utf-8")
        return CommandResult(args=args, stdout="", stderr="")

    monkeypatch.setattr(external_tools, "_run", fake_run)

    result = recognize_with_audiveris(
        source,
        output_dir,
        ToolConfig(audiveris_path="audiveris", omr_preprocess=True, omr_preprocess_long_edge=360),
    )

    assert result.name == "scan_omr.mxl"
    assert calls
    assert "_preprocessed" in calls[0][-1]
    assert Path(calls[0][-1]).exists()
