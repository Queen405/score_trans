from __future__ import annotations

from fractions import Fraction
from typing import Any

from ....models.score import TextBlock
from ..models.layout import RenderItem
from ..utils.helpers import _is_dynamic_text, _scale_bbox
from ..utils.positioning import _measure_text_x, _slot_has_dynamic, _slot_has_lyric
from ..utils.text import _esc


def _render_measure_text_blocks(
    source: Any,
    x: float,
    y: int,
    width: float,
    slots: list[tuple[RenderItem, float, float]],
) -> list[str]:
    blocks = [
        block
        for block in getattr(source, "text_blocks", [])
        if block.text
        and block.role in {"expression", "other", "lyric"}
        and block.bbox is None
    ]
    out: list[str] = []
    seen: set[tuple[str, Fraction | None]] = set()
    used_lanes: dict[tuple[float, str], int] = {}
    for block in blocks:
        text = block.text.strip()
        start = getattr(block, "start", None)
        key = (text, start)
        if not text or key in seen:
            continue
        if _is_dynamic_text(text) and _slot_has_dynamic(slots, text, start):
            continue
        if block.role == "lyric" and _slot_has_lyric(slots, text, start):
            continue
        seen.add(key)
        class_name = "dynamic" if _is_dynamic_text(text) else "lyric"
        text_x = _measure_text_x(source, x, width, slots, start)
        placement = (getattr(block, "placement", None) or "below").lower()
        anchor = "middle" if start is not None else "start"
        base_y = y - 48 if placement == "above" else y + 62
        lane_key = (round(text_x, 1), placement)
        lane = used_lanes.get(lane_key, 0)
        used_lanes[lane_key] = lane + 1
        text_y = base_y - lane * 18 if placement == "above" else base_y + lane * 20
        out.append(
            f'<text class="{class_name}" x="{text_x:.1f}" y="{text_y:.1f}" text-anchor="{anchor}">{_esc(text)}</text>'
        )
    return out


def _render_positioned_text_blocks(
    blocks: list[TextBlock],
    width: int,
    height: int,
    *,
    include_measure_numbers: bool = True,
) -> list[str]:
    out: list[str] = []
    seen: set[tuple[str, tuple[float, float, float, float]]] = set()
    seen_texts: set[str] = set()
    unpositioned: list[TextBlock] = []
    for block in blocks:
        if not block.text:
            continue
        if block.role == "instrument":
            continue
        if block.role == "measure_number" and not include_measure_numbers:
            continue
        if block.bbox is None:
            unpositioned.append(block)
            continue
        x1, y1, x2, y2 = _scale_bbox(block.bbox, width, height)
        if x2 <= x1 or y2 <= y1:
            continue
        key = (block.text, (round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)))
        if key in seen:
            continue
        seen.add(key)
        seen_texts.add(block.text.strip())

        font_size = getattr(block, "font_size", None)
        if font_size is None:
            font_size = max(8.0, (y2 - y1) * 0.78)
        else:
            font_size = max(1.0, float(font_size))
        class_name = "dynamic" if _is_dynamic_text(block.text) else "ocr-overlay"
        out.append(
            f'<text class="{class_name}" x="{x1:.1f}" y="{y2 - font_size * 0.16:.1f}" '
            f'font-size="{font_size:.1f}" text-anchor="start">{_esc(block.text)}</text>'
        )
    out.extend(
        _render_unpositioned_text_blocks(unpositioned, width, height, seen_texts)
    )
    return out


def _render_unpositioned_text_blocks(
    blocks: list[TextBlock],
    width: int,
    height: int,
    seen_texts: set[str],
) -> list[str]:
    out: list[str] = []
    x = max(14.0, width * 0.035)
    y = max(28.0, height * 0.045)
    font_size = max(12.0, min(22.0, width / 70.0))
    line_gap = font_size * 1.35
    used: set[str] = set()
    for block in blocks:
        text = block.text.strip()
        if not text or text in seen_texts or text in used:
            continue
        used.add(text)
        class_name = "dynamic" if _is_dynamic_text(text) else "ocr-overlay"
        out.append(
            f'<text class="{class_name}" x="{x:.1f}" y="{y + (len(used) - 1) * line_gap:.1f}" '
            f'font-size="{font_size:.1f}" text-anchor="start">{_esc(text)}</text>'
        )
        if y + len(used) * line_gap > height - font_size:
            break
    return out
