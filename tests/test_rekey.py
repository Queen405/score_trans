from __future__ import annotations

import re
from fractions import Fraction

import pytest
from score_trans.domain.constants import KEY_TO_FIFTHS, STEP_TO_SEMITONE
from score_trans.domain.parse.jianpu_text import parse_jianpu_score
from score_trans.domain.pitch_spelling import jianpu_pitch_to_written
from score_trans.domain.rekey import _DEFAULT_KEY, _parse_pitch_core, rekey_text
from score_trans.models.jianpu.types import RekeySkipReason


def _rekey(text: str, previous_text: str, **kwargs: object) -> str:
    """转调并只取文本，供关注记谱结果的用例使用。

    rekey_text 返回 RekeyResult；跳过原因由本文件末尾的专门用例断言。
    """
    return rekey_text(text, previous_text, **kwargs).text  # type: ignore[arg-type]


def _skip_reason(text: str, previous_text: str) -> RekeySkipReason | None:
    return rekey_text(text, previous_text).skip_reason


def test_rekey_preserves_pitch_c_to_g() -> None:
    out = _rekey("1=G\n4 5 6", "1=C\n4 5 6")
    # F G A (C) -> b7 1 2 (G); F natural sits an octave below G so carries a comma.
    assert out == "1=G\nb7, 1 2"


def test_rekey_same_key_is_noop() -> None:
    text = "1=C\n1 2 3 4 |"
    assert _rekey(text, text) == text


def test_rekey_accidentals_are_transposed_not_dropped() -> None:
    # #4 (F#) in C -> 7 (F# is the natural 7th in G), 5 (G) -> 1.
    assert _rekey("1=G\n#4 5", "1=C\n#4 5") == "1=G\n7, 1"


def test_rekey_downward_g_to_c() -> None:
    # G A B (G) -> 5 6 7 (C).
    assert _rekey("1=C\n1 2 3", "1=G\n1 2 3") == "1=C\n5 6 7"


def test_rekey_preserves_barlines_time_signature_lyrics_and_tuplets() -> None:
    previous = "1=C\n4/4\n1 2 3 4 | 5 6 7 1\nL: 春 夏 秋 冬\n$3:2;1 2 3$"
    text = "1=G\n4/4\n1 2 3 4 | 5 6 7 1\nL: 春 夏 秋 冬\n$3:2;1 2 3$"
    out = _rekey(text, previous)
    assert out == ("1=G\n4/4\n4, 5, 6, b7, | 1 2 3 4,\nL: 春 夏 秋 冬\n$3:2;4, 5, 6,$")


def test_rekey_only_segment_after_changed_key_is_transposed() -> None:
    # Notes before the changed key line are left untouched; only the segment
    # after the changed key (until the next key line or EOF) is transposed.
    previous = "1=C\n1 2 3 4 |\n1=C\n5 6 7 1"
    text = "1=C\n1 2 3 4 |\n1=G\n5 6 7 1"
    out = _rekey(text, previous)
    assert out == "1=C\n1 2 3 4 |\n1=G\n1 2 3 4,"


def test_rekey_unparseable_text_returns_unchanged() -> None:
    text = "1=G\nnot real jianpu @@"
    assert _rekey(text, "1=C\n1 2 3") == text


def test_rekey_inline_key_after_barline() -> None:
    # A key token right after a barline (mid-line) is detected; only the notes
    # following it on the line (and after) transpose; notes before it stay.
    previous = "1=C\n1 2 3 4 | 5 6 7 1"
    text = "1=C\n1 2 3 4 | 1=G 5 6 7 1"
    assert _rekey(text, previous) == "1=C\n1 2 3 4 | 1=G 1 2 3 4,"


def test_rekey_key_at_line_start_transposes_the_same_line() -> None:
    # 调号写在小节行首（1=G 5 6 7 …）时，本行音符同属新调管辖，必须与后续小节
    # 一起转调。回归：行首调号曾让 _KEY_LINE 把整行误判为元数据而跳过本小节。
    previous = "1=C\n4/4\n\n1 2 3 4 |\n5 6 7 1' |\n2 3 4 5 |"
    text = "1=C\n4/4\n\n1 2 3 4 |\n1=G 5 6 7 1' |\n2 3 4 5 |"
    assert _rekey(text, previous) == (
        "1=C\n4/4\n\n1 2 3 4 |\n1=G 1 2 3 4 |\n5, 6, b7, 1 |"
    )


