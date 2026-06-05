from __future__ import annotations

from fractions import Fraction
from typing import Any

from ....models.score import JianpuEvent
from ..models.layout import RenderItem
from ..parsing.events import _duration_token, _note_body_token
from .factory import _event_to_item


def _measure_render_items(measure: Any, beat_count: int) -> list[list[RenderItem]]:
    beat_type = getattr(measure, "beat_type", 4)
    beat_duration = Fraction(4, beat_type)
    grouped: list[list[RenderItem]] = [[] for _ in range(max(1, beat_count))]

    events = list(getattr(measure, "events", []))
    if not events:
        measure_beats = list(getattr(measure, "beats", []))
        if measure_beats:
            for index, beat in enumerate(measure_beats[:beat_count]):
                grouped[index].extend(_event_to_item(event) for event in beat.events)
        return grouped

    cursor = Fraction(0, 1)
    for event in events:
        start = event.start if event.start is not None else cursor
        if event.kind == "rest" and event.duration > beat_duration:
            for beat_index, item in _split_rest_across_beats(event, start, beat_count, beat_duration):
                grouped[beat_index].append(item)
        elif event.kind == "note" and event.duration > beat_duration:
            remaining = event.duration
            item_start = start
            first = True
            while remaining > 0:
                chunk = min(remaining, beat_duration)
                beat_index = min(beat_count - 1, max(0, int(item_start / beat_duration)))
                token = _note_body_token(event) if first else "-"
                grouped[beat_index].append(RenderItem(
                    token=token,
                    duration=chunk,
                    start=item_start,
                    generated=event.generated,
                    lyric=event.lyric if first else None,
                    tie_start=event.tie_start if first else False,
                    tie_stop=event.tie_stop if first else False,
                    slur_start=event.slur_start if first else False,
                    slur_stop=event.slur_stop if first else False,
                    dynamic=event.dynamic,
                    articulation=event.articulation,
                    articulations=list(getattr(event, "articulations", []) or ([event.articulation] if event.articulation else [])),
                    ornaments=list(getattr(event, "ornaments", [])),
                    technical=list(getattr(event, "technical", [])),
                ))
                remaining -= chunk
                item_start += chunk
                first = False
        else:
            beat_index = min(beat_count - 1, max(0, int(start / beat_duration)))
            grouped[beat_index].append(_event_to_item(event))
        cursor = start + event.duration
    return grouped


def _split_rest_across_beats(
    event: JianpuEvent,
    start: Fraction,
    beat_count: int,
    beat_duration: Fraction,
) -> list[tuple[int, RenderItem]]:
    pieces: list[tuple[int, RenderItem]] = []
    remaining = event.duration
    cursor = start
    while remaining > 0:
        beat_index = min(beat_count - 1, max(0, int(cursor / beat_duration)))
        beat_end = Fraction(beat_index + 1, 1) * beat_duration
        chunk = min(remaining, beat_end - cursor if beat_end > cursor else remaining)
        pieces.append(
            (
                beat_index,
                RenderItem(token=_duration_token("0", chunk), duration=chunk, generated=event.generated, start=cursor),
            )
        )
        remaining -= chunk
        cursor += chunk
    return pieces
