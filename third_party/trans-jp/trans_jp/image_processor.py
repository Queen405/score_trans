"""Compatibility imports; implementation lives in the layered package."""

from __future__ import annotations

from .preprocess.image import (
    prepare_work_image as prepare_work_image,
    to_binary as to_binary,
    otsu_binarize as otsu_binarize,
    otsu_threshold as otsu_threshold,
)

from .io.images import load_image as load_image
