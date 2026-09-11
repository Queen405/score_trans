from __future__ import annotations

from fractions import Fraction

from ..models.score import Event, JianpuScore, Measure


def score_parts(scores: list[JianpuScore]) -> list[list[JianpuScore]]:
    """Join the nth staff on each source page without changing the input."""
    if not scores:
        return []
    if not any(score.part_count > 1 or score.part_index > 0 for score in scores):
        return [scores]
    pages: dict[int, list[JianpuScore]] = {}
    for score in scores:
        pages.setdefault(score.page_index, []).append(score)
    parts: dict[int, list[JianpuScore]] = {}
    for page in sorted(pages):
        for rank, score in enumerate(sorted(pages[page], key=lambda s: s.part_index)):
            parts.setdefault(rank, []).append(score)
    return list(parts.values())


def event_onsets(measure: Measure) -> list[tuple[Fraction, Event]]:
    cursor = Fraction(0)
    result: list[tuple[Fraction, Event]] = []
    for event in measure.events:
        start = event.start if event.start is not None else cursor
        result.append((start, event))
        cursor = start + event.duration
    return result


def measure_boundaries(cells: list[list[Measure | None]]) -> list[Fraction]:
    """Quarter-note positions, including rests and the longest staff per bar."""
    boundaries = [Fraction(0)]
    for measures in cells:
        span = max(
            (
                max(
                    m.duration,
                    max(
                        (start + e.duration for start, e in event_onsets(m)),
                        default=Fraction(0),
                    ),
                )
                for m in measures
                if m is not None
            ),
            default=Fraction(0),
        )
        boundaries.append(boundaries[-1] + span)
    return boundaries


def to_tick(quarters: Fraction, ppq: int) -> int:
    # Quantize absolute positions, never accumulate individually rounded notes.
    return round(quarters * ppq)
