from __future__ import annotations

import xml.etree.ElementTree as ET

from score_trans.domain.jianpu import parse_jianpu_score
from score_trans.services.render.engraving.renderer import PublicationRenderer


def _parts(count: int = 2):
    parts = []
    for index in range(count):
        score = parse_jianpu_score("1=C\n4/4\n1 2 3 4 | 5 6 7 1 |")
        score.part_index = index
        score.part_count = count
        score.part_name = f"声部 {index + 1}"
        parts.append(score)
    return parts


def test_multi_part_numbers_labels_and_barlines_are_systemic() -> None:
    page = PublicationRenderer().render_scores(_parts(), title="层次")[0]
    root = ET.fromstring(page.svg)
    numbers = [
        node
        for node in root.iter()
        if "measure-no" in node.attrib.get("class", "").split()
    ]
    names = [
        node
        for node in root.iter()
        if "part-name" in node.attrib.get("class", "").split()
    ]
    measures = [node for node in root.iter() if node.attrib.get("class") == "measure"]
    assert len(numbers) == 2
    assert len(names) == 2
    assert len(measures) == 3
    assert all(node.attrib["x1"] == node.attrib["x2"] for node in measures)


def test_continuation_pages_use_running_title_and_no_repeated_part_names() -> None:
    parts = []
    for index in range(2):
        score = parse_jianpu_score("1=C\n4/4\n" + "1 2 3 4 | " * 18)
        score.part_index = index
        score.part_count = 2
        score.part_name = f"声部 {index + 1}"
        parts.append(score)
    pages = PublicationRenderer().render_scores(
        parts, title="长曲", page_width=900, page_height=700
    )
    assert len(pages) > 1
    assert 'class="part-name"' in pages[0].svg
    assert all('class="part-name"' not in page.svg for page in pages[1:])
    assert all('class="score-title"' not in page.svg for page in pages[1:])
    assert all('class="continuation-title"' in page.svg for page in pages[1:])
