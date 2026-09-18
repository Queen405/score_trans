from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from fractions import Fraction
from itertools import pairwise
from pathlib import Path

import pytest
from score_trans.domain.jianpu import parse_jianpu_score
from score_trans.exec.render.actions import RenderActions, _renumber_scores_continuously
from score_trans.models.settings.config import ToolConfig
from score_trans.models.score import (
    Beam,
    Event,
    JianpuPitch,
    JianpuScore,
    Measure,
    TextBlock,
    TupletSpan,
)
from score_trans.services.render import (
    A4LayoutOptions,
    PublicationRenderService,
    RenderOptions,
)
from score_trans.services.render.engraving.fonts import font_registry
from score_trans.services.render.engraving.geometry import (
    mark_layouts,
    measure_event_ink,
    pitch_layouts,
)
from score_trans.services.render.engraving.renderer import (
    PublicationRenderer,
    _Anchor,
    _Cell,
    _draw_explicit_beam_level,
    _draw_rhythm_lines,
    _draw_rhythm_run,
    _duration_spring,
    _event_positions,
    _event_visual_extents,
    _intrinsic_measure_width,
    _rhythm_line_base,
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
from score_trans.services.files.upload_service import UploadService

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


def _text_bbox(node: ET.Element) -> tuple[float, float, float, float]:
    left, top, right, bottom = _text_box(node)
    return left, top, right - left, bottom - top


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
    assert root.attrib["data-engine-version"] == "publication-15"
    assert "春江" in svg
    assert "<path" in svg


def test_score_meta_displays_the_default_tempo_when_text_omits_it() -> None:
    root = _root(render_jianpu_svg("1=C\n4/4\n1 2 3 4 |"))
    meta = next(
        node for node in root.iter() if node.attrib.get("class") == "score-meta"
    )

    assert "♩=120" in meta.attrib["aria-label"]


def test_measure_level_tempo_renders_once_in_the_upper_annotation_band() -> None:
    score = parse_jianpu_score("tempo=120\n1=C\n4/4\n1 2 3 4 |\ntempo=80\n5 6 7 1 *2 |")
    score.measures[1].text_blocks.append(
        TextBlock("♩=80", role="expression", direction_kind="metronome")
    )
    root = _root(render_score_svg(score))
    tempo_marks = [
        node for node in root.iter() if node.attrib.get("class") == "tempo-mark"
    ]

    assert [node.attrib["aria-label"] for node in tempo_marks] == ["♩=80"]
    assert (
        len([node for node in root.iter() if node.attrib.get("aria-label") == "♩=80"])
        == 1
    )

    tempo_box = _text_bbox(tempo_marks[0])
    measure_number = next(
        node
        for node in root.iter()
        if node.attrib.get("class") == "measure-no"
        and node.attrib.get("aria-label") == "2"
    )
    repeat_count = next(
        node for node in root.iter() if node.attrib.get("class") == "repeat-count"
    )
    _assert_horizontal_clearance(_text_bbox(measure_number), tempo_box, 6)
    _assert_horizontal_clearance(tempo_box, _text_bbox(repeat_count), 6)


def test_explicit_dotted_full_measure_rest_is_rendered() -> None:
    score = parse_jianpu_score("1=C\n4/4\n0. |")

    assert len(score.measures) == 1
    assert score.measures[0].events[0].kind == "rest"
    assert score.measures[0].events[0].dotted == 1

    root = _root(render_score_svg(score))
    rests = [
        node
        for node in root.iter()
        if node.attrib.get("data-note-token") in {"0", "0."}
    ]
    assert len(rests) == 2
    assert not any(node.attrib.get("class") == "extension-line" for node in root.iter())
    assert any("duration-line" in node.attrib.get("class", "") for node in root.iter())
    assert (
        len([node for node in root.iter() if "measure" in node.attrib.get("class", "")])
        >= 2
    )


def test_long_rests_render_as_repeated_zeros_without_extension_lines() -> None:
    root = _root(render_jianpu_svg("1=C\n4/4\nw0 | h0 3 4 |"))

    zeros = [
        node
        for node in root.iter()
        if node.attrib.get("class") == "note" and node.attrib.get("aria-label") == "0"
    ]
    assert len(zeros) == 6
    assert not any(node.attrib.get("class") == "extension-line" for node in root.iter())


def test_tremolo_mark_hugs_note_bottom_right() -> None:
    style = PublicationStyle()

    dashed = Event(
        kind="note",
        duration=Fraction(2),
        pitches=[JianpuPitch(3)],
        ornaments=["tremolo"],
    )
    root = _root(
        render_score_svg(
            JianpuScore(measures=[Measure("1", duration=Fraction(4), events=[dashed])])
        )
    )
    note = next(node for node in root.iter() if node.attrib.get("class") == "note")
    extension = next(
        node for node in root.iter() if node.attrib.get("class") == "extension-line"
    )
    mark = next(
        node
        for node in root.iter()
        if "performance-mark" in node.attrib.get("class", "").split()
        and node.attrib.get("data-mark") == "tremolo"
    )
    note_box = _bbox(note)
    mark_box = _bbox(mark)
    assert mark_box[0] <= float(extension.attrib["x1"])
    assert mark_box[0] >= note_box[0] + note_box[2]
    note_bottom = note_box[1] + note_box[3]
    mark_center = mark_box[1] + mark_box[3] / 2
    assert abs(mark_center - note_bottom) <= 1.0
    assert mark_box[1] + mark_box[3] > note_bottom

    underlined = Event(
        kind="note",
        duration=Fraction(1, 2),
        pitches=[JianpuPitch(3)],
        ornaments=["tremolo"],
    )
    root = _root(
        render_score_svg(
            JianpuScore(
                measures=[Measure("1", duration=Fraction(4), events=[underlined])]
            )
        )
    )
    note = next(node for node in root.iter() if node.attrib.get("class") == "note")
    beam = next(
        node for node in root.iter() if "duration-line" in node.attrib.get("class", "")
    )
    mark = next(
        node
        for node in root.iter()
        if "performance-mark" in node.attrib.get("class", "").split()
        and node.attrib.get("data-mark") == "tremolo"
    )
    note_box = _bbox(note)
    mark_box = _bbox(mark)
    assert mark_box[0] >= note_box[0] + note_box[2]
    note_bottom = note_box[1] + note_box[3]
    assert abs(mark_box[1] + mark_box[3] / 2 - note_bottom) <= 1.0
    assert mark_box[1] + mark_box[3] < float(beam.attrib["y1"])

    chord = Event(
        kind="note",
        duration=Fraction(1),
        pitches=[JianpuPitch(5), JianpuPitch(3), JianpuPitch(1)],
        ornaments=["tremolo"],
    )
    marks = mark_layouts(chord, style)
    tremolo_marks = [mark for mark in marks if mark.mark_id == "tremolo"]
    rows = pitch_layouts(chord, style)
    assert len(tremolo_marks) == len(rows) == 3
    for mark, row in zip(tremolo_marks, rows, strict=True):
        assert mark.ink_box.left >= row.note_box.right
        assert (
            abs((mark.ink_box.top + mark.ink_box.bottom) / 2 - row.note_box.bottom)
            <= 1.0
        )


def test_hidden_rest_is_not_rendered_in_svg() -> None:
    score = JianpuScore(target_key="C", source_key="C", beats=4, beat_type=4)
    score.measures.append(
        Measure(
            source_number="1",
            duration=Fraction(4, 1),
            events=[
                Event(
                    kind="note",
                    duration=Fraction(1, 1),
                    pitches=[JianpuPitch(1)],
                ),
                Event(kind="rest", duration=Fraction(1, 1), hidden=True),
                Event(
                    kind="note",
                    duration=Fraction(1, 1),
                    pitches=[JianpuPitch(3)],
                ),
                Event(
                    kind="note",
                    duration=Fraction(1, 1),
                    pitches=[JianpuPitch(4)],
                ),
            ],
        )
    )

    root = _root(render_score_svg(score))
    tokens = {node.attrib.get("data-note-token") for node in root.iter()}
    assert "0" not in tokens
    assert "1" in tokens and "3" in tokens and "4" in tokens


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


def test_dotted_quarter_note_renders_dot_without_extension_line() -> None:
    # 附点四分音符（1.5 拍）的小数部分由附点表达，不应再画延长横线。
    root = _root(render_score_svg(long_duration_score()))

    assert any(node.attrib.get("class") == "rhythm-dot" for node in root.iter())
    assert not any(node.attrib.get("class") == "extension-line" for node in root.iter())


def test_dotted_half_note_renders_dashes_without_rhythm_dot() -> None:
    # 附点二分音符（3 拍）是纯整数拍，用横线表达，不再画附点。
    root = _root(render_jianpu_svg("1=C\n4/4\nh1. 2 |"))

    dashes = [
        node for node in root.iter() if node.attrib.get("class") == "extension-line"
    ]
    assert len(dashes) == 2
    assert not any(node.attrib.get("class") == "rhythm-dot" for node in root.iter())


def _extension_centers(root: ET.Element) -> list[float]:
    return [
        (float(node.attrib["x1"]) + float(node.attrib["x2"])) / 2
        for node in root.iter()
        if node.attrib.get("class") == "extension-line"
    ]


def _note_centers(root: ET.Element) -> list[float]:
    centers: list[float] = []
    for node in root.iter():
        if node.attrib.get("class") == "note":
            values = [float(value) for value in node.attrib["data-bbox"].split()]
            centers.append(values[0] + values[2] / 2)
    return centers


def test_whole_note_dashes_fill_beat_slots_evenly() -> None:
    root = _root(render_jianpu_svg("1=C\n4/4\nw1 |"))

    notes = _note_centers(root)
    dashes = _extension_centers(root)
    assert len(notes) == 1
    assert len(dashes) == 3

    steps = [b - a for a, b in pairwise([notes[0], *dashes])]
    assert all(step > 20.0 for step in steps)
    assert max(steps) - min(steps) <= 1.0


def test_whole_note_measure_width_matches_quarter_note_measure() -> None:
    root = _root(render_jianpu_svg("1=C\n4/4\nw1 | 1 2 3 4 |"))
    barlines = sorted(
        float(node.attrib["x1"])
        for node in root.iter()
        if node.tag.endswith("line") and "measure" in node.attrib.get("class", "")
    )
    widths = [b - a for a, b in pairwise(barlines)]

    assert len(widths) >= 2
    assert abs(widths[0] - widths[1]) <= 8.0


def test_subbeat_note_extension_dash_sits_between_beat_slots() -> None:
    root = _root(render_jianpu_svg("1=C\n4/4\n1 2 s3- 4 |"))

    notes = _note_centers(root)
    dashes = _extension_centers(root)
    assert len(notes) == 4
    assert len(dashes) == 1
    assert notes[2] < dashes[0] < notes[3]


def test_dotted_half_note_dashes_are_evenly_spaced() -> None:
    root = _root(render_jianpu_svg("1=C\n4/4\nh1. 2 |"))

    notes = _note_centers(root)
    dashes = _extension_centers(root)
    assert len(notes) == 2
    assert len(dashes) == 2
    assert notes[0] < dashes[0] < dashes[1] < notes[1]

    steps = [b - a for a, b in pairwise([notes[0], *dashes, notes[1]])]
    assert max(steps) - min(steps) <= 6.0


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


def test_break_beams_at_beat_splits_rhythm_lines_per_beat() -> None:
    events = [
        Event(
            kind="note",
            duration=Fraction(1, 2),
            pitches=[JianpuPitch(index + 1)],
            start=Fraction(index, 2),
        )
        for index in range(8)
    ]
    scene = PublicationScene(640.0, 180.0, 0)
    anchors = [
        _Anchor(
            60.0 * (index + 1),
            100.0,
            BBox(60.0 * (index + 1), 80.0, 20.0, 28.0),
            events[index],
        )
        for index in range(8)
    ]
    beat_boundaries = [Fraction(b) for b in (0, 1, 2, 3, 4)]

    _draw_rhythm_lines(
        scene,
        anchors,
        style=PublicationStyle(break_beams_at_beat=True),
        beat_boundaries=beat_boundaries,
    )
    lines = [
        node for node in scene.nodes if "duration-line" in node.attrs.get("class", "")
    ]

    assert len(lines) == 4

    spans = sorted((float(node.attrs["x1"]), float(node.attrs["x2"])) for node in lines)
    for (prev_x1, prev_x2), (curr_x1, curr_x2) in zip(spans, spans[1:]):
        assert curr_x1 - prev_x2 >= 15.0


def test_break_beams_at_beat_disabled_keeps_continuous_line() -> None:
    events = [
        Event(
            kind="note",
            duration=Fraction(1, 2),
            pitches=[JianpuPitch(index + 1)],
            start=Fraction(index, 2),
        )
        for index in range(8)
    ]
    scene = PublicationScene(640.0, 180.0, 0)
    anchors = [
        _Anchor(
            60.0 * (index + 1),
            100.0,
            BBox(60.0 * (index + 1), 80.0, 20.0, 28.0),
            events[index],
        )
        for index in range(8)
    ]
    beat_boundaries = [Fraction(b) for b in (0, 1, 2, 3, 4)]

    _draw_rhythm_lines(
        scene,
        anchors,
        style=PublicationStyle(break_beams_at_beat=False),
        beat_boundaries=beat_boundaries,
    )
    lines = [
        node for node in scene.nodes if "duration-line" in node.attrs.get("class", "")
    ]

    assert len(lines) == 1


def test_break_beams_at_beat_splits_sixteenth_both_levels() -> None:
    events = [
        Event(
            kind="note",
            duration=Fraction(1, 4),
            pitches=[JianpuPitch(index + 1)],
            start=Fraction(index, 4),
        )
        for index in range(8)
    ]
    scene = PublicationScene(640.0, 180.0, 0)
    anchors = [
        _Anchor(
            60.0 * (index + 1),
            100.0,
            BBox(60.0 * (index + 1), 80.0, 20.0, 28.0),
            events[index],
        )
        for index in range(8)
    ]
    beat_boundaries = [Fraction(b) for b in (0, 1, 2)]

    _draw_rhythm_lines(
        scene,
        anchors,
        style=PublicationStyle(break_beams_at_beat=True),
        beat_boundaries=beat_boundaries,
    )
    lines = [
        node for node in scene.nodes if "duration-line" in node.attrs.get("class", "")
    ]

    assert len(lines) == 4


def test_live_render_follows_break_beams_option() -> None:
    """即时渲染（render_score_svg 路径）随 RenderOptions.break_beams_at_beat 生效。"""
    score = parse_jianpu_score("1=C\n4/4\nq1 q2 q3 q4 q5 q6 q7 q1 |")

    off_svg = render_score_svg(score, RenderOptions(break_beams_at_beat=False))
    on_svg = render_score_svg(score, RenderOptions(break_beams_at_beat=True))

    off_root = _root(off_svg)
    on_root = _root(on_svg)
    off_beams = [
        node
        for node in off_root.iter()
        if "duration-line" in node.attrib.get("class", "")
    ]
    on_beams = [
        node
        for node in on_root.iter()
        if "duration-line" in node.attrib.get("class", "")
    ]
    assert len(off_beams) == 1
    assert len(on_beams) == 4


def test_simultaneous_independent_voices_remain_distinct_and_do_not_overlap() -> None:
    """复调小节的多 voice 渲染为上下两排：垂直分离、同 onset 水平对齐。"""
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
    by_source = {
        node.attrib["data-source-ids"]: [
            float(value) for value in node.attrib["data-bbox"].split()
        ]
        for node in anchors
    }

    assert set(by_source) == {"voice-1", "voice-2"}
    v1_box = by_source["voice-1"]
    v2_box = by_source["voice-2"]
    # 垂直分离：voice 2 排在 voice 1 下方
    assert v2_box[1] > v1_box[1]
    # 同一 onset 水平对齐（比较中心点：不同字形的 ink 左边缘本就不同）
    assert v1_box[0] + v1_box[2] / 2 == pytest.approx(
        v2_box[0] + v2_box[2] / 2, abs=1.0
    )
    # 小节线延伸到下排声线之下
    barlines = [
        node
        for node in root.iter()
        if node.tag.endswith("line") and "measure" in node.attrib.get("class", "")
    ]
    assert barlines
    bar_bottom = max(float(node.attrib["y2"]) for node in barlines)
    assert bar_bottom >= v2_box[1]


def test_polyphonic_measure_renders_two_lanes_with_aligned_onsets() -> None:
    """用户场景：休止+和弦线与全音符线渲染为两排，barline 覆盖下排。"""
    events = [
        # lane 1：四分休止 + 三个四分音符
        Event(kind="rest", duration=Fraction(1), start=Fraction(0), voice="1"),
        *[
            Event(
                kind="note",
                duration=Fraction(1),
                pitches=[JianpuPitch(1), JianpuPitch(3)],
                start=Fraction(index),
                voice="1",
                source_ids=[f"chord-{index}"],
            )
            for index in (1, 2, 3)
        ],
        # lane 2：全音符（低音）
        Event(
            kind="note",
            duration=Fraction(4),
            pitches=[JianpuPitch(1, octave=-1)],
            start=Fraction(0),
            voice="2",
            source_ids=["bass"],
        ),
    ]
    score = JianpuScore(measures=[Measure("1", duration=Fraction(4), events=events)])

    root = _root(render_score_svg(score))
    anchors = [
        node for node in root.iter() if "source-anchor" in node.attrib.get("class", "")
    ]
    by_source = {
        node.attrib["data-source-ids"]: [
            float(value) for value in node.attrib["data-bbox"].split()
        ]
        for node in anchors
        if node.attrib.get("data-source-ids")
    }
    assert set(by_source) == {"chord-1", "chord-2", "chord-3", "bass"}
    lane1_y = by_source["chord-1"][1]
    bass_box = by_source["bass"]
    # 垂直分离
    assert bass_box[1] > lane1_y
    # 全音符的起始 onset（0）与 lane 1 的休止符同 x：休止符没有 source_ids，
    # 用 lane 1 第一个和弦（onset 1）验证 x 单调递增即可
    assert by_source["chord-1"][0] < by_source["chord-2"][0] < by_source["chord-3"][0]
    # barline 高度覆盖下排
    barlines = [
        node
        for node in root.iter()
        if node.tag.endswith("line") and "measure" in node.attrib.get("class", "")
    ]
    bar_bottom = max(float(node.attrib["y2"]) for node in barlines)
    assert bar_bottom >= bass_box[1]


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

    clearance = PublicationStyle().accidental_clearance
    assert accidental_x + accidental_width / 2 + clearance <= note_x - note_width / 2


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
        if "performance-mark" in node.attrib.get("class", "").split()
        and ({"articulation", "ornament"} & set(node.attrib.get("class", "").split()))
    ]

    assert len(marks) == 2
    assert all(_bbox(mark)[3] + 2 <= attachment_top for mark in marks)


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
        if "performance-mark" in mark.attrib.get("class", "").split():
            left, top, right, bottom = _bbox(mark)
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


