from __future__ import annotations

from fractions import Fraction
from math import ceil
from typing import Any

from ..models.layout import BeatLayout, MeasureLayout, RenderItem
from ..options import RenderOptions
from ..parsing.tokens import _parse_chord_token, _token_duration, _token_slashes
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
    natural = (
        42
        + sum(beat.width for beat in beats)
        + max(0, len(beats) - 1) * options.beat_gap
    )
    min_width, ideal_width, complexity = _measure_width_targets(beats, natural, options)
    return MeasureLayout(
        source=source,
        number=number,
        beats=beats,
        width=ideal_width,
        min_width=min_width,
        ideal_width=ideal_width,
        complexity=complexity,
        errors=errors or [],
    )


def _score_measure_layout(measure, options: RenderOptions) -> MeasureLayout:
    from ..items.grouping import _measure_render_items

    fallback_beats = len(getattr(measure, "beats", [])) or 1
    declared_beats = max(1, getattr(measure, "beats_per_measure", fallback_beats))
    beat_count = _visual_beat_count(measure, declared_beats)
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


def _visual_beat_count(measure: Any, declared_beats: int) -> int:
    beat_type = getattr(measure, "beat_type", 4)
    beat_duration = Fraction(4, beat_type)
    duration = getattr(measure, "duration", None)
    if duration is None or duration <= 0:
        return declared_beats
    measured = ceil(duration / beat_duration)
    return max(declared_beats, measured)


def _measure_width_targets(
    beats: list[BeatLayout],
    natural: float,
    options: RenderOptions,
) -> tuple[float, float, float]:
    if not options.compact_measure_layout:
        width = max(
            options.min_measure_width, min(float(options.max_measure_width), natural)
        )
        return width, width, 1.0

    item_count = sum(len(beat.items) for beat in beats)
    max_items_per_beat = max((len(beat.items) for beat in beats), default=0)
    beamed_count = sum(
        1 for beat in beats for item in beat.items if _token_slashes(item.token) > 0
    )
    chord_count = sum(
        1
        for beat in beats
        for item in beat.items
        if _parse_chord_token(item.token.strip().strip("()~")) is not None
    )
    complexity = (
        1.0
        + max(0, max_items_per_beat - 1) * 0.38
        + beamed_count * 0.035
        + chord_count * 0.045
    )
    base_min = max(float(options.min_measure_width), natural * 0.9)
    if max_items_per_beat >= 4:
        base_min = max(float(options.min_measure_width) * 1.9, natural * 0.92)
    elif max_items_per_beat >= 2:
        base_min = max(float(options.min_measure_width) * 1.04, natural * 0.88)
    elif item_count <= len(beats):
        base_min = max(float(options.min_measure_width), natural * 0.9)
    min_width = min(float(options.max_measure_width), base_min)
    ideal_width = max(min_width, min(float(options.max_measure_width), natural))
    return min_width, ideal_width, complexity


def _text_measure_layout(
    measure: str, number: int, beat_count: int, options: RenderOptions
) -> MeasureLayout:
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
