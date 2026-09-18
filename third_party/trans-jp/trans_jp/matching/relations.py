from __future__ import annotations
from ..models.contracts import RowSegment, RecognizedToken
from ..models.notation import Notation
from ..models.raster import RowAnalysis
from ..models.geometry import Primitive
from .geometry import page_box


def _curve(
    row: RowSegment,
    owner: RecognizedToken,
    start: RecognizedToken,
    end: RecognizedToken,
    analysis: RowAnalysis,
) -> None:
    a, b = start.geometry.bodies[0], end.geometry.bodies[0]
    height = max(a.height, b.height)
    if b.cx <= a.cx:
        owner.geometry.warnings.append("连线端点顺序无效")
        return
    candidates = [page_box(row, c.bounds) for c in analysis.components]
    candidates = [
        box
        for box in candidates
        if box.width > (b.cx - a.cx) * 0.65
        and abs(box.x - a.cx) < height
        and abs(box.right - b.cx) < height
        and box.bottom < max(a.y, b.y) + height * 0.2
        and box.y > min(a.y, b.y) - height * 2
    ]
    if not candidates:
        owner.geometry.warnings.append("连线墨迹未定位")
        return
    box = min(candidates, key=lambda c: abs(c.x - a.cx) + abs(c.right - b.cx))
    owner.geometry.primitives.append(
        Primitive(
            "curve",
            box,
            "slur",
            thickness=max(0.6, analysis.line_thickness / row.transform.scale_y),
        )
    )
    owner.geometry.status = "matched"


def attach_relations(
    row: RowSegment,
    group: list[tuple[RecognizedToken, Notation]],
    analysis: RowAnalysis,
) -> None:
    stack: list[tuple[RecognizedToken, RecognizedToken]] = []
    pending: list[RecognizedToken] = []
    tie: tuple[RecognizedToken, RecognizedToken, Notation] | None = None
    previous: tuple[RecognizedToken, Notation] | None = None
    for token, note in group:
        if note.kind == "relation":
            if token.text.strip() == "~":
                if previous and tie is None:
                    tie = (token, *previous)
                elif not previous:
                    token.geometry.warnings.append("延音线缺少起点")
            else:
                pending.extend([token] * note.opens)
                for _ in range(note.closes):
                    if stack and previous:
                        owner, start = stack.pop()
                        _curve(row, owner, start, previous[0], analysis)
                    else:
                        token.geometry.warnings.append("圆滑线缺少起点")
            continue
        if not token.geometry.bodies:
            if note.kind == "note":
                previous = None
                if tie:
                    tie[0].geometry.warnings.append("延音线终点未定位")
                    tie = None
            continue
        stack.extend((owner, token) for owner in pending)
        pending.clear()
        stack.extend([(token, token)] * note.opens)
        if tie:
            owner, start, start_note = tie
            if start_note.pitches == note.pitches:
                _curve(row, owner, start, token, analysis)
            else:
                owner.geometry.warnings.append("延音线两端音高不一致")
            tie = None
        elif note.tie_end:
            token.geometry.warnings.append("延音线缺少起点")
        if note.tie_start:
            tie = (token, token, note)
        for _ in range(note.closes):
            if stack:
                owner, start = stack.pop()
                _curve(row, owner, start, token, analysis)
            else:
                token.geometry.warnings.append("圆滑线缺少起点")
        previous = (token, note)
    for owner in [*(owner for owner, _ in stack), *pending, *([tie[0]] if tie else [])]:
        owner.geometry.warnings.append("跨行或未闭合连线，未绘制")
