from fractions import Fraction
from zipfile import ZipFile

import pytest

from score_trans.domain.jianpu import (
    jianpu_to_musicxml,
    musicxml_file_to_jianpu,
    musicxml_to_jianpu,
    normalize_jianpu_text,
    parse_jianpu,
    parse_jianpu_score,
    parse_jianpu_scores,
)
from score_trans.domain.jianpu_tokens import duration_affixes, token_duration
from score_trans.domain.musicxml import score_to_jianpu_text
from score_trans.domain.performance_marks import PERFORMANCE_MARKS
from score_trans.models.score import Event, JianpuPitch, JianpuScore, Measure


def test_parse_simple_jianpu() -> None:
    options, tokens = parse_jianpu("1=G\n3/4\n1 2 3 | 0- |")

    assert options.key == "G"
    assert options.beats == 3
    assert [token.kind for token in tokens].count("bar") == 2
    assert tokens[0].value == "1"


def test_measure_level_key_and_time_signature_are_attached_to_following_measure() -> (
    None
):
    score = parse_jianpu_score("1=C\n4/4\n1 2 3 4 |\n1=G\n3/4\n1 2 3 |")

    assert score.measures[0].target_key == "C"
    assert score.measures[0].beats_per_measure == 4
    assert score.measures[1].target_key == "G"
    assert score.measures[1].beats_per_measure == 3
    assert score.measures[1].beat_type == 4


def test_measure_level_key_and_time_signature_roundtrip_to_text() -> None:
    normalized = normalize_jianpu_text("1=C\n4/4\n1 2 3 4 |\n1=G\n3/4\n1 2 3 |")

    assert "1=G" in normalized
    assert "3/4" in normalized
    assert "1 2 3 |" in normalized


def test_measure_level_key_and_time_signature_roundtrip_to_musicxml() -> None:
    xml = jianpu_to_musicxml("1=C\n4/4\n1 2 3 4 |\n1=G\n3/4\n1 2 3 |")

    assert xml.count("<key>") == 2
    assert "<fifths>1</fifths>" in xml
    assert xml.count("<time>") == 2
    assert "<beats>3</beats>" in xml


def test_key_or_time_signature_after_notes_is_rejected() -> None:
    # 拍号/调号必须写在该小节音符之前；写在音符后面会错误地切断当前小节。
    with pytest.raises(ValueError):
        parse_jianpu_score("1=C\n4/4\n1 2 3 4 3/4 1 2 3 |")
    with pytest.raises(ValueError, match="调号"):
        parse_jianpu_score("1=C\n4/4\n1 2 3 4 1=F 1 2 3 |")


def test_measure_level_signatures_roundtrip_without_empty_measures() -> None:
    # 写出器不应把调号/拍号当作空小节单独成行（曾经的 bug：1=F |  3/4 |）。
    normalized = normalize_jianpu_text("1=C\n4/4\n1 2 3 4 |\n1=G\n3/4\n1 2 3 |")

    assert "1=G 3/4 1 2 3 |" in normalized
    assert "1=G |" not in normalized
    assert "3/4 |" not in normalized


def test_jianpu_to_musicxml_contains_score() -> None:
    xml = jianpu_to_musicxml("1=C\n4/4\n1 2 3 4 |")

    assert "<score-partwise" in xml
    assert "<fifths>0</fifths>" in xml
    assert "<step>C</step>" in xml


def test_multi_part_marker_names_roundtrip_json_escaping() -> None:
    text = (
        '// @part 1 name="Violin \\"Solo\\" 🎻"\n'
        "1=C\n4/4\n1 2 3 4 |\n"
        '// @part 2 name="低音"\n'
        "1=C\n4/4\n5 6 7 1' |"
    )

    scores = parse_jianpu_scores(text)
    normalized = normalize_jianpu_text(text)

    assert [score.part_name for score in scores] == ['Violin "Solo" 🎻', "低音"]
    assert len(parse_jianpu_scores(normalized)) == 2
    assert 'name="Violin \\"Solo\\" 🎻"' in normalized


def test_multi_part_jianpu_to_musicxml_preserves_parts() -> None:
    text = (
        '// @part 1 name="高音"\n1=C\n4/4\n1 2 3 4 |\n'
        '// @part 2 name="低音"\n1=C\n4/4\n5 6 7 1\' |'
    )

    xml = jianpu_to_musicxml(text, title="双声部")

    assert xml.count("<score-part id=") == 2
    assert xml.count("<part id=") == 2
    assert "<part-name>高音</part-name>" in xml
    assert "<part-name>低音</part-name>" in xml


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


