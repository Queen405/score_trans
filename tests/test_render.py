import json
from fractions import Fraction
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest
from fastapi import HTTPException

from score_trans.domain.jianpu import jianpu_to_musicxml, parse_jianpu_score
from score_trans.domain.musicxml import musicxml_to_score
from score_trans.domain.write.jianpu_text import scores_to_jianpu_document
from score_trans.domain.write.musicxml import scores_to_musicxml
from score_trans.exec.render.actions import (
    RenderActions,
    RenderJianpuTextAction,
    RenderMusicXmlJianpuAction,
)
from score_trans.models.provenance.schemas import (
    SourceTextAttachment,
    TextAnchor,
    TextPlacementAnchor,
)
from score_trans.models.render.schemas import (
    BatchRenderRequest,
    BatchRenderPageRequest,
    RenderJianpuTextSvgRequest,
)
from score_trans.models.score import (
    JianpuEvent,
    JianpuMeasure,
    JianpuPitch,
    JianpuScore,
    TextBlock,
)
from score_trans.models.settings.config import ToolConfig
from score_trans.services.files.upload_service import UploadService
from score_trans.services.ocr.providers import MockOCRProvider
from score_trans.services.render import RenderedA4FilePage
from score_trans.services.render import RenderOptions
from score_trans.services.render.main import (
    render_jianpu_a4_svgs,
    render_jianpu_svg,
    render_scores_a4_pages,
    render_scores_a4_svgs,
    render_score_page_svg,
    render_score_svg,
)
from score_trans.services.render.layout.measure import _score_measure_layout
from score_trans.services.render.layout.beat import _item_slots
from score_trans.services.render.layout.rows import _layout_rows
from score_trans.services.render.main import (
    A4_BOTTOM_MARGIN,
    A4_LINE_HEIGHT,
    A4_PAGE_HEIGHT,
    A4_ROW_BOTTOM_EXTENT,
    _a4_render_options,
    _a4_score_top,
    _paginate_rows,
)


def _part_score(name: str, degree: int, source_id: str) -> JianpuScore:
    event = JianpuEvent(
        kind="note",
        duration=Fraction(1, 1),
        pitches=[JianpuPitch(degree, source_id=source_id)],
        start=Fraction(0, 1),
        source_ids=[source_id],
        source_roles={"note": [source_id]},
    )
    return JianpuScore(
        part_name=name,
        part_count=2,
        measures=[
            JianpuMeasure(
                source_number="1",
                duration=Fraction(4, 1),
                events=[event],
            )
        ],
    )


def test_batch_render_multi_part_preserves_every_source_anchor(tmp_path) -> None:
    document = scores_to_jianpu_document(
        [
            _part_score("高音🎻", 1, "s1:i10"),
            _part_score("低音", 5, "s1:i20"),
        ]
    )
    actions = RenderActions(
        uploads=UploadService(ToolConfig(work_dir=tmp_path / "work"))
    )

    response = actions.render_batch_a4(
        BatchRenderRequest(
            pages=[
                BatchRenderPageRequest(
                    jianpu_text=document.text,
                    text_anchors=document.anchors,
                )
            ]
        )
    )

    svg_path = actions.uploads.get_path(response.pages[0].svg_file_id)
    assert svg_path is not None
    svg = svg_path.read_text(encoding="utf-8")
    assert "s1:i10" in svg
    assert "s1:i20" in svg
    assert svg.count("source-anchor") >= 2

    render_map_id = response.pages[0].render_map_file_id
    assert render_map_id
    render_map_path = actions.uploads.get_path(render_map_id)
    assert render_map_path is not None
    source_ids = {
        anchor["source_id"]
        for anchor in json.loads(render_map_path.read_text(encoding="utf-8"))["anchors"]
    }
    assert {"p0|s1:i10", "p0|s1:i20"} <= source_ids


def test_multi_part_text_preview_renders_parts_in_parallel(tmp_path) -> None:
    document = scores_to_jianpu_document(
        [
            _part_score("高音", 1, "s1:i10"),
            _part_score("低音", 5, "s1:i20"),
        ]
    )
    input_path = tmp_path / "score.txt"
    output_path = tmp_path / "score.svg"
    input_path.write_text(document.text, encoding="utf-8")

    pages = RenderJianpuTextAction().execute_a4_pages(
        input_path,
        output_path,
        text_anchors=document.anchors,
    )

    svg = pages[0].path.read_text(encoding="utf-8")
    assert ">高音</text>" in svg
    assert ">低音</text>" in svg
    assert "s1:i10" in svg
    assert "s1:i20" in svg


def test_multi_part_musicxml_preview_renders_every_part(tmp_path) -> None:
    input_path = tmp_path / "score.musicxml"
    output_path = tmp_path / "score.svg"
    input_path.write_text(
        scores_to_musicxml(
            [
                _part_score("高音", 1, "s1:i10"),
                _part_score("低音", 5, "s1:i20"),
            ],
            title="双声部",
        ),
        encoding="utf-8",
    )

    pages = RenderMusicXmlJianpuAction().execute_a4_pages(
        input_path,
        output_path,
    )

    svg = pages[0].path.read_text(encoding="utf-8")
    assert ">高音</text>" in svg
    assert ">低音</text>" in svg


def test_multi_part_render_rejects_unequal_measure_counts(tmp_path) -> None:
    text = (
        '// @part 1 name="高音"\n1=C\n4/4\n1 |\n2 |\n'
        '// @part 2 name="低音"\n1=C\n4/4\n5 |'
    )
    actions = RenderActions(
        uploads=UploadService(ToolConfig(work_dir=tmp_path / "work"))
    )

    with pytest.raises(HTTPException, match="各声部小节数量不一致") as exc_info:
        actions.render_batch_a4(
            BatchRenderRequest(pages=[BatchRenderPageRequest(jianpu_text=text)])
        )

    assert exc_info.value.status_code == 400


def test_render_package_exposes_narrow_interface() -> None:
    from score_trans.services import render

    assert set(render.__all__) == {
        "A4MeasureRange",
        "RenderedA4FilePage",
        "RenderedA4Page",
        "RenderOptions",
        "RenderService",
    }


def _svg_root(svg: str) -> ET.Element:
    return ET.fromstring(svg)


def _svg_elements(root: ET.Element, tag: str) -> list[ET.Element]:
    return [element for element in root.iter() if element.tag.endswith(tag)]


def _simple_score(
    *events: JianpuEvent, text_blocks: list[TextBlock] | None = None
) -> JianpuScore:
    score = JianpuScore(
        title="Rendered page",
        target_key="C",
        beats=4,
        beat_type=4,
        text_blocks=text_blocks or [],
    )
    score.measures.append(
        JianpuMeasure(
            source_number="1",
            duration=Fraction(4, 1),
            events=list(events),
        )
    )
    return score


