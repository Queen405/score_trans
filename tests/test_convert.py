import logging
import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path

from score_trans.domain.jianpu import jianpu_to_musicxml, parse_jianpu_score
from score_trans.domain.musicxml import (
    musicxml_to_score,
    musicxml_to_scores,
    score_to_jianpu_text,
)
from score_trans.domain.write.musicxml import scores_to_musicxml
from score_trans.models.score import (
    Event,
    JianpuEvent,
    JianpuPitch,
    JianpuScore,
    Measure,
    TextBlock,
)
from score_trans.dao.settings.settings_dao import SettingsDao
from score_trans.exec.convert.actions import ConvertActions
from score_trans.models.convert.schemas import MusicXmlToJianpuRequest
from score_trans.models.provenance.entities import JianpuDocument
from score_trans.models.settings.config import ToolConfig
from score_trans.services.files.file_service import FileService
from score_trans.services.files.upload_service import UploadService
from score_trans.services.settings.settings_service import SettingsService


class CapturingMusicXmlToJianpu:
    def __init__(self) -> None:
        self.image_path: Path | None = None

    def execute_document(self, musicxml_path: str | Path, **kwargs) -> JianpuDocument:
        self.image_path = kwargs.get("image_path")
        return JianpuDocument(text="1=C\n4/4\n1 |", anchors=[], text_hash="hash")


def test_convert_does_not_resolve_or_call_ocr_when_setting_is_disabled(
    tmp_path,
) -> None:
    uploads = UploadService(ToolConfig(work_dir=tmp_path / "work"))
    musicxml_path = tmp_path / "score.musicxml"
    musicxml_path.write_text("<score-partwise/>", encoding="utf-8")
    image_path = tmp_path / "score.png"
    image_path.write_bytes(b"png")
    musicxml_id = uploads.register(musicxml_path)
    image_id = uploads.register(image_path)
    dao = SettingsDao(tmp_path / "settings.db", defaults={"enable_omr_ocr": "0"})
    converter = CapturingMusicXmlToJianpu()
    actions = ConvertActions(
        uploads=uploads,
        file_service=FileService(),
        musicxml_to_jianpu=converter,
        settings=SettingsService(dao),
    )

    response = actions.musicxml_to_jianpu_response(
        MusicXmlToJianpuRequest(
            musicxml_file_id=musicxml_id,
            page_image_file_id=image_id,
        )
    )

    assert response.jianpu_text == "1=C\n4/4\n1 |"
    assert converter.image_path is None


def test_convert_skips_pdf_ocr_input_even_when_setting_is_enabled(tmp_path) -> None:
    uploads = UploadService(ToolConfig(work_dir=tmp_path / "work"))
    musicxml_path = tmp_path / "score.musicxml"
    musicxml_path.write_text("<score-partwise/>", encoding="utf-8")
    pdf_path = tmp_path / "score.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")
    musicxml_id = uploads.register(musicxml_path)
    pdf_id = uploads.register(pdf_path)
    dao = SettingsDao(tmp_path / "settings.db", defaults={"enable_omr_ocr": "1"})
    converter = CapturingMusicXmlToJianpu()
    actions = ConvertActions(
        uploads=uploads,
        file_service=FileService(),
        musicxml_to_jianpu=converter,
        settings=SettingsService(dao),
    )

    actions.musicxml_to_jianpu_response(
        MusicXmlToJianpuRequest(
            musicxml_file_id=musicxml_id,
            page_image_file_id=pdf_id,
        )
    )

    assert converter.image_path is None


def test_musicxml_preserves_double_accidentals_and_sharp_key_spelling() -> None:
    xml = """
    <score-partwise version="4.0">
      <part-list><score-part id="P1"><part-name>Music</part-name></score-part></part-list>
      <part id="P1"><measure number="1">
        <attributes>
          <divisions>1</divisions><key><fifths>0</fifths></key>
          <time><beats>4</beats><beat-type>4</beat-type></time>
        </attributes>
        <note><pitch><step>C</step><alter>2</alter><octave>4</octave></pitch>
          <duration>1</duration><type>quarter</type><accidental>double-sharp</accidental></note>
        <note><pitch><step>B</step><alter>-2</alter><octave>4</octave></pitch>
          <duration>1</duration><type>quarter</type><accidental>double-flat</accidental></note>
        <note><pitch><step>D</step><alter>1</alter><octave>4</octave></pitch>
          <duration>1</duration><type>quarter</type><accidental>sharp</accidental></note>
        <note><rest/><duration>1</duration><type>quarter</type></note>
      </measure></part>
    </score-partwise>
    """

    c_score = musicxml_to_score(xml, target_key="C")
    d_score = musicxml_to_score(xml, target_key="D")

    assert [
        (pitch.degree, pitch.accidental)
        for event in c_score.measures[0].events[:2]
        for pitch in event.pitches
    ] == [(1, 2), (7, -2)]
    assert "x1 bb7" in score_to_jianpu_text(c_score)
    assert d_score.measures[0].events[2].pitches[0].degree == 1
    assert d_score.measures[0].events[2].pitches[0].accidental == 1
    assert "#1" in score_to_jianpu_text(d_score)


def test_musicxml_beam_statuses_roundtrip_on_event() -> None:
    xml = """
    <score-partwise version="4.0">
      <part-list><score-part id="P1"><part-name>Music</part-name></score-part></part-list>
      <part id="P1"><measure number="1">
        <attributes>
          <divisions>1</divisions><key><fifths>0</fifths></key>
          <time><beats>4</beats><beat-type>4</beat-type></time>
        </attributes>
        <note><pitch><step>C</step><octave>4</octave></pitch>
          <duration>1</duration><type>eighth</type>
          <beam number="1">begin</beam>
          <beam number="2">forward-hook</beam>
        </note>
        <note><pitch><step>D</step><octave>4</octave></pitch>
          <duration>1</duration><type>eighth</type>
          <beam number="1">continue</beam>
          <beam number="2">backward-hook</beam>
        </note>
        <note><pitch><step>E</step><octave>4</octave></pitch>
          <duration>1</duration><type>eighth</type>
          <beam number="1">end</beam>
        </note>
      </measure></part>
    </score-partwise>
    """

    score = musicxml_to_score(xml)
    events = score.measures[0].events
    assert [(beam.number, beam.status) for beam in events[0].beams] == [
        ("1", "begin"),
        ("2", "forward-hook"),
    ]
    assert [(beam.number, beam.status) for beam in events[1].beams] == [
        ("1", "continue"),
        ("2", "backward-hook"),
    ]
    assert [(beam.number, beam.status) for beam in events[2].beams] == [("1", "end")]

    roundtrip = ET.fromstring(scores_to_musicxml([score]))
    assert [
        (beam.get("number"), beam.text) for beam in roundtrip.findall(".//note/beam")
    ] == [
        ("1", "begin"),
        ("2", "forward-hook"),
        ("1", "continue"),
        ("2", "backward-hook"),
        ("1", "end"),
    ]


def test_musicxml_preserves_multiple_lyric_verses() -> None:
    source = "1=C\n4/4\n1 2 3 4 | 5 6 7 1' |\nL: 春 q眠 | q0 q觉\nL2: 星 闪 | 月 光"
    xml = jianpu_to_musicxml(source)
    root = ET.fromstring(xml)
    first_note_lyrics = root.findall(".//measure[1]/note[1]/lyric")
    assert [lyric.get("number") for lyric in first_note_lyrics] == ["1", "2"]
    restored = musicxml_to_score(xml)
    assert restored.measures[0].events[0].lyrics == {1: "春", 2: "星"}
    assert any(
        block.role == "lyric" and block.text == "觉" and block.start == Fraction(1, 2)
        for block in restored.measures[1].text_blocks
    )


