from __future__ import annotations

import numpy as np
from ..models.geometry import Box
from ..raster.runs import scan_runs
from ..raster.sections import join_sections


def detect_metadata_regions(binary: np.ndarray) -> tuple[Box, ...]:
    """Propose tight key-declaration windows around two measured '=' strokes.

    These are visual evidence regions, not detected key or meter values.
    Numbered notation underlines are filtered by stroke length and paired extent;
    remaining false candidates must still be rejected by local transcription.
    """
    height, width = binary.shape
    strokes = [
        s.bounds
        for s in join_sections(scan_runs(binary))
        if 2 <= s.bounds.width <= max(16, width * 0.025)
        and s.bounds.height <= max(2, s.bounds.width * 0.35)
        and s.bounds.width >= s.bounds.height * 2.5
    ]
    regions: list[Box] = []
    for i, a in enumerate(strokes):
        for b in strokes[i + 1 :]:
            if abs(a.cx - b.cx) > max(a.width, b.width) * 0.2:
                continue
            if not 0.7 <= a.width / max(b.width, 1) <= 1.4:
                continue
            gap = abs(a.cy - b.cy)
            if not max(a.height, b.height) < gap < max(a.width, b.width) * 0.85:
                continue
            glyph_height = max(a.width, b.width) * 2.2
            proposal = Box(
                a.x - glyph_height * 1.1,
                min(a.y, b.y) - glyph_height,
                glyph_height * 5.8,
                glyph_height * 3,
            ).clip(width, height)
            if not any(
                abs(p.cx - proposal.cx) < glyph_height
                and abs(p.cy - proposal.cy) < glyph_height
                for p in regions
            ):
                regions.append(proposal)
    return tuple(sorted(regions, key=lambda b: (b.y, b.x)))
