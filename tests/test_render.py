from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from fractions import Fraction
from itertools import pairwise
from pathlib import Path

from score_trans.domain.jianpu import parse_jianpu_score
from score_trans.exec.render.actions import _renumber_scores_continuously
from score_trans.models.score import (
    Beam,
    Event,
    JianpuPitch,
    JianpuScore,
    Measure,
    TextBlock,
)
from score_trans.services.render import PublicationRenderService, RenderOptions
from score_trans.services.render.engraving.fonts import font_registry
from score_trans.services.render.engraving.geometry import measure_event_ink
from score_trans.services.render.engraving.renderer import (
    _Anchor,
    _Cell,
    _draw_explicit_beam_level,
    _draw_rhythm_lines,
    _draw_rhythm_run,
    _duration_spring,
    _event_positions,
    _intrinsic_measure_width,
    _system_extra_height,
)
from score_trans.services.render.engraving.scene import BBox, PublicationScene
from score_trans.services.render.engraving.style import PublicationStyle
from score_trans.services.render.main import (
    render_jianpu_page_svg,
    render_jianpu_svg,
    render_score_page_svg,
    render_score_svg,
    render_scores_a4_pages,
)

from tests.fixtures.render_cases import (
    long_duration_score,
    overfull_tail_duration_score,
    staccato_score,
)


def _root(svg: str) -> ET.Element:
    return ET.fromstring(svg)


def _translate(node: ET.Element) -> tuple[float, float]:
    match = re.search(r"translate\(([-\d.]+) ([-\d.]+)\)", node.attrib["transform"])
    assert match is not None
    return float(match.group(1)), float(match.group(2))


def _scale(node: ET.Element) -> float:
    match = re.search(r"scale\(([-\d.]+)", node.attrib["transform"])
    assert match is not None
    return abs(float(match.group(1)))


def _text_box(node: ET.Element) -> tuple[float, float, float, float]:
    x, y = _translate(node)
    left, top, right, bottom = font_registry().ink_bounds(
        node.attrib["aria-label"], _scale(node)
    )
    return x + left, y + top, x + right, y + bottom


def _bbox(node: ET.Element) -> tuple[float, float, float, float]:
    return tuple(float(value) for value in node.attrib["data-bbox"].split())  # type: ignore[return-value]


def _node_bbox(node: ET.Element) -> tuple[float, float, float, float]:
    if node.attrib.get("data-bbox"):
        return _bbox(node)
    if node.tag.endswith("circle"):
        cx = float(node.attrib["cx"])
        cy = float(node.attrib["cy"])
        radius = float(node.attrib["r"])
        return cx - radius, cy - radius, radius * 2, radius * 2
    raise AssertionError(f"unsupported node bbox: {node.tag}")


def _assert_horizontal_clearance(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
    minimum: float = 0.0,
) -> None:
    left_x, _left_y, left_width, _left_height = left
    right_x, _right_y, _right_width, _right_height = right
    assert left_x + left_width + minimum <= right_x


def test_publication_renderer_is_the_only_engine() -> None:
    svg = render_jianpu_svg("title=春江\n1=C\n4/4\n1 2 3 4 |")

    root = _root(svg)
    assert root.attrib["data-render-engine"] == "publication"
    assert root.attrib["data-engine-version"] == "publication-3"
    assert "春江" in svg
    assert "<path" in svg


def test_explicit_dotted_full_measure_rest_is_rendered() -> None:
    score = parse_jianpu_score("1=C\n4/4\n0. |")

    assert len(score.measures) == 1
    assert score.measures[0].events[0].kind == "rest"
    assert score.measures[0].events[0].dotted == 1

    root = _root(render_score_svg(score))
    rest = next(
        node
        for node in root.iter()
        if node.attrib.get("data-note-token") in {"0", "0."}
    )
    assert any(node.attrib.get("class") == "rhythm-dot" for node in rest.iter())
    assert (
        len([node for node in root.iter() if "measure" in node.attrib.get("class", "")])
        >= 2
    )


def test_batch_measure_numbers_start_at_requested_number_after_reordering() -> None:
    pages = [
        parse_jianpu_score("1=C\n4/4\n1 2 3 4 |"),
        parse_jianpu_score("1=C\n4/4\n5 6 7 1 |"),
    ]

    _renumber_scores_continuously(pages, initial_measure_number=5)

    assert [page.measures[0].display_number for page in pages] == [5, 6]


def test_render_options_emit_requested_initial_measure_number() -> None:
    score = parse_jianpu_score("1=C\n4/4\n1 2 3 4 |")

    pages = render_scores_a4_pages([score], RenderOptions(initial_measure_number=5))

    assert 'aria-label="5"' in pages[0].svg


def test_playback_and_source_contract_is_preserved() -> None:
    score = parse_jianpu_score("1=C\n4/4\n1 [3+5] 0 q6 |")
    score.measures[0].events[0].source_ids = ["s1:i10"]
    score.measures[0].events[0].source_roles = {"note": ["s1:i10"]}
    svg = render_score_svg(score)
    root = _root(svg)
    groups = [
        node for node in root.iter() if "playback-note" in node.attrib.get("class", "")
    ]

    assert [node.attrib["data-note-index"] for node in groups] == ["0", "1", "2"]
    assert groups[1].attrib["data-note-token"] == "[3+5]"
    assert groups[0].attrib["data-source-ids"] == "s1:i10"
    assert groups[0].attrib["data-source-role-note"] == "s1:i10"
    assert len(groups[0].attrib["data-bbox"].split()) == 4


