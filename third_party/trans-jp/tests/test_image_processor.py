from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from trans_jp.image_processor import (
    load_image,
    otsu_binarize,
    otsu_threshold,
    prepare_work_image,
    to_binary,
)


def test_load_image_returns_pil_image(synthetic_jianpu_image):
    original = load_image(synthetic_jianpu_image)
    assert isinstance(original, Image.Image)
    assert original.size == (800, 400)


def test_to_binary_produces_two_levels(synthetic_jianpu_image):
    original = load_image(synthetic_jianpu_image)
    binary = to_binary(original)
    assert binary.shape == (400, 800)
    assert set(np.unique(binary)).issubset({0, 255})


def test_load_image_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_image(tmp_path / "nope.png")


def test_otsu_threshold_separates_foreground():
    gray = np.full((100, 100), 255, dtype=np.uint8)
    gray[40:60, 40:60] = 0
    threshold = otsu_threshold(gray)
    assert 0 <= threshold < 255
    binary = otsu_binarize(gray)
    assert binary[50, 50] == 0
    assert binary[0, 0] == 255


def test_otsu_threshold_empty_image():
    gray = np.zeros((0, 0), dtype=np.uint8)
    assert otsu_threshold(gray) == 128


def test_prepare_work_image_upscales_small_image():
    img = Image.new("RGB", (400, 100), "white")
    work, scale = prepare_work_image(img, 1000)
    assert work.size == (1000, 250)
    assert scale == pytest.approx(2.5)


def test_prepare_work_image_caps_at_4x():
    img = Image.new("RGB", (400, 100), "white")
    work, scale = prepare_work_image(img, 2500)
    assert scale == 4.0
    assert work.size == (1600, 400)


def test_prepare_work_image_skips_large_image():
    img = Image.new("RGB", (3000, 800), "white")
    work, scale = prepare_work_image(img, 2500)
    assert scale == 1.0
    assert work.size == (3000, 800)


def test_prepare_work_image_disabled():
    img = Image.new("RGB", (400, 100), "white")
    work, scale = prepare_work_image(img, 0)
    assert scale == 1.0
    assert work.size == (400, 100)