def _many_measure_score(start: int, count: int) -> JianpuScore:
    score = JianpuScore(title="连续排版", target_key="C", beats=4, beat_type=4)
    for offset in range(count):
        number = start + offset
        measure = JianpuMeasure(
            source_number=str(number),
            display_measure_number=number,
            duration=Fraction(4, 1),
            events=[
                JianpuEvent(
                    kind="note",
                    duration=Fraction(1, 1),
                    pitches=[JianpuPitch(1)],
                    start=Fraction(0, 1),
                )
            ],
        )
        score.measures.append(measure)
    return score


def _a4_row_counts_for_repeated_measure(
    measure_body: str,
    *,
    count: int = 12,
) -> list[int]:
    options = _a4_render_options(None, title="简谱")
    text = f"1=C\n4/4\n{measure_body} |"

    def make_layout():
        score = parse_jianpu_score(text)
        return _score_measure_layout(score.measures[0], options)

    rows = _layout_rows([make_layout() for _ in range(count)], options)
    return [len(row) for row in rows]


def test_render_jianpu_svg_contains_title_and_notes() -> None:
    svg = render_jianpu_svg("1=C\n4/4\n1 2 | 3 4 |")

    assert "<svg" in svg
    assert "1=C" in svg
    assert ">1<" in svg


def test_render_jianpu_svg_marks_playback_note_indices() -> None:
    svg = render_jianpu_svg("1=C\n4/4\n1 [3+5] 0 q6 |")
    root = _svg_root(svg)
    groups = [
        group
        for group in _svg_elements(root, "g")
        if group.attrib.get("class") == "playback-note"
    ]

    assert [group.attrib["data-note-index"] for group in groups] == ["0", "1", "2"]
    assert groups[1].attrib["data-note-token"] == "[3+5]"
    assert "playback-note.playback-current" in svg


def test_render_new_syntax_repeat_marks_and_semantics() -> None:
    svg = render_jianpu_svg(
        "title=完整\n1=C\n4/4\n|: \\f ^> q[#3'+5] 1~ ~1 (s2 s3) :|\nL: 春 风 又 绿"
    )

    assert "完整" in svg
    assert 'stroke-width="3.0"' in svg
    assert ">f</text>" in svg
    assert 'class="articulation"' in svg
    assert ">#</text>" in svg
    assert 'class="tie"' in svg
    assert 'class="slur"' in svg
    assert 'class="duration-line beam-line"' in svg
    assert ">春</text>" in svg


def test_staccato_uses_triangle_distinct_from_high_octave_dot() -> None:
    svg = render_jianpu_svg("1=C\n4/4\n^. 1 2' |")
    root = _svg_root(svg)
    staccato_paths = [
        path
        for path in _svg_elements(root, "path")
        if path.attrib.get("class") == "staccato"
    ]
    octave_dots = [
        circle
        for circle in _svg_elements(root, "circle")
        if circle.attrib.get("class") == "octave-dot"
    ]

    assert len(staccato_paths) == 1
    assert staccato_paths[0].attrib["d"].endswith(" Z")
    assert len(octave_dots) == 1


def test_render_tuplet_group_shows_bracket_and_number() -> None:
    svg = render_jianpu_svg("1=C\n4/4\n$^.1 ^>2 3$ 4 5 6 |")

    assert 'class="tuplet-bracket"' in svg
    assert 'class="tuplet-number"' in svg
    assert 'class="articulation"' in svg
    assert 'class="staccato"' in svg
    assert ">3</text>" in svg


def test_tuplet_group_spacing_is_tighter_than_plain_same_beat_notes() -> None:
    options = RenderOptions(tuplet_gap_ratio=0.12, tuplet_slot_width_ratio=0.48)

    tuplet_gap = _first_note_center_gap("$666666$ 1 2 3", options)
    plain_gap = _first_note_center_gap("q1 q2 3 4", options)

    assert tuplet_gap < plain_gap * 0.5


def test_tuplet_marks_render_above_tuplet_number() -> None:
    svg = render_jianpu_svg("1=C\n4/4\n$^.1 ^>2 ^.3 ^>4 ^.5 ^>6$ 1 2 3 |")
    root = _svg_root(svg)
    tuplet_number = next(
        text
        for text in _svg_elements(root, "text")
        if text.attrib.get("class") == "tuplet-number"
    )
    articulation = next(
        path
        for path in _svg_elements(root, "path")
        if path.attrib.get("class") == "articulation"
    )
    mark_y = _path_first_m(articulation.attrib["d"])[1]
    number_y = float(tuplet_number.attrib["y"])

    assert number_y > mark_y
    assert number_y - mark_y < 28


def test_first_row_tuplet_marks_clear_score_meta() -> None:
    svg = render_jianpu_svg(
        "title=月亮之上\n1=C\n4/4\n$^>7 ^.6 ^.6 ^.6 ^.7 ^.6$ "
        "$^>7 ^.6 ^.6 ^.7 ^.6 ^.6$ |"
    )
    root = _svg_root(svg)
    meta = next(
        text
        for text in _svg_elements(root, "text")
        if text.attrib.get("class") == "meta"
    )
    articulation = next(
        path
        for path in _svg_elements(root, "path")
        if path.attrib.get("class") == "articulation"
    )

    assert _path_first_m(articulation.attrib["d"])[1] > float(meta.attrib["y"]) + 8


def test_render_measure_level_key_and_time_signature_markers() -> None:
    svg = render_jianpu_svg("1=C\n4/4\n1 2 3 4 |\n1=G\n3/4\n1 2 3 |")

    assert 'class="measure-attribute"' in svg
    assert "1=G" in svg
    assert "3/4" in svg


def test_render_score_svg_uses_display_measure_number() -> None:
    score = musicxml_to_score(
        jianpu_to_musicxml("1=C\n4/4\n1 2 |"), start_measure_number=118
    )

    svg = render_score_svg(score)

    assert ">118<" in svg
    assert "generated" in svg


def test_measure_number_stays_close_to_measure_top() -> None:
    svg = render_jianpu_svg("1=C\n4/4\n1' 2' 3' 4' |")
    root = _svg_root(svg)
    measure_no = next(
        text
        for text in _svg_elements(root, "text")
        if text.attrib.get("class") == "measure-no"
    )
    first_note = next(
        text
        for text in _svg_elements(root, "text")
        if text.attrib.get("class") == "note"
    )

    assert float(measure_no.attrib["y"]) > float(first_note.attrib["y"]) - 64


def test_render_can_hide_measure_numbers_when_requested() -> None:
    score = musicxml_to_score(
        jianpu_to_musicxml("1=C\n4/4\n1 2 |"), start_measure_number=118
    )

    svg = render_score_svg(score, RenderOptions(show_measure_numbers=False))

    assert 'class="measure-no"' not in svg
    assert "generated" in svg


