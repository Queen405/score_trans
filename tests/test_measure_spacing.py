from __future__ import annotations

import itertools
import xml.etree.ElementTree as ET
from dataclasses import replace
from fractions import Fraction

import pytest

from score_trans.domain.jianpu import parse_jianpu_score
from score_trans.models.common.errors import RenderError
from score_trans.models.score import Beam, Event, JianpuPitch, Measure
from score_trans.services.render.engraving.geometry import (
    measure_event_ink,
    pitch_layouts,
)
from score_trans.services.render.engraving.renderer import (
    PublicationRenderer,
    _break_systems,
    _build_cells,
    _event_positions,
    _shared_cell_positions,
    _spacing_profile,
)
from score_trans.services.render.engraving.rhythm import beat_group_boundaries
from score_trans.services.render.engraving.style import PublicationStyle
from score_trans.services.render.options import A4LayoutOptions, RenderOptions
from score_trans.services.render.main import render_score_svg


def _notes(count: int, duration: Fraction = Fraction(1, 2)) -> list[Event]:
    return [
        Event("note", duration, [JianpuPitch(3)], start=index * duration)
        for index in range(count)
    ]


@pytest.mark.parametrize(
    ("meter", "count", "groups"),
    [
        ("2/4", 4, 2),
        ("3/4", 6, 3),
        ("4/4", 8, 4),
        ("3/8", 3, 1),
        ("6/8", 6, 2),
        ("9/8", 9, 3),
        ("12/8", 12, 4),
        ("5/8", 5, 2),
        ("7/8", 7, 3),
    ],
)
def test_publication_defaults_break_beams_into_meter_groups(
    meter: str, count: int, groups: int
) -> None:
    score = parse_jianpu_score(f"1=C\n{meter}\n" + " ".join(["q3"] * count) + " |")
    root = ET.fromstring(render_score_svg(score))
    lines = [
        node
        for node in root.iter()
        if "beam-line" in node.attrib.get("class", "").split()
    ]
    assert len(lines) == groups
    assert RenderOptions().break_beams_at_beat
    assert A4LayoutOptions().break_beams_at_beat
    spans = sorted(
        (float(line.attrib["x1"]), float(line.attrib["x2"])) for line in lines
    )
    assert all(left[1] < right[0] for left, right in itertools.pairwise(spans))


def test_explicit_asymmetric_beam_groups_are_preserved() -> None:
    events = _notes(5)
    for index, status in enumerate(["begin", "continue", "end", "begin", "end"]):
        events[index].beams = [Beam("1", status)]
    measure = Measure(
        "1", duration=Fraction(5, 2), events=events, beats_per_measure=5, beat_type=8
    )
    assert beat_group_boundaries(measure) == [
        Fraction(0),
        Fraction(3, 2),
        Fraction(5, 2),
    ]


def test_rests_participate_in_beam_groups() -> None:
    score = parse_jianpu_score("1=C\n2/4\nq0 q1 q2 q3 |")
    root = ET.fromstring(render_score_svg(score))
    lines = [
        node
        for node in root.iter()
        if "beam-line" in node.attrib.get("class", "").split()
    ]
    assert len(lines) == 2


@pytest.mark.parametrize("tones", [2, 3, 4, 5])
@pytest.mark.parametrize("dots", [1, 2])
def test_each_chord_tone_has_its_own_duration_dots(tones: int, dots: int) -> None:
    pitches = "+".join(str(index + 1) for index in range(tones))
    score = parse_jianpu_score(f"1=C\n2/4\nq[{pitches}]" + "." * dots + " |")
    root = ET.fromstring(render_score_svg(score))
    circles = [node for node in root.iter() if node.attrib.get("class") == "rhythm-dot"]
    assert len(circles) == tones * dots
    assert len({node.attrib["cy"] for node in circles}) == tones
    assert len({node.attrib["cx"] for node in circles}) == dots
    assert all(float(node.attrib["r"]) == pytest.approx(2.1 * 0.82) for node in circles)


def test_full_measure_long_note_and_chord_start_at_first_beat() -> None:
    style = PublicationStyle(measures_per_system=5)
    for pitches in [[JianpuPitch(3)], [JianpuPitch(5), JianpuPitch(3), JianpuPitch(1)]]:
        event = Event("note", Fraction(2), pitches, start=Fraction(0))
        full = Measure("1", duration=Fraction(2), events=[event], beats_per_measure=2)
        regular = replace(
            full,
            events=[
                replace(event, duration=Fraction(1)),
                replace(event, start=Fraction(1), duration=Fraction(1)),
            ],
        )
        assert _event_positions([event], 100, 400, full, style)[0] == pytest.approx(
            _event_positions(regular.events, 100, 400, regular, style)[0]
        )