def test_rhythm_pitch_and_chord_features_are_visible() -> None:
    svg = render_jianpu_svg("1=C\n4/4\nq#1' [1+3+5] 2.. 4--- |")

    assert 'class="accidental"' in svg
    assert 'class="octave-dot"' in svg
    assert 'class="duration-line beam-line"' in svg
    assert 'class="rhythm-dot"' in svg
    assert 'class="extension-line"' in svg


def test_dotted_duration_line_starts_after_rhythm_dot() -> None:
    root = _root(render_score_svg(long_duration_score()))
    dot = next(node for node in root.iter() if node.attrib.get("class") == "rhythm-dot")
    line = next(
        node for node in root.iter() if node.attrib.get("class") == "extension-line"
    )

    assert float(line.attrib["x1"]) >= float(dot.attrib["cx"]) + float(dot.attrib["r"]) + 3


def test_consecutive_short_notes_share_continuous_rhythm_lines() -> None:
    events = [
        Event(
            kind="note",
            duration=Fraction(1, 2),
            pitches=[JianpuPitch(index + 1)],
            start=Fraction(index, 2),
        )
        for index in range(4)
    ]
    score = JianpuScore(measures=[Measure("1", duration=Fraction(2), events=events)])

    root = _root(render_score_svg(score))
    beams = [
        node for node in root.iter() if "duration-line" in node.attrib.get("class", "")
    ]

    assert len(beams) == 1
    assert float(beams[0].attrib["x2"]) - float(beams[0].attrib["x1"]) > 100


def test_sixteenth_notes_share_both_rhythm_lines() -> None:
    events = [
        Event(
            kind="note",
            duration=Fraction(1, 4),
            pitches=[JianpuPitch(index + 1)],
            start=Fraction(index, 4),
        )
        for index in range(4)
    ]
    score = JianpuScore(measures=[Measure("1", duration=Fraction(1), events=events)])

    root = _root(render_score_svg(score))
    beams = [
        node for node in root.iter() if "duration-line" in node.attrib.get("class", "")
    ]

    assert len(beams) == 2


def test_simultaneous_independent_voices_remain_distinct_and_do_not_overlap() -> None:
    events = [
        Event(
            kind="note",
            duration=Fraction(1),
            pitches=[JianpuPitch(1)],
            start=Fraction(0),
            voice="1",
            source_ids=["voice-1"],
        ),
        Event(
            kind="rest",
            duration=Fraction(1, 2),
            start=Fraction(0),
            voice="2",
            source_ids=["voice-2"],
        ),
    ]
    score = JianpuScore(measures=[Measure("1", duration=Fraction(4), events=events)])

    root = _root(render_score_svg(score))
    anchors = [
        node for node in root.iter() if "source-anchor" in node.attrib.get("class", "")
    ]
    boxes = [
        [float(value) for value in node.attrib["data-bbox"].split()] for node in anchors
    ]

    assert len(anchors) == 2
    assert {node.attrib["data-source-ids"] for node in anchors} == {
        "voice-1",
        "voice-2",
    }
    assert (
        boxes[0][0] + boxes[0][2] <= boxes[1][0]
        or boxes[1][0] + boxes[1][2] <= boxes[0][0]
    )


def test_accidental_has_clearance_from_its_note() -> None:
    event = Event(
        kind="note",
        duration=Fraction(1),
        pitches=[JianpuPitch(3, accidental=Fraction(1))],
    )
    root = _root(render_score_svg(JianpuScore(measures=[Measure("1", events=[event])])))
    accidental = next(
        node for node in root.iter() if node.attrib.get("class") == "accidental"
    )
    note = next(node for node in root.iter() if node.attrib.get("class") == "note")
    accidental_x, _ = _translate(accidental)
    note_x, _ = _translate(note)
    accidental_width = font_registry().measure(
        "♯", float(accidental.attrib["data-font-size"])
    )
    note_width = font_registry().measure("3", float(note.attrib["data-font-size"]))

    assert accidental_x + accidental_width / 2 + 4 <= note_x - note_width / 2


def test_accidental_is_left_and_above_note() -> None:
    event = Event(
        kind="note",
        duration=Fraction(1),
        pitches=[JianpuPitch(3, accidental=Fraction(1))],
    )
    root = _root(render_score_svg(JianpuScore(measures=[Measure("1", events=[event])])))
    accidental = next(
        node for node in root.iter() if node.attrib.get("class") == "accidental"
    )
    note = next(node for node in root.iter() if node.attrib.get("class") == "note")
    _accidental_left, accidental_top, accidental_right, _ = _text_box(accidental)
    note_left, note_top, _, _ = _text_box(note)

    assert accidental_right <= note_left - 2
    assert accidental_top <= note_top + 5


def test_accidental_does_not_shift_note_baseline() -> None:
    events = [
        Event(
            kind="note",
            duration=Fraction(1),
            start=Fraction(index),
            pitches=[
                JianpuPitch(3, accidental=Fraction(1) if index == 0 else Fraction(0))
            ],
        )
        for index in range(2)
    ]
    root = _root(
        render_score_svg(
            JianpuScore(measures=[Measure("1", duration=Fraction(2), events=events)])
        )
    )
    note_baselines = [
        _translate(node)[1]
        for node in root.iter()
        if node.attrib.get("class") == "note"
    ]

    assert note_baselines[0] == note_baselines[1]


def test_chord_attachment_clearance() -> None:
    event = Event(
        kind="note",
        duration=Fraction(1),
        pitches=[
            JianpuPitch(7),
            JianpuPitch(6, octave=-1),
            JianpuPitch(5, octave=-2),
        ],
    )
    root = _root(render_score_svg(JianpuScore(measures=[Measure("1", events=[event])])))
    notes = [node for node in root.iter() if node.attrib.get("class") == "note"]
    dots = [node for node in root.iter() if node.attrib.get("class") == "octave-dot"]
    bottom_note = notes[2]
    middle_dot_bottom = float(dots[0].attrib["cy"]) + float(dots[0].attrib["r"])
    bottom_note_top = _text_box(bottom_note)[1]

    assert middle_dot_bottom + 4 <= bottom_note_top


