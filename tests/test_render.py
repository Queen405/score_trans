from fractions import Fraction
import xml.etree.ElementTree as ET

from score_trans.domain.jianpu import jianpu_to_musicxml
from score_trans.domain.musicxml import musicxml_to_score
from score_trans.exec.render.actions import RenderJianpuTextAction
from score_trans.models.score import JianpuEvent, JianpuMeasure, JianpuPitch, JianpuScore, TextBlock
from score_trans.services.ocr.provider import MockOCRProvider
from score_trans.services.render.rendering import RenderOptions, render_jianpu_svg, render_score_page_svg, render_score_svg


def _svg_root(svg: str) -> ET.Element:
    return ET.fromstring(svg)


def _svg_elements(root: ET.Element, tag: str) -> list[ET.Element]:
    return [element for element in root.iter() if element.tag.endswith(tag)]


def _simple_score(*events: JianpuEvent, text_blocks: list[TextBlock] | None = None) -> JianpuScore:
    score = JianpuScore(title="Rendered page", target_key="C", beats=4, beat_type=4, text_blocks=text_blocks or [])
    score.measures.append(
        JianpuMeasure(
            source_number="1",
            duration=Fraction(4, 1),
            events=list(events),
        )
    )
    return score


def test_render_jianpu_svg_contains_title_and_notes() -> None:
    svg = render_jianpu_svg("key=C\ntime=4/4\n1 2 | 3 4 |")

    assert "<svg" in svg
    assert "1=C" in svg
    assert ">1<" in svg


def test_render_score_svg_uses_display_measure_number() -> None:
    score = musicxml_to_score(jianpu_to_musicxml("key=C\ntime=4/4\n1 2 |"), start_measure_number=118)

    svg = render_score_svg(score)

    assert ">118<" in svg
    assert "generated" in svg


def test_render_score_page_svg_preserves_requested_page_size() -> None:
    score = _simple_score(
        JianpuEvent(kind="note", duration=Fraction(1, 1), pitches=[JianpuPitch(1)], start=Fraction(0, 1))
    )

    svg = render_score_page_svg(score, page_width=1240, page_height=1754)
    root = _svg_root(svg)

    assert root.attrib["width"] == "1240"
    assert root.attrib["height"] == "1754"
    assert root.attrib["viewBox"] == "0 0 1240 1754"


def test_render_jianpu_text_page_runs_ocr_and_preserves_bbox(tmp_path) -> None:
    text_path = tmp_path / "score.txt"
    image_path = tmp_path / "score.png"
    output_path = tmp_path / "score.svg"
    text_path.write_text("key=C\ntime=4/4\n1 2 |", encoding="utf-8")
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


def test_render_jianpu_text_page_uses_editable_text_directives(tmp_path) -> None:
    text_path = tmp_path / "score.txt"
    image_path = tmp_path / "score.png"
    output_path = tmp_path / "score.svg"
    text_path.write_text("key=C\ntime=4/4\n1 2 |\n\n@text 40 70 90 92 lyric 改后的歌词", encoding="utf-8")
    image_path.write_bytes(b"fake image")
    provider = MockOCRProvider([TextBlock("旧歌词", bbox=(40, 70, 90, 92), role="lyric")])

    RenderJianpuTextAction().execute_page(
        text_path,
        output_path,
        page_width=320,
        page_height=480,
        image_path=image_path,
        ocr_provider=provider,
    )

    svg = output_path.read_text(encoding="utf-8")
    assert "改后的歌词" in svg
    assert "旧歌词" not in svg


def test_render_jianpu_text_page_supports_chord_tokens(tmp_path) -> None:
    text_path = tmp_path / "score.txt"
    image_path = tmp_path / "score.png"
    output_path = tmp_path / "score.svg"
    text_path.write_text("key=C\ntime=4/4\n[3/+#2/] |", encoding="utf-8")
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


