from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import replace
from pathlib import Path
from zipfile import ZipFile

import pytest
from score_trans.domain.jianpu import jianpu_to_musicxml, musicxml_to_jianpu
from score_trans.models.correct.schemas import ConversionOptionsDTO, CorrectionRequest
from score_trans.models.provenance.schemas import (
    BoundingBox,
    MusicXmlLocator,
    SourceElement,
    SourceGlyph,
    SourceMap,
    SourceMapSheet,
    SourceMeasureLocator,
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
    CANDIDATE_TAGS,
    CorrectableEntity,
    CorrectableGlyph,
    DELETABLE_TAGS,
    _candidates_for_family,
    _rank_candidates,
    extract_entities,
    load_source_map,
)
from score_trans.services.correct.musicxml_patch import (
    apply_candidate_selections,
    apply_deletions,
)


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


def _candidate_entity(
    source_id: str,
    tag: str,
    locator: str,
    shape: str,
    alternative: str,
) -> CorrectableEntity:
    return replace(
        _entity(source_id, tag, locator),
        shape=shape,
        candidates=(
            (shape, 0.8, "audiveris_shape_classifier"),
            (alternative, 0.7, "audiveris_shape_classifier"),
        ),
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


def test_apply_deletions_removes_notation_marks_without_deleting_notes_or_siblings() -> (
    None
):
    xml = """<score-partwise><part><measure>
      <note id="st__dot__slur__ts-s1-i42__art__orn__fermata__bow__finger__arpeggio">
        <pitch><step>C</step><octave>4</octave></pitch><duration>6</duration><type>quarter</type><dot/>
        <tie type="start"/><notations><tied type="start"/><slur type="start"/>
          <articulations><staccato/><accent/></articulations>
          <ornaments><trill-mark/></ornaments><fermata/><arpeggiate/>
          <technical><up-bow/><fingering>1</fingering></technical></notations>
      </note>
      <direction id="st__direction-dynamic"><direction-type><dynamics><f/></dynamics><words>dolce</words></direction-type></direction>
      <direction id="st__direction-wedge"><direction-type><wedge type="crescendo"/></direction-type><sound dynamics="70"/></direction>
    </measure></part></score-partwise>"""
    specs = {
        "dot": ("augmentation-dot", "dot", "AUGMENTATION_DOT"),
        "slur": ("slur", "slur", "SLUR_ABOVE"),
        "tie": ("slur", "t-s1-i42", "SLUR"),
        "art": ("articulation", "art", "STACCATO"),
        "orn": ("ornament", "orn", "TR"),
        "fermata": ("fermata", "fermata", "FERMATA"),
        "bow": ("bow", "bow", "BOW_UP"),
        "finger": ("fingering", "finger", "DIGIT_1"),
        "arpeggio": ("arpeggiato", "arpeggio", "ARPEGGIATO"),
        "direction-dynamic": ("dynamics", "direction-dynamic", "DYNAMICS_F"),
        "direction-wedge": ("wedge", "direction-wedge", "CRESCENDO"),
    }
    entities = {
        key: replace(_entity(key, tag, locator), shape=shape)
        for key, (tag, locator, shape) in specs.items()
    }

    corrected = ET.fromstring(apply_deletions(xml, list(entities), entities))

    note = corrected.find(".//note")
    assert note is not None and note.find("pitch") is not None
    assert note.find("dot") is None
    assert note.find("tie") is None
    assert note.find("notations/tied") is None
    assert note.find("notations/slur") is None
    assert note.find("notations/articulations/staccato") is None
    assert note.find("notations/articulations/accent") is not None
    assert note.find("notations/ornaments/trill-mark") is None
    assert note.find("notations/fermata") is None
    assert note.find("notations/arpeggiate") is None
    assert note.find("notations/technical/up-bow") is None
    assert note.find("notations/technical/fingering") is None
    dynamic_direction = corrected.find(".//direction[@id='st__direction-dynamic']")
    assert dynamic_direction is not None
    assert dynamic_direction.find(".//dynamics") is None
    assert dynamic_direction.find(".//words").text == "dolce"
    wedge_direction = corrected.find(".//direction[@id='st__direction-wedge']")
    assert wedge_direction is not None
    assert wedge_direction.find(".//wedge") is None
    assert wedge_direction.find("sound") is None


def test_deleted_augmentation_dot_is_removed_from_jianpu_and_duration() -> None:
    xml = """<score-partwise><part><measure>
      <attributes><divisions>2</divisions></attributes>
      <note id="st__n-s1-i1__ad-s1-i2"><pitch><step>C</step><octave>4</octave></pitch>
        <duration>3</duration><type>quarter</type><dot/></note>
    </measure></part></score-partwise>"""
    entity = replace(
        _entity("dot", "augmentation-dot", "ad-s1-i2"),
        shape="AUGMENTATION_DOT",
    )

    corrected = apply_deletions(xml, ["dot"], {"dot": entity})

    assert "<dot" not in corrected
    assert "<duration>2</duration>" in corrected
    assert "." not in musicxml_to_jianpu(corrected).splitlines()[-1]


def test_deleted_slur_dynamic_and_articulation_disappear_from_jianpu() -> None:
    xml = """<score-partwise><part><measure>
      <attributes><divisions>1</divisions></attributes>
      <direction id="st__dy-s1-i1"><direction-type><dynamics><f/></dynamics></direction-type></direction>
      <note id="st__n-s1-i2__ss-s1-i4__ar-s1-i5"><pitch><step>C</step><octave>4</octave></pitch>
        <duration>1</duration><type>quarter</type><notations><slur type="start"/><articulations><staccato/></articulations></notations></note>
      <note id="st__n-s1-i3__se-s1-i4"><pitch><step>D</step><octave>4</octave></pitch>
        <duration>1</duration><type>quarter</type><notations><slur type="stop"/></notations></note>
    </measure></part></score-partwise>"""
    entities = {
        "slur": replace(_entity("slur", "slur", "s-s1-i4"), shape="SLUR_ABOVE"),
        "dynamic": replace(
            _entity("dynamic", "dynamic", "dy-s1-i1"), shape="DYNAMICS_F"
        ),
        "articulation": replace(
            _entity("articulation", "articulation", "ar-s1-i5"),
            shape="STACCATO",
        ),
    }

    corrected = apply_deletions(xml, list(entities), entities)
    text = musicxml_to_jianpu(corrected).splitlines()[-1]

    assert "\\f" not in text
    assert "^." not in text
    assert "(" not in text and ")" not in text


@pytest.mark.parametrize("dynamic", ["p", "pp", "mp", "mf", "f", "ff", "sfz"])
def test_delete_unidentified_musicxml_dynamic_linked_through_note_id(
    dynamic: str,
) -> None:
    # Audiveris exports dynamics without a direction id and stores their source
    # id in the associated note's provenance id instead.
    xml = f"""<score-partwise><part><measure>
      <attributes><divisions>1</divisions></attributes>
      <direction><direction-type><dynamics><{dynamic}/></dynamics></direction-type></direction>
      <note id="st__n-s1-i1__dy-s1-i9"><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration><type>quarter</type></note>
    </measure></part></score-partwise>"""
    entity = replace(
        _entity("dynamic", "dynamic", "dy-s1-i9"),
        shape=f"DYNAMICS_{dynamic.upper()}",
    )

    corrected = apply_deletions(xml, ["dynamic"], {"dynamic": entity})
    text = musicxml_to_jianpu(corrected)

    assert f"\\{dynamic}" not in text
    assert "<dynamics" not in corrected


def test_deleted_tuplet_removes_timing_modification_from_jianpu() -> None:
    xml = """<score-partwise><part><measure>
      <attributes><divisions>3</divisions></attributes>
      <note id="st__n-s1-i1__tu-s1-i9"><pitch><step>C</step><octave>4</octave></pitch><duration>2</duration><type>eighth</type>
        <time-modification><actual-notes>3</actual-notes><normal-notes>2</normal-notes></time-modification>
        <notations><tuplet type="start"/></notations></note>
      <note id="st__n-s1-i2__tu-s1-i9"><pitch><step>D</step><octave>4</octave></pitch><duration>2</duration><type>eighth</type>
        <time-modification><actual-notes>3</actual-notes><normal-notes>2</normal-notes></time-modification>
        <notations><tuplet type="stop"/></notations></note>
    </measure></part></score-partwise>"""
    entity = replace(_entity("tuplet", "tuplet", "tu-s1-i9"), shape="TUPLET_THREE")

    corrected = apply_deletions(xml, ["tuplet"], {"tuplet": entity})

    assert "<time-modification>" not in corrected
    assert "<tuplet" not in corrected


def test_correction_request_accepts_empty_deleted_source_ids() -> None:
    """B 方案：允许提交空删除列表（语义=不删除任何标记，用于恢复全部）。"""
    request = CorrectionRequest(
        original_musicxml="<score-partwise/>",
        omr_file_id="omr",
        source_map_file_id="map",
        deleted_source_ids=[],
    )
    assert request.deleted_source_ids == []


def test_every_exposed_correctable_entity_is_left_click_deletable() -> None:
    assert CANDIDATE_TAGS <= DELETABLE_TAGS


def test_candidate_ranking_normalizes_audiveris_inter_grades() -> None:
    ranked = _rank_candidates(
        (
            ("CLASSIFIER", 0.98, "audiveris_shape_classifier"),
            ("MANUAL", 3.0, "audiveris_inter_grade"),
            ("ALGORITHMIC", 2.0, "audiveris_inter_grade"),
            ("LOW", 0.42, "audiveris_notehead_template"),
        )
    )

    assert ranked == (
        ("MANUAL", 1.0, "audiveris_inter_grade"),
        ("ALGORITHMIC", 0.99, "audiveris_inter_grade"),
        ("CLASSIFIER", 0.98, "audiveris_shape_classifier"),
        ("LOW", 0.42, "audiveris_notehead_template"),
    )


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


def test_candidate_selection_updates_musicxml_notehead_style() -> None:
    entity = _entity("head", "head", "note-1")
    entity = replace(
        entity,
        shape="NOTEHEAD_BLACK",
        candidates=(
            ("NOTEHEAD_BLACK", 0.8, "audiveris_shape_classifier"),
            ("NOTEHEAD_CROSS", 0.2, "audiveris_shape_classifier"),
        ),
    )
    xml = '<score-partwise><part><measure><note id="note-1"><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration></note></measure></part></score-partwise>'

    corrected = ET.fromstring(
        apply_candidate_selections(xml, {"head": "NOTEHEAD_CROSS"}, {"head": entity})
    )

    assert corrected.findtext(".//note/notehead") == "x"
    assert corrected.findtext(".//note/duration") == "1"


def test_candidate_selection_updates_structural_and_expression_mark_families() -> None:
    def candidate_entity(
        source_id: str, tag: str, locator: str, shape: str, alternative: str
    ):
        return replace(
            _entity(source_id, tag, locator),
            shape=shape,
            candidates=(
                (shape, 0.7, "audiveris_shape_classifier"),
                (alternative, 0.3, "audiveris_shape_classifier"),
            ),
        )

    entities = {
        "clef": candidate_entity("clef", "clef", "clef-target", "G_CLEF", "F_CLEF"),
        "key": candidate_entity(
            "key", "key", "key-target", "KEY_SHARP_1", "KEY_FLAT_1"
        ),
        "time": candidate_entity(
            "time", "time-whole", "time-target", "TIME_FOUR_FOUR", "TIME_THREE_FOUR"
        ),
        "alter": candidate_entity("alter", "alter", "note-target", "SHARP", "FLAT"),
        "dynamic": candidate_entity(
            "dynamic", "dynamic", "direction-dynamic", "DYNAMICS_F", "DYNAMICS_P"
        ),
        "articulation": candidate_entity(
            "articulation", "articulation", "note-target", "STACCATO", "TENUTO"
        ),
        "ornament": candidate_entity(
            "ornament", "ornament", "note-target", "TR", "MORDENT"
        ),
        "fermata": candidate_entity(
            "fermata", "fermata", "note-target", "FERMATA", "FERMATA_BELOW"
        ),
        "plucking": candidate_entity(
            "plucking", "plucking", "note-target", "PLUCK_P", "PLUCK_I"
        ),
    }
    xml = """<score-partwise><part id="P1"><measure number="1">
      <attributes>
        <clef id="clef-target"><sign>G</sign><line>2</line></clef>
        <key id="key-target"><fifths>1</fifths></key>
        <time id="time-target"><beats>4</beats><beat-type>4</beat-type></time>
      </attributes>
      <direction id="direction-dynamic"><direction-type><dynamics><f/></dynamics></direction-type></direction>
      <note id="note-target"><pitch><step>C</step><alter>1</alter><octave>4</octave></pitch>
        <duration>1</duration><type>quarter</type><accidental>sharp</accidental>
        <notations><articulations><staccato/></articulations><ornaments><trill-mark/></ornaments>
          <fermata type="upright"/><technical><pluck>p</pluck></technical></notations>
      </note>
    </measure></part></score-partwise>"""

    corrected = ET.fromstring(
        apply_candidate_selections(
            xml,
            {
                "clef": "F_CLEF",
                "key": "KEY_FLAT_1",
                "time": "TIME_THREE_FOUR",
                "alter": "FLAT",
                "dynamic": "DYNAMICS_P",
                "articulation": "TENUTO",
                "ornament": "MORDENT",
                "fermata": "FERMATA_BELOW",
                "plucking": "PLUCK_I",
            },
            entities,
        )
    )

    assert corrected.findtext(".//clef/sign") == "F"
    assert corrected.findtext(".//key/fifths") == "-1"
    assert corrected.findtext(".//time/beats") == "3"
    assert corrected.findtext(".//time/beat-type") == "4"
    assert corrected.findtext(".//note/pitch/alter") == "-1"
    assert corrected.findtext(".//note/accidental") == "flat"
    assert corrected.find(".//dynamics/p") is not None
    assert corrected.find(".//articulations/tenuto") is not None
    assert corrected.find(".//ornaments/mordent") is not None
    assert corrected.find(".//fermata").get("type") == "inverted"
    assert corrected.findtext(".//technical/pluck") == "i"


def test_unexported_system_clef_candidate_is_inserted_and_limited_to_its_system() -> (
    None
):
    clef = replace(
        _entity("clef-missing", "clef", "clef-missing"),
        shape="G_CLEF",
        bounds=(10, 5, 12, 30),
        staff="1",
        candidates=(
            ("G_CLEF", 0.8, "audiveris_shape_classifier"),
            ("F_CLEF", 0.2, "audiveris_shape_classifier"),
        ),
    )
    first_note = replace(
        _entity("head-one", "head", "note-one"),
        bounds=(100, 15, 12, 12),
        staff="1",
        pitch=2.0,
    )
    next_system_note = replace(
        _entity("head-two", "head", "note-two"),
        bounds=(100, 100, 12, 12),
        staff="1",
        pitch=2.0,
    )
    xml = """<score-partwise><part id="P1">
      <measure number="1"><attributes><divisions>1</divisions></attributes>
        <note id="note-one"><pitch><step>C</step><octave>4</octave></pitch>
          <duration>1</duration><type>quarter</type></note></measure>
      <measure number="2"><print new-system="yes"/>
        <note id="note-two"><pitch><step>C</step><octave>4</octave></pitch>
          <duration>1</duration><type>quarter</type></note></measure>
    </part></score-partwise>"""

    corrected = ET.fromstring(
        apply_candidate_selections(
            xml,
            {"clef-missing": "F_CLEF"},
            {
                "clef-missing": clef,
                "head-one": first_note,
                "head-two": next_system_note,
            },
        )
    )

    clefs = list(corrected.iter("clef"))
    assert [clef.findtext("sign") for clef in clefs] == ["F", "G"]
    notes = list(corrected.iter("note"))
    assert _pitch(notes[0]) != ("C", 4)
    assert _pitch(notes[1]) == ("C", 4)


def test_candidate_selection_updates_note_value_without_measure_validation() -> None:
    entity = replace(
        _entity("head", "head", "note-1"),
        shape="NOTEHEAD_BLACK",
        candidates=(
            ("NOTEHEAD_BLACK", 0.8, "audiveris_notehead_template"),
            ("NOTEHEAD_VOID", 0.7, "audiveris_notehead_template"),
        ),
    )
    # Changing this quarter note to a half note makes the 4/4 measure overfull.
    # That is allowed here; syntax validation stays a separate workflow.
    xml = (
        "<score-partwise><part><measure><attributes><divisions>1</divisions>"
        "<time><beats>4</beats><beat-type>4</beat-type></time></attributes>"
        '<note id="note-1"><pitch><step>C</step><octave>4</octave></pitch>'
        "<duration>1</duration><type>quarter</type></note>"
        '<note id="note-2"><pitch><step>D</step><octave>4</octave></pitch>'
        "<duration>1</duration><type>quarter</type></note>"
        '<note id="note-3"><pitch><step>E</step><octave>4</octave></pitch>'
        "<duration>1</duration><type>quarter</type></note>"
        '<note id="note-4"><pitch><step>F</step><octave>4</octave></pitch>'
        "<duration>1</duration><type>quarter</type></note>"
        "</measure></part></score-partwise>"
    )

    corrected_xml = apply_candidate_selections(
        xml, {"head": "NOTEHEAD_VOID"}, {"head": entity}
    )
    corrected = ET.fromstring(corrected_xml)

    target_note = corrected.find(".//note[@id='note-1']")
    assert target_note is not None
    assert target_note.findtext("type") == "half"
    assert target_note.findtext("duration") == "2"
    assert "h1" in musicxml_to_jianpu(corrected_xml)


def test_notehead_duration_candidate_updates_all_members_of_its_chord() -> None:
    first = replace(
        _entity("first", "head", "note-first"),
        shape="NOTEHEAD_BLACK",
    )
    selected = replace(
        _entity("selected", "head", "note-selected"),
        shape="NOTEHEAD_BLACK",
        candidates=(
            ("NOTEHEAD_BLACK", 0.7, "audiveris_notehead_template"),
            ("NOTEHEAD_VOID", 0.3, "audiveris_notehead_template"),
        ),
    )
    xml = """<score-partwise><part><measure>
      <attributes><divisions>2</divisions></attributes>
      <note id="note-first"><pitch><step>C</step><octave>4</octave></pitch>
        <duration>1</duration><type>eighth</type></note>
      <note id="note-selected"><chord/><pitch><step>E</step><octave>4</octave></pitch>
        <duration>1</duration><type>eighth</type></note>
      <note id="note-next"><pitch><step>G</step><octave>4</octave></pitch>
        <duration>1</duration><type>eighth</type></note>
    </measure></part></score-partwise>"""

    corrected = ET.fromstring(
        apply_candidate_selections(
            xml,
            {"selected": "NOTEHEAD_VOID"},
            {"first": first, "selected": selected},
        )
    )

    chord = list(corrected.iter("note"))[:2]
    assert [note.findtext("type") for note in chord] == ["half", "half"]
    assert [note.findtext("duration") for note in chord] == ["4", "4"]
    assert corrected.find(".//note[@id='note-next']/type").text == "eighth"


def test_rest_candidate_updates_recognized_value_without_rhythm_validation() -> None:
    entity = replace(
        _entity("rest", "rest", "rest-note"),
        shape="QUARTER_REST",
        candidates=(
            ("QUARTER_REST", 0.8, "audiveris_shape_classifier"),
            ("HALF_REST", 0.7, "audiveris_shape_classifier"),
        ),
    )
    xml = (
        "<score-partwise><part><measure><attributes><divisions>1</divisions>"
        "<time><beats>1</beats><beat-type>4</beat-type></time></attributes>"
        '<note id="rest-note"><rest/><duration>1</duration><type>quarter</type></note>'
        "</measure></part></score-partwise>"
    )

    corrected = ET.fromstring(
        apply_candidate_selections(xml, {"rest": "HALF_REST"}, {"rest": entity})
    )

    assert corrected.findtext(".//note/type") == "half"
    assert corrected.findtext(".//note/duration") == "2"


def test_candidate_selection_updates_non_notehead_mark_families() -> None:
    entities = {
        "slur": replace(
            _entity("slur", "slur", "slur-source"),
            shape="SLUR_ABOVE",
            candidates=(
                ("SLUR_ABOVE", 0.8, "audiveris_shape_classifier"),
                ("SLUR_BELOW", 0.7, "audiveris_shape_classifier"),
            ),
        ),
        "tuplet": replace(
            _entity("tuplet", "tuplet", "tuplet-source"),
            shape="TUPLET_THREE",
            candidates=(
                ("TUPLET_THREE", 0.8, "audiveris_shape_classifier"),
                ("TUPLET_SIX", 0.7, "audiveris_shape_classifier"),
            ),
        ),
        "fingering": replace(
            _entity("fingering", "fingering", "note-finger"),
            shape="DIGIT_1",
            candidates=(
                ("DIGIT_1", 0.8, "audiveris_shape_classifier"),
                ("DIGIT_2", 0.7, "audiveris_shape_classifier"),
            ),
        ),
        "pause": replace(
            _entity("pause", "breath-mark", "note-pause"),
            shape="BREATH_MARK",
            candidates=(
                ("BREATH_MARK", 0.8, "audiveris_shape_classifier"),
                ("CAESURA", 0.7, "audiveris_shape_classifier"),
            ),
        ),
        "bow": replace(
            _entity("bow", "bow", "note-bow"),
            shape="BOW_DOWN",
            candidates=(
                ("BOW_DOWN", 0.8, "audiveris_shape_classifier"),
                ("BOW_UP", 0.7, "audiveris_shape_classifier"),
            ),
        ),
        "wedge": replace(
            _entity("wedge", "wedge", "direction-wedge"),
            shape="CRESCENDO",
            candidates=(
                ("CRESCENDO", 0.8, "audiveris_shape_classifier"),
                ("DIMINUENDO", 0.7, "audiveris_shape_classifier"),
            ),
        ),
        "pedal": replace(
            _entity("pedal", "pedal", "direction-pedal"),
            shape="PEDAL_MARK",
            candidates=(
                ("PEDAL_MARK", 0.8, "audiveris_shape_classifier"),
                ("PEDAL_UP_MARK", 0.7, "audiveris_shape_classifier"),
            ),
        ),
    }
    xml = """<score-partwise><part><measure>
      <note id="st__slur-source__tuplet-source__note-finger__note-pause__note-bow"><pitch><step>C</step><octave>4</octave></pitch>
        <duration>1</duration><notations><slur type="start" placement="above"/>
          <tuplet type="start"><tuplet-actual><tuplet-number>3</tuplet-number></tuplet-actual></tuplet>
          <technical><fingering>1</fingering><down-bow/></technical>
          <articulations><breath-mark/></articulations></notations></note>
      <note id="st__slur-source__tuplet-source__other"><pitch><step>D</step><octave>4</octave></pitch>
        <duration>1</duration><notations><slur type="stop" placement="above"/>
          <tuplet type="stop"><tuplet-actual><tuplet-number>3</tuplet-number></tuplet-actual></tuplet>
        </notations></note>
      <direction id="st__direction-wedge"><direction-type><wedge type="crescendo"/></direction-type></direction>
      <direction id="st__direction-pedal"><direction-type><pedal type="start"/></direction-type><sound damper-pedal="yes"/></direction>
    </measure></part></score-partwise>"""

    corrected = ET.fromstring(
        apply_candidate_selections(
            xml,
            {
                "slur": "SLUR_BELOW",
                "tuplet": "TUPLET_SIX",
                "fingering": "DIGIT_2",
                "pause": "CAESURA",
                "bow": "BOW_UP",
                "wedge": "DIMINUENDO",
                "pedal": "PEDAL_UP_MARK",
            },
            entities,
        )
    )

    assert [item.get("placement") for item in corrected.iter("slur")] == [
        "below",
        "below",
    ]
    assert [
        item.findtext("tuplet-actual/tuplet-number")
        for item in corrected.iter("tuplet")
    ] == ["6", "6"]
    assert corrected.findtext(".//technical/fingering") == "2"
    assert corrected.find(".//technical/up-bow") is not None
    assert corrected.find(".//articulations/caesura") is not None
    assert corrected.find(".//direction-type/wedge").get("type") == "diminuendo"
    assert corrected.find(".//direction-type/pedal").get("type") == "stop"
    assert corrected.find(".//sound").get("damper-pedal") == "no"


def test_pedal_candidate_is_inserted_when_audiveris_omits_musicxml_direction() -> None:
    pedal = replace(
        _entity("pedal", "pedal", "direction-pedal"),
        shape="PEDAL_MARK",
        bounds=(40, 10, 12, 8),
        staff="1",
        candidates=(
            ("PEDAL_MARK", 0.8, "audiveris_shape_classifier"),
            ("PEDAL_UP_MARK", 0.2, "audiveris_shape_classifier"),
        ),
    )
    note = replace(
        _entity("note", "head", "note-1"),
        bounds=(50, 20, 10, 10),
        staff="1",
    )
    xml = '<score-partwise><part><measure><note id="note-1"><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration></note></measure></part></score-partwise>'

    corrected = ET.fromstring(
        apply_candidate_selections(
            xml,
            {"pedal": "PEDAL_UP_MARK"},
            {"pedal": pedal, "note": note},
        )
    )

    direction = corrected.find(".//direction")
    assert direction is not None
    assert direction.find("direction-type/pedal").get("type") == "stop"
    assert direction.find("sound").get("damper-pedal") == "no"
    assert list(corrected.find(".//measure"))[0] is direction


def test_unrecognized_notehead_candidate_inserts_note_at_glyph_position() -> None:
    neighbor = replace(
        _entity("s1:i10", "head", "note-neighbor", inter_id="10"),
        shape="NOTEHEAD_BLACK",
        bounds=(10, 10, 12, 8),
        staff="2",
        pitch=0,
    )
    glyph = CorrectableGlyph(
        glyph_id="s1:g99",
        bounds=(30, 3, 12, 8),
        hit_path="M30 3h12v8z",
        candidates=(
            ("NOTEHEAD_BLACK", 0.73, "audiveris_notehead_template"),
            ("NOTEHEAD_VOID", 0.61, "audiveris_notehead_template"),
        ),
        tag="unrecognized-head",
        shape="UNKNOWN",
        grade=0,
        staff="2",
        pitch=-1,
        part_id="P1",
        measure_number="1",
    )
    xml = (
        '<score-partwise><part id="P1"><measure number="1">'
        "<attributes><divisions>1</divisions></attributes>"
        '<note id="note-neighbor"><pitch><step>C</step><octave>4</octave></pitch>'
        "<duration>1</duration><voice>3</voice><type>quarter</type><staff>2</staff></note>"
        "</measure></part></score-partwise>"
    )

    corrected = ET.fromstring(
        apply_candidate_selections(
            xml,
            {glyph.glyph_id: "NOTEHEAD_VOID"},
            {neighbor.source_id: neighbor},
            {glyph.glyph_id: glyph},
        )
    )

    notes = corrected.findall(".//measure/note")
    assert len(notes) == 2
    inserted = notes[1]
    assert inserted.get("id") == "st__n-s1-g99"
    assert inserted.findtext("pitch/step") == "D"
    assert inserted.findtext("pitch/octave") == "4"
    assert inserted.findtext("duration") == "2"
    assert inserted.findtext("type") == "half"
    assert inserted.findtext("voice") == "3"
    assert inserted.findtext("staff") == "2"


def test_deleting_unrecognized_glyph_is_valid_and_does_not_insert_it() -> None:
    glyph = CorrectableGlyph(
        glyph_id="s1:g99",
        bounds=(30, 3, 12, 8),
        hit_path="M30 3h12v8z",
        candidates=(("NOTEHEAD_BLACK", 0.73, "audiveris_notehead_template"),),
        tag="unrecognized-head",
        shape="UNKNOWN",
        grade=0,
    )
    xml = '<score-partwise><part><measure number="1" /></part></score-partwise>'

    assert ET.tostring(
        ET.fromstring(
            apply_deletions(xml, [glyph.glyph_id], {}, {glyph.glyph_id: glyph})
        )
    ) == ET.tostring(ET.fromstring(xml))
    with pytest.raises(ValueError, match="无法定位待删除标记"):
        apply_deletions(xml, ["s1:g404"], {}, {glyph.glyph_id: glyph})


def test_unexported_musicxml_head_inter_is_inserted_when_candidate_is_selected() -> (
    None
):
    neighbor = replace(
        _entity("s1:i10", "head", "note-neighbor", inter_id="10"),
        shape="NOTEHEAD_BLACK",
        bounds=(10, 10, 12, 8),
        staff="1",
        pitch=0,
    )
    omitted = replace(
        _entity("s1:i99", "head", "note-omitted", inter_id="99"),
        shape="NOTEHEAD_BLACK",
        bounds=(30, 3, 12, 8),
        staff="1",
        pitch=-1,
        part_id="P1",
        measure_number="1",
        candidates=(
            ("NOTEHEAD_BLACK", 0.38, "audiveris_shape_classifier"),
            ("NOTEHEAD_VOID", 0.31, "audiveris_shape_classifier"),
        ),
    )
    xml = (
        '<score-partwise><part id="P1"><measure number="1">'
        "<attributes><divisions>1</divisions></attributes>"
        '<note id="note-neighbor"><pitch><step>C</step><octave>4</octave></pitch>'
        "<duration>1</duration><type>quarter</type></note>"
        "</measure></part></score-partwise>"
    )

    corrected = ET.fromstring(
        apply_candidate_selections(
            xml,
            {omitted.source_id: "NOTEHEAD_VOID"},
            {neighbor.source_id: neighbor, omitted.source_id: omitted},
        )
    )

    notes = corrected.findall(".//measure/note")
    assert len(notes) == 2
    inserted = notes[1]
    assert inserted.get("id") == "st__n-s1-i99"
    assert inserted.findtext("type") == "half"
    assert inserted.findtext("pitch/step") == "D"


def test_missing_clef_current_candidate_is_inserted_without_pitch_transform() -> None:
    clef = replace(
        _candidate_entity("clef-missing", "clef", "clef-missing", "G_CLEF", "F_CLEF"),
        bounds=(10, 5, 12, 30),
        staff="1",
    )
    anchor = replace(
        _entity("head-one", "head", "note-one"),
        bounds=(100, 15, 12, 12),
        staff="1",
        pitch=2.0,
    )
    xml = """<score-partwise><part><measure>
      <note id="note-one"><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration><type>quarter</type></note>
    </measure></part></score-partwise>"""

    corrected = ET.fromstring(
        apply_candidate_selections(
            xml,
            {"clef-missing": "G_CLEF"},
            {"clef-missing": clef, "head-one": anchor},
        )
    )

    assert corrected.findtext(".//clef/sign") == "G"
    assert _pitch(next(corrected.iter("note"))) == ("C", 4)


def test_missing_pedal_current_candidate_is_inserted() -> None:
    pedal = replace(
        _candidate_entity(
            "pedal", "pedal", "direction-pedal", "PEDAL_MARK", "PEDAL_UP_MARK"
        ),
        bounds=(40, 10, 12, 8),
        staff="1",
    )
    note = replace(
        _entity("note", "head", "note-1"),
        bounds=(50, 20, 10, 10),
        staff="1",
    )
    xml = '<score-partwise><part><measure><note id="note-1"><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration></note></measure></part></score-partwise>'

    corrected = ET.fromstring(
        apply_candidate_selections(
            xml,
            {"pedal": "PEDAL_MARK"},
            {"pedal": pedal, "note": note},
        )
    )

    assert corrected.find(".//direction-type/pedal").get("type") == "start"
    assert corrected.find(".//sound").get("damper-pedal") == "yes"


def test_tuplet_candidate_updates_whole_group_and_jianpu() -> None:
    tuplet = _candidate_entity(
        "tuplet", "tuplet", "tuplet-source", "TUPLET_THREE", "TUPLET_SIX"
    )
    notes = []
    for index, step in enumerate("CDEFGA"):
        note_id = f"note-{index}"
        notations = ""
        if index == 0:
            note_id = "st__group__tuplet-source__first"
            notations = '<notations><tuplet type="start"><tuplet-actual><tuplet-number>3</tuplet-number></tuplet-actual></tuplet></notations>'
        elif index == 5:
            note_id = "st__group__tuplet-source__last"
            notations = '<notations><tuplet type="stop"><tuplet-actual><tuplet-number>3</tuplet-number></tuplet-actual></tuplet></notations>'
        notes.append(
            f'<note id="{note_id}"><pitch><step>{step}</step><octave>4</octave></pitch>'
            "<duration>1</duration><type>eighth</type>"
            "<time-modification><actual-notes>3</actual-notes><normal-notes>2</normal-notes></time-modification>"
            f"{notations}</note>"
        )
    xml = (
        '<score-partwise><part id="P1"><measure number="1"><attributes><divisions>2</divisions></attributes>'
        + "".join(notes)
        + "</measure></part></score-partwise>"
    )

    corrected_xml = apply_candidate_selections(
        xml, {"tuplet": "TUPLET_SIX"}, {"tuplet": tuplet}
    )
    corrected = ET.fromstring(corrected_xml)

    assert [
        item.text
        for item in corrected.findall(".//note/time-modification/actual-notes")
    ] == ["6"] * 6
    assert [
        item.text
        for item in corrected.findall(".//note/time-modification/normal-notes")
    ] == ["4"] * 6
    assert [
        item.findtext("tuplet-actual/tuplet-number")
        for item in corrected.iter("tuplet")
    ] == ["6", "6"]
    assert musicxml_to_jianpu(corrected_xml) != musicxml_to_jianpu(xml)


def test_replacing_marks_preserves_sibling_notations_and_direction_content() -> None:
    articulation = _candidate_entity(
        "articulation", "articulation", "note-target", "STACCATO", "TENUTO"
    )
    ornament = _candidate_entity("ornament", "ornament", "note-target", "TR", "MORDENT")
    dynamic = _candidate_entity(
        "dynamic", "dynamic", "direction-dynamic", "DYNAMICS_F", "DYNAMICS_P"
    )
    xml = """<score-partwise><part><measure>
      <direction id="direction-dynamic"><direction-type><dynamics><f/></dynamics></direction-type><direction-type><words>dolce</words></direction-type><sound/></direction>
      <note id="note-target"><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration><type>quarter</type>
        <notations><articulations><accent/><staccato/></articulations><ornaments><trill-mark/><turn/></ornaments></notations>
      </note>
    </measure></part></score-partwise>"""

    corrected = ET.fromstring(
        apply_candidate_selections(
            xml,
            {
                "articulation": "TENUTO",
                "ornament": "MORDENT",
                "dynamic": "DYNAMICS_P",
            },
            {
                "articulation": articulation,
                "ornament": ornament,
                "dynamic": dynamic,
            },
        )
    )

    articulations = [item.tag for item in corrected.findall(".//articulations/*")]
    ornaments = [item.tag for item in corrected.findall(".//ornaments/*")]
    assert articulations == ["accent", "tenuto"]
    assert ornaments == ["turn", "mordent"]
    assert corrected.findtext(".//direction/words") is None
    assert corrected.findtext(".//direction-type/words") == "dolce"
    assert corrected.find(".//dynamics/p") is not None
    direction = corrected.find(".//direction")
    assert direction is not None
    assert [item.tag for item in direction][-1] == "sound"


def test_new_note_children_follow_musicxml_schema_order() -> None:
    head = _candidate_entity(
        "head", "head", "note-target", "NOTEHEAD_BLACK", "NOTEHEAD_CROSS"
    )
    alter = _candidate_entity("alter", "alter", "note-target", "SHARP", "FLAT")
    xml = """<score-partwise><part><measure>
      <note id="note-target"><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration><type>quarter</type><time-modification><actual-notes>3</actual-notes><normal-notes>2</normal-notes></time-modification><notations/></note>
    </measure></part></score-partwise>"""

    corrected = ET.fromstring(
        apply_candidate_selections(
            xml,
            {"head": "NOTEHEAD_CROSS", "alter": "FLAT"},
            {"head": head, "alter": alter},
        )
    )

    names = [item.tag for item in corrected.find(".//note")]
    assert names == [
        "pitch",
        "duration",
        "type",
        "accidental",
        "time-modification",
        "notehead",
        "notations",
    ]


def test_duration_ratio_uses_half_up_rounding() -> None:
    head = _candidate_entity(
        "head", "head", "note-target", "WHOLE_NOTE", "NOTEHEAD_BLACK"
    )
    xml = '<score-partwise><part><measure><note id="note-target"><pitch><step>C</step><octave>4</octave></pitch><duration>10</duration><type>whole</type></note></measure></part></score-partwise>'

    corrected = ET.fromstring(
        apply_candidate_selections(xml, {"head": "NOTEHEAD_BLACK"}, {"head": head})
    )

    assert corrected.findtext(".//note/duration") == "3"
    assert corrected.findtext(".//note/type") == "quarter"


def test_candidate_selection_rejects_unknown_candidate_atomically() -> None:
    entity = _entity("head", "head", "note-1")
    with pytest.raises(ValueError, match="不包含候选"):
        apply_candidate_selections(
            '<score-partwise><part><measure><note id="note-1"/></measure></part></score-partwise>',
            {"head": "NOT_A_CANDIDATE"},
            {"head": entity},
        )


def test_musicxml_locator_does_not_confuse_numeric_id_prefixes() -> None:
    first = _candidate_entity(
        "s1:i1", "head", "n-s1-i1", "NOTEHEAD_BLACK", "NOTEHEAD_CROSS"
    )
    tenth = _candidate_entity(
        "s1:i10", "head", "n-s1-i10", "NOTEHEAD_BLACK", "NOTEHEAD_VOID"
    )
    xml = """<score-partwise><part><measure>
      <note id="st__n-s1-i1"><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration><type>quarter</type></note>
      <note id="st__n-s1-i10"><pitch><step>D</step><octave>4</octave></pitch><duration>1</duration><type>quarter</type></note>
    </measure></part></score-partwise>"""

    corrected = ET.fromstring(
        apply_candidate_selections(
            xml,
            {"s1:i1": "NOTEHEAD_CROSS", "s1:i10": "NOTEHEAD_VOID"},
            {"s1:i1": first, "s1:i10": tenth},
        )
    )

    notes = {note.get("id"): note for note in corrected.iter("note")}
    assert notes["st__n-s1-i1"].findtext("notehead") == "x"
    assert notes["st__n-s1-i1"].findtext("type") == "quarter"
    assert notes["st__n-s1-i10"].findtext("type") == "half"
    assert notes["st__n-s1-i10"].findtext("duration") == "2"


def test_unexported_head_does_not_reuse_longer_numeric_id_match() -> None:
    omitted = replace(
        _candidate_entity(
            "s1:i1", "head", "n-s1-i1", "NOTEHEAD_BLACK", "NOTEHEAD_VOID"
        ),
        inter_id="1",
        bounds=(30, 3, 12, 8),
        staff="1",
        pitch=-1,
        part_id="P1",
        measure_number="1",
    )
    neighbor = replace(
        _entity("s1:i10", "head", "n-s1-i10", inter_id="10"),
        shape="NOTEHEAD_BLACK",
        bounds=(10, 10, 12, 8),
        staff="1",
        pitch=0,
    )
    xml = """<score-partwise><part id="P1"><measure number="1"><attributes><divisions>1</divisions></attributes>
      <note id="st__n-s1-i10"><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration><type>quarter</type></note>
    </measure></part></score-partwise>"""

    corrected = ET.fromstring(
        apply_candidate_selections(
            xml,
            {"s1:i1": "NOTEHEAD_VOID"},
            {"s1:i1": omitted, "s1:i10": neighbor},
        )
    )

    notes = list(corrected.iter("note"))
    assert len(notes) == 2
    assert notes[0].get("id") == "st__n-s1-i10"
    assert notes[0].findtext("type") == "quarter"
    assert notes[1].get("id") == "st__n-s1-i1"
    assert notes[1].findtext("type") == "half"
    assert notes[1].findtext("pitch/step") == "D"


def test_wedge_locator_prefix_collision_does_not_change_other_wedges() -> None:
    wedge = _candidate_entity("s1:i1", "wedge", "wg-s1-i1", "CRESCENDO", "DIMINUENDO")
    xml = """<score-partwise><part><measure>
      <direction id="wg-s1-i1-start"><direction-type><wedge type="crescendo"/></direction-type></direction>
      <direction id="wg-s1-i1-stop"><direction-type><wedge type="stop"/></direction-type></direction>
      <direction id="wg-s1-i10-start"><direction-type><wedge type="crescendo"/></direction-type></direction>
    </measure></part></score-partwise>"""

    corrected = ET.fromstring(
        apply_candidate_selections(xml, {"s1:i1": "DIMINUENDO"}, {"s1:i1": wedge})
    )

    directions = {item.get("id"): item for item in corrected.iter("direction")}
    assert directions["wg-s1-i1-start"].find(".//wedge").get("type") == "diminuendo"
    assert directions["wg-s1-i1-stop"].find(".//wedge").get("type") == "stop"
    assert directions["wg-s1-i10-start"].find(".//wedge").get("type") == "crescendo"


def test_slur_locator_matches_musicxml_start_and_end_roles() -> None:
    slur = _candidate_entity("s1:i42", "slur", "s-s1-i42", "SLUR_ABOVE", "SLUR_BELOW")
    xml = """<score-partwise><part><measure>
      <note id="st__ss-s1-i42"><notations><slur type="start" placement="above"/></notations></note>
      <note id="st__se-s1-i42"><notations><slur type="stop" placement="above"/></notations></note>
    </measure></part></score-partwise>"""

    corrected = ET.fromstring(
        apply_candidate_selections(xml, {"s1:i42": "SLUR_BELOW"}, {"s1:i42": slur})
    )

    assert [item.get("placement") for item in corrected.iter("slur")] == [
        "below",
        "below",
    ]


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
        jianpu_measures_per_system=4,
        jianpu_margin_top_mm=15.5,
        jianpu_header_gap_mm=7.5,
        jianpu_footer_protection_mm=4,
        jianpu_note_size_percent=120,
        jianpu_lyric_size_percent=85,
        jianpu_title_size_percent=130,
        jianpu_annotation_size_percent=95,
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
    assert renderer.kwargs["measures_per_system"] == 4
    layout = renderer.kwargs["layout"]
    assert layout.margin_top_mm == 15.5
    assert layout.header_gap_mm == 7.5
    assert layout.footer_protection_mm == 4
    assert layout.note_size_percent == 120
    assert layout.lyric_size_percent == 85
    assert layout.title_size_percent == 130
    assert layout.annotation_size_percent == 95


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


def test_extract_entities_uses_omr_key_shape_when_source_map_is_unknown(
    tmp_path: Path,
) -> None:
    omr = tmp_path / "score.omr"
    sheet_xml = """<sheet><picture width="1000" height="1400"/><inters>
      <key id="105" fifths="2"><bounds x="50" y="20" w="20" h="40"/></key>
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
                        source_id="s1:i105",
                        inter_id=105,
                        shape="null",
                        grade=0.9,
                        bounds=BoundingBox(x=50, y=20, width=20, height=40),
                        hit_path="M50 20h20v40z",
                        musicxml_locator=MusicXmlLocator(contains="k-s1-i105"),
                    )
                ],
            )
        ]
    )

    entity = extract_entities(omr, source_map)[0].entities[0]

    assert entity.shape == "KEY_SHARP_2"
    assert entity.candidates == (("KEY_SHARP_2", 0.9, "audiveris_inter_grade"),)


def test_rank_candidates_keeps_recognized_shape_when_outscored() -> None:
    """Top-5 截断时也必须保留当前识别形状，否则改选后无法恢复原始结果。"""
    ranked = _rank_candidates(
        tuple(
            (f"SHAPE_{index}", 0.9 - index * 0.05, "audiveris_shape_classifier")
            for index in range(6)
        )
        + (("CURRENT", 0.01, "audiveris_inter_grade"),),
        "CURRENT",
    )

    assert len(ranked) == 5
    assert ranked[-1][0] == "CURRENT"
    assert "SHAPE_5" not in {item[0] for item in ranked}


@pytest.mark.parametrize(
    ("tag", "valid_shape", "invalid_shape"),
    [
        ("time-whole", "TIME_FOUR_FOUR", "NOTEHEAD_BLACK"),
        ("rest", "QUARTER_REST", "NOTEHEAD_VOID"),
        ("alter", "SHARP", "NOTEHEAD_BLACK"),
        ("dynamics", "DYNAMICS_F", "NOTEHEAD_BLACK"),
    ],
)
def test_candidate_family_filter_rejects_cross_family_shapes(
    tag: str, valid_shape: str, invalid_shape: str
) -> None:
    candidates = (
        (valid_shape, 0.7, "audiveris_shape_classifier"),
        (invalid_shape, 0.99, "audiveris_shape_classifier"),
    )

    assert _candidates_for_family(candidates, tag) == (candidates[0],)


def test_time_nine_eight_candidate_updates_signature() -> None:
    """9/8 是合法拍号，不能退化成不可应用的 TIME_CUSTOM。"""
    entity = replace(
        _entity("s1:i9", "time-whole", "t-s1-i9"),
        shape="TIME_THREE_FOUR",
        candidates=(
            ("TIME_THREE_FOUR", 0.9, "audiveris_inter_grade"),
            ("TIME_NINE_EIGHT", 0.7, "audiveris_shape_classifier_composite"),
        ),
    )
    xml = """<score-partwise><part><measure number="1">
      <attributes><time id="t-s1-i9"><beats>3</beats><beat-type>4</beat-type></time></attributes>
    </measure></part></score-partwise>"""

    corrected = ET.fromstring(
        apply_candidate_selections(xml, {"s1:i9": "TIME_NINE_EIGHT"}, {"s1:i9": entity})
    )

    assert corrected.findtext(".//time/beats") == "9"
    assert corrected.findtext(".//time/beat-type") == "8"


def test_offset_glyph_is_inserted_before_chord_head_without_joining_it() -> None:
    """离和弦列很远的 glyph 仍是独立音符（近似的降级行为，不是和弦）。"""
    head_entity = replace(
        _entity("n-s1-i1", "head", "n-s1-i1"),
        bounds=(100, 20, 10, 10),
        shape="NOTEHEAD_BLACK",
        staff="1",
        pitch=0.0,
    )
    follower_entity = replace(
        _entity("n-s1-i2", "head", "n-s1-i2", inter_id="2"),
        bounds=(50, 20, 10, 10),
        shape="NOTEHEAD_BLACK",
        staff="1",
        pitch=2.0,
    )
    glyph = CorrectableGlyph(
        glyph_id="s1:g7",
        bounds=(5, 20, 8, 10),
        hit_path="M5 20h8v10z",
        candidates=(("NOTEHEAD_BLACK", 0.8, "audiveris_notehead_template"),),
        tag="head",
        shape="NOTEHEAD_BLACK",
        grade=0.0,
        staff="1",
        pitch=0.0,
        part_id="P1",
        measure_number="1",
    )
    xml = """<score-partwise><part id="P1"><measure number="1">
      <attributes><divisions>4</divisions></attributes>
      <note id="n-s1-i1"><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration><type>quarter</type></note>
      <note id="n-s1-i2"><chord/><pitch><step>E</step><octave>4</octave></pitch><duration>4</duration><type>quarter</type></note>
    </measure></part></score-partwise>"""

    corrected = ET.fromstring(
        apply_candidate_selections(
            xml,
            {"s1:g7": "NOTEHEAD_BLACK"},
            {"n-s1-i1": head_entity, "n-s1-i2": follower_entity},
            {"s1:g7": glyph},
        )
    )

    notes = corrected.findall(".//measure/note")
    inserted = [note for note in notes if note.get("id", "").startswith("st__n-s1-g7")]
    assert len(inserted) == 1
    assert notes.index(inserted[0]) == 0
    assert inserted[0].find("chord") is None
    assert notes.index(inserted[0]) + 1 == next(
        index for index, note in enumerate(notes) if note.get("id") == "n-s1-i1"
    )
    assert notes[-1].find("chord") is not None


def test_phantom_candidate_is_not_reported_as_applied() -> None:
    """定位不到 MusicXML 元素的候选不能返回为已应用。"""
    entity = _candidate_entity("k-s1-i7", "key", "k-s1-i7", "KEY_SHARP_2", "KEY_FLAT_2")
    xml = """<score-partwise><part><measure number="1">
      <attributes><key><fifths>0</fifths></key></attributes>
    </measure></part></score-partwise>"""
    applied: dict[str, str] = {}

    corrected = apply_candidate_selections(
        xml, {"k-s1-i7": "KEY_FLAT_2"}, {"k-s1-i7": entity}, applied_out=applied
    )

    assert applied == {}
    assert ET.fromstring(corrected).findtext(".//key/fifths") == "0"


def test_applied_candidate_is_reported_for_real_target() -> None:
    """能定位到目标的候选应出现在 applied 集合中。"""
    entity = replace(
        _entity("s1:i9", "time-whole", "t-s1-i9"),
        shape="TIME_THREE_FOUR",
        candidates=(
            ("TIME_THREE_FOUR", 0.9, "audiveris_inter_grade"),
            ("TIME_NINE_EIGHT", 0.7, "audiveris_shape_classifier_composite"),
        ),
    )
    xml = """<score-partwise><part><measure number="1">
      <attributes><time id="t-s1-i9"><beats>3</beats><beat-type>4</beat-type></time></attributes>
    </measure></part></score-partwise>"""
    applied: dict[str, str] = {}

    apply_candidate_selections(
        xml, {"s1:i9": "TIME_NINE_EIGHT"}, {"s1:i9": entity}, applied_out=applied
    )

    assert applied == {"s1:i9": "TIME_NINE_EIGHT"}


def test_apply_rejects_overlapping_delete_and_candidate() -> None:
    """同一标记不能既删除又选候选，避免先删后改产生的歧义。"""
    from score_trans.exec.correct.actions import CorrectActions

    request = CorrectionRequest(
        original_musicxml="<score-partwise/>",
        omr_file_id="omr",
        source_map_file_id="map",
        deleted_source_ids=["s1:i1"],
        candidate_selections={"s1:i1": "NOTEHEAD_VOID"},
    )

    with pytest.raises(ValueError, match="同时删除并选择候选"):
        CorrectActions().apply_corrections(request)


def _head_at(
    source_id: str,
    *,
    x: int,
    pitch: float,
    staff: str = "1",
    shape: str = "NOTEHEAD_BLACK",
) -> CorrectableEntity:
    return replace(
        _entity(source_id, "head", source_id),
        bounds=(x, 20, 12, 10),
        shape=shape,
        staff=staff,
        pitch=pitch,
        candidates=((shape, 0.9, "audiveris_inter_grade"),),
    )


def _glyph_at(
    glyph_id: str,
    *,
    x: int,
    pitch: float,
    staff: str = "1",
    shape: str = "NOTEHEAD_BLACK",
    tag: str = "unrecognized-head",
    part_id: str | None = None,
    measure_number: str | None = None,
) -> CorrectableGlyph:
    return CorrectableGlyph(
        glyph_id=glyph_id,
        bounds=(x, 24, 12, 10),
        hit_path="M0 0h12v10z",
        candidates=((shape, 0.8, "audiveris_notehead_template"),),
        tag=tag,
        shape="UNKNOWN",
        grade=0.0,
        staff=staff,
        pitch=pitch,
        part_id=part_id,
        measure_number=measure_number,
    )


_CHORD_XML = """<score-partwise><part id="P1"><measure number="1">
  <attributes><divisions>4</divisions></attributes>
  <note id="n-s1-i1"><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration><voice>1</voice><type>quarter</type></note>
  <note id="n-s1-i2"><pitch><step>G</step><octave>4</octave></pitch><duration>4</duration><voice>1</voice><type>quarter</type></note>
</measure></part></score-partwise>"""


def _apply_chord_case(
    xml: str,
    entities: dict[str, CorrectableEntity],
    glyphs: dict[str, CorrectableGlyph],
    selections: dict[str, str],
) -> ET.Element:
    return ET.fromstring(apply_candidate_selections(xml, selections, entities, glyphs))


def test_same_column_glyph_becomes_chord_member() -> None:
    """同列的未识别符头应写成和弦成员，而不是新的时间步。"""
    corrected = _apply_chord_case(
        _CHORD_XML,
        {
            "n-s1-i1": _head_at("n-s1-i1", x=100, pitch=0.0),
            "n-s1-i2": _head_at("n-s1-i2", x=200, pitch=4.0),
        },
        {"s1:g7": _glyph_at("s1:g7", x=100, pitch=-2.0)},
        {"s1:g7": "NOTEHEAD_BLACK"},
    )

    notes = corrected.findall(".//measure/note")
    assert len(notes) == 3
    inserted = notes[1]
    assert inserted.get("id") == "st__n-s1-g7"
    assert inserted.find("chord") is not None
    assert inserted.findtext("pitch/step") == "E"
    assert inserted.findtext("duration") == "4"
    assert inserted.findtext("type") == "quarter"
    # 和弦成员不推进时间轴：非和弦音符的总时值不变
    assert (
        sum(
            int(note.findtext("duration"))
            for note in notes
            if note.find("chord") is None
        )
        == 8
    )


def test_same_column_tolerates_second_interval_offset() -> None:
    """二度叠置的符头会横向错开一点，仍应并入同一和弦列。"""
    corrected = _apply_chord_case(
        _CHORD_XML,
        {
            "n-s1-i1": _head_at("n-s1-i1", x=100, pitch=0.0),
            "n-s1-i2": _head_at("n-s1-i2", x=200, pitch=4.0),
        },
        {"s1:g7": _glyph_at("s1:g7", x=111, pitch=-2.0)},
        {"s1:g7": "NOTEHEAD_BLACK"},
    )

    inserted = [
        note
        for note in corrected.findall(".//measure/note")
        if (note.get("id") or "").startswith("st__n-s1-g7")
    ]
    assert len(inserted) == 1
    assert inserted[0].find("chord") is not None


def test_glyph_beyond_tolerance_stays_independent_note() -> None:
    """明显属于下一列时不能误并成和弦。"""
    corrected = _apply_chord_case(
        _CHORD_XML,
        {
            "n-s1-i1": _head_at("n-s1-i1", x=100, pitch=0.0),
            "n-s1-i2": _head_at("n-s1-i2", x=200, pitch=4.0),
        },
        {
            "s1:g7": _glyph_at(
                "s1:g7", x=120, pitch=-2.0, part_id="P1", measure_number="1"
            )
        },
        {"s1:g7": "NOTEHEAD_BLACK"},
    )

    notes = corrected.findall(".//measure/note")
    inserted = [
        note for note in notes if (note.get("id") or "").startswith("st__n-s1-g7")
    ]
    assert len(inserted) == 1
    assert inserted[0].find("chord") is None
    assert notes.index(inserted[0]) == 1


def test_chord_member_is_appended_after_last_member() -> None:
    """三音和弦的组尾之后插入，既有 follower 保持原位。"""
    xml = """<score-partwise><part><measure number="1">
      <attributes><divisions>4</divisions></attributes>
      <note id="n-s1-i1"><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration><type>quarter</type></note>
      <note id="n-s1-i2"><chord/><pitch><step>E</step><octave>4</octave></pitch><duration>4</duration><type>quarter</type></note>
      <note id="n-s1-i3"><chord/><pitch><step>G</step><octave>4</octave></pitch><duration>4</duration><type>quarter</type></note>
      <note id="n-s1-i4"><pitch><step>B</step><octave>4</octave></pitch><duration>4</duration><type>quarter</type></note>
    </measure></part></score-partwise>"""
    corrected = _apply_chord_case(
        xml,
        {
            "n-s1-i1": _head_at("n-s1-i1", x=100, pitch=0.0),
            "n-s1-i2": _head_at("n-s1-i2", x=100, pitch=2.0),
            "n-s1-i3": _head_at("n-s1-i3", x=100, pitch=4.0),
            "n-s1-i4": _head_at("n-s1-i4", x=200, pitch=6.0),
        },
        {"s1:g7": _glyph_at("s1:g7", x=100, pitch=-1.0)},
        {"s1:g7": "NOTEHEAD_BLACK"},
    )

    notes = corrected.findall(".//measure/note")
    assert [note.get("id") for note in notes] == [
        "n-s1-i1",
        "n-s1-i2",
        "n-s1-i3",
        "st__n-s1-g7",
        "n-s1-i4",
    ]
    assert notes[3].find("chord") is not None
    assert notes[2].find("chord") is not None


def test_chord_member_inherits_dotted_duration() -> None:
    """和弦头是附点音符时，成员继承它的 duration/type。"""
    xml = """<score-partwise><part><measure number="1">
      <attributes><divisions>4</divisions></attributes>
      <note id="n-s1-i1"><pitch><step>C</step><octave>4</octave></pitch><duration>6</duration><voice>1</voice><type>quarter</type><dot/></note>
      <note id="n-s1-i2"><pitch><step>G</step><octave>4</octave></pitch><duration>4</duration><voice>1</voice><type>quarter</type></note>
    </measure></part></score-partwise>"""
    corrected = _apply_chord_case(
        xml,
        {
            "n-s1-i1": _head_at("n-s1-i1", x=100, pitch=0.0),
            "n-s1-i2": _head_at("n-s1-i2", x=200, pitch=4.0),
        },
        {"s1:g7": _glyph_at("s1:g7", x=100, pitch=-2.0)},
        {"s1:g7": "NOTEHEAD_BLACK"},
    )

    inserted = [
        note
        for note in corrected.findall(".//measure/note")
        if (note.get("id") or "").startswith("st__n-s1-g7")
    ][0]
    assert inserted.findtext("duration") == "6"
    assert inserted.findtext("type") == "quarter"


def test_chord_member_type_updates_chord_to_selected_candidate() -> None:
    """候选时值与和弦头不同时，简谱应体现用户选择的候选时值。"""
    corrected = _apply_chord_case(
        _CHORD_XML,
        {
            "n-s1-i1": _head_at("n-s1-i1", x=100, pitch=0.0),
            "n-s1-i2": _head_at("n-s1-i2", x=200, pitch=4.0),
        },
        {"s1:g7": _glyph_at("s1:g7", x=100, pitch=-2.0, shape="NOTEHEAD_VOID")},
        {"s1:g7": "NOTEHEAD_VOID"},
    )

    inserted = [
        note
        for note in corrected.findall(".//measure/note")
        if (note.get("id") or "").startswith("st__n-s1-g7")
    ][0]
    assert inserted.find("chord") is not None
    assert inserted.findtext("type") == "half"
    assert inserted.findtext("duration") == "8"
    assert corrected.findtext(".//measure/note/type") == "half"
    assert corrected.findtext(".//measure/note/duration") == "8"


def test_duplicate_pitch_member_is_skipped() -> None:
    """同列已有相同音高时不再重复插入成员。"""
    corrected = _apply_chord_case(
        _CHORD_XML,
        {
            "n-s1-i1": _head_at("n-s1-i1", x=100, pitch=0.0),
            "n-s1-i2": _head_at("n-s1-i2", x=200, pitch=4.0),
        },
        {
            "s1:g7": _glyph_at(
                "s1:g7", x=100, pitch=0.0, part_id="P1", measure_number="1"
            )
        },
        {"s1:g7": "NOTEHEAD_BLACK"},
    )

    notes = corrected.findall(".//measure/note")
    assert len(notes) == 2
    assert all(not (note.get("id") or "").startswith("st__n-s1-g7") for note in notes)


def test_rest_glyph_never_becomes_chord_member() -> None:
    """休止符不能进和弦组，插到组首之前。"""
    corrected = _apply_chord_case(
        _CHORD_XML,
        {
            "n-s1-i1": _head_at("n-s1-i1", x=100, pitch=0.0),
            "n-s1-i2": _head_at("n-s1-i2", x=200, pitch=4.0),
        },
        {
            "s1:g7": _glyph_at(
                "s1:g7", x=100, pitch=0.0, shape="EIGHTH_REST", tag="rest"
            )
        },
        {"s1:g7": "EIGHTH_REST"},
    )

    notes = corrected.findall(".//measure/note")
    inserted = [
        note for note in notes if (note.get("id") or "").startswith("st__n-s1-g7")
    ][0]
    assert inserted.find("chord") is None
    assert inserted.find("rest") is not None
    assert notes.index(inserted) == 0


def test_unexported_head_merges_into_same_column_chord() -> None:
    """未写入 MusicXML 的已识别 head 也走同一套和弦合并逻辑。"""
    corrected = _apply_chord_case(
        _CHORD_XML,
        {
            "n-s1-i1": _head_at("n-s1-i1", x=100, pitch=0.0),
            "n-s1-i2": _head_at("n-s1-i2", x=200, pitch=4.0),
            "s1:i99": _head_at("s1:i99", x=100, pitch=-2.0),
        },
        {},
        {"s1:i99": "NOTEHEAD_BLACK"},
    )

    notes = corrected.findall(".//measure/note")
    inserted = [
        note for note in notes if (note.get("id") or "").startswith("st__n-s1-i99")
    ][0]
    assert inserted.find("chord") is not None
    assert notes.index(inserted) == 1


def _all_missing_chord_fixture() -> tuple[
    str, dict[str, CorrectableEntity], dict[str, CorrectableGlyph]
]:
    xml = """<score-partwise><part id="P1">
      <measure number="27"><attributes><divisions>4</divisions><measure-style><multiple-rest>6</multiple-rest></measure-style></attributes>
        <note print-object="no"><rest measure="yes"/><duration>8</duration></note></measure>
      <measure number="28"><note print-object="no"><rest measure="yes"/><duration>8</duration></note></measure>
      <measure number="29"><note print-object="no"><rest measure="yes"/><duration>8</duration></note></measure>
      <measure number="30"><note print-object="no"><rest measure="yes"/><duration>8</duration></note></measure>
      <measure number="31"><note print-object="no"><rest measure="yes"/><duration>8</duration></note></measure>
      <measure number="32"><note print-object="no"><rest measure="yes"/><duration>8</duration></note></measure>
      <measure number="33"><attributes><divisions>4</divisions></attributes>
        <note id="n-s1-i1"><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration><voice>2</voice><type>quarter</type><staff>1</staff></note></measure>
    </part></score-partwise>"""
    reference = replace(
        _head_at("n-s1-i1", x=500, pitch=0.0),
        staff="1",
        part_id="P1",
        measure_number="33",
    )
    glyphs = {
        f"s1:g{index}": _glyph_at(
            f"s1:g{index}",
            x=100 + (1 if index % 2 else 0),
            pitch=pitch,
            part_id="P1",
            measure_number="27",
        )
        for index, pitch in enumerate((4.0, 0.0, -2.0, -6.0), start=1)
    }
    return xml, {reference.source_id: reference}, glyphs


def test_all_missing_same_column_notes_form_one_chord_in_located_measure() -> None:
    xml, entities, glyphs = _all_missing_chord_fixture()
    selections = {glyph_id: "NOTEHEAD_BLACK" for glyph_id in reversed(glyphs)}
    corrected = apply_candidate_selections(xml, selections, entities, glyphs)
    root = ET.fromstring(corrected)

    target = root.find(".//part[@id='P1']/measure[@number='27']")
    assert target is not None
    notes = target.findall("note")
    assert len(notes) == 4
    assert [note.find("chord") is not None for note in notes] == [
        False,
        True,
        True,
        True,
    ]
    assert {note.findtext("voice") for note in notes} == {"1"}
    assert len({note.findtext("duration") for note in notes}) == 1
    assert target.find("note[@print-object='no']") is None
    assert target.findtext("attributes/measure-style/multiple-rest") is None
    assert (
        root.findtext(".//measure[@number='28']/attributes/measure-style/multiple-rest")
        == "5"
    )
    assert len(root.findall(".//measure[@number='33']/note")) == 1
    assert any(
        line.startswith("[") for line in musicxml_to_jianpu(corrected).splitlines()
    )


def test_all_missing_groups_stay_independent_and_order_is_stable() -> None:
    xml, entities, glyphs = _all_missing_chord_fixture()
    glyphs["s1:g2"] = replace(glyphs["s1:g2"], bounds=(200, 24, 12, 10))
    glyphs["s1:g4"] = replace(glyphs["s1:g4"], bounds=(201, 24, 12, 10))
    first = apply_candidate_selections(
        xml, {key: "NOTEHEAD_BLACK" for key in glyphs}, entities, glyphs
    )
    second = apply_candidate_selections(
        xml, {key: "NOTEHEAD_BLACK" for key in reversed(glyphs)}, entities, glyphs
    )
    assert musicxml_to_jianpu(first) == musicxml_to_jianpu(second)
    for corrected in (first, second):
        target = ET.fromstring(corrected).find(".//measure[@number='27']")
        assert target is not None
        notes = target.findall("note")
        assert len(notes) == 4
        assert [note.find("chord") is not None for note in notes] == [
            False,
            True,
            False,
            True,
        ]


def test_located_duplicate_pitch_is_not_written_or_reported_as_applied() -> None:
    xml, entities, glyphs = _all_missing_chord_fixture()
    glyphs["s1:g2"] = replace(glyphs["s1:g2"], pitch=4.0)
    applied: dict[str, str] = {}
    corrected = apply_candidate_selections(
        xml,
        {"s1:g1": "NOTEHEAD_BLACK", "s1:g2": "NOTEHEAD_BLACK"},
        entities,
        glyphs,
        applied_out=applied,
    )
    assert applied == {"s1:g1": "NOTEHEAD_BLACK"}
    assert len(ET.fromstring(corrected).findall(".//measure[@number='27']/note")) == 1


def test_located_new_onset_in_multivoice_measure_is_safely_skipped() -> None:
    xml = """<score-partwise><part id="P1"><measure number="1"><attributes><divisions>4</divisions></attributes>
      <note id="n-s1-i1"><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration><voice>1</voice><type>quarter</type><staff>1</staff></note>
      <backup><duration>4</duration></backup>
      <note id="n-s1-i2"><pitch><step>E</step><octave>4</octave></pitch><duration>4</duration><voice>2</voice><type>quarter</type><staff>1</staff></note>
    </measure></part></score-partwise>"""
    entities = {
        "n-s1-i1": replace(_head_at("n-s1-i1", x=100, pitch=0.0), staff="1"),
        "n-s1-i2": replace(_head_at("n-s1-i2", x=100, pitch=2.0), staff="1"),
    }
    glyph = _glyph_at("s1:g9", x=200, pitch=4.0, part_id="P1", measure_number="1")
    applied: dict[str, str] = {}
    corrected = apply_candidate_selections(
        xml,
        {"s1:g9": "NOTEHEAD_BLACK"},
        entities,
        {"s1:g9": glyph},
        applied_out=applied,
    )
    assert applied == {}
    assert len(ET.fromstring(corrected).findall(".//measure/note")) == 2
    assert "s1-g9" not in corrected


def test_new_chord_head_can_be_deleted_without_breaking_remaining_chord() -> None:
    xml, entities, glyphs = _all_missing_chord_fixture()
    corrected = apply_candidate_selections(
        xml, {key: "NOTEHEAD_BLACK" for key in glyphs}, entities, glyphs
    )
    root = ET.fromstring(corrected)
    first = root.find(".//measure[@number='27']/note")
    assert first is not None
    head_id = next(
        key for key in glyphs if first.get("id") == f"st__n-{key.replace(':', '-')}"
    )
    inserted_entity = replace(
        _head_at(head_id, x=100, pitch=glyphs[head_id].pitch or 0.0),
        musicxml_locator=f"n-{head_id.replace(':', '-')}",
        staff="1",
    )
    deleted = apply_deletions(
        corrected, [head_id], {**entities, head_id: inserted_entity}, glyphs
    )
    notes = ET.fromstring(deleted).findall(".//measure[@number='27']/note")
    assert len(notes) == 3
    assert [note.find("chord") is not None for note in notes] == [False, True, True]


def test_source_map_v3_measure_locator_is_loaded(tmp_path: Path) -> None:
    source = SourceMap(
        version=3,
        sheets=[
            SourceMapSheet(
                sheet_index=1,
                width=100,
                height=100,
                overlay_file="overlay.png",
            )
        ],
    )
    source.sheets[0].glyphs.append(
        SourceGlyph(
            glyph_id="s1:g1",
            bounds=BoundingBox(x=10, y=10, width=10, height=10),
            hit_path="M10 10h10v10z",
            suspicious=True,
            measure=SourceMeasureLocator(part_id="P1", number="27"),
        )
    )
    path = tmp_path / "score-link-map.json"
    path.write_text(source.model_dump_json(), encoding="utf-8")
    loaded = load_source_map(path)
    assert loaded.sheets[0].glyphs[0].measure == SourceMeasureLocator(
        part_id="P1", number="27"
    )


def test_legacy_independent_insert_without_measure_is_not_guessed() -> None:
    glyph = _glyph_at("s1:g7", x=300, pitch=0.0)
    applied: dict[str, str] = {}
    corrected = apply_candidate_selections(
        _CHORD_XML,
        {"s1:g7": "NOTEHEAD_BLACK"},
        {
            "n-s1-i1": _head_at("n-s1-i1", x=100, pitch=0.0),
            "n-s1-i2": _head_at("n-s1-i2", x=200, pitch=4.0),
        },
        {"s1:g7": glyph},
        applied_out=applied,
    )
    assert applied == {}
    assert "st__n-s1-g7" not in corrected
