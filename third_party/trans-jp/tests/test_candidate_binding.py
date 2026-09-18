from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from trans_jp.models.contracts import RecognizedToken, RowResult, RowSegment
from trans_jp.structure.page_analyzer import analyze_row
from trans_jp.structure.candidates import build_registry
from trans_jp.preprocess.image import otsu_binarize
from trans_jp.matching.token_matcher import match_row


def example():
    image = Image.new("RGB", (500, 160), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=32)
    for x, digit in [(50, "1"), (150, "3"), (250, "5")]:
        draw.text((x, 60), digit, font=font, fill="black")
    draw.line((350, 55, 350, 100), fill="black", width=2)
    binary = otsu_binarize(np.asarray(image.convert("L")))
    analysis = analyze_row(binary)
    registry = build_registry(binary, analysis, 0)
    digits = sorted(
        [c for c in registry.candidates if c.kind == "digit" and 40 < c.bounds.x < 300],
        key=lambda c: c.bounds.x,
    )
    assert len(digits) == 3
    tokens = [
        RecognizedToken(i, text, None, None, "note", candidate_ids=(c.candidate_id,))
        for i, (text, c) in enumerate(zip(["1", "3", "5"], digits))
    ]
    row = RowSegment(0, 0, 160, Path("unused.png"), 500, 160)
    result = RowResult(
        row, "notation", "1 3 5", tokens, schema_version=2, registry=registry
    )
    return binary, analysis, result, digits


def test_ids_bind_without_model_coordinates():
    binary, analysis, raw, digits = example()
    result = match_row(raw, binary, analysis)
    assert all(t.geometry is None for t in raw.tokens)
    assert [t.geometry.bodies[0] for t in result.tokens] == [c.bounds for c in digits]
    assert all(t.geometry.status == "matched" for t in result.tokens)


def test_invalid_duplicate_and_cross_row_ids_never_draw():
    binary, analysis, raw, digits = example()
    raw.tokens[1].candidate_ids = raw.tokens[0].candidate_ids
    raw.tokens[2].candidate_ids = ("r9999:c0000",)
    result = match_row(raw, binary, analysis)
    assert all(not t.geometry.primitives for t in result.tokens)
    assert all(t.geometry.warnings for t in result.tokens)


def test_omission_does_not_shift_following_bindings():
    binary, analysis, raw, digits = example()
    raw.tokens = raw.tokens[1:]
    result = match_row(raw, binary, analysis)
    assert [t.geometry.bodies[0] for t in result.tokens] == [
        c.bounds for c in digits[1:]
    ]


def test_reverse_order_rejects_both_conflicting_tokens():
    binary, analysis, raw, digits = example()
    raw.tokens[0].candidate_ids, raw.tokens[1].candidate_ids = (
        raw.tokens[1].candidate_ids,
        raw.tokens[0].candidate_ids,
    )
    result = match_row(raw, binary, analysis)
    assert not result.tokens[0].geometry.primitives
    assert not result.tokens[1].geometry.primitives
    assert result.tokens[2].geometry.bodies == [digits[2].bounds]


def test_v2_never_falls_back_to_xy():
    binary, analysis, raw, digits = example()
    raw.tokens[0] = replace(
        raw.tokens[0],
        candidate_ids=(),
        x=digits[0].bounds.x / 500,
        w=digits[0].bounds.width / 500,
    )
    result = match_row(raw, binary, analysis)
    assert not result.tokens[0].geometry.primitives


def test_registry_ids_and_digest_are_deterministic():
    binary, analysis, raw, _ = example()
    assert build_registry(binary, analysis, 0) == raw.registry
    assert build_registry(binary, analysis, 1).digest != raw.registry.digest


def test_octave_dot_band_is_not_a_digit_voice():
    image = Image.new("RGB", (500, 150), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=40)
    for x in [60, 150, 240]:
        draw.text((x, 70), "1", font=font, fill="black")
        draw.ellipse((x + 9, 60, x + 15, 66), fill="black")
    binary = otsu_binarize(np.asarray(image.convert("L")))
    analysis = analyze_row(binary)
    registry = build_registry(binary, analysis, 0)
    assert len([c for c in registry.candidates if c.kind == "digit"]) == 3
    assert any(c.bounds.height < 10 for c in analysis.components)


