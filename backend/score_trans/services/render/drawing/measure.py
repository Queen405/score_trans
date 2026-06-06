from __future__ import annotations

from typing import Any

from ..models.layout import MeasureLayout, RenderItem
from ..options import RenderOptions
from ..utils.text import _esc
from ..utils.bars import _bar_line, _repeat_end_bar, _repeat_start_bar
from .beams import _render_beams
from .beat import _render_slot_items
from .spanners import _render_spanners
from .text import _render_measure_text_blocks


def _render_measure(
    measure: MeasureLayout,
    x: float,
    y: int,
    width: float,
    options: RenderOptions,
    *,
    draw_start_bar: bool,
) -> list[str]:
    from ..layout.beat import _item_slots

    out = [f'<g class="measure" data-number="{_esc(str(measure.number))}" data-width="{width:.1f}">']
    if options.show_measure_numbers:
        out.append(f'<text class="measure-no" x="{x + 6:.1f}" y="{y - 62}">{_esc(str(measure.number))}</text>')
    repeat_count = getattr(measure.source, "repeat_count", 1)
    if repeat_count > 1:
        out.append(f'<text class="repeat-count" x="{x + width - 6:.1f}" y="{y - 62}" text-anchor="end">*{repeat_count}</text>')
    if getattr(measure.source, "repeat_start", False):
        out.extend(_repeat_start_bar(x, y))
    elif draw_start_bar:
        out.append(_bar_line(x, y))
    content_x = x + 26
    content_width = max(32.0, width - 56)
    natural_content = sum(beat.width for beat in measure.beats) + max(0, len(measure.beats) - 1) * options.beat_gap
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
        slots = _item_slots(beat.items, beat_x, beat_width)
        out.extend(_render_slot_items(slots, y))
        measure_slots.extend(slots)
        beat_x += beat_width + options.beat_gap * scale
    out.extend(_render_beams(measure_slots, y))
    out.extend(_render_spanners(measure_slots, y))
    out.extend(_render_measure_text_blocks(measure.source, x, y, width, measure_slots))
    if measure.errors:
        out.append(f'<text class="measure-no error" x="{x + 6:.1f}" y="{y + 80}">{_esc("; ".join(measure.errors))}</text>')
    if getattr(measure.source, "repeat_end", False):
        out.extend(_repeat_end_bar(x + width, y))
    else:
        out.append(_bar_line(x + width, y))
    out.append("</g>")
    return out