def test_chord_mark_stack_stays_above_highest_pitch_attachment() -> None:
    event = Event(
        kind="note",
        duration=Fraction(1),
        pitches=[JianpuPitch(7, octave=1), JianpuPitch(3, octave=-1)],
        articulations=["accent"],
        ornaments=["trill"],
    )
    root = _root(render_score_svg(JianpuScore(measures=[Measure("1", events=[event])])))
    note_top = min(
        _text_box(node)[1] for node in root.iter() if node.attrib.get("class") == "note"
    )
    dot_top = min(
        float(node.attrib["cy"]) - float(node.attrib["r"])
        for node in root.iter()
        if node.attrib.get("class") == "octave-dot"
    )
    attachment_top = min(note_top, dot_top)
    marks = [
        node
        for node in root.iter()
        if node.attrib.get("class") in {"articulation", "ornament"}
    ]

    assert len(marks) == 2
    assert all(_text_box(mark)[3] + 2 <= attachment_top for mark in marks)


def test_chord_accidentals_follow_their_pitch_rows() -> None:
    event = Event(
        kind="note",
        duration=Fraction(1),
        pitches=[
            JianpuPitch(7, accidental=Fraction(1)),
            JianpuPitch(3, accidental=Fraction(-1)),
        ],
    )
    root = _root(render_score_svg(JianpuScore(measures=[Measure("1", events=[event])])))
    notes = [node for node in root.iter() if node.attrib.get("class") == "note"]
    accidentals = [
        node for node in root.iter() if node.attrib.get("class") == "accidental"
    ]

    assert len(notes) == len(accidentals) == 2
    assert _translate(accidentals[0])[1] < _translate(accidentals[1])[1]
    assert all(
        _translate(accidental)[1] < _translate(note)[1]
        for accidental, note in zip(accidentals, notes, strict=True)
    )


def test_mark_bbox_contains_rendered_left_and_below_right_marks() -> None:
    event = Event(
        kind="note",
        duration=Fraction(1),
        pitches=[JianpuPitch(3)],
        technical=["arpeggio", "breath-mark"],
    )
    root = _root(render_score_svg(JianpuScore(measures=[Measure("1", events=[event])])))
    anchor = next(
        node for node in root.iter() if "source-anchor" in node.attrib.get("class", "")
    )
    anchor_box = _bbox(anchor)
    for mark in root.iter():
        if mark.attrib.get("class") in {"technical", "articulation", "ornament"}:
            left, top, right, bottom = _text_box(mark)
            assert left >= anchor_box[0]
            assert top >= anchor_box[1]
            assert right <= anchor_box[0] + anchor_box[2]
            assert bottom <= anchor_box[1] + anchor_box[3]


def test_tuplet_bracket_stays_above_extended_chord_attachments() -> None:
    events = [
        Event(
            kind="note",
            duration=Fraction(1, 3),
            start=Fraction(index, 3),
            pitches=[JianpuPitch(7, octave=2), JianpuPitch(5, octave=-1)],
            tuplet_id="triplet",
            tuplet_count=3,
        )
        for index in range(3)
    ]
    root = _root(
        render_score_svg(
            JianpuScore(measures=[Measure("1", duration=Fraction(1), events=events)])
        )
    )
    brackets = [
        node for node in root.iter() if node.attrib.get("class") == "tuplet-bracket"
    ]
    assert brackets
    bracket_y = min(
        float(re.search(r"M [-\d.]+ ([-\d.]+)", node.attrib["d"]).group(1))
        for node in brackets
    )  # type: ignore[union-attr]
    top_attachment = min(
        min(
            _text_box(node)[1]
            for node in root.iter()
            if node.attrib.get("class") == "note"
        ),
        min(
            float(node.attrib["cy"]) - float(node.attrib["r"])
            for node in root.iter()
            if node.attrib.get("class") == "octave-dot"
        ),
    )
    assert bracket_y + 2 <= top_attachment


def test_equal_duration_events_have_balanced_visual_slots() -> None:
    events = [
        Event(
            kind="note",
            duration=Fraction(1),
            start=Fraction(index),
            pitches=[
                JianpuPitch(
                    3 + (index % 2),
                    accidental=Fraction(1) if index == 0 else Fraction(0),
                    accidental_text="♯♯♯" if index == 0 else None,
                )
            ],
            articulations=["accent"] if index == 0 else [],
        )
        for index in range(4)
    ]
    measure = Measure("1", duration=Fraction(4), events=events)
    centers = _event_positions(events, 100.0, 900.0, measure, PublicationStyle())
    gaps = [right - left for left, right in pairwise(centers)]

    assert max(gaps) - min(gaps) < 15


def test_dense_measure_minimum_width_uses_visual_span_not_token_padding() -> None:
    events = [
        Event(
            kind="note",
            duration=Fraction(1, 2),
            start=Fraction(index, 2),
            pitches=[JianpuPitch(3)],
        )
        for index in range(12)
    ]
    measure = Measure("1", duration=Fraction(6), events=events)

    assert _intrinsic_measure_width(measure, PublicationStyle()) < 520


