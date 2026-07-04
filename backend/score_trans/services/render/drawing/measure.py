from __future__ import annotations

from ....domain.performance_marks import get_performance_mark
from ..models.layout import MeasureLayout, RenderItem
from ..options import RenderOptions
from ..utils.metrics import _token_metrics
from ..utils.text import _esc
from ..utils.bars import _bar_line, _repeat_end_bar, _repeat_start_bar
from .beams import _render_beams
from .beat import (
    _performance_mark_ids,
    _render_slot_items,
    _unknown_mark_entries,
)
from .performance_marks import _render_performance_mark
from .spanners import _render_spanners
from .text import _render_measure_text_blocks

_MARK_ABOVE_TOKEN = 20  # highest technical mark above token visual top
_MEASURE_NO_GAP = 4  # clearance between measure number and highest element
_TUPLET_MARK_GAP = 9.0
_BAR_CONTENT_PADDING = 4.0


def _measure_number_y(measure: MeasureLayout, y: int, options: RenderOptions) -> int:
    """Compute the y-coordinate for the measure number, avoiding overlap with notes."""
    min_top = float(y)
    for beat in measure.beats:
        for item in beat.items:
            top = _token_metrics(item.token, y, options)["top"]
            upper_mark_extent = sum(
                mark.visual_height + mark.stack_gap
                for mark_id in _performance_mark_ids(item)
                if (mark := get_performance_mark(mark_id)) is not None
                and mark.placement == "above"
            )
            upper_mark_extent += len(_unknown_mark_entries(item)) * 16
            min_top = min(min_top, top - max(0, upper_mark_extent))
    return int(min(min_top - _MARK_ABOVE_TOKEN - _MEASURE_NO_GAP, y - 44))


def _measure_bar_bounds(
    measure: MeasureLayout,
    y: int,
    options: RenderOptions,
) -> tuple[float, float]:
    top = float(y - 50)
    bottom = float(y + 58)
    for beat in measure.beats:
        for item in beat.items:
            metrics = _token_metrics(item.token, y, options)
            top = min(top, metrics["top"] - _BAR_CONTENT_PADDING)
            bottom = max(bottom, metrics["bottom"] + _BAR_CONTENT_PADDING)

            above_extent = 0.0
            for mark_id in _performance_mark_ids(item):
                mark = get_performance_mark(mark_id)
                if mark is None:
                    continue
                if mark.placement == "above":
                    above_extent += mark.visual_height + mark.stack_gap
                elif mark.placement == "below-right":
                    bottom = max(
                        bottom,
                        metrics["bottom"] + mark.visual_height + _BAR_CONTENT_PADDING,
                    )
                elif mark.placement in {"left", "right"}:
                    top = min(
                        top,
                        y - mark.visual_height / 2 - _BAR_CONTENT_PADDING,
                    )
                    bottom = max(
                        bottom,
                        y + mark.visual_height / 2 + _BAR_CONTENT_PADDING,
                    )

            unknown_extent = len(_unknown_mark_entries(item)) * 16.0
            if item.tuplet_id:
                top = min(top, metrics["top"] - 22.0)
            if above_extent or unknown_extent:
                anchor_gap = 32.0 if item.tuplet_id else 13.0
                top = min(
                    top,
                    metrics["top"]
                    - anchor_gap
                    - above_extent
                    - unknown_extent
                    - _BAR_CONTENT_PADDING,
                )
            if item.dynamic:
                bottom = max(bottom, metrics["bottom"] + 34.0)
            if item.lyric:
                bottom = max(bottom, metrics["bottom"] + 22.0)

    used_lanes: dict[tuple[object, str], int] = {}
    seen: set[tuple[str, object]] = set()
    for block in getattr(measure.source, "text_blocks", []):
        text = str(getattr(block, "text", "") or "").strip()
        role = getattr(block, "role", None)
        if (
            not text
            or role not in {"expression", "other", "lyric"}
            or getattr(block, "bbox", None) is not None
        ):
            continue
        start = getattr(block, "start", None)
        key = (text, start)
        if key in seen:
            continue
        seen.add(key)
        placement = (getattr(block, "placement", None) or "below").lower()
        lane_key = (start, placement)
        lane = used_lanes.get(lane_key, 0)
        used_lanes[lane_key] = lane + 1
        text_y = y - 48 - lane * 18 if placement == "above" else y + 62 + lane * 20
        font_size = (
            options.dynamic_font_size
            if role == "expression"
            else options.lyric_font_size
        )
        top = min(top, text_y - font_size - _BAR_CONTENT_PADDING)
        bottom = max(bottom, text_y + _BAR_CONTENT_PADDING)
    return top, bottom


