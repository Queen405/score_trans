from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

import pytest

from score_trans.models.provenance.schemas import (
    BoundingBox,
    MusicXmlLocator,
    SourceElement,
    SourceMap,
    SourceMapSheet,
)
from score_trans.services.correct.clef_transform import transform_pitch
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


def test_clef_transform_accounts_for_octave_change() -> None:
    assert transform_pitch(
        "C", 0.0, 4, "G", 2, "G", 2, -1, 0
    ) == ("C", 0.0, 5)


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


def test_apply_deletions_rejects_unknown_or_ambiguous_locator() -> None:
    xml = '<score-partwise><part id="P1"><measure><attributes><key id="same"/></attributes></measure><measure><attributes><key id="same"/></attributes></measure></part></score-partwise>'
    with pytest.raises(ValueError, match="无法定位"):
        apply_deletions(xml, ["missing"], {})
    entity = _entity("key", "key", "same")
    with pytest.raises(ValueError, match="不唯一"):
        apply_deletions(xml, ["key"], {"key": entity})


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