def test_multiple_tuplet_groups_reuse_space_between_groups() -> None:
    events = [
        Event(
            kind="note",
            duration=Fraction(1, 6),
            start=Fraction(index, 6),
            pitches=[JianpuPitch(index % 7 + 1)],
            tuplet_id=f"group-{index // 6}",
            tuplet_count=6,
            tuplet_index=index % 6,
        )
        for index in range(24)
    ]
    measure = Measure("1", duration=Fraction(4), events=events)
    style = PublicationStyle()
    positions = _event_positions(events, 100.0, 900.0, measure, style)
    boxes = [measure_event_ink(event, style) for event in events]
    visual_gaps = [
        positions[index + 1]
        + boxes[index + 1].left
        - positions[index]
        - boxes[index].right
        for index in range(len(events) - 1)
    ]
    internal_gaps = [
        gap for index, gap in enumerate(visual_gaps) if index not in {5, 11, 17}
    ]
    group_gaps = [visual_gaps[index] for index in (5, 11, 17)]

    assert max(group_gaps) - max(internal_gaps) < 24
    assert min(group_gaps) - max(internal_gaps) >= 6
    assert max(internal_gaps) - min(internal_gaps) < 16


def test_multiple_tuplet_groups_keep_a_small_boundary_gap_when_compressed() -> None:
    events = [
        Event(
            kind="note",
            duration=Fraction(1, 6),
            start=Fraction(index, 6),
            pitches=[JianpuPitch(index % 7 + 1)],
            tuplet_id=f"group-{index // 6}",
            tuplet_count=6,
            tuplet_index=index % 6,
        )
        for index in range(24)
    ]
    measure = Measure("1", duration=Fraction(4), events=events)
    style = PublicationStyle()
    positions = _event_positions(events, 100.0, 600.0, measure, style)
    boxes = [measure_event_ink(event, style) for event in events]
    visual_gaps = [
        positions[index + 1]
        + boxes[index + 1].left
        - positions[index]
        - boxes[index].right
        for index in range(len(events) - 1)
    ]
    internal_gaps = [
        gap for index, gap in enumerate(visual_gaps) if index not in {5, 11, 17}
    ]
    group_gaps = [visual_gaps[index] for index in (5, 11, 17)]

    assert min(group_gaps) - max(internal_gaps) >= 6


def test_multiple_tuplet_groups_have_compact_intrinsic_width() -> None:
    events = [
        Event(
            kind="note",
            duration=Fraction(1, 6),
            start=Fraction(index, 6),
            pitches=[JianpuPitch(index % 7 + 1)],
            tuplet_id=f"group-{index // 6}",
            tuplet_count=6,
            tuplet_index=index % 6,
        )
        for index in range(24)
    ]
    measure = Measure("1", duration=Fraction(4), events=events)

    assert _intrinsic_measure_width(measure, PublicationStyle()) < 650


def test_mixed_duration_spring_keeps_quarter_wider_than_eighth() -> None:
    style = PublicationStyle()
    assert _duration_spring(Fraction(1), Fraction(1, 2), style) > _duration_spring(
        Fraction(1, 2), Fraction(1, 2), style
    )


def test_narrow_measure_keeps_visual_slots_inside_content() -> None:
    events = [
        Event(
            kind="note",
            duration=Fraction(1),
            start=Fraction(index),
            pitches=[
                JianpuPitch(
                    3,
                    accidental_text="♯♯♯♯" if index == 0 else None,
                )
            ],
        )
        for index in range(3)
    ]
    measure = Measure("1", duration=Fraction(3), events=events)
    centers = _event_positions(events, 100.0, 260.0, measure, PublicationStyle())
    boxes = [
        (box.left, box.right)
        for box in (measure_event_ink(event, PublicationStyle()) for event in events)
    ]

    assert all(
        100.0 <= center + left and center + right <= 260.0
        for center, (left, right) in zip(centers, boxes, strict=True)
    )
    visual_gaps = [
        (centers[index + 1] + boxes[index + 1][0]) - (centers[index] + boxes[index][1])
        for index in range(len(centers) - 1)
    ]
    assert max(visual_gaps) - min(visual_gaps) < 18


def test_overfull_dense_measure_keeps_all_event_ink_inside_content() -> None:
    events = [
        Event(
            kind="note",
            duration=Fraction(1, 3),
            start=Fraction(index, 3),
            pitches=[JianpuPitch(3)],
        )
        for index in range(18)
    ]
    measure = Measure("1", duration=Fraction(6), events=events)
    style = PublicationStyle()
    positions = _event_positions(events, 100.0, 300.0, measure, style)
    boxes = [measure_event_ink(event, style) for event in events]

    assert all(
        100.0 <= x + box.left and x + box.right <= 300.0
        for x, box in zip(positions, boxes, strict=True)
    )


def test_low_octave_dot_stays_above_duration_lines() -> None:
    event = Event(
        kind="note",
        duration=Fraction(1, 4),
        pitches=[JianpuPitch(6, octave=-1)],
    )
    root = _root(render_score_svg(JianpuScore(measures=[Measure("1", events=[event])])))
    dot = next(node for node in root.iter() if node.attrib.get("class") == "octave-dot")
    lines = [
        node for node in root.iter() if "duration-line" in node.attrib.get("class", "")
    ]

    assert lines
    assert all(
        float(line.attrib["y1"]) >= float(dot.attrib["cy"]) + 8 for line in lines
    )


def test_rhythm_runs_share_lowest_safe_baseline_in_a_measure() -> None:
    low = Event(
        kind="note",
        duration=Fraction(1, 2),
        pitches=[JianpuPitch(6, octave=-1)],
        voice="1",
    )
    normal = Event(
        kind="note",
        duration=Fraction(1, 2),
        pitches=[JianpuPitch(3)],
        voice="2",
    )
    scene = PublicationScene(320.0, 180.0, 0)
    anchors = [
        _Anchor(130.0, 100.0, BBox(120.0, 80.0, 20.0, 28.0), low),
        _Anchor(220.0, 100.0, BBox(210.0, 80.0, 20.0, 28.0), normal),
    ]

    _draw_rhythm_lines(scene, anchors, style=PublicationStyle())
    lines = [
        node
        for node in scene.nodes
        if "duration-line" in node.attrs.get("class", "")
    ]

    assert len(lines) == 2
    assert float(lines[0].attrs["y1"]) == float(lines[1].attrs["y1"])


