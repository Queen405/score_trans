from __future__ import annotations

from collections import Counter
from dataclasses import replace
from ..models.contracts import RowResult
from ..models.geometry import TokenGeometry, Box
from ..models.raster import RowAnalysis
from .geometry import page_box, add_shape, add_line


def match_body_row(raw: RowResult, analysis: RowAnalysis) -> RowResult:
    """Project confirmed body labels. Do not parse visual stacks as timed music."""
    result = replace(
        raw,
        tokens=[replace(t, geometry=TokenGeometry()) for t in raw.tokens],
        warnings=list(raw.warnings),
        analysis=analysis,
    )
    registry = result.registry
    candidates = {c.candidate_id: c for c in registry.candidates} if registry else {}
    uses = Counter(cid for t in result.tokens for cid in t.candidate_ids)
    for token in result.tokens:
        g = token.geometry
        if token.text == "&":
            g.status = "ignored"
            continue
        selected = [candidates[cid] for cid in token.candidate_ids if cid in candidates]
        valid = (
            bool(selected)
            and len(selected) == len(token.candidate_ids)
            and registry.row_index == result.row.index
            and (registry.width, registry.height)
            == (result.row.width, result.row.height)
        )
        if not valid or any(
            uses[c.candidate_id] != 1
            or c.ambiguous
            or any(uses[x] for x in c.conflicts)
            for c in selected
        ):
            g.warnings.append("主体编号无效或占用冲突")
            continue
        if token.role == "barline":
            if len(selected) != 1 or selected[0].kind != "barline":
                g.warnings.append("小节线主体类型错误")
                continue
            for line in selected[0].lines:
                add_line(result.row, g, line, "barline")
            g.status = "matched" if g.primitives else "unmatched"
            continue
        labels = token.text[1:-1].split("+") if token.role == "chord" else [token.text]
        if len(labels) != len(selected) or any(
            label not in tuple("01234567") or c.kind != "digit"
            for label, c in zip(labels, selected)
        ):
            g.warnings.append("主体分类与 token 不一致")
            continue
        g.voice = min(selected[-1].band_ids)
        g.bodies = [page_box(result.row, c.bounds) for c in selected]
        for label, c in zip(labels, selected, strict=True):
            add_shape(result.row, g, "glyph", c.bounds, label)
            body = c.bounds
            neighbors = [
                other.bounds
                for other in registry.candidates
                if other.kind in ("digit", "barline")
                and set(c.band_ids).intersection(other.band_ids)
                and other.candidate_id not in token.candidate_ids
                and other.candidate_id not in c.conflicts
            ]
            left = max(
                ((b.cx + body.cx) / 2 for b in neighbors if b.cx < body.cx), default=0
            )
            right = min(
                ((b.cx + body.cx) / 2 for b in neighbors if b.cx > body.cx),
                default=result.row.width,
            )
            # Real underlines are drawn as observed ink, not converted into a duration.
            for line in analysis.horizontal:
                b = line.bounds
                if (
                    b.x <= body.cx <= b.right
                    and body.bottom - 1 <= b.cy < body.bottom + body.height * 0.9
                ):
                    x, end = max(b.x, left), min(b.right, right)
                    if end > x:
                        add_line(
                            result.row,
                            g,
                            line,
                            "underline",
                            Box(x, b.y, end - x, b.height),
                        )
        g.status = "partial"
        g.warnings.append("主体已确认；八度、时值和附属关系未验证")
    result.warnings.extend(
        f"行 {result.row.index} token {t.index}: {w}"
        for t in result.tokens
        for w in t.geometry.warnings
    )
    return result
