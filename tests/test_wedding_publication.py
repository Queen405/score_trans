from __future__ import annotations

from itertools import combinations
from pathlib import Path

import pytest

from score_trans.domain.parse.jianpu_text import parse_jianpu_parts
from score_trans.domain.playback_timeline import score_parts
from score_trans.services.render.main import _a4_renderer
from score_trans.services.render.options import A4LayoutOptions, RenderOptions
from score_trans.services.render.engraving.renderer import (
    _build_cells,
    _break_systems,
    _fixed_page_pitches,
    _fixed_systems_height,
    _part_groups,
    _part_vertical_envelope,
    _pagination_bottom,
    _solve_fixed_pagination,
)

FIXTURE = Path(__file__).parent / "fixtures/publication/wedding-three-part.jianpu"


@pytest.mark.parametrize("count", [3, 4, 5])
def test_real_score_fixed_pagination_packs_visible_ink_and_respects_footer(
    count: int,
) -> None:
    scores = [
        part.score for part in parse_jianpu_parts(FIXTURE.read_text(encoding="utf-8"))
    ]
    parts = score_parts(scores)
    assert [sum(len(score.measures) for score in part) for part in parts] == [187] * 3
    renderer = _a4_renderer(
        RenderOptions(title="结婚记"),
        A4LayoutOptions(
            measures_per_system=count,
            part_gap_percent=0,
            system_gap_percent=20,
            break_beams_at_beat=True,
        ),
    )
    style = renderer.style
    systems = _break_systems(
        _build_cells(parts, style), style, len(parts), part_groups=_part_groups(parts)
    )
    minimum, pages = _solve_fixed_pagination(systems, style, show_title=True)
    assert sum(len(page) for page in pages) == len(systems)
    assert all(len(system.cells) <= count for system in systems)
    assert len(pages[-1]) >= 2
    if count == 5:
        assert len(pages) <= 9
        assert any(len(page) >= 5 for page in pages)
        template = systems[0].widths
        for system in systems:
            assert system.widths == pytest.approx(template[: len(system.cells)])
    for page_index, page in enumerate(pages):
        header = (
            style.first_system_header_height
            if page_index == 0
            else style.continuation_system_header_height
        )
        natural_height = _fixed_systems_height(page, style, minimum)
        assert (
            style.margin_top + header + natural_height
            <= _pagination_bottom(style) + 1e-6
        )
        pitches = _fixed_page_pitches(
            page,
            style,
            minimum,
            page_index=page_index,
            page_count=len(pages),
            show_title=True,
        )
        first, last = page[0].vertical, page[-1].vertical
        used = style.margin_top + header + first.above + sum(pitches) + last.below
        assert used <= _pagination_bottom(style) + 1e-6
        if count == 5:
            # Populated pages use the available height, including the last page.
            assert _pagination_bottom(style) - used < 1e-4
        for system in page:
            bounds = [
                _part_vertical_envelope(system, i, style, show_measure_numbers=True)
                for i in range(3)
            ]
            gaps = [
                system.parts[i + 1].offset
                + bounds[i + 1][0]
                - system.parts[i].offset
                - bounds[i][1]
                for i in range(2)
            ]
            assert (
                style.note_size * 0.65 - 1e-6
                <= gaps[0]
                <= style.note_size * 0.85 + 1e-6
            )
            assert (
                style.note_size * 0.30 - 1e-6
                <= gaps[1]
                <= style.note_size * 0.45 + 1e-6
            )
            assert gaps[0] > gaps[1]
    before = [[id(system) for system in page] for page in pages]
    offsets = [[part.offset for part in system.parts] for system in systems]
    _floor, repeated = _solve_fixed_pagination(systems, style, show_title=True)
    assert before == [[id(system) for system in page] for page in repeated]
    for system, previous in zip(systems, offsets, strict=True):
        assert [part.offset for part in system.parts] == pytest.approx(previous)


def test_real_score_output_keeps_shared_onsets_and_has_no_staff_collisions() -> None:
    scores = [
        part.score for part in parse_jianpu_parts(FIXTURE.read_text(encoding="utf-8"))
    ]
    renderer = _a4_renderer(
        RenderOptions(title="结婚记"),
        A4LayoutOptions(
            measures_per_system=5,
            part_gap_percent=0,
            system_gap_percent=20,
            break_beams_at_beat=True,
        ),
    )
    pages = renderer.render_scores(scores, title="结婚记", initial_measure_number=1)
    numbers = []
    barline_columns = set()
    for page in pages:
        assert not any(
            issue["kind"]
            in {
                "page-overflow",
                "measure-overflow",
                "event-overlap",
                "geometry-overlap",
            }
            for issue in page.scene.geometry_issues
        )
        notes = [
            node
            for node in page.scene.nodes
            if "playback-note" in str(node.attrs.get("class", "")).split()
        ]
        by_tick = {}
        for note in notes:
            digit = next(
                child for child in note.children if child.attrs.get("class") == "note"
            )
            tick = note.attrs["data-playback-tick"]
            position = float(digit.attrs["x"])
            assert position == pytest.approx(by_tick.setdefault(tick, position))
        for left, right in combinations(notes, 2):
            if left.attrs["data-part-index"] == right.attrs["data-part-index"]:
                continue
            x1, y1, w1, h1 = map(float, str(left.attrs["data-bbox"]).split())
            x2, y2, w2, h2 = map(float, str(right.attrs["data-bbox"]).split())
            assert min(x1 + w1, x2 + w2) <= max(x1, x2) or min(y1 + h1, y2 + h2) <= max(
                y1, y2
            )
        connectors = [
            node
            for node in page.scene.nodes
            if node.attrs.get("class") == "system-connector"
        ]
        braces = [
            node
            for node in page.scene.nodes
            if node.attrs.get("class") == "system-bracket group-brace"
        ]
        assert len(connectors) == len(braces)
        for node in page.scene.nodes:
            if node.attrs.get("class") == "measure-no":
                numbers.append(int(node.text))
            if node.attrs.get("class") == "measure":
                barline_columns.add(round(float(node.attrs["x1"]), 6))
    assert numbers == list(range(1, 188))
    assert len(barline_columns) == 5
