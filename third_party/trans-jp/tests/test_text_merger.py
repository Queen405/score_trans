from __future__ import annotations

from pathlib import Path

from trans_jp.schemas import RecognizedToken, RowResult, RowSegment
from trans_jp.text_merger import merge_rows
from trans_jp.utf16 import utf16_length


def _row(index: int, text: str, token_texts: list[str]) -> RowResult:
    tokens = [
        RecognizedToken(index=i, text=t, x=0.1 * i, w=0.05, role="note")
        for i, t in enumerate(token_texts)
    ]
    return RowResult(
        row=RowSegment(
            index=index,
            y_top=index * 100,
            y_bottom=index * 100 + 50,
            image_path=Path(f"row_{index}.png"),
            width=800,
            height=50,
        ),
        row_type="notation",
        jianpu_text=text,
        tokens=tokens,
    )


def test_merge_two_rows_with_newline():
    rows = [
        _row(0, "1 2 3 4 |", ["1", "2", "3", "4", "|"]),
        _row(1, "5 6 7 1' |", ["5", "6", "7", "1'", "|"]),
    ]
    merged, anchors = merge_rows(rows)
    assert merged == "1 2 3 4 |\n5 6 7 1' |"
    assert len(anchors) == 10


def test_anchor_source_id_format():
    rows = [_row(0, "1 2 |", ["1", "2", "|"])]
    _, anchors = merge_rows(rows)
    assert anchors[0]["source_id"] == "s0:r0:t0"
    assert anchors[2]["source_id"] == "s0:r0:t2"


def test_anchor_utf16_positions():
    rows = [_row(0, "1 2 |", ["1", "2", "|"])]
    merged, anchors = merge_rows(rows)
    assert anchors[0]["start_utf16"] == 0
    assert anchors[0]["end_utf16"] == 1
    assert anchors[1]["start_utf16"] == 2
    assert anchors[1]["end_utf16"] == 3
    assert anchors[2]["start_utf16"] == 4
    assert anchors[2]["end_utf16"] == 5
    for anchor in anchors:
        assert anchor["valid"] is True


def test_duplicate_tokens_sequential_search():
    rows = [_row(0, "1 1 1 |", ["1", "1", "1", "|"])]
    merged, anchors = merge_rows(rows)
    assert anchors[0]["start_utf16"] == 0
    assert anchors[1]["start_utf16"] == 2
    assert anchors[2]["start_utf16"] == 4
    assert anchors[3]["start_utf16"] == 6


def test_multi_char_token_span():
    rows = [_row(0, "#1 1' [1+3+5] |", ["#1", "1'", "[1+3+5]", "|"])]
    merged, anchors = merge_rows(rows)
    assert anchors[0]["end_utf16"] - anchors[0]["start_utf16"] == 2
    assert anchors[2]["end_utf16"] - anchors[2]["start_utf16"] == 7


def test_token_not_found_marked_invalid():
    rows = [_row(0, "1 2 |", ["1", "X", "|"])]
    merged, anchors = merge_rows(rows)
    assert anchors[1]["valid"] is False
    assert anchors[0]["valid"] is True
    assert anchors[2]["valid"] is True


def test_empty_row_text_skipped():
    rows = [
        _row(0, "1 2 |", ["1", "2", "|"]),
        _row(1, "", []),
        _row(2, "3 4 |", ["3", "4", "|"]),
    ]
    merged, anchors = merge_rows(rows)
    assert merged == "1 2 |\n3 4 |"
    assert len(anchors) == 6
    assert anchors[3]["source_id"] == "s0:r2:t0"


def test_utf16_length_counts_surrogates():
    assert utf16_length("abc") == 3
    assert utf16_length("春风") == 2
    assert utf16_length("𝄞") == 2


def test_utf16_anchor_with_chinese_lyrics():
    rows = [
        RowResult(
            row=RowSegment(0, 0, 50, Path("row_0.png"), 800, 50),
            row_type="lyrics",
            jianpu_text="L: 春 风",
            tokens=[
                RecognizedToken(0, "L:", 0.02, 0.04, "lyrics"),
                RecognizedToken(1, "春", 0.10, 0.04, "lyrics"),
                RecognizedToken(2, "风", 0.16, 0.04, "lyrics"),
            ],
        )
    ]
    merged, anchors = merge_rows(rows)
    assert anchors[1]["start_utf16"] == 3
    assert anchors[1]["end_utf16"] == 4
    assert anchors[2]["start_utf16"] == 5