@pytest.mark.parametrize(
    "duration",
    [
        Fraction(1, 8),
        Fraction(3, 16),
        Fraction(7, 32),
        Fraction(15, 64),
        Fraction(1, 4),
        Fraction(1, 2),
        Fraction(7, 8),
        Fraction(1, 1),
        Fraction(7, 4),
        Fraction(9, 4),
        Fraction(5, 2),
        Fraction(7, 2),
        Fraction(5, 1),
    ],
)
def test_duration_affixes_roundtrip_every_supported_duration(
    duration: Fraction,
) -> None:
    prefix, suffix = duration_affixes(duration)

    assert token_duration(f"{prefix}5{suffix}") == duration


def test_duration_extensions_are_added_after_dots() -> None:
    assert token_duration("q5.-") == Fraction(7, 4)
    assert token_duration("q5..-") == Fraction(15, 8)


def test_parse_multiple_dots_uses_the_original_base_duration() -> None:
    score = parse_jianpu_score("1=C\n4/4\n5.. q6.. 7... |")
    events = score.measures[0].events

    assert [event.duration for event in events] == [
        Fraction(7, 4),
        Fraction(7, 8),
        Fraction(15, 8),
    ]
    assert [event.dotted for event in events] == [2, 2, 3]

    reparsed = parse_jianpu_score(score_to_jianpu_text(score))
    assert [event.duration for event in reparsed.measures[0].events] == [
        Fraction(7, 4),
        Fraction(7, 8),
        Fraction(15, 8),
    ]
    assert [event.dotted for event in reparsed.measures[0].events] == [2, 2, 3]


def test_duration_affixes_reject_unrepresentable_duration() -> None:
    with pytest.raises(ValueError, match="无法用简谱时值语法表示"):
        duration_affixes(Fraction(1, 16))


def test_parse_explicit_accidental_tokens() -> None:
    _, tokens = parse_jianpu("n7 bb6 x4 #5 b3 |")

    assert [token.accidental for token in tokens[:5]] == [0, -2, 2, 1, -1]
    assert [token.value for token in tokens[:5]] == ["7", "6", "4", "5", "3"]


@pytest.mark.parametrize("dynamic", ["pppp", "ffff", "sf", "fz", "rfz", "sfp"])
def test_extended_musicxml_dynamics_are_valid_jianpu_tokens(dynamic: str) -> None:
    score = parse_jianpu_score(f"1=C\n4/4\n\\{dynamic} 1 2 3 4 |")

    assert score.measures[0].events[0].dynamic == dynamic


def test_line_start_sharp_note_is_not_treated_as_comment() -> None:
    score = parse_jianpu_score("1=C\n4/4\n#5 6 7 1' |\n2 3 4 5 |")

    assert len(score.measures) == 2
    first_event = score.measures[0].events[0]
    assert first_event.source_token == "#5"
    assert first_event.pitches[0].degree == 5
    assert first_event.pitches[0].accidental == 1


def test_double_slash_comments_are_ignored() -> None:
    text = (
        "// whole line comment\n"
        "1=C // key comment\n"
        "4/4 // time comment\n"
        "#5 6 7 1' | // measure comment\n"
        "// another comment\n"
        "2 3 4 5 |"
    )
    normalized = normalize_jianpu_text(text)

    assert "//" not in normalized
    assert "#5 6 7 1' |" in normalized
    assert "2 3 4 5 |" in normalized


def test_normalize_jianpu_text_can_force_accidental_mode() -> None:
    text = "1=C\n4/4\nb7 #4 1 2 |"

    assert "#6 #4 1 2 |" in normalize_jianpu_text(
        text,
        accidental_mode="sharp",
    )
    assert "b7 b5 1 2 |" in normalize_jianpu_text(
        text,
        accidental_mode="flat",
    )


def test_musicxml_file_to_jianpu_reads_mxl(tmp_path) -> None:
    xml = jianpu_to_musicxml("1=C\n4/4\n1 2 |")
    mxl = tmp_path / "score.mxl"
    with ZipFile(mxl, "w") as archive:
        archive.writestr("score.xml", xml)
        archive.writestr("META-INF/container.xml", "<container/>")

    assert "1 2" in musicxml_file_to_jianpu(mxl)