def test_render_can_show_measure_numbers_only_at_row_start() -> None:
    svg = render_jianpu_svg(
        "1=C\n4/4\n1 2 | 3 4 | 5 6 |",
        RenderOptions(
            width=360,
            margin=20,
            min_measure_width=140,
            max_measure_width=140,
            measure_number_mode="row_start",
        ),
    )

    root = _svg_root(svg)
    measure_numbers = [
        text.text
        for text in _svg_elements(root, "text")
        if text.attrib.get("class") == "measure-no"
    ]

    assert measure_numbers == ["1", "3"]


def test_render_score_page_svg_preserves_requested_page_size() -> None:
    score = _simple_score(
        JianpuEvent(
            kind="note",
            duration=Fraction(1, 1),
            pitches=[JianpuPitch(1)],
            start=Fraction(0, 1),
        )
    )

    svg = render_score_page_svg(score, page_width=1240, page_height=1754)
    root = _svg_root(svg)

    assert root.attrib["width"] == "1240"
    assert root.attrib["height"] == "1754"
    assert root.attrib["viewBox"] == "0 0 1240 1754"


def test_render_scores_a4_svgs_continue_across_source_page_boundaries() -> None:
    first_source = _many_measure_score(1, 70)
    second_source = _many_measure_score(71, 8)
    third_source = _many_measure_score(79, 4)

    pages = render_scores_a4_svgs([first_source, second_source, third_source])

    assert len(pages) >= 2
    first_root = _svg_root(pages[0])
    second_root = _svg_root(pages[1])
    first_page_numbers = [
        element.attrib.get("data-number")
        for element in first_root.iter()
        if element.attrib.get("class") == "measure"
    ]
    second_page_numbers = [
        element.attrib.get("data-number")
        for element in second_root.iter()
        if element.attrib.get("class") == "measure"
    ]
    all_numbers = [*first_page_numbers, *second_page_numbers]

    assert "1" in first_page_numbers
    assert "70" in second_page_numbers
    assert "71" in second_page_numbers
    assert all_numbers[:78] == [str(number) for number in range(1, 79)]


def test_a4_layout_uses_increased_line_height() -> None:
    assert A4_LINE_HEIGHT == 160


def test_a4_compact_layout_hits_measure_capacity_targets() -> None:
    assert _a4_row_counts_for_repeated_measure("1 2 3 4")[0] == 4
    assert _a4_row_counts_for_repeated_measure("q1 q2 q3 q4 q5 q6 q7 q1'")[0] == 3
    assert (
        _a4_row_counts_for_repeated_measure(
            "s1 s2 s3 s4 s5 s6 s7 s1' s1 s2 s3 s4 s5 s6 s7 s1'"
        )[0]
        == 2
    )
    assert (
        _a4_row_counts_for_repeated_measure(
            "q[3+3] q[3+3] q[3+3] q[3+3] q[3+3] q[3+3] q[3+3] q[3+3]"
        )[0]
        == 3
    )


def test_a4_compact_layout_tightens_only_consecutive_short_note_spacing() -> None:
    options = _a4_render_options(None, title="简谱")

    sixteenth_gap = _first_note_center_gap("s1 s2 s3 s4", options)
    thirty_second_gap = _first_note_center_gap("d1 d2 d3 d4", options)
    eighth_gap = _first_note_center_gap("q1 q2 q3 q4", options)

    assert sixteenth_gap < options.note_font_size * 0.8
    assert thirty_second_gap < options.note_font_size * 0.8
    assert eighth_gap > options.note_font_size


def _first_note_center_gap(measure_body: str, options: RenderOptions) -> float:
    score = parse_jianpu_score(f"1=C\n4/4\n{measure_body} |")
    layout = _score_measure_layout(score.measures[0], options)
    slots = _item_slots(layout.beats[0].items, 0, layout.beats[0].width, options)
    return slots[1][1] - slots[0][1]


def test_a4_layout_paginates_ten_rows_per_page() -> None:
    options = _a4_render_options(None, title="简谱")
    score = parse_jianpu_score("1=C\n4/4\n1 2 3 4 |")
    layout = _score_measure_layout(score.measures[0], options)

    pages = _paginate_rows([[layout] for _ in range(25)], options)

    assert [len(page) for page in pages] == [10, 10, 5]


def test_a4_full_page_rows_reach_bottom_safe_area() -> None:
    options = _a4_render_options(None, title="简谱")
    score = parse_jianpu_score("1=C\n4/4\n1 2 3 4 |")
    layout = _score_measure_layout(score.measures[0], options)

    first_page = _paginate_rows([[layout] for _ in range(10)], options)[0]
    last_baseline = _a4_score_top(options) + (len(first_page) - 1) * options.line_height
    remaining = A4_PAGE_HEIGHT - A4_BOTTOM_MARGIN - last_baseline - A4_ROW_BOTTOM_EXTENT

    assert len(first_page) == 10
    assert 0 <= remaining < 8


def test_a4_compact_render_keeps_dense_symbols_legible() -> None:
    svg = render_jianpu_a4_svgs(
        "1=C\n4/4\nq5, q6, s1 s2 $345$ \\mf q[3+5] q[3+5] |\n1 2 3 4 5 |"
    )[0]
    root = _svg_root(svg)

    assert ".note { font-size: 26px" in svg
    assert ".measure-no { font-size: 20px" in svg
    assert 'class="tuplet-bracket"' in svg
    assert 'class="duration-line beam-line"' in svg
    assert ">mf</text>" in svg
    assert "小节超拍" in svg

    dot_ys = [
        float(circle.attrib["cy"])
        for circle in _svg_elements(root, "circle")
        if circle.attrib.get("class") == "octave-dot"
    ]
    beam_ys = [
        float(line.attrib["y1"])
        for line in _svg_elements(root, "line")
        if line.attrib.get("class") == "duration-line beam-line"
    ]
    assert dot_ys
    assert beam_ys
    assert max(beam_ys) > max(dot_ys) + 6


def test_render_scores_a4_pages_report_source_measure_ranges() -> None:
    first_source = _many_measure_score(1, 70)
    second_source = _many_measure_score(71, 8)

    pages = render_scores_a4_pages([first_source, second_source])

    assert len(pages) >= 2
    assert pages[0].measure_ranges[0].source_page_index == 0
    assert any(
        item.source_page_index == 1
        and item.start_measure_number <= 71 <= item.end_measure_number
        for item in pages[1].measure_ranges
        if item.start_measure_number is not None and item.end_measure_number is not None
    )


