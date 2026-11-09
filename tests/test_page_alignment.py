from __future__ import annotations

from itertools import accumulate, combinations

import pytest

from score_trans.services.render.engraving.renderer import (
    _Cell,
    _PartLayout,
    _System,
    _SystemVerticalMetrics,
    _break_systems,
    _fixed_page_pitches,
    _fixed_systems_height,
    _paginate_fixed,
    _pagination_bottom,
)
from score_trans.services.render.engraving.style import PublicationStyle


def test_fixed_column_positions_survive_different_content_and_short_final_row() -> None:
    style = PublicationStyle(page_width=1200, measures_per_system=5)
    widths = [100, 200, 110, 160, 100, 190, 100, 180, 100, 150, 110, 130]
    cells = [
        _Cell(index, [], width, minimum_width=width * 0.7)
        for index, width in enumerate(widths)
    ]
    systems = _break_systems(cells, style, 1)
    assert [len(system.cells) for system in systems] == [5, 5, 2]
    template = list(accumulate(systems[0].widths))
    for system in systems[1:]:
        assert list(accumulate(system.widths)) == pytest.approx(
            template[: len(system.cells)]
        )


def test_exceptional_dense_measures_keep_boundaries_on_shared_grid() -> None:
    style = PublicationStyle(page_width=664, measures_per_system=4)
    widths = [260, 50, 50, 50, 50, 260, 50, 50]
    cells = [_Cell(index, [], width) for index, width in enumerate(widths)]
    systems = _break_systems(cells, style, 1)
    assert sum(len(system.cells) for system in systems) == len(cells)
    assert any(len(system.cells) < 4 for system in systems)
    for system in systems:
        for position in accumulate(system.widths):
            assert position / 125 == pytest.approx(round(position / 125))
        assert all(
            width >= cell.width
            for cell, width in zip(system.cells, system.widths, strict=True)
        )


def _system(height: float, *, multipart: bool = False) -> _System:
    return _System(
        [],
        [],
        height,
        parts=[_PartLayout(), _PartLayout()] if multipart else [],
        vertical=_SystemVerticalMetrics(20, 20, height - 20),
        part_gap_reductions=(0.0,) if multipart else (),
    )


def test_multi_part_pagination_is_not_capped_at_four_systems() -> None:
    style = PublicationStyle(page_height=1100, margin_top=30, measures_per_system=5)
    systems = [_system(70, multipart=True) for _ in range(12)]
    pages = _paginate_fixed(systems, style, 104)
    assert len(pages) == 2
    assert any(len(page) > 4 for page in pages)


def test_pagination_minimizes_page_count_before_distributing_whitespace() -> None:
    style = PublicationStyle(page_height=800, measures_per_system=5)
    systems = [_system(height) for height in [140, 180, 130, 200, 160, 170, 120]]
    feasible_counts = []
    for size in range(len(systems)):
        for cuts in combinations(range(1, len(systems)), size):
            ends = [*cuts, len(systems)]
            start = 0
            valid = True
            for page_index, end in enumerate(ends):
                header = (
                    style.first_system_header_height
                    if page_index == 0
                    else style.continuation_system_header_height
                )
                available = _pagination_bottom(style) - style.margin_top - header
                if (
                    _fixed_systems_height(systems[start:end], style, 104, compression=1)
                    > available
                ):
                    valid = False
                    break
                start = end
            if valid:
                feasible_counts.append(len(ends))
    assert len(_paginate_fixed(systems, style, 104)) == min(feasible_counts)


def test_populated_last_page_also_reaches_footer_protection_boundary() -> None:
    style = PublicationStyle(page_height=850, margin_top=30, measures_per_system=5)
    systems = [_system(150) for _ in range(4)]
    pitches = _fixed_page_pitches(
        systems, style, 104, page_index=1, page_count=2, show_title=True
    )
    used = (
        style.margin_top
        + style.continuation_system_header_height
        + 20
        + sum(pitches)
        + 130
    )
    assert used == pytest.approx(_pagination_bottom(style))
