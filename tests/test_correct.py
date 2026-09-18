from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

import pytest
from score_trans.domain.jianpu import jianpu_to_musicxml, musicxml_to_jianpu
from score_trans.models.correct.schemas import ConversionOptionsDTO, CorrectionRequest
from score_trans.models.provenance.schemas import (
    BoundingBox,
    MusicXmlLocator,
    SourceElement,
    SourceMap,
    SourceMapSheet,
    SourceTextAttachment,
    TextPlacementAnchor,
)
from score_trans.models.score import JianpuScore
from score_trans.services.correct.clef_transform import transform_pitch
from score_trans.services.correct.correction_service import (
    CorrectionService,
    _document_title,
)
from score_trans.services.correct.entity_service import (
    CorrectableEntity,
    extract_entities,
)
from score_trans.services.correct.musicxml_patch import apply_deletions


def _entity(
    source_id: str,
    tag: str,
    locator: str,
    *,
    inter_id: str = "1",
) -> CorrectableEntity:
    return CorrectableEntity(
        source_id=source_id,
        inter_id=inter_id,
        sheet_index=1,
        tag=tag,
        shape=tag.upper(),
        grade=0.9,
        bounds=(10, 20, 30, 40),
        is_structural=tag in {"clef", "time-whole", "time-custom", "key"},
        musicxml_attribute="id",
        musicxml_locator=locator,
        hit_path="M10 20h30v40z",
    )


def _pitch(note: ET.Element) -> tuple[str, int]:
    pitch = note.find("pitch")
    assert pitch is not None
    return pitch.findtext("step", ""), int(pitch.findtext("octave", "0"))


def test_apply_deletions_targets_exact_structural_elements() -> None:
    xml = """<score-partwise><part id="P1">
      <measure number="1"><attributes>
        <clef id="clef-first"><sign>G</sign><line>2</line></clef>
        <time id="time-first"><beats>4</beats><beat-type>4</beat-type></time>
      </attributes><note id="note-before"><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration></note></measure>
      <measure number="2"><attributes>
        <clef id="clef-target"><sign>F</sign><line>4</line></clef>
        <time id="time-target"><beats>3</beats><beat-type>4</beat-type></time>
      </attributes><note id="note-after"><pitch><step>G</step><octave>2</octave></pitch><duration>1</duration></note></measure>
      <measure number="3"><attributes><clef id="clef-stop"><sign>G</sign><line>2</line></clef></attributes>
        <note id="note-stop"><pitch><step>D</step><octave>3</octave></pitch><duration>1</duration></note></measure>
    </part></score-partwise>"""
    entities = {
        "clef": _entity("clef", "clef", "clef-target"),
        "time": _entity("time", "time-whole", "time-target"),
    }

    corrected = ET.fromstring(apply_deletions(xml, ["clef", "time"], entities))

    assert [element.get("id") for element in corrected.iter("clef")] == [
        "clef-first",
        "clef-stop",
    ]
    assert [element.get("id") for element in corrected.iter("time")] == ["time-first"]
    notes = {note.get("id"): note for note in corrected.iter("note")}
    assert _pitch(notes["note-before"]) == ("C", 4)
    assert _pitch(notes["note-after"]) == ("E", 4)
    assert _pitch(notes["note-stop"]) == ("D", 3)


def test_correction_request_accepts_empty_deleted_source_ids() -> None:
    """B 方案：允许提交空删除列表（语义=不删除任何标记，用于恢复全部）。"""
    request = CorrectionRequest(
        original_musicxml="<score-partwise/>",
        omr_file_id="omr",
        source_map_file_id="map",
        deleted_source_ids=[],
    )
    assert request.deleted_source_ids == []


