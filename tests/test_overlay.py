from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from score_trans.services.overlay.omr_parser import OmrParser, SheetModel
from score_trans.services.overlay.overlay_service import OverlayService
from score_trans.services.overlay.svg_generator import SvgGenerator


OMR_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "二胡"
    / "微信图片_20260628233854_154_922.omr"
)


@pytest.fixture
def sheets() -> list[SheetModel]:
    return OmrParser().parse(OMR_FIXTURE)


def test_parser_finds_all_sheets(sheets: list[SheetModel]) -> None:
    assert len(sheets) == 2


def test_parser_reads_image_dimensions(sheets: list[SheetModel]) -> None:
    sheet = sheets[0]
    assert sheet.width == 2396
    assert sheet.height == 3650


def test_parser_extracts_inters(sheets: list[SheetModel]) -> None:
    sheet = sheets[0]
    tags = {inter.tag for inter in sheet.inters}
    assert "head" in tags
    assert "clef" in tags
    assert "stem" in tags
    assert "beam" in tags
    assert "slur" in tags
    assert "barline" in tags


def test_parser_skips_container_inters(sheets: list[SheetModel]) -> None:
    sheet = sheets[0]
    tags = {inter.tag for inter in sheet.inters}
    assert "head-chord" not in tags
    assert "rest-chord" not in tags
    assert "beam-group" not in tags
    assert "staff-barline" not in tags


def test_parser_reads_stem_median(sheets: list[SheetModel]) -> None:
    sheet = sheets[0]
    stems = [inter for inter in sheet.inters if inter.tag == "stem"]
    assert len(stems) > 0
    stem = stems[0]
    assert stem.median is not None
    assert len(stem.median) == 4
    assert stem.width is not None
    assert stem.width > 0


def test_parser_reads_slur_curve(sheets: list[SheetModel]) -> None:
    sheet = sheets[0]
    slurs = [inter for inter in sheet.inters if inter.tag == "slur"]
    assert len(slurs) > 0
    slur = slurs[0]
    assert slur.curve is not None
    assert len(slur.curve) == 8


def test_parser_best_grade(sheets: list[SheetModel]) -> None:
    sheet = sheets[0]
    for inter in sheet.inters:
        assert 0.0 <= inter.grade <= 1.0


def test_svg_generator_produces_valid_xml(sheets: list[SheetModel]) -> None:
    svg = SvgGenerator().generate(sheets[0])
    root = ET.fromstring(svg)
    assert root.tag.endswith("svg")


def test_svg_generator_has_correct_viewbox(sheets: list[SheetModel]) -> None:
    svg = SvgGenerator().generate(sheets[0])
    root = ET.fromstring(svg)
    viewbox = root.get("viewBox", "")
    parts = viewbox.split()
    assert len(parts) == 4
    assert parts[2] == "2396"
    assert parts[3] == "3650"


def test_svg_generator_contains_rects_and_geometric_elements(
    sheets: list[SheetModel],
) -> None:
    svg = SvgGenerator().generate(sheets[0])
    assert "<rect" in svg
    assert "<line" in svg
    assert "<polygon" in svg
    assert "<path" in svg


def test_overlay_service_returns_empty_for_missing_omr(tmp_path: Path) -> None:
    service = OverlayService()
    result = service.generate_overlay_svgs(tmp_path)
    assert result == []


def test_overlay_service_generates_svg_files(tmp_path: Path) -> None:
    import shutil

    omr_copy = tmp_path / "test.omr"
    shutil.copy2(OMR_FIXTURE, omr_copy)
    service = OverlayService()
    result = service.generate_overlay_svgs(tmp_path)
    assert len(result) == 2
    for path in result:
        assert path.exists()
        assert path.suffix == ".svg"
        content = path.read_text(encoding="utf-8")
        assert "<svg" in content
