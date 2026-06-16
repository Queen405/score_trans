from __future__ import annotations

from ..models.layout import MeasureLayout
from ..options import RenderOptions


def _layout_rows(
    layouts: list[MeasureLayout], options: RenderOptions
) -> list[list[MeasureLayout]]:
    available = options.width - options.margin * 2
    if not layouts:
        return []
    if options.compact_measure_layout:
        return _layout_compact_rows(layouts, available, options)
    rows: list[list[MeasureLayout]] = []
    row: list[MeasureLayout] = []
    used = 0.0
    for layout in layouts:
        layout.width = min(
            max(layout.width, options.min_measure_width),
            min(options.max_measure_width, available),
        )
        if row and used + layout.width > available:
            _justify_row(row, available, is_last=False)
            rows.append(row)
            row = []
            used = 0.0
        row.append(layout)
        used += layout.width
    if row:
        _justify_row(row, available, is_last=True)
        rows.append(row)
    return rows


def _layout_compact_rows(
    layouts: list[MeasureLayout],
    available: float,
    options: RenderOptions,
) -> list[list[MeasureLayout]]:
    rows: list[list[MeasureLayout]] = []
    row: list[MeasureLayout] = []
    for layout in layouts:
        _normalize_compact_measure_width(layout, available, options)
        candidate = [*row, layout]
        if row and not _compact_row_fits(candidate, available):
            _fit_compact_row(row, available, is_last=False)
            rows.append(row)
            row = []
        row.append(layout)
    if row:
        _fit_compact_row(row, available, is_last=True)
        rows.append(row)
    return rows


def _normalize_compact_measure_width(
    layout: MeasureLayout,
    available: float,
    options: RenderOptions,
) -> None:
    max_width = min(float(options.max_measure_width), available)
    ideal = layout.ideal_width or layout.width
    minimum = layout.min_width or min(layout.width, ideal)
    layout.ideal_width = min(max_width, max(float(options.min_measure_width), ideal))
    layout.min_width = min(
        layout.ideal_width, max(float(options.min_measure_width), minimum)
    )
    layout.width = layout.ideal_width


def _row_min_total(row: list[MeasureLayout]) -> float:
    return sum(measure.min_width or measure.width for measure in row)


def _compact_row_fits(row: list[MeasureLayout], available: float) -> bool:
    ideal_total = sum(measure.ideal_width or measure.width for measure in row)
    if ideal_total <= available:
        return True
    min_total = _row_min_total(row)
    if min_total > available:
        return False
    return (ideal_total - available) / ideal_total <= 0.04


def _fit_compact_row(
    row: list[MeasureLayout], available: float, *, is_last: bool
) -> None:
    ideal_total = sum(measure.ideal_width or measure.width for measure in row)
    min_total = _row_min_total(row)
    if ideal_total > available and min_total <= available:
        shrink = ideal_total - available
        flex_total = sum(
            max(
                0.0,
                (measure.ideal_width or measure.width)
                - (measure.min_width or measure.width),
            )
            for measure in row
        )
        for measure in row:
            ideal = measure.ideal_width or measure.width
            minimum = measure.min_width or measure.width
            flex = max(0.0, ideal - minimum)
            measure.width = (
                ideal - shrink * (flex / flex_total) if flex_total else minimum
            )
        return

    for measure in row:
        measure.width = measure.ideal_width or measure.width
    _justify_row(row, available, is_last=is_last)


def _justify_row(row: list[MeasureLayout], available: float, *, is_last: bool) -> None:
    total = sum(measure.width for measure in row)
    if total <= 0:
        return
    limit = 1.06 if is_last else 1.18
    factor = min(limit, available / total)
    if factor <= 1.02:
        return
    for measure in row:
        measure.width *= factor
