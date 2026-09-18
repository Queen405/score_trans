from __future__ import annotations

import numpy as np
from PIL import Image, ImageFilter

_MAX_UPSCALE_RATIO = 4.0


def prepare_work_image(
    original: Image.Image, min_edge: int
) -> tuple[Image.Image, float]:
    """Upscale the whole image for segmentation + LLM input.

    Returns (work_image, scale). scale > 1.0 means the work image is larger
    than the original; coordinates measured on the work image must be divided
    by scale to map back to original-image coordinates.
    """
    if min_edge <= 0:
        return original, 1.0
    longest = max(original.size)
    if longest >= min_edge or longest == 0:
        return original, 1.0
    scale = min(min_edge / longest, _MAX_UPSCALE_RATIO)
    new_size = (int(original.size[0] * scale), int(original.size[1] * scale))
    return original.resize(new_size, Image.Resampling.LANCZOS), scale


def to_binary(image: Image.Image) -> np.ndarray:
    gray = image.convert("L")
    gray = gray.filter(ImageFilter.MedianFilter(size=3))
    arr = np.asarray(gray, dtype=np.uint8)
    return otsu_binarize(arr)


def otsu_binarize(gray: np.ndarray) -> np.ndarray:
    threshold = otsu_threshold(gray)
    return np.where(gray <= threshold, 0, 255).astype(np.uint8)


def otsu_threshold(gray: np.ndarray) -> int:
    hist, _ = np.histogram(gray, bins=256, range=(0, 256))
    total = gray.size
    if total == 0:
        return 128
    weight = hist.astype(np.float64) / total
    bins = np.arange(256, dtype=np.float64)
    omega = np.cumsum(weight)
    mu = np.cumsum(weight * bins)
    mu_total = mu[-1]
    denom = omega * (1.0 - omega)
    denom[denom == 0] = np.nan
    sigma_b2 = (mu_total * omega - mu) ** 2 / denom
    best = int(np.nanargmax(sigma_b2)) if not np.all(np.isnan(sigma_b2)) else 128
    return best
