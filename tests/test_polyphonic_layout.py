from __future__ import annotations

import re
from fractions import Fraction
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from score_trans.domain.jianpu import parse_jianpu_score
from score_trans.domain.parse.jianpu_text import parse_jianpu_parts
from score_trans.models.score import JianpuScore
from score_trans.services.render.engraving.renderer import (
    PublicationPage,
    PublicationRenderer,
)
from score_trans.services.render.engraving.style import PublicationStyle


MELODY = "(q6 q#1' q6 q#1' ^> h3') |"
BASS = "0 ^. [3+#1] ^. [3+#1] ^. [3+#1] & w6, |"


def _scores(*bodies: str) -> list[JianpuScore]:
    scores = [parse_jianpu_score("1=C\n4/4\n" + body) for body in bodies]
    for index, score in enumerate(scores, 1):
        score.part_index = index
        score.part_count = len(scores)
    return scores


def _notes(page: PublicationPage) -> list[ET.Element]:
    return [
        n
        for n in ET.fromstring(page.svg).iter()
        if "playback-note" in n.attrib.get("class", "").split()
    ]


def _x(note: ET.Element) -> float:
    digits = [
        n
        for n in note.iter()
        if n.attrib.get("aria-label", "") in "01234567" and n.attrib.get("aria-label")
    ]
    return float(re.search(r"translate\(([-\d.]+)", digits[0].attrib["transform"])[1])


def _box(note: ET.Element) -> tuple[float, ...]:
    return tuple(map(float, note.attrib["data-bbox"].split()))


def test_melody_spacing_and_cross_part_onsets_with_polyphonic_bass() -> None:
    page = PublicationRenderer().render_scores(_scores(MELODY, BASS))[0]
    notes = _notes(page)
    melody = [n for n in notes if n.attrib["data-part-index"] == "0"]
    xs = [_x(n) for n in melody]
    assert all(b - a >= 20 for a, b in zip(xs, xs[1:]))
    positions = {}
    for n in notes:
        tick = n.attrib["data-playback-tick"]
        if tick in positions:
            assert _x(n) == pytest.approx(positions[tick], abs=0.01)
        positions[tick] = _x(n)


def test_chord_and_octave_voices_have_clear_ink_gap() -> None:
    page = PublicationRenderer().render_scores(_scores(BASS))[0]
    notes = _notes(page)
    chords = [n for n in notes if n.attrib["data-note-token"].startswith("[")]
    bass = next(n for n in notes if n.attrib["data-note-token"] == "w6,")
    chord_bottom = max(_box(n)[1] + _box(n)[3] for n in chords)
    assert _box(bass)[1] - chord_bottom >= 18 - 0.01


def test_polyphonic_upper_part_pushes_next_part_down() -> None:
    body = "w[1+3+5] & w[1,+3,+5,] & w1,, |"
    page = PublicationRenderer().render_scores(_scores(body, "w2 |"))[0]
    notes = _notes(page)
    upper = [n for n in notes if n.attrib["data-part-index"] == "0"]
    lower = next(n for n in notes if n.attrib["data-part-index"] == "1")
    assert _box(lower)[1] - max(_box(n)[1] + _box(n)[3] for n in upper) >= 18


def test_full_piano_fixture_remains_aligned_and_inside_pages() -> None:
    text = (Path(__file__).parent / "fixtures/piano_polyphonic.jianpu").read_text(
        encoding="utf-8"
    )
    parts = parse_jianpu_parts(text)
    scores = [part.score for part in parts]
    pages = PublicationRenderer().render_scores(scores)
    assert sum(len(s.measures) for s in scores) == 32
    assert sum(len(_notes(p)) for p in pages) == sum(
        e.kind == "note" for s in scores for m in s.measures for e in m.events
    )
    for page in pages:
        positions = {}
        for n in _notes(page):
            tick = n.attrib["data-playback-tick"]
            if tick in positions:
                assert _x(n) == pytest.approx(positions[tick], abs=0.01)
            positions[tick] = _x(n)
            x, y, w, h = _box(n)
            assert x >= 0 and y >= 0
            assert x + w <= page.scene.width
            assert y + h < page.scene.height - 48