def test_rekey_key_at_line_start_with_multiple_measures_on_the_line() -> None:
    # 行首调号后同一行有多个小节时，该行所有小节都在新调管辖之下。
    previous = "1=C\n4/4\n1 2 3 4 |\n5 6 7 1' | 2 3 4 5 |"
    text = "1=C\n4/4\n1 2 3 4 |\n1=G 5 6 7 1' | 2 3 4 5 |"
    assert _rekey(text, previous) == (
        "1=C\n4/4\n1 2 3 4 |\n1=G 1 2 3 4 | 5, 6, b7, 1 |"
    )


def test_rekey_key_at_line_start_followed_by_a_time_signature() -> None:
    # 「1=G 3/4」剥掉调号后只剩拍号，仍属元数据，不能被当成音符转调。
    previous = "1=C\n4/4\n1 2 3 4 |\n3/4\n1 2 3 |"
    text = "1=C\n4/4\n1 2 3 4 |\n1=G 3/4\n1 2 3 |"
    assert _rekey(text, previous) == "1=C\n4/4\n1 2 3 4 |\n1=G 3/4\n4, 5, 6, |"


def test_rekey_multi_character_keys() -> None:
    # Flat/sharp keys (Bb, F#) are recognised as key tokens.
    assert _rekey("1=Bb\n1 2 3", "1=C\n1 2 3") == "1=Bb\n2, 3, #4,"
    assert _rekey("1=F#\n1 2 3", "1=C\n1 2 3") == "1=F#\nb5, b6, b7,"


def test_rekey_key_change_inside_a_page_section() -> None:
    previous = '// @page 1 name="a"\n1=C\n1 2 3 |\n// @page 2 name="b"\n1=C\n5 6 7 1'
    text = '// @page 1 name="a"\n1=C\n1 2 3 |\n// @page 2 name="b"\n1=G\n5 6 7 1'
    assert _rekey(text, previous) == (
        '// @page 1 name="a"\n1=C\n1 2 3 |\n// @page 2 name="b"\n1=G\n1 2 3 4,'
    )


# ── Token forms that used to be skipped entirely ──


def test_rekey_transposes_notes_carrying_duration_prefixes() -> None:
    # q1/h3 previously failed the whole-token pitch match and stayed at the old
    # pitch, producing a mixture of transposed and untransposed notes.
    assert _rekey("1=G\nq1 q2 h3", "1=C\nq1 q2 h3") == "1=G\nq4, q5, h6,"
    assert _rekey("1=G\ndd3 w1 s2", "1=C\ndd3 w1 s2") == "1=G\ndd6, w4, s5,"


def test_rekey_transposes_chords_outside_tuplets() -> None:
    assert _rekey("1=G\n[1+3+5]", "1=C\n[1+3+5]") == "1=G\n[4,+6,+1]"
    assert _rekey("1=G\nq[1+3+5]", "1=C\nq[1+3+5]") == "1=G\nq[4,+6,+1]"


def test_rekey_transposes_postfix_accidentals() -> None:
    assert _rekey("1=G\n5# 4b", "1=C\n5# 4b") == "1=G\n#1 bb7,"


def test_rekey_transposes_notes_with_duration_extensions_and_dots() -> None:
    assert _rekey("1=G\n1- 2--", "1=C\n1- 2--") == "1=G\n4,- 5,--"
    assert _rekey("1=G\n1. h5.", "1=C\n1. h5.") == "1=G\n4,. h1."


def test_rekey_transposes_notes_with_attached_marks_and_dynamics() -> None:
    assert _rekey("1=G\n^.1 ^>2", "1=C\n^.1 ^>2") == "1=G\n^.4, ^>5,"
    # Multi-character mark tokens must be consumed whole, not one character.
    assert _rekey("1=G\n^zy1 ^t1", "1=C\n^zy1 ^t1") == "1=G\n^zy4, ^t4,"
    assert _rekey("1=G\n\\p 1 2", "1=C\n\\p 1 2") == "1=G\n\\p 4, 5,"


def test_rekey_transposes_slurs_ties_and_leaves_rests_alone() -> None:
    assert _rekey("1=G\n(1 2 3)", "1=C\n(1 2 3)") == "1=G\n(4, 5, 6,)"
    assert _rekey("1=G\n4~ ~5", "1=C\n4~ ~5") == "1=G\nb7,~ ~1"
    assert _rekey("1=G\n0 1 0 2", "1=C\n0 1 0 2") == "1=G\n0 4, 0 5,"