def _sixteenth_run(count: int = 16) -> tuple[list[Event], Measure]:
    events = [
        Event(
            kind="note",
            duration=Fraction(1, 4),
            start=Fraction(index, 4),
            pitches=[JianpuPitch(index % 7 + 1)],
        )
        for index in range(count)
    ]
    measure = Measure(
        "1",
        duration=Fraction(count, 4),
        events=events,
        beats_per_measure=count // 4,
        beat_type=4,
    )
    return events, measure


def _boundary_within_ratio(
    events: list[Event],
    measure: Measure,
    left: float,
    right: float,
    style: PublicationStyle,
    boundary_indices: set[int],
) -> float:
    centers = _event_positions(events, left, right, measure, style)
    gaps = [end - start for start, end in pairwise(centers)]
    boundary = [gaps[index] for index in boundary_indices]
    within = [gap for index, gap in enumerate(gaps) if index not in boundary_indices]
    return (sum(boundary) / len(boundary)) / (sum(within) / len(within))


def test_subdivided_beats_get_a_boundary_gap() -> None:
    # 16 sixteenths in 4/4: within-beat gaps are uniform; each beat boundary
    # (indices 3, 7, 11) is widened by a ratio so beats stay distinguishable.
    events, measure = _sixteenth_run()
    style = PublicationStyle()
    centers = _event_positions(events, 100.0, 900.0, measure, style)
    gaps = [right - left for left, right in pairwise(centers)]
    boundary_gaps = [gaps[i] for i in (3, 7, 11)]
    within_gaps = [gap for index, gap in enumerate(gaps) if index not in {3, 7, 11}]

    # A ratio, not an absolute increment: the visible division must survive
    # whatever stretch factor the line density imposes.
    ratio = min(boundary_gaps) / max(within_gaps)
    assert ratio >= 1.0 + style.beat_boundary_ratio - 0.02
    assert max(within_gaps) - min(within_gaps) < 1.0