def test_render_batch_a4_assigns_source_ocr_to_first_overlapping_final_page(
    tmp_path,
) -> None:
    actions = RenderActions(
        uploads=UploadService(ToolConfig(work_dir=tmp_path / "work"))
    )
    combined = "1=C\n4/4\n" + ("1 2 3 4 |\n" * 78)
    first_source = "1=C\n4/4\n" + ("1 2 3 4 |\n" * 70)
    second_source = "1=C\n4/4\n" + ("5 6 7 1' |\n" * 8)

    response = actions.render_batch_a4(
        BatchRenderRequest(
            pages=[
                BatchRenderPageRequest(jianpu_text=combined, start_measure_number=1)
            ],
            source_pages=[
                BatchRenderPageRequest(
                    jianpu_text=first_source,
                    ocr_text=json.dumps(
                        [
                            {
                                "text": "第一页文字",
                                "bbox": [12, 30, 120, 54],
                                "role": "lyric",
                            },
                            {
                                "text": "88",
                                "bbox": [4, 6, 20, 24],
                                "role": "measure_number",
                            },
                        ],
                        ensure_ascii=False,
                    ),
                    start_measure_number=1,
                ),
                BatchRenderPageRequest(
                    jianpu_text=second_source,
                    ocr_text=json.dumps(
                        [
                            {
                                "text": "第二页文字",
                                "bbox": [14, 32, 128, 58],
                                "role": "expression",
                            }
                        ],
                        ensure_ascii=False,
                    ),
                ),
            ],
        )
    )

    assert len(response.pages) >= 2
    first_ocr = response.pages[0].ocr_text or ""
    second_ocr = response.pages[1].ocr_text or ""
    assert "第一页文字" in first_ocr
    assert "第二页文字" not in first_ocr
    assert "第二页文字" in second_ocr
    assert "88" not in first_ocr
    first_svg = actions.uploads.get_path(response.pages[0].svg_file_id).read_text(
        encoding="utf-8"
    )
    second_svg = actions.uploads.get_path(response.pages[1].svg_file_id).read_text(
        encoding="utf-8"
    )
    assert "第一页文字" in first_svg
    assert "第二页文字" in second_svg


def test_render_batch_a4_saved_page_ocr_overrides_source_suggestion(tmp_path) -> None:
    actions = RenderActions(
        uploads=UploadService(ToolConfig(work_dir=tmp_path / "work"))
    )
    text = "1=C\n4/4\n" + ("1 2 3 4 |\n" * 12)
    saved_ocr = json.dumps(
        [{"text": "保存后的文字", "bbox": [84, 120, 200, 148], "role": "lyric"}],
        ensure_ascii=False,
    )

    response = actions.render_batch_a4(
        BatchRenderRequest(
            pages=[BatchRenderPageRequest(jianpu_text=text, start_measure_number=1)],
            source_pages=[
                BatchRenderPageRequest(
                    jianpu_text=text,
                    ocr_text=json.dumps(
                        [
                            {
                                "text": "识别文字",
                                "bbox": [10, 20, 110, 44],
                                "role": "lyric",
                            }
                        ],
                        ensure_ascii=False,
                    ),
                    start_measure_number=1,
                )
            ],
            render_page_ocr_texts=[{"page_index": 0, "ocr_text": saved_ocr}],
        )
    )

    assert response.pages[0].ocr_text == saved_ocr
    svg = actions.uploads.get_path(response.pages[0].svg_file_id).read_text(
        encoding="utf-8"
    )
    assert "保存后的文字" in svg
    assert "识别文字" not in svg


def test_render_batch_a4_places_structured_text_by_semantic_anchor(tmp_path) -> None:
    actions = RenderActions(
        uploads=UploadService(ToolConfig(work_dir=tmp_path / "work"))
    )
    text = "1=C\n4/4\n" + ("1 2 3 4 |\n" * 90)
    measure_starts: list[int] = []
    cursor = 0
    while (cursor := text.find("1 2 3 4 |", cursor)) >= 0:
        measure_starts.append(cursor)
        cursor += 1
    attachments = [
        SourceTextAttachment(
            id="title",
            text="补充标题",
            role="title",
            anchor=TextPlacementAnchor(kind="score_start"),
        ),
        SourceTextAttachment(
            id="middle",
            text="中段提示",
            role="expression",
            anchor=TextPlacementAnchor(
                kind="source_element",
                source_id="s1:i50",
                relative_y=0.55,
            ),
        ),
        SourceTextAttachment(
            id="footer",
            text="页脚信息",
            role="footer",
            anchor=TextPlacementAnchor(kind="score_end"),
        ),
    ]

    response = actions.render_batch_a4(
        BatchRenderRequest(
            pages=[
                BatchRenderPageRequest(
                    jianpu_text=text,
                    start_measure_number=1,
                    text_attachments=attachments,
                    text_anchors=[
                        TextAnchor(
                            source_id="s1:i50",
                            start_utf16=measure_starts[49],
                            end_utf16=measure_starts[49] + 1,
                            role="note",
                        )
                    ],
                )
            ]
        )
    )

    assert len(response.pages) == 3
    assert [block.text for block in response.pages[0].text_blocks] == ["补充标题"]
    assert [block.text for block in response.pages[1].text_blocks] == ["中段提示"]
    assert [block.text for block in response.pages[2].text_blocks] == ["页脚信息"]
    assert "中段提示" in (
        actions.uploads.get_path(response.pages[1].svg_file_id).read_text(
            encoding="utf-8"
        )
    )


def test_render_jianpu_text_page_runs_ocr_and_preserves_bbox(tmp_path) -> None:
    text_path = tmp_path / "score.txt"
    image_path = tmp_path / "score.png"
    output_path = tmp_path / "score.svg"
    text_path.write_text("1=C\n4/4\n1 2 |", encoding="utf-8")
    image_path.write_bytes(b"fake image")
    provider = MockOCRProvider([TextBlock("歌词", bbox=(40, 70, 90, 92), role="lyric")])

    RenderJianpuTextAction().execute_page(
        text_path,
        output_path,
        page_width=320,
        page_height=480,
        image_path=image_path,
        ocr_provider=provider,
    )

    svg = output_path.read_text(encoding="utf-8")
    root = _svg_root(svg)
    ocr_text = next(text for text in _svg_elements(root, "text") if text.text == "歌词")
    assert provider.calls == [image_path]
    assert root.attrib["width"] == "320"
    assert root.attrib["height"] == "480"
    assert ocr_text.attrib["class"] == "ocr-overlay"
    assert float(ocr_text.attrib["x"]) == 40.0
    assert 70.0 < float(ocr_text.attrib["y"]) <= 92.0


def test_render_jianpu_text_page_ignores_legacy_text_directives(tmp_path) -> None:
    text_path = tmp_path / "score.txt"
    image_path = tmp_path / "score.png"
    output_path = tmp_path / "score.svg"
    text_path.write_text(
        "1=C\n4/4\n1 2 |\n\n@text 40 70 90 92 lyric 改后的歌词", encoding="utf-8"
    )
    image_path.write_bytes(b"fake image")
    provider = MockOCRProvider(
        [TextBlock("旧歌词", bbox=(40, 70, 90, 92), role="lyric")]
    )

    RenderJianpuTextAction().execute_page(
        text_path,
        output_path,
        page_width=320,
        page_height=480,
        image_path=image_path,
        ocr_provider=provider,
    )

    svg = output_path.read_text(encoding="utf-8")
    assert "旧歌词" in svg
    assert "改后的歌词" not in svg
    assert "@text" not in svg


