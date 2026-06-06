from __future__ import annotations

from ..models.layout import RenderItem
from ..utils.metrics import _token_metrics

# Type alias for a slot: (RenderItem, center_x, slot_width)
Slot = tuple[RenderItem, float, float]


def _render_spanners(
    slots: list[Slot],
    y: int,
    *,
    open_tie: Slot | None = None,
    open_slur: Slot | None = None,
) -> tuple[list[str], Slot | None, Slot | None]:
    """Render tie/slur arcs for a single measure's slots.

    Returns (svg_fragments, remaining_open_tie, remaining_open_slur) so the
    caller can carry open spanner state across measures on the same row.
    """
    out: list[str] = []
    cur_tie = open_tie
    cur_slur = open_slur
    for item, cx, slot_width in slots:
        current = (item, cx, slot_width)
        if item.tie_stop:
            if cur_tie is None:
                out.append(_render_tie_arc(None, current, y))
            else:
                out.append(_render_tie_arc(cur_tie, current, y))
                cur_tie = None
        if item.slur_stop:
            if cur_slur is None:
                out.append(_render_slur_arc(None, current, y))
            else:
                out.append(_render_slur_arc(cur_slur, current, y))
                cur_slur = None
        if item.tie_start:
            cur_tie = current
        if item.slur_start:
            cur_slur = current
    return out, cur_tie, cur_slur


def _finish_open_spanners(
    y: int,
    *,
    open_tie: Slot | None = None,
    open_slur: Slot | None = None,
) -> list[str]:
    """Render dangling open tie/slur arcs at the end of a row."""
    out: list[str] = []
    if open_tie is not None:
        out.append(_render_tie_arc(open_tie, None, y))
    if open_slur is not None:
        out.append(_render_slur_arc(open_slur, None, y))
    return out


def _render_tie_arc(
    start: tuple[RenderItem, float, float] | None,
    stop: tuple[RenderItem, float, float] | None,
    y: int,
) -> str:
    start_item, start_cx, start_slot = start if start is not None else stop  # type: ignore[misc]
    stop_item, stop_cx, stop_slot = stop if stop is not None else start  # type: ignore[misc]
    assert start_item is not None and stop_item is not None
    start_metrics = _token_metrics(start_item.token, y)
    stop_metrics = _token_metrics(stop_item.token, y)
    arc_y = max(start_metrics["bottom"], stop_metrics["bottom"]) + 9
    if start is None:
        x1 = stop_cx - max(34.0, min(54.0, stop_slot + 12))
        x2 = stop_cx - 8
    elif stop is None:
        x1 = start_cx + 8
        x2 = start_cx + max(34.0, min(54.0, start_slot + 12))
    else:
        x1 = start_cx + 8
        x2 = stop_cx - 8
        if x2 - x1 < 26:
            center = (start_cx + stop_cx) / 2
            x1 = center - 18
            x2 = center + 18
    return _arc_between("tie", x1, x2, arc_y, max(7.0, min(12.0, (x2 - x1) / 10)))


def _render_slur_arc(
    start: tuple[RenderItem, float, float] | None,
    stop: tuple[RenderItem, float, float] | None,
    y: int,
) -> str:
    start_item, start_cx, start_slot = start if start is not None else stop  # type: ignore[misc]
    stop_item, stop_cx, stop_slot = stop if stop is not None else start  # type: ignore[misc]
    assert start_item is not None and stop_item is not None
    start_metrics = _token_metrics(start_item.token, y)
    stop_metrics = _token_metrics(stop_item.token, y)
    arc_y = min(start_metrics["top"], stop_metrics["top"]) - 22
    if start is None:
        x1 = stop_cx - max(46.0, min(72.0, stop_slot + 18))
        x2 = stop_cx + 5
    elif stop is None:
        x1 = start_cx - 5
        x2 = start_cx + max(46.0, min(72.0, start_slot + 18))
    else:
        x1 = start_cx - 5
        x2 = stop_cx + 5
        if x2 - x1 < 34:
            center = (start_cx + stop_cx) / 2
            x1 = center - 22
            x2 = center + 22
    return _arc_between("slur", x1, x2, arc_y, -max(14.0, min(26.0, (x2 - x1) / 8)))


def _arc(class_name: str, x: float, y: float, width: float, height: float, *, forward: bool) -> str:
    end_x = x + width if forward else x - width
    return _arc_between(class_name, x, end_x, y, height)


def _arc_between(class_name: str, x1: float, x2: float, y: float, height: float) -> str:
    width = x2 - x1
    control_y = y + height
    return (
        f'<path class="{class_name}" d="M {x1:.1f} {y:.1f} '
        f'C {x1 + width * 0.25:.1f} {control_y:.1f}, {x1 + width * 0.75:.1f} {control_y:.1f}, {x2:.1f} {y:.1f}"/>'
    )