def test_rekey_leaves_structural_tokens_alone() -> None:
    assert _rekey("1=G\n|: 1 2 :| *2", "1=C\n|: 1 2 :| *2") == "1=G\n|: 4, 5, :| *2"
    assert _rekey("1=G\n12: 1 2 3", "1=C\n12: 1 2 3") == "1=G\n12: 4, 5, 6,"


def test_rekey_transposes_microtonal_and_double_accidentals() -> None:
    out = _rekey("1=G\nqs1 qf2 tqs3", "1=C\nqs1 qf2 tqs3")
    assert out == "1=G\nqs4, qf5, tqs6,"
    assert _rekey("1=G\nx4 bb7", "1=C\nx4 bb7") == "1=G\n#7, bb3"


def test_rekey_mixed_measure_transposes_every_note_form() -> None:
    source = "1=C\n4/4\nq1 q2 h3 | 4 5 [1+3+5] 5# |"
    out = _rekey("1=G\n4/4\nq1 q2 h3 | 4 5 [1+3+5] 5# |", source)
    assert out == "1=G\n4/4\nq4, q5, h6, | b7, 1 [4,+6,+1] #1 |"


# ── Tuplet bodies ──


def test_rekey_tuplet_bodies_handle_spaced_and_tight_layouts() -> None:
    assert _rekey("1=G\n$123$", "1=C\n$123$") == "1=G\n$4,5,6,$"
    assert _rekey("1=G\n$[1+3+5]23$", "1=C\n$[1+3+5]23$") == "1=G\n$[4,+6,+1]5,6,$"


def test_rekey_tuplet_postfix_accidental_is_not_corrupted() -> None:
    # A blind substitution used to emit "b7,#" here: a prefix flat plus the
    # leftover postfix sharp, which re-parses a semitone too high.
    out = _rekey("1=G\n$4# 5$", "1=C\n$4# 5$")
    assert out == "1=G\n$7, 1$"
    assert _rekey(out, "1=G\n$4# 5$") == out


def test_rekey_tuplet_keeps_ratio_marks_and_dynamics() -> None:
    assert _rekey("1=G\n$3:2;1 2 3$", "1=C\n$3:2;1 2 3$") == "1=G\n$3:2;4, 5, 6,$"
    assert _rekey("1=G\n$^t1 2 3$", "1=C\n$^t1 2 3$") == "1=G\n$^t4, 5, 6,$"
    assert _rekey("1=G\n$\\p1 2 3$", "1=C\n$\\p1 2 3$") == "1=G\n$\\p4, 5, 6,$"


# ── Key token discovery ──


def test_rekey_ignores_keys_inside_inline_comments() -> None:
    previous = "1=C\n1 2 3\n4 5 6"
    text = "1=C\n1 2 3 // 1=G\n4 5 6"
    assert _rekey(text, previous) == text


def test_rekey_ignores_keys_inside_lyric_and_text_lines() -> None:
    previous = "1=C\n1 2 3\nL: a b c\n4 5 6"
    text = "1=C\n1 2 3\nL: 1=G b c\n4 5 6"
    assert _rekey(text, previous) == text


def test_rekey_does_not_transpose_a_lyric_line_on_a_segment_boundary() -> None:
    previous = "1=C\n1 2\nL: 1 2 1=C 3"
    text = "1=G\n1 2\nL: 1 2 1=C 3"
    # Only the note line moves; the lyric line keeps its literal digits.
    assert _rekey(text, previous) == "1=G\n4, 5,\nL: 1 2 1=C 3"


def test_rekey_key_token_vocabulary_matches_the_parser() -> None:
    # The parser accepts [A-G] plus at most one accidental; 1=Bbb is not a key,
    # so it must not be treated as one here either.
    text = "1=Bbb\n1 2 3"
    assert _rekey(text, "1=C\n1 2 3") == text


def test_rekey_rejects_a_key_the_scale_table_does_not_support() -> None:
    # 1=D# parses but has no entry in KEY_TO_FIFTHS; failing loudly lets the API
    # turn it into a 400 instead of silently emitting wrong pitches.
    with pytest.raises(ValueError, match="不支持的简谱调"):
        _rekey("1=D#\n1 2 3", "1=C\n1 2 3")


# ── Multiple and inserted key changes ──


