from __future__ import annotations

from pathlib import Path

import pytest
from score_trans.domain.jianpu_tokens import tuplet_normal_notes

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("actual_notes", "expected"),
    [(1, 1), (2, 2), (3, 2), (4, 4), (5, 4), (6, 4), (7, 4), (8, 8), (9, 8)],
)
def test_shared_tuplet_normal_notes_preserves_existing_results(
    actual_notes: int,
    expected: int,
) -> None:
    assert tuplet_normal_notes(actual_notes) == expected


def test_removed_domain_symbols_and_wrappers_are_not_present() -> None:
    source_files = {
        path: path.read_text(encoding="utf-8")
        for path in (
            ROOT / "backend/score_trans/domain/constants.py",
            ROOT / "backend/score_trans/domain/jianpu_tokens.py",
            ROOT / "backend/score_trans/domain/text_attachments.py",
            ROOT / "backend/score_trans/domain/jianpu.py",
            ROOT / "backend/score_trans/domain/parse/musicxml.py",
            ROOT / "backend/score_trans/domain/write/musicxml.py",
            ROOT / "backend/score_trans/domain/parse/jianpu_text.py",
            ROOT / "backend/score_trans/domain/write/jianpu_text.py",
            ROOT / "backend/score_trans/domain/xml_utils.py",
        )
    }
    removed = (
        "DEGREE_TO_MAJOR_OFFSET",
        "PREFIX_SLASHES",
        "first_ocr_measure_number",
        "jianpu_to_html",
        "score_to_musicxml",
        "musicxml_path_to_score(",
        "def _consume_duration_prefix",
        "def _duration_parts",
        "def _mark_token",
        "def _pitch_to_token",
        "def _indent",
    )
    for symbol in removed:
        assert not any(symbol in source for source in source_files.values()), symbol