def test_parse_new_project_syntax_chords_lyrics_and_marks() -> None:
    score = parse_jianpu_score(
        "title=瑞雪迎春\n1=D\n4/4\nq1 #2. ^r [1+3+5] \\f 4~ | ~4 (5 6) |\nL: 春 风 又 绿"
    )

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


def test_parse_note_can_end_slur_and_start_tie() -> None:
    score = parse_jianpu_score("1=C\n4/4\n(1 2 3)~ | ~3 4 5 6 |")

    combined = score.measures[0].events[2]
    assert combined.slur_stop is True
    assert combined.tie_start is True
    assert score.measures[1].events[0].tie_stop is True


def test_measure_level_tremolo_shorthand_matches_expanded_marks() -> None:
    shorthand = parse_jianpu_score("1=C\n4/4\n(^l) q5 q1 q4 q5 h1'~ |")
    expanded = parse_jianpu_score("1=C\n4/4\n^l q5 ^l q1 ^l q4 ^l q5 ^l h1'~ |")

    assert [event.ornaments for event in shorthand.measures[0].events] == [
        event.ornaments for event in expanded.measures[0].events
    ]

    normalized = normalize_jianpu_text("1=C\n4/4\n(^l) q5 q1 q4 q5 h1'~ |")

    assert "(^l)" not in normalized
    assert normalized.count("^l") == 5


def test_measure_level_marks_apply_to_notes_and_chords_not_rests() -> None:
    score = parse_jianpu_score(
        "1=C\n4/4\n(^l) (^.) (^>) (^r) (^f) 1 [1+3+5] 0 2 |\n1 2 3 4 |"
    )
    first_measure = score.measures[0].events
    second_measure = score.measures[1].events

    expected_articulations = ["staccato", "accent", "trill-mark", "fermata"]
    assert first_measure[0].articulations == expected_articulations
    assert first_measure[0].ornaments == ["tremolo"]
    assert first_measure[1].is_chord
    assert first_measure[1].articulations == expected_articulations
    assert first_measure[1].ornaments == ["tremolo"]
    assert first_measure[2].kind == "rest"
    assert first_measure[2].articulations == []
    assert first_measure[2].ornaments == []
    assert first_measure[3].articulations == expected_articulations
    assert first_measure[3].ornaments == ["tremolo"]
    assert all(event.articulations == [] for event in second_measure)
    assert all(event.ornaments == [] for event in second_measure)


def test_measure_level_mark_can_follow_repeat_key_and_time_changes() -> None:
    score = parse_jianpu_score("1=C\n4/4\n1 2 3 4 |\n|: 1=G 3/4 (^>) 1 2 3 :|")
    changed_measure = score.measures[1]

    assert changed_measure.repeat_start is True
    assert changed_measure.repeat_end is True
    assert changed_measure.target_key == "G"
    assert changed_measure.beats_per_measure == 3
    assert all(event.articulations == ["accent"] for event in changed_measure.events)


def test_measure_level_marks_dedupe_with_single_note_marks() -> None:
    score = parse_jianpu_score("1=C\n4/4\n(^l) (^>) ^l ^> 1 2 3 4 |")
    first_event = score.measures[0].events[0]

    assert first_event.articulations == ["accent"]
    assert first_event.ornaments == ["tremolo"]


def test_measure_level_mark_after_first_event_is_rejected() -> None:
    with pytest.raises(ValueError, match="小节级演奏标记"):
        parse_jianpu_score("1=C\n4/4\n1 (^l) 2 3 4 |")


def test_measure_level_time_signature_after_key_is_supported() -> None:
    # 合法的换调+换拍同行写法（也是写出器的输出格式），拍号紧跟调号后。
    score = parse_jianpu_score("1=C\n4/4\n1 2 3 4 |\n1=G 3/4 1 2 3 |")

    assert score.measures[1].target_key == "G"
    assert score.measures[1].beats_per_measure == 3
    assert score.measures[1].beat_type == 4


def test_ai_output_measure_labels_are_ignored() -> None:
    normalized = normalize_jianpu_text(
        "title=中阮\n1=C\n4/4\n272: 3' 3' 2' 2' | 1' 1' 7 7 |"
    )

    assert "272:" not in normalized
    assert "3' 3' 2' 2'" in normalized


def test_single_dotted_note_line_is_not_treated_as_measure_label() -> None:
    score = parse_jianpu_score("1=C\n4/4\n1.   \n|")

    assert len(score.measures) == 1
    assert len(score.measures[0].events) == 1
    assert score.measures[0].events[0].pitches[0].degree == 1
    assert score.measures[0].events[0].duration == Fraction(3, 2)