def test_beat_boundary_ratio_is_stable_across_line_density() -> None:
    # The core guarantee of the ratio-based approach: the same events laid out
    # at three very different spans keep the same boundary/within proportion.
    # The old absolute-increment implementation drifted 1.24 / 1.16 / 1.08 here,
    # which is why the division was invisible on wide systems.
    events, measure = _sixteenth_run()
    style = PublicationStyle()
    ratios = [
        _boundary_within_ratio(events, measure, 100.0, right, style, {3, 7, 11})
        for right in (640.0, 900.0, 1600.0)
    ]

    assert max(ratios) - min(ratios) < 0.02
    assert min(ratios) >= 1.0 + style.beat_boundary_ratio - 0.02


def test_overfull_measure_keeps_beat_division() -> None:
    # 24 sixteenths crammed into a narrow span falls back to
    # _bounded_event_positions; the beat division must survive that path too.
    events, measure = _sixteenth_run(24)
    style = PublicationStyle()
    boundary_indices = {3, 7, 11, 15, 19}
    ratio = _boundary_within_ratio(
        events, measure, 100.0, 400.0, style, boundary_indices
    )

    assert ratio >= 1.0 + style.beat_boundary_ratio - 0.05


def test_one_note_per_beat_has_no_boundary_gap() -> None:
    # 4 quarter notes: one event per beat is not "subdivided", so no beat gap
    # is applied and spacing stays perfectly even.
    events = [
        Event(
            kind="note",
            duration=Fraction(1),
            start=Fraction(index),
            pitches=[JianpuPitch(index % 7 + 1)],
        )
        for index in range(4)
    ]
    measure = Measure(
        "1", duration=Fraction(4), events=events, beats_per_measure=4, beat_type=4
    )
    centers = _event_positions(events, 100.0, 900.0, measure, PublicationStyle())
    gaps = [right - left for left, right in pairwise(centers)]

    assert max(gaps) - min(gaps) < 1.0


