import xml.etree.ElementTree as ET

from score_trans.domain.jianpu import jianpu_to_musicxml
from score_trans.domain.musicxml import musicxml_to_score, score_to_jianpu_text
from score_trans.models.score import Event, JianpuEvent, TextBlock


def test_musicxml_to_score_respects_start_measure_number() -> None:
    xml = jianpu_to_musicxml("1=C\n4/4\n1 2 3 4 |")

    score = musicxml_to_score(xml, start_measure_number=118)

    assert score.measures[0].display_number == 118


def test_musicxml_to_score_pads_incomplete_measure() -> None:
    xml = jianpu_to_musicxml("1=C\n4/4\n1 2 |")

    score = musicxml_to_score(xml)

    assert score.measures[0].events[-1].kind == "rest"
    assert score.measures[0].events[-1].generated is True
    assert score.measures[0].total_duration == score.measure_duration


def test_musicxml_to_score_can_transpose_target_key() -> None:
    xml = jianpu_to_musicxml("1=C\n4/4\n1 2 3 4 |")

    score = musicxml_to_score(xml, target_key="D")
    text = score_to_jianpu_text(score)

    assert "1=D" in text
    assert "b7, 1 2 b3" in text
    assert "#6, 1 2 #2" in score_to_jianpu_text(
        score,
        accidental_mode="sharp",
    )
    assert "b7, 1 2 b3" in score_to_jianpu_text(
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
