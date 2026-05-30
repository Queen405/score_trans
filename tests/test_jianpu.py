from zipfile import ZipFile

from score_trans.domain.jianpu import jianpu_to_musicxml, musicxml_file_to_jianpu, musicxml_to_jianpu, parse_jianpu


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

    assert "key=C" in jianpu
    assert "time=4/4" in jianpu
    assert "1 2 3 4" in jianpu
    assert "0" in jianpu


def test_parse_duration_extension_suffix() -> None:
    _, tokens = parse_jianpu("0- 1--- |")

    assert tokens[0].duration == 2
    assert tokens[1].duration == 4


def test_musicxml_file_to_jianpu_reads_mxl(tmp_path) -> None:
    xml = jianpu_to_musicxml("key=C\ntime=4/4\n1 2 |")
    mxl = tmp_path / "score.mxl"
    with ZipFile(mxl, "w") as archive:
        archive.writestr("score.xml", xml)
        archive.writestr("META-INF/container.xml", "<container/>")

    assert "1 2" in musicxml_file_to_jianpu(mxl)