def test_render_score_page_svg_places_ocr_text_block_at_bbox() -> None:
    score = _simple_score(
        JianpuEvent(kind="note", duration=Fraction(1, 1), pitches=[JianpuPitch(1)], start=Fraction(0, 1)),
        text_blocks=[TextBlock("Allegro sempre", bbox=(120, 40, 280, 64), role="expression")],
    )

    svg = render_score_page_svg(score, page_width=600, page_height=800)
    root = _svg_root(svg)
    ocr_text = next(text for text in _svg_elements(root, "text") if text.text == "Allegro sempre")

    assert "Allegro sempre" in svg
    assert ocr_text.attrib["class"] == "ocr-overlay"
    assert float(ocr_text.attrib["x"]) == 120.0
    assert 40.0 < float(ocr_text.attrib["y"]) <= 64.0
    assert 8.0 <= float(ocr_text.attrib["font-size"]) <= 24.0


def test_render_score_page_svg_keeps_bboxless_ocr_text_visible() -> None:
    score = _simple_score(
        JianpuEvent(kind="note", duration=Fraction(1, 1), pitches=[JianpuPitch(1)], start=Fraction(0, 1)),
        text_blocks=[TextBlock("原谱标题", role="title")],
    )

    svg = render_score_page_svg(score, page_width=600, page_height=800)
    root = _svg_root(svg)
    ocr_text = next(text for text in _svg_elements(root, "text") if text.text == "原谱标题")

    assert "原谱标题" in svg
    assert ocr_text.attrib["class"] == "ocr-overlay"
    assert float(ocr_text.attrib["x"]) > 0
    assert float(ocr_text.attrib["y"]) > 0


def test_render_score_page_svg_uses_ocr_measure_number_without_overlay_duplicate() -> None:
    musicxml = jianpu_to_musicxml("key=C\ntime=4/4\n1 2 | 3 4 |")
    score = musicxml_to_score(musicxml)
    score.text_blocks.append(TextBlock("88", bbox=(12, 20, 28, 38), role="measure_number"))
    for index, measure in enumerate(score.measures):
        measure.display_number = 88 + index

    svg = render_score_page_svg(score, page_width=600, page_height=800)
    root = _svg_root(svg)
    texts = _svg_elements(root, "text")

    measure_numbers = [text.text for text in texts if text.attrib.get("class") == "measure-no"]
    positioned_numbers = [
        text for text in texts
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

    assert any(text.attrib.get("class") == "dynamic" and text.text == "f" for text in text_elements)
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

    assert '>f</text>' in svg
    assert 'poco rit.' in svg
    assert '>tr</text>' in svg
    assert '>2</text>' in svg
    assert 'class="articulation"' in svg


def test_musicxml_tremolo_renders_zhongruan_roll_mark_below_right() -> None:
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
    roll = next(text for text in _svg_elements(root, "text") if text.text == "轮")
    note = next(text for text in _svg_elements(root, "text") if text.attrib.get("class") == "note" and text.text == "2")

    assert roll.attrib["class"] == "technique-mark"
    assert float(roll.attrib["x"]) > float(note.attrib["x"])
    assert float(roll.attrib["y"]) > float(note.attrib["y"])
    assert "trem." not in svg


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

    assert '>#</text>' in svg
    assert '>♮</text>' in svg
    assert '>bb</text>' in svg
    assert '>#4</text>' not in svg
    assert '>n7</text>' not in svg


def test_render_text_uses_publication_marks() -> None:
    svg = render_jianpu_svg("key=D\ntime=4/4\n1/ 2. 3- 4~ | ~4 (5 6) |")

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
        "key=D\ntime=4/4\n1 2 3 4 |",
        RenderOptions(show_beat_guides=True, show_staff_guides=True),
    )

    assert '<line class="beat-guide"' in svg
    assert '<line class="staff-line"' in svg


def test_render_chord_orders_notes_from_high_to_low() -> None:
    svg = render_jianpu_svg("key=C\ntime=4/4\n[1+7'+3] |")

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
        "key=C\ntime=4/4\n0--- | 1// 2// 1// 2// 5// 6// 5// 6// 1// 2// 5// 6// 5// 6// 1'// 2'// |"
    )

    widths = []
    for line in svg.splitlines():
        if 'class="measure"' in line:
            widths.append(float(line.split('data-width="')[1].split('"')[0]))

    assert len(widths) == 2
    assert widths[1] > widths[0] * 1.8