def test_apply_deletions_empty_list_preserves_every_element() -> None:
    """空删除列表不得改动任何音符或结构元素（语义等价，非字符串相等）。"""
    xml = """<score-partwise><part id="P1">
      <measure number="1"><attributes>
        <clef id="clef-first"><sign>G</sign><line>2</line></clef>
        <time id="time-first"><beats>4</beats><beat-type>4</beat-type></time>
      </attributes><note id="note-before"><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration></note></measure>
    </part></score-partwise>"""
    entities: dict[str, CorrectableEntity] = {}

    original = ET.fromstring(xml)
    corrected = ET.fromstring(apply_deletions(xml, [], entities))

    assert len(list(corrected.iter("note"))) == len(list(original.iter("note")))
    assert len(list(corrected.iter("clef"))) == len(list(original.iter("clef")))
    assert len(list(corrected.iter("time"))) == len(list(original.iter("time")))
    notes = {note.get("id"): note for note in corrected.iter("note")}
    assert _pitch(notes["note-before"]) == ("C", 4)


def test_deleted_note_head_is_hidden_from_jianpu() -> None:
    """删除有音高音符后：MusicXML 用休止符占拍保节奏，但简谱文本不显示 0。"""
    xml = """<score-partwise><part id="P1"><measure number="1">
      <note id="note-target"><pitch><step>C</step><octave>4</octave></pitch><duration>2</duration><voice>1</voice><type>half</type></note>
      <note id="note-other"><pitch><step>G</step><octave>4</octave></pitch><duration>2</duration><voice>1</voice><type>half</type></note>
    </measure></part></score-partwise>"""
    entity = _entity("head", "head", "note-target")

    working = apply_deletions(xml, ["head"], {"head": entity})
    text = musicxml_to_jianpu(working)

    assert "0" not in text
    assert "5" in text


def test_clef_transform_accounts_for_octave_change() -> None:
    assert transform_pitch("C", 0.0, 4, "G", 2, "G", 2, -1, 0) == ("C", 0.0, 5)


def test_delete_note_head_preserves_rhythm_as_rest() -> None:
    xml = """<score-partwise><part id="P1"><measure number="1">
      <note id="note-target"><pitch><step>C</step><alter>-1</alter><octave>4</octave></pitch>
        <duration>2</duration><voice>1</voice><type>half</type><accidental>flat</accidental></note>
    </measure></part></score-partwise>"""
    entity = _entity("head", "head", "note-target")

    corrected = ET.fromstring(apply_deletions(xml, ["head"], {"head": entity}))

    note = corrected.find("./part/measure/note")
    assert note is not None
    assert note.find("rest") is not None
    assert note.find("pitch") is None
    assert note.findtext("duration") == "2"
    assert note.findtext("type") == "half"
    # 删除产生的休止符打上 print-object="no"，解析时置 hidden，简谱/SVG 跳过
    assert note.get("print-object") == "no"


def test_apply_deletions_rejects_unknown_or_ambiguous_locator() -> None:
    xml = '<score-partwise><part id="P1"><measure><attributes><key id="same"/></attributes></measure><measure><attributes><key id="same"/></attributes></measure></part></score-partwise>'
    with pytest.raises(ValueError, match="无法定位"):
        apply_deletions(xml, ["missing"], {})
    entity = _entity("key", "key", "same")
    with pytest.raises(ValueError, match="不唯一"):
        apply_deletions(xml, ["key"], {"key": entity})


def test_apply_deletions_skips_phantom_reference_instead_of_aborting() -> None:
    """Audiveris 的 score-link-map 偶尔引用 MusicXML 未导出的 id（结构元素尤甚）。
    定位到 0 个元素时跳过该标记（无可删除对象），其余删除照常应用，不中断整批。"""
    xml = """<score-partwise><part id="P1"><measure number="1">
      <attributes><key id="key-real"><fifths>-2</fifths></key></attributes>
      <note id="note-real"><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration></note>
    </measure></part></score-partwise>"""
    phantom = _entity("phantom", "key", "key-s1-i4997")
    real_head = _entity("head", "head", "note-real")

    corrected = ET.fromstring(
        apply_deletions(
            xml, ["phantom", "head"], {"phantom": phantom, "head": real_head}
        )
    )

    # 幻影调号被跳过：原 key 仍在
    assert len(list(corrected.iter("key"))) == 1
    # 真实音符被删除并改为休止符
    note = corrected.find(".//note")
    assert note is not None
    assert note.find("rest") is not None
    assert note.find("pitch") is None
    assert note.get("print-object") == "no"


