from __future__ import annotations

from fractions import Fraction

from ..models.playback import MeasureVisit
from ..models.score import Event, JianpuScore, Measure
from .endings import EndingSpan, ending_pass_numbers, ending_spans


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


def _house_numbers_per_cell(
    cells: list[list[Measure | None]],
) -> dict[int, str]:
    """每小节所属房子的规范化编号；同时校验各声部房子标记一致。

    房子跨度由 domain.endings.ending_spans 从边界标记扫描，下标与 cells 对齐。
    声部间不一致时抛 ValueError（与反复次数不一致的策略相同）。
    """
    part_count = max((len(cell) for cell in cells), default=0)
    if part_count == 0:
        return {}
    spans_by_part: list[list[EndingSpan]] = [
        ending_spans([cell[part] if part < len(cell) else None for cell in cells])
        for part in range(part_count)
    ]

    def number_at(spans: list[EndingSpan], index: int) -> str | None:
        return next(
            (span.number for span in spans if span.start <= index <= span.stop),
            None,
        )

    reference = spans_by_part[0]
    for spans in spans_by_part[1:]:
        for index in range(len(cells)):
            if number_at(spans, index) != number_at(reference, index):
                raise ValueError(f"第 {index + 1} 小节各声部的跳房子标记不一致")
    return {
        index: span.number
        for span in reference
        for index in range(span.start, span.stop + 1)
    }


def _has_repeat_start(measures: list[Measure | None]) -> bool:
    return any(measure is not None and measure.repeat_start for measure in measures)


def _has_repeat_end(measures: list[Measure | None]) -> bool:
    return any(measure is not None and measure.repeat_end for measure in measures)


def _has_section_end(measures: list[Measure | None]) -> bool:
    return any(measure is not None and measure.section_end for measure in measures)


def _next_repeat_end(
    cells: list[list[Measure | None]], start: int, *, allow_forward: bool
) -> int | None:
    for index in range(start, len(cells)):
        if _has_repeat_end(cells[index]):
            return index
        if index > start and _has_section_end(cells[index - 1]):
            return None
        if not allow_forward and _has_repeat_start(cells[index]):
            return None
        if allow_forward and index > start and _has_repeat_start(cells[index]):
            # Nested repeats retain the existing unsupported/linear-fallback scope.
            return None
    return None


def _repeat_count(measures: list[Measure | None]) -> int:
    counts = {
        int(measure.repeat_count)
        for measure in measures
        if measure is not None and measure.repeat_end and measure.repeat_count > 1
    }
    if len(counts) > 1:
        raise ValueError("反复次数不一致")
    return max(2, next(iter(counts), 2))


def _ending_tail_end(
    cells: list[list[Measure | None]], house_at: dict[int, str], repeat_end: int
) -> int:
    """Return the first cell after the alternate-ending tail of a repeat group."""
    index = repeat_end + 1
    while index < len(cells):
        if index not in house_at or _has_repeat_start(cells[index]):
            break
        index += 1
        if _has_section_end(cells[index - 1]):
            break
    return index


def playback_visits(cells: list[list[Measure | None]]) -> list[MeasureVisit]:
    """Expand repeats and volta endings while retaining original cell identities.

    Each pass is built independently from the repeat body plus its alternate-ending
    tail. This is what allows separate ``{1.}``, ``{2.}``, ``{3.}`` houses to work
    with ``*3``; shared houses such as ``{1,2.}`` follow the same rule. Houses
    outside a repeat group are always linear.
    """
    boundaries = measure_boundaries(cells)
    house_at = _house_numbers_per_cell(cells)

    def plays(index: int, pass_number: int) -> bool:
        house = house_at.get(index)
        return house is None or pass_number in ending_pass_numbers(house)

    sequence: list[int] = []
    index = 0
    section_start = 0
    while index < len(cells):
        has_forward = _has_repeat_start(cells[index])
        repeat_end = (
            _next_repeat_end(cells, index, allow_forward=True)
            if has_forward
            else _next_repeat_end(cells, index, allow_forward=False)
            if index == section_start
            else None
        )
        if repeat_end is None:
            sequence.append(index)
            index += 1
            if _has_section_end(cells[index - 1]):
                section_start = index
            continue

        count = _repeat_count(cells[repeat_end])
        tail_end = _ending_tail_end(cells, house_at, repeat_end)
        for pass_number in range(1, count + 1):
            sequence.extend(
                cell_index
                for cell_index in range(index, repeat_end)
                if plays(cell_index, pass_number)
            )
            if plays(repeat_end, pass_number):
                sequence.append(repeat_end)
            sequence.extend(
                cell_index
                for cell_index in range(repeat_end + 1, tail_end)
                if plays(cell_index, pass_number)
            )
        index = tail_end
        section_start = index

    visits: list[MeasureVisit] = []
    cursor = Fraction(0)
    for source_index in sequence:
        duration = boundaries[source_index + 1] - boundaries[source_index]
        visits.append(
            MeasureVisit(source_index, cursor, boundaries[source_index], duration)
        )
        cursor += duration
    return visits
