from __future__ import annotations

from fractions import Fraction

from ..models.playback import MeasureVisit
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


def score_onset_groups(cells: list[list[Measure | None]]) -> dict[Fraction, int]:
    boundaries = measure_boundaries(cells)
    starts = {
        boundaries[index] + start
        for index, measures in enumerate(cells)
        for measure in measures
        if measure is not None
        for start, event in event_onsets(measure)
        if event.kind == "note" and event.pitches
    }
    return {start: index for index, start in enumerate(sorted(starts))}


def playback_visits(cells: list[list[Measure | None]]) -> list[MeasureVisit]:
    """Expand the whole score once while retaining original cell identities."""
    boundaries = measure_boundaries(cells)
    sequence: list[int] = []
    repeat_start: int | None = None
    for index, measures in enumerate(cells):
        present = [measure for measure in measures if measure is not None]
        if any(measure.repeat_start for measure in present):
            repeat_start = len(sequence)
        sequence.append(index)
        endings = [measure for measure in present if measure.repeat_end]
        if endings:
            counts = {
                int(measure.repeat_count)
                for measure in endings
                if measure.repeat_count > 1
            }
            if len(counts) > 1:
                raise ValueError(f"第 {index + 1} 小节各声部的反复次数不一致")
            count = max(2, next(iter(counts), 2))
            section = sequence[repeat_start if repeat_start is not None else 0 :]
            sequence.extend(section * (count - 1))
            repeat_start = None
    visits: list[MeasureVisit] = []
    cursor = Fraction(0)
    for index in sequence:
        duration = boundaries[index + 1] - boundaries[index]
        visits.append(MeasureVisit(index, cursor, boundaries[index], duration))
        cursor += duration
    return visits
