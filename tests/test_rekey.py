from __future__ import annotations

from fractions import Fraction

import pytest
from score_trans.domain.constants import KEY_TO_FIFTHS, STEP_TO_SEMITONE
from score_trans.domain.pitch_spelling import jianpu_pitch_to_written
from score_trans.domain.rekey import _parse_pitch_core, rekey_text


def test_rekey_preserves_pitch_c_to_g() -> None:
    out = rekey_text("1=G\n4 5 6", "1=C\n4 5 6")
    # F G A (C) -> b7 1 2 (G); F natural sits an octave below G so carries a comma.
    assert out == "1=G\nb7, 1 2"


def test_rekey_same_key_is_noop() -> None:
    text = "1=C\n1 2 3 4 |"
    assert rekey_text(text, text) == text


def test_rekey_accidentals_are_transposed_not_dropped() -> None:
    # #4 (F#) in C -> 7 (F# is the natural 7th in G), 5 (G) -> 1.
    assert rekey_text("1=G\n#4 5", "1=C\n#4 5") == "1=G\n7, 1"


def test_rekey_downward_g_to_c() -> None:
    # G A B (G) -> 5 6 7 (C).
    assert rekey_text("1=C\n1 2 3", "1=G\n1 2 3") == "1=C\n5 6 7"


def test_rekey_preserves_barlines_time_signature_lyrics_and_tuplets() -> None:
    previous = "1=C\n4/4\n1 2 3 4 | 5 6 7 1\nL: 春 夏 秋 冬\n$3:2;1 2 3$"
    text = "1=G\n4/4\n1 2 3 4 | 5 6 7 1\nL: 春 夏 秋 冬\n$3:2;1 2 3$"
    out = rekey_text(text, previous)
    assert out == ("1=G\n4/4\n4, 5, 6, b7, | 1 2 3 4,\nL: 春 夏 秋 冬\n$3:2;4, 5, 6,$")


def test_rekey_only_segment_after_changed_key_is_transposed() -> None:
    # Notes before the changed key line are left untouched; only the segment
    # after the changed key (until the next key line or EOF) is transposed.
    previous = "1=C\n1 2 3 4 |\n1=C\n5 6 7 1"
    text = "1=C\n1 2 3 4 |\n1=G\n5 6 7 1"
    out = rekey_text(text, previous)
    assert out == "1=C\n1 2 3 4 |\n1=G\n1 2 3 4,"


def test_rekey_unparseable_text_returns_unchanged() -> None:
    text = "1=G\nnot real jianpu @@"
    assert rekey_text(text, "1=C\n1 2 3") == text


def test_rekey_inline_key_after_barline() -> None:
    # A key token right after a barline (mid-line) is detected; only the notes
    # following it on the line (and after) transpose; notes before it stay.
    previous = "1=C\n1 2 3 4 | 5 6 7 1"
    text = "1=C\n1 2 3 4 | 1=G 5 6 7 1"
    assert rekey_text(text, previous) == "1=C\n1 2 3 4 | 1=G 1 2 3 4,"


def test_rekey_multi_character_keys() -> None:
    # Flat/sharp keys (Bb, F#) are recognised as key tokens.
    assert rekey_text("1=Bb\n1 2 3", "1=C\n1 2 3") == "1=Bb\n2, 3, #4,"
    assert rekey_text("1=F#\n1 2 3", "1=C\n1 2 3") == "1=F#\nb5, b6, b7,"


def test_rekey_key_change_inside_a_page_section() -> None:
    previous = '// @page 1 name="a"\n1=C\n1 2 3 |\n// @page 2 name="b"\n1=C\n5 6 7 1'
    text = '// @page 1 name="a"\n1=C\n1 2 3 |\n// @page 2 name="b"\n1=G\n5 6 7 1'
    assert rekey_text(text, previous) == (
        '// @page 1 name="a"\n1=C\n1 2 3 |\n// @page 2 name="b"\n1=G\n1 2 3 4,'
    )


