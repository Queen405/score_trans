from __future__ import annotations

from ..models.layout import RenderItem
from ..options import RenderOptions
from ..utils.metrics import _token_metrics

# Type alias for a slot: (RenderItem, center_x, slot_width)
Slot = tuple[RenderItem, float, float]


def _render_spanners(
    slots: list[Slot],
    y: int,
    *,
    open_tie: Slot | None = None,
    open_slur: Slot | None = None,
    open_slide: Slot | None = None,
    options: RenderOptions | None = None,
) -> tuple[list[str], Slot | None, Slot | None, Slot | None]:
    """Render tie/slur arcs for a single measure's slots.

    Returns SVG plus remaining tie, slur, and slide state so the
    caller can carry open spanner state across measures on the same row.
    """
    out: list[str] = []
    cur_tie = open_tie
    cur_slur = open_slur
    cur_slide = open_slide
    for item, cx, slot_width in slots:
        current = (item, cx, slot_width)
        if item.tie_stop:
            if cur_tie is None:
                out.append(_render_tie_arc(None, current, y, options))
            else:
                out.append(_render_tie_arc(cur_tie, current, y, options))
                cur_tie = None
        if item.slur_stop:
            if cur_slur is None:
                out.append(_render_slur_arc(None, current, y, options))
            else:
                out.append(_render_slur_arc(cur_slur, current, y, options))
                cur_slur = None
        if item.slide_stop:
            if cur_slide is None:
                out.append(_render_slide_curve(None, current, y, options))
            else:
                out.append(_render_slide_curve(cur_slide, current, y, options))
                cur_slide = None
        if item.tie_start:
            cur_tie = current
        if item.slur_start:
            cur_slur = current
        if item.slide_start:
            cur_slide = current
    return out, cur_tie, cur_slur, cur_slide


def _finish_open_spanners(
    y: int,
    *,
    open_tie: Slot | None = None,
    open_slur: Slot | None = None,
    open_slide: Slot | None = None,
    options: RenderOptions | None = None,
) -> list[str]:
    """Render dangling open tie/slur arcs at the end of a row."""
    out: list[str] = []
    if open_tie is not None:
        out.append(_render_tie_arc(open_tie, None, y, options))
    if open_slur is not None:
        out.append(_render_slur_arc(open_slur, None, y, options))
    if open_slide is not None:
        out.append(_render_slide_curve(open_slide, None, y, options))
    return out


def _render_tie_arc(
    start: tuple[RenderItem, float, float] | None,
    stop: tuple[RenderItem, float, float] | None,
    y: int,
    options: RenderOptions | None = None,
) -> str:
    start_item, start_cx, start_slot = start if start is not None else stop  # type: ignore[misc]
    stop_item, stop_cx, stop_slot = stop if stop is not None else start  # type: ignore[misc]
    assert start_item is not None and stop_item is not None
    start_metrics = _token_metrics(start_item.token, y, options)
    stop_metrics = _token_metrics(stop_item.token, y, options)
    arc_y = max(start_metrics["bottom"], stop_metrics["bottom"]) + 13
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
    options: RenderOptions | None = None,
) -> str:
    start_item, start_cx, start_slot = start if start is not None else stop  # type: ignore[misc]
    stop_item, stop_cx, stop_slot = stop if stop is not None else start  # type: ignore[misc]
    assert start_item is not None and stop_item is not None
    start_metrics = _token_metrics(start_item.token, y, options)
    stop_metrics = _token_metrics(stop_item.token, y, options)
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


def _render_slide_curve(
    start: tuple[RenderItem, float, float] | None,
    stop: tuple[RenderItem, float, float] | None,
    y: int,
    options: RenderOptions | None = None,
) -> str:
    start_item, start_cx, start_slot = start if start is not None else stop  # type: ignore[misc]
    stop_item, stop_cx, stop_slot = stop if stop is not None else start  # type: ignore[misc]
    assert start_item is not None and stop_item is not None
    _token_metrics(start_item.token, y, options)
    _token_metrics(stop_item.token, y, options)
    curve_y = y - 3
    if start is None:
        x1 = stop_cx - max(34.0, min(58.0, stop_slot + 14))
        x2 = stop_cx - 10
    elif stop is None:
        x1 = start_cx + 10
        x2 = start_cx + max(34.0, min(58.0, start_slot + 14))
    else:
        x1 = start_cx + 10
        x2 = stop_cx - 10
        if x2 - x1 < 22:
            center = (start_cx + stop_cx) / 2
            x1 = center - 15
            x2 = center + 15
    width = x2 - x1
    direction = start_item.slide_direction or stop_item.slide_direction
    if direction == "down":
        start_offset, end_offset = -5.0, 5.0
        control_1, control_2 = -3.0, 3.0
    elif direction == "up":
        start_offset, end_offset = 5.0, -5.0
        control_1, control_2 = 3.0, -3.0
    else:
        start_offset, end_offset = 4.0, -4.0
        control_1, control_2 = -5.0, 5.0
    direction_attr = f' data-direction="{direction}"' if direction else ""
    return (
        f'<path class="slide" data-mark="continuous-slide"{direction_attr} '
        f'd="M {x1:.1f} {curve_y + start_offset:.1f} '
        f"C {x1 + width * 0.3:.1f} {curve_y + control_1:.1f}, "
        f"{x1 + width * 0.7:.1f} {curve_y + control_2:.1f}, "
        f'{x2:.1f} {curve_y + end_offset:.1f}"/>'
    )


def _arc_between(class_name: str, x1: float, x2: float, y: float, height: float) -> str:
    width = x2 - x1
    control_y = y + height
    return (
        f'<path class="{class_name}" d="M {x1:.1f} {y:.1f} '
        f'C {x1 + width * 0.25:.1f} {control_y:.1f}, {x1 + width * 0.75:.1f} {control_y:.1f}, {x2:.1f} {y:.1f}"/>'
    )
