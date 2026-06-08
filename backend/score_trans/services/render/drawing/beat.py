from __future__ import annotations

from ..models.layout import RenderItem
from ..parsing.tokens import _parse_chord_token, _parse_note
from ..utils.articulations import _render_articulation
from ..utils.helpers import _mark_display
from ..utils.positioning import _technique_mark, _technique_mark_x, _technique_mark_y, _upper_mark_anchor_y
from ..utils.text import _esc
from ..utils.metrics import _token_metrics
from .beams import _render_beams, _beamable_slashes
from .spanners import _render_spanners
from .token import _render_token


def _render_beat_items(items: list[RenderItem], x: float, width: float, y: int) -> list[str]:
    from ..layout.beat import _item_slots
    slots = _item_slots(items, x, width)
    return _render_slot_items(slots, y) + _render_beams(slots, y) + _render_spanners(slots, y)


def _render_slot_items(slots: list[tuple[RenderItem, float, float]], y: int) -> list[str]:
    out: list[str] = []
    beamed_ids = {id(item) for item, _, _ in slots if _beamable_slashes(item.token) > 0}
    for item, cx, slot in slots:
        out.extend(_render_item(item, cx, y, slot, suppress_duration=id(item) in beamed_ids))
    return out


def _render_item(item: RenderItem, cx: float, y: int, slot_width: float, *, suppress_duration: bool = False) -> list[str]:
    out = _render_token(item.token, cx, y, generated=item.generated, suppress_duration=suppress_duration)
    if item.dynamic:
        bottom = _token_metrics(item.token, y)["bottom"]
        out.append(f'<text class="dynamic" x="{cx:.1f}" y="{bottom + 30:.1f}" text-anchor="middle">{_esc(item.dynamic)}</text>')
    for index, mark in enumerate(_technique_marks(item)):
        tx = _technique_mark_x(item.token, cx)
        ty = _technique_mark_y(item.token, y) + index * 17
        if mark == "轮":
            d = " ".join(
                f"M {tx + i * 3.5:.1f} {ty - 7:.1f} L {tx + 8 + i * 3.5:.1f} {ty + 2:.1f}"
                for i in range(3)
            )
            out.append(
                f'<path class="technique-mark" d="{d}" stroke="#171717" stroke-width="1.5" fill="none"/>'
            )
        else:
            out.append(
                f'<text class="technique-mark" x="{tx:.1f}" '
                f'y="{ty:.1f}" text-anchor="start">{_esc(mark)}</text>'
            )
    upper_anchor_y = _upper_mark_anchor_y(item.token, y)
    articulations = item.articulations or ([item.articulation] if item.articulation else [])
    for index, articulation in enumerate(articulations[:4]):
        out.extend(_render_articulation(articulation, cx, upper_anchor_y - index * 12))
    visible_ornaments = [ornament for ornament in item.ornaments if _technique_mark(ornament) is None]
    for index, ornament in enumerate(visible_ornaments[:3]):
        out.append(
            f'<text class="ornament" x="{cx:.1f}" y="{upper_anchor_y - 46 - index * 14:.1f}" '
            f'text-anchor="middle">{_esc(_mark_display(ornament))}</text>'
        )
    visible_technical = [technical for technical in item.technical if _technique_mark(technical) is None]
    for index, technical in enumerate(visible_technical[:4]):
        out.append(
            f'<text class="technical" x="{cx:.1f}" y="{upper_anchor_y - 64 - index * 13:.1f}" '
            f'text-anchor="middle">{_esc(_mark_display(technical))}</text>'
        )
    if item.lyric:
        bottom = _token_metrics(item.token, y)["bottom"]
        out.append(f'<text class="lyric" x="{cx:.1f}" y="{bottom + 18:.1f}" text-anchor="middle">{_esc(item.lyric)}</text>')
    if item.playback_index is not None:
        return [
            f'<g class="playback-note" data-note-index="{item.playback_index}" data-note-token="{_esc(item.token)}">',
            *out,
            "</g>",
        ]
    return out


def _technique_marks(item: RenderItem) -> list[str]:
    marks: list[str] = []
    seen: set[str] = set()
    for name in [*item.ornaments, *item.technical]:
        mark = _technique_mark(name)
        if mark and mark not in seen:
            marks.append(mark)
            seen.add(mark)
    return marks