def test_octave_dots_clear_actual_note_ink_bounds() -> None:
    event = Event(
        kind="note",
        duration=Fraction(1),
        pitches=[JianpuPitch(1, octave=1), JianpuPitch(6, octave=-1)],
    )
    root = _root(render_score_svg(JianpuScore(measures=[Measure("1", events=[event])])))
    notes = [node for node in root.iter() if node.attrib.get("class") == "note"]
    dots = [node for node in root.iter() if node.attrib.get("class") == "octave-dot"]
    assert len(notes) == 2
    assert len(dots) == 2
    high_note_top = _text_box(notes[0])[1]
    low_note_bottom = _text_box(notes[1])[3]
    high_dot_bottom = float(dots[0].attrib["cy"]) + float(dots[0].attrib["r"])
    low_dot_top = float(dots[1].attrib["cy"]) - float(dots[1].attrib["r"])

    assert high_dot_bottom <= high_note_top - 3
    assert low_dot_top >= low_note_bottom + 3


def test_beam_line_stays_inside_measure_content() -> None:
    scene = PublicationScene(240.0, 160.0, 0)
    event = Event(kind="note", duration=Fraction(1, 2), pitches=[JianpuPitch(3)])
    anchors = [
        _Anchor(180.0, 100.0, BBox(170.0, 90.0, 18.0, 24.0), event),
        _Anchor(206.0, 100.0, BBox(196.0, 90.0, 18.0, 24.0), event),
    ]

    _draw_rhythm_run(scene, anchors, 1, left_limit=172.0, right_limit=212.0)
    line = next(
        node for node in scene.nodes if "duration-line" in node.attrs.get("class", "")
    )

    assert float(line.attrs["x1"]) >= 172.0
    assert float(line.attrs["x2"]) <= 212.0


def test_explicit_beam_hook_is_clipped_to_measure_boundary() -> None:
    scene = PublicationScene(240.0, 160.0, 0)
    event = Event(
        kind="note",
        duration=Fraction(1, 16),
        pitches=[JianpuPitch(3)],
        beams=[Beam("1", "forward-hook")],
    )
    anchor = _Anchor(208.0, 100.0, BBox(198.0, 90.0, 18.0, 24.0), event)

    _draw_explicit_beam_level(
        scene,
        [anchor],
        1,
        left_limit=172.0,
        right_limit=212.0,
    )
    line = next(
        node for node in scene.nodes if "duration-line" in node.attrs.get("class", "")
    )

    assert float(line.attrs["x1"]) >= 172.0
    assert float(line.attrs["x2"]) <= 212.0


def test_explicit_musicxml_beams_override_fallback_grouping() -> None:
    events = [
        Event(
            kind="note",
            duration=Fraction(1, 2),
            pitches=[JianpuPitch(index + 1)],
            start=Fraction(index, 2),
            beams=[Beam("1", status)],
        )
        for index, status in enumerate(("begin", "end", "begin", "end"))
    ]
    root = _root(
        render_score_svg(
            JianpuScore(measures=[Measure("1", duration=Fraction(2), events=events)])
        )
    )
    lines = [
        node for node in root.iter() if "duration-line" in node.attrib.get("class", "")
    ]

    assert len(lines) == 2


def test_tuplet_notes_are_compact_and_have_no_lower_rhythm_lines() -> None:
    events = [
        Event(
            kind="note",
            duration=Fraction(1, 3),
            pitches=[JianpuPitch(index + 1)],
            start=Fraction(index, 3),
            tuplet_id="triplet-1",
            tuplet_count=3,
            tuplet_index=index,
        )
        for index in range(3)
    ]
    score = JianpuScore(measures=[Measure("1", duration=Fraction(4), events=events)])

    root = _root(render_score_svg(score))
    beams = [
        node for node in root.iter() if "duration-line" in node.attrib.get("class", "")
    ]
    notes = [
        node for node in root.iter() if "playback-note" in node.attrib.get("class", "")
    ]

    assert not beams
    assert (
        float(notes[-1].attrib["data-bbox"].split()[0])
        - float(notes[0].attrib["data-bbox"].split()[0])
        <= 48
    )
    assert any("tuplet-bracket" in node.attrib.get("class", "") for node in root.iter())


def test_single_part_system_has_one_start_barline_and_terminal_barline() -> None:
    root = _root(render_jianpu_svg("1=C\n4/4\n1 2 3 4 |"))
    system_brackets = [
        node for node in root.iter() if "system-bracket" in node.attrib.get("class", "")
    ]
    terminal_lines = [
        node
        for node in root.iter()
        if "terminal-barline" in node.attrib.get("class", "")
    ]

    assert not system_brackets
    assert len(terminal_lines) == 2


def test_simple_measure_barlines_do_not_span_the_full_system_height() -> None:
    root = _root(render_jianpu_svg("1=C\n4/4\n1 2 3 4 | 5 6 7 1 |"))
    barlines = [
        node
        for node in root.iter()
        if node.tag.endswith("line") and "measure" in node.attrib.get("class", "")
    ]

    assert barlines
    assert (
        max(
            abs(float(node.attrib["y2"]) - float(node.attrib["y1"]))
            for node in barlines
        )
        <= 58
    )


