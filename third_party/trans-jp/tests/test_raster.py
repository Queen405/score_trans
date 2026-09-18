from __future__ import annotations

import numpy as np
import pytest
from PIL import Image, ImageDraw
from trans_jp.raster.runs import scan_runs
from trans_jp.raster.sections import join_sections
from trans_jp.raster.filaments import detect_filaments, erase_filaments
from trans_jp.raster.projections import barline_candidates
from trans_jp.models.geometry import Curve
from trans_jp.models.raster import RowGeometry


def test_runs_and_sections_preserve_area_and_orientation():
    pixels = np.full((40, 60), 255, np.uint8)
    pixels[5:15, 10:30] = 0
    for direction in ["horizontal", "vertical"]:
        sections = join_sections(scan_runs(pixels, direction), direction)
        assert len(sections) == 1
        assert sections[0].area == 200
        assert (
            sections[0].bounds.x,
            sections[0].bounds.y,
            sections[0].bounds.width,
            sections[0].bounds.height,
        ) == (10, 5, 20, 10)


@pytest.mark.parametrize("vertical", [False, True])
@pytest.mark.parametrize("rise", [0, 5, -5])
def test_sloped_broken_filament_keeps_endpoints(vertical, rise):
    image = Image.new("L", (240, 100), 255)
    draw = ImageDraw.Draw(image)
    draw.line((20, 40, 200, 40 + rise), fill=0, width=2)
    draw.rectangle((98, 0, 102, 99), fill=255)
    binary = np.array(image)
    if vertical:
        binary = binary.T
    lines = detect_filaments(binary, "vertical" if vertical else "horizontal", 24)
    longest = max(
        lines, key=lambda line: line.bounds.height if vertical else line.bounds.width
    )
    a, b = longest.points
    if vertical:
        a, b = a[::-1], b[::-1]
    assert abs(a[0] - 20) <= 2 and abs(b[0] - 201) <= 2
    assert abs(a[1] - 40) <= 2 and abs(b[1] - (40 + rise)) <= 2
    assert longest.support > 0.9


def test_large_gap_does_not_merge_independent_underlines():
    pixels = np.full((100, 240), 255, np.uint8)
    pixels[40:42, 20:80] = 0
    pixels[40:42, 120:200] = 0
    lines = detect_filaments(pixels, "horizontal", 24)
    assert len(lines) == 2


def test_parallel_lines_remain_separate():
    pixels = np.full((100, 240), 255, np.uint8)
    for y in [40, 48, 56, 64]:
        pixels[y : y + 2, 20:200] = 0
    lines = detect_filaments(pixels, "horizontal", 24)
    assert len(lines) == 4


def test_vertical_projection_rejects_a_short_digit_stroke():
    pixels = np.full((100, 240), 255, np.uint8)
    pixels[20:70, 60:62] = 0
    pixels[38:58, 120:122] = 0
    band = RowGeometry(
        Curve(((0, 25), (240, 25))),
        Curve(((0, 65), (240, 65))),
        Curve(((0, 65), (240, 65))),
        40,
        (),
    )
    lines = detect_filaments(pixels, "vertical", 24)
    bars = barline_candidates(pixels, band, lines)
    assert len(bars) == 1 and abs(bars[0].bounds.cx - 61) < 1


def test_erase_follows_stroke_not_enclosing_rectangle():
    image = Image.new("L", (240, 100), 255)
    draw = ImageDraw.Draw(image)
    draw.line((20, 40, 200, 50), fill=0, width=2)
    draw.rectangle((110, 40, 114, 43), fill=0)
    pixels = np.array(image)
    lines = detect_filaments(pixels, "horizontal", 24)
    cleaned = erase_filaments(pixels, lines, 50)
    assert cleaned[41, 112] == 0
    assert cleaned[45, 110] == 255