def test_compound_meter_one_eighth_per_beat_has_no_boundary_gap() -> None:
    # 6/8 with 6 eighth notes: the parser lays out 6 beats of one eighth each,
    # so no beat is subdivided and spacing stays even.
    events = [
        Event(
            kind="note",
            duration=Fraction(1, 2),
            start=Fraction(index, 2),
            pitches=[JianpuPitch(index % 7 + 1)],
        )
        for index in range(6)
    ]
    measure = Measure(
        "1", duration=Fraction(3), events=events, beats_per_measure=6, beat_type=8
    )
    centers = _event_positions(events, 100.0, 900.0, measure, PublicationStyle())
    gaps = [right - left for left, right in pairwise(centers)]

    assert max(gaps) - min(gaps) < 1.0


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
        node for node in scene.nodes if "duration-line" in node.attrs.get("class", "")
    ]

    assert len(lines) == 2
    assert float(lines[0].attrs["y1"]) == float(lines[1].attrs["y1"])


def test_rhythm_lines_ignore_non_rhythmic_high_chord_for_shared_baseline() -> None:
    high_chord = Event(
        kind="note",
        duration=Fraction(1),
        pitches=[
            JianpuPitch(7, octave=2),
            JianpuPitch(5, octave=1),
            JianpuPitch(3),
            JianpuPitch(1, octave=-1),
        ],
        voice="1",
    )
    rhythmic = Event(
        kind="note",
        duration=Fraction(1, 2),
        pitches=[JianpuPitch(3)],
        voice="1",
    )
    scene = PublicationScene(320.0, 180.0, 0)
    anchors = [
        _Anchor(130.0, 100.0, BBox(120.0, 70.0, 20.0, 60.0), high_chord),
        _Anchor(220.0, 100.0, BBox(210.0, 90.0, 20.0, 28.0), rhythmic),
    ]

    _draw_rhythm_lines(scene, anchors, style=PublicationStyle())
    line = next(
        node for node in scene.nodes if "duration-line" in node.attrs.get("class", "")
    )

    assert float(line.attrs["y1"]) == _rhythm_line_base(anchors[1], PublicationStyle())


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


def test_span_primitives_emit_truthful_bboxes() -> None:
    source = Event(
        kind="note",
        duration=Fraction(1),
        pitches=[JianpuPitch(3)],
        source_ids=["note-span"],
        source_roles={"note": ["note-span"]},
        tie_start=True,
        slur_start=True,
    )
    target = Event(
        kind="note",
        duration=Fraction(1),
        pitches=[JianpuPitch(4)],
        source_ids=["note-target"],
        source_roles={"note": ["note-target"]},
        tie_stop=True,
        slur_stop=True,
    )
    tuplet_events = [
        Event(
            kind="note",
            duration=Fraction(1, 3),
            start=Fraction(index, 3),
            pitches=[JianpuPitch(index + 1)],
            tuplet_id="span-group",
            tuplet_count=3,
            source_ids=[f"tuplet-{index}"],
            source_roles={"note": [f"tuplet-{index}"]},
        )
        for index in range(3)
    ]
    score = JianpuScore(
        measures=[
            Measure("1", duration=Fraction(2), events=[source, target]),
            Measure("2", duration=Fraction(1), events=tuplet_events),
        ]
    )
    root = _root(render_score_svg(score))

    span_nodes = [
        node
        for node in root.iter()
        if node.attrib.get("class") in {"tie", "slur", "tuplet-bracket"}
    ]

    assert span_nodes
    assert all(
        len(node.attrib.get("data-bbox", "").split()) == 4 for node in span_nodes
    )


def test_rhythm_line_registers_span_bbox_for_source_map() -> None:
    first = Event(
        kind="note",
        duration=Fraction(1, 2),
        pitches=[JianpuPitch(3)],
        start=Fraction(0),
        source_ids=["beam-a"],
        source_roles={"note": ["beam-a"]},
    )
    second = Event(
        kind="note",
        duration=Fraction(1, 2),
        pitches=[JianpuPitch(4)],
        start=Fraction(1, 2),
        source_ids=["beam-b"],
        source_roles={"note": ["beam-b"]},
    )
    page = PublicationRenderer().render_scores(
        [
            JianpuScore(
                measures=[Measure("1", duration=Fraction(1), events=[first, second])]
            )
        ]
    )[0]

    line = next(
        node
        for node in page.scene.nodes
        if "duration-line" in node.attrs.get("class", "")
    )
    assert len(line.attrs.get("data-bbox", "").split()) == 4
    assert page.scene.source_boxes["beam-a"].height > 0
    assert page.scene.source_boxes["beam-b"].height > 0


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


def test_tuplet_notes_are_compact_and_share_a_rhythm_line() -> None:
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

    assert len(beams) == 1
    note_centers = [
        float(node.attrib["data-bbox"].split()[0])
        + float(node.attrib["data-bbox"].split()[2]) / 2
        for node in notes
    ]
    assert float(beams[0].attrib["x1"]) < note_centers[0]
    assert float(beams[0].attrib["x2"]) > note_centers[-1]
    assert note_centers[-1] - note_centers[0] <= 48
    assert any("tuplet-bracket" in node.attrib.get("class", "") for node in root.iter())


def test_sextuplet_notes_render_two_rhythm_line_levels() -> None:
    events = [
        Event(
            kind="note",
            duration=Fraction(1, 6),
            pitches=[JianpuPitch(index % 7 + 1)],
            start=Fraction(index, 6),
            tuplet_id="sextuplet-1",
            tuplet_count=6,
            tuplet_index=index,
        )
        for index in range(6)
    ]
    score = JianpuScore(measures=[Measure("1", duration=Fraction(4), events=events)])

    root = _root(render_score_svg(score))
    beams = [
        node for node in root.iter() if "duration-line" in node.attrib.get("class", "")
    ]

    assert len(beams) == 2
    levels = {float(node.attrib["y1"]) for node in beams}
    assert len(levels) == 2


