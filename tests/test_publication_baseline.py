from __future__ import annotations

import json
from pathlib import Path

from score_trans.domain.parse.jianpu_text import parse_jianpu_parts
from score_trans.services.render.main import render_scores_a4_pages
from score_trans.services.render.options import A4LayoutOptions

FIXTURES = Path(__file__).parent / "fixtures" / "publication"


def test_publication_review_corpus_is_complete_and_deterministic() -> None:
    cases = json.loads((FIXTURES / "cases.json").read_text(encoding="utf-8"))
    assert len(cases) == 6
    for case in cases:
        parts = parse_jianpu_parts(
            (FIXTURES / case["path"]).resolve().read_text(encoding="utf-8")
        )
        layout = A4LayoutOptions(measures_per_system=case["measures_per_system"])
        first = render_scores_a4_pages([part.score for part in parts], layout=layout)
        second = render_scores_a4_pages([part.score for part in parts], layout=layout)
        assert len(first) >= case.get("min_pages", 1), case["name"]
        assert [page.svg for page in first] == [page.svg for page in second]
        assert all(page.svg.startswith("<svg") for page in first)