# ── Token forms that used to be skipped entirely ──


def test_rekey_transposes_notes_carrying_duration_prefixes() -> None:
    # q1/h3 previously failed the whole-token pitch match and stayed at the old
    # pitch, producing a mixture of transposed and untransposed notes.
    assert rekey_text("1=G\nq1 q2 h3", "1=C\nq1 q2 h3") == "1=G\nq4, q5, h6,"
    assert rekey_text("1=G\ndd3 w1 s2", "1=C\ndd3 w1 s2") == "1=G\ndd6, w4, s5,"


def test_rekey_transposes_chords_outside_tuplets() -> None:
    assert rekey_text("1=G\n[1+3+5]", "1=C\n[1+3+5]") == "1=G\n[4,+6,+1]"
    assert rekey_text("1=G\nq[1+3+5]", "1=C\nq[1+3+5]") == "1=G\nq[4,+6,+1]"


def test_rekey_transposes_postfix_accidentals() -> None:
    assert rekey_text("1=G\n5# 4b", "1=C\n5# 4b") == "1=G\n#1 bb7,"


def test_rekey_transposes_notes_with_duration_extensions_and_dots() -> None:
    assert rekey_text("1=G\n1- 2--", "1=C\n1- 2--") == "1=G\n4,- 5,--"
    assert rekey_text("1=G\n1. h5.", "1=C\n1. h5.") == "1=G\n4,. h1."


def test_rekey_transposes_notes_with_attached_marks_and_dynamics() -> None:
    assert rekey_text("1=G\n^.1 ^>2", "1=C\n^.1 ^>2") == "1=G\n^.4, ^>5,"
    # Multi-character mark tokens must be consumed whole, not one character.
    assert rekey_text("1=G\n^zy1 ^t1", "1=C\n^zy1 ^t1") == "1=G\n^zy4, ^t4,"
    assert rekey_text("1=G\n\\p 1 2", "1=C\n\\p 1 2") == "1=G\n\\p 4, 5,"


def test_rekey_transposes_slurs_ties_and_leaves_rests_alone() -> None:
    assert rekey_text("1=G\n(1 2 3)", "1=C\n(1 2 3)") == "1=G\n(4, 5, 6,)"
    assert rekey_text("1=G\n4~ ~5", "1=C\n4~ ~5") == "1=G\nb7,~ ~1"
    assert rekey_text("1=G\n0 1 0 2", "1=C\n0 1 0 2") == "1=G\n0 4, 0 5,"


def test_rekey_leaves_structural_tokens_alone() -> None:
    assert rekey_text("1=G\n|: 1 2 :| *2", "1=C\n|: 1 2 :| *2") == "1=G\n|: 4, 5, :| *2"
    assert rekey_text("1=G\n12: 1 2 3", "1=C\n12: 1 2 3") == "1=G\n12: 4, 5, 6,"


def test_rekey_transposes_microtonal_and_double_accidentals() -> None:
    out = rekey_text("1=G\nqs1 qf2 tqs3", "1=C\nqs1 qf2 tqs3")
    assert out == "1=G\nqs4, qf5, tqs6,"
    assert rekey_text("1=G\nx4 bb7", "1=C\nx4 bb7") == "1=G\n#7, bb3"


def test_rekey_mixed_measure_transposes_every_note_form() -> None:
    source = "1=C\n4/4\nq1 q2 h3 | 4 5 [1+3+5] 5# |"
    out = rekey_text("1=G\n4/4\nq1 q2 h3 | 4 5 [1+3+5] 5# |", source)
    assert out == "1=G\n4/4\nq4, q5, h6, | b7, 1 [4,+6,+1] #1 |"


# ── Tuplet bodies ──