def test_render_jianpu_text_page_supports_chord_tokens(tmp_path) -> None:
    text_path = tmp_path / "score.txt"
    image_path = tmp_path / "score.png"
    output_path = tmp_path / "score.svg"
    text_path.write_text("1=C\n4/4\nq[3+#2] |", encoding="utf-8")
    image_path.write_bytes(b"fake image")

    RenderJianpuTextAction().execute_page(
        text_path,
        output_path,
        page_width=320,
        page_height=480,
        image_path=image_path,
        ocr_provider=MockOCRProvider([]),
    )

    svg = output_path.read_text(encoding="utf-8")
    assert ">3<" in svg
    assert ">#</text>" in svg
    assert ">2<" in svg


def test_render_jianpu_text_page_rejects_ai_dotted_duration_prefix_variant(
    tmp_path,
) -> None:
    text_path = tmp_path / "score.txt"
    image_path = tmp_path / "score.png"
    output_path = tmp_path / "score.svg"
    text_path.write_text("1=C\n4/4\nh.4' 1 |", encoding="utf-8")
    image_path.write_bytes(b"fake image")

    with pytest.raises(ValueError, match="附点"):
        RenderJianpuTextAction().execute_page(
            text_path,
            output_path,
            page_width=320,
            page_height=480,
            image_path=image_path,
            ocr_provider=MockOCRProvider([]),
            start_measure_number=5,
        )


class RecordingTextRenderer:
    def __init__(self) -> None:
        self.input_text = ""
        self.show_measure_numbers = True

    def execute(
        self,
        input_path: str | Path,
        output_path: str | Path,
        *,
        title: str = "简谱",
        show_measure_numbers: bool = True,
        measure_number_mode: str = "all",
    ) -> Path:
        self.input_text = Path(input_path).read_text(encoding="utf-8")
        self.show_measure_numbers = show_measure_numbers
        Path(output_path).write_text("<svg></svg>", encoding="utf-8")
        return Path(output_path)

    def execute_a4_pages(
        self,
        input_path: str | Path,
        output_path: str | Path,
        *,
        title: str = "简谱",
        start_measure_number: int | None = None,
        show_measure_numbers: bool = True,
        measure_number_mode: str = "all",
    ) -> list[RenderedA4FilePage]:
        path = self.execute(
            input_path,
            output_path,
            title=title,
            show_measure_numbers=show_measure_numbers,
            measure_number_mode=measure_number_mode,
        )
        return [RenderedA4FilePage(path=path, measure_ranges=[])]


def test_render_jianpu_text_svg_preserves_editor_comments_in_response(tmp_path) -> None:
    renderer = RecordingTextRenderer()
    actions = RenderActions(
        uploads=UploadService(ToolConfig(work_dir=tmp_path / "work")),
        text_renderer=renderer,
    )
    text = "1=C\n4/4\n// 保留这个注释\n#5 6 7 1' | // 行尾注释"

    response = actions.render_jianpu_text_svg(
        RenderJianpuTextSvgRequest(jianpu_text=text, title="简谱")
    )

    assert response.jianpu_text == text
    assert "//" not in renderer.input_text
    assert "#5 6 7 1' |" in renderer.input_text
    assert actions.uploads.get_path(response.svg_file_id) is not None


def test_render_score_page_svg_places_ocr_text_block_at_bbox() -> None:
    score = _simple_score(
        JianpuEvent(
            kind="note",
            duration=Fraction(1, 1),
            pitches=[JianpuPitch(1)],
            start=Fraction(0, 1),
        ),
        text_blocks=[
            TextBlock("Allegro sempre", bbox=(120, 40, 280, 64), role="expression")
        ],
    )

    svg = render_score_page_svg(score, page_width=600, page_height=800)
    root = _svg_root(svg)
    ocr_text = next(
        text for text in _svg_elements(root, "text") if text.text == "Allegro sempre"
    )

    assert "Allegro sempre" in svg
    assert ocr_text.attrib["class"] == "ocr-overlay"
    assert float(ocr_text.attrib["x"]) == 120.0
    assert 40.0 < float(ocr_text.attrib["y"]) <= 64.0
    assert 8.0 <= float(ocr_text.attrib["font-size"]) <= 24.0


def test_render_score_page_svg_keeps_bboxless_ocr_text_visible() -> None:
    score = _simple_score(
        JianpuEvent(
            kind="note",
            duration=Fraction(1, 1),
            pitches=[JianpuPitch(1)],
            start=Fraction(0, 1),
        ),
        text_blocks=[TextBlock("原谱标题", role="title")],
    )

    svg = render_score_page_svg(score, page_width=600, page_height=800)
    root = _svg_root(svg)
    ocr_text = next(
        text for text in _svg_elements(root, "text") if text.text == "原谱标题"
    )

    assert "原谱标题" in svg
    assert ocr_text.attrib["class"] == "ocr-overlay"
    assert float(ocr_text.attrib["x"]) > 0
    assert float(ocr_text.attrib["y"]) > 0


def test_render_score_page_svg_uses_ocr_measure_number_without_overlay_duplicate() -> (
    None
):
    musicxml = jianpu_to_musicxml("1=C\n4/4\n1 2 | 3 4 |")
    score = musicxml_to_score(musicxml)
    score.text_blocks.append(
        TextBlock("88", bbox=(12, 20, 28, 38), role="measure_number")
    )
    for index, measure in enumerate(score.measures):
        measure.display_number = 88 + index

    svg = render_score_page_svg(score, page_width=600, page_height=800)
    root = _svg_root(svg)
    texts = _svg_elements(root, "text")

    measure_numbers = [
        text.text for text in texts if text.attrib.get("class") == "measure-no"
    ]
    positioned_numbers = [
        text
        for text in texts
        if text.text == "88" and text.attrib.get("class") in {"ocr-overlay", "dynamic"}
    ]
    assert measure_numbers[:2] == ["88", "89"]
    assert positioned_numbers == []


def test_render_score_page_svg_renders_dynamic_and_fermata() -> None:
    score = _simple_score(
        JianpuEvent(
            kind="note",
            duration=Fraction(1, 1),
            pitches=[JianpuPitch(5)],
            dynamic="f",
            articulation="fermata",
            start=Fraction(0, 1),
        )
    )

    svg = render_score_page_svg(score, page_width=600, page_height=800)
    root = _svg_root(svg)
    text_elements = _svg_elements(root, "text")
    path_elements = _svg_elements(root, "path")

    assert any(
        text.attrib.get("class") == "dynamic" and text.text == "f"
        for text in text_elements
    )
    assert any(path.attrib.get("class") == "articulation" for path in path_elements)


