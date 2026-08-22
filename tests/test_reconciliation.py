from __future__ import annotations

import logging

import pytest
from score_trans.domain.reconciliation import (
    anchorable_source_ids,
    unanchored_source_ids_by_page,
)
from score_trans.exec.pipeline.actions import _warn_unanchored_source_elements
from score_trans.models.provenance.schemas import SourceMap, TextAnchor
from score_trans.services.overlay.overlay_service import find_unanchored_source_ids


def _source_map(shapes: list[tuple[str, str]]) -> SourceMap:
    elements = [
        {
            "source_id": source_id,
            "inter_id": index + 1,
            "shape": shape,
            "grade": 0.9,
            "bounds": {"x": 0, "y": 0, "width": 10, "height": 10},
            "hit_path": "M0 0",
            "musicxml_locator": {"attribute": "id", "contains": source_id},
        }
        for index, (source_id, shape) in enumerate(shapes)
    ]
    return SourceMap.model_validate(
        {
            "version": 1,
            "sheets": [
                {
                    "sheet_index": 1,
                    "width": 100,
                    "height": 200,
                    "overlay_file": "overlay_sheet1.png",
                    "elements": elements,
                }
            ],
        }
    )


def test_unanchored_diff_returns_missing_ids() -> None:
    missing = unanchored_source_ids_by_page(
        ["s1:i1", "s1:i2", "s1:i3"],
        {"s1:i1"},
    )

    assert missing == {1: ["s1:i2", "s1:i3"]}


def test_unanchored_diff_empty_when_fully_anchored() -> None:
    assert unanchored_source_ids_by_page(["s1:i1"], {"s1:i1"}) == {}
    assert unanchored_source_ids_by_page([], {"s1:i1"}) == {}
    assert unanchored_source_ids_by_page([], set()) == {}


def test_unanchored_diff_groups_by_page_and_deduplicates() -> None:
    missing = unanchored_source_ids_by_page(
        ["s2:i5", "s1:i9", "s2:i3", "s2:i5", "s10:i1"],
        set(),
    )

    assert missing == {1: ["s1:i9"], 2: ["s2:i3", "s2:i5"], 10: ["s10:i1"]}


def test_unanchored_diff_parses_batch_prefixed_ids() -> None:
    missing = unanchored_source_ids_by_page(["p3|s2:i5", "p1|s7:i2"], {"p1|s7:i2"})

    assert missing == {2: ["p3|s2:i5"]}


def test_unanchored_diff_groups_unparseable_ids_under_page_zero() -> None:
    missing = unanchored_source_ids_by_page(["note-x", "s1:i1"], set())

    assert missing == {0: ["note-x"], 1: ["s1:i1"]}


def test_anchorable_source_ids_excludes_structural_shapes() -> None:
    source_map = _source_map(
        [
            ("s1:i1", "NOTEHEAD_BLACK"),
            ("s1:i2", "QUARTER_REST"),
            ("s1:i3", "SHARP"),
            ("s1:i4", "AUGMENTATION_DOT"),
            ("s1:i5", "SLUR"),
            ("s1:i6", "DYNAMICS_F"),
            ("s1:i7", "FERMATA"),
            ("s1:i8", "G_CLEF"),
            ("s1:i9", "F_CLEF_8VB"),
            ("s1:i10", "C_CLEF"),
            ("s1:i11", "PERCUSSION_CLEF"),
            ("s1:i12", "KEY_SHARP_2"),
            ("s1:i13", "KEY_CANCEL"),
            ("s1:i14", "TIME_FOUR_FOUR"),
            ("s1:i15", "TIME_SIX"),
            ("s1:i16", "TUPLET_THREE"),
            ("s1:i17", "TUPLET_SIX"),
        ]
    )

    assert anchorable_source_ids(source_map) == [
        "s1:i1",
        "s1:i2",
        "s1:i3",
        "s1:i4",
        "s1:i5",
        "s1:i6",
        "s1:i7",
    ]


def test_find_unanchored_source_ids_end_to_end() -> None:
    source_map = _source_map(
        [
            ("s1:i1", "NOTEHEAD_BLACK"),
            ("s1:i2", "NOTEHEAD_BLACK"),
            ("s1:i3", "G_CLEF"),
        ]
    )

    assert find_unanchored_source_ids(source_map, {"s1:i1"}) == {1: ["s1:i2"]}
    assert find_unanchored_source_ids(source_map, {"s1:i1", "s1:i2"}) == {}


def test_warn_unanchored_source_elements_logs_per_page(
    caplog: pytest.LogCaptureFixture,
) -> None:
    source_map = _source_map(
        [
            ("s1:i1", "NOTEHEAD_BLACK"),
            ("s1:i2", "NOTEHEAD_BLACK"),
            ("s1:i3", "G_CLEF"),
        ]
    )
    anchors = [TextAnchor(source_id="s1:i1", start_utf16=0, end_utf16=1, role="note")]

    with caplog.at_level(logging.WARNING):
        _warn_unanchored_source_elements(source_map, anchors)

    messages = [record.getMessage() for record in caplog.records]
    assert any(
        "第 1 页有 1 个识别符号未能进入乐谱，这些音符在五线谱上不可点击" in message
        for message in messages
    )
    assert all("s1:i3" not in message for message in messages)


def test_warn_unanchored_source_elements_silent_when_aligned(
    caplog: pytest.LogCaptureFixture,
) -> None:
    source_map = _source_map([("s1:i1", "NOTEHEAD_BLACK")])
    anchors = [TextAnchor(source_id="s1:i1", start_utf16=0, end_utf16=1, role="note")]

    with caplog.at_level(logging.WARNING):
        _warn_unanchored_source_elements(source_map, anchors)
        _warn_unanchored_source_elements(None, [])

    assert not caplog.records