def test_consecutive_eighth_notes_share_beam_lines() -> None:
    svg = render_jianpu_svg("key=C\ntime=4/4\n1/ 2/ 3/ 4/ |")

    assert svg.count('class="duration-line beam-line"') == 1
    assert '<line class="duration-line" x1=' not in svg


def test_consecutive_sixteenth_notes_share_two_beam_lines() -> None:
    svg = render_jianpu_svg("key=C\ntime=4/4\n1// 2// 3// 4// |")

    assert svg.count('class="duration-line beam-line"') == 2


def test_rests_inside_short_note_group_share_beam_lines() -> None:
    svg = render_jianpu_svg("key=C\ntime=4/4\n0/ 6/ 0/ 6/ |")

    assert svg.count('class="duration-line beam-line"') == 1
    assert '<line class="duration-line" x1=' not in svg


def test_quarter_notes_break_beam_groups() -> None:
    svg = render_jianpu_svg("key=C\ntime=4/4\n1/ 2/ 3 4/ |")

    assert svg.count('class="duration-line beam-line"') == 2


def test_accidentals_are_rendered_smaller_than_note_digits() -> None:
    svg = render_jianpu_svg("key=C\ntime=4/4\nb6 #4 |")

    assert '.accidental { font-size: 13px' in svg
    assert '<text class="accidental"' in svg
    assert '>b</text>' in svg
    assert '>#</text>' in svg
    assert '>b6</text>' not in svg
    assert '>#4</text>' not in svg


def test_text_tie_and_slur_arcs_stay_close_to_noteheads() -> None:
    svg = render_jianpu_svg("key=C\ntime=4/4\n1'~ (2' 3') |")

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
    beam_line = next(line for line in svg.splitlines() if 'class="duration-line beam-line"' in line)
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
                    pitches=[JianpuPitch(1, octave=1), JianpuPitch(5), JianpuPitch(1, octave=-1)],
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
    accent = next(path for path in _svg_elements(root, "path") if path.attrib.get("class") == "articulation")
    accent_y = float(accent.attrib["d"].split()[2])

    assert accent_y < min(note_ys) - 20


def test_generated_full_measure_rest_is_split_into_visible_beats() -> None:
    score = JianpuScore(title="Generated rest", target_key="C", beats=4, beat_type=4)
    score.measures.append(
        JianpuMeasure(
            source_number="1",
            duration=Fraction(4, 1),
            events=[JianpuEvent(kind="rest", duration=Fraction(4, 1), start=Fraction(0, 1), generated=True)],
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
            events=[JianpuEvent(kind="rest", duration=Fraction(4, 1), start=Fraction(0, 1))],
        )
    )

    svg = render_score_svg(score)

    assert svg.count(">0</text>") == 4
    assert 'class="extension-line"' not in svg


def test_low_octave_duration_line_sits_below_low_dot() -> None:
    svg = render_jianpu_svg("key=C\ntime=4/4\n5,/ |")

    dot_line = next(line for line in svg.splitlines() if 'class="octave-dot"' in line)
    beam_line = next(line for line in svg.splitlines() if 'class="duration-line beam-line"' in line)
    dot_y = float(dot_line.split('cy="')[1].split('"')[0])
    beam_y = float(beam_line.split('y1="')[1].split('"')[0])

    assert beam_y > dot_y + 8


def test_low_octave_dot_sits_close_to_notehead() -> None:
    svg = render_jianpu_svg("key=C\ntime=4/4\n1, |")

    note_line = next(line for line in svg.splitlines() if 'class="note"' in line and ">1<" in line)
    dot_line = next(line for line in svg.splitlines() if 'class="octave-dot"' in line)
    note_y = float(note_line.split('y="')[1].split('"')[0])
    dot_y = float(dot_line.split('cy="')[1].split('"')[0])

    assert 15 <= dot_y - note_y <= 20


def test_extension_line_sits_at_note_height_not_below_note() -> None:
    svg = render_jianpu_svg("key=C\ntime=4/4\n2--- |")

    note_line = next(line for line in svg.splitlines() if 'class="note"' in line)
    extension_line = next(line for line in svg.splitlines() if 'class="extension-line"' in line)
    note_y = float(note_line.split('y="')[1].split('"')[0])
    extension_y = float(extension_line.split('y1="')[1].split('"')[0])

    assert extension_y < note_y
