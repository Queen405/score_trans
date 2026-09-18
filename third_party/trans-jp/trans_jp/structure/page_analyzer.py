from __future__ import annotations

import numpy as np
from ..models.raster import RowAnalysis, SymbolCandidate
from ..raster.runs import scan_runs
from ..raster.sections import join_sections
from ..raster.filaments import detect_filaments, erase_filaments
from .baseline import fit_bands


def analyze_row(binary: np.ndarray) -> RowAnalysis:
    components = tuple(
        SymbolCandidate(f"c{i}", "ink", s.bounds, s.area)
        for i, s in enumerate(join_sections(scan_runs(binary)))
        if s.area >= 2
    )
    heights = [
        c.bounds.height
        for c in components
        if c.bounds.height >= 6
        and 0.18 <= c.bounds.width / max(1, c.bounds.height) <= 1.5
    ]
    height = float(np.median(heights)) if heights else 16.0
    horizontal = detect_filaments(binary, "horizontal", height)
    vertical = detect_filaments(binary, "vertical", height)
    # Keep short horizontal strokes inside the digits. Long rules are detached
    # only in the body mask; the original image remains available for symbols.
    body_mask = erase_filaments(binary, horizontal, height * 1.8)
    cleaned = tuple(
        SymbolCandidate(f"d{i}", "digit", s.bounds, s.area)
        for i, s in enumerate(join_sections(scan_runs(body_mask)))
        if s.area >= 2
    )
    bands = fit_bands(cleaned)
    thickness = (
        float(
            np.median([line_item.thickness for line_item in (*horizontal, *vertical)])
        )
        if horizontal or vertical
        else 1.0
    )
    return RowAnalysis(components, horizontal, vertical, bands, thickness)
