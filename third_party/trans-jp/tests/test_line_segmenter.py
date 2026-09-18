from __future__ import annotations

import numpy as np
from PIL import Image

from trans_jp.image_processor import load_image, to_binary
from trans_jp.line_segmenter import segment


def test_segment_detects_three_rows(synthetic_jianpu_image, tmp_path):
    original = load_image(synthetic_jianpu_image)
    binary = to_binary(original)
    rows = segment(binary, original, tmp_path / "rows")
    assert len(rows) == 3
    assert rows[0].index == 0
    assert rows[0].y_top < rows[1].y_top < rows[2].y_top
    for row in rows:
        assert row.image_path.is_file()
        assert row.height == row.y_bottom - row.y_top
        assert row.width == 800


def test_segment_blank_image_returns_empty(tmp_path):
    img = Image.new("RGB", (400, 300), "white")
    binary = np.full((300, 400), 255, dtype=np.uint8)
    rows = segment(binary, img, tmp_path / "rows")
    assert rows == []


def test_segment_merges_narrow_gaps(tmp_path):
    binary = np.full((200, 400), 255, dtype=np.uint8)
    binary[10:30, :] = 0
    binary[33:50, :] = 0
    binary[100:150, :] = 0
    img = Image.new("RGB", (400, 200), "white")
    rows = segment(binary, img, tmp_path / "rows")
    assert len(rows) == 2
    assert rows[0].y_top <= 10
    assert rows[0].y_bottom >= 50
    assert rows[1].y_top <= 100


def test_segment_filters_tiny_rows(tmp_path):
    binary = np.full((200, 400), 255, dtype=np.uint8)
    binary[10:12, :] = 0
    binary[100:150, :] = 0
    img = Image.new("RGB", (400, 200), "white")
    rows = segment(binary, img, tmp_path / "rows")
    assert len(rows) == 1
    assert rows[0].y_top <= 100


def test_segment_crops_match_bounds(synthetic_jianpu_image, tmp_path):
    original = load_image(synthetic_jianpu_image)
    binary = to_binary(original)
    rows = segment(binary, original, tmp_path / "rows")
    for row in rows:
        with Image.open(row.image_path) as cropped:
            assert cropped.size == (row.width, row.height)


def test_segment_coord_scale_maps_back_to_original(tmp_path):
    work = Image.new("RGB", (1600, 800), "white")
    binary = np.full((800, 1600), 255, dtype=np.uint8)
    binary[40:100, :] = 0
    binary[400:500, :] = 0
    rows = segment(binary, work, tmp_path / "rows", coord_scale=2.0)
    assert len(rows) == 2
    # 逻辑行带 padding：原图坐标下，裁剪区间必须包含真实墨迹带（40:100 /2 = 20:50）
    assert rows[0].y_top <= 20
    assert rows[0].y_bottom >= 50
    assert rows[1].y_top <= 200
    assert rows[1].y_bottom >= 250
    with Image.open(rows[0].image_path) as cropped:
        assert cropped.size[0] == 1600
        assert cropped.size[1] == rows[0].height


def test_underline_and_dots_merge_into_notation_line(tmp_path):
    """数字带 + 紧贴的时值线带 + 低八度点带 = 同一个逻辑行。"""
    img = Image.new("RGB", (800, 400), "white")
    binary = np.full((400, 800), 255, dtype=np.uint8)
    binary[100:132, 50:700] = 0  # 数字带（32px 高）
    binary[138:142, 50:700] = 0  # 时值线带（4px，间距 6px）
    binary[148:156, 100:200] = 0  # 低八度点带（间距 6px）
    binary[300:330, 50:700] = 0  # 远处另一行（歌词）
    rows = segment(binary, img, tmp_path / "rows")
    assert len(rows) == 2
    # 第一行必须覆盖从数字顶部到八度点底部（含 padding）
    assert rows[0].y_top <= 100
    assert rows[0].y_bottom >= 156
    # 第二行是独立的歌词行
    assert rows[1].y_top > 156


def test_isolated_thin_band_filtered(tmp_path):
    """孤立的细带（如噪点线）不构成逻辑行。"""
    img = Image.new("RGB", (800, 300), "white")
    binary = np.full((300, 800), 255, dtype=np.uint8)
    binary[50:53, :] = 0  # 3px 孤立细带
    binary[150:190, :] = 0  # 40px 正常行
    rows = segment(binary, img, tmp_path / "rows")
    assert len(rows) == 1
    assert rows[0].y_bottom > 100
