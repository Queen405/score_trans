from __future__ import annotations

import math
from ..models.contracts import RecognizedToken
from ..models.notation import Notation
from ..models.raster import SymbolCandidate


def align_sequence(
    tokens: list[tuple[RecognizedToken, Notation]],
    candidates: list[SymbolCandidate],
    width: int,
    height: float,
) -> list[tuple[int, int]]:
    """Conservative v1 replay. Missing positions are never invented or stretched."""
    choices = {}
    distances = {}
    for i, (token, note) in enumerate(tokens):
        x, w = token.x, token.w
        if (
            x is None
            or w is None
            or not all(math.isfinite(v) for v in (x, w))
            or not 0 <= x < 1
            or w <= 0
            or x + w > 1 + 1e-9
        ):
            continue
        center = (x + w / 2) * width
        if note.extensions:
            center = x * width + min(w * width, height * 0.7) / 2
        ranked = sorted(
            (abs(center - c.bounds.cx) / max(height, 1), j)
            for j, c in enumerate(candidates)
            if (note.kind == "barline") == (c.kind == "barline")
        )
        for distance, j in ranked:
            distances[i, j] = distance
        if (
            ranked
            and ranked[0][0] <= 0.6
            and (len(ranked) == 1 or ranked[1][0] - ranked[0][0] >= 0.5)
        ):
            choices[i] = ranked[0][1]
    pairs = []
    for i, j in choices.items():
        competitors = sorted(
            (distance, other)
            for (other, candidate), distance in distances.items()
            if candidate == j
        )
        if competitors[0][1] == i and (
            len(competitors) == 1 or competitors[1][0] - competitors[0][0] >= 0.5
        ):
            pairs.append((i, j))
    conflicts = set()
    for k, (i, j) in enumerate(pairs):
        for other_i, other_j in pairs[k + 1 :]:
            if other_j <= j:
                conflicts.update((i, other_i))
    return [(i, j) for i, j in pairs if i not in conflicts]