def test_writer_keeps_repeated_same_verse_lyrics_at_distinct_starts() -> None:
    score = JianpuScore(
        measures=[
            Measure(
                "1",
                duration=Fraction(4),
                events=[
                    Event(
                        kind="note",
                        duration=Fraction(1),
                        start=Fraction(start),
                        pitches=[JianpuPitch(1)],
                        lyrics={1: "啦"},
                    )
                    for start in range(3)
                ],
            )
        ]
    )

    text = score_to_jianpu_text(score)

    assert text.splitlines()[-1] == "L: 啦 啦 啦"


def test_jianpu_to_musicxml_preserves_accidental_direction_and_magnitude() -> None:
    xml = jianpu_to_musicxml("1=C\n4/4\nb2 #4 x1 bb7 |")
    root = ET.fromstring(xml)
    pitches = [
        (
            pitch.findtext("step"),
            int(pitch.findtext("alter") or 0),
            int(pitch.findtext("octave") or 0),
        )
        for pitch in root.findall(".//pitch")
    ]

    assert pitches == [
        ("D", -1, 4),
        ("F", 1, 4),
        ("C", 2, 4),
        ("B", -2, 4),
    ]


def test_jianpu_to_musicxml_uses_correct_octave_across_key_scale_boundary() -> None:
    xml = jianpu_to_musicxml("1=D\n4/4\n1 7 1' 7, |")
    root = ET.fromstring(xml)

    assert [
        (pitch.findtext("step"), int(pitch.findtext("octave") or 0))
        for pitch in root.findall(".//pitch")
    ] == [("D", 4), ("C", 5), ("D", 5), ("C", 4)]


def test_musicxml_natural_cancelling_key_sharp_becomes_natural_jianpu_degree() -> None:
    xml = """
    <score-partwise version="4.0">
      <part-list><score-part id="P1"><part-name>Music</part-name></score-part></part-list>
      <part id="P1"><measure number="1">
        <attributes>
          <divisions>1</divisions><key><fifths>1</fifths></key>
          <time><beats>4</beats><beat-type>4</beat-type></time>
        </attributes>
        <note><pitch><step>F</step><octave>5</octave></pitch>
          <duration>4</duration><type>whole</type><accidental>natural</accidental></note>
      </measure></part>
    </score-partwise>
    """

    score = musicxml_to_score(xml, target_key="G")
    pitch = score.measures[0].events[0].pitches[0]
    roundtrip = ET.fromstring(scores_to_musicxml([score]))

    assert (pitch.degree, pitch.accidental, pitch.octave) == (7, -1, 0)
    assert "n7" in score_to_jianpu_text(score)
    assert roundtrip.findtext(".//pitch/step") == "F"
    assert roundtrip.find(".//pitch/alter") is None
    assert roundtrip.findtext(".//pitch/octave") == "5"


def test_jianpu_natural_cancels_target_key_signature_on_export() -> None:
    root = ET.fromstring(jianpu_to_musicxml("1=G\n4/4\nn7 |"))

    assert root.findtext(".//pitch/step") == "F"
    assert root.find(".//pitch/alter") is None
    assert root.findtext(".//accidental") == "natural"


def test_musicxml_repeat_endings_and_print_breaks_roundtrip() -> None:
    xml = """
    <score-partwise version="4.0">
      <part-list><score-part id="P1"><part-name>Music</part-name></score-part></part-list>
      <part id="P1">
        <measure number="1">
          <attributes>
            <divisions>1</divisions><key><fifths>0</fifths></key>
            <time><beats>4</beats><beat-type>4</beat-type></time>
          </attributes>
          <barline location="left">
            <ending number="1" type="start"/>
            <repeat direction="forward"/>
          </barline>
          <note><rest/><duration>4</duration><type>whole</type></note>
        </measure>
        <measure number="2">
          <print new-page="yes" new-system="yes"/>
          <note><rest/><duration>4</duration><type>whole</type></note>
          <barline location="right">
            <ending number="1" type="stop"/>
            <repeat direction="backward" times="3"/>
          </barline>
        </measure>
      </part>
    </score-partwise>
    """

    score = musicxml_to_score(xml)
    first, second = score.measures
    roundtrip = ET.fromstring(scores_to_musicxml([score]))
    barlines = roundtrip.findall(".//barline")

    assert first.repeat_start is True
    assert first.ending_start == "1"
    assert second.repeat_end is True
    assert second.repeat_count == 3
    assert second.ending_stop == "1"
    assert second.new_page is True
    assert second.new_system is True
    assert barlines[0].get("location") == "left"
    assert barlines[0].find("repeat").get("direction") == "forward"
    assert barlines[0].find("ending").attrib == {"number": "1", "type": "start"}
    assert barlines[1].get("location") == "right"
    assert barlines[1].find("repeat").attrib == {
        "direction": "backward",
        "times": "3",
    }
    assert barlines[1].find("ending").attrib == {"number": "1", "type": "stop"}
    assert roundtrip.find(".//measure[@number='2']/print").attrib == {
        "new-page": "yes",
        "new-system": "yes",
    }


def test_jianpu_repeat_flags_write_musicxml_repeats() -> None:
    root = ET.fromstring(jianpu_to_musicxml("1=C\n4/4\n|: 1 2 3 4 :|"))
    repeats = [repeat.attrib for repeat in root.findall(".//barline/repeat")]

    assert repeats == [{"direction": "forward"}, {"direction": "backward"}]


def test_musicxml_same_number_nested_tuplets_keep_both_spans() -> None:
    def note(notations: str) -> str:
        return (
            "<note><pitch><step>C</step><octave>4</octave></pitch>"
            "<duration>1</duration><type>quarter</type>"
            "<time-modification><actual-notes>3</actual-notes>"
            "<normal-notes>2</normal-notes></time-modification>"
            f"<notations>{notations}</notations></note>"
        )

    xml = f"""
    <score-partwise version="4.0">
      <part-list><score-part id="P1"><part-name>Music</part-name></score-part></part-list>
      <part id="P1"><measure number="1">
        <attributes>
          <divisions>1</divisions><key><fifths>0</fifths></key>
          <time><beats>4</beats><beat-type>4</beat-type></time>
        </attributes>
        {note('<tuplet number="1" type="start"/>')}
        {note('<tuplet number="1" type="start"/>')}
        {note('<tuplet number="1" type="stop"/>')}
        {note('<tuplet number="1" type="stop"/>')}
      </measure></part>
    </score-partwise>
    """

    score = musicxml_to_score(xml)
    events = [event for event in score.measures[0].events if not event.generated]
    span_ids = [[span.id for span in event.tuplet_spans] for event in events]
    jianpu_text = score_to_jianpu_text(score)
    roundtrip = ET.fromstring(scores_to_musicxml([score]))

    assert [len(ids) for ids in span_ids] == [1, 2, 2, 1]
    assert span_ids[0][0] == span_ids[1][0] == span_ids[2][0] == span_ids[3][0]
    assert span_ids[1][1] == span_ids[2][1]
    assert span_ids[0][0] != span_ids[1][1]
    # The outer group spans a sub-beat total (3 eighths-triplet worth of sounding
    # time), which jianpu text cannot express; it degrades to plain tokens.
    assert "$" not in jianpu_text.splitlines()[-1]
    assert musicxml_to_score(jianpu_to_musicxml(jianpu_text)).measures
    assert [tuplet.attrib for tuplet in roundtrip.findall(".//notations/tuplet")] == [
        {"type": "start", "number": "1"},
        {"type": "start", "number": "1"},
        {"type": "stop", "number": "1"},
        {"type": "stop", "number": "1"},
    ]


