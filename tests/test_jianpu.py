from fractions import Fraction
from zipfile import ZipFile

from score_trans.domain.jianpu import (
    jianpu_to_musicxml,
    migrate_legacy_jianpu,
    musicxml_file_to_jianpu,
    musicxml_to_jianpu,
    normalize_jianpu_text,
    parse_jianpu,
    parse_jianpu_score,
)


def test_parse_simple_jianpu() -> None:
    options, tokens = parse_jianpu("key=G\ntime=3/4\n1 2 3 | 0 - |")

    assert options.key == "G"
    assert options.beats == 3
    assert [token.kind for token in tokens].count("bar") == 2
    assert tokens[0].value == "1"


def test_jianpu_to_musicxml_contains_score() -> None:
    xml = jianpu_to_musicxml("key=C\ntime=4/4\n1 2 3 4 |")

    assert "<score-partwise" in xml
    assert "<fifths>0</fifths>" in xml
    assert "<step>C</step>" in xml


def test_musicxml_to_jianpu_roundtrip_basic() -> None:
    xml = jianpu_to_musicxml("key=C\ntime=4/4\n1 2 3 4 | 0 5/ 6. |")
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
    xml = jianpu_to_musicxml("key=C\ntime=4/4\n1 2 |")
    mxl = tmp_path / "score.mxl"
    with ZipFile(mxl, "w") as archive:
        archive.writestr("score.xml", xml)
        archive.writestr("META-INF/container.xml", "<container/>")

    assert "1 2" in musicxml_file_to_jianpu(mxl)


def test_parse_new_project_syntax_chords_lyrics_and_marks() -> None:
    score = parse_jianpu_score("title=瑞雪迎春\n1=D\n4/4\nq1 #2. ^tr [1+3+5] \\f 4~ | ~4 (5 6) |\nL: 春 风 又 绿")

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


def test_legacy_text_migrates_to_new_syntax() -> None:
    migrated = migrate_legacy_jianpu("key=C\ntime=4/4\n1 2/ 3 | [3/+#2/] |")

    assert migrated.startswith("1=C\n4/4")
    assert "q2" in migrated
    assert "q[3+#2]" in migrated
    assert normalize_jianpu_text(migrated).startswith("1=C\n4/4")


def test_ai_output_measure_labels_are_ignored() -> None:
    normalized = normalize_jianpu_text("title=中阮\n1=C\n4/4\n272: 3' 3' 2' 2' | 1' 1' 7 7 |")

    assert "272:" not in normalized
    assert "3' 3' 2' 2'" in normalized


def test_ai_chord_duration_inside_brackets_is_normalized() -> None:
    normalized = normalize_jianpu_text("1=C\n4/4\n[q1+3+5] [q1+3+5] [q1+3+5] [q1+3+5] |")

    assert "q[" in normalized
    assert "[q1" not in normalized