def test_musicxml_direction_marks_attach_to_note_and_positioned_words() -> None:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="3.1">
  <part-list><score-part id="P1"><part-name>Part</part-name></score-part></part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>1</divisions>
        <key><fifths>0</fifths></key>
        <time><beats>4</beats><beat-type>4</beat-type></time>
      </attributes>
      <direction placement="above"><direction-type><words>poco rit.</words></direction-type></direction>
      <direction placement="below"><direction-type><dynamics><f/></dynamics></direction-type></direction>
      <note>
        <pitch><step>C</step><octave>4</octave></pitch>
        <duration>1</duration>
        <notations>
          <articulations><staccato/><accent/></articulations>
          <ornaments><trill-mark/></ornaments>
          <technical><fingering>2</fingering></technical>
        </notations>
      </note>
    </measure>
  </part>
</score-partwise>"""

    score = musicxml_to_score(xml)
    svg = render_score_svg(score)

    assert ">f</text>" in svg
    assert "poco rit." in svg
    assert ">tr</text>" in svg
    assert ">2</text>" in svg
    assert 'class="articulation"' in svg


def _path_first_m(path_d: str) -> tuple[float, float]:
    import re

    m = re.search(r"M\s+([\d.]+)\s+([\d.]+)", path_d)
    if m:
        return float(m.group(1)), float(m.group(2))
    return 0.0, 0.0


def test_musicxml_tremolo_renders_ruan_roll_mark_below_right() -> None:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="3.1">
  <part-list><score-part id="P1"><part-name>中阮</part-name></score-part></part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>1</divisions>
        <key><fifths>0</fifths></key>
        <time><beats>4</beats><beat-type>4</beat-type></time>
      </attributes>
      <note>
        <pitch><step>D</step><octave>4</octave></pitch>
        <duration>2</duration>
        <notations>
          <ornaments><tremolo type="single">3</tremolo></ornaments>
        </notations>
      </note>
    </measure>
  </part>
</score-partwise>"""

    score = musicxml_to_score(xml)
    svg = render_score_svg(score)
    root = _svg_root(svg)
    assert score.instrument_profile == "ruan"
    roll = next(
        el
        for el in _svg_elements(root, "path")
        if el.attrib.get("class") == "technique-mark"
    )
    note = next(
        text
        for text in _svg_elements(root, "text")
        if text.attrib.get("class") == "note" and text.text == "2"
    )

    roll_x, roll_y = _path_first_m(roll.attrib["d"])
    assert roll_x > float(note.attrib["x"])
    assert roll_y > float(note.attrib["y"])
    assert "trem." not in svg


def test_jianpu_text_roll_mark_renders_below_right() -> None:
    from score_trans.domain.parse.jianpu_text import parse_jianpu_score

    text = "1=C\n4/4\n^l 1 2 3 4 |"
    score = parse_jianpu_score(text)
    svg = render_score_svg(score)
    root = _svg_root(svg)

    roll = next(
        el
        for el in _svg_elements(root, "path")
        if el.attrib.get("class") == "technique-mark"
    )
    note = next(
        text
        for text in _svg_elements(root, "text")
        if text.attrib.get("class") == "note" and text.text == "1"
    )

    roll_x, roll_y = _path_first_m(roll.attrib["d"])
    assert roll_x > float(note.attrib["x"])
    assert roll_y > float(note.attrib["y"])
    assert "轮" not in svg


def test_jianpu_text_roll_mark_roundtrip() -> None:
    from score_trans.domain.parse.jianpu_text import parse_jianpu_score
    from score_trans.domain.write.jianpu_text import score_to_jianpu_text

    text = "1=C\n4/4\n^l 1 2 3 4 |"
    score = parse_jianpu_score(text)
    out = score_to_jianpu_text(score)

    assert "^l" in out
    assert 'class="lyric"' not in out
    score2 = parse_jianpu_score(out)
    assert score2.measures[0].events[0].ornaments == ["tremolo"]
    assert score2.measures[0].events[0].articulations == []


def test_musicxml_explicit_accidentals_render_as_separate_symbols() -> None:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="3.1">
  <part-list><score-part id="P1"><part-name>Part</part-name></score-part></part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>1</divisions>
        <key><fifths>0</fifths></key>
        <time><beats>4</beats><beat-type>4</beat-type></time>
      </attributes>
      <note>
        <pitch><step>F</step><alter>1</alter><octave>4</octave></pitch>
        <duration>1</duration>
        <accidental>sharp</accidental>
      </note>
      <note>
        <pitch><step>B</step><octave>4</octave></pitch>
        <duration>1</duration>
        <accidental>natural</accidental>
      </note>
      <note>
        <pitch><step>B</step><alter>-2</alter><octave>4</octave></pitch>
        <duration>1</duration>
        <accidental>double-flat</accidental>
      </note>
    </measure>
  </part>