def test_rekey_handles_two_key_changes_in_one_call() -> None:
    previous = "1=C\n1 2 |\n1=C\n3 4"
    text = "1=G\n1 2 |\n1=D\n3 4"
    assert _rekey(text, previous) == "1=G\n4, 5, |\n1=D\n2 b3"


def test_rekey_uses_the_preceding_key_when_a_key_is_inserted() -> None:
    # Index-based pairing used to match the inserted 1=D against the old 1=G and
    # transpose the following segment from the wrong source key.
    previous = "1=C\n1 2 3 |\n1=G\n1 2 3"
    text = "1=C\n1 2 3 |\n1=D\n1 2 3 |\n1=G\n1 2 3"
    assert _rekey(text, previous) == "1=C\n1 2 3 |\n1=D\nb7, 1 2 |\n1=G\n1 2 3"


def test_rekey_deleting_a_key_along_with_content_leaves_the_text_unchanged() -> None:
    # Notes disappeared too, so they cannot be matched one-to-one and no reliable
    # old key is available for what survived. See the governing-key tests below
    # for the pure-deletion case, which does transpose.
    previous = "1=C\n1 2 3 |\n1=G\n4 5 6"
    text = "1=C\n1 2 3"
    assert _rekey(text, previous) == text


def test_rekey_changes_a_key_back_to_one_that_matches_another_section() -> None:
    # Multi-section scores repeat the key on every section, so editing one back to
    # the shared value makes the two key sequences differ only at that position.
    # LCS then matched the *other* section's key against the edited slot, turned
    # the real replace into delete+insert, and produced no segment at all — the
    # user-visible symptom was "I can leave C but never get back to C".
    previous = "1=D\n4/4\n1 2 3 4 |\n1=C\n5 6 7 1 |"
    text = "1=C\n4/4\n1 2 3 4 |\n1=C\n5 6 7 1 |"
    result = rekey_text(text, previous)
    assert result.skip_reason is None
    assert result.text == "1=C\n4/4\n2 3 #4 5 |\n1=C\n5 6 7 1 |"


def test_rekey_change_back_to_a_duplicate_key_works_at_every_position() -> None:
    # The same trap exists for any section, not just the first one.
    for position in range(3):
        old_keys = ["C", "C", "C"]
        old_keys[position] = "G"
        previous = _sectioned_doc(old_keys)
        text = _sectioned_doc(["C", "C", "C"])
        result = rekey_text(text, previous)
        assert result.skip_reason is None, position
        assert result.text != text, position


def _sectioned_doc(keys: list[str]) -> str:
    lines: list[str] = []
    for index, key in enumerate(keys):
        lines.append(f"1={key}")
        if index == 0:
            lines.append("4/4")
        lines.append("1 2 3 4 |")
    return "\n".join(lines)


@pytest.mark.parametrize("start_key", list(KEY_TO_FIFTHS))
def test_rekey_round_trips_through_every_key_and_back(start_key: str) -> None:
    # Walk a two-section document (both sections sharing one key, as real
    # multi-page scores do) through every other key and back to the start; the
    # first section must land on exactly the notes it began with.
    original = _rekey_first_key(start_key)
    current = original
    for key in KEY_TO_FIFTHS:
        if key == start_key:
            continue
        result = rekey_text(_swap_first_key(current, key), current)
        assert result.skip_reason is None, f"{start_key} -> {key}"
        current = result.text
    back = rekey_text(_swap_first_key(current, start_key), current)
    assert back.skip_reason is None, f"back to {start_key}"
    assert back.text == original


def _rekey_first_key(key: str) -> str:
    return f"1={key}\n4/4\n1 2 3 4 |\n1={key}\n5 6 7 1 |"


def _swap_first_key(text: str, key: str) -> str:
    return re.sub(r"1=[A-G][#b]?", f"1={key}", text, count=1)


# ── Deleting a key falls back to the key that is actually in force ──


def test_rekey_deleting_a_mid_document_key_reverts_to_the_preceding_key() -> None:
    # Removing "1=D" means the notes it governed are now read in C, so they have
    # to be rewritten back to C spelling. Locating the region by key-sequence
    # index cannot express this — the deleted token is gone from the new text —
    # so the governing-key path handles it.
    previous = "1=C\n4/4\n1 2 3 4 |\n1=D\nb7, 1 2 b3 |\n1=G\n5 6 7 1 |"
    text = "1=C\n4/4\n1 2 3 4 |\nb7, 1 2 b3 |\n1=G\n5 6 7 1 |"
    result = rekey_text(text, previous)
    assert result.skip_reason is None
    # Only the orphaned segment moves; the C section and the 1=G section stay put.
    assert result.text == "1=C\n4/4\n1 2 3 4 |\n1 2 3 4 |\n1=G\n5 6 7 1 |"


