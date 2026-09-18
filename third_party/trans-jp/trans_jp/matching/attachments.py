from __future__ import annotations
from ..models.contracts import RowSegment
from ..models.geometry import Box, TokenGeometry
from ..models.notation import Notation, Pitch
from ..models.raster import RowAnalysis
from .geometry import add_shape, add_line


def attach_pitch(
    row: RowSegment,
    geometry: TokenGeometry,
    pitch: Pitch,
    body: Box,
    analysis: RowAnalysis,
) -> None:
    h = body.height
    if pitch.accidental:
        options = [
            c.bounds
            for c in analysis.components
            if body.x - h * 1.2 < c.bounds.x < body.x
            and c.bounds.right < body.x + 1
            and body.y - h * 0.8 < c.bounds.y < body.cy
            and h * 0.3 < c.bounds.height < h * 1.5
        ]
        if options:
            add_shape(
                row,
                geometry,
                "glyph",
                min(options, key=lambda b: body.x - b.right),
                pitch.accidental,
            )
        else:
            geometry.warnings.append("升降号未定位")
    if pitch.octave:
        dots = [
            c.bounds
            for c in analysis.components
            if max(c.bounds.width, c.bounds.height) < h * 0.36
            and 0.4 < c.bounds.width / max(c.bounds.height, 1) < 2.2
            and abs(c.bounds.cx - body.cx) < h * 0.35
            and (
                body.y - h * 1.6 < c.bounds.cy < body.y
                if pitch.octave > 0
                else body.bottom < c.bounds.cy < body.bottom + h * 1.6
            )
        ]
        dots.sort(key=lambda b: abs(b.cy - body.cy))
        for dot in dots[: abs(pitch.octave)]:
            add_shape(row, geometry, "dot", dot, "octave")
        if len(dots) < abs(pitch.octave):
            geometry.warnings.append("部分八度点未定位")


def attach_rhythm(
    row: RowSegment,
    geometry: TokenGeometry,
    note: Notation,
    body: Box,
    analysis: RowAnalysis,
    left: float,
    right: float,
    next_body: float,
) -> None:
    h = body.height
    lines = sorted(
        [
            line
            for line in analysis.horizontal
            if line.bounds.x <= body.cx <= line.bounds.right
            and body.bottom - 1 <= line.bounds.cy < body.bottom + h * 0.9
        ],
        key=lambda line_item: line_item.bounds.y,
    )
    for line in lines[: note.underlines]:
        b = line.bounds
        x = max(b.x, left)
        end = min(b.right, right)
        add_line(
            row, geometry, line, "underline", Box(x, b.y, max(0, end - x), b.height)
        )
    if len(lines) < note.underlines:
        geometry.warnings.append("部分减时线未定位")
    extensions = sorted(
        [
            line
            for line in analysis.horizontal
            if body.right < line.bounds.x < next_body
            and line.bounds.right <= next_body
            and abs(line.bounds.cy - body.cy) < h * 0.3
        ],
        key=lambda line_item: line_item.bounds.x,
    )
    for line in extensions[: note.extensions]:
        add_line(row, geometry, line, "extension")
    if len(extensions) < note.extensions:
        geometry.warnings.append("部分延长线未定位")
    dot_left = (
        extensions[note.extensions - 1].bounds.right
        if note.extensions and len(extensions) >= note.extensions
        else body.right
    )
    dots = sorted(
        [
            c.bounds
            for c in analysis.components
            if dot_left < c.bounds.cx < min(next_body, dot_left + h)
            and abs(c.bounds.cy - body.cy) < h * 0.4
            and max(c.bounds.width, c.bounds.height) < h * 0.35
        ],
        key=lambda b: b.x,
    )
    for dot in dots[: note.dots]:
        add_shape(row, geometry, "dot", dot, "augmentation")
    if len(dots) < note.dots:
        geometry.warnings.append("部分附点未定位")