def test_rekey_tuplet_bodies_handle_spaced_and_tight_layouts() -> None:
    assert rekey_text("1=G\n$q1 q2 q3$", "1=C\n$q1 q2 q3$") == "1=G\n$q4, q5, q6,$"
    assert rekey_text("1=G\n$123$", "1=C\n$123$") == "1=G\n$4,5,6,$"
    assert rekey_text("1=G\n$[1+3+5]23$", "1=C\n$[1+3+5]23$") == "1=G\n$[4,+6,+1]5,6,$"


def test_rekey_tuplet_postfix_accidental_is_not_corrupted() -> None:
    # A blind substitution used to emit "b7,#" here: a prefix flat plus the
    # leftover postfix sharp, which re-parses a semitone too high.
    out = rekey_text("1=G\n$4# 5$", "1=C\n$4# 5$")
    assert out == "1=G\n$7, 1$"
    assert rekey_text(out, "1=G\n$4# 5$") == out


def test_rekey_tuplet_keeps_ratio_marks_and_dynamics() -> None:
    assert rekey_text("1=G\n$3:2;1 2 3$", "1=C\n$3:2;1 2 3$") == "1=G\n$3:2;4, 5, 6,$"
    assert rekey_text("1=G\n$^t1 2 3$", "1=C\n$^t1 2 3$") == "1=G\n$^t4, 5, 6,$"
    assert rekey_text("1=G\n$\\p1 2 3$", "1=C\n$\\p1 2 3$") == "1=G\n$\\p4, 5, 6,$"


# ── Key token discovery ──


def test_rekey_ignores_keys_inside_inline_comments() -> None:
    previous = "1=C\n1 2 3\n4 5 6"
    text = "1=C\n1 2 3 // 1=G\n4 5 6"
    assert rekey_text(text, previous) == text


def test_rekey_ignores_keys_inside_lyric_and_text_lines() -> None:
    previous = "1=C\n1 2 3\nL: a b c\n4 5 6"
    text = "1=C\n1 2 3\nL: 1=G b c\n4 5 6"
    assert rekey_text(text, previous) == text


def test_rekey_does_not_transpose_a_lyric_line_on_a_segment_boundary() -> None:
    previous = "1=C\n1 2\nL: 1 2 1=C 3"
    text = "1=G\n1 2\nL: 1 2 1=C 3"
    # Only the note line moves; the lyric line keeps its literal digits.
    assert rekey_text(text, previous) == "1=G\n4, 5,\nL: 1 2 1=C 3"


def test_rekey_key_token_vocabulary_matches_the_parser() -> None:
    # The parser accepts [A-G] plus at most one accidental; 1=Bbb is not a key,
    # so it must not be treated as one here either.
    text = "1=Bbb\n1 2 3"
    assert rekey_text(text, "1=C\n1 2 3") == text


def test_rekey_rejects_a_key_the_scale_table_does_not_support() -> None:
    # 1=D# parses but has no entry in KEY_TO_FIFTHS; failing loudly lets the API
    # turn it into a 400 instead of silently emitting wrong pitches.
    with pytest.raises(ValueError, match="不支持的简谱调"):
        rekey_text("1=D#\n1 2 3", "1=C\n1 2 3")


# ── Multiple and inserted key changes ──


def test_rekey_handles_two_key_changes_in_one_call() -> None:
    previous = "1=C\n1 2 |\n1=C\n3 4"
    text = "1=G\n1 2 |\n1=D\n3 4"
    assert rekey_text(text, previous) == "1=G\n4, 5, |\n1=D\n2 b3"


def test_rekey_uses_the_preceding_key_when_a_key_is_inserted() -> None:
    # Index-based pairing used to match the inserted 1=D against the old 1=G and
    # transpose the following segment from the wrong source key.
    previous = "1=C\n1 2 3 |\n1=G\n1 2 3"
    text = "1=C\n1 2 3 |\n1=D\n1 2 3 |\n1=G\n1 2 3"
    assert rekey_text(text, previous) == "1=C\n1 2 3 |\n1=D\nb7, 1 2 |\n1=G\n1 2 3"