</score-partwise>"""

    score = musicxml_to_score(xml)
    svg = render_score_svg(score)

    assert ">#</text>" in svg
    assert ">♮</text>" in svg
    assert ">bb</text>" in svg
    assert ">#4</text>" not in svg
    assert ">n7</text>" not in svg


def test_render_text_uses_publication_marks() -> None:
    svg = render_jianpu_svg("1=D\n4/4\nq1 2. 3- 4~ | ~4 (5 6) |")

    assert "duration-line" in svg
    assert "rhythm-dot" in svg
    assert "extension-line" in svg
    assert 'class="tie"' in svg
    assert 'class="slur"' in svg
    assert '<line class="beat-guide"' not in svg
    assert 'class="measure-no"' in svg
    assert 'data-number="1"' in svg
    assert 'data-number="2"' in svg


def test_render_can_show_editing_guides_when_requested() -> None:
    svg = render_jianpu_svg(
        "1=D\n4/4\n1 2 3 4 |",
        RenderOptions(show_beat_guides=True, show_staff_guides=True),
    )

    assert '<line class="beat-guide"' in svg
    assert '<line class="staff-line"' in svg


def test_render_chord_orders_notes_from_high_to_low() -> None:
    svg = render_jianpu_svg("1=C\n4/4\n[1+7'+3] |")

    note_lines = [line for line in svg.splitlines() if 'class="note"' in line]

    assert [line.split(">")[1].split("<")[0] for line in note_lines] == ["7", "3", "1"]
    assert "duration duration-line" not in svg


def test_render_structured_ast_score() -> None:
    score = JianpuScore(title="AST Score", target_key="G", beats=3, beat_type=4)
    score.measures.append(
        JianpuMeasure(
            source_number="A",
            display_measure_number=12,
            duration=Fraction(3, 1),
            events=[
                JianpuEvent(
                    kind="note",
                    duration=Fraction(1, 2),
                    pitches=[JianpuPitch(5, octave=1), JianpuPitch(1)],
                    dotted=1,
                    tie_start=True,
                    slur_start=True,
                    lyric="la",
                ),
                JianpuEvent(kind="rest", duration=Fraction(1, 1)),
            ],
        )
    )

    svg = render_jianpu_svg(score)

    assert "AST Score" in svg
    assert "1=G" in svg
    assert "3/4" in svg
    assert ">12</text>" in svg
    assert ">5<" in svg
    assert ">1<" in svg
    assert ">0<" in svg
    assert "duration-line" in svg
    assert "rhythm-dot" in svg
    assert 'class="tie"' in svg
    assert 'class="slur"' in svg
    assert ">la</text>" in svg


def test_dense_measure_gets_more_width_than_empty_measure() -> None:
    svg = render_jianpu_svg(
        "1=C\n4/4\n0--- | s1 s2 s1 s2 s5 s6 s5 s6 s1 s2 s5 s6 s5 s6 s1' s2' |"
    )

    widths = []
    for line in svg.splitlines():
        if 'class="measure"' in line:
            widths.append(float(line.split('data-width="')[1].split('"')[0]))

    assert len(widths) == 2
    assert widths[1] > widths[0] * 1.8


def test_consecutive_eighth_notes_share_beam_lines() -> None:
    svg = render_jianpu_svg("1=C\n4/4\nq1 q2 q3 q4 |")

    assert svg.count('class="duration-line beam-line"') == 1
    assert '<line class="duration-line" x1=' not in svg


def test_consecutive_sixteenth_notes_share_two_beam_lines() -> None:
    svg = render_jianpu_svg("1=C\n4/4\ns1 s2 s3 s4 |")

    assert svg.count('class="duration-line beam-line"') == 2


def test_low_octave_eighth_beam_stays_separated_from_sixteenth_beam() -> None:
    svg = render_jianpu_svg("1=C\n4/4\nq3, s2 s3 4 5 6 |")
    root = _svg_root(svg)
    beam_ys = [
        float(line.attrib["y1"])
        for line in _svg_elements(root, "line")
        if line.attrib.get("class") == "duration-line beam-line"
    ]

    assert len(beam_ys) == 2
    assert beam_ys[1] >= beam_ys[0] + 5.5


def test_rests_inside_short_note_group_share_beam_lines() -> None:
    svg = render_jianpu_svg("1=C\n4/4\nq0 q6 q0 q6 |")

    assert svg.count('class="duration-line beam-line"') == 1
    assert '<line class="duration-line" x1=' not in svg


def test_quarter_notes_break_beam_groups() -> None:
    svg = render_jianpu_svg("1=C\n4/4\nq1 q2 3 q4 |")

    assert svg.count('class="duration-line beam-line"') == 2


def test_accidentals_are_rendered_smaller_than_note_digits() -> None:
    svg = render_jianpu_svg("1=C\n4/4\nb6 #4 |")

    assert ".accidental { font-size: 18px" in svg
    assert '<text class="accidental"' in svg
    assert ">b</text>" in svg
    assert ">#</text>" in svg
    assert ">b6</text>" not in svg
    assert ">#4</text>" not in svg


def test_text_tie_and_slur_arcs_stay_close_to_noteheads() -> None:
    svg = render_jianpu_svg("1=C\n4/4\n1'~ (2' 3') |")

    assert 'class="tie"' in svg
    assert 'class="slur"' in svg
    assert "-22" not in svg


def test_score_slur_is_paired_between_events() -> None:
    score = JianpuScore(title="Slur", target_key="C", beats=4, beat_type=4)
    score.measures.append(
        JianpuMeasure(
            source_number="1",
            duration=Fraction(4, 1),
            events=[
                JianpuEvent(
                    kind="note",
                    duration=Fraction(1, 1),
                    pitches=[JianpuPitch(1, octave=1)],
                    slur_start=True,
                    start=Fraction(0, 1),
                ),
                JianpuEvent(
                    kind="note",
                    duration=Fraction(1, 1),
                    pitches=[JianpuPitch(2, octave=1)],
                    slur_stop=True,
                    start=Fraction(1, 1),
                ),
            ],
        )
    )

    svg = render_score_svg(score)

    assert svg.count('class="slur"') == 1


def test_chord_tie_sits_below_duration_lines() -> None:
    score = JianpuScore(title="Tie", target_key="C", beats=4, beat_type=4)
    score.measures.append(
        JianpuMeasure(
            source_number="1",
            duration=Fraction(4, 1),
            events=[
                JianpuEvent(
                    kind="note",
                    duration=Fraction(1, 2),
                    pitches=[JianpuPitch(6, accidental=-1), JianpuPitch(6)],
                    tie_start=True,
                    start=Fraction(0, 1),
                ),
            ],
        )
    )

    svg = render_score_svg(score)

    tie_line = next(line for line in svg.splitlines() if 'class="tie"' in line)
    beam_line = next(
        line for line in svg.splitlines() if 'class="duration-line beam-line"' in line
    )
    tie_y = float(tie_line.split("M ")[1].split(" ")[1])
    beam_y = float(beam_line.split('y1="')[1].split('"')[0])
    assert tie_y > beam_y + 4


def test_chord_accent_sits_above_highest_note() -> None:
    score = JianpuScore(title="Accent", target_key="C", beats=4, beat_type=4)
    score.measures.append(
        JianpuMeasure(
            source_number="1",
            duration=Fraction(4, 1),
            events=[
                JianpuEvent(
                    kind="note",
                    duration=Fraction(1, 1),
                    pitches=[
                        JianpuPitch(1, octave=1),
                        JianpuPitch(5),
                        JianpuPitch(1, octave=-1),
                    ],
                    articulations=["accent"],
                    start=Fraction(0, 1),
                ),
            ],
        )
    )

    svg = render_score_svg(score)
    root = _svg_root(svg)
    note_ys = [
        float(text.attrib["y"])
        for text in _svg_elements(root, "text")
        if text.attrib.get("class") == "note"
    ]
    accent = next(
        path
        for path in _svg_elements(root, "path")
        if path.attrib.get("class") == "articulation"
    )
    accent_y = float(accent.attrib["d"].split()[2])

    assert accent_y < min(note_ys) - 20


def test_generated_full_measure_rest_is_split_into_visible_beats() -> None:
    score = JianpuScore(title="Generated rest", target_key="C", beats=4, beat_type=4)
    score.measures.append(
        JianpuMeasure(
            source_number="1",
            duration=Fraction(4, 1),
            events=[
                JianpuEvent(
                    kind="rest",
                    duration=Fraction(4, 1),
                    start=Fraction(0, 1),
                    generated=True,
                )
            ],
        )
    )

    svg = render_score_svg(score)

    assert svg.count(">0</text>") == 4
    assert 'class="extension-line"' not in svg


def test_musicxml_full_measure_rest_is_split_into_visible_beats() -> None:
    score = JianpuScore(title="Rest", target_key="C", beats=4, beat_type=4)
    score.measures.append(
        JianpuMeasure(
            source_number="1",
            duration=Fraction(4, 1),
            events=[
                JianpuEvent(kind="rest", duration=Fraction(4, 1), start=Fraction(0, 1))
            ],
        )
    )

    svg = render_score_svg(score)

    assert svg.count(">0</text>") == 4
    assert 'class="extension-line"' not in svg


def test_low_octave_duration_line_sits_below_low_dot() -> None:
    svg = render_jianpu_svg("1=C\n4/4\nq5, |")

    dot_line = next(line for line in svg.splitlines() if 'class="octave-dot"' in line)
    beam_line = next(
        line for line in svg.splitlines() if 'class="duration-line beam-line"' in line
    )
    dot_y = float(dot_line.split('cy="')[1].split('"')[0])
    beam_y = float(beam_line.split('y1="')[1].split('"')[0])

    assert beam_y > dot_y + 8


def test_low_octave_dot_sits_close_to_notehead() -> None:
    svg = render_jianpu_svg("1=C\n4/4\n1, |")

    note_line = next(
        line for line in svg.splitlines() if 'class="note"' in line and ">1<" in line
    )
    dot_line = next(line for line in svg.splitlines() if 'class="octave-dot"' in line)
    note_y = float(note_line.split('y="')[1].split('"')[0])
    dot_y = float(dot_line.split('cy="')[1].split('"')[0])

    assert 4 <= dot_y - note_y <= 10


def test_extension_line_sits_at_note_height_not_below_note() -> None:
    svg = render_jianpu_svg("1=C\n4/4\n2--- |")

    note_line = next(line for line in svg.splitlines() if 'class="note"' in line)
    extension_line = next(
        line for line in svg.splitlines() if 'class="extension-line"' in line
    )
    note_y = float(note_line.split('y="')[1].split('"')[0])
    extension_y = float(extension_line.split('y1="')[1].split('"')[0])

    assert extension_y < note_y


def test_erhu_performance_marks_render_once_with_canonical_ids() -> None:
    text = (
        "instrument=erhu\n1=C\n4/4\n"
        "^lg ^tg ^pg ^1 ^zr ^rg ^bx ^sh ^xh ^dh ^ds ^dx "
        "^hx ^hs ^sc ^xc ^kx ^nx ^wx ^jx ^gx 1 2 3 4 |"
    )
    root = _svg_root(render_jianpu_svg(text))
    groups = [
        element
        for element in _svg_elements(root, "g")
        if element.attrib.get("class") == "performance-mark"
    ]
    mark_ids = [element.attrib.get("data-mark") for element in groups]

    assert len(mark_ids) == len(set(mark_ids))
    assert {
        "down-bow",
        "up-bow",
        "throw-bow",
        "fingering-1",
        "natural-harmonic",
        "artificial-harmonic",
        "pluck",
        "scoop",
        "plop",
        "finger-pad-slide",
        "doit",
        "falloff",
        "lower-return-slide",
        "upper-return-slide",
        "upper-trill",
        "lower-trill",
        "open-string",
        "inner-string",
        "outer-string",
        "breath-mark",
        "hook-string",
    } == set(mark_ids)


def test_continuous_slide_renders_dangling_segments_across_rows() -> None:
    from score_trans.services.render.options import RenderOptions

    text = "instrument=erhu\n1=C\n4/4\n1 2 3 4 |\n^lh 5 6 7 1 |"
    svg = render_jianpu_svg(
        text,
        RenderOptions(width=360, min_measure_width=250, max_measure_width=250),
    )
    root = _svg_root(svg)
    slides = [
        path
        for path in _svg_elements(root, "path")
        if path.attrib.get("class") == "slide"
    ]

    assert len(slides) == 2
    assert all(slide.attrib.get("data-mark") == "continuous-slide" for slide in slides)


def test_guzheng_performance_marks_render_with_canonical_ids() -> None:
    text = (Path(__file__).parent / "fixtures" / "guzheng_marks.jianpu").read_text(
        encoding="utf-8"
    )
    root = _svg_root(render_jianpu_svg(text))
    groups = [
        element
        for element in _svg_elements(root, "g")
        if element.attrib.get("class") == "performance-mark"
    ]
    mark_ids = [element.attrib.get("data-mark") for element in groups]

    assert len(mark_ids) == len(set(mark_ids))
    assert {
        "tremolo",
        "guzheng-sweep-tremolo",
        "string-sweep",
        "natural-harmonic",
        "guzheng-board-front-flower",
        "guzheng-on-beat-flower",
        "guzheng-ascending-scrape",
        "guzheng-descending-scrape",
        "guzheng-vibrato",
        "scoop",
        "plop",
        "guzheng-ornament-up-slide",
        "guzheng-ornament-down-slide",
        "guzheng-double-tuo",
        "guzheng-double-mo",
        "arpeggio",
    } == set(mark_ids)


def test_ruan_performance_marks_reuse_shared_renderers() -> None:
    root = _svg_root(
        render_jianpu_svg(
            "instrument=ruan\n1=C\n4/4\n^l ^sx ^zr ^zy 1 ^py [1+3+5] 2 3 |"
        )
    )
    mark_ids = {
        element.attrib.get("data-mark")
        for element in _svg_elements(root, "g")
        if element.attrib.get("class") == "performance-mark"
    }

    assert {
        "tremolo",
        "string-sweep",
        "natural-harmonic",
        "ornament-note",
        "arpeggio",
    } <= mark_ids


def test_guzheng_directional_slides_keep_direction_across_rows() -> None:
    from score_trans.services.render.options import RenderOptions

    text = "instrument=guzheng\n1=C\n4/4\n3 2 1 5 |\n^lh 6 5 ^lh 3 1 |"
    svg = render_jianpu_svg(
        text,
        RenderOptions(width=360, min_measure_width=250, max_measure_width=250),
    )
    root = _svg_root(svg)
    slides = [
        path
        for path in _svg_elements(root, "path")
        if path.attrib.get("class") == "slide"
    ]

    assert [slide.attrib.get("data-direction") for slide in slides] == [
        "up",
        "up",
        "down",
    ]


def test_unregistered_musicxml_marks_keep_text_fallback() -> None:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="4.0">
  <part-list><score-part id="P1"><part-name>Music</part-name></score-part></part-list>
  <part id="P1"><measure number="1">
    <attributes><divisions>1</divisions><time><beats>4</beats><beat-type>4</beat-type></time></attributes>
    <note>
      <pitch><step>C</step><octave>4</octave></pitch><duration>4</duration>
      <notations>
        <ornaments><turn/></ornaments>
        <technical><thumb-position/></technical>
      </notations>
    </note>
  </measure></part>
</score-partwise>"""

    score = musicxml_to_score(xml)
    svg = render_score_svg(score)

    assert score.measures[0].events[0].ornaments == ["turn"]
    assert score.measures[0].events[0].technical == ["thumb-position"]
    assert ">turn</text>" in svg
    assert ">thumb</text>" in svg
