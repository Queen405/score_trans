from __future__ import annotations

from fractions import Fraction

import score_trans.domain.write.jianpu_text as jianpu_writer
from score_trans.domain.write.jianpu_text import score_to_jianpu_document
from score_trans.models.score import Event, JianpuPitch, JianpuScore, Measure


def _utf16_slice(text: str, start: int, end: int) -> str:
    encoded = text.encode("utf-16-le")
    return encoded[start * 2 : end * 2].decode("utf-16-le")


def _tuplet_events(count: int, degrees: list[int]) -> list[Event]:
    return [
        Event(
            kind="note",
            duration=Fraction(1, count),
            pitches=[JianpuPitch(degree=degree, source_id=f"s1:i{100 + index}")],
            tuplet_start=index == 0,
            tuplet_count=count if index == 0 else None,
        )
        for index, degree in enumerate(degrees)
    ]


def _make_measure(events: list[Event]) -> Measure:
    return Measure(
        source_number="1",
        events=events,
        target_key="C",
        beats_per_measure=4,
        beat_type=4,
    )


def test_triplet_group_anchors_every_note() -> None:
    events = [
        *_tuplet_events(3, [1, 2, 3]),
        Event(
            kind="note",
            duration=Fraction(1, 1),
            pitches=[JianpuPitch(degree=4, source_id="s1:i200")],
        ),
    ]
    document = score_to_jianpu_document(JianpuScore(measures=[_make_measure(events)]))

    assert "$123$ 4 |" in document.text
    for index in range(3):
        anchor = next(
            a for a in document.anchors if a.source_id == f"s1:i{100 + index}"
        )
        assert _utf16_slice(document.text, anchor.start_utf16, anchor.end_utf16) == str(
            index + 1
        )
        assert anchor.start_utf16 == document.text.index("$") + 1 + index
    tail = next(a for a in document.anchors if a.source_id == "s1:i200")
    assert _utf16_slice(document.text, tail.start_utf16, tail.end_utf16) == "4"


def test_measure_level_tempo_line_keeps_following_note_anchors_aligned() -> None:
    first = Event(
        kind="note",
        duration=Fraction(4),
        pitches=[JianpuPitch(degree=1, source_id="s1:first")],
    )
    second = Event(
        kind="note",
        duration=Fraction(4),
        pitches=[JianpuPitch(degree=5, source_id="s1:second")],
    )
    first_measure = _make_measure([first])
    first_measure.tempo = 120
    second_measure = _make_measure([second])
    second_measure.source_number = "2"
    second_measure.tempo = 80

    document = score_to_jianpu_document(
        JianpuScore(tempo=120, measures=[first_measure, second_measure])
    )

    assert "\ntempo=80\n" in document.text
    for source_id, token in (("s1:first", "1"), ("s1:second", "5")):
        anchor = next(a for a in document.anchors if a.source_id == source_id)
        assert (
            _utf16_slice(document.text, anchor.start_utf16, anchor.end_utf16) == token
        )


def test_cross_tuplet_slur_keeps_external_parenthesis_anchors() -> None:
    events = _tuplet_events(3, [1, 2, 3])
    events[0].slur_start = True
    events[0].source_roles = {"slur_start": ["s1:slur-start"]}
    tail = Event(
        kind="note",
        duration=Fraction(1, 1),
        pitches=[JianpuPitch(degree=4, source_id="s1:i200")],
        slur_stop=True,
        source_roles={"slur_stop": ["s1:slur-stop"]},
    )

    document = score_to_jianpu_document(
        JianpuScore(measures=[_make_measure([*events, tail])])
    )
    slur_anchors = {
        anchor.source_id: _utf16_slice(
            document.text,
            anchor.start_utf16,
            anchor.end_utf16,
        )
        for anchor in document.anchors
        if anchor.role == "slur"
    }

    assert "($123$ 4) |" in document.text
    assert slur_anchors == {"s1:slur-start": "(", "s1:slur-stop": ")"}


def test_sextuplet_group_anchors_every_note() -> None:
    events = _tuplet_events(6, [1, 2, 3, 4, 5, 6])
    document = score_to_jianpu_document(JianpuScore(measures=[_make_measure(events)]))

    assert "$123456$ |" in document.text
    anchored = {a.source_id for a in document.anchors if a.role == "note"}
    assert {f"s1:i{100 + index}" for index in range(6)} <= anchored


def test_mid_tuplet_miss_keeps_remaining_group_and_following_anchors() -> None:
    events = [
        *_tuplet_events(3, [1, 2, 3]),
        Event(
            kind="note",
            duration=Fraction(1, 1),
            pitches=[JianpuPitch(degree=4, source_id="s1:i200")],
        ),
    ]
    score = JianpuScore(measures=[_make_measure(events)])
    text = "1=C\n4/4\n$153$ 4 |"

    anchors = jianpu_writer._text_anchors_raw(score, text, accidental_mode="auto")

    assert all(anchor.source_id != "s1:i101" for anchor in anchors)
    first = next(a for a in anchors if a.source_id == "s1:i100")
    third = next(a for a in anchors if a.source_id == "s1:i102")
    tail = next(a for a in anchors if a.source_id == "s1:i200")
    assert text[first.start_utf16 : first.end_utf16] == "1"
    assert text[third.start_utf16 : third.end_utf16] == "3"
    assert third.start_utf16 == text.index("3")
    assert text[tail.start_utf16 : tail.end_utf16] == "4"
    assert tail.start_utf16 == text.rindex("4")