def test_musicxml_tuplet_state_continues_across_measures() -> None:
    xml = """
    <score-partwise version="4.0">
      <part-list><score-part id="P1"><part-name>Music</part-name></score-part></part-list>
      <part id="P1">
        <measure number="1">
          <attributes>
            <divisions>1</divisions><key><fifths>0</fifths></key>
            <time><beats>4</beats><beat-type>4</beat-type></time>
          </attributes>
          <note><rest/><duration>4</duration><type>whole</type>
            <time-modification><actual-notes>3</actual-notes><normal-notes>2</normal-notes></time-modification>
            <notations><tuplet number="1" type="start"/></notations></note>
        </measure>
        <measure number="2">
          <note><rest/><duration>4</duration><type>whole</type>
            <time-modification><actual-notes>3</actual-notes><normal-notes>2</normal-notes></time-modification>
            <notations><tuplet number="1" type="stop"/></notations></note>
        </measure>
      </part>
    </score-partwise>
    """

    score = musicxml_to_score(xml)
    first = score.measures[0].events[0]
    second = score.measures[1].events[0]

    assert first.tuplet_spans[0].id == second.tuplet_spans[0].id
    assert first.tuplet_spans[0].start is True
    assert second.tuplet_spans[0].stop is True


def test_stale_tuplet_span_does_not_hide_later_explicit_tuplet_boundaries() -> None:
    xml = """
    <score-partwise version="4.0">
      <part-list><score-part id="P1"><part-name>Music</part-name></score-part></part-list>
      <part id="P1">
        <measure number="1">
          <attributes>
            <divisions>3</divisions><key><fifths>0</fifths></key>
            <time><beats>4</beats><beat-type>4</beat-type></time>
          </attributes>
          <note><rest/><duration>3</duration>
            <time-modification><actual-notes>3</actual-notes><normal-notes>2</normal-notes></time-modification>
            <notations><tuplet number="1" type="start"/></notations></note>
        </measure>
        <measure number="2">
          <note><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration>
            <time-modification><actual-notes>3</actual-notes><normal-notes>2</normal-notes></time-modification>
            <notations><tuplet number="2" type="start"/></notations></note>
          <note><pitch><step>D</step><octave>4</octave></pitch><duration>1</duration>
            <time-modification><actual-notes>3</actual-notes><normal-notes>2</normal-notes></time-modification></note>
          <note><pitch><step>E</step><octave>4</octave></pitch><duration>1</duration>
            <time-modification><actual-notes>3</actual-notes><normal-notes>2</normal-notes></time-modification>
            <notations><tuplet number="2" type="stop"/></notations></note>
        </measure>
      </part>
    </score-partwise>
    """

    score = musicxml_to_score(xml)
    second_measure = score.measures[1]

    assert second_measure.events[0].tuplet_start is True
    assert second_measure.events[2].tuplet_stop is True
    assert "$" in score_to_jianpu_text(score).splitlines()[-1]


def test_musicxml_orphan_time_modified_tuplet_degrades_to_plain_tokens() -> None:
    # An orphan sub-beat tuplet (only 2 of 3 notes, total < 1 beat) cannot be
    # expressed as $...$ or an integer-normal ratio; the writer degrades it to
    # plain tokens (lossy) and logs a non-fatal warning instead of crashing.
    xml = """
    <score-partwise version="4.0">
      <part-list><score-part id="P1"><part-name>Music</part-name></score-part></part-list>
      <part id="P1"><measure number="1">
        <attributes>
          <divisions>24</divisions><key><fifths>0</fifths></key>
          <time><beats>1</beats><beat-type>12</beat-type></time>
        </attributes>
        <note>
          <pitch><step>C</step><octave>4</octave></pitch>
          <duration>4</duration><type>16th</type>
          <time-modification>
            <actual-notes>3</actual-notes><normal-notes>2</normal-notes>
          </time-modification>
          <beam number="1">begin</beam><beam number="2">begin</beam>
        </note>
        <note>
          <pitch><step>D</step><octave>4</octave></pitch>
          <duration>4</duration><type>16th</type>
          <time-modification>
            <actual-notes>3</actual-notes><normal-notes>2</normal-notes>
          </time-modification>
          <notations><tuplet number="1" type="stop"/></notations>
          <beam number="1">end</beam><beam number="2">end</beam>
        </note>
      </measure></part>
    </score-partwise>
    """

    score = musicxml_to_score(xml)
    events = score.measures[0].events

    # Recovery still detects the orphan tuplet on the score model.
    assert [event.duration for event in events] == [Fraction(1, 6)] * 2
    assert [event.tuplet_count for event in events] == [3, 3]
    assert [event.tuplet_normal_count for event in events] == [2, 2]
    assert events[0].tuplet_start is True
    assert events[1].tuplet_stop is True

    # The text degrades: no $...$ wrapper, plain tokens instead.
    text = score_to_jianpu_text(score)
    assert "$" not in text.splitlines()[-1]
    assert "s1 s2" in text


def test_musicxml_duplet_with_notated_duration_corrects_to_sounded() -> None:
    xml = """
    <score-partwise version="4.0">
      <part-list><score-part id="P1"><part-name>Music</part-name></score-part></part-list>
      <part id="P1"><measure number="1">
        <attributes>
          <divisions>6</divisions><key><fifths>0</fifths></key>
          <time><beats>3</beats><beat-type>4</beat-type></time>
        </attributes>
        <note>
          <pitch><step>C</step><octave>4</octave></pitch>
          <duration>6</duration><type>quarter</type>
          <time-modification>
            <actual-notes>2</actual-notes><normal-notes>3</normal-notes>
          </time-modification>
          <notations><tuplet number="1" type="start"/></notations>
        </note>
        <note>
          <pitch><step>D</step><octave>4</octave></pitch>
          <duration>6</duration><type>quarter</type>
          <time-modification>
            <actual-notes>2</actual-notes><normal-notes>3</normal-notes>
          </time-modification>
          <notations><tuplet number="1" type="stop"/></notations>
        </note>
      </measure></part>
    </score-partwise>
    """

    score = musicxml_to_score(xml)
    events = score.measures[0].events

    assert events[0].duration == Fraction(3, 2)
    assert events[1].duration == Fraction(3, 2)
    assert events[0].tuplet_count == 2
    assert events[0].tuplet_normal_count == 3

    text = score_to_jianpu_text(score)
    assert "$2:3;" in text

    reparsed = parse_jianpu_score(text)
    assert [event.duration for event in reparsed.measures[0].events] == [
        Fraction(3, 2),
        Fraction(3, 2),
    ]


def test_musicxml_tuplet_corrects_unscaled_quarter_durations_without_dots() -> None:
    def note(step: str, tuplet_type: str | None = None) -> str:
        notations = (
            f'<notations><tuplet number="1" type="{tuplet_type}"/></notations>'
            if tuplet_type
            else ""
        )
        return (
            f"<note><pitch><step>{step}</step><octave>4</octave></pitch>"
            "<duration>1</duration><type>quarter</type>"
            "<time-modification><actual-notes>3</actual-notes>"
            "<normal-notes>2</normal-notes></time-modification>"
            f"{notations}</note>"
        )

    xml = f"""
    <score-partwise version="4.0">
      <part-list><score-part id="P1"><part-name>Music</part-name></score-part></part-list>
      <part id="P1"><measure number="1">
        <attributes>
          <divisions>1</divisions><key><fifths>0</fifths></key>
          <time><beats>2</beats><beat-type>4</beat-type></time>
        </attributes>
        {note("C", "start")}{note("D")}{note("E", "stop")}
      </measure></part>
    </score-partwise>
    """

    score = musicxml_to_score(xml)
    text = score_to_jianpu_text(score)

    assert [event.duration for event in score.measures[0].events] == [
        Fraction(2, 3),
        Fraction(2, 3),
        Fraction(2, 3),
    ]
    assert "$3:2;123$" in text
    assert "." not in text.splitlines()[-1]


