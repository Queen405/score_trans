from __future__ import annotations

from fractions import Fraction

from ....models.score import Measure


def beat_group_boundaries(measure: Measure) -> list[Fraction]:
    """Publication beam groups, in quarter-note time (not parser beat slots)."""
    count = measure.beats_per_measure
    unit = Fraction(4, max(1, measure.beat_type))
    if measure.beat_type == 8 and count in (5, 7):
        starts = {
            event.start
            for event in measure.events
            if event.start is not None
            and any(
                beam.number == "1" and beam.status == "begin" for beam in event.beams
            )
        }
        stops = {
            event.start + event.duration
            for event in measure.events
            if event.start is not None
            and any(beam.number == "1" and beam.status == "end" for beam in event.beams)
        }
        if Fraction(0) in starts and count * unit in stops:
            return sorted({*starts, *stops})
    if measure.beat_type == 8 and count == 3:
        groups = [3]
    elif measure.beat_type == 8 and count >= 6 and count % 3 == 0:
        groups = [3] * (count // 3)
    elif measure.beat_type == 8 and count in (5, 7):
        groups = [2] * ((count - 3) // 2) + [3]
    else:
        groups = [1] * max(1, count)
    end = max(measure.duration, count * unit)
    result = [Fraction(0)]
    for group in groups:
        result.append(result[-1] + group * unit)
    # Overfull input still has an ordered time axis and visible beat groups.
    step = groups[-1] * unit
    while result[-1] < end:
        result.append(result[-1] + step)
    return result