def test_rekey_deleting_the_last_key_reverts_the_region_to_end_of_text() -> None:
    previous = "1=C\n4/4\n1 2 3 4 |\n1=D\nb7, 1 2 b3 |"
    text = "1=C\n4/4\n1 2 3 4 |\nb7, 1 2 b3 |"
    assert _rekey(text, previous) == "1=C\n4/4\n1 2 3 4 |\n1 2 3 4 |"


def test_rekey_deleting_a_page_key_reverts_to_the_earlier_page_key() -> None:
    # The editor holds batch-level text, so a later page's key falls back to the
    # key still in force from an earlier page rather than to the default.
    previous = "// @page 1\n1=G\n4/4\n1 2 3 4 |\n// @page 2\n1=C\n5 6 7 1 |"
    text = "// @page 1\n1=G\n4/4\n1 2 3 4 |\n// @page 2\n5 6 7 1 |"
    result = rekey_text(text, previous)
    assert result.skip_reason is None
    assert result.text == ("// @page 1\n1=G\n4/4\n1 2 3 4 |\n// @page 2\n1 2 3 4, |")


def test_rekey_deleting_an_inline_key_reverts_only_what_followed_it() -> None:
    previous = "1=C\n4/4\n1 2 3 4 | 1=D b7, 1 2 b3 |"
    text = "1=C\n4/4\n1 2 3 4 | b7, 1 2 b3 |"
    assert _rekey(text, previous) == "1=C\n4/4\n1 2 3 4 | 1 2 3 4 |"


def test_rekey_deleting_the_only_key_reverts_to_the_parser_default() -> None:
    previous = "1=D\n4/4\nb7, 1 2 b3 |"
    text = "4/4\nb7, 1 2 b3 |"
    result = rekey_text(text, previous)
    assert result.skip_reason is None
    assert result.text == "4/4\n1 2 3 4 |"


def test_rekey_default_key_matches_what_the_parser_assumes() -> None:
    # A keyless document is read in _DEFAULT_KEY; if the two ever drift apart the
    # rewritten text would disagree with how it is rendered.
    assert parse_jianpu_score("4/4\n1 2 3 4 |").target_key == _DEFAULT_KEY


def test_rekey_deleting_a_key_token_but_leaving_a_blank_line_behaves_the_same() -> None:
    # Selecting just the "1=D" characters leaves an empty line behind. Blank-line
    # differences must not defeat the pure-key-edit gate.
    previous = "1=C\n4/4\n1 2 3 4 |\n1=D\nb7, 1 2 b3 |"
    text = "1=C\n4/4\n1 2 3 4 |\n\nb7, 1 2 b3 |"
    assert _rekey(text, previous) == "1=C\n4/4\n1 2 3 4 |\n\n1 2 3 4 |"


def test_rekey_deleting_a_key_together_with_a_note_edit_is_reported() -> None:
    # The gate rejects this: notes changed too, so they no longer correspond and
    # guessing an old key would write wrong pitches.
    previous = "1=C\n4/4\n1 2 3 4 |\n1=D\nb7, 1 2 b3 |"
    text = "1=C\n4/4\n1 2 3 5 |\nb7, 1 2 b3 |"
    result = rekey_text(text, previous)
    assert result.skip_reason == "unresolvable_key_change"
    assert result.text == text


def test_rekey_adding_a_comment_that_mentions_a_key_changes_nothing() -> None:
    previous = "1=C\n1 2 3\n4 5 6"
    text = "1=C\n1 2 3 // 1=G\n4 5 6"
    result = rekey_text(text, previous)
    assert result.skip_reason is None
    assert result.text == text