@pytest.mark.parametrize(
    "body",
    [
        "^xy 1 2 3 4 |",
        "$^xy 1 2$ 3 4 5 |",
        "$^xy12$ 3 4 5 |",
    ],
)
def test_unknown_performance_marks_are_rejected(body: str) -> None:
    with pytest.raises(ValueError, match=r"不支持的演奏标记.*\^xy"):
        parse_jianpu_score(f"1=C\n4/4\n{body}")


def test_known_performance_marks_can_be_attached_to_notes() -> None:
    score = parse_jianpu_score("1=C\n4/4\n1 ^.2 ^>3 ^-4 |")
    events = score.measures[0].events

    assert [event.pitches[0].degree for event in events] == [1, 2, 3, 4]
    assert events[1].articulations == ["staccato"]
    assert events[2].articulations == ["accent"]
    assert events[3].articulations == ["tenuto"]


def test_compact_tuplet_supports_chords() -> None:
    score = parse_jianpu_score("1=C\n4/4\n$[1+3]2$ 3 4 5 |")
    tuplet = score.measures[0].events[:2]

    assert tuplet[0].is_chord is True
    assert [pitch.degree for pitch in tuplet[0].pitches] == [3, 1]
    assert tuplet[1].pitches[0].degree == 2
    assert [event.tuplet_count for event in tuplet] == [2, 2]


def test_underfilled_measure_records_validation_error() -> None:
    measure = parse_jianpu_score("1=C\n4/4\n1 2 |").measures[0]

    assert measure.validation_errors == ["小节少拍：实际 2，目标 4"]


def test_second_key_declaration_before_notes_is_measure_level_change() -> None:
    score = parse_jianpu_score("1=C\n4/4\n1=G\n1 2 3 4 |")

    assert score.target_key == "C"
    assert score.measures[0].target_key == "G"


def test_postfix_double_accidentals_are_supported() -> None:
    score = parse_jianpu_score("1=C\n4/4\n1bb 2x 3 4 |")
    pitches = [event.pitches[0] for event in score.measures[0].events]

    assert [pitch.accidental for pitch in pitches] == [-2, 2, 0, 0]
    assert "bb1 x2 3 4 |" in score_to_jianpu_text(score)


def test_chord_duration_prefix_before_brackets_is_supported() -> None:
    normalized = normalize_jianpu_text(
        "1=C\n4/4\nq[1+3+5] q[1+3+5] q[1+3+5] q[1+3+5] |"
    )

    assert "q[" in normalized
    assert "[q1" not in normalized


def test_tuplet_group_total_duration_is_one_beat() -> None:
    score = parse_jianpu_score("1=C\n4/4\n$123$ 4 5 6 |")
    events = score.measures[0].events

    assert [event.duration for event in events[:3]] == [Fraction(1, 3)] * 3
    assert sum((event.duration for event in events[:3]), Fraction(0, 1)) == Fraction(
        1, 1
    )
    assert events[0].tuplet_start is True
    assert events[2].tuplet_stop is True
    assert events[0].tuplet_count == 3


def test_tuplet_group_explicit_note_values_control_total_duration() -> None:
    eighth_triplet = parse_jianpu_score("1=C\n4/4\n$q1 q2 q3$ 4 5 6 |")
    half_note_triplet = parse_jianpu_score("1=C\n4/4\n$h1 h2 h3$ |")

    assert [event.duration for event in eighth_triplet.measures[0].events[:3]] == [
        Fraction(1, 3)
    ] * 3
    assert [event.duration for event in half_note_triplet.measures[0].events[:3]] == [
        Fraction(4, 3)
    ] * 3
    assert sum(
        (event.duration for event in half_note_triplet.measures[0].events[:3]),
        Fraction(0, 1),
    ) == Fraction(4, 1)
    assert "$h1 h2 h3$" in score_to_jianpu_text(half_note_triplet)


def test_tuplet_group_normalizes_back_to_dollar_syntax() -> None:
    normalized = normalize_jianpu_text("1=C\n4/4\n$1234$ 1 2 3 |")

    assert "$1234$" in normalized


