from fractions import Fraction
from zipfile import ZipFile

from score_trans.domain.jianpu import (
    jianpu_to_musicxml,
    musicxml_file_to_jianpu,
    musicxml_to_jianpu,
    normalize_jianpu_text,
    parse_jianpu,
    parse_jianpu_score,
)
from score_trans.domain.musicxml import score_to_jianpu_text


def test_parse_simple_jianpu() -> None:
    options, tokens = parse_jianpu("1=G\n3/4\n1 2 3 | 0- |")

    assert options.key == "G"
    assert options.beats == 3
    assert [token.kind for token in tokens].count("bar") == 2
    assert tokens[0].value == "1"


def test_jianpu_to_musicxml_contains_score() -> None:
    xml = jianpu_to_musicxml("1=C\n4/4\n1 2 3 4 |")

    assert "<score-partwise" in xml
    assert "<fifths>0</fifths>" in xml
    assert "<step>C</step>" in xml


def test_musicxml_to_jianpu_roundtrip_basic() -> None:
    xml = jianpu_to_musicxml("1=C\n4/4\n1 2 3 4 | 0 q5 6. |")
    jianpu = musicxml_to_jianpu(xml)

    assert "1=C" in jianpu
    assert "4/4" in jianpu
    assert "1 2 3 4" in jianpu
    assert "0" in jianpu


def test_parse_duration_extension_suffix() -> None:
    _, tokens = parse_jianpu("0- 1--- |")

    assert tokens[0].duration == 2
    assert tokens[1].duration == 4


def test_parse_explicit_accidental_tokens() -> None:
    _, tokens = parse_jianpu("n7 bb6 x4 #5 b3 |")

    assert [token.accidental for token in tokens[:5]] == [0, -2, 2, 1, -1]
    assert [token.value for token in tokens[:5]] == ["7", "6", "4", "5", "3"]


def test_musicxml_file_to_jianpu_reads_mxl(tmp_path) -> None:
    xml = jianpu_to_musicxml("1=C\n4/4\n1 2 |")
    mxl = tmp_path / "score.mxl"
    with ZipFile(mxl, "w") as archive:
        archive.writestr("score.xml", xml)
        archive.writestr("META-INF/container.xml", "<container/>")

    assert "1 2" in musicxml_file_to_jianpu(mxl)


def test_parse_new_project_syntax_chords_lyrics_and_marks() -> None:
    score = parse_jianpu_score("title=瑞雪迎春\n1=D\n4/4\nq1 #2. ^r [1+3+5] \\f 4~ | ~4 (5 6) |\nL: 春 风 又 绿")

    assert score.title == "瑞雪迎春"
    assert score.target_key == "D"
    assert score.measures[0].events[0].duration == Fraction(1, 2)
    assert score.measures[0].events[1].pitches[0].accidental == 1
    assert score.measures[0].events[2].is_chord
    assert score.measures[0].events[2].articulations == ["trill-mark"]
    assert score.measures[0].events[3].dynamic == "f"
    assert score.measures[0].events[3].tie_start is True
    assert score.measures[1].events[0].tie_stop is True
    assert score.measures[0].events[0].lyric == "春"


def test_legacy_text_is_rejected() -> None:
    try:
        parse_jianpu_score("key=C\ntime=4/4\n1 2/ 3 |")
    except ValueError as exc:
        assert "旧语法" in str(exc)
    else:
        raise AssertionError("legacy syntax should be rejected")


def test_ai_output_measure_labels_are_ignored() -> None:
    normalized = normalize_jianpu_text("title=中阮\n1=C\n4/4\n272: 3' 3' 2' 2' | 1' 1' 7 7 |")

    assert "272:" not in normalized
    assert "3' 3' 2' 2'" in normalized


def test_chord_duration_prefix_before_brackets_is_supported() -> None:
    normalized = normalize_jianpu_text("1=C\n4/4\nq[1+3+5] q[1+3+5] q[1+3+5] q[1+3+5] |")

    assert "q[" in normalized
    assert "[q1" not in normalized


def test_score_to_jianpu_text_preserves_marks_and_lyrics() -> None:
    score = parse_jianpu_score("title=完整\n1=C\n4/4\n|: \\mf ^> (q1~ ~q1) q[1+3+5] q0 :|\nL: 春 风")
    text = score_to_jianpu_text(score)

    assert "|:" in text
    assert ":|" in text
    assert "\\mf" in text
    assert "^>" in text
    assert "(q1~" in text
    assert "~q1)" in text
    assert "q[5+3+1]" in text
    assert "L: 春 风" in text
