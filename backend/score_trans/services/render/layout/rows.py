from __future__ import annotations

from ..models.layout import MeasureLayout
from ..options import RenderOptions


def _layout_rows(layouts: list[MeasureLayout], options: RenderOptions) -> list[list[MeasureLayout]]:
    available = options.width - options.margin * 2
    if not layouts:
        return []
    rows: list[list[MeasureLayout]] = []
    row: list[MeasureLayout] = []
    used = 0.0
    for layout in layouts:
        layout.width = min(max(layout.width, options.min_measure_width), min(options.max_measure_width, available))
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
