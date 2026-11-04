from __future__ import annotations

import logging
import re
from pathlib import Path

from ...models.common.types import IMAGE_SUFFIXES
from ..files.image_info import image_dimensions

logger = logging.getLogger(__name__)

_PDF_SUFFIXES = {".pdf"}
_LOW_INTERLINE_PATTERN = re.compile(
    r"too low interline value of\s*(\d+)\s*pixels", re.IGNORECASE
)
_DEFAULT_TARGET_INTERLINE = 18
_MAX_PIXEL_BUDGET_RATIO = 0.95


def is_raster_image(path: str | Path) -> bool:
    return Path(path).suffix.lower() in IMAGE_SUFFIXES


def is_pdf(path: str | Path) -> bool:
    return Path(path).suffix.lower() in _PDF_SUFFIXES


def parse_low_interline(message: str) -> int | None:
    match = _LOW_INTERLINE_PATTERN.search(message or "")
    if match is None:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _capped_scale(
    width: int, height: int, requested_scale: float, max_pixels: int
) -> float:
    if max_pixels <= 0:
        return requested_scale
    capped = (max_pixels / (width * height)) ** 0.5
    return min(requested_scale, capped)


def _save_upscaled(source: Path, dest: Path, scale: float) -> Path:
    from PIL import Image

    resample = _resampling_filter(Image)
    with Image.open(source) as image:
        image.load()
        src_w, src_h = image.width, image.height
        if scale < 1.0:
            new_size = (
                max(1, int(src_w * scale)),
                max(1, int(src_h * scale)),
            )
        else:
            new_size = (
                max(1, round(src_w * scale)),
                max(1, round(src_h * scale)),
            )
        resized = image.resize(new_size, resample)
        save_kwargs: dict[str, object] = {}
        fmt = image.format or "PNG"
        if fmt == "JPEG" or fmt == "WEBP":
            save_kwargs = {"quality": 95}
        elif fmt == "PNG":
            save_kwargs = {"optimize": True}
        dest.parent.mkdir(parents=True, exist_ok=True)
        resized.save(dest, format=fmt, **save_kwargs)
    logger.info(
        "Preprocessed %s -> %s (scale=%.3f, %dx%d -> %dx%d)",
        source.name,
        dest.name,
        scale,
        src_w,
        src_h,
        new_size[0],
        new_size[1],
    )
    return dest


def max_pixel_budget(max_pixels: int) -> int:
    """Return the preprocessing budget, leaving 5% below Audiveris' limit."""
    if max_pixels <= 0:
        return 0
    return max(1, int(max_pixels * _MAX_PIXEL_BUDGET_RATIO))


def ensure_max_pixel_count(
    input_path: str | Path,
    output_dir: str | Path,
    *,
    max_pixels: int,
) -> Path | None:
    """Downscale raster images that exceed 95% of the Audiveris pixel limit."""
    path = Path(input_path)
    if not is_raster_image(path) or max_pixels <= 0:
        return None
    target_pixels = max_pixel_budget(max_pixels)
    try:
        width_f, height_f = image_dimensions(path)
    except OSError:
        return None
    width, height = int(width_f), int(height_f)
    current_pixels = width * height
    if current_pixels <= target_pixels:
        return None
    scale = (target_pixels / current_pixels) ** 0.5
    out = Path(output_dir) / "_preprocess"
    dest = out / path.name
    return _save_upscaled(path, dest, scale)


def _resampling_filter(Image):
    resampling = getattr(Image, "Resampling", None)
    if resampling is not None:
        return resampling.LANCZOS
    return Image.LANCZOS


def ensure_min_resolution(
    input_path: str | Path,
    output_dir: str | Path,
    *,
    min_edge: int,
    max_pixels: int,
) -> Path | None:
    path = Path(input_path)
    if not is_raster_image(path):
        return None
    if min_edge <= 0:
        return None
    try:
        width_f, height_f = image_dimensions(path)
    except OSError:
        return None
    width, height = int(width_f), int(height_f)
    long_edge = max(width, height)
    if long_edge >= min_edge:
        return None
    requested = min_edge / long_edge
    scale = _capped_scale(width, height, requested, max_pixels)
    if scale <= 1.0:
        return None
    out = Path(output_dir) / "_preprocess"
    dest = out / path.name
    return _save_upscaled(path, dest, scale)


def upscale_by_factor(
    input_path: str | Path,
    output_dir: str | Path,
    *,
    factor: float,
    max_pixels: int,
) -> Path:
    path = Path(input_path)
    try:
        width_f, height_f = image_dimensions(path)
    except OSError as exc:
        raise RuntimeError(f"无法读取图片尺寸：{path}") from exc
    width, height = int(width_f), int(height_f)
    scale = _capped_scale(width, height, factor, max_pixels)
    if scale <= 1.0:
        raise RuntimeError(f"按倍数 {factor} 放大后超过 maxPixels={max_pixels}，已跳过")
    out = Path(output_dir) / "_preprocess"
    dest = out / path.name
    return _save_upscaled(path, dest, scale)


def retry_scale_from_interline(
    measured_interline: int,
    *,
    target_interline: int = _DEFAULT_TARGET_INTERLINE,
) -> float:
    if measured_interline <= 0:
        return 0.0
    return target_interline / measured_interline


def binarize_score_for_omr(
    input_path: str | Path,
    output_dir: str | Path,
    *,
    threshold: int = 0,
) -> Path | None:
    """按用户设定的固定阈值生成 OMR 专用图；0 表示交给 Audiveris。"""
    if threshold == 0:
        return None
    if threshold < 0 or threshold > 254:
        raise ValueError("二值化阈值必须为 0（Audiveris 自动）或 1–254")
    path = Path(input_path)
    if not is_raster_image(path):
        return None
    from PIL import Image

    with Image.open(path) as source:
        source.load()
        binary = source.convert("L").point(
            lambda value: 0 if value < threshold else 255,
            mode="1",
        )
        dest = (
            Path(output_dir) / "_preprocess" / f"threshold_{threshold}_{path.stem}.png"
        )
        dest.parent.mkdir(parents=True, exist_ok=True)
        binary.save(dest, format="PNG", optimize=True)
    logger.info(
        "Binarized OMR input %s -> %s (threshold=%d)",
        path.name,
        dest.name,
        threshold,
    )
    return dest