def test_tuplet_lyric_clears_the_rhythm_line() -> None:
    root = _root(render_jianpu_svg("1=C\n4/4\n$123$ 4 |\nL: 春 江"))

    beams = [
        node for node in root.iter() if "duration-line" in node.attrib.get("class", "")
    ]
    lyrics = [node for node in root.iter() if node.attrib.get("class") == "lyric"]

    assert beams and lyrics
    beam_bottom = max(float(node.attrib["y1"]) for node in beams)
    first_lyric_top = min(float(node.attrib["data-bbox"].split()[1]) for node in lyrics)
    assert first_lyric_top >= beam_bottom


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
    assert bracket.attrib["d"].count(" C ") == 2
    assert " V " not in bracket.attrib["d"]
    assert " H " not in bracket.attrib["d"]


def test_nested_tuplet_spans_render_one_bracket_per_span() -> None:
    events = [
        Event(
            kind="note",
            duration=Fraction(1, 3),
            start=Fraction(index, 3),
            pitches=[JianpuPitch(index + 1)],
            tuplet_id="outer",
            tuplet_count=3,
            tuplet_index=index,
            tuplet_spans=[
                TupletSpan("outer", start=index == 0, stop=index == 2),
                TupletSpan("inner", start=index == 0, stop=index == 2),
            ],
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

    assert len(brackets) == 2
    assert (
        len(
            {
                re.search(r"M [-\d.]+ ([-\d.]+)", node.attrib["d"]).group(1)
                for node in brackets
            }
        )
        == 2
    )  # type: ignore[union-attr]


def test_tuplet_spans_without_primary_id_still_render_a_bracket() -> None:
    events = [
        Event(
            kind="note",
            duration=Fraction(1, 3),
            start=Fraction(index, 3),
            pitches=[JianpuPitch(index + 1)],
            tuplet_spans=[TupletSpan("span-only", start=index == 0, stop=index == 2)],
        )
        for index in range(3)
    ]
    root = _root(
        render_score_svg(
            JianpuScore(measures=[Measure("1", duration=Fraction(1), events=events)])
        )
    )

    assert any(node.attrib.get("class") == "tuplet-bracket" for node in root.iter())


def test_cross_measure_tuplet_brackets_mark_continuation_segments() -> None:
    first = Event(
        kind="note",
        duration=Fraction(1, 3),
        pitches=[JianpuPitch(3)],
        tuplet_id="cross",
        tuplet_count=3,
        tuplet_start=True,
        tuplet_spans=[TupletSpan("cross", start=True)],
    )
    second = Event(
        kind="note",
        duration=Fraction(1, 3),
        pitches=[JianpuPitch(4)],
        tuplet_id="cross",
        tuplet_count=3,
        tuplet_spans=[TupletSpan("cross")],
    )
    third = Event(
        kind="note",
        duration=Fraction(1, 3),
        pitches=[JianpuPitch(5)],
        tuplet_id="cross",
        tuplet_count=3,
        tuplet_stop=True,
        tuplet_spans=[TupletSpan("cross", stop=True)],
    )
    pages = render_scores_a4_pages(
        [
            JianpuScore(
                measures=[Measure("1", duration=Fraction(1, 3), events=[first])]
            ),
            JianpuScore(
                measures=[Measure("2", duration=Fraction(2, 3), events=[second, third])]
            ),
        ]
    )
    brackets = [
        node
        for page in pages
        for node in _root(page.svg).iter()
        if node.attrib.get("class") == "tuplet-bracket"
    ]

    assert len(brackets) == 2
    assert {node.attrib.get("data-continuation") for node in brackets} == {
        "start",
        "end",
    }


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
        node
        for node in _root(render_score_svg(plain)).iter()
        if node.attrib.get("class") == "note"
    ]
    changed_notes = [
        node
        for node in _root(render_score_svg(changed)).iter()
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
    marks = [
        node
        for node in root.iter()
        if "performance-mark" in node.attrib.get("class", "").split()
        and "technical" in node.attrib.get("class", "").split()
    ]
    note_x, _note_y = _translate(note)
    note_bottom = _bbox(note)[1] + _bbox(note)[3]
    positions = {node.attrib["aria-label"]: _translate(node) for node in marks}
    tremolo_box = _bbox(
        next(node for node in marks if node.attrib["data-mark"] == "tremolo")
    )

    assert positions["scoop"][0] < note_x
    assert positions["tremolo"][0] > note_x
    assert tremolo_box[1] < note_bottom < tremolo_box[1] + tremolo_box[3]


def test_left_mark_does_not_overlap_note_or_accidental_ink() -> None:
    event = Event(
        kind="note",
        duration=Fraction(1),
        pitches=[JianpuPitch(3, accidental_text="####")],
        technical=["scoop"],
    )
    rows = pitch_layouts(event, PublicationStyle())
    marks = mark_layouts(event, PublicationStyle())
    scoop = next(mark for mark in marks if mark.mark_id == "scoop")

    assert all(
        scoop.ink_box.right <= box.left or scoop.ink_box.left >= box.right
        for row in rows
        for box in (row.note_box, row.accidental_box)
        if box is not None
    )


def test_above_marks_use_measured_stack_height() -> None:
    event = Event(
        kind="note",
        duration=Fraction(1),
        pitches=[JianpuPitch(3, octave=1)],
        articulations=["fermata", "accent"],
    )
    marks = mark_layouts(event, PublicationStyle())
    ordered = sorted(marks, key=lambda mark: mark.ink_box.top)

    assert len(ordered) == 2
    assert ordered[0].ink_box.bottom + 2 <= ordered[1].ink_box.top


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
    dynamic = next(
        node for node in root.iter() if node.attrib.get("class") == "dynamic"
    )
    dynamic_box = _text_box(dynamic)
    lowest_octave_dot_bottom = max(
        float(node.attrib["cy"]) + float(node.attrib["r"])
        for node in root.iter()
        if node.attrib.get("class") == "octave-dot"
    )

    assert dynamic_box[1] >= lowest_octave_dot_bottom + 5.9


def test_event_lyric_clears_low_octave_chord_attachments() -> None:
    event = Event(
        kind="note",
        duration=Fraction(1),
        pitches=[JianpuPitch(2), JianpuPitch(5), JianpuPitch(2, octave=-1)],
        lyric="春",
    )
    root = _root(render_score_svg(JianpuScore(measures=[Measure("1", events=[event])])))
    lyric = next(node for node in root.iter() if node.attrib.get("class") == "lyric")
    lyric_box = _text_box(lyric)
    lowest_octave_dot_bottom = max(
        float(node.attrib["cy"]) + float(node.attrib["r"])
        for node in root.iter()
        if node.attrib.get("class") == "octave-dot"
    )

    assert lyric_box[1] >= lowest_octave_dot_bottom + 6


def test_event_lyric_is_not_rendered_again_from_measure_text_block() -> None:
    event = Event(
        kind="note",
        duration=Fraction(1),
        pitches=[JianpuPitch(3)],
        lyric="春",
    )
    measure = Measure(
        "1",
        duration=Fraction(4),
        events=[event],
        text_blocks=[TextBlock("春", role="lyric", start=Fraction(0))],
    )

    root = _root(render_score_svg(JianpuScore(measures=[measure])))

    assert (
        sum(
            1
            for node in root.iter()
            if node.attrib.get("class") == "lyric"
            and node.attrib.get("aria-label") == "春"
        )
        == 1
    )


def test_wide_event_stays_centered_when_its_ink_cannot_fit() -> None:
    event = Event(
        kind="note",
        duration=Fraction(1),
        pitches=[JianpuPitch(3)],
        lyric="超长歌词" * 100,
    )
    measure = Measure("1", duration=Fraction(4), events=[event])
    style = PublicationStyle(page_width=400, margin_left=40, margin_right=40)
    page = PublicationRenderer(style).render_scores([JianpuScore(measures=[measure])])[
        0
    ]
    root = _root(page.svg)
    note = next(node for node in root.iter() if node.attrib.get("class") == "note")
    note_x, _note_y = _translate(note)

    assert style.margin_left <= note_x <= style.page_width - style.margin_right


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


def test_measure_repeat_count_is_rendered() -> None:
    root = _root(render_jianpu_svg("1=C\n4/4\n1 2 3 4 *3 |"))

    repeat_counts = [
        node.attrib.get("aria-label")
        for node in root.iter()
        if node.attrib.get("class") == "repeat-count"
    ]

    assert repeat_counts == ["*3"]


def test_measure_repeat_count_after_barline_is_rendered() -> None:
    root = _root(render_jianpu_svg("1=C\n4/4\n1 2 3 4 | *2"))

    repeat_counts = [
        node.attrib.get("aria-label")
        for node in root.iter()
        if node.attrib.get("class") == "repeat-count"
    ]

    assert repeat_counts == ["*2"]


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


def test_page_number_offset_is_applied_to_rendered_pages() -> None:
    score = parse_jianpu_score("1=C\n4/4\n" + " 1 |" * 20)
    score.measures[5].new_page = True
    pages = PublicationRenderer(PublicationStyle(page_height=500.0)).render_scores(
        [score], page_index_offset=3
    )

    assert len(pages) > 1
    assert 'class="annotation page-number"' in pages[0].svg
    assert ">4</text>" in pages[0].svg
    assert ">5</text>" in pages[1].svg


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


def _a4_svg_with_layout(
    score: JianpuScore,
    *,
    content_scale_percent: int = 100,
    system_gap_percent: int = 100,
    short_note_gap_percent: int = 100,
    beat_gap_percent: int = 100,
) -> tuple[ET.Element, object]:
    try:
        page = PublicationRenderService().build_scores_a4_svg_pages(
            [score],
            content_scale_percent=content_scale_percent,
            system_gap_percent=system_gap_percent,
            short_note_gap_percent=short_note_gap_percent,
            beat_gap_percent=beat_gap_percent,
        )[0]
    except TypeError as exc:
        pytest.fail(f"A4 renderer does not expose layout controls: {exc}")
    return _root(page.svg), page


def _physical_note_xs(root: ET.Element) -> list[float]:
    content = next(
        node for node in root if node.attrib.get("class") == "publication-content"
    )
    content_scale = _scale(content)
    return [
        _translate(node)[0] * content_scale
        for node in content.iter()
        if node.attrib.get("class") == "note"
    ]


def test_a4_content_scale_preserves_page_and_scales_render_metadata(
    tmp_path: Path,
) -> None:
    score = parse_jianpu_score("title=缩放测试\n1=C\n4/4\nq1 q2 q3 q4 |")
    score.measures[0].events[0].source_ids = ["s1:i10"]

    page = PublicationRenderService().render_scores_a4_svg_pages(
        [score],
        tmp_path / "scaled.svg",
        content_scale_percent=67,
        system_gap_percent=100,
        short_note_gap_percent=100,
    )[0]
    root = _root(page.path.read_text(encoding="utf-8"))

    assert root.attrib["width"] == "1240"
    assert root.attrib["height"] == "1754"
    assert root.attrib["viewBox"] == "0 0 1240 1754"
    assert root.attrib["data-layout-key"] == "67:100:100:100:0"
    content = next(
        node for node in root if node.attrib.get("class") == "publication-content"
    )
    assert _scale(content) == pytest.approx(0.67)
    title = next(
        node for node in content.iter() if node.attrib.get("class") == "score-title"
    )
    assert float(title.attrib["data-font-size"]) == pytest.approx(26.8)
    note = next(
        node
        for node in content.iter()
        if "s1:i10" in node.attrib.get("data-source-ids", "")
    )
    note_bbox = _bbox(note)
    assert page.render_map_path is not None
    render_map = json.loads(page.render_map_path.read_text(encoding="utf-8"))
    render_map_bbox = render_map["anchors"][0]["bbox"]
    assert render_map_bbox["x"] <= note_bbox[0]
    assert render_map_bbox["y"] <= note_bbox[1]
    assert (
        render_map_bbox["x"] + render_map_bbox["width"]
        >= note_bbox[0] + note_bbox[2] - 1e-6
    )
    assert (
        render_map_bbox["y"] + render_map_bbox["height"]
        >= note_bbox[1] + note_bbox[3] - 1e-6
    )
    assert note_bbox[0] + note_bbox[2] <= 1240
    assert note_bbox[1] + note_bbox[3] <= 1754


def test_short_note_gap_changes_actual_centers_but_not_quarter_notes() -> None:
    short_score = parse_jianpu_score("1=C\n4/4\nq1 q2 q3 q4 q5 q6 q7 q1' |")
    wide_short, _ = _a4_svg_with_layout(short_score)
    compact_short, _ = _a4_svg_with_layout(short_score, short_note_gap_percent=20)

    wide_xs = _physical_note_xs(wide_short)
    compact_xs = _physical_note_xs(compact_short)
    assert compact_xs[-1] - compact_xs[0] < wide_xs[-1] - wide_xs[0]

    quarter_score = parse_jianpu_score("1=C\n4/4\n1 2 3 4 |")
    wide_quarter, _ = _a4_svg_with_layout(quarter_score)
    compact_quarter, _ = _a4_svg_with_layout(quarter_score, short_note_gap_percent=20)
    assert _physical_note_xs(compact_quarter) == pytest.approx(
        _physical_note_xs(wide_quarter)
    )


def test_expanded_short_note_gap_increases_common_eighth_note_span() -> None:
    score = parse_jianpu_score("1=C\n4/4\nq1 q2 q3 q4 q5 q6 q7 q1 |")

    spans: list[float] = []
    for percent in (100, 110, 120):
        root, _page = _a4_svg_with_layout(
            score,
            short_note_gap_percent=percent,
        )
        positions = _physical_note_xs(root)
        spans.append(positions[-1] - positions[0])

    assert spans[0] < spans[1] < spans[2]


def test_expanded_short_note_gap_stays_inside_measure_barlines() -> None:
    score = parse_jianpu_score("1=C\n4/4\nq1 q2 q3 q4 q5 q6 q7 q1 |")
    events = score.measures[0].events
    style = PublicationStyle(short_note_gap_scale=1.8)
    left, right = 20.0, 400.0

    positions = _event_positions(events, left, right, score.measures[0], style)
    first_extent = _event_visual_extents(events[0], style)
    last_extent = _event_visual_extents(events[-1], style)

    assert positions[0] + first_extent[0] >= left - 1e-6
    assert positions[-1] + last_extent[1] <= right + 1e-6


def test_short_note_control_preserves_noneligible_adjacent_gaps() -> None:
    score = parse_jianpu_score("1=C\n4/4\nq1 q2 3 4 |")
    events = score.measures[0].events

    def gaps(scale: float) -> list[float]:
        positions = _event_positions(
            events,
            20.0,
            800.0,
            score.measures[0],
            PublicationStyle(short_note_gap_scale=scale),
        )
        return [right - left for left, right in pairwise(positions)]

    compact = gaps(0.2)
    standard = gaps(1.0)
    expanded = gaps(1.8)

    assert compact[0] < standard[0] <= expanded[0]
    assert compact[1:] == pytest.approx(standard[1:])
    assert expanded[1:] == pytest.approx(standard[1:])


def _dense_sixteenth_measure(count: int = 16) -> tuple[list[Event], Measure]:
    events = [
        Event(
            kind="note",
            duration=Fraction(1, 4),
            start=Fraction(index, 4),
            pitches=[JianpuPitch(index % 7 + 1)],
        )
        for index in range(count)
    ]
    measure = Measure(
        "1",
        duration=Fraction(count, 4),
        events=events,
        beats_per_measure=count // 4,
        beat_type=4,
    )
    return events, measure


def test_lower_short_note_gap_tightens_dense_within_beat_gaps() -> None:
    # Regression lock: the control used to be applied only above 1.0 while the
    # rhythm line's side extent was double-counted as per-event ink, so 20% /
    # 50% / 90% produced byte-identical spacing in a dense bar.
    events, measure = _dense_sixteenth_measure()

    def within_beat_gap(percent: int) -> float:
        style = PublicationStyle(short_note_gap_scale=percent / 100.0)
        width = _intrinsic_measure_width(measure, style)
        centers = _event_positions(events, 20.0, width - 20.0, measure, style)
        gaps = [right - left for left, right in pairwise(centers)]
        return min(gaps)

    tight = within_beat_gap(20)
    middle = within_beat_gap(70)
    loose = within_beat_gap(100)

    assert tight < middle < loose


def test_lower_short_note_gap_fits_more_measures_per_line() -> None:
    bar = " ".join(f"s{index % 7 + 1}" for index in range(16))
    score = parse_jianpu_score("1=C\n4/4\n" + " | ".join([bar] * 12) + " |")

    def first_row_measures(percent: int) -> int:
        page = PublicationRenderService().build_scores_a4_svg_pages(
            [score], short_note_gap_percent=percent
        )[0]
        rows: dict[float, int] = {}
        for x_value, y_value in re.findall(
            r'<line class="measure" x1="([-\d.]+)" y1="([-\d.]+)"', page.svg
        ):
            del x_value
            key = round(float(y_value), 1)
            rows[key] = rows.get(key, 0) + 1
        # Each row draws one leading barline plus one per measure.
        return max(rows.values()) - 1

    assert first_row_measures(20) > first_row_measures(100)


def test_beat_gap_floor_survives_maximum_short_note_compaction() -> None:
    # The ratio pass alone collapses under compaction; beat_boundary_gap is the
    # absolute floor that keeps the beat division visible at the tightest
    # setting the short-note control allows.
    events, measure = _dense_sixteenth_measure()
    style = PublicationStyle(short_note_gap_scale=0.2)
    ratio = _boundary_within_ratio(events, measure, 100.0, 700.0, style, {3, 7, 11})
    centers = _event_positions(events, 100.0, 700.0, measure, style)
    gaps = [right - left for left, right in pairwise(centers)]
    boundary = [gaps[index] for index in (3, 7, 11)]
    within = [gap for index, gap in enumerate(gaps) if index not in {3, 7, 11}]

    assert ratio > 1.0 + style.beat_boundary_ratio
    mean_boundary = sum(boundary) / len(boundary)
    mean_within = sum(within) / len(within)
    assert mean_boundary - mean_within >= style.beat_boundary_gap * 0.9


def test_zero_beat_gap_leaves_only_the_ratio_channel() -> None:
    events, measure = _dense_sixteenth_measure()
    compacted = PublicationStyle(short_note_gap_scale=0.2, beat_boundary_gap=0.0)
    with_floor = PublicationStyle(short_note_gap_scale=0.2)
    without = _boundary_within_ratio(
        events, measure, 100.0, 700.0, compacted, {3, 7, 11}
    )
    with_ = _boundary_within_ratio(
        events, measure, 100.0, 700.0, with_floor, {3, 7, 11}
    )

    # Without the floor the compaction flattens the division back toward the
    # bare ratio, which is exactly what beat_gap_percent=0 restores.
    assert without < with_
    assert without < 1.0 + compacted.beat_boundary_ratio


def test_rhythm_line_is_not_clipped_in_a_dense_measure() -> None:
    bar = " ".join(f"s{index % 7 + 1}" for index in range(16))
    score = parse_jianpu_score("1=C\n4/4\n" + " | ".join([bar] * 12) + " |")
    page = PublicationRenderService().build_scores_a4_svg_pages(
        [score], short_note_gap_percent=20
    )[0]
    root = _root(page.svg)
    style = PublicationStyle()
    lines = [
        node for node in root.iter() if "duration-line" in node.attrib.get("class", "")
    ]
    assert lines
    # A clipped run would lose its side extent at the measure inner bound; every
    # run here must still carry the full extent on both ends.
    for line in lines:
        width = float(line.attrib["x2"]) - float(line.attrib["x1"])
        assert width >= 2 * style.rhythm_line_side_extent


def test_overfull_measure_ignores_the_short_note_control() -> None:
    # Documented fallback: _bounded_event_positions preserves the barline rather
    # than the requested gaps, so an overfull bar is scale-invariant.
    events, measure = _dense_sixteenth_measure(24)

    def centers(scale: float) -> list[float]:
        return _event_positions(
            events, 100.0, 400.0, measure, PublicationStyle(short_note_gap_scale=scale)
        )

    assert centers(0.2) == pytest.approx(centers(1.0))
    assert centers(1.8) == pytest.approx(centers(1.0))


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("content_scale_percent", 64),
        ("content_scale_percent", 101),
        ("system_gap_percent", 19),
        ("system_gap_percent", 181),
        ("short_note_gap_percent", 19),
        ("short_note_gap_percent", 181),
        ("beat_gap_percent", -1),
        ("beat_gap_percent", 201),
    ),
)
def test_a4_layout_options_reject_out_of_range_values(
    field: str,
    value: int,
) -> None:
    with pytest.raises(ValueError, match=field):
        A4LayoutOptions(**{field: value})


