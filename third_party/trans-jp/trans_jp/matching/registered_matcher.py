from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from ..models.contracts import RowResult
from ..models.geometry import TokenGeometry
from ..models.raster import RowAnalysis
from ..symbols.notation_parser import parse_notation
from .attachments import attach_pitch, attach_rhythm
from .candidate_binding import bind_candidates
from .geometry import add_line, add_shape, page_box
from .relations import attach_relations


def match_registered_row(raw: RowResult, analysis: RowAnalysis) -> RowResult:
    result = replace(
        raw,
        tokens=[replace(t, geometry=TokenGeometry()) for t in raw.tokens],
        warnings=list(raw.warnings),
        analysis=analysis,
    )
    notes, contexts = {}, {}
    measure = voice = 0
    for t in result.tokens:
        g = t.geometry
        g.voice = voice
        contexts[t.index] = (measure, voice)
        if t.text.strip() == "&":
            g.status = "ignored"
            voice += 1
            continue
        if t.role.startswith("header_") or t.role == "lyrics" or t.text.strip() == "L:":
            g.status = "ignored"
            continue
        note = parse_notation(t.text)
        if note is None:
            g.status = "unsupported"
            g.warnings.append("不支持的记法，保留文本")
            continue
        notes[t.index] = note
        if note.kind == "relation":
            g.status = "ignored"
        if note.kind == "barline":
            measure += 1
            voice = 0
    bound, rejected = bind_candidates(result, notes, contexts)
    for t in result.tokens:
        g = t.geometry
        if t.index in rejected:
            g.warnings.extend(rejected[t.index])
        if t.index not in bound:
            continue
        selected, note, row = bound[t.index], notes[t.index], result.row
        body = selected[-1].bounds
        if note.kind in ("barline", "extension"):
            for c in selected:
                for line in c.lines:
                    add_line(row, g, line, note.kind)
            if note.kind == "barline":
                if len(selected[0].lines) != t.text.count("|"):
                    g.warnings.append("小节线线段数与识别文本不符")
                if ":" in t.text:
                    dots = [
                        c.bounds
                        for c in analysis.components
                        if max(c.bounds.width, c.bounds.height) < body.height * 0.25
                        and abs(c.bounds.cx - body.cx) < body.height * 0.6
                        and body.y < c.bounds.cy < body.bottom
                    ]
                    for dot in dots:
                        add_shape(row, g, "dot", dot, "repeat")
                    if len(dots) < 2:
                        g.warnings.append("反复圆点未定位")
        else:
            # Unclaimed ink also bounds attachments so omitted notes cannot be robbed.
            band = set(selected[-1].band_ids)
            neighbors = [
                c.bounds
                for c in result.registry.candidates
                if c.kind in ("digit", "barline")
                and band.intersection(c.band_ids)
                and c.candidate_id not in t.candidate_ids
                and c.candidate_id not in selected[-1].conflicts
            ]
            left = max(
                ((b.cx + body.cx) / 2 for b in neighbors if b.cx < body.cx), default=0
            )
            right = min(
                ((b.cx + body.cx) / 2 for b in neighbors if b.cx > body.cx),
                default=row.width,
            )
            next_body = min(
                (b.x for b in neighbors if b.x > body.right), default=row.width
            )
            local = replace(
                analysis,
                components=tuple(
                    c for c in analysis.components if left <= c.bounds.cx <= right
                ),
            )
            g.bodies = [page_box(row, c.bounds) for c in selected]
            for pitch, c in zip(note.pitches, selected, strict=True):
                add_shape(row, g, "glyph", c.bounds, pitch.degree)
                attach_pitch(row, g, pitch, c.bounds, local)
            attach_rhythm(row, g, note, body, local, left, right, next_body)
        g.status = "partial" if g.warnings else "matched"
    _remove_ambiguous_attachments(result)
    groups = defaultdict(list)
    for t in result.tokens:
        if t.index in notes:
            groups[t.geometry.voice].append((t, notes[t.index]))
    for group in groups.values():
        attach_relations(result.row, group, analysis)
    for t in result.tokens:
        g = t.geometry
        if g.status == "unmatched" and not g.warnings:
            g.warnings.append("未找到可靠候选，未绘制")
        if g.primitives:
            g.status = "partial" if g.warnings else "matched"
        elif g.status in ("matched", "partial"):
            g.status = "unmatched"
        result.warnings.extend(
            f"行 {result.row.index} token {t.index} ({t.text}): {w}" for w in g.warnings
        )
    return result


def _remove_ambiguous_attachments(result: RowResult) -> None:
    owners = defaultdict(set)
    for t in result.tokens:
        for p in t.geometry.primitives:
            if (
                p.kind == "dot"
                or (p.kind == "glyph" and p.value not in "01234567")
                or p.value == "extension"
            ):
                owners[(p.kind, p.bounds)].add(t.index)
    collisions = {key for key, indexes in owners.items() if len(indexes) > 1}
    for t in result.tokens:
        g = t.geometry
        if any((p.kind, p.bounds) in collisions for p in g.primitives):
            g.primitives = [
                p for p in g.primitives if (p.kind, p.bounds) not in collisions
            ]
            g.warnings.append("附属符号存在多个归属，未绘制")
