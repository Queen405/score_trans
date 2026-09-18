from __future__ import annotations

import numpy as np
from ..models.contracts import RowResult
from ..models.geometry import TokenGeometry
from ..models.raster import RowAnalysis, SymbolCandidate
from ..raster.projections import barline_candidates
from ..symbols.notation_parser import parse_notation
from .sequence_alignment import align_sequence
from .geometry import page_box, add_shape, add_line
from .attachments import attach_pitch, attach_rhythm
from .relations import attach_relations


def match_row(
    result: RowResult, binary: np.ndarray, analysis: RowAnalysis
) -> RowResult:
    """Create a new row result. Raw recognition tokens and input row are untouched."""
    if result.schema_version == 3:
        from .body_matcher import match_body_row

        return match_body_row(result, analysis)
    if result.schema_version == 2:
        from .registered_matcher import match_registered_row

        return match_registered_row(result, analysis)
    from dataclasses import replace

    result = replace(
        result,
        tokens=[replace(t, geometry=TokenGeometry()) for t in result.tokens],
        warnings=list(result.warnings),
        analysis=analysis,
    )
    groups = {}
    voice = 0
    for token in result.tokens:
        token.geometry.voice = voice
        if token.text.strip() == "&":
            token.geometry.status = "ignored"
            voice += 1
            continue
        if (
            token.role.startswith("header_")
            or token.role == "lyrics"
            or token.text.strip() == "L:"
        ):
            token.geometry.status = "ignored"
            continue
        note = parse_notation(token.text)
        if note is None:
            token.geometry.status = "unsupported"
            token.geometry.warnings.append("不支持的记法，保留文本")
            continue
        if note.kind == "relation":
            token.geometry.status = "ignored"
        groups.setdefault(voice, []).append((token, note))
        if note.kind == "barline":
            voice = 0
    bands = list(analysis.bands)
    if any(t.role == "lyrics" for t in result.tokens) and len(bands) > len(groups):
        bands = bands[:-1]
    # Dense baselines win; ties favor a lower baseline so a chord-only row
    # anchors on the lowest pitch instead of counting chord tones as voices.
    selected = sorted(
        sorted(bands, key=lambda b: (-len(b.candidates), -b.baseline.points[0][1]))[
            : len(groups)
        ],
        key=lambda b: b.baseline.points[0][1],
    )
    row = result.row
    for voice, group in groups.items():
        if voice >= len(selected):
            for token, _ in group:
                token.geometry.warnings.append("未找到对应声部带")
            continue
        band = selected[voice]
        height = band.digit_height
        bars = barline_candidates(binary, band, analysis.vertical)
        candidates = sorted(
            [
                *band.candidates,
                *(
                    SymbolCandidate(f"bar{i}", "barline", line.bounds, 0)
                    for i, line in enumerate(bars)
                ),
            ],
            key=lambda c: c.bounds.cx,
        )
        physical = [(t, n) for t, n in group if n.kind in ("note", "barline")]
        pairs = align_sequence(physical, candidates, row.width, height)
        located = {i: candidates[j] for i, j in pairs}
        for i, candidate in located.items():
            token, note = physical[i]
            g = token.geometry
            body = candidate.bounds
            if note.kind == "barline":
                nearby = sorted(
                    [
                        line
                        for line in bars
                        if abs(line.bounds.cx - body.cx) < height * 0.55
                    ],
                    key=lambda line_item: abs(line_item.bounds.cx - body.cx),
                )
                count = token.text.count("|")
                for line in nearby[:count]:
                    add_line(row, g, line, "barline")
                if len(nearby) < count:
                    g.warnings.append("部分小节线未定位")
                if ":" in token.text:
                    dots = [
                        c.bounds
                        for c in analysis.components
                        if max(c.bounds.width, c.bounds.height) < height * 0.35
                        and abs(c.bounds.cx - body.cx) < height
                        and body.y < c.bounds.cy < body.bottom
                    ]
                    for dot in dots:
                        add_shape(row, g, "dot", dot, "repeat")
                    if len(dots) < 2:
                        g.warnings.append("反复圆点未定位")
            else:
                if len(note.pitches) == 1:
                    bodies = [body]
                else:
                    options = [
                        c.bounds
                        for b in bands
                        for c in b.candidates
                        if abs(c.bounds.cx - body.cx) < height * 0.45
                        and body.bottom - height * len(note.pitches) * 2 < c.bounds.y
                        and c.bounds.bottom <= body.bottom + height * 0.2
                    ]
                    bodies = sorted(
                        sorted(options, key=lambda b: -b.bottom)[: len(note.pitches)],
                        key=lambda b: b.y,
                    )
                if len(bodies) != len(note.pitches):
                    g.warnings.append("和弦音高数量与墨迹不符")
                    continue
                g.bodies = [page_box(row, b) for b in bodies]
                for pitch, b in zip(note.pitches, bodies, strict=True):
                    add_shape(row, g, "glyph", b, pitch.degree)
                    attach_pitch(row, g, pitch, b, analysis)
                left = max(
                    (
                        (c.bounds.cx + body.cx) / 2
                        for j, c in located.items()
                        if j < i and c.bounds.cx < body.cx
                    ),
                    default=0,
                )
                right = min(
                    (
                        (c.bounds.cx + body.cx) / 2
                        for j, c in located.items()
                        if j > i and c.bounds.cx > body.cx
                    ),
                    default=row.width,
                )
                next_body = min(
                    (
                        c.bounds.x
                        for j, c in located.items()
                        if j > i and c.bounds.x > body.right
                    ),
                    default=row.width,
                )
                attach_rhythm(row, g, note, body, analysis, left, right, next_body)
            g.status = "partial" if g.warnings else "matched"
        for token, note in group:
            if (
                note.kind == "extension"
                and token.x is not None
                and token.w is not None
                and 0 <= token.x < 1
                and 0 < token.w <= 1 - token.x
            ):
                x = (token.x + token.w / 2) * row.width
                options = [
                    line
                    for line in analysis.horizontal
                    if abs(line.bounds.cx - x) < max(height, token.w * row.width)
                    and abs(line.bounds.cy - (band.baseline.y_at(x) - height / 2))
                    < height * 0.35
                ]
                for line in sorted(
                    options, key=lambda line_item: abs(line_item.bounds.cx - x)
                )[: note.extensions]:
                    add_line(row, token.geometry, line, "extension")
                if token.geometry.primitives:
                    token.geometry.status = "matched"
        attach_relations(row, group, analysis)
    for token in result.tokens:
        g = token.geometry
        if g.status == "unmatched" and not g.warnings:
            g.warnings.append("未找到可靠墨迹，未绘制")
        if g.primitives and g.warnings:
            g.status = "partial"
        result.warnings.extend(
            f"行 {row.index} token {token.index} ({token.text}): {w}"
            for w in g.warnings
        )
    return result
