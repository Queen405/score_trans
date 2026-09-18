from __future__ import annotations

from dataclasses import replace
import numpy as np
from ..models.candidates import CandidateRegistry, LocatedCandidate
from ..models.geometry import Box
from ..models.raster import RowAnalysis
from ..raster.projections import barline_candidates


def _overlap(a: Box, b: Box) -> float:
    return max(0, min(a.right, b.right) - max(a.x, b.x)) * max(
        0, min(a.bottom, b.bottom) - max(a.y, b.y)
    )


def build_registry(
    binary: np.ndarray, analysis: RowAnalysis, row_index: int
) -> CandidateRegistry:
    candidates = []
    bars = {}
    for band_id, band in enumerate(analysis.bands):
        # A tiny aligned band immediately above/below full-size digits is a
        # dot/apostrophe band, not another voice. Keep it in raw components.
        if any(
            other.digit_height > band.digit_height * 2.2
            and sum(
                any(
                    abs(c.bounds.cx - d.bounds.cx) < other.digit_height * 0.8
                    and abs(c.bounds.cy - d.bounds.cy) < other.digit_height * 2
                    for d in other.candidates
                )
                for c in band.candidates
            )
            >= max(1, len(band.candidates) * 0.7)
            for other in analysis.bands
            if other is not band
        ):
            continue
        for component in band.candidates:
            b = component.bounds
            candidates.append(
                LocatedCandidate(
                    "",
                    "digit",
                    b,
                    (band_id,),
                    (component.candidate_id,),
                    ambiguous=b.width > band.digit_height * 1.35,
                )
            )
        lines = sorted(
            barline_candidates(binary, band, analysis.vertical),
            key=lambda line: line.bounds.cx,
        )
        groups = []
        for line in lines:
            if (
                groups
                and line.bounds.x - groups[-1][-1].bounds.right
                < band.digit_height * 0.4
            ):
                groups[-1].append(line)
            else:
                groups.append([line])
        for group in groups:
            key = tuple(group)
            if key not in bars:
                b = group[0].bounds
                for line in group[1:]:
                    b = b.union(line.bounds)
                bars[key] = LocatedCandidate(
                    "", "barline", b, (band_id,), (), lines=key
                )
            else:
                bars[key] = replace(bars[key], band_ids=(*bars[key].band_ids, band_id))
        for line in analysis.horizontal:
            b = line.bounds
            h = band.digit_height
            if (
                abs(b.cy - (band.baseline.y_at(b.cx) - h / 2)) < h * 0.3
                and h * 0.3 < b.width < h * 1.5
                and not any(_overlap(b, c.bounds) > 0 for c in band.candidates)
            ):
                candidates.append(
                    LocatedCandidate("", "extension", b, (band_id,), (), lines=(line,))
                )
    candidates.extend(bars.values())
    candidates.sort(
        key=lambda c: (min(c.band_ids), c.bounds.cx, c.kind, c.bounds.y, c.bounds.width)
    )
    candidates = [
        replace(c, candidate_id=f"r{row_index:04d}:c{i:04d}")
        for i, c in enumerate(candidates)
    ]
    result = []
    for c in candidates:
        conflicts = tuple(
            other.candidate_id
            for other in candidates
            if other != c
            and (
                _overlap(c.bounds, other.bounds)
                / max(
                    1,
                    min(
                        c.bounds.width * c.bounds.height,
                        other.bounds.width * other.bounds.height,
                    ),
                )
                > 0.65
            )
        )
        result.append(replace(c, conflicts=conflicts))
    return CandidateRegistry(row_index, binary.shape[1], binary.shape[0], tuple(result))