def test_tuplet_group_accepts_note_marks_inside_dollar_syntax() -> None:
    score = parse_jianpu_score("1=C\n4/4\n$^.1 ^>2 ^-3$ 4 5 6 |")
    events = score.measures[0].events[:3]

    assert [event.duration for event in events] == [Fraction(1, 3)] * 3
    assert [event.articulations for event in events] == [
        ["staccato"],
        ["accent"],
        ["tenuto"],
    ]
    assert events[0].tuplet_start is True
    assert events[2].tuplet_stop is True


def test_tuplet_group_writes_note_marks_inside_dollar_syntax() -> None:
    score = parse_jianpu_score("1=C\n4/4\n$^.1 ^>2 ^-3$ 4 5 6 |")
    text = score_to_jianpu_text(score)

    assert "$^.1 ^>2 ^-3$" in text


def test_ai_dotted_duration_prefix_variant_is_rejected() -> None:
    try:
        parse_jianpu_score("1=C\n4/4\nh.4' |")
    except ValueError as exc:
        assert "附点" in str(exc)
        assert "h4'." in str(exc)
    else:
        raise AssertionError("prefix-before-degree dotted `h.4'` should be rejected")


def test_score_to_jianpu_text_preserves_marks_and_lyrics() -> None:
    score = parse_jianpu_score(
        "title=完整\n1=C\n4/4\n|: \\mf ^> (q1~ ~q1) q[1+3+5] q0 :|\nL: 春 风"
    )
    text = score_to_jianpu_text(score)

    assert "|:" in text
    assert ":|" in text
    assert "\\mf" in text
    assert "^>" in text
    assert "(q1~" in text
    assert "~q1)" in text
    assert "q[5+3+1]" in text
    assert "L: 春 风" in text


def test_score_to_jianpu_text_only_writes_supported_mark_tokens() -> None:
    score = JianpuScore(target_key="C", source_key="C", beats=4, beat_type=4)
    score.measures.append(
        Measure(
            source_number="1",
            duration=Fraction(4, 1),
            events=[
                Event(
                    kind="note",
                    duration=Fraction(1, 1),
                    pitches=[JianpuPitch(1)],
                    articulations=["breath-mark", "accent"],
                ),
                Event(
                    kind="note",
                    duration=Fraction(1, 1),
                    pitches=[JianpuPitch(2)],
                    ornaments=["tremolo", "turn"],
                ),
                Event(kind="rest", duration=Fraction(2, 1)),
            ],
        )
    )

    text = score_to_jianpu_text(score)

    assert "^breath-mark" not in text
    assert "^turn" not in text
    assert "^> 1" in text
    assert "^l 2" in text
    parse_jianpu_score(text)


def test_erhu_profile_marks_parse_normalize_and_dedupe() -> None:
    text = (
        "instrument=erhu\n1=C\n4/4\n"
        "^lg ^tg ^pg ^1 ^zr ^rg ^bx ^sh ^xh ^dh ^ds ^dx "
        "^hx ^hs ^sc ^xc ^kx ^nx ^wx ^jx ^gx ^lg 1 2 3 4 |"
    )

    score = parse_jianpu_score(text)
    event = score.measures[0].events[0]
    normalized = normalize_jianpu_text(text)

    assert score.instrument_profile == "erhu"
    assert event.technical.count("down-bow") == 1
    assert set(event.technical) == {
        "down-bow",
        "up-bow",
        "throw-bow",
        "fingering-1",
        "natural-harmonic",
        "artificial-harmonic",
        "pluck",
        "scoop",
        "plop",
        "finger-pad-slide",
        "doit",
        "falloff",
        "lower-return-slide",
        "upper-return-slide",
        "open-string",
        "inner-string",
        "outer-string",
        "hook-string",
    }
    assert event.ornaments == ["upper-trill", "lower-trill"]
    assert event.articulations == ["breath-mark"]
    assert normalized.count("^lg") == 1
    assert "instrument=erhu" in normalized


def test_continuous_slide_marks_previous_and_target_notes() -> None:
    score = parse_jianpu_score("instrument=erhu\n1=C\n4/4\n1 2 3 4 |\n^lh 5 6 7 1 |")
    start = score.measures[0].events[-1]
    stop = score.measures[1].events[0]

    assert start.slide_start is True
    assert stop.slide_stop is True
    assert "^lh 5" in score_to_jianpu_text(score)


def test_continuous_slide_requires_a_previous_note() -> None:
    with pytest.raises(ValueError, match="没有可连接的起始音"):
        parse_jianpu_score("instrument=erhu\n1=C\n4/4\n^lh 1 2 3 4 |")


