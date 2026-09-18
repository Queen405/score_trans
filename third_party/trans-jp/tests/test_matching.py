from __future__ import annotations

from pathlib import Path
import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont
from trans_jp.models.contracts import RowSegment, RowResult, RecognizedToken
from trans_jp.models.geometry import Box, Transform
from trans_jp.preprocess.image import otsu_binarize
from trans_jp.structure.page_analyzer import analyze_row
from trans_jp.matching.token_matcher import match_row
from trans_jp.overlay_generator import generate_overlay_svg
from trans_jp.source_map_builder import build_source_map
from trans_jp.symbols.notation_parser import parse_notation


def canvas():
    image = Image.new("RGB", (800, 240), "white")
    return image, ImageDraw.Draw(image), ImageFont.load_default(size=32)


def digit(draw, font, x, y, text="3"):
    draw.text((x, y), text, font=font, fill="black")
    a, b, c, d = draw.textbbox((x, y), text, font=font)
    return Box(a, b, c - a, d - b)


def token(index, text, box, role="note"):
    return RecognizedToken(index, text, box.x / 800, box.width / 800, role)


def match(image, tokens, transform=Transform()):
    binary = otsu_binarize(np.array(image.convert("L")))
    row = RowSegment(
        0,
        0,
        image.height,
        Path("unused.png"),
        image.width,
        image.height,
        transform=transform,
    )
    raw = RowResult(row, "notation", " ".join(t.text for t in tokens), tokens)
    result = match_row(raw, binary, analyze_row(binary))
    assert all(t.geometry is None for t in raw.tokens), (
        "Recognition inputs must stay untouched"
    )
    return result


@pytest.mark.parametrize(
    ("text", "lines", "octave", "extensions"),
    [
        ("q3'", 1, 1, 0),
        ("s5,.", 2, -1, 0),
        ("dd1", 4, 0, 0),
        ("h1.", 0, 0, 1),
        ("w0", 0, 0, 3),
        ("3---", 0, 0, 3),
    ],
)
def test_notation(text, lines, octave, extensions):
    note = parse_notation(text)
    assert (note.underlines, note.pitches[0].octave, note.extensions) == (
        lines,
        octave,
        extensions,
    )


@pytest.mark.parametrize("text", ["12", "q.3", "$123$", "^f", "[1,3,5]", "title=123"])
def test_unsupported_is_not_misread_as_digit(text):
    assert parse_notation(text) is None


def test_omission_does_not_stretch_later_notes():
    image, draw, font = canvas()
    boxes = [digit(draw, font, x, 70) for x in [60, 160, 260, 360, 460]]
    result = match(image, [token(i, "3", b) for i, b in enumerate(boxes[1:])])
    for tok, expected in zip(result.tokens, boxes[1:], strict=True):
        assert abs(tok.geometry.bodies[0].cx - expected.cx) < 3
        assert tok.geometry.bodies[0].height < 30


def test_octaves_dots_and_shared_underlines():
    image, draw, font = canvas()
    a, b = digit(draw, font, 60, 70), digit(draw, font, 160, 70, "5")
    draw.ellipse((a.cx - 2, a.y - 10, a.cx + 2, a.y - 6), fill="black")
    draw.ellipse((b.cx - 2, b.bottom + 15, b.cx + 2, b.bottom + 19), fill="black")
    draw.ellipse((b.right + 7, b.cy - 2, b.right + 11, b.cy + 2), fill="black")
    for delta in [4, 10]:
        draw.line(
            (a.x, a.bottom + delta, b.right, a.bottom + delta), fill="black", width=2
        )
    result = match(image, [token(0, "s3'", a), token(1, "s5,.", b)])
    assert not result.warnings, result.warnings
    for tok in result.tokens:
        assert len([p for p in tok.geometry.primitives if p.value == "underline"]) == 2
        assert len([p for p in tok.geometry.primitives if p.value == "octave"]) == 1
    line_a = next(
        p for p in result.tokens[0].geometry.primitives if p.value == "underline"
    )
    line_b = next(
        p for p in result.tokens[1].geometry.primitives if p.value == "underline"
    )
    assert line_a.bounds == line_b.bounds
    assert line_a.hit_bounds.right <= line_b.hit_bounds.x
    svg = generate_overlay_svg([result], *image.size)
    assert "<text" not in svg and "<rect" not in svg
    assert svg.count('data-mark="underline"') == 2