def test_musicxml_non_notatable_duration_without_tuplet_does_not_crash() -> None:
    xml = """
    <score-partwise version="4.0">
      <part-list><score-part id="P1"><part-name>Music</part-name></score-part></part-list>
      <part id="P1"><measure number="1">
        <attributes>
          <divisions>6</divisions><key><fifths>0</fifths></key>
          <time><beats>4</beats><beat-type>4</beat-type></time>
        </attributes>
        <note>
          <pitch><step>C</step><octave>4</octave></pitch>
          <duration>4</duration><type>eighth</type>
        </note>
        <note>
          <pitch><step>D</step><octave>4</octave></pitch>
          <duration>4</duration><type>eighth</type>
        </note>
      </measure></part>
    </score-partwise>
    """

    score = musicxml_to_score(xml)
    events = score.measures[0].events

    assert events[0].duration == Fraction(2, 3)
    assert events[1].duration == Fraction(2, 3)

    text = score_to_jianpu_text(score)
    assert "1" in text
    assert "2" in text


def test_musicxml_non_notatable_duration_in_tuplet_does_not_crash() -> None:
    xml = """
    <score-partwise version="4.0">
      <part-list><score-part id="P1"><part-name>Music</part-name></score-part></part-list>
      <part id="P1"><measure number="1">
        <attributes>
          <divisions>6</divisions><key><fifths>0</fifths></key>
          <time><beats>4</beats><beat-type>4</beat-type></time>
        </attributes>
        <note>
          <pitch><step>C</step><octave>4</octave></pitch>
          <duration>4</duration><type>eighth</type>
          <time-modification>
            <actual-notes>2</actual-notes><normal-notes>3</normal-notes>
          </time-modification>
          <notations><tuplet number="1" type="start"/></notations>
        </note>
        <note>
          <pitch><step>D</step><octave>4</octave></pitch>
          <duration>4</duration><type>eighth</type>
          <time-modification>
            <actual-notes>2</actual-notes><normal-notes>3</normal-notes>
          </time-modification>
          <notations><tuplet number="1" type="stop"/></notations>
        </note>
      </measure></part>
    </score-partwise>
    """

    score = musicxml_to_score(xml)
    events = score.measures[0].events

    assert events[0].duration == Fraction(2, 3)
    assert events[0].tuplet_count == 2
    assert events[0].tuplet_normal_count == 3

    text = score_to_jianpu_text(score)
    # 4/3-beat group: non-integer total, cannot be a $...$ ratio; degrades to
    # plain tokens without crashing.
    assert "$" not in text


def test_extended_musicxml_dynamic_roundtrips_through_jianpu_text() -> None:
    xml = """
    <score-partwise version="4.0">
      <part-list><score-part id="P1"><part-name>Music</part-name></score-part></part-list>
      <part id="P1"><measure number="1">
        <attributes>
          <divisions>1</divisions><key><fifths>0</fifths></key>
          <time><beats>4</beats><beat-type>4</beat-type></time>
        </attributes>
        <note><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration>
          <notations><dynamics><sf/></dynamics></notations></note>
      </measure></part>
    </score-partwise>
    """

    text = score_to_jianpu_text(musicxml_to_score(xml))
    reparsed = parse_jianpu_score(text)

    assert "\\sf" in text
    assert reparsed.measures[0].events[0].dynamic == "sf"


def test_jianpu_title_and_tempo_write_musicxml_metadata() -> None:
    root = ET.fromstring(
        jianpu_to_musicxml("title=春之歌\ntempo=96\n1=C\n4/4\n1 2 3 4 |")
    )

    assert root.findtext("./work/work-title") == "春之歌"
    assert root.findtext(".//direction-type/metronome/beat-unit") == "quarter"
    assert root.findtext(".//direction-type/metronome/per-minute") == "96"
    assert root.find(".//direction/sound").attrib == {"tempo": "96"}


def test_musicxml_measure_level_tempos_are_inherited_and_roundtrip() -> None:
    xml = """
    <score-partwise version="4.0">
      <part-list><score-part id="P1"><part-name>Music</part-name></score-part></part-list>
      <part id="P1">
        <measure number="1">
          <attributes><divisions>1</divisions><key><fifths>0</fifths></key>
            <time><beats>4</beats><beat-type>4</beat-type></time></attributes>
          <direction><direction-type><metronome><beat-unit>quarter</beat-unit>
            <per-minute>120</per-minute></metronome></direction-type><sound tempo="120"/></direction>
          <note><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration></note>
        </measure>
        <measure number="2">
          <direction><direction-type><metronome><beat-unit>quarter</beat-unit>
            <per-minute>80</per-minute></metronome></direction-type><sound tempo="80"/></direction>
          <note><pitch><step>D</step><octave>4</octave></pitch><duration>4</duration></note>
        </measure>
        <measure number="3">
          <note><pitch><step>E</step><octave>4</octave></pitch><duration>4</duration></note>
        </measure>
      </part>
    </score-partwise>
    """

    score = musicxml_to_score(xml)
    written = ET.fromstring(scores_to_musicxml([score]))
    reparsed = musicxml_to_score(ET.tostring(written, encoding="unicode"))

    assert score.tempo == 120
    assert [measure.tempo for measure in score.measures] == [120, 80, 80]
    assert [
        sound.attrib["tempo"] for sound in written.findall(".//direction/sound")
    ] == [
        "120",
        "80",
    ]
    assert [measure.tempo for measure in reparsed.measures] == [120, 80, 80]


def test_musicxml_without_tempo_keeps_header_implicit_but_measures_effective() -> None:
    xml = """
    <score-partwise version="4.0">
      <part-list><score-part id="P1"><part-name>Music</part-name></score-part></part-list>
      <part id="P1"><measure number="1">
        <attributes><divisions>1</divisions><time><beats>4</beats><beat-type>4</beat-type></time></attributes>
        <note><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration></note>
      </measure></part>
    </score-partwise>
    """

    score = musicxml_to_score(xml)
    text = score_to_jianpu_text(score)

    assert score.tempo is None
    assert score.measures[0].tempo == 120
    assert "tempo=" not in text


def test_jianpu_measure_level_tempo_writes_two_musicxml_tempo_events() -> None:
    root = ET.fromstring(
        jianpu_to_musicxml(
            "tempo=120\n1=C\n4/4\n1 2 3 4 |\ntempo=80\n5 6 7 1 |\n1 2 3 4 |"
        )
    )

    assert [sound.attrib["tempo"] for sound in root.findall(".//direction/sound")] == [
        "120",
        "80",
    ]


def test_multpart_musicxml_writes_the_tempo_map_only_in_the_first_part() -> None:
    text = (
        '// @part 1 name="A"\n'
        "tempo=120\n1=C\n4/4\n1 2 3 4 |\ntempo=80\n5 6 7 1 |\n"
        '// @part 2 name="B"\n'
        "1=C\n4/4\n1 2 3 4 |\n5 6 7 1 |"
    )

    root = ET.fromstring(jianpu_to_musicxml(text))
    parts = root.findall("./part")

    assert [sound.attrib["tempo"] for sound in parts[0].findall(".//sound")] == [
        "120",
        "80",
    ]
    assert parts[1].findall(".//sound") == []


def test_musicxml_writer_preserves_multiple_rhythm_dots() -> None:
    root = ET.fromstring(jianpu_to_musicxml("1=C\n4/4\n5.. q6.. 7... |"))
    notes = root.findall(".//note")

    assert [note.findtext("type") for note in notes] == [
        "quarter",
        "eighth",
        "quarter",
    ]
    assert [len(note.findall("dot")) for note in notes] == [2, 2, 3]