def test_rekey_deleting_a_key_leaves_the_text_unchanged() -> None:
    previous = "1=C\n1 2 3 |\n1=G\n4 5 6"
    text = "1=C\n1 2 3"
    assert rekey_text(text, previous) == text


# ── Line endings ──


def test_rekey_preserves_crlf_line_endings() -> None:
    out = rekey_text("1=G\r\n1 2 3\r\n4 5 6", "1=C\r\n1 2 3\r\n4 5 6")
    assert out == "1=G\r\n4, 5, 6,\r\nb7, 1 2"


def test_rekey_preserves_lone_cr_line_endings() -> None:
    out = rekey_text("1=G\r1 2 3", "1=C\r1 2 3")
    assert out == "1=G\r4, 5, 6,"


# ── Natural sign ──


def test_rekey_natural_sign_cancels_the_source_key_alteration() -> None:
    # n4 in F is B natural (absolute semitone 59). Treating the natural as
    # accidental 0 would read it as Bb and land a semitone low.
    out = rekey_text("1=Bb\nn4 5", "1=F\nn4 5")
    assert out == "1=Bb\n#1 2"
    assert _absolute_semitone("n4", "F") == _absolute_semitone("#1", "Bb")


# ── Accidental mode ──


def test_rekey_respects_the_accidental_mode_setting() -> None:
    source = "1=C\n4 5 6"
    assert rekey_text("1=G\n4 5 6", source, accidental_mode="auto") == "1=G\nb7, 1 2"
    assert rekey_text("1=G\n4 5 6", source, accidental_mode="sharp") == "1=G\n#6, 1 2"
    assert rekey_text("1=G\n4 5 6", source, accidental_mode="flat") == "1=G\nb7, 1 2"


# ── Exhaustive pitch preservation ──


def _absolute_semitone(core: str, key: str) -> Fraction:
    degree, accidental, octave, is_natural = _parse_pitch_core(core)
    assert degree is not None, core
    if is_natural:
        _step, key_alter, _octave = jianpu_pitch_to_written(
            degree, Fraction(0, 1), octave, key
        )
        accidental = -key_alter
    step, alter, absolute_octave = jianpu_pitch_to_written(
        degree, accidental, octave, key
    )
    return absolute_octave * 12 + STEP_TO_SEMITONE[step] + alter


_PITCH_FORMS = (
    "1",
    "4",
    "7",
    "1'",
    "1,",
    "#4",
    "b7",
    "x4",
    "bb7",
    "5#",
    "4b",
    "n4",
    "n7",
    "qs1",
    "tqf4",
)


@pytest.mark.parametrize("accidental_mode", ["auto", "sharp", "flat"])
def test_rekey_never_changes_absolute_pitch_across_all_key_pairs(
    accidental_mode: str,
) -> None:
    for old_key in KEY_TO_FIFTHS:
        for new_key in KEY_TO_FIFTHS:
            if old_key == new_key:
                continue
            for form in _PITCH_FORMS:
                out = rekey_text(
                    f"1={new_key}\n4/4\n{form}",
                    f"1={old_key}\n4/4\n{form}",
                    accidental_mode=accidental_mode,  # type: ignore[arg-type]
                )
                result = out.split("\n")[2].strip()
                assert result, f"{old_key}->{new_key} {form} produced nothing"
                assert _absolute_semitone(form, old_key) == _absolute_semitone(
                    result, new_key
                ), f"{old_key}->{new_key} {form} -> {result}"


def test_rekey_output_is_notatable_and_idempotent() -> None:
    source = "1=C\n4/4\nq1 q2 h3 | #4 5 [1+3+5] 5# | $3:2;1 2 3$ n7 |"
    for key in KEY_TO_FIFTHS:
        text = source.replace("1=C", f"1={key}", 1)
        out = rekey_text(text, source)
        # Re-running the same change must be a fixed point.
        assert rekey_text(out, text) == out
        assert "#b" not in out and "b#" not in out
