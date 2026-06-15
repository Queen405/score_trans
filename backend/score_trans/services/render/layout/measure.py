from __future__ import annotations

from typing import Any

from ..models.layout import BeatLayout, MeasureLayout, RenderItem
from ..options import RenderOptions
from ..parsing.tokens import _token_duration
from .beat import _beat_visual_width


def _measure_layout(
    source: Any,
    number: str | int,
    grouped: list[list[RenderItem]],
    options: RenderOptions,
    errors: list[str] | None = None,
) -> MeasureLayout:
    beats = [
        BeatLayout(items=items, width=_beat_visual_width(items, options))
        for items in grouped
    ]
    natural = 42 + sum(beat.width for beat in beats) + max(0, len(beats) - 1) * options.beat_gap
    return MeasureLayout(
        source=source,
        number=number,
        beats=beats,
        width=max(options.min_measure_width, min(float(options.max_measure_width), natural)),
        errors=errors or [],
    )


def _score_measure_layout(measure, options: RenderOptions) -> MeasureLayout:
    from ..items.grouping import _measure_render_items

    fallback_beats = len(getattr(measure, "beats", [])) or 1
    beat_count = max(1, getattr(measure, "beats_per_measure", fallback_beats))
    grouped = _measure_render_items(measure, beat_count)
    while len(grouped) < beat_count:
        grouped.append([])
    return _measure_layout(
        measure,
        measure.display_number,
        grouped,
        options,
        errors=list(getattr(measure, "validation_errors", [])),
    )


def _text_measure_layout(measure: str, number: int, beat_count: int, options: RenderOptions) -> MeasureLayout:
    tokens = measure.split() or ["0"]
    grouped: list[list[RenderItem]] = [[] for _ in range(max(1, beat_count))]
    cursor = _token_duration("0") * 0
    from fractions import Fraction
    cursor = Fraction(0, 1)
    for token in tokens:
        index = min(len(grouped) - 1, max(0, int(cursor)))
        grouped[index].append(RenderItem(token=token, duration=_token_duration(token)))
        cursor += _token_duration(token)
    return _measure_layout(measure, number, grouped, options)