def test_tuplet_bracket_leaves_a_gap_for_its_number() -> None:
    events = [
        Event(
            kind="note",
            duration=Fraction(1, 3),
            pitches=[JianpuPitch(index + 1, octave=1)],
            start=Fraction(index, 3),
            tuplet_id="triplet-gap",
            tuplet_count=3,
        )
        for index in range(3)
    ]
    score = JianpuScore(measures=[Measure("1", duration=Fraction(4), events=events)])
    root = _root(render_score_svg(score))
    bracket = next(
        node for node in root.iter() if "tuplet-bracket" in node.attrib.get("class", "")
    )

    assert bracket.attrib["d"].count("M ") == 2


def test_dense_tuplet_measures_are_not_overpacked_on_the_same_row() -> None:
    measures: list[Measure] = []
    for measure_index in range(4):
        events = [
            Event(
                kind="note",
                duration=Fraction(1, 3),
                pitches=[JianpuPitch(index % 7 + 1)],
                start=Fraction(index, 3),
                tuplet_id=f"m{measure_index}-g{index // 6}",
                tuplet_count=6,
                articulations=["accent"],
            )
            for index in range(18)
        ]
        measures.append(
            Measure(str(measure_index + 1), duration=Fraction(6), events=events)
        )
    pages = render_scores_a4_pages([JianpuScore(measures=measures)])
    assert len(pages) == 1
    root = _root(pages[0].svg)
    measure_numbers = [
        node for node in root.iter() if "measure-no" in node.attrib.get("class", "")
    ]
    rows: set[float] = set()
    for node in measure_numbers:
        match = re.search(r"translate\([^ ]+ ([^)]+)\)", node.attrib["transform"])
        assert match is not None
        rows.add(float(match.group(1)))

    assert len(rows) <= 2


def test_measure_attributes_only_render_when_key_or_meter_changes() -> None:
    score = parse_jianpu_score("1=C\n4/4\n1 | 2 | 3 |")
    score.measures[2].target_key = "G"

    svg = render_score_svg(score)

    assert svg.count('class="measure-attribute"') == 1


def test_measure_attribute_does_not_shift_event_slots() -> None:
    plain = parse_jianpu_score("1=C\n4/4\n1 | 2 3 4 5 |")
    changed = parse_jianpu_score("1=C\n4/4\n1 | 2 3 4 5 |")
    changed.measures[1].target_key = "F"
    changed.measures[1].beats_per_measure = 3

    plain_notes = [
        node for node in _root(render_score_svg(plain)).iter()
        if node.attrib.get("class") == "note"
    ]
    changed_notes = [
        node for node in _root(render_score_svg(changed)).iter()
        if node.attrib.get("class") == "note"
    ]

    assert _translate(plain_notes[1])[0] == _translate(changed_notes[1])[0]


def test_mark_placement_is_respected() -> None:
    event = Event(
        kind="note",
        duration=Fraction(1),
        pitches=[JianpuPitch(3)],
        technical=["scoop", "tremolo"],
    )
    root = _root(render_score_svg(JianpuScore(measures=[Measure("1", events=[event])])))
    note = next(node for node in root.iter() if node.attrib.get("class") == "note")
    marks = [node for node in root.iter() if node.attrib.get("class") == "technical"]
    note_x, note_y = _translate(note)
    positions = {node.attrib["aria-label"]: _translate(node) for node in marks}

    assert positions["scoop"][0] < note_x
    assert positions["≋"][0] > note_x
    assert positions["≋"][1] > note_y


def test_semantic_note_and_mark_nodes_carry_exact_source_ids() -> None:
    event = Event(
        kind="note",
        duration=Fraction(1),
        pitches=[JianpuPitch(3, source_id="note-3")],
        articulations=["accent"],
        source_ids=["note-3", "accent-3"],
        source_roles={"note": ["note-3"], "articulation": ["accent-3"]},
    )
    score = JianpuScore(measures=[Measure("1", duration=Fraction(4), events=[event])])

    root = _root(render_score_svg(score))
    note = next(node for node in root.iter() if node.attrib.get("class") == "note")
    mark = next(
        node for node in root.iter() if "articulation" in node.attrib.get("class", "")
    )

    assert note.attrib["data-source-ids"] == "note-3"
    assert note.attrib["data-source-role"] == "note"
    assert mark.attrib["data-source-ids"] == "accent-3"
    assert mark.attrib["data-source-role"] == "articulation"


def test_chord_accidentals_keep_their_pitch_source_ids_after_pitch_sorting() -> None:
    event = Event(
        kind="note",
        duration=Fraction(1),
        pitches=[
            JianpuPitch(
                1,
                accidental=Fraction(-1),
                source_id="note-low",
                accidental_source_id="accidental-low",
            ),
            JianpuPitch(
                6,
                accidental=Fraction(1),
                source_id="note-high",
                accidental_source_id="accidental-high",
            ),
        ],
        source_roles={
            "note": ["note-low", "note-high"],
            "accidental": ["accidental-low", "accidental-high"],
        },
    )
    score = JianpuScore(measures=[Measure("1", duration=Fraction(4), events=[event])])

    root = _root(render_score_svg(score))
    accidentals = {
        node.attrib["aria-label"]: node.attrib["data-source-ids"]
        for node in root.iter()
        if node.attrib.get("class") == "accidental"
    }

    assert accidentals == {"♭": "accidental-low", "♯": "accidental-high"}


