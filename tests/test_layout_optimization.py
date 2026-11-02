from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from itertools import combinations

import pytest

from score_trans.models.common.errors import RenderError
from score_trans.models.score import Event, JianpuPitch, Measure
from score_trans.services.render.engraving.renderer import (
    _Cell,
    _System,
    _boundary_penalties,
    _break_systems,
    _optimal_system_ends,
    _paginate,
    _pagination_bottom,
)
from score_trans.services.render.engraving.style import PublicationStyle


def _cells(widths: list[float]) -> list[_Cell]:
    return [_Cell(i, [], width) for i, width in enumerate(widths)]


def test_dynamic_program_matches_exhaustive_partition_cost() -> None:
    style = PublicationStyle(page_width=664)  # 500 units of content
    widths = [210, 110, 180, 130, 250, 120, 170]
    cells = _cells(widths)

    def cost(ends: list[int]) -> float:
        total = 0.0
        start = 0
        for end in ends:
            ratio = sum(widths[start:end]) / style.content_width
            if ratio > style.max_system_overflow_ratio and end - start > 1:
                return float("inf")
            if end != len(cells) or ratio >= style.last_line_fill_threshold:
                total += abs(1 - ratio) ** 3 * 1000
            if end - start == 1 and ratio < 0.6:
                total += style.singleton_system_penalty
            start = end
        return total

    all_costs = [
        cost([*cuts, len(cells)])
        for size in range(len(cells))
        for cuts in combinations(range(1, len(cells)), size)
    ]
    ends = _optimal_system_ends(cells, style)
    assert cost(ends) == pytest.approx(min(all_costs))
    assert ends == _optimal_system_ends(cells, style)


def test_forced_breaks_override_optimization() -> None:
    cells = _cells([100] * 7)
    cells[2].forced_system = True
    cells[5].forced_page = True
    ends = _optimal_system_ends(cells, PublicationStyle())
    assert 2 in ends and 5 in ends
    assert ends[-1] == 7


@pytest.mark.parametrize("kind", ["slur", "tie", "slide"])
def test_span_penalty_persists_until_stop_and_reopens(kind: str) -> None:
    style = PublicationStyle()
    events = [Event("note", Fraction(1), [JianpuPitch(1)]) for _ in range(5)]
    setattr(events[0], f"{kind}_start", True)
    setattr(events[2], f"{kind}_stop", True)
    setattr(events[2], f"{kind}_start", True)
    setattr(events[4], f"{kind}_stop", True)
    cells = [
        _Cell(i, [Measure(str(i), events=[event])], 150)
        for i, event in enumerate(events)
    ]
    penalties = _boundary_penalties(cells, style)
    penalty = style.slur_break_penalty if kind == "slur" else style.tie_break_penalty
    assert penalties == [0, penalty, penalty, penalty, penalty, 0]


def test_closed_span_and_lyric_punctuation_do_not_penalize_boundary() -> None:
    first = Event("note", Fraction(1), [JianpuPitch(1)], slur_start=True, lyric="一")
    last = Event("note", Fraction(1), [JianpuPitch(2)], slur_stop=True, lyric="句。")
    cell = _Cell(0, [Measure("1", events=[first, last])], 150)
    assert _boundary_penalties([cell], PublicationStyle()) == [0, 0]


def test_footer_limit_cannot_be_erased_by_tolerance() -> None:
    style = PublicationStyle()
    normal = _pagination_bottom(style)
    huge = _pagination_bottom(replace(style, pagination_bottom_allowance=10000))
    assert huge <= style.page_height - style.footer_reserved
    assert huge < style.page_height - 24 - style.footer_clearance
    assert normal <= huge


def test_paginated_systems_respect_footer_and_forced_pages() -> None:
    style = PublicationStyle(page_height=650)
    systems = [_System([], [], 110) for _ in range(9)]
    systems[4].force_page_before = True
    pages = _paginate(systems, style)
    assert [s for page in pages for s in page] == systems
    assert any(page[0] is systems[4] for page in pages)
    for index, page in enumerate(pages):
        header = (
            style.title_block_height if index == 0 else style.continuation_header_height
        )
        bottom = style.margin_top + header + sum(s.height for s in page)
        bottom += (len(page) - 1) * style.system_gap
        assert bottom <= _pagination_bottom(style)


def test_no_title_uses_continuation_header_for_pagination() -> None:
    style = PublicationStyle(page_height=500)
    systems = [_System([], [], 140), _System([], [], 140)]
    assert len(_paginate(systems, style, show_title=False)) == 1
    assert len(_paginate(systems, style, show_title=True)) == 2


def test_oversized_system_fails_instead_of_overflowing_footer() -> None:
    with pytest.raises(RenderError, match="超出页面"):
        _paginate([_System([], [], 2000)], PublicationStyle())


@pytest.mark.parametrize("count", [3, 4, 5])
def test_fixed_system_uses_aligned_columns_for_full_and_short_rows(count: int) -> None:
    style = PublicationStyle(page_width=664, measures_per_system=count)
    cells = _cells([100] * (count + 2))

    systems = _break_systems(cells, style, 1)

    assert [len(system.cells) for system in systems] == [count, 2]
    column_width = style.content_width / count
    for system in systems:
        assert system.widths == pytest.approx([column_width] * len(system.cells))


def test_fixed_system_honors_forced_breaks_without_rejustifying_short_row() -> None:
    style = PublicationStyle(page_width=664, measures_per_system=4)
    cells = _cells([100] * 9)
    cells[2].forced_system = True
    cells[6].forced_page = True

    systems = _break_systems(cells, style, 1)

    assert [len(system.cells) for system in systems] == [2, 4, 3]
    assert systems[2].force_page_before is True
    assert all(width == 125 for system in systems for width in system.widths)


def test_fixed_system_width_protection_keeps_original_grid() -> None:
    style = PublicationStyle(page_width=664, measures_per_system=4)
    cells = _cells([130] * 8)

    systems = _break_systems(cells, style, 1)

    assert [len(system.cells) for system in systems] == [3, 3, 2]
    assert all(width == 125 for system in systems for width in system.widths)


def test_fixed_system_expands_dense_measure_across_aligned_columns() -> None:
    style = PublicationStyle(page_width=664, measures_per_system=4)

    systems = _break_systems(_cells([100, 200, 100]), style, 1)

    assert len(systems) == 1
    assert systems[0].widths == pytest.approx([125, 250, 125])


def test_fixed_system_gives_extreme_measure_a_full_row_instead_of_failing() -> None:
    style = PublicationStyle(page_width=664, measures_per_system=4)

    systems = _break_systems(_cells([1000, 100]), style, 1)

    assert [len(system.cells) for system in systems] == [1, 1]
    assert systems[0].widths == pytest.approx([500])
    assert systems[1].widths == pytest.approx([125])