@pytest.mark.parametrize(
    "field",
    (
        "content_scale_percent",
        "system_gap_percent",
        "short_note_gap_percent",
        "beat_gap_percent",
    ),
)
def test_a4_layout_options_reject_non_integer_values(field: str) -> None:
    with pytest.raises(TypeError, match=field):
        A4LayoutOptions(**{field: "100"})


def test_expanded_mixed_short_notes_with_wide_ink_stay_inside_measure() -> None:
    events = [
        Event(
            kind="note",
            duration=Fraction(2),
            pitches=[JianpuPitch(1)],
            lyric="很宽的歌词",
            start=Fraction(0),
        ),
        Event(
            kind="note",
            duration=Fraction(1, 4),
            pitches=[JianpuPitch(2, accidental=Fraction(-1))],
            start=Fraction(2),
        ),
        Event(
            kind="note",
            duration=Fraction(1, 4),
            pitches=[JianpuPitch(3, accidental=Fraction(1))],
            start=Fraction(9, 4),
        ),
        Event(
            kind="note",
            duration=Fraction(2),
            pitches=[JianpuPitch(4)],
            lyric="另一段宽歌词",
            start=Fraction(5, 2),
        ),
        Event(
            kind="note",
            duration=Fraction(2),
            pitches=[JianpuPitch(5)],
            start=Fraction(9, 2),
        ),
    ]
    measure = Measure("1", duration=Fraction(13, 2), events=events)
    style = PublicationStyle(short_note_gap_scale=1.8)
    left, right = 20.0, 420.0

    positions = _event_positions(events, left, right, measure, style)

    for event, position in zip(events, positions, strict=True):
        extent = _event_visual_extents(event, style)
        assert position + extent[0] >= left - 1e-6
        assert position + extent[1] <= right + 1e-6