def test_musicxml_writer_preserves_direction_kinds_without_dynamic_duplicates() -> None:
    score = parse_jianpu_score("title=方向\ntempo=88\n1=C\n4/4\n1 2 3 4 |")
    measure = score.measures[0]
    measure.text_blocks.extend(
        [
            TextBlock(
                text="Allegro",
                role="expression",
                start=Fraction(0, 1),
                placement="above",
                direction_kind="words",
            ),
            TextBlock(
                text="A",
                role="expression",
                start=Fraction(1, 1),
                direction_kind="rehearsal",
            ),
            TextBlock(
                text="sf",
                role="expression",
                start=Fraction(2, 1),
                direction_kind="dynamics",
            ),
        ]
    )
    measure.events[2].dynamic = "sf"

    root = ET.fromstring(scores_to_musicxml([score]))

    assert root.findtext(".//direction-type/words") == "Allegro"
    assert root.findtext(".//direction-type/rehearsal") == "A"
    assert root.find(".//direction-type/dynamics/sf") is not None
    assert root.find(".//notations/dynamics/sf") is None


def test_musicxml_structural_directions_roundtrip_with_attributes() -> None:
    xml = """
    <score-partwise version="4.0">
      <part-list><score-part id="P1"><part-name>Music</part-name></score-part></part-list>
      <part id="P1"><measure number="1">
        <attributes>
          <divisions>1</divisions><key><fifths>0</fifths></key>
          <time><beats>4</beats><beat-type>4</beat-type></time>
        </attributes>
        <direction><direction-type>
          <wedge type="crescendo" number="2"/>
          <wedge type="stop" number="2"/>
          <pedal type="start" line="yes" number="3"/>
          <pedal type="stop" line="yes" number="3"/>
          <octave-shift type="down" size="15" number="4"/>
          <octave-shift type="stop" size="15" number="4"/>
        </direction-type></direction>
        <note><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration><type>whole</type></note>
      </measure></part>
    </score-partwise>
    """

    score = musicxml_to_score(xml)
    structural = [
        block
        for block in score.measures[0].text_blocks
        if block.direction_kind in {"wedge", "pedal", "octave-shift"}
    ]
    root = ET.fromstring(scores_to_musicxml([score]))

    assert [block.direction_kind for block in structural] == [
        "wedge",
        "wedge",
        "pedal",
        "pedal",
        "octave-shift",
        "octave-shift",
    ]
    assert [block.direction_attributes for block in structural] == [
        {"type": "crescendo", "number": "2"},
        {"type": "stop", "number": "2"},
        {"type": "start", "line": "yes", "number": "3"},
        {"type": "stop", "line": "yes", "number": "3"},
        {"type": "down", "size": "15", "number": "4"},
        {"type": "stop", "size": "15", "number": "4"},
    ]
    assert [element.attrib for element in root.findall(".//wedge")] == [
        {"type": "crescendo", "number": "2"},
        {"type": "stop", "number": "2"},
    ]
    assert [element.attrib for element in root.findall(".//pedal")] == [
        {"type": "start", "line": "yes", "number": "3"},
        {"type": "stop", "line": "yes", "number": "3"},
    ]
    assert [element.attrib for element in root.findall(".//octave-shift")] == [
        {"type": "down", "size": "15", "number": "4"},
        {"type": "stop", "size": "15", "number": "4"},
    ]
    assert root.findall(".//direction-type/words") == []


def test_musicxml_direction_metadata_roundtrips_with_tempo_and_title() -> None:
    xml = """
    <score-partwise version="4.0">
      <work><work-title>原题</work-title></work>
      <part-list><score-part id="P1"><part-name>Music</part-name></score-part></part-list>
      <part id="P1"><measure number="1">
        <attributes>
          <divisions>1</divisions><key><fifths>0</fifths></key>
          <time><beats>4</beats><beat-type>4</beat-type></time>
        </attributes>
        <direction placement="above">
          <direction-type><metronome><beat-unit>quarter</beat-unit><per-minute>108</per-minute></metronome></direction-type>
          <sound tempo="108"/>
        </direction>
        <direction placement="above"><direction-type><words>dolce</words></direction-type></direction>
        <direction><direction-type><rehearsal>B</rehearsal></direction-type></direction>
        <note><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration></note>
      </measure></part>
    </score-partwise>
    """

    score = musicxml_to_score(xml)
    roundtrip = ET.fromstring(scores_to_musicxml([score]))

    assert score.title == "原题"
    assert score.tempo == 108
    assert [block.direction_kind for block in score.measures[0].text_blocks] == [
        None,
        "metronome",
        "words",
        "rehearsal",
    ]
    assert score.measures[0].text_blocks[1].text == "♩=108"
    assert roundtrip.findtext("./work/work-title") == "原题"
    assert roundtrip.findtext(".//direction-type/metronome/beat-unit") == "quarter"
    assert roundtrip.findtext(".//direction-type/words") == "dolce"
    assert roundtrip.findtext(".//direction-type/rehearsal") == "B"
    assert roundtrip.find(".//direction/sound").attrib == {"tempo": "108"}


def test_musicxml_writer_preserves_multivoice_timeline_with_backup_and_forward() -> (
    None
):
    score = parse_jianpu_score("1=C\n4/4\n1 2 3 4 |")
    measure = score.measures[0]
    first, second, third, fourth = measure.events
    first.duration = Fraction(2, 1)
    first.start = Fraction(0, 1)
    first.voice = "1"
    second.duration = Fraction(2, 1)
    second.start = Fraction(2, 1)
    second.voice = "1"
    third.start = Fraction(0, 1)
    third.voice = "2"
    fourth.start = Fraction(2, 1)
    fourth.voice = "2"
    measure.events = [first, third, second, fourth]
    measure.text_blocks.append(
        TextBlock(
            text="dolce",
            role="expression",
            start=Fraction(1, 1),
            direction_kind="words",
        )
    )

    xml = scores_to_musicxml([score])
    root = ET.fromstring(xml)
    restored = musicxml_to_score(xml)
    restored_events = [
        event for event in restored.measures[0].events if not event.generated
    ]

    assert [note.findtext("voice") for note in root.findall(".//note")] == [
        "1",
        "1",
        "2",
        "2",
    ]
    assert root.find(".//backup") is not None
    assert root.find(".//forward") is not None
    assert [
        (event.voice, event.start, event.duration) for event in restored_events
    ] == [
        ("1", Fraction(0, 1), Fraction(2, 1)),
        ("1", Fraction(2, 1), Fraction(2, 1)),
        ("2", Fraction(0, 1), Fraction(1, 1)),
        ("2", Fraction(2, 1), Fraction(1, 1)),
    ]
    assert next(
        block for block in restored.measures[0].text_blocks if block.text == "dolce"
    ).start == Fraction(1, 1)


def test_musicxml_writer_keeps_single_voice_compatible_while_emitting_gaps() -> None:
    score = parse_jianpu_score("1=C\n4/4\n1 2 |")
    measure = score.measures[0]
    first, second = measure.events[:2]
    first.start = Fraction(0, 1)
    second.start = Fraction(2, 1)
    measure.events = [first, second]

    xml = scores_to_musicxml([score])
    root = ET.fromstring(xml)
    restored = musicxml_to_score(xml)

    assert root.findall(".//note/voice") == []
    assert root.findtext(".//forward/duration") == "8"
    assert [event.start for event in restored.measures[0].events[:2]] == [
        Fraction(0, 1),
        Fraction(2, 1),
    ]