def test_first_tuplet_note_miss_keeps_remaining_group_anchors() -> None:
    events = _tuplet_events(3, [1, 2, 3])
    score = JianpuScore(measures=[_make_measure(events)])
    text = "1=C\n4/4\n$523$ |"

    anchors = jianpu_writer._text_anchors_raw(score, text, accidental_mode="auto")

    assert all(anchor.source_id != "s1:i100" for anchor in anchors)
    second = next(a for a in anchors if a.source_id == "s1:i101")
    third = next(a for a in anchors if a.source_id == "s1:i102")
    assert text[second.start_utf16 : second.end_utf16] == "2"
    assert text[third.start_utf16 : third.end_utf16] == "3"
    assert second.start_utf16 == text.index("2")
    assert third.start_utf16 == text.index("3")


def test_sextuplet_mid_group_miss_keeps_remaining_anchors() -> None:
    events = _tuplet_events(6, [1, 2, 3, 4, 5, 6])
    score = JianpuScore(measures=[_make_measure(events)])
    text = "1=C\n4/4\n$123x56$ |"

    anchors = jianpu_writer._text_anchors_raw(score, text, accidental_mode="auto")

    assert all(anchor.source_id != "s1:i103" for anchor in anchors)
    anchored = {a.source_id for a in anchors}
    assert {
        "s1:i100",
        "s1:i101",
        "s1:i102",
        "s1:i104",
        "s1:i105",
    } <= anchored
    last = next(a for a in anchors if a.source_id == "s1:i105")
    assert text[last.start_utf16 : last.end_utf16] == "6"
    assert last.start_utf16 == text.index("6")


def _nonlegacy_chord_sextuplet() -> list[Event]:
    def chord(index: int, degrees: tuple[int, int], **kwargs: object) -> Event:
        return Event(
            kind="note",
            duration=Fraction(1, 12),
            pitches=[
                JianpuPitch(degree=degrees[0], source_id=f"s1:i{200 + index * 2}"),
                JianpuPitch(
                    degree=degrees[1], octave=-1, source_id=f"s1:i{201 + index * 2}"
                ),
            ],
            tuplet_start=index == 0,
            tuplet_count=6 if index == 0 else None,
            **kwargs,  # type: ignore[arg-type]
        )

    return [
        chord(0, (4, 6)),
        chord(1, (6, 4), slur_start=True),
        chord(2, (4, 6)),
        chord(3, (6, 4), slur_stop=True),
        chord(4, (4, 6), dynamic="p"),
        chord(5, (6, 4), dynamic="p"),
    ]


def test_subbeat_tuplet_with_prefix_marks_anchors_every_pitch() -> None:
    document = score_to_jianpu_document(
        JianpuScore(measures=[_make_measure(_nonlegacy_chord_sextuplet())])
    )

    # Sub-beat group (total 1/2 beat): degrades to plain tokens, no $...$ wrap.
    assert "d[4+6,] (d[6+4,] d[4+6,] d[6+4,]) \\pd[4+6,] \\pd[6+4,]" in (document.text)
    assert "$" not in document.text
    anchored = {a.source_id for a in document.anchors if a.role == "note"}
    assert {f"s1:i{200 + n}" for n in range(12)} <= anchored
    first = next(a for a in document.anchors if a.source_id == "s1:i200")
    assert _utf16_slice(document.text, first.start_utf16, first.end_utf16) == "4"
    dynamic_anchors = [
        a for a in document.anchors if a.role == "dynamic" and a.source_id == ""
    ]
    assert not dynamic_anchors


def test_triplet_articulations_have_their_own_source_anchors() -> None:
    pitches = [
        JianpuPitch(degree=5, source_id="s1:i100"),
        JianpuPitch(degree=5, octave=-1, source_id="s1:i101"),
        JianpuPitch(degree=2, octave=-1, source_id="s1:i102"),
        JianpuPitch(degree=5, octave=-2, source_id="s1:i103"),
    ]
    events = [
        Event(
            kind="note",
            duration=Fraction(2, 3) if index < 3 else Fraction(1),
            pitches=pitches,
            articulations=["accent"],
            source_roles={"articulation": [f"s1:i{200 + index}"]},
            tuplet_start=index == 0,
            tuplet_count=3 if index == 0 else None,
            tuplet_index=index if index < 3 else 0,
            tuplet_stop=index == 2,
        )
        for index in range(4)
    ]
    document = score_to_jianpu_document(JianpuScore(measures=[_make_measure(events)]))

    assert (
        "$3:2;^>[5+5,+2,+5,,] ^>[5+5,+2,+5,,] ^>[5+5,+2,+5,,]$ ^> [5+5,+2,+5,,] |"
    ) in document.text
    accents = [anchor for anchor in document.anchors if anchor.role == "articulation"]
    assert [anchor.source_id for anchor in accents] == [
        "s1:i200",
        "s1:i201",
        "s1:i202",
        "s1:i203",
    ]
    assert len({anchor.start_utf16 for anchor in accents}) == 4
    assert all(
        _utf16_slice(document.text, anchor.start_utf16, anchor.end_utf16) == "^>"
        for anchor in accents
    )


def test_nonlegacy_tuplet_prefixed_event_positions_are_exact() -> None:
    document = score_to_jianpu_document(
        JianpuScore(measures=[_make_measure(_nonlegacy_chord_sextuplet())])
    )
    text = document.text

    slurred = next(a for a in document.anchors if a.source_id == "s1:i202")
    assert text[slurred.start_utf16 - 3 : slurred.start_utf16] == "(d["
    assert _utf16_slice(text, slurred.start_utf16, slurred.end_utf16) == "6"
    dynamic = next(a for a in document.anchors if a.source_id == "s1:i208")
    assert text[dynamic.start_utf16 - 4 : dynamic.start_utf16] == "\\pd["
    assert _utf16_slice(text, dynamic.start_utf16, dynamic.end_utf16) == "4"