def test_system_gap_control_reduces_actual_distance_between_rows() -> None:
    score = parse_jianpu_score("1=C\n4/4\n1 2 3 4 | 5 6 7 1 |")
    score.measures[1].new_system = True

    standard, _ = _a4_svg_with_layout(score)
    compact, _ = _a4_svg_with_layout(score, system_gap_percent=20)

    def row_note_y(root: ET.Element) -> list[float]:
        content = next(
            node for node in root if node.attrib.get("class") == "publication-content"
        )
        scale = _scale(content)
        return sorted(
            {
                _translate(node)[1] * scale
                for node in content.iter()
                if node.attrib.get("class") == "note"
            }
        )

    standard_rows = row_note_y(standard)
    compact_rows = row_note_y(compact)
    assert len(standard_rows) == len(compact_rows) == 2
    assert compact_rows[1] - compact_rows[0] < standard_rows[1] - standard_rows[0]


def test_default_compact_layout_fits_more_music_on_each_a4_page() -> None:
    text = (
        "title=空间利用率\n1=C\n4/4\n"
        + " | ".join(["q1 q2 q3 q4 q5 q6 q7 q1" for _ in range(80)])
        + " |"
    )
    score = parse_jianpu_score(text)

    compact_pages = render_scores_a4_pages([score])
    standard_pages = render_scores_a4_pages(
        [score],
        layout=A4LayoutOptions(
            content_scale_percent=100,
            system_gap_percent=100,
            short_note_gap_percent=100,
        ),
    )

    assert len(compact_pages) == 1
    assert len(standard_pages) == 2


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
    triangle = next(
        node
        for node in root.iter()
        if node.tag.endswith("path")
        and "performance-mark-primitive" in node.attrib.get("class", "")
        and node.attrib.get("fill") == "#171717"
    )
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
        node
        for node in root.iter()
        if "performance-mark" in node.attrib.get("class", "").split()
        and "staccato" in node.attrib.get("class", "").split()
    )

    triangle = next(
        node
        for node in staccato.iter()
        if node.tag.endswith("path")
        and "performance-mark-primitive" in node.attrib.get("class", "")
    )
    assert "L" in triangle.attrib["d"]
    assert "cy" not in triangle.attrib
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