def test_musicxml_microtonal_accidentals_roundtrip_without_quantization() -> None:
    xml = """
    <score-partwise version="4.0">
      <part-list><score-part id="P1"><part-name>Music</part-name></score-part></part-list>
      <part id="P1"><measure number="1">
        <attributes>
          <divisions>1</divisions><key><fifths>0</fifths></key>
          <time><beats>4</beats><beat-type>4</beat-type></time>
        </attributes>
        <note><pitch><step>C</step><alter>0.5</alter><octave>4</octave></pitch><duration>1</duration><accidental>quarter-sharp</accidental></note>
        <note><pitch><step>D</step><alter>-0.5</alter><octave>4</octave></pitch><duration>1</duration><accidental>quarter-flat</accidental></note>
        <note><pitch><step>E</step><alter>1.5</alter><octave>4</octave></pitch><duration>1</duration><accidental>three-quarters-sharp</accidental></note>
        <note><pitch><step>F</step><alter>-1.5</alter><octave>4</octave></pitch><duration>1</duration><accidental>three-quarters-flat</accidental></note>
      </measure></part>
    </score-partwise>
    """

    score = musicxml_to_score(xml)
    pitches = [event.pitches[0] for event in score.measures[0].events]
    text = score_to_jianpu_text(score)
    reparsed = parse_jianpu_score(text)
    roundtrip = ET.fromstring(scores_to_musicxml([reparsed]))

    assert [pitch.alter for pitch in pitches] == [
        Fraction(1, 2),
        Fraction(-1, 2),
        Fraction(3, 2),
        Fraction(-3, 2),
    ]
    assert [pitch.accidental_text for pitch in pitches] == [
        "qs",
        "qf",
        "tqs",
        "tqf",
    ]
    assert ["qs1", "qf2", "tqs3", "tqf4"] == text.splitlines()[-1].split()[:4]
    assert [event.pitches[0].accidental for event in reparsed.measures[0].events] == [
        Fraction(1, 2),
        Fraction(-1, 2),
        Fraction(3, 2),
        Fraction(-3, 2),
    ]
    assert [element.text for element in roundtrip.findall(".//pitch/alter")] == [
        "0.5",
        "-0.5",
        "1.5",
        "-1.5",
    ]
    assert [element.text for element in roundtrip.findall(".//accidental")] == [
        "quarter-sharp",
        "quarter-flat",
        "three-quarters-sharp",
        "three-quarters-flat",
    ]


def test_musicxml_to_score_marks_incomplete_measure() -> None:
    xml = jianpu_to_musicxml("1=C\n4/4\n1 2 |")

    measure = musicxml_to_score(xml).measures[0]

    assert all(event.generated is False for event in measure.events)
    assert measure.validation_errors
    assert "少拍" in measure.validation_errors[0]


def test_musicxml_to_score_can_transpose_target_key() -> None:
    xml = jianpu_to_musicxml("1=C\n4/4\n1 2 3 4 |")

    score = musicxml_to_score(xml, target_key="D")
    text = score_to_jianpu_text(score)

    assert "1=D" in text
    assert "n7, 1 2 n3" in text
    assert "n7, 1 2 n3" in score_to_jianpu_text(
        score,
        accidental_mode="sharp",
    )
    assert "n7, 1 2 n3" in score_to_jianpu_text(
        score,
        accidental_mode="flat",
    )


def test_model_exports_structured_ast_names_and_compat_aliases() -> None:
    event = Event(kind="rest", duration=1)

    assert JianpuEvent is Event
    assert isinstance(event, JianpuEvent)
    assert TextBlock(text="dolce").role == "other"


def test_musicxml_to_score_marks_overfull_measure() -> None:
    xml = jianpu_to_musicxml("1=C\n4/4\n1 2 3 4 5 |")

    measure = musicxml_to_score(xml).measures[0]

    assert measure.validation_errors
    assert "超拍" in measure.validation_errors[0]
    assert measure.events[-1].generated is False


def test_musicxml_ignores_duplicate_note_ids_within_measure() -> None:
    xml = """
    <score-partwise version="4.0">
      <part-list><score-part id="P1"><part-name>Music</part-name></score-part></part-list>
      <part id="P1"><measure number="1">
        <attributes>
          <divisions>1</divisions><key><fifths>0</fifths></key>
          <time><beats>4</beats><beat-type>4</beat-type></time>
        </attributes>
        <note id="n-1"><pitch><step>C</step><octave>4</octave></pitch>
          <duration>1</duration><voice>1</voice></note>
        <backup><duration>1</duration></backup>
        <note id="n-1"><pitch><step>C</step><octave>4</octave></pitch>
          <duration>1</duration><voice>2</voice></note>
      </measure></part>
    </score-partwise>
    """

    measure = musicxml_to_score(xml).measures[0]
    source_events = [event for event in measure.events if not event.generated]

    assert len(source_events) == 1
    assert source_events[0].pitches[0].midi == 60


def test_musicxml_multiple_rest_is_not_expanded_into_duplicate_measures() -> None:
    xml = """
    <score-partwise version="4.0">
      <part-list><score-part id="P1"><part-name>Music</part-name></score-part></part-list>
      <part id="P1">
        <measure number="1">
          <attributes>
            <divisions>1</divisions><key><fifths>0</fifths></key>
            <time><beats>4</beats><beat-type>4</beat-type></time>
            <measure-style><multiple-rest>3</multiple-rest></measure-style>
          </attributes>
          <note><rest measure="yes"/><duration>4</duration></note>
        </measure>
        <measure number="2"><note><rest measure="yes"/><duration>4</duration></note></measure>
        <measure number="3"><note><rest measure="yes"/><duration>4</duration></note></measure>
      </part>
    </score-partwise>
    """

    score = musicxml_to_score(xml)

    assert [measure.source_number for measure in score.measures] == ["1", "2", "3"]


def test_musicxml_measure_rest_uses_full_measure_duration() -> None:
    xml = """
    <score-partwise version="4.0">
      <part-list><score-part id="P1"><part-name>Music</part-name></score-part></part-list>
      <part id="P1"><measure number="1">
        <attributes>
          <divisions>1</divisions><key><fifths>0</fifths></key>
          <time><beats>4</beats><beat-type>4</beat-type></time>
        </attributes>
        <note><rest measure="yes"/><duration>1</duration></note>
      </measure></part>
    </score-partwise>
    """

    score = musicxml_to_score(xml)

    assert score.measures[0].events[0].duration == Fraction(4, 1)
    assert score_to_jianpu_text(score).splitlines()[-1] == "w0 |"


def test_writer_clamps_overlong_rest_to_current_measure_capacity() -> None:
    xml = """
    <score-partwise version="4.0">
      <part-list><score-part id="P1"><part-name>Music</part-name></score-part></part-list>
      <part id="P1"><measure number="1">
        <attributes>
          <divisions>1</divisions><key><fifths>0</fifths></key>
          <time><beats>4</beats><beat-type>4</beat-type></time>
        </attributes>
        <note><rest/><duration>12</duration><voice>2</voice></note>
      </measure></part>
    </score-partwise>
    """

    score = musicxml_to_score(xml)

    assert score_to_jianpu_text(score).splitlines()[-1] == "w0 |"


def test_writer_replaces_pitchless_note_with_parseable_rest() -> None:
    xml = """
    <score-partwise version="4.0">
      <part-list><score-part id="P1"><part-name>Music</part-name></score-part></part-list>
      <part id="P1"><measure number="1">
        <attributes>
          <divisions>1</divisions><key><fifths>0</fifths></key>
          <time><beats>4</beats><beat-type>4</beat-type></time>
        </attributes>
        <note><duration>1</duration></note>
      </measure></part>
    </score-partwise>
    """

    text = score_to_jianpu_text(musicxml_to_score(xml))

    assert "?" not in text
    assert "0" in text
    assert parse_jianpu_score(text).measures


def test_writer_drops_nonstandard_dynamic_instead_of_emitting_invalid_token() -> None:
    xml = """
    <score-partwise version="4.0">
      <part-list><score-part id="P1"><part-name>Music</part-name></score-part></part-list>
      <part id="P1"><measure number="1">
        <attributes>
          <divisions>1</divisions><key><fifths>0</fifths></key>
          <time><beats>4</beats><beat-type>4</beat-type></time>
        </attributes>
        <note><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration>
          <notations><dynamics><other-dynamics>molto</other-dynamics></dynamics></notations>
        </note>
      </measure></part>
    </score-partwise>
    """

    text = score_to_jianpu_text(musicxml_to_score(xml))

    assert "\\molto" not in text
    assert parse_jianpu_score(text).measures


