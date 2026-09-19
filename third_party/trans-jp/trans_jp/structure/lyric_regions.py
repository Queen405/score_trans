from __future__ import annotations

import re
import numpy as np
from ..models.geometry import Box, Transform
from ..models.lyrics import TextRegion


def intervals(mask: np.ndarray, gap: int = 0) -> list[tuple[int, int]]:
    positions = np.flatnonzero(mask)
    if not len(positions):
        return []
    cuts = np.flatnonzero(np.diff(positions) > gap + 1) + 1
    return [(int(p[0]), int(p[-1]) + 1) for p in np.split(positions, cuts)]


def find_text_regions(binary: np.ndarray, transform: Transform) -> list[TextRegion]:
    """Page-wide fine ink bands, before logical notation rows are merged."""
    ink = binary == 0
    regions = []
    scale = max(transform.scale_x, transform.scale_y)
    for top, bottom in intervals(
        ink.sum(axis=1) >= max(2, ink.shape[1] * 0.001), max(1, round(scale))
    ):
        height = bottom - top
        if height < max(5, 3 * scale):
            continue
        for left, right in intervals(
            ink[top:bottom].any(axis=0), round(max(height * 4, ink.shape[1] * 0.07))
        ):
            local = ink[top:bottom, left:right]
            ys, xs = np.nonzero(local)
            if len(xs) < 8:
                continue
            b = Box(
                left + int(xs.min()),
                top + int(ys.min()),
                int(xs.max() - xs.min() + 1),
                int(ys.max() - ys.min() + 1),
            )
            regions.append(TextRegion(f"text:{len(regions):04d}", b, transform.box(b)))
    return regions


def language(text: str) -> str:
    chinese = bool(re.search(r"[㐀-鿿]", text))
    english = bool(re.search(r"[a-zA-Z]", text))
    return (
        "mixed"
        if chinese and english
        else "zh"
        if chinese
        else "en"
        if english
        else "unknown"
    )


def text_units(text: str) -> list[str]:
    # Punctuation stays attached to its preceding character/word.
    units = re.findall(r"[㐀-鿿]|[A-Za-z]+(?:['’-][A-Za-z]+)*|[0-9]+|[^\s]", text)
    result = []
    for unit in units:
        if re.fullmatch(r"[^\w㐀-鿿]+", unit) and result:
            result[-1] += unit
        else:
            result.append(unit)
    return result


def word_boxes(binary: np.ndarray, region: TextRegion, text: str) -> list[Box]:
    """Use measured ink gaps only; no equal-width boxes from text length."""
    b = region.bounds_work
    x, y, w, h = map(int, (b.x, b.y, b.width, b.height))
    ink = binary[y : y + h, x : x + w] == 0
    spans = intervals(ink.any(axis=0))
    if not spans:
        return []
    # Join disconnected Chinese radicals or Latin letters; conservative alignment
    # below rejects any disagreement with the independently read line.
    gap = max(1, round(h * (0.18 if language(text) in ("zh", "mixed") else 0.20)))
    groups = []
    for a, z in spans:
        if (
            groups
            and a - groups[-1][1] <= gap
            and (
                language(text) == "en"
                or z - groups[-1][0] <= h * 1.2
                or z - a < h * 0.3
            )
        ):
            groups[-1] = (groups[-1][0], z)
        else:
            groups.append((a, z))
    result = []
    for a, z in groups:
        ys, xs = np.nonzero(ink[:, a:z])
        if len(xs):
            result.append(
                Box(
                    x + a + int(xs.min()),
                    y + int(ys.min()),
                    int(xs.max() - xs.min() + 1),
                    int(ys.max() - ys.min() + 1),
                )
            )
    return result