def _render_measure(
    measure: MeasureLayout,
    x: float,
    y: int,
    width: float,
    options: RenderOptions,
    *,
    draw_start_bar: bool,
    attribute_text: str | None = None,
    show_measure_number: bool | None = None,
    open_tie=None,
    open_slur=None,
    open_slide=None,
) -> tuple[list[str], object, object, object]:
    from ..layout.beat import _item_slots

    bar_top, bar_bottom = _measure_bar_bounds(measure, y, options)
    out = [
        f'<g class="measure" data-number="{_esc(str(measure.number))}" data-width="{width:.1f}">'
    ]
    if options.show_measure_numbers and (
        show_measure_number if show_measure_number is not None else True
    ):
        no_y = _measure_number_y(measure, y, options)
        out.append(
            f'<text class="measure-no" x="{x + 6:.1f}" y="{no_y}">{_esc(str(measure.number))}</text>'
        )
    if attribute_text:
        out.append(
            f'<text class="measure-attribute" x="{x + 28:.1f}" y="{y - 62}">{_esc(attribute_text)}</text>'
        )
    repeat_count = getattr(measure.source, "repeat_count", 1)
    if repeat_count > 1:
        rc_y = _measure_number_y(measure, y, options)
        out.append(
            f'<text class="repeat-count" x="{x + width - 6:.1f}" y="{rc_y}" text-anchor="end">*{repeat_count}</text>'
        )
    if getattr(measure.source, "repeat_start", False):
        out.extend(_repeat_start_bar(x, y, top=bar_top, bottom=bar_bottom))
    elif draw_start_bar:
        out.append(_bar_line(x, y, top=bar_top, bottom=bar_bottom))
    content_x = x + 26
    content_width = max(32.0, width - 56)
    natural_content = (
        sum(beat.width for beat in measure.beats)
        + max(0, len(measure.beats) - 1) * options.beat_gap
    )
    scale = content_width / natural_content if natural_content > 0 else 1.0
    beat_x = content_x
    measure_slots: list[tuple[RenderItem, float, float]] = []
    for beat_index, beat in enumerate(measure.beats):
        beat_width = beat.width * scale
        if options.show_beat_guides and beat_index > 0:
            out.append(
                f'<line class="beat-guide" x1="{beat_x:.1f}" y1="{y - 34}" '
                f'x2="{beat_x:.1f}" y2="{y + 52}"/>'
            )
        slots = _item_slots(beat.items, beat_x, beat_width, options)
        out.extend(_render_slot_items(slots, y, options))
        measure_slots.extend(slots)
        beat_x += beat_width + options.beat_gap * scale
    out.extend(_render_beams(measure_slots, y, options))
    out.extend(_render_tuplets(measure_slots, y, options))
    spanner_svg, new_tie, new_slur, new_slide = _render_spanners(
        measure_slots,
        y,
        open_tie=open_tie,
        open_slur=open_slur,
        open_slide=open_slide,
        options=options,
    )
    out.extend(spanner_svg)
    out.extend(_render_measure_text_blocks(measure.source, x, y, width, measure_slots))
    if measure.errors:
        out.append(
            f'<text class="measure-no error" x="{x + 6:.1f}" y="{y + 80}">{_esc("; ".join(measure.errors))}</text>'
        )
    if getattr(measure.source, "repeat_end", False):
        out.extend(
            _repeat_end_bar(
                x + width,
                y,
                top=bar_top,
                bottom=bar_bottom,
            )
        )
    else:
        out.append(
            _bar_line(
                x + width,
                y,
                top=bar_top,
                bottom=bar_bottom,
            )
        )
    out.append("</g>")
    return out, new_tie, new_slur, new_slide


def _render_tuplets(
    slots: list[tuple[RenderItem, float, float]],
    y: int,
    options: RenderOptions,
) -> list[str]:
    groups: dict[str, list[tuple[RenderItem, float, float]]] = {}
    for slot in slots:
        item, _cx, _slot_width = slot
        if not item.tuplet_id or not item.tuplet_count:
            continue
        groups.setdefault(item.tuplet_id, []).append(slot)

    out: list[str] = []
    for group_slots in groups.values():
        if len(group_slots) < 2:
            continue
        first_item, first_cx, first_width = group_slots[0]
        last_item, last_cx, last_width = group_slots[-1]
        count = first_item.tuplet_count or len(group_slots)
        x1 = first_cx - min(18.0, first_width / 2)
        x2 = last_cx + min(18.0, last_width / 2)
        top = min(
            _token_metrics(item.token, y, options)["top"]
            for item, _cx, _width in group_slots
        )
        bracket_y = top - 18
        tick = 7
        mid = (x1 + x2) / 2
        gap = 16
        out.append(
            f'<path class="tuplet-bracket" d="M {x1:.1f} {bracket_y + tick:.1f} '
            f"L {x1:.1f} {bracket_y:.1f} L {mid - gap:.1f} {bracket_y:.1f} "
            f"M {mid + gap:.1f} {bracket_y:.1f} L {x2:.1f} {bracket_y:.1f} "
            f'L {x2:.1f} {bracket_y + tick:.1f}"/>'
        )
        out.append(
            f'<text class="tuplet-number" x="{mid:.1f}" y="{bracket_y + 4:.1f}" '
            f'text-anchor="middle">{count}</text>'
        )
        out.extend(_render_tuplet_upper_marks(group_slots, bracket_y, y, options))
    return out


def _render_tuplet_upper_marks(
    group_slots: list[tuple[RenderItem, float, float]],
    bracket_y: float,
    y: int,
    options: RenderOptions,
) -> list[str]:
    out: list[str] = []
    for item, cx, _width in group_slots:
        layer = 0
        stack_offset = 0.0
        for mark_id in _performance_mark_ids(item):
            mark = get_performance_mark(mark_id)
            if mark is None or mark.placement != "above":
                continue
            mark_y = bracket_y - 14 - stack_offset
            out.extend(
                _render_performance_mark(
                    mark_id,
                    item.token,
                    cx,
                    y,
                    layer,
                    options,
                    anchor_y=mark_y,
                )
            )
            layer += 1
            stack_offset += mark.visual_height + mark.stack_gap
        for category, name in _unknown_mark_entries(item):
            mark_class = "technical" if category == "technical" else "ornament"
            mark_y = bracket_y - 10 - stack_offset
            out.append(
                f'<text class="{mark_class}" x="{cx:.1f}" y="{mark_y:.1f}" '
                f'text-anchor="middle">{_esc(name)}</text>'
            )
            layer += 1
            stack_offset += _TUPLET_MARK_GAP
    return out