def test_touching_line_does_not_fuse_two_digits():
    image, draw, font = canvas()
    a, b = digit(draw, font, 60, 70), digit(draw, font, 160, 70, "5")
    draw.line((a.x, a.bottom - 1, b.right, a.bottom - 1), fill="black", width=2)
    result = match(image, [token(0, "q3", a), token(1, "q5", b)])
    for tok, expected in zip(result.tokens, [a, b], strict=True):
        assert tok.geometry.bodies
        assert abs(tok.geometry.bodies[0].cx - expected.cx) < 3
        assert any(p.value == "underline" for p in tok.geometry.primitives)


def test_chord_only_baseline():
    image, draw, font = canvas()
    a = digit(draw, font, 60, 30, "5")
    digit(draw, font, 60, 65, "3")
    b = digit(draw, font, 60, 100, "1")
    result = match(image, [token(0, "[1+3+5]", a.union(b), "chord")])
    assert not result.warnings, result.warnings
    assert [
        p.value for p in result.tokens[0].geometry.primitives if p.kind == "glyph"
    ] == ["5", "3", "1"]


def test_multivoice_resets_per_measure():
    image, draw, font = canvas()
    boxes = [
        digit(draw, font, x, y) for x, y in [(60, 30), (60, 120), (300, 30), (300, 120)]
    ]
    draw.line((220, 30, 220, 162), fill="black", width=2)
    tokens = [
        token(0, "3", boxes[0]),
        RecognizedToken(1, "&", 0, 0, "other"),
        token(2, "3", boxes[1]),
        RecognizedToken(3, "|", 220 / 800, 2 / 800, "barline"),
        token(4, "3", boxes[2]),
        RecognizedToken(5, "&", 0, 0, "other"),
        token(6, "3", boxes[3]),
    ]
    result = match(image, tokens)
    assert [result.tokens[i].geometry.voice for i in [0, 2, 4, 6]] == [0, 1, 0, 1]
    for i, box in zip([0, 2, 4, 6], boxes, strict=True):
        assert abs(result.tokens[i].geometry.bodies[0].cy - box.cy) < 3


def test_missing_second_voice_and_empty_image_are_nonfatal():
    image, draw, font = canvas()
    a = digit(draw, font, 60, 70)
    result = match(
        image,
        [token(0, "3", a), RecognizedToken(1, "&", 0, 0, "other"), token(2, "5", a)],
    )
    assert result.tokens[2].geometry.status == "unmatched"
    assert len(build_source_map([result], *image.size)["sheets"][0]["elements"]) == 1
    blank = Image.new("RGB", image.size, "white")
    result = match(blank, [token(0, "3", a)])
    assert not build_source_map([result], *image.size)["sheets"][0]["elements"]
    assert "<path" not in generate_overlay_svg([result], *image.size)


def test_rest_and_extensions():
    image, draw, font = canvas()
    a = digit(draw, font, 60, 70, "0")
    b = digit(draw, font, 400, 70)
    for x in [130, 210, 290]:
        draw.line((x, a.cy, x + 22, a.cy), fill="black", width=2)
    result = match(
        image, [token(0, "w0", Box(a.x, a.y, 255, a.height), "rest"), token(1, "3", b)]
    )
    assert not result.warnings, result.warnings
    assert (
        len([p for p in result.tokens[0].geometry.primitives if p.value == "extension"])
        == 3
    )


@pytest.mark.parametrize("tie", [False, True])
def test_same_row_arc(tie):
    image, draw, font = canvas()
    a = digit(draw, font, 60, 80)
    b = digit(draw, font, 160, 80, "3" if tie else "5")
    draw.arc((a.cx, a.y - 22, b.cx, a.y + 12), 180, 360, fill="black", width=2)
    texts = ["3~", "~3"] if tie else ["(3", "5)"]
    result = match(
        image,
        [
            token(i, text, box)
            for i, (text, box) in enumerate(zip(texts, [a, b], strict=True))
        ],
    )
    assert not result.warnings, result.warnings
    assert (
        len(
            [
                p
                for t in result.tokens
                for p in t.geometry.primitives
                if p.kind == "curve"
            ]
        )
        == 1
    )