def test_chord_extension_line_is_centred_on_stack_not_bottom_tone() -> None:
    score = parse_jianpu_score("1=C\n2/4\nh[5+3+1] |")
    page = PublicationRenderer(PublicationStyle(measures_per_system=5)).render_scores(
        [score]
    )[0]
    chord = next(
        node
        for node in page.scene.nodes
        if node.attrs.get("data-note-token") == "h[5+3+1]"
    )
    digits = [child for child in chord.children if child.attrs.get("class") == "note"]
    baseline = float(digits[-1].attrs["y"])
    rows = pitch_layouts(score.measures[0].events[0], PublicationStyle())
    expected = (
        baseline
        + (
            min(row.note_box.top for row in rows)
            + max(row.note_box.bottom for row in rows)
        )
        / 2
    )
    dash = next(
        child
        for node in page.scene.nodes
        for child in node.children
        if child.attrs.get("class") == "extension-line"
    )
    assert float(dash.attrs["y1"]) == pytest.approx(expected)


def test_swapping_parts_cannot_change_shared_rhythmic_positions() -> None:
    lanes = [
        Measure(
            "1",
            duration=Fraction(2),
            events=[Event("rest", Fraction(1), start=Fraction(i)) for i in range(2)],
        ),
        Measure("1", duration=Fraction(2), events=_notes(4)),
        Measure("1", duration=Fraction(2), events=_notes(8, Fraction(1, 4))),
    ]
    style = PublicationStyle(measures_per_system=5, short_note_gap_scale=0.2)
    positions = _shared_cell_positions(lanes, 0, 400, style)
    for permutation in itertools.permutations(lanes):
        assert _shared_cell_positions(
            list(permutation), 0, 400, style
        ) == pytest.approx(positions)


def test_automatic_and_fixed_modes_use_same_measure_position_solver() -> None:
    measure = parse_jianpu_score("1=C\n2/4\ns1 s2 q3 4 |").measures[0]
    automatic = PublicationStyle()
    fixed = replace(automatic, measures_per_system=5)
    assert _shared_cell_positions([measure], 0, 350, automatic) == pytest.approx(
        _shared_cell_positions([measure], 0, 350, fixed)
    )


def test_fixed_count_gives_dense_measures_more_width_without_changing_count() -> None:
    score = parse_jianpu_score(
        "1=C\n2/4\nh3 | s1 s2 s3 s4 s5 s6 s7 s1 | h3 | 1 2 | h3 |"
    )
    style = PublicationStyle(measures_per_system=5)
    systems = _break_systems(_build_cells([[score]], style), style, 1)
    assert len(systems) == 1
    assert len(systems[0].cells) == 5
    assert systems[0].widths[1] > systems[0].widths[0]
    assert sum(systems[0].widths) == pytest.approx(style.content_width)
    assert all(
        width >= cell.minimum_width
        for width, cell in zip(systems[0].widths, systems[0].cells, strict=True)
    )


def test_unavoidable_density_reduces_count_instead_of_overlapping_or_shrinking() -> (
    None
):
    score = parse_jianpu_score(
        "1=C\n2/4\n" + " ".join(["s1 s2 s3 s4 s5 s6 s7 s1 |"] * 5)
    )
    style = PublicationStyle(page_width=650, measures_per_system=5)
    systems = _break_systems(_build_cells([[score]], style), style, 1)
    assert all(len(system.cells) < 5 for system in systems)
    assert sum(len(system.cells) for system in systems) == 5
    assert all(sum(system.widths) <= style.content_width + 1e-6 for system in systems)


def test_too_narrow_measure_is_rejected_before_negative_spacing() -> None:
    measure = Measure("1", duration=Fraction(2), events=_notes(4), beats_per_measure=2)
    style = PublicationStyle()
    with pytest.raises(RenderError, match="超出可用宽度"):
        _event_positions(measure.events, 100, 140, measure, style)


def test_spacing_interpolation_never_breaks_hard_ink_clearance() -> None:
    measure = Measure(
        "1", duration=Fraction(2), events=_notes(8, Fraction(1, 4)), beats_per_measure=2
    )
    style = PublicationStyle(short_note_gap_scale=0.2)
    profile = _spacing_profile([measure], style)
    for width in [
        profile.minimum_width,
        profile.natural_width,
        profile.natural_width + 100,
    ]:
        positions = profile.positions(0, width)
        for left, right in itertools.pairwise(measure.events):
            gap = (
                positions[right.start]
                + measure_event_ink(right, style).left
                - positions[left.start]
                - measure_event_ink(left, style).right
            )
            assert gap >= style.event_clearance - 1e-6


def test_chord_ties_keep_one_arc_for_each_sustained_pitch() -> None:
    score = parse_jianpu_score("1=C\n2/4\n[5+3+1]~ ~[5+3+1] |")
    root = ET.fromstring(render_score_svg(score))
    ties = [node for node in root.iter() if node.attrib.get("class") == "tie"]
    assert len(ties) == 3
    assert len({node.attrib["data-bbox"].split()[1] for node in ties}) == 3
    score.measures[0].events[0].source_roles["tie_start"] = ["tie-start"]
    score.measures[0].events[1].source_roles["tie_stop"] = ["tie-stop"]
    page = PublicationRenderer().render_scores([score])[0]
    assert "tie-start" in page.scene.source_boxes
    assert "tie-stop" in page.scene.source_boxes