@pytest.mark.parametrize("anchor_key", list(KEY_TO_FIFTHS))
def test_rekey_inserting_then_deleting_a_key_restores_the_original(
    anchor_key: str,
) -> None:
    # Round-trip invariant across every key pair: adding a mid-document key and
    # then removing it again must land back on the notes we started from.
    original = f"1={anchor_key}\n4/4\n1 2 3 4 |\n5 6 7 1 |"
    for inserted_key in KEY_TO_FIFTHS:
        if inserted_key == anchor_key:
            continue
        lines = original.split("\n")
        inserted = "\n".join(lines[:3] + [f"1={inserted_key}"] + lines[3:])
        added = rekey_text(inserted, original)
        assert added.skip_reason is None, f"{anchor_key} + {inserted_key}"
        assert added.text != inserted, f"{anchor_key} + {inserted_key}"
        removed_text = "\n".join(
            line for line in added.text.split("\n") if line != f"1={inserted_key}"
        )
        removed = rekey_text(removed_text, added.text)
        assert removed.skip_reason is None, f"{anchor_key} - {inserted_key}"
        assert removed.text == original, f"{anchor_key} - {inserted_key}"


# ── Skip reasons ──


def test_rekey_transposes_even_when_the_baseline_is_a_mid_typing_state() -> None:
    # The editor's baseline is whatever the document looked like before the edit,
    # which during incremental typing is often unparseable ("1=E5" is not a token).
    # Parsing previous_text used to reject this and silently return the input, so
    # typing a new key one character at a time never transposed anything.
    previous = "1=C\n4/4\n1 2 3 4 |\n1=E5 6 7 1 |"
    text = "1=C\n4/4\n1 2 3 4 |\n1=E 5 6 7 1 |"
    result = rekey_text(text, previous)
    assert result.skip_reason is None
    assert result.text == "1=C\n4/4\n1 2 3 4 |\n1=E b3 4 5 b6, |"


def test_rekey_transposes_when_the_baseline_lost_its_key_letter() -> None:
    # Deleting the letter of "1=C" leaves "1=", which does not parse either.
    previous = "1=\n4/4\n1 2 3 4"
    text = "1=D\n4/4\n1 2 3 4"
    result = rekey_text(text, previous)
    # The old key is unrecoverable from "1=", so there is nothing to transpose
    # from — but the caller must be told, not left guessing.
    assert result.skip_reason == "unresolvable_key_change"
    assert result.text == text


def test_rekey_reports_an_unparseable_current_text() -> None:
    result = rekey_text("1=G\nnot real jianpu @@", "1=C\n1 2 3")
    assert result.skip_reason == "parse_error"
    assert result.detail


def test_rekey_reports_a_current_text_with_no_key_token() -> None:
    assert _skip_reason("4/4\n1 2 3", "1=C\n1 2 3") == "no_key_token"


def test_rekey_reports_no_skip_reason_when_the_keys_did_not_change() -> None:
    # An ordinary note edit must not look like a failure to the caller.
    assert _skip_reason("1=C\n1 2 3 4", "1=C\n1 2 3") is None


def test_rekey_reports_an_unresolvable_change_when_a_key_is_deleted() -> None:
    assert (
        _skip_reason("1=C\n1 2 3", "1=C\n1 2 3 |\n1=G\n4 5 6")
        == "unresolvable_key_change"
    )


# ── Line endings ──


def test_rekey_preserves_crlf_line_endings() -> None:
    out = _rekey("1=G\r\n1 2 3\r\n4 5 6", "1=C\r\n1 2 3\r\n4 5 6")
    assert out == "1=G\r\n4, 5, 6,\r\nb7, 1 2"


def test_rekey_preserves_lone_cr_line_endings() -> None:
    out = _rekey("1=G\r1 2 3", "1=C\r1 2 3")
    assert out == "1=G\r4, 5, 6,"


# ── Natural sign ──


def test_rekey_natural_sign_cancels_the_source_key_alteration() -> None:
    # n4 in F is B natural (absolute semitone 59). Treating the natural as
    # accidental 0 would read it as Bb and land a semitone low.
    out = _rekey("1=Bb\nn4 5", "1=F\nn4 5")
    assert out == "1=Bb\n#1 2"
    assert _absolute_semitone("n4", "F") == _absolute_semitone("#1", "Bb")


# ── Accidental mode ──


def test_rekey_respects_the_accidental_mode_setting() -> None:
    source = "1=C\n4 5 6"
    assert _rekey("1=G\n4 5 6", source, accidental_mode="auto") == "1=G\nb7, 1 2"
    assert _rekey("1=G\n4 5 6", source, accidental_mode="sharp") == "1=G\n#6, 1 2"
    assert _rekey("1=G\n4 5 6", source, accidental_mode="flat") == "1=G\nb7, 1 2"


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
                out = _rekey(
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
        out = _rekey(text, source)
        # Re-running the same change must be a fixed point.
        assert _rekey(out, text) == out
        assert "#b" not in out and "b#" not in out
