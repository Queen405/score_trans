from __future__ import annotations

import xml.etree.ElementTree as ET

from score_trans.domain.jianpu import parse_jianpu_score
from score_trans.services.render.engraving.fonts import font_registry
from score_trans.services.render.main import render_scores_a4_pages


def test_publication_roles_use_real_weight_specific_outlines_and_metrics() -> None:
    score = parse_jianpu_score("title=茉莉花\n1=C\n4/4\n1 2 3 4 |")
    score.measures[0].events[0].lyric = "好"
    page = render_scores_a4_pages([score])[0]
    root = ET.fromstring(page.svg)
    expected = {"note": 500, "lyric": 500, "score-title": 700, "score-meta": 500}
    for class_name, weight in expected.items():
        node = next(
            item
            for item in root.iter()
            if class_name in item.attrib.get("class", "").split()
        )
        assert int(node.attrib["data-font-weight"]) == weight
        text = node.attrib["aria-label"]
        size = float(node.attrib["data-font-size"])
        assert font_registry().paths(text, weight)[0]
        assert font_registry().measure(text, size, weight) > 0
    assert font_registry().paths("1", 500) != font_registry().paths("1", 700)


def test_note_metrics_use_the_same_weight_as_the_svg_role() -> None:
    score = parse_jianpu_score("1=C\n4/4\n1 2 3 4 |")
    page = render_scores_a4_pages([score])[0]
    root = ET.fromstring(page.svg)
    note = next(item for item in root.iter() if item.attrib.get("class") == "note")
    weight = int(note.attrib["data-font-weight"])
    size = float(note.attrib["data-font-size"])
    assert font_registry().measure("1", size, weight) > font_registry().measure(
        "1", size, 700
    )
