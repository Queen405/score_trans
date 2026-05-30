from fractions import Fraction

from score_trans.domain.jianpu import jianpu_to_musicxml
from score_trans.domain.models import JianpuEvent, JianpuMeasure, JianpuPitch, JianpuScore
from score_trans.domain.musicxml import musicxml_to_score
from score_trans.services.rendering import RenderOptions, render_jianpu_svg, render_score_svg


def test_render_jianpu_svg_contains_title_and_notes() -> None:
    svg = render_jianpu_svg("key=C\ntime=4/4\n1 2 | 3 4 |")

    assert "<svg" in svg
    assert "1=C" in svg
    assert ">1<" in svg


def test_render_score_svg_uses_display_measure_number() -> None:
    score = musicxml_to_score(jianpu_to_musicxml("key=C\ntime=4/4\n1 2 |"), start_measure_number=118)

    svg = render_score_svg(score)

    assert ">118<" in svg
    assert "generated" in svg


def test_render_text_uses_publication_marks() -> None:
    svg = render_jianpu_svg("key=D\ntime=4/4\n1/ 2. 3- 4~ | ~4 (5 6) |")

    assert "duration-line" in svg
    assert "rhythm-dot" in svg
    assert "extension-line" in svg
    assert 'class="tie"' in svg
    assert 'class="slur"' in svg
    assert '<line class="beat-guide"' not in svg
    assert 'class="measure-no"' in svg
    assert 'data-number="1"' in svg
    assert 'data-number="2"' in svg


def test_render_can_show_editing_guides_when_requested() -> None:
    svg = render_jianpu_svg(
        "key=D\ntime=4/4\n1 2 3 4 |",
        RenderOptions(show_beat_guides=True, show_staff_guides=True),
    )

    assert '<line class="beat-guide"' in svg
    assert '<line class="staff-line"' in svg


def test_render_chord_orders_notes_from_high_to_low() -> None:
    svg = render_jianpu_svg("key=C\ntime=4/4\n[1+7'+3] |")

    note_lines = [line for line in svg.splitlines() if 'class="note"' in line]

    assert [line.split(">")[1].split("<")[0] for line in note_lines] == ["7", "3", "1"]
    assert "duration duration-line" not in svg


def test_render_structured_ast_score() -> None:
    score = JianpuScore(title="AST Score", target_key="G", beats=3, beat_type=4)
    score.measures.append(
        JianpuMeasure(
            source_number="A",
            display_measure_number=12,
            duration=Fraction(3, 1),
            events=[
                JianpuEvent(
                    kind="note",
                    duration=Fraction(1, 2),
                    pitches=[JianpuPitch(5, octave=1), JianpuPitch(1)],
                    dotted=1,
                    tie_start=True,
                    slur_start=True,
                    lyric="la",
                ),
                JianpuEvent(kind="rest", duration=Fraction(1, 1)),
            ],
        )
    )

    svg = render_jianpu_svg(score)

    assert "AST Score" in svg
    assert "1=G" in svg
    assert "3/4" in svg
    assert ">12</text>" in svg
    assert ">5<" in svg
    assert ">1<" in svg
    assert ">0<" in svg
    assert "duration-line" in svg
    assert "rhythm-dot" in svg
    assert 'class="tie"' in svg
    assert 'class="slur"' in svg
    assert ">la</text>" in svg


def test_dense_measure_gets_more_width_than_empty_measure() -> None:
    svg = render_jianpu_svg(
        "key=C\ntime=4/4\n0--- | 1// 2// 1// 2// 5// 6// 5// 6// 1// 2// 5// 6// 5// 6// 1'// 2'// |"
    )

    widths = []
    for line in svg.splitlines():
        if 'class="measure"' in line:
            widths.append(float(line.split('data-width="')[1].split('"')[0]))

    assert len(widths) == 2
    assert widths[1] > widths[0] * 1.8


def test_consecutive_eighth_notes_share_beam_lines() -> None:
    svg = render_jianpu_svg("key=C\ntime=4/4\n1/ 2/ 3/ 4/ |")

    assert svg.count('class="duration-line beam-line"') == 1
    assert '<line class="duration-line" x1=' not in svg


def test_consecutive_sixteenth_notes_share_two_beam_lines() -> None:
    svg = render_jianpu_svg("key=C\ntime=4/4\n1// 2// 3// 4// |")

    assert svg.count('class="duration-line beam-line"') == 2


def test_rests_inside_short_note_group_share_beam_lines() -> None:
    svg = render_jianpu_svg("key=C\ntime=4/4\n0/ 6/ 0/ 6/ |")

    assert svg.count('class="duration-line beam-line"') == 1
    assert '<line class="duration-line" x1=' not in svg


def test_quarter_notes_break_beam_groups() -> None:
    svg = render_jianpu_svg("key=C\ntime=4/4\n1/ 2/ 3 4/ |")

    assert svg.count('class="duration-line beam-line"') == 2


def test_accidentals_are_rendered_smaller_than_note_digits() -> None:
    svg = render_jianpu_svg("key=C\ntime=4/4\nb6 #4 |")

    assert '.accidental { font-size: 13px' in svg
    assert '<text class="accidental"' in svg
    assert '>b</text>' in svg
    assert '>#</text>' in svg
    assert '>b6</text>' not in svg
    assert '>#4</text>' not in svg


def test_text_tie_and_slur_arcs_stay_close_to_noteheads() -> None:
    svg = render_jianpu_svg("key=C\ntime=4/4\n1'~ (2' 3') |")

    assert 'class="tie"' in svg
    assert 'class="slur"' in svg
    assert "-22" not in svg


def test_score_slur_is_paired_between_events() -> None:
    score = JianpuScore(title="Slur", target_key="C", beats=4, beat_type=4)
    score.measures.append(
        JianpuMeasure(
            source_number="1",
            duration=Fraction(4, 1),
            events=[
                JianpuEvent(
                    kind="note",
                    duration=Fraction(1, 1),
                    pitches=[JianpuPitch(1, octave=1)],
                    slur_start=True,
                    start=Fraction(0, 1),
                ),
                JianpuEvent(
                    kind="note",
                    duration=Fraction(1, 1),
                    pitches=[JianpuPitch(2, octave=1)],
                    slur_stop=True,
                    start=Fraction(1, 1),
                ),
            ],
        )
    )

    svg = render_score_svg(score)

    assert svg.count('class="slur"') == 1


def test_chord_tie_sits_below_duration_lines() -> None:
    score = JianpuScore(title="Tie", target_key="C", beats=4, beat_type=4)
    score.measures.append(
        JianpuMeasure(
            source_number="1",
            duration=Fraction(4, 1),
            events=[
                JianpuEvent(
                    kind="note",
                    duration=Fraction(1, 2),
                    pitches=[JianpuPitch(6, accidental=-1), JianpuPitch(6)],
                    tie_start=True,
                    start=Fraction(0, 1),
                ),
            ],
        )
    )

    svg = render_score_svg(score)

    tie_line = next(line for line in svg.splitlines() if 'class="tie"' in line)
    beam_line = next(line for line in svg.splitlines() if 'class="duration-line beam-line"' in line)
    tie_y = float(tie_line.split("M ")[1].split(" ")[1])
    beam_y = float(beam_line.split('y1="')[1].split('"')[0])
    assert tie_y > beam_y + 4