def _baseline(note: ET.Element) -> float:
    digit = next(
        n for n in note.iter() if n.attrib.get("aria-label") in tuple("01234567")
    )
    return float(
        re.search(r"translate\([-\d.]+ ([-\d.]+)", digit.attrib["transform"])[1]
    )


def test_absent_voice_keeps_baseline_and_spanner_identity_across_pages() -> None:
    from score_trans.models.score import Event, JianpuPitch, JianpuScore, Measure

    def note(voice: str, degree: int, source: str, **kwargs: bool) -> Event:
        return Event(
            kind="note",
            duration=Fraction(4),
            start=Fraction(0),
            voice=voice,
            pitches=[JianpuPitch(degree)],
            source_ids=[source],
            source_roles={
                k: [source] for k in ("slur_start", "slur_stop") if kwargs.get(k)
            },
            **kwargs,
        )

    score = JianpuScore(
        measures=[
            Measure(
                "1",
                duration=Fraction(4),
                events=[
                    note("1", 1, "upper-start"),
                    note("2", 5, "lower-start", slur_start=True),
                ],
            ),
            Measure("2", duration=Fraction(4), events=[note("2", 5, "lower-only")]),
            Measure(
                "3",
                duration=Fraction(4),
                new_page=True,
                events=[
                    note("1", 1, "upper-end"),
                    note("2", 5, "lower-end", slur_stop=True),
                ],
            ),
        ]
    )
    pages = PublicationRenderer().render_scores([score])
    assert len(pages) == 2
    first = {n.attrib["data-source-id"]: n for n in _notes(pages[0])}
    assert _baseline(first["lower-only"]) == pytest.approx(
        _baseline(first["lower-start"])
    )
    last = {n.attrib["data-source-id"]: n for n in _notes(pages[1])}
    assert _baseline(last["lower-end"]) > _baseline(last["upper-end"]) + 38
    spans = [
        n
        for n in ET.fromstring(pages[1].svg).iter()
        if n.attrib.get("data-span-kind") == "slur"
    ]
    assert spans
    assert all("upper-end" not in n.attrib.get("data-source-ids", "") for n in spans)
    assert any("lower-end" in n.attrib.get("data-source-ids", "") for n in spans)
    for n in spans:
        _, y, _, h = map(float, n.attrib["data-bbox"].split())
        assert y + h > _baseline(last["upper-end"])


def test_rhythm_lines_use_each_voice_baseline() -> None:
    page = PublicationRenderer().render_scores(
        _scores("q1 q1 q1 q1 & q5, q5, q5, q5, |")
    )[0]
    notes = _notes(page)
    upper = [n for n in notes if n.attrib["data-note-token"] == "q1"]
    lower = [n for n in notes if n.attrib["data-note-token"] == "q5,"]
    lines = [
        n
        for n in ET.fromstring(page.svg).iter()
        if n.tag.endswith("line") and "duration-line" in n.attrib.get("class", "")
    ]
    assert lines
    ys = {float(n.attrib["y1"]) for n in lines}
    assert any(_baseline(upper[0]) < y < _baseline(lower[0]) for y in ys)
    assert any(y > _baseline(lower[0]) for y in ys)


def test_missing_onsets_are_resolved_without_mutating_music_events() -> None:
    from score_trans.models.score import Event, JianpuPitch, JianpuScore, Measure

    events = [
        Event(kind="note", duration=d, pitches=[JianpuPitch(1)])
        for d in [Fraction(2), Fraction(1), Fraction(1)]
    ]
    score = JianpuScore(measures=[Measure("1", duration=Fraction(4), events=events)])
    page = PublicationRenderer().render_scores([score])[0]
    assert [n.attrib["data-playback-tick"] for n in _notes(page)] == [
        "0",
        "960",
        "1440",
    ]
    assert all(e.start is None for e in events)


