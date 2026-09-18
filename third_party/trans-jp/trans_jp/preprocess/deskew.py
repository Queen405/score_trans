from __future__ import annotations

import numpy as np
from PIL import Image
from ..models.geometry import Transform
from ..raster.filaments import detect_filaments
from ..raster.runs import scan_runs
from ..raster.sections import join_sections
from .image import otsu_binarize


def normalize_skew(
    image: Image.Image, source_size: tuple[int, int]
) -> tuple[Image.Image, Transform]:
    """Conservative vertical shear; keep an invertible original-pixel transform."""
    ratio = min(1.0, 1400 / max(image.size))
    probe = (
        image.resize(
            (max(1, int(image.width * ratio)), max(1, int(image.height * ratio)))
        )
        if ratio < 1
        else image
    )
    binary = otsu_binarize(np.array(probe.convert("L")))
    sections = join_sections(scan_runs(binary))
    sizes = [
        s.bounds.height
        for s in sections
        if s.area >= 8
        and 0.2 <= s.bounds.width / max(s.bounds.height, 1) <= 1.3
        and s.bounds.height >= 6
    ]
    scale = float(np.median(sizes)) if sizes else 16.0
    lines = [
        line
        for line in detect_filaments(binary, "horizontal", scale)
        if line.bounds.width > scale * 2
    ]
    slope = 0.0
    if len(lines) >= 3:
        values = np.array([line.slope for line in lines])
        median = float(np.median(values))
        coherent = values[np.abs(values - median) < 0.015]
        if (
            len(coherent) >= 3
            and len(coherent) >= len(values) * 0.65
            and 0.003 < abs(median) < 0.12
        ):
            slope = float(np.median(coherent))
    offset = max(0.0, slope * image.width)
    height = image.height + int(np.ceil(abs(slope) * image.width))
    transform = Transform(
        image.width / source_size[0], image.height / source_size[1], slope, offset
    )
    if slope:
        image = image.transform(
            (image.width, height),
            Image.Transform.AFFINE,
            (1, 0, 0, slope, 1, -offset),
            Image.Resampling.BICUBIC,
            fillcolor="white",
        )
    return image, transform