def test_geometry_checks_actual_ink_instead_of_blank_space_inside_event_boxes() -> None:
    from score_trans.services.render.engraving.qa import check_scene_geometry
    from score_trans.services.render.engraving.scene import (
        BBox,
        PublicationScene,
        SceneNode,
    )

    scene = PublicationScene(200, 200, 0)
    scene.add(
        SceneNode(
            "g",
            {"class": "source-anchor", "data-bbox": "0 0 20 120"},
            ink_boxes=(BBox(0, 0, 20, 20), BBox(0, 100, 20, 20)),
        )
    )
    other = SceneNode(
        "g",
        {"class": "source-anchor", "data-bbox": "10 50 20 20"},
        ink_boxes=(BBox(10, 50, 20, 20),),
    )
    scene.add(other)
    assert not check_scene_geometry(scene, PublicationStyle())
    other.ink_boxes = (BBox(10, 10, 20, 20),)
    other.attrs["data-bbox"] = "10 10 20 20"
    assert any(
        issue["kind"] == "event-overlap"
        for issue in check_scene_geometry(scene, PublicationStyle())
    )


def test_tuplet_ratios_survive_columns_from_another_voice_and_justification() -> None:
    triplet = Measure(
        "1",
        duration=Fraction(2),
        events=[
            Event(
                "note",
                Fraction(2, 3),
                [JianpuPitch(3)],
                start=Fraction(index * 2, 3),
                tuplet_id="t",
                tuplet_count=3,
            )
            for index in range(3)
        ],
    )
    quarters = Measure("1", duration=Fraction(2), events=_notes(2, Fraction(1)))
    style = PublicationStyle()
    profile = _spacing_profile([triplet, quarters], style)
    for width in [
        profile.minimum_width,
        profile.natural_width,
        profile.natural_width + 300,
    ]:
        positions = profile.positions(0, width)
        assert positions[Fraction(1)] == pytest.approx(
            (positions[Fraction(2, 3)] + positions[Fraction(4, 3)]) / 2
        )


@pytest.mark.parametrize("size", [70, 100, 140])
def test_note_size_changes_scale_rhythm_lines_and_dashes_with_digits(size: int) -> None:
    from score_trans.services.render.main import _a4_renderer

    score = parse_jianpu_score("1=C\n2/4\nq[5'+3+1,]. s[5'+3+1,] 1 | h[5+3+1] |")
    page = _a4_renderer(
        RenderOptions(), A4LayoutOptions(measures_per_system=5, note_size_percent=size)
    ).render_scores([score])[0]
    assert not page.scene.geometry_issues
    root = ET.fromstring(page.svg)
    dash = next(
        node for node in root.iter() if node.attrib.get("class") == "extension-line"
    )
    assert float(dash.attrib["x2"]) - float(dash.attrib["x1"]) == pytest.approx(
        11 * 0.82 * size / 100, abs=0.002
    )
    beam = next(
        node
        for node in root.iter()
        if "beam-line" in node.attrib.get("class", "").split()
    )
    assert float(beam.attrib["stroke-width"]) == pytest.approx(
        1.8 * 0.82 * size / 100, abs=0.001
    )


def test_chord_tie_endpoints_follow_matching_tones_when_stack_changes() -> None:
    import re
    from score_trans.services.render.engraving.renderer import _Anchor, _spanner
    from score_trans.services.render.engraving.scene import BBox

    first = Event("note", Fraction(1), [JianpuPitch(5), JianpuPitch(3), JianpuPitch(1)])
    last = Event("note", Fraction(1), [JianpuPitch(5), JianpuPitch(3)])
    node = _spanner(
        "tie",
        _Anchor(100, 100, BBox(90, 40, 20, 60), first),
        _Anchor(200, 100, BBox(190, 60, 20, 40), last),
    )
    assert len(node.children) == 2
    for tie in node.children:
        coordinates = [
            float(value) for value in re.findall(r"[-\d.]+", str(tie.attrs["d"]))
        ]
        assert coordinates[7] - coordinates[1] > 10


def test_short_rest_does_not_create_an_oversized_hole_before_chords() -> None:
    sparse = Measure(
        "1",
        duration=Fraction(2),
        events=[Event("rest", Fraction(2), start=Fraction(0))],
    )
    dense = Measure(
        "1",
        duration=Fraction(2),
        events=[
            Event("rest", Fraction(1, 2), start=Fraction(0)),
            Event(
                "note",
                Fraction(1, 2),
                [JianpuPitch(3), JianpuPitch(1)],
                start=Fraction(1, 2),
            ),
            Event(
                "note",
                Fraction(1, 2),
                [JianpuPitch(3), JianpuPitch(1)],
                start=Fraction(1),
            ),
            Event(
                "note", Fraction(1, 2), [JianpuPitch(5, octave=1)], start=Fraction(3, 2)
            ),
        ],
    )
    positions = _shared_cell_positions(
        [sparse, dense], 0, 300, PublicationStyle(short_note_gap_scale=0.2)
    )
    anchors = [positions[Fraction(index, 2)] for index in range(4)]
    gaps = [b - a for a, b in itertools.pairwise(anchors)]
    assert max(gaps) - min(gaps) < 6
