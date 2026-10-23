from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

import pytest

from score_trans.services.overlay.omr_parser import (
    OmrParser,
    SheetModel,
    _parse_inter,
)
from score_trans.services.overlay.overlay_service import OverlayService
from score_trans.services.overlay.svg_generator import SvgGenerator, _parallelogram


OMR_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "二胡"
    / "微信图片_20260628233854_154_922.omr"
)


@pytest.fixture
def sheets() -> list[SheetModel]:
    if not OMR_FIXTURE.is_file():
        pytest.skip("OMR fixture not available (examples/ excluded from VCS)")
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


def test_parser_prefers_contextual_grade_when_present() -> None:
    element = ET.fromstring(
        '<head id="1" grade="0.9" ctx-grade="0.2">'
        '<bounds x="1" y="2" w="3" h="4"/>'
        "</head>"
    )

    inter = _parse_inter(element)

    assert inter is not None
    assert inter.grade == pytest.approx(0.2)


def test_parser_sorts_sheet_entries_numerically(tmp_path: Path) -> None:
    omr_path = tmp_path / "numeric-order.omr"
    sheet_xml = (
        '<sheet><picture width="10" height="20"/>'
        '<inters><head id="1"><bounds x="1" y="2" w="3" h="4"/></head></inters>'
        "</sheet>"
    )
    with ZipFile(omr_path, "w") as archive:
        archive.writestr("book/sheet#10/sheet#10.xml", sheet_xml)
        archive.writestr("book/sheet#2/sheet#2.xml", sheet_xml)

    parsed = OmrParser().parse(omr_path)

    assert [sheet.index for sheet in parsed] == [2, 10]


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


def test_svg_generator_contains_symbols_and_geometric_elements(
    sheets: list[SheetModel],
) -> None:
    svg = SvgGenerator().generate(sheets[0])
    assert '<text class="symbol cat-note"' in svg
    assert "&#xE0A4;" in svg
    assert "<line" in svg
    assert "<polygon" in svg
    assert "<path" in svg


def test_beam_uses_audiveris_vertical_sided_parallelogram() -> None:
    polygon = _parallelogram((10.0, 10.0, 20.0, 14.0), 4.0, "#008844", 1.0)

    assert 'points="10.0,8.0 20.0,12.0 20.0,16.0 10.0,12.0"' in polygon


def test_overlay_service_returns_empty_for_missing_omr(tmp_path: Path) -> None:
    service = OverlayService()
    result = service.generate_overlay_svgs(tmp_path)
    assert result == []


def test_native_overlay_accepts_version_two_source_map(tmp_path: Path) -> None:
    """Candidate metadata must not disable the native recognition overlay."""
    import base64
    import json

    # A 1x1 transparent PNG is enough to exercise the sidecar contract.
    (tmp_path / "overlay.png").write_bytes(
        base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/"
            "eU8AAAAASUVORK5CYII="
        )
    )
    (tmp_path / "score-link-map.json").write_text(
        json.dumps(
            {
                "version": 2,
                "sheets": [
                    {
                        "sheet_index": 1,
                        "width": 1,
                        "height": 1,
                        "overlay_file": "overlay.png",
                        "elements": [],
                        "glyphs": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    overlay, source_map = OverlayService().find_native_overlay(tmp_path)

    assert overlay == tmp_path / "overlay.png"
    assert source_map == tmp_path / "score-link-map.json"


def test_overlay_service_generates_svg_files(tmp_path: Path) -> None:
    import shutil

    if not OMR_FIXTURE.is_file():
        pytest.skip("OMR fixture not available (examples/ excluded from VCS)")
    omr_copy = tmp_path / "test.omr"
    shutil.copy2(OMR_FIXTURE, omr_copy)
    service = OverlayService()
    result = service.generate_overlay_svgs(tmp_path)
    assert len(result) == 1
    assert result[0].name == "overlay_sheet1.svg"
    for path in result:
        assert path.exists()
        assert path.suffix == ".svg"
        content = path.read_text(encoding="utf-8")
        assert "<svg" in content