def test_event_dynamic_is_not_rendered_again_as_measure_text() -> None:
    event = Event(
        kind="note",
        duration=Fraction(1),
        pitches=[JianpuPitch(1)],
        dynamic="f",
    )
    measure = Measure(
        "1",
        duration=Fraction(4),
        events=[event],
        text_blocks=[TextBlock("f", role="expression")],
    )

    svg = render_score_svg(JianpuScore(measures=[measure]))

    assert svg.count('class="dynamic"') == 1


def test_dynamic_mark_clears_low_octave_chord_attachments() -> None:
    event = Event(
        kind="note",
        duration=Fraction(1),
        pitches=[
            JianpuPitch(2),
            JianpuPitch(5),
            JianpuPitch(2, octave=-1),
            JianpuPitch(5, octave=-1),
        ],
        dynamic="f",
    )
    root = _root(render_score_svg(JianpuScore(measures=[Measure("1", events=[event])])))
    dynamic = next(node for node in root.iter() if node.attrib.get("class") == "dynamic")
    dynamic_box = _text_box(dynamic)
    lowest_octave_dot_bottom = max(
        float(node.attrib["cy"]) + float(node.attrib["r"])
        for node in root.iter()
        if node.attrib.get("class") == "octave-dot"
    )

    assert dynamic_box[1] >= lowest_octave_dot_bottom + 5.9


def test_spanners_tuplets_marks_and_lyrics_are_rendered() -> None:
    score = parse_jianpu_score("1=C\n4/4\n$^.1 2 3$ 4~ | ~4 (5 6) |\nL: 春 江 花 月")
    score.measures[0].events[0].dynamic = "mf"
    score.measures[0].repeat_start = True
    score.measures[1].repeat_end = True
    score.measures[1].ending_start = "1."
    svg = render_score_svg(score)

    assert 'class="tuplet-bracket"' in svg
    assert 'class="tuplet-number"' in svg
    assert 'class="tie"' in svg
    assert 'class="slur"' in svg
    assert 'data-mark="staccato"' in svg
    assert 'class="dynamic"' in svg
    assert 'class="lyric"' in svg
    assert 'class="repeat-dot"' in svg
    assert 'class="ending-line"' in svg


def test_unknown_musicxml_mark_uses_text_fallback() -> None:
    event = Event(
        kind="note",
        duration=Fraction(1),
        pitches=[JianpuPitch(1)],
        technical=["future-technique"],
    )
    score = JianpuScore(measures=[Measure("1", duration=Fraction(4), events=[event])])

    assert "future-technique" in render_score_svg(score)


def test_generated_full_measure_rest_is_expanded_visually() -> None:
    rest = Event(kind="rest", duration=Fraction(4), generated=True)
    score = JianpuScore(measures=[Measure("1", duration=Fraction(4), events=[rest])])
    svg = render_score_svg(score)

    assert svg.count('aria-label="0"') == 4


def test_a4_pages_are_deterministic_and_report_source_ranges() -> None:
    first = parse_jianpu_score("1=C\n4/4\n1 2 3 4 | 5 6 7 1' |")
    second = parse_jianpu_score("1=C\n4/4\n1 2 3 4 |")
    for measure in first.measures:
        measure.source_page_index = 0
    for measure in second.measures:
        measure.source_page_index = 1
    pages1 = render_scores_a4_pages([first, second])
    pages2 = render_scores_a4_pages([first, second])

    assert [hashlib.sha256(page.svg.encode()).hexdigest() for page in pages1] == [
        hashlib.sha256(page.svg.encode()).hexdigest() for page in pages2
    ]
    assert pages1[0].measure_ranges[0].source_page_index == 0
    assert {item.source_page_index for item in pages1[0].measure_ranges} == {0, 1}


def test_manual_system_and_page_breaks_are_honored() -> None:
    score = parse_jianpu_score("1=C\n4/4\n1 2 3 4 | 5 6 7 1 | 1 2 3 4 |")
    score.measures[1].new_system = True
    score.measures[2].new_page = True

    pages = render_scores_a4_pages([score])

    assert len(pages) >= 2


def test_slur_continues_across_system_break() -> None:
    score = parse_jianpu_score("1=C\n4/4\n(1 2 | 3 4) |")
    score.measures[1].new_system = True
    root = _root(render_scores_a4_pages([score])[0].svg)
    slurs = [node for node in root.iter() if node.attrib.get("class") == "slur"]

    assert len(slurs) == 2
    assert {node.attrib.get("data-continuation") for node in slurs} == {"end", "start"}


def test_multi_part_system_contains_all_parts_and_aligned_bars() -> None:
    high = parse_jianpu_score("1=C\n4/4\n1 2 | 3 4 |")
    low = parse_jianpu_score("1=C\n4/4\n5 6 | 7 1 |")
    high.part_index, high.part_count, high.part_name = 0, 2, "高声部"
    low.part_index, low.part_count, low.part_name = 1, 2, "低声部"

    pages = render_scores_a4_pages([high, low])

    assert len(pages) == 1
    assert "高声部" in pages[0].svg
    assert "低声部" in pages[0].svg
    assert pages[0].svg.count('class="measure"') >= 4


def test_custom_page_size_is_preserved() -> None:
    svg = render_jianpu_page_svg(
        "1=C\n4/4\n1 2 3 4 |",
        page_width=600,
        page_height=800,
    )
    root = _root(svg)

    assert root.attrib["width"] == "600"
    assert root.attrib["height"] == "800"


def test_measure_number_modes() -> None:
    score = parse_jianpu_score("1=C\n4/4\n1 | 2 | 3 | 4 | 5 | 6 |")

    all_svg = render_score_svg(score, RenderOptions(measure_number_mode="all"))
    none_svg = render_score_svg(
        score,
        RenderOptions(show_measure_numbers=False, measure_number_mode="none"),
    )
    row_svg = render_score_svg(score, RenderOptions(measure_number_mode="row_start"))

    assert all_svg.count('class="measure-no"') == 6
    assert 'class="measure-no"' not in none_svg
    assert 0 < row_svg.count('class="measure-no"') < 6


