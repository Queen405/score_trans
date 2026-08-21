from __future__ import annotations

from fractions import Fraction

from score_trans.models.score import Event, JianpuPitch, JianpuScore, Measure


def single_measure_score(*events: Event, duration: Fraction = Fraction(4, 1)) -> JianpuScore:
    return JianpuScore(
        measures=[Measure("1", duration=duration, events=list(events))]
    )


def accidental_edge_score() -> JianpuScore:
    events = [
        Event(
            kind="note",
            duration=Fraction(1),
            pitches=[JianpuPitch(1, accidental=Fraction(1))],
            start=Fraction(0),
        ),
        Event(
            kind="note",
            duration=Fraction(1),
            pitches=[JianpuPitch(7, accidental=Fraction(-1))],
            start=Fraction(3),
        ),
    ]
    return single_measure_score(*events)


def dense_chord_score() -> JianpuScore:
    event = Event(
        kind="note",
        duration=Fraction(1, 4),
        pitches=[
            JianpuPitch(1, octave=1),
            JianpuPitch(3),
            JianpuPitch(5),
            JianpuPitch(7, octave=-1),
        ],
        start=Fraction(0),
    )
    return single_measure_score(event)


def long_duration_score() -> JianpuScore:
    return single_measure_score(
        Event(
            kind="note",
            duration=Fraction(3, 2),
            pitches=[JianpuPitch(3)],
            dotted=1,
            start=Fraction(0),
        ),
        duration=Fraction(4),
    )


def overfull_tail_duration_score() -> JianpuScore:
    events = [
        Event(
            kind="note",
            duration=Fraction(1),
            pitches=[JianpuPitch(1)],
            start=Fraction(0),
        ),
        Event(
            kind="note",
            duration=Fraction(1),
            pitches=[JianpuPitch(3)],
            start=Fraction(1),
        ),
        Event(
            kind="note",
            duration=Fraction(1),
            pitches=[JianpuPitch(5)],
            start=Fraction(2),
        ),
        Event(
            kind="note",
            duration=Fraction(2),
            pitches=[JianpuPitch(7)],
            start=Fraction(3),
        ),
    ]
    return single_measure_score(*events)


def staccato_score() -> JianpuScore:
    return single_measure_score(
        Event(
            kind="note",
            duration=Fraction(1),
            pitches=[JianpuPitch(3)],
            articulation="staccato",
            articulations=["staccato"],
        )
    )