def test_measure_text_layout_uses_text_start_for_horizontal_position() -> None:
    measure = Measure(
        "1",
        duration=Fraction(4),
        events=[Event(kind="note", duration=Fraction(1), pitches=[JianpuPitch(1)])],
        text_blocks=[
            TextBlock("左", role="expression", start=Fraction(0)),
            TextBlock("右", role="expression", start=Fraction(3)),
        ],
    )
    root = _root(render_score_svg(JianpuScore(measures=[measure])))
    texts = {
        node.attrib["aria-label"]: _translate(node)[0]
        for node in root.iter()
        if node.attrib.get("class") == "annotation"
        and node.attrib.get("aria-label") in {"左", "右"}
    }

    assert texts["左"] < texts["右"]


def test_measure_text_layout_emits_truthful_bbox_for_custom_font_size() -> None:
    block = TextBlock("大字", role="expression", font_size=48)
    score = JianpuScore(
        measures=[
            Measure(
                "1",
                duration=Fraction(4),
                events=[
                    Event(kind="note", duration=Fraction(4), pitches=[JianpuPitch(1)])
                ],
                text_blocks=[block],
            )
        ]
    )
    root = _root(render_score_svg(score))
    text = next(node for node in root.iter() if node.attrib.get("aria-label") == "大字")

    assert len(text.attrib.get("data-bbox", "").split()) == 4
    _left, _top, _width, height = _bbox(text)
    assert height > 20


def test_tie_routes_below_note_while_slur_stays_above() -> None:
    first = Event(
        kind="note",
        duration=Fraction(1),
        pitches=[JianpuPitch(3)],
        tie_start=True,
        slur_start=True,
        start=Fraction(0),
    )
    second = Event(
        kind="note",
        duration=Fraction(1),
        pitches=[JianpuPitch(3)],
        tie_stop=True,
        slur_stop=True,
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
    slur = next(node for node in root.iter() if node.attrib.get("class") == "slur")
    note = next(node for node in root.iter() if node.attrib.get("class") == "note")
    _note_x, note_y = _translate(note)

    tie_ys = [float(v) for v in re.findall(r"[-\d.]+", tie.attrib["d"])][1::2]
    slur_ys = [float(v) for v in re.findall(r"[-\d.]+", slur.attrib["d"])][1::2]

    assert tie_ys and slur_ys
    assert min(tie_ys) > note_y
    assert max(slur_ys) < note_y


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


# ---------------------------------------------------------------------------
# Title resolution: jianpu text title= directive should win over default
# ---------------------------------------------------------------------------


def test_effective_title_uses_score_title_when_request_is_default() -> None:
    from score_trans.exec.render.actions import _effective_title

    score = JianpuScore(title="My Song")
    assert _effective_title("简谱", [score]) == "My Song"

    # Request explicitly set a non-default title — request wins
    assert _effective_title("Custom", [score]) == "Custom"

    # No scores — fall back to request title
    assert _effective_title("简谱", []) == "简谱"

    # None request title — score title wins
    assert _effective_title(None, [score]) == "My Song"


def test_batch_render_uses_jianpu_text_title_over_default(tmp_path: Path) -> None:
    """When jianpu text has title=My Song and req.title is '简谱', the SVG
    should contain 'My Song' and not '简谱'."""
    from score_trans.models.render.schemas import (
        BatchRenderPageRequest,
        BatchRenderRequest,
    )

    uploads = UploadService(ToolConfig(work_dir=tmp_path / "work"))
    actions = RenderActions(uploads=uploads)
    req = BatchRenderRequest(
        pages=[
            BatchRenderPageRequest(
                jianpu_text="title=My Song\n1=C\n4/4\n1 2 3 4 |",
            )
        ],
        title="简谱",
        jianpu_content_scale_percent=75,
        jianpu_system_gap_percent=88,
        jianpu_short_note_gap_percent=85,
    )
    response = actions.render_batch_a4(req)

    svg_path = uploads.get_path(response.svg_file_id)
    assert svg_path is not None
    root = ET.fromstring(svg_path.read_text(encoding="utf-8"))
    assert root.attrib["data-layout-key"] == "75:88:85:100:0"
    assert response.pages[0].layout_key == "75:88:85:100:0"
    text_content = " ".join(node.text or "" for node in root.iter() if node.text)
    assert "My Song" in text_content
    assert "简谱" not in text_content