@pytest.mark.parametrize("scale", [0.65, 1.0])
def test_full_fixture_geometry_with_small_pages_and_scale(scale: float) -> None:
    from dataclasses import replace

    text = (Path(__file__).parent / "fixtures/piano_polyphonic.jianpu").read_text(
        encoding="utf-8"
    )
    scores = [p.score for p in parse_jianpu_parts(text)]
    renderer = PublicationRenderer(
        style=replace(PublicationStyle(), page_height=950), coordinate_scale=scale
    )
    pages = renderer.render_scores(scores)
    assert len(pages) > 1
    for p in pages:
        assert not [
            issue
            for issue in p.scene.geometry_issues
            if issue["kind"] in ("page-overflow", "event-overlap")
        ]


def test_sustained_voice_overlaps_later_entry_even_after_visual_split() -> None:
    from score_trans.models.score import Event, JianpuPitch, JianpuScore, Measure

    events = [
        Event(
            kind="note",
            duration=Fraction(1),
            start=Fraction(2),
            voice="1",
            pitches=[JianpuPitch(3)],
            source_ids=["later"],
        ),
        Event(
            kind="note",
            duration=Fraction(4),
            start=Fraction(0),
            voice="2",
            pitches=[JianpuPitch(6, octave=-1)],
            source_ids=["sustain"],
        ),
    ]
    score = JianpuScore(measures=[Measure("1", duration=Fraction(4), events=events)])
    notes = {
        n.attrib["data-source-id"]: n
        for n in _notes(PublicationRenderer().render_scores([score])[0])
    }
    assert _baseline(notes["sustain"]) > _baseline(notes["later"]) + 38
    assert _x(notes["sustain"]) < _x(notes["later"])


def test_full_fixture_playback_and_source_mapping_is_preserved() -> None:
    from score_trans.domain.playback_timeline import measure_boundaries, to_tick
    from score_trans.config.settings import MIDI_TICKS_PER_BEAT

    text = (Path(__file__).parent / "fixtures/piano_polyphonic.jianpu").read_text(
        encoding="utf-8"
    )
    scores = [p.score for p in parse_jianpu_parts(text)]
    boundaries = measure_boundaries(
        [list(measures) for measures in zip(*(s.measures for s in scores), strict=True)]
    )
    expected = {}
    for part, score in enumerate(scores):
        for index, measure in enumerate(score.measures):
            for event in measure.events:
                if event.kind != "note":
                    continue
                tick = to_tick(boundaries[index] + event.start, MIDI_TICKS_PER_BEAT)
                key = (part, tick, event.source_token)
                expected[key] = (event.source_start_utf16, event.source_end_utf16)
    ticks = sorted({key[1] for key in expected})
    groups = {tick: index for index, tick in enumerate(ticks)}
    pages = PublicationRenderer().render_scores(scores)
    seen = {}
    indices = []
    for page in pages:
        for note in _notes(page):
            part = int(note.attrib["data-part-index"])
            tick = int(note.attrib["data-playback-tick"])
            assert int(note.attrib["data-note-group"]) == groups[tick]
            indices.append(int(note.attrib["data-note-index"]))
            seen[(part, tick, note.attrib["data-note-token"])] = (
                int(note.attrib["data-source-start-utf16"]),
                int(note.attrib["data-source-end-utf16"]),
            )
    assert seen == expected
    assert indices == list(range(len(expected)))


def test_polyphonic_lyrics_are_measured_at_their_shifted_position() -> None:
    from score_trans.services.render.engraving.fonts import font_registry

    scores = _scores(BASS)
    scores[0].measures[0].events[1].lyric = "测试"
    scores[0].measures[0].events[1].source_ids = ["lyric-note"]
    page = PublicationRenderer().render_scores(scores)[0]
    note = next(
        n for n in _notes(page) if n.attrib.get("data-source-id") == "lyric-note"
    )
    lyric = next(n for n in note.iter() if "lyric" in n.attrib.get("class", "").split())
    baseline = float(
        re.search(r"translate\([-\d.]+ ([-\d.]+)", lyric.attrib["transform"])[1]
    )
    bottom = (
        baseline + font_registry().ink_bounds("测试", PublicationStyle().lyric_size)[3]
    )
    box = _box(note)
    assert box[1] + box[3] >= bottom - 0.01
    bass = next(n for n in _notes(page) if n.attrib["data-note-token"] == "w6,")
    assert baseline > _box(bass)[1] + _box(bass)[3]