def test_musicxml_standard_marks_roundtrip_through_jianpu_tokens() -> None:
    xml = """
    <score-partwise version="4.0">
      <part-list><score-part id="P1"><part-name>Music</part-name></score-part></part-list>
      <part id="P1"><measure number="1">
        <attributes>
          <divisions>1</divisions><key><fifths>0</fifths></key>
          <time><beats>4</beats><beat-type>4</beat-type></time>
        </attributes>
        <note><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration>
          <notations><articulations><staccatissimo/></articulations></notations></note>
        <note><pitch><step>D</step><octave>4</octave></pitch><duration>1</duration>
          <notations><ornaments><turn/></ornaments></notations></note>
        <note><pitch><step>E</step><octave>4</octave></pitch><duration>1</duration>
          <notations><ornaments><inverted-turn/></ornaments></notations></note>
      </measure></part>
    </score-partwise>
    """

    text = score_to_jianpu_text(musicxml_to_score(xml))

    assert "^! 1 ^t 2 ^t' 3" in text
    assert parse_jianpu_score(text).measures


def test_musicxml_to_score_preserves_non_numeric_measure_number() -> None:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="3.1">
  <part-list><score-part id="P1"><part-name>Music</part-name></score-part></part-list>
  <part id="P1">
    <measure number="A">
      <attributes>
        <divisions>1</divisions>
        <key><fifths>0</fifths></key>
        <time><beats>4</beats><beat-type>4</beat-type></time>
      </attributes>
      <note><rest/><duration>4</duration></note>
    </measure>
  </part>
</score-partwise>
"""

    measure = musicxml_to_score(xml).measures[0]

    assert measure.source_number == "A"
    assert measure.display_measure_number == "A"
    assert measure.display_number == "A"


def test_musicxml_auto_mode_follows_mid_piece_key_change(caplog) -> None:
    xml = """
    <score-partwise version="4.0">
      <part-list><score-part id="P1"><part-name>Music</part-name></score-part></part-list>
      <part id="P1">
        <measure number="1">
          <attributes>
            <divisions>1</divisions><key><fifths>1</fifths></key>
            <time><beats>4</beats><beat-type>4</beat-type></time>
          </attributes>
          <note><rest measure="yes"/><duration>4</duration></note>
        </measure>
        <measure number="2">
          <attributes><key><fifths>0</fifths></key></attributes>
          <note><rest measure="yes"/><duration>4</duration></note>
        </measure>
      </part>
    </score-partwise>
    """

    with caplog.at_level(logging.INFO):
        score = musicxml_to_scores(xml, target_key="auto")[0]

    assert [measure.source_key for measure in score.measures] == ["G", "C"]
    assert [measure.target_key for measure in score.measures] == ["G", "C"]
    assert "小节 2 跟随曲中转调：G -> C" in caplog.text


def test_musicxml_explicit_target_key_does_not_follow_modulation(caplog) -> None:
    xml = """
    <score-partwise version="4.0">
      <part-list><score-part id="P1"><part-name>Music</part-name></score-part></part-list>
      <part id="P1">
        <measure number="1">
          <attributes>
            <divisions>1</divisions><key><fifths>1</fifths></key>
            <time><beats>4</beats><beat-type>4</beat-type></time>
          </attributes>
          <note><rest measure="yes"/><duration>4</duration></note>
        </measure>
        <measure number="2">
          <attributes><key><fifths>0</fifths></key></attributes>
          <note><rest measure="yes"/><duration>4</duration></note>
        </measure>
      </part>
    </score-partwise>
    """

    score = musicxml_to_scores(xml, target_key="G")[0]

    assert [measure.source_key for measure in score.measures] == ["G", "C"]
    assert [measure.target_key for measure in score.measures] == ["G", "G"]
    assert "小节 2 检测到中途调号变化：G -> C；目标简谱调保持 G" in caplog.text


def test_musicxml_auto_modulation_recomputes_degrees_per_section() -> None:
    xml = """
    <score-partwise version="4.0">
      <part-list><score-part id="P1"><part-name>Music</part-name></score-part></part-list>
      <part id="P1">
        <measure number="1">
          <attributes><divisions>1</divisions><key><fifths>0</fifths></key><time><beats>4</beats><beat-type>4</beat-type></time></attributes>
          <note><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration><type>quarter</type></note>
          <note><pitch><step>D</step><octave>4</octave></pitch><duration>1</duration><type>quarter</type></note>
          <note><pitch><step>E</step><octave>4</octave></pitch><duration>1</duration><type>quarter</type></note>
          <note><pitch><step>G</step><octave>4</octave></pitch><duration>1</duration><type>quarter</type></note>
        </measure>
        <measure number="2">
          <attributes><key><fifths>1</fifths></key></attributes>
          <note><pitch><step>G</step><octave>4</octave></pitch><duration>1</duration><type>quarter</type></note>
          <note><pitch><step>A</step><octave>4</octave></pitch><duration>1</duration><type>quarter</type></note>
          <note><pitch><step>B</step><octave>4</octave></pitch><duration>1</duration><type>quarter</type></note>
        </measure>
      </part>
    </score-partwise>
    """

    score = musicxml_to_scores(xml, target_key="auto")[0]

    first_degrees = [p.degree for e in score.measures[0].events for p in e.pitches]
    second_degrees = [p.degree for e in score.measures[1].events for p in e.pitches]
    assert first_degrees == [1, 2, 3, 5]
    assert second_degrees == [1, 2, 3]

    text = score_to_jianpu_text(score)
    assert "1=C" in text.splitlines()[0]
    assert "1=G" in text


def test_musicxml_auto_modulation_combined_with_time_change() -> None:
    xml = """
    <score-partwise version="4.0">
      <part-list><score-part id="P1"><part-name>Music</part-name></score-part></part-list>
      <part id="P1">
        <measure number="1">
          <attributes><divisions>1</divisions><key><fifths>0</fifths></key><time><beats>4</beats><beat-type>4</beat-type></time></attributes>
          <note><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration><type>whole</type></note>
        </measure>
        <measure number="2">
          <attributes><key><fifths>1</fifths></key><time><beats>3</beats><beat-type>4</beat-type></time></attributes>
          <note><pitch><step>G</step><octave>4</octave></pitch><duration>3</duration><type>half</type><dot</note>
        </measure>
      </part>
    </score-partwise>
    """.replace("<dot</note>", "<dot/></note>")

    score = musicxml_to_scores(xml, target_key="auto")[0]

    assert score.measures[1].target_key == "G"
    assert score.measures[1].beats_per_measure == 3
    assert score.measures[1].beat_type == 4

    text = score_to_jianpu_text(score)
    assert "1=G 3/4" in text


def test_musicxml_auto_multi_section_modulation() -> None:
    xml = """
    <score-partwise version="4.0">
      <part-list><score-part id="P1"><part-name>Music</part-name></score-part></part-list>
      <part id="P1">
        <measure number="1">
          <attributes><divisions>1</divisions><key><fifths>0</fifths></key><time><beats>4</beats><beat-type>4</beat-type></time></attributes>
          <note><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration><type>whole</type></note>
        </measure>
        <measure number="2">
          <attributes><key><fifths>1</fifths></key></attributes>
          <note><pitch><step>G</step><octave>4</octave></pitch><duration>4</duration><type>whole</type></note>
        </measure>
        <measure number="3">
          <attributes><key><fifths>2</fifths></key></attributes>
          <note><pitch><step>D</step><octave>4</octave></pitch><duration>4</duration><type>whole</type></note>
        </measure>
      </part>
    </score-partwise>
    """

    score = musicxml_to_scores(xml, target_key="auto")[0]

    assert [m.target_key for m in score.measures] == ["C", "G", "D"]
    degrees = [p.degree for m in score.measures for e in m.events for p in e.pitches]
    assert degrees == [1, 1, 1]

    text = score_to_jianpu_text(score)
    markers = [ln.split()[0] for ln in text.splitlines() if ln.strip().startswith("1=")]
    assert markers == ["1=C", "1=G", "1=D"]


def test_musicxml_auto_no_modulation_unchanged() -> None:
    xml = """
    <score-partwise version="4.0">
      <part-list><score-part id="P1"><part-name>Music</part-name></score-part></part-list>
      <part id="P1">
        <measure number="1">
          <attributes><divisions>1</divisions><key><fifths>0</fifths></key><time><beats>4</beats><beat-type>4</beat-type></time></attributes>
          <note><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration><type>whole</type></note>
        </measure>
        <measure number="2">
          <note><pitch><step>D</step><octave>4</octave></pitch><duration>4</duration><type>whole</type></note>
        </measure>
      </part>
    </score-partwise>
    """

    score = musicxml_to_scores(xml, target_key="auto")[0]

    assert [m.target_key for m in score.measures] == ["C", "C"]
    text = score_to_jianpu_text(score)
    assert "1=G" not in text


def test_split_multi_staff_part_preserves_empty_measure_slots() -> None:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="4.0">
  <part-list><score-part id="P1"><part-name>Piano</part-name></score-part></part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>1</divisions>
        <time><beats>4</beats><beat-type>4</beat-type></time>
        <staves>2</staves>
      </attributes>
      <note id="st__n-s1-i10">
        <pitch><step>C</step><octave>4</octave></pitch>
        <duration>4</duration><staff>1</staff>
      </note>
    </measure>
    <measure number="2">
      <note id="st__n-s1-i11">
        <pitch><step>D</step><octave>4</octave></pitch>
        <duration>4</duration><staff>1</staff>
      </note>
      <backup><duration>4</duration></backup>
      <note id="st__n-s1-i20">
        <pitch><step>G</step><octave>3</octave></pitch>
        <duration>4</duration><staff>2</staff>
      </note>
    </measure>
  </part>
</score-partwise>
"""

    scores = musicxml_to_scores(xml)

    assert [
        [measure.source_number for measure in score.measures] for score in scores
    ] == [
        ["1", "2"],
        ["1", "2"],
    ]
    assert scores[1].measures[0].events[0].kind == "rest"
    assert scores[1].measures[0].events[0].generated is True
    assert scores[1].measures[1].events[0].source_ids == ["s1:i20"]