def test_service_writes_scene_render_map(tmp_path: Path) -> None:
    score = parse_jianpu_score("1=C\n4/4\n1 |")
    score.measures[0].events[0].source_ids = ["s1:i10"]
    pages = PublicationRenderService().render_scores_a4_svg_pages(
        [score], tmp_path / "score.svg"
    )

    assert pages[0].path.exists()
    assert pages[0].render_map_path is not None
    payload = json.loads(pages[0].render_map_path.read_text(encoding="utf-8"))
    assert payload["anchors"][0]["selector"] == 'g[data-source-ids~="s1:i10"]'


def test_bundled_font_manifest_is_stable() -> None:
    registry = font_registry()

    assert len(registry.manifest_hash) == 64
    assert registry.measure("简谱 123", 20) > 0


def test_bundled_font_ink_bounds_are_deterministic() -> None:
    registry = font_registry()
    first = registry.ink_bounds("♯1●", 20)
    second = registry.ink_bounds("♯1●", 20)

    assert first == second
    assert first[0] < first[2]
    assert first[1] < first[3]


def test_a4_viewbox_is_stable() -> None:
    svg = render_scores_a4_pages([parse_jianpu_score("1=C\n4/4\n1 2 3 4 |")])[0].svg
    root = _root(svg)

    assert root.attrib["width"] == "1240"
    assert root.attrib["height"] == "1754"
    assert root.attrib["viewBox"] == "0 0 1240 1754"


def test_score_page_does_not_use_system_fonts() -> None:
    score = parse_jianpu_score("1=C\n4/4\n1 2 3 4 |")
    svg = render_score_page_svg(score, page_width=1240, page_height=1754)

    assert "font-family=" not in svg
    assert "<path" in svg


def test_staccato_uses_a_distinct_bounded_vector_triangle() -> None:
    root = _root(render_score_svg(staccato_score()))
    staccato_nodes = [
        node for node in root.iter() if "staccato" in node.attrib.get("class", "")
    ]

    assert staccato_nodes
    triangle = next(node for node in staccato_nodes if node.tag.endswith("path"))
    assert triangle.attrib["d"].count("L") == 2


def test_high_octave_staccato_keeps_octave_dot_and_mark_distinct() -> None:
    event = Event(
        kind="note",
        duration=Fraction(1),
        pitches=[JianpuPitch(3, octave=1)],
        articulation="staccato",
        articulations=["staccato"],
    )
    root = _root(render_score_svg(JianpuScore(measures=[Measure("1", events=[event])])))

    octave_dot = next(
        node for node in root.iter() if node.attrib.get("class") == "octave-dot"
    )
    staccato = next(
        node for node in root.iter() if "staccato" in node.attrib.get("class", "")
    )

    assert staccato.tag.endswith("path")
    assert "L" in staccato.attrib["d"]
    assert "cy" not in staccato.attrib
    assert float(octave_dot.attrib["cy"]) != float(staccato.attrib.get("cy", "nan"))


def test_system_height_grows_for_multiple_unpositioned_text_rows() -> None:
    plain = Measure(
        "1",
        duration=Fraction(4),
        events=[Event(kind="note", duration=Fraction(4), pitches=[JianpuPitch(1)])],
    )
    crowded = Measure(
        "1",
        duration=Fraction(4),
        events=[Event(kind="note", duration=Fraction(4), pitches=[JianpuPitch(1)])],
        text_blocks=[
            TextBlock("第一段", role="lyric"),
            TextBlock("第二段", role="lyric"),
            TextBlock("第三段", role="lyric"),
        ],
    )
    style = PublicationStyle()

    plain_height = _system_extra_height([_Cell(0, [plain], 150.0)], style)
    crowded_height = _system_extra_height([_Cell(0, [crowded], 150.0)], style)

    assert crowded_height > plain_height


def test_tie_prefers_an_upper_route_without_changing_slur_route() -> None:
    first = Event(
        kind="note",
        duration=Fraction(1),
        pitches=[JianpuPitch(3)],
        tie_start=True,
        start=Fraction(0),
    )
    second = Event(
        kind="note",
        duration=Fraction(1),
        pitches=[JianpuPitch(3)],
        tie_stop=True,
        start=Fraction(1),
    )
    root = _root(
        render_score_svg(
            JianpuScore(
                measures=[Measure("1", duration=Fraction(4), events=[first, second])]
            )
        )
    )
    tie = next(node for node in root.iter() if node.attrib.get("class") == "tie")
    note = next(node for node in root.iter() if node.attrib.get("class") == "note")
    _note_x, note_y = _translate(note)
    coordinates = [float(value) for value in re.findall(r"[-\d.]+", tie.attrib["d"])]

    assert coordinates
    assert min(coordinates[1::2]) < note_y


def test_overfull_duration_does_not_cross_the_right_measure_barline() -> None:
    root = _root(render_score_svg(overfull_tail_duration_score()))
    barlines = [
        node
        for node in root.iter()
        if node.tag.endswith("line") and "measure" in node.attrib.get("class", "")
    ]
    assert barlines
    right_barline = max(float(node.attrib["x1"]) for node in barlines)
    extension_lines = [
        node for node in root.iter() if node.attrib.get("class") == "extension-line"
    ]

    assert extension_lines
    assert all(
        float(node.attrib["x2"]) <= right_barline - 4 for node in extension_lines
    ), [
        (node.attrib["x1"], node.attrib["x2"], right_barline)
        for node in extension_lines
    ]
