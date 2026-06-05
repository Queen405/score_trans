from __future__ import annotations

from fractions import Fraction
from typing import Any

from ..models.layout import RenderItem
from ..parsing.tokens import _parse_note
from .helpers import _same_start


def _measure_text_x(
    source: Any,
    x: float,
    width: float,
    slots: list[tuple[RenderItem, float, float]],
    start: Fraction | None,
) -> float:
    if start is not None:
        same_start = [(cx, slot_width) for item, cx, slot_width in slots if item.start == start]
        if same_start:
            return same_start[0][0]
        duration = getattr(source, "duration", None)
        if duration:
            ratio = max(0.0, min(1.0, float(start / duration)))
            return x + 26 + max(0.0, width - 56) * ratio
    return x + 28


def _slot_has_dynamic(slots: list[tuple[RenderItem, float, float]], text: str, start: Fraction | None) -> bool:
    return any(item.dynamic == text and _same_start(item.start, start) for item, _, _ in slots)


def _slot_has_lyric(slots: list[tuple[RenderItem, float, float]], text: str, start: Fraction | None) -> bool:
    return any(item.lyric == text and _same_start(item.start, start) for item, _, _ in slots)


def _upper_mark_anchor_y(token: str, y: int) -> float:
    from .metrics import _token_metrics
    return _token_metrics(token, y)["top"] + 28.0


def _technique_mark(name: str) -> str | None:
    normalized = name.strip().lower().replace("_", "-").replace(" ", "-")
    return {
        "tremolo": "轮",
        "roll": "轮",
        "rolled": "轮",
        "lun": "轮",
        "lun-yin": "轮",
        "轮": "轮",
        "轮音": "轮",
    }.get(normalized)


def _technique_mark_x(token: str, cx: float) -> float:
    from ..layout.beat import _token_visual_width
    return cx + max(15.0, min(24.0, _token_visual_width(token) * 0.38))


def _technique_mark_y(token: str, y: int) -> float:
    token = token.strip().strip("()~")
    if token.startswith("[") and token.endswith("]"):
        notes = [_parse_note(part.strip()) for part in token[1:-1].split("+") if part.strip()]
        if notes:
            from ..constants import CHORD_GAP
            top_y = y - (len(notes) - 1) * CHORD_GAP / 2
            return top_y + CHORD_GAP * (len(notes) - 1) + 20
    return y + 21
