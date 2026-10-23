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
        ending_spans(
            [cell[part] if part < len(cell) else None for cell in cells]
        )
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


def playback_visits(cells: list[list[Measure | None]]) -> list[MeasureVisit]:
    """Expand the whole score once while retaining original cell identities.

    跳房子（volta）语义：反复段第 k 遍只演奏编号列表含 k 的房子；
    第 k 遍无匹配房子时跳过段内所有房子；反复段之外（current_pass 为 None
    的线性区，例如从未进入任何反复段的孤立房子）永远线性播放。
    """
    boundaries = measure_boundaries(cells)
    house_at = _house_numbers_per_cell(cells)
    sequence: list[int] = []
    repeat_start: int | None = None
    current_pass: int | None = None
    for index, measures in enumerate(cells):
        present = [measure for measure in measures if measure is not None]
        if any(measure.repeat_start for measure in present):
            repeat_start = len(sequence)
            current_pass = 1
        house_number = house_at.get(index)
        if (
            house_number is None
            or current_pass is None
            or current_pass in ending_pass_numbers(house_number)
        ):
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
            for pass_number in range(2, count + 1):
                sequence.extend(
                    cell_index
                    for cell_index in section
                    if (house := house_at.get(cell_index)) is None
                    or pass_number in ending_pass_numbers(house)
                )
            repeat_start = None
            current_pass = count
    visits: list[MeasureVisit] = []
    cursor = Fraction(0)
    for index in sequence:
        duration = boundaries[index + 1] - boundaries[index]
        visits.append(MeasureVisit(index, cursor, boundaries[index], duration))
        cursor += duration
    return visits
