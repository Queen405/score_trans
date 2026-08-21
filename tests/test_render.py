from __future__ import annotations

from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from score_trans.domain.jianpu import parse_jianpu_score
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
from score_trans.services.render.main import (
    render_jianpu_page_svg,
    render_jianpu_svg,
    render_score_page_svg,
    render_score_svg,
    render_scores_a4_pages,
)
from score_trans.services.render.engraving.renderer import (
    _Cell,
    _system_extra_height,
)
from score_trans.services.render.engraving.style import PublicationStyle

from tests.fixtures.render_cases import (
    overfull_tail_duration_score,
    staccato_score,
)


def _root(svg: str) -> ET.Element:
    return ET.fromstring(svg)


def _translate(node: ET.Element) -> tuple[float, float]:
    match = re.search(r"translate\(([-\d.]+) ([-\d.]+)\)", node.attrib["transform"])
    assert match is not None
    return float(match.group(1)), float(match.group(2))


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
    assert root.attrib["data-engine-version"] == "publication-2"
    assert "春江" in svg
    assert "<path" in svg


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

    assert len(rows) == 4


def test_measure_attributes_only_render_when_key_or_meter_changes() -> None:
    score = parse_jianpu_score("1=C\n4/4\n1 | 2 | 3 |")
    score.measures[2].target_key = "G"

    svg = render_score_svg(score)

    assert svg.count('class="measure-attribute"') == 1


def test_measure_attribute_reserves_space_before_first_event() -> None:
    score = parse_jianpu_score("1=C\n4/4\n1 | #2 |")
    score.measures[1].target_key = "F"
    score.measures[1].beats_per_measure = 3
    root = _root(render_score_svg(score))
    attribute = next(
        node for node in root.iter() if node.attrib.get("class") == "measure-attribute"
    )
    second_note = [node for node in root.iter() if node.attrib.get("class") == "note"][
        1
    ]
    attribute_x, _ = _translate(attribute)
    note_x, _ = _translate(second_note)
    attribute_width = font_registry().measure(
        attribute.attrib["aria-label"], float(attribute.attrib["data-font-size"])
    )
    note_width = font_registry().measure(
        second_note.attrib["aria-label"], float(second_note.attrib["data-font-size"])
    )

    assert attribute_x + attribute_width + 8 <= note_x - note_width / 2


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


def test_staccato_uses_a_bounded_vector_circle() -> None:
    root = _root(render_score_svg(staccato_score()))
    staccato_nodes = [
        node for node in root.iter() if "staccato" in node.attrib.get("class", "")
    ]

    assert staccato_nodes
    assert any(node.tag.endswith("circle") for node in staccato_nodes)
    circle = next(node for node in staccato_nodes if node.tag.endswith("circle"))
    assert float(circle.attrib["r"]) <= 3.0


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