def test_apply_deletions_skips_phantom_note_reference() -> None:
    """音符级幻影引用同样跳过：定位到 0 个元素时不报错、不改动 MusicXML。"""
    xml = """<score-partwise><part id="P1"><measure number="1">
      <note id="note-real"><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration></note>
    </measure></part></score-partwise>"""
    phantom_head = _entity("head", "head", "note-missing")

    corrected = ET.fromstring(apply_deletions(xml, ["head"], {"head": phantom_head}))

    note = corrected.find(".//note")
    assert note is not None
    assert note.find("pitch") is not None


def test_extract_entities_uses_sheet_scoped_source_map_and_omr_dimensions(
    tmp_path: Path,
) -> None:
    omr = tmp_path / "score.omr"
    sheet_xml = """<sheet><picture width="1000" height="1400"/><inters>
      <clef id="10" shape="F_CLEF"><bounds x="10" y="20" w="30" h="40"/></clef>
      <stem id="11" shape="STEM"><bounds x="50" y="60" w="4" h="80"/></stem>
    </inters></sheet>"""
    with ZipFile(omr, "w") as archive:
        archive.writestr("book/sheet#1/sheet#1.xml", sheet_xml)
    source_map = SourceMap(
        sheets=[
            SourceMapSheet(
                sheet_index=1,
                width=1000,
                height=1400,
                overlay_file="overlay.png",
                elements=[
                    SourceElement(
                        source_id="clef0-s1-i10",
                        inter_id=10,
                        shape="F_CLEF",
                        grade=0.9,
                        bounds=BoundingBox(x=10, y=20, width=30, height=40),
                        hit_path="M10 20h30v40z",
                        musicxml_locator=MusicXmlLocator(contains="clef-target"),
                    ),
                    SourceElement(
                        source_id="stem0-s1-i11",
                        inter_id=11,
                        shape="STEM",
                        grade=0.9,
                        bounds=BoundingBox(x=50, y=60, width=4, height=80),
                        hit_path="M50 60h4v80z",
                        musicxml_locator=MusicXmlLocator(contains="note-target"),
                    ),
                ],
            )
        ]
    )

    sheets = extract_entities(omr, source_map)

    assert len(sheets) == 1
    assert (sheets[0].width, sheets[0].height) == (1000, 1400)
    assert [entity.source_id for entity in sheets[0].entities] == ["clef0-s1-i10"]


def test_correction_request_preserves_text_attachments_and_title() -> None:
    title = SourceTextAttachment(
        id="title-1",
        text="月亮之上",
        role="title",
        anchor=TextPlacementAnchor(kind="score_start"),
    )
    request = CorrectionRequest(
        original_musicxml="<score-partwise/>",
        omr_file_id="omr",
        source_map_file_id="map",
        deleted_source_ids=["source-1"],
        text_attachments=[title],
    )

    assert request.text_attachments == [title]
    assert (
        _document_title(
            ConversionOptionsDTO(),
            request.text_attachments,
            [JianpuScore(title="旧标题")],
        )
        == "月亮之上"
    )


def test_correction_forwards_a4_layout_controls(tmp_path: Path) -> None:
    class CapturingRenderer:
        def __init__(self) -> None:
            self.kwargs: dict[str, object] = {}

        def render_scores_a4_svg_page_results(self, _scores, output_path, **kwargs):
            self.kwargs = dict(kwargs)
            output_path.write_text("<svg/>", encoding="utf-8")
            return [type("RenderedPage", (), {"path": output_path})()]

    renderer = CapturingRenderer()
    service = CorrectionService(render_service=renderer)
    options = ConversionOptionsDTO(
        jianpu_content_scale_percent=75,
        jianpu_system_gap_percent=88,
        jianpu_short_note_gap_percent=85,
        jianpu_beat_gap_percent=140,
        jianpu_break_beams_at_beat=True,
    )

    service.correct(
        jianpu_to_musicxml("1=C\n4/4\n1 2 |"),
        [],
        {},
        options,
        tmp_path,
    )

    assert renderer.kwargs["content_scale_percent"] == 75
    assert renderer.kwargs["system_gap_percent"] == 88
    assert renderer.kwargs["short_note_gap_percent"] == 85
    assert renderer.kwargs["beat_gap_percent"] == 140
    assert renderer.kwargs["break_beams_at_beat"] is True