def test_same_cursor_dynamics_use_last_value_without_leaking_to_next_note() -> None:
    xml = """
    <score-partwise version="4.0">
      <part-list><score-part id="P1"><part-name>Music</part-name></score-part></part-list>
      <part id="P1"><measure number="1">
        <attributes>
          <divisions>1</divisions>
          <time><beats>4</beats><beat-type>4</beat-type></time>
        </attributes>
        <direction><direction-type><dynamics><p/></dynamics></direction-type></direction>
        <direction><direction-type><dynamics><f/></dynamics></direction-type></direction>
        <note><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration></note>
        <note><pitch><step>D</step><octave>4</octave></pitch><duration>1</duration></note>
      </measure></part>
    </score-partwise>
    """

    measure = musicxml_to_score(xml).measures[0]
    dynamic_blocks = [
        block for block in measure.text_blocks if block.direction_kind == "dynamics"
    ]

    assert [block.text for block in dynamic_blocks] == ["p", "f"]
    assert [event.dynamic for event in measure.events[:2]] == ["f", None]


def test_erhu_marks_and_profile_roundtrip_through_musicxml() -> None:
    source = (
        "instrument=erhu\n1=C\n4/4\n"
        "^lg (1 ^lh 2) ^tg ^pg 3 ^1 ^zr ^rg ^bx 4 |\n"
        "^sh 1 ^xh 2 ^dh 3 ^ds 4 |\n"
        "^dx 1 ^hx 2 ^hs 3 ^sc ^xc 4 |\n"
        "^kx 1 ^nx 2 ^wx 3 ^jx ^gx 4 |"
    )

    xml = jianpu_to_musicxml(source)
    restored = score_to_jianpu_text(musicxml_to_score(xml))

    assert "score-trans-instrument-profile" in xml
    assert '<slide type="start"' in xml
    assert '<slide type="stop"' in xml
    assert "<natural" in xml
    assert "<artificial" in xml
    assert "erhu:throw-bow" in xml
    assert "instrument=erhu" in restored
    for token in (
        "^lg",
        "^lh",
        "^tg",
        "^pg",
        "^1",
        "^zr",
        "^rg",
        "^bx",
        "^sh",
        "^xh",
        "^dh",
        "^ds",
        "^dx",
        "^hx",
        "^hs",
        "^sc",
        "^xc",
        "^kx",
        "^nx",
        "^wx",
        "^jx",
        "^gx",
    ):
        assert token in restored


def test_chord_performance_mark_is_written_only_once() -> None:
    xml = jianpu_to_musicxml("instrument=erhu\n1=C\n4/4\n^lg [1+3+5] 2 3 4 |")
    root = ET.fromstring(xml)

    assert len(root.findall(".//down-bow")) == 1


def test_musicxml_merges_slur_from_non_primary_chord_note() -> None:
    xml = """
    <score-partwise version="4.0">
      <part-list><score-part id="P1"><part-name>Music</part-name></score-part></part-list>
      <part id="P1"><measure number="1">
        <attributes>
          <divisions>1</divisions><key><fifths>0</fifths></key>
          <time><beats>4</beats><beat-type>4</beat-type></time>
        </attributes>
        <note><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration></note>
        <note><chord/><pitch><step>E</step><octave>4</octave></pitch><duration>1</duration>
          <notations><slur number="1" type="start"/></notations></note>
        <note><pitch><step>D</step><octave>4</octave></pitch><duration>1</duration>
          <notations><slur number="1" type="stop"/></notations></note>
      </measure></part>
    </score-partwise>
    """

    events = musicxml_to_score(xml).measures[0].events

    assert events[0].slur_start is True
    assert events[1].slur_stop is True


def test_guzheng_marks_musicxml_round_trip_and_chord_marks_write_once() -> None:
    source = (
        "instrument=guzheng\n1=C\n4/4\n"
        "^l ^sy ^sx ^zr ^bq ^zb ^sg ^xg ^cy ^sh ^xh ^zs ^zx 3 2 1 7 |\n"
        "^st [3+5] ^sm [1+2] ^py [1+3+5] 3 |\n"
        "3 ^lh 5 5 ^lh 3 |"
    )
    xml = jianpu_to_musicxml(source)
    root = ET.fromstring(xml)
    restored = score_to_jianpu_text(musicxml_to_score(xml))

    assert root.findtext(".//part-name") == "Guzheng"
    assert len(root.findall(".//arpeggiate")) == 1
    assert xml.count("guzheng:double-tuo") == 1
    assert xml.count("guzheng:double-mo") == 1
    assert xml.count("guzheng:sweep-tremolo") == 1
    assert "instrument=guzheng" in restored
    for token in (
        "^l",
        "^sy",
        "^sx",
        "^zr",
        "^bq",
        "^zb",
        "^sg",
        "^xg",
        "^cy",
        "^sh",
        "^xh",
        "^zs",
        "^zx",
        "^st",
        "^sm",
        "^py",
        "^lh",
    ):
        assert token in restored
    restored_score = musicxml_to_score(xml)
    slide_events = restored_score.measures[2].events[:4]
    assert [event.slide_direction for event in slide_events] == [
        "up",
        "up",
        "down",
        "down",
    ]