def test_conflicting_ink_candidates_reject_all_owners():
    binary, analysis, raw, digits = example()
    duplicate = replace(
        digits[0], candidate_id="r0000:c9999", conflicts=(digits[0].candidate_id,)
    )
    candidates = tuple(
        replace(c, conflicts=(duplicate.candidate_id,)) if c == digits[0] else c
        for c in raw.registry.candidates
    )
    raw.registry = replace(raw.registry, candidates=(*candidates, duplicate))
    raw.tokens[1].candidate_ids = (duplicate.candidate_id,)
    result = match_row(raw, binary, analysis)
    assert not result.tokens[0].geometry.primitives
    assert not result.tokens[1].geometry.primitives


def test_registered_chord_keeps_vertical_order_and_original_transform():
    from trans_jp.models.geometry import Transform

    image = Image.new("RGB", (500, 200), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=28)
    for y, text in [(20, "5"), (70, "3"), (120, "1")]:
        draw.text((60, y), text, font=font, fill="black")
    binary = otsu_binarize(np.asarray(image.convert("L")))
    analysis = analyze_row(binary)
    registry = build_registry(binary, analysis, 0)
    digits = sorted(
        [c for c in registry.candidates if c.kind == "digit"], key=lambda c: c.bounds.y
    )
    transform = Transform(2, 2.1, 0.03, 5)
    row = RowSegment(
        0, 0, 200, Path("unused"), 500, 200, work_y_top=40, transform=transform
    )
    token = RecognizedToken(
        0,
        "[1+3+5]",
        None,
        None,
        "chord",
        candidate_ids=tuple(c.candidate_id for c in digits),
    )
    raw = RowResult(
        row, "notation", token.text, [token], schema_version=2, registry=registry
    )
    result = match_row(raw, binary, analysis)
    g = result.tokens[0].geometry
    assert g.status == "matched"
    assert [p.value for p in g.primitives] == ["5", "3", "1"]
    for actual, c in zip(g.bodies, digits):
        expected = transform.box(replace(c.bounds, y=c.bounds.y + 40))
        assert actual == expected


def test_registered_shared_underlines_and_polyphony():
    image = Image.new("RGB", (600, 230), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=32)
    for x, y, value in [(60, 30, "3"), (150, 30, "5"), (60, 140, "1"), (150, 140, "2")]:
        draw.text((x, y), value, font=font, fill="black")
    a, b, c, d = draw.textbbox((60, 30), "3", font=font)
    draw.line((60, d + 4, 172, d + 4), fill="black", width=2)
    binary = otsu_binarize(np.asarray(image.convert("L")))
    analysis = analyze_row(binary)
    registry = build_registry(binary, analysis, 0)
    digits = sorted(
        [c for c in registry.candidates if c.kind == "digit"],
        key=lambda c: (c.band_ids, c.bounds.x),
    )
    tokens = [
        RecognizedToken(
            i, text, None, None, "note", candidate_ids=(candidate.candidate_id,)
        )
        for i, (text, candidate) in enumerate(zip(["q3", "q5", "1", "2"], digits))
    ]
    tokens.insert(2, RecognizedToken(9, "&", None, None, "other"))
    row = RowSegment(0, 0, 230, Path("unused"), 600, 230)
    result = match_row(
        RowResult(
            row, "notation", "q3 q5 & 1 2", tokens, schema_version=2, registry=registry
        ),
        binary,
        analysis,
    )
    assert all(t.geometry.status == "matched" for t in result.tokens if t.text != "&")
    lines = [
        next(p for p in t.geometry.primitives if p.value == "underline")
        for t in result.tokens[:2]
    ]
    assert lines[0].bounds == lines[1].bounds
    assert lines[0].hit_bounds.right <= lines[1].hit_bounds.x


def test_bad_barline_rejects_all_boundary_conflicts():
    binary, analysis, raw, digits = example()
    bar = next(c for c in raw.registry.candidates if c.kind == "barline")
    raw.tokens.insert(
        1,
        RecognizedToken(
            9, "|", None, None, "barline", candidate_ids=(bar.candidate_id,)
        ),
    )
    raw.tokens = [replace(t, index=i) for i, t in enumerate(raw.tokens)]
    result = match_row(raw, binary, analysis)
    assert result.tokens[0].geometry.bodies
    assert all(not t.geometry.primitives for t in result.tokens[1:])
