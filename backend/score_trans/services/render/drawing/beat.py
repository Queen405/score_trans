from __future__ import annotations

from ....domain.performance_marks import (
    canonical_mark_id,
    event_mark_ids,
    get_performance_mark,
)
from ..models.layout import RenderItem
from ..options import RenderOptions
from ..utils.text import _esc
from ..utils.metrics import _token_metrics
from ..utils.helpers import _mark_display
from .beams import _render_beams, _beamable_slashes
from .performance_marks import _render_performance_mark
from .spanners import _render_spanners
from .token import _render_token


def _render_beat_items(
    items: list[RenderItem],
    x: float,
    width: float,
    y: int,
    options: RenderOptions | None = None,
) -> list[str]:
    from ..layout.beat import _item_slots

    slots = _item_slots(items, x, width, options)
    spanners, _tie, _slur, _slide = _render_spanners(
        slots, y, options=options
    )
    return (
        _render_slot_items(slots, y, options)
        + _render_beams(slots, y, options)
        + spanners
    )


def _render_slot_items(
    slots: list[tuple[RenderItem, float, float]],
    y: int,
    options: RenderOptions | None = None,
) -> list[str]:
    out: list[str] = []
    beamed_ids = {id(item) for item, _, _ in slots if _beamable_slashes(item.token) > 0}
    for item, cx, slot in slots:
        out.extend(
            _render_item(
                item,
                cx,
                y,
                slot,
                suppress_duration=id(item) in beamed_ids,
                suppress_upper_marks=item.tuplet_id is not None,
                options=options,
            )
        )
    return out


def _render_item(
    item: RenderItem,
    cx: float,
    y: int,
    slot_width: float,
    *,
    suppress_duration: bool = False,
    suppress_upper_marks: bool = False,
    options: RenderOptions | None = None,
) -> list[str]:
    out = _render_token(
        item.token,
        cx,
        y,
        generated=item.generated,
        suppress_duration=suppress_duration,
        options=options,
    )
    if item.dynamic:
        bottom = _token_metrics(item.token, y, options)["bottom"]
        out.append(
            f'<text class="dynamic" x="{cx:.1f}" y="{bottom + 30:.1f}" text-anchor="middle">{_esc(item.dynamic)}</text>'
        )
    placement_layers: dict[str, int] = {}
    for mark_id in _performance_mark_ids(item):
        mark = get_performance_mark(mark_id)
        if mark is None:
            continue
        if suppress_upper_marks and mark.placement == "above":
            continue
        layer = placement_layers.get(mark.placement, 0)
        out.extend(
            _render_performance_mark(
                mark_id,
                item.token,
                cx,
                y,
                layer,
                options,
            )
        )
        placement_layers[mark.placement] = layer + 1
    if not suppress_upper_marks:
        unknown_layer = placement_layers.get("above", 0)
        top = _token_metrics(item.token, y, options)["top"]
        for category, name in _unknown_mark_entries(item):
            mark_class = "technical" if category == "technical" else "ornament"
            out.append(
                f'<text class="{mark_class}" x="{cx:.1f}" '
                f'y="{top - 9 - unknown_layer * 16:.1f}" '
                f'text-anchor="middle">{_esc(_mark_display(name))}</text>'
            )
            unknown_layer += 1
    if item.lyric:
        bottom = _token_metrics(item.token, y, options)["bottom"]
        out.append(
            f'<text class="lyric" x="{cx:.1f}" y="{bottom + 18:.1f}" text-anchor="middle">{_esc(item.lyric)}</text>'
        )
    if item.playback_index is not None:
        return [
            f'<g class="playback-note" data-note-index="{item.playback_index}" data-note-token="{_esc(item.token)}">',
            *out,
            "</g>",
        ]
    return out


def _performance_mark_ids(item: RenderItem) -> list[str]:
    articulations = item.articulations or (
        [item.articulation] if item.articulation else []
    )
    return event_mark_ids(
        list(articulations),
        list(item.ornaments),
        list(item.technical),
    )


def _unknown_mark_entries(item: RenderItem) -> list[tuple[str, str]]:
    articulations = item.articulations or (
        [item.articulation] if item.articulation else []
    )
    result: list[tuple[str, str]] = []
    for category, marks in (
        ("articulation", articulations),
        ("ornament", item.ornaments),
        ("technical", item.technical),
    ):
        for mark in marks:
            if canonical_mark_id(mark) is None:
                result.append((category, mark))
    return result
