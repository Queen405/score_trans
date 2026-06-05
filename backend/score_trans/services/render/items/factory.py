from __future__ import annotations

from fractions import Fraction

from ....models.score import JianpuEvent
from ..models.layout import RenderItem
from ..parsing.events import _duration_token, _event_token


def _event_to_item(event: JianpuEvent) -> RenderItem:
    token = event.source_token or (_duration_token("0", event.duration) if event.kind == "rest" else _event_token(event))
    return RenderItem(
        token=token,
        duration=event.duration,
        generated=event.generated,
        start=event.start,
        lyric=event.lyric,
        tie_start=event.tie_start,
        tie_stop=event.tie_stop,
        slur_start=event.slur_start,
        slur_stop=event.slur_stop,
        dynamic=event.dynamic,
        articulation=event.articulation,
        articulations=list(getattr(event, "articulations", []) or ([event.articulation] if event.articulation else [])),
        ornaments=list(getattr(event, "ornaments", [])),
        technical=list(getattr(event, "technical", [])),
    )


def _events_to_beats(events: list[JianpuEvent], beat_count: int, beat_duration: Fraction):
    from ....models.score import JianpuBeat

    beats = [JianpuBeat(index=index + 1, duration=beat_duration) for index in range(max(1, beat_count))]
    cursor = Fraction(0, 1)
    for event in events:
        start = event.start if event.start is not None else cursor
        index = min(len(beats) - 1, max(0, int(start / beat_duration)))
        beats[index].events.append(event)
        cursor = start + event.duration
    return beats
