from __future__ import annotations
from pathlib import Path
from xml.etree import ElementTree as ET
from trans_jp.models.geometry import Box, Primitive, TokenGeometry
from trans_jp.overlay_generator import ROLE_COLORS, generate_overlay_svg
from trans_jp.schemas import RecognizedToken, RowResult, RowSegment

NS = {"svg": "http://www.w3.org/2000/svg"}


def _rows():
    tokens = [
        RecognizedToken(0, "1", 0.05, 0.04, "note"),
        RecognizedToken(1, "2", 0.12, 0.04, "note"),
        RecognizedToken(2, "|", 0.33, 0.02, "barline"),
    ]
    for token, box in zip(
        tokens,
        [Box(60, 100, 12, 24), Box(144, 100, 12, 24), Box(396, 95, 1, 35)],
        strict=True,
    ):
        token.geometry = TokenGeometry(
            "matched",
            primitives=[
                Primitive(
                    "line", box, "barline", ((box.cx, box.y), (box.cx, box.bottom))
                )
                if token.role == "barline"
                else Primitive("glyph", box, token.text)
            ],
        )
    return [
        RowResult(
            RowSegment(0, 90, 140, Path("x"), 1200, 50), "notation", "1 2 |", tokens
        )
    ]


def test_overlay_is_valid_and_uses_paths():
    root = ET.fromstring(generate_overlay_svg(_rows(), 1200, 800))
    assert root.attrib["viewBox"] == "0 0 1200 800"
    assert (
        len(root.findall("svg:g", NS)) == 3
        and len(root.findall(".//svg:path", NS)) == 3
    )
    assert not root.findall(".//svg:text", NS) and not root.findall(".//svg:rect", NS)


def test_overlay_colors_by_role():
    groups = ET.fromstring(generate_overlay_svg(_rows(), 1200, 800)).findall(
        "svg:g", NS
    )
    assert groups[0].attrib["data-status"] == "matched"
    assert ROLE_COLORS["note"] in generate_overlay_svg(_rows(), 1200, 800)


def test_unknown_or_unlocated_tokens_do_not_render():
    rows = _rows()
    rows[0].tokens[0].geometry = None
    rows[0].tokens[0].role = "weird"
    svg = generate_overlay_svg(rows, 1200, 800)
    assert "s0:r0:t0" not in svg
    assert "<text" not in svg


def test_rasterized_paths_and_lines_use_explicit_role_color():
    import fitz

    rows = _rows()
    rows[0].tokens = rows[0].tokens[:1]
    rows[0].tokens[0].geometry.primitives.append(
        Primitive("line", Box(60, 130, 12, 2), "underline", ((60, 131), (72, 131)), 2)
    )
    svg = generate_overlay_svg(rows, 1200, 800)
    with fitz.open("svg", svg.encode()) as document:
        page = document[0]
        pix = page.get_pixmap(
            matrix=fitz.Matrix(1200 / page.rect.width, 800 / page.rect.height),
            alpha=True,
        )
        assert pix.pixel(65, 130) == (0, 170, 68, 255)
        assert pix.pixel(0, 0) == (0, 0, 0, 0)


def test_glyph_affine_maps_its_ink_corners_to_original_image():
    import re
    import pytest
    from trans_jp.io.assets import glyph_assets
    from trans_jp.rendering.primitive_renderer import render_primitive

    corners = ((60.0, 100.0), (72.0, 103.0), (60.0, 124.0))
    p = Primitive("glyph", Box(60, 100, 12, 27), "1", corners)
    svg = render_primitive(p, "#00aa44", glyph_assets())
    matrix = re.search(r"matrix\(([^)]+)\)", svg).group(1)
    a, b, c, d, e, f = map(float, matrix.split())
    x0, y0, x1, y1 = glyph_assets()["1"]["bounds"]
    for (x, y), expected in zip([(x0, y1), (x1, y1), (x0, y0)], corners, strict=True):
        assert (a * x + c * y + e, b * x + d * y + f) == pytest.approx(
            expected, abs=0.001
        )
