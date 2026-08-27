from __future__ import annotations

from score_trans.domain.rekey import rekey_text


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
    assert out == (
        "1=G\n4/4\n4, 5, 6, b7, | 1 2 3 4,\nL: 春 夏 秋 冬\n$3:2;4, 5, 6,$"
    )


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
