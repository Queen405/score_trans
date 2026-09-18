from __future__ import annotations
from pathlib import Path
from trans_jp.models.geometry import Box, Primitive, TokenGeometry
from trans_jp.schemas import RecognizedToken, RowResult, RowSegment
from trans_jp.source_map_builder import build_source_map


def _row(box: Box, *, index=0, confidence=0.9):
    token = RecognizedToken(0, "1", 0.1, 0.1, "note")
    token.geometry = TokenGeometry("matched", primitives=[Primitive("glyph", box, "1")])
    return RowResult(
        RowSegment(index, 0, 50, Path("unused.png"), 1200, 50),
        "notation",
        "1",
        [token],
        confidence=confidence,
    )


def test_source_map_structure():
    source_map = build_source_map([_row(Box(60, 100, 12, 24))], 1200, 800)
    sheet = source_map["sheets"][0]
    assert source_map["version"] == 1 and sheet["overlay_file"] == "overlay.svg"
    assert len(sheet["elements"]) == 1


def test_element_bounds_from_geometry():
    element = build_source_map([_row(Box(60, 100, 12, 24))], 1200, 800)["sheets"][0][
        "elements"
    ][0]
    assert element["bounds"] == {"x": 60, "y": 100, "width": 12, "height": 24}


def test_hit_path_rectangle():
    element = build_source_map([_row(Box(60, 100, 12, 24))], 1200, 800)["sheets"][0][
        "elements"
    ][0]
    assert element["hit_path"] == "M60.0,100.0 L72.0,100.0 L72.0,124.0 L60.0,124.0 Z"


def test_source_id_and_shape():
    row = _row(Box(60, 100, 12, 24), index=2)
    row.tokens[0].role = "rest"
    element = build_source_map([row], 1200, 800)["sheets"][0]["elements"][0]
    assert element["source_id"] == "s0:r2:t0" and element["shape"] == "REST"


def test_grade_defaults_when_no_confidence():
    assert (
        build_source_map([_row(Box(60, 100, 12, 24), confidence=None)], 1200, 800)[
            "sheets"
        ][0]["elements"][0]["grade"]
        == 0.5
    )


def test_out_of_bounds_clamped():
    element = build_source_map([_row(Box(1195, 795, 20, 20))], 1200, 800)["sheets"][0][
        "elements"
    ][0]
    assert element["bounds"]["width"] == 5 and element["bounds"]["height"] == 5


def test_hit_path_separates_primitives():
    row = _row(Box(60, 100, 12, 24))
    row.tokens[0].geometry.primitives.append(
        Primitive("line", Box(160, 111, 12, 1), "extension")
    )
    element = build_source_map([row], 1200, 800)["sheets"][0]["elements"][0]
    assert element["hit_path"].count("M") == 2


def test_unlocated_token_is_omitted():
    token = RecognizedToken(0, "1", 0.05, 0.04, "note")
    row = RowResult(
        RowSegment(0, 100, 150, Path("x"), 1200, 50), "notation", "1", [token]
    )
    assert not build_source_map([row], 1200, 800)["sheets"][0]["elements"]
