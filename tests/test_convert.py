from score_trans.domain.jianpu import jianpu_to_musicxml
from score_trans.domain.musicxml import musicxml_to_score, score_to_jianpu_text
from score_trans.exec.convert.actions import MusicXmlToJianpuAction
from score_trans.models.score import Event, JianpuEvent, TextBlock
from score_trans.services.ocr.providers import MockOCRProvider


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


def test_convert_to_jianpu_includes_positioned_ocr_text(tmp_path) -> None:
    musicxml_path = tmp_path / "score.musicxml"
    image_path = tmp_path / "score.png"
    musicxml_path.write_text(jianpu_to_musicxml("1=C\n4/4\n1 2 3 4 |"), encoding="utf-8")
    image_path.write_bytes(b"fake image")
    provider = MockOCRProvider([TextBlock("歌词 一", bbox=(10, 20, 50, 32), role="lyric")])

    text = MusicXmlToJianpuAction().execute(musicxml_path, image_path=image_path, ocr_provider=provider)

    assert provider.calls == [image_path]
    assert "@text 10 20 50 32 lyric 歌词 一" in text