def test_clef_key_time_locator_matches_injected_ids() -> None:
    """方案 A：Audiveris 注入的 id 能被 _matching_elements 子串匹配命中"""
    xml = """<score-partwise><part id="P1">
      <measure number="1"><attributes>
        <clef id="c-s1-i236"><sign>F</sign><line>4</line></clef>
        <key id="k-s1-i105"><fifths>2</fifths></key>
        <time id="t-s1-i87"><beats>4</beats><beat-type>4</beat-type></time>
      </attributes>
      <note id="st__n-s1-i50"><pitch><step>G</step><octave>2</octave></pitch><duration>1</duration></note>
      </measure>
    </part></score-partwise>"""
    entities = {
        "clef": _entity("clef", "clef", "c-s1-i236"),
        "key": _entity("key", "key", "k-s1-i105"),
        "time": _entity("time", "time-whole", "t-s1-i87"),
    }

    corrected = ET.fromstring(apply_deletions(xml, ["clef", "key", "time"], entities))

    assert not list(corrected.iter("clef"))
    assert not list(corrected.iter("key"))
    assert not list(corrected.iter("time"))
    note = next(corrected.iter("note"))
    assert note.find("pitch/step").text == "E"
    assert note.find("pitch/octave").text == "4"


def test_extract_entities_includes_structural_when_in_source_map(
    tmp_path: Path,
) -> None:
    """方案 A：source-link-map 含结构标记时，extract_entities 能合并返回"""
    omr = tmp_path / "score.omr"
    sheet_xml = """<sheet><picture width="1000" height="1400"/><inters>
      <clef id="236" shape="F_CLEF"><bounds x="10" y="20" w="30" h="40"/></clef>
      <key id="105" shape="KEY_SHARP_2"><bounds x="50" y="20" w="20" h="40"/></key>
      <time-whole id="87" shape="TIME_FOUR_FOUR"><bounds x="80" y="20" w="25" h="40"/></time-whole>
    </inters></sheet>"""
    with ZipFile(omr, "w") as archive:
        archive.writestr("book/sheet#1/sheet#1.xml", sheet_xml)
    source_map = SourceMap(
        sheets=[
            SourceMapSheet(
                sheet_index=1,
                width=1000,
                height=1400,
                overlay_file="overlay.png",
                elements=[
                    SourceElement(
                        source_id="s1:i236",
                        inter_id=236,
                        shape="F_CLEF",
                        grade=0.9,
                        bounds=BoundingBox(x=10, y=20, width=30, height=40),
                        hit_path="M10 20h30v40z",
                        musicxml_locator=MusicXmlLocator(contains="c-s1-i236"),
                    ),
                    SourceElement(
                        source_id="s1:i105",
                        inter_id=105,
                        shape="KEY_SHARP_2",
                        grade=0.9,
                        bounds=BoundingBox(x=50, y=20, width=20, height=40),
                        hit_path="M50 20h20v40z",
                        musicxml_locator=MusicXmlLocator(contains="k-s1-i105"),
                    ),
                    SourceElement(
                        source_id="s1:i87",
                        inter_id=87,
                        shape="TIME_FOUR_FOUR",
                        grade=0.9,
                        bounds=BoundingBox(x=80, y=20, width=25, height=40),
                        hit_path="M80 20h25v40z",
                        musicxml_locator=MusicXmlLocator(contains="t-s1-i87"),
                    ),
                ],
            )
        ]
    )

    sheets = extract_entities(omr, source_map)

    assert len(sheets) == 1
    tags = sorted(entity.tag for entity in sheets[0].entities)
    assert tags == ["clef", "key", "time-whole"]