def test_guzheng_marks_parse_with_reused_canonical_ids() -> None:
    score = parse_jianpu_score(
        "instrument=guzheng\n1=C\n4/4\n"
        "^l ^sy ^sx ^zr ^bq ^zb ^sg ^xg ^cy ^sh ^xh ^zs ^zx 1 |\n"
        "^st [3+5] ^sm [1+2] ^py [1+3+5] 2 |"
    )
    first = score.measures[0].events[0]
    chord_events = score.measures[1].events[:3]

    assert score.instrument_profile == "guzheng"
    assert first.ornaments == ["tremolo"]
    assert {
        "guzheng-sweep-tremolo",
        "string-sweep",
        "natural-harmonic",
        "guzheng-board-front-flower",
        "guzheng-on-beat-flower",
        "guzheng-ascending-scrape",
        "guzheng-descending-scrape",
        "guzheng-vibrato",
        "scoop",
        "plop",
        "guzheng-ornament-up-slide",
        "guzheng-ornament-down-slide",
    } == set(first.technical)
    assert chord_events[0].technical == ["guzheng-double-tuo"]
    assert chord_events[1].technical == ["guzheng-double-mo"]
    assert chord_events[2].technical == ["arpeggio"]


def test_ruan_marks_parse_and_legacy_profile_normalizes() -> None:
    score = parse_jianpu_score(
        "instrument=ruan\n1=C\n4/4\n^l ^sx ^zr ^zy 1 2 3 4 |\n3 ^lh 5 ^py [1+3+5] 2 |"
    )
    first = score.measures[0].events[0]

    assert score.instrument_profile == "ruan"
    assert first.ornaments == ["tremolo", "ornament-note"]
    assert first.technical == ["string-sweep", "natural-harmonic"]
    assert score.measures[1].events[0].slide_start is True
    assert score.measures[1].events[1].slide_stop is True
    assert score.measures[1].events[2].technical == ["arpeggio"]

    legacy = parse_jianpu_score("instrument=zhongruan\n1=C\n4/4\n^l 1 2 3 4 |")
    assert legacy.instrument_profile == "ruan"
    assert "instrument=ruan" in score_to_jianpu_text(legacy)


def test_ruan_arpeggio_requires_a_chord() -> None:
    with pytest.raises(ValueError, match="必须跟随和弦"):
        parse_jianpu_score("instrument=ruan\n1=C\n4/4\n^py 1 2 3 4 |")


@pytest.mark.parametrize("token", ["st", "sm", "py"])
def test_guzheng_chord_only_marks_reject_single_notes(token: str) -> None:
    with pytest.raises(ValueError, match="必须跟随和弦"):
        parse_jianpu_score(f"instrument=guzheng\n1=C\n4/4\n^{token} 1 2 3 4 |")


def test_guzheng_continuous_slide_infers_direction() -> None:
    score = parse_jianpu_score("instrument=guzheng\n1=C\n4/4\n3 ^lh 5 5 ^lh 3 |")
    events = score.measures[0].events

    assert [event.slide_direction for event in events] == [
        "up",
        "up",
        "down",
        "down",
    ]


def test_guzheng_continuous_slide_rejects_ambiguous_endpoints() -> None:
    with pytest.raises(ValueError, match="起止音高不能相同"):
        parse_jianpu_score("instrument=guzheng\n1=C\n4/4\n3 ^lh 3 2 1 |")
    with pytest.raises(ValueError, match="只能连接两个单音"):
        parse_jianpu_score("instrument=guzheng\n1=C\n4/4\n[1+3] ^lh 5 2 1 |")


def test_guzheng_flower_marks_preserve_written_note_duration() -> None:
    score = parse_jianpu_score("instrument=guzheng\n1=C\n4/4\n^bq q3 ^zb h4 q1 2 |")
    events = score.measures[0].events

    assert events[0].duration == Fraction(1, 2)
    assert events[1].duration == Fraction(2, 1)


def test_performance_mark_tokens_are_unique_and_new_tokens_are_short() -> None:
    tokens = [mark.token for mark in PERFORMANCE_MARKS]
    guzheng_tokens = {
        "sy",
        "sx",
        "st",
        "sm",
        "py",
        "bq",
        "zb",
        "sg",
        "xg",
        "cy",
        "zs",
        "zx",
    }

    assert len(tokens) == len(set(tokens))
    assert guzheng_tokens <= set(tokens)
    assert all(token.isalpha() and 1 <= len(token) <= 2 for token in guzheng_tokens)
