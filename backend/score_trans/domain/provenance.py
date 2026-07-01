from __future__ import annotations

from ..models.provenance.schemas import TextAnchor
from ..models.score import Event, JianpuScore


def apply_text_anchors(score: JianpuScore, anchors: list[TextAnchor]) -> None:
    """Attach still-valid editor anchors to parsed events for SVG rendering."""
    events = [
        event
        for measure in score.measures
        for event in measure.events
        if event.source_start_utf16 is not None and event.source_end_utf16 is not None
    ]
    events.sort(key=lambda event: event.source_start_utf16 or 0)

    for anchor in anchors:
        if not anchor.valid:
            continue
        event = _event_for_anchor(events, anchor)
        if event is None:
            continue
        if anchor.source_id not in event.source_ids:
            event.source_ids.append(anchor.source_id)
        role_sources = event.source_roles.setdefault(anchor.role, [])
        if anchor.source_id not in role_sources:
            role_sources.append(anchor.source_id)


def _event_for_anchor(events: list[Event], anchor: TextAnchor) -> Event | None:
    for event in events:
        start = event.source_start_utf16
        end = event.source_end_utf16
        if start is None or end is None:
            continue
        if start <= anchor.start_utf16 < end or (
            anchor.start_utf16 <= start < anchor.end_utf16
        ):
            return event

    if anchor.role in {
        "articulation",
        "ornament",
        "technical",
        "dynamic",
        "slur",
        "tuplet",
    }:
        return next(
            (
                event
                for event in events
                if event.source_start_utf16 is not None
                and event.source_start_utf16 >= anchor.end_utf16
                and event.source_start_utf16 - anchor.end_utf16 <= 16
            ),
            None,
        )
    return None
