from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}


@dataclass(slots=True)
class ImagePreprocessOptions:
    target_long_edge: int = 3600
    binarize: bool = False
    dpi: int = 300


def prepare_omr_input(input_path: Path, output_dir: Path, config) -> Path:
    # Always render PDF to PNG first (forced conversion)
    if input_path.suffix.lower() == ".pdf":
        target_dir = output_dir / "_preprocessed"
        target_dir.mkdir(parents=True, exist_ok=True)
        png_path = target_dir / f"{input_path.stem}_page_001.png"
        from ...utils.pdf import pdf_page_to_png

        pdf_page_to_png(input_path, png_path, dpi=220)
        input_path = png_path

    if not getattr(config, "omr_preprocess", True):
        return input_path
    if input_path.suffix.lower() not in IMAGE_SUFFIXES:
        return input_path

    target_dir = output_dir / "_preprocessed"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{input_path.stem}_omr.png"
    options = ImagePreprocessOptions(
        target_long_edge=getattr(config, "omr_preprocess_long_edge", 3600),
        binarize=getattr(config, "omr_preprocess_binarize", False),
    )
    preprocess_score_image(input_path, target_path, options)
    return target_path


def preprocess_score_image(input_path: Path, output_path: Path, options: ImagePreprocessOptions | None = None) -> Path:
    options = options or ImagePreprocessOptions()
    try:
        from PIL import Image, ImageFilter, ImageOps
    except ImportError as exc:  # pragma: no cover - dependency guard for hand-built environments
        raise RuntimeError("Install pillow to enable OMR image preprocessing.") from exc

    with Image.open(input_path) as original:
        image = ImageOps.exif_transpose(original).convert("L")

    image = _crop_white_margin(image)
    image = ImageOps.autocontrast(image, cutoff=1)
    image = _resize_to_long_edge(image, options.target_long_edge)
    image = image.filter(ImageFilter.UnsharpMask(radius=1.0, percent=120, threshold=4))
    if options.binarize:
        image = _binarize_otsu(image)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG", dpi=(options.dpi, options.dpi), optimize=True)
    return output_path


def _crop_white_margin(image):
    threshold = 246
    mask = image.point(lambda pixel: 0 if pixel >= threshold else 255, mode="L")
    bbox = mask.getbbox()
    if bbox is None:
        return image

    width, height = image.size
    left, top, right, bottom = bbox
    if (right - left) * (bottom - top) < width * height * 0.2:
        return image

    pad = max(12, int(max(width, height) * 0.012))
    left = max(0, left - pad)
    top = max(0, top - pad)
    right = min(width, right + pad)
    bottom = min(height, bottom + pad)
    return image.crop((left, top, right, bottom))


def _resize_to_long_edge(image, target_long_edge: int):
    if target_long_edge <= 0:
        return image
    width, height = image.size
    long_edge = max(width, height)
    if long_edge >= target_long_edge:
        return image

    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Install pillow to enable OMR image preprocessing.") from exc

    scale = target_long_edge / long_edge
    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    return image.resize(size, Image.Resampling.LANCZOS)


def _binarize_otsu(image):
    threshold = _otsu_threshold(image.histogram())
    return image.point(lambda pixel: 0 if pixel < threshold else 255, mode="L")


def _otsu_threshold(histogram: list[int]) -> int:
    total = sum(histogram)
    if total == 0:
        return 128

    sum_total = sum(level * count for level, count in enumerate(histogram))
    weight_background = 0
    sum_background = 0.0
    best_threshold = 128
    best_variance = -1.0

    for threshold, count in enumerate(histogram):
        weight_background += count
        if weight_background == 0:
            continue
        weight_foreground = total - weight_background
        if weight_foreground == 0:
            break

        sum_background += threshold * count
        mean_background = sum_background / weight_background
        mean_foreground = (sum_total - sum_background) / weight_foreground
        variance = weight_background * weight_foreground * (mean_background - mean_foreground) ** 2
        if variance > best_variance:
            best_variance = variance
            best_threshold = threshold
    return best_threshold
