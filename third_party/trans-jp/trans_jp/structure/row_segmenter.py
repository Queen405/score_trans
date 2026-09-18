from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from ..models.contracts import RowSegment
from ..models.geometry import Transform, Box

_SMOOTH_WINDOW = 5
_CONTENT_RATIO = 0.05
_MIN_BAND_HEIGHT = 2
_GROUP_GAP_RATIO = 0.8
_MIN_GROUP_GAP = 12
_PAD_RATIO = 0.25
_MIN_PAD = 6
_MIN_LINE_HEIGHT = 12


def segment(
    binary: np.ndarray,
    original: Image.Image,
    rows_dir: Path,
    *,
    smooth_window: int = _SMOOTH_WINDOW,
    content_ratio: float = _CONTENT_RATIO,
    min_band_height: int = _MIN_BAND_HEIGHT,
    group_gap_ratio: float = _GROUP_GAP_RATIO,
    min_group_gap: int = _MIN_GROUP_GAP,
    pad_ratio: float = _PAD_RATIO,
    min_pad: int = _MIN_PAD,
    min_line_height: int = _MIN_LINE_HEIGHT,
    coord_scale: float = 1.0,
    transform: Transform | None = None,
) -> list[RowSegment]:
    """Segment a binarized image into logical notation lines.

    Two stages:

    1. Detect fine-grained ink bands via horizontal projection. Bands are
       deliberately thin: digit glyphs, duration underlines, octave dots,
       dynamics and lyrics are separate bands at this stage.
    2. Group vertically adjacent bands into one logical line when the gap is
       smaller than an adaptive threshold derived from the median band
       height. A notation line therefore keeps its underlines (durations),
       dots (octaves) and nearby dynamics; lyrics lines, separated by larger
       gaps, stay on their own. Each line is then padded symmetrically, with
       padding clipped at the midpoint of the gap to neighbouring lines so
       slur arcs above digits are preserved without double-cropping.

    ``binary``/``original`` are the *work* image (possibly upscaled).
    Row crops are taken from the work image; ``RowSegment.y_top``/``y_bottom``
    are stored in original-image coordinates (divided by ``coord_scale``),
    which is the coordinate space of the source map and overlay.
    """
    if binary.size == 0:
        return []
    row_sums = np.sum(binary == 0, axis=1).astype(np.float64)
    kernel = np.ones(smooth_window) / smooth_window
    row_sums = np.convolve(row_sums, kernel, mode="same")
    peak = float(row_sums.max())
    if peak <= 0:
        return []
    threshold = peak * content_ratio

    bands = _content_intervals(row_sums, threshold)
    bands = [b for b in bands if b[1] - b[0] >= min_band_height]
    if not bands:
        return []

    lines = _group_bands(bands, group_gap_ratio, min_group_gap)
    lines = [ln for ln in lines if ln[1] - ln[0] >= min_line_height]
    lines = _pad_lines(lines, binary.shape[0], pad_ratio, min_pad)

    transform = transform or Transform(coord_scale, coord_scale)
    img_width = original.size[0]
    rows: list[RowSegment] = []
    for index, (y_top, y_bottom) in enumerate(lines):
        image_path = rows_dir / f"row_{index}.png"
        source_box = transform.box(Box(0, y_top, img_width, y_bottom - y_top))
        rows.append(
            RowSegment(
                index=index,
                y_top=int(source_box.y + 0.5),
                y_bottom=int(source_box.bottom + 0.5),
                image_path=image_path,
                width=img_width,
                height=y_bottom - y_top,
                work_y_top=y_top,
                transform=transform,
            )
        )
    return rows


def _content_intervals(row_sums: np.ndarray, threshold: float) -> list[tuple[int, int]]:
    above = row_sums > threshold
    intervals: list[tuple[int, int]] = []
    start: int | None = None
    for i, is_content in enumerate(above):
        if is_content and start is None:
            start = i
        elif not is_content and start is not None:
            intervals.append((start, i))
            start = None
    if start is not None:
        intervals.append((start, len(above)))
    return intervals


def _group_bands(
    bands: list[tuple[int, int]], group_gap_ratio: float, min_group_gap: int
) -> list[list[int]]:
    heights = sorted(b - a for a, b in bands)
    median_height = heights[len(heights) // 2]
    group_gap = max(min_group_gap, group_gap_ratio * median_height)

    lines: list[list[int]] = [[bands[0][0], bands[0][1]]]
    for start, end in bands[1:]:
        if start - lines[-1][1] < group_gap:
            lines[-1][1] = end
        else:
            lines.append([start, end])
    return lines


def _pad_lines(
    lines: list[list[int]], image_height: int, pad_ratio: float, min_pad: int
) -> list[tuple[int, int]]:
    padded: list[tuple[int, int]] = []
    for i, (start, end) in enumerate(lines):
        pad = max(min_pad, int((end - start) * pad_ratio))
        if i > 0:
            prev_end = lines[i - 1][1]
            top_limit = prev_end + (start - prev_end) // 2
        else:
            top_limit = 0
        if i < len(lines) - 1:
            next_start = lines[i + 1][0]
            bottom_limit = next_start - (next_start - end) // 2
        else:
            bottom_limit = image_height
        padded.append((max(top_limit, start - pad), min(bottom_limit, end + pad)))
    return padded
