from __future__ import annotations

from fractions import Fraction

from ....models.score import TextBlock


def _same_start(left: Fraction | None, right: Fraction | None) -> bool:
    if left is None or right is None:
        return left is right
    return left == right


def _scale_bbox(bbox: tuple[float, float, float, float], width: int, height: int) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = bbox
    if max(abs(x1), abs(y1), abs(x2), abs(y2)) <= 1.5:
        return x1 * width, y1 * height, x2 * width, y2 * height
    return x1, y1, x2, y2


def _is_dynamic_text(text: str) -> bool:
    return text.strip() in {
        "p", "pp", "ppp", "pppp", "f", "ff", "fff", "ffff",
        "mp", "mf", "sf", "sfz", "sfp", "fp", "fz", "rfz",
    }


def _split_accidental(display: str) -> tuple[str, str]:
    for token, symbol in (("bb", "bb"), ("x", "x"), ("n", "♮"), ("♮", "♮"), ("#", "#"), ("b", "b")):
        if display.startswith(token) and len(display) > len(token):
            return symbol, display[len(token):]
    return "", display


def _mark_display(name: str) -> str:
    normalized = name.strip().lower().replace("_", "-")
    return {
        "trill-mark": "tr",
        "mordent": "mord.",
        "inverted-mordent": "mord.",
        "turn": "turn",
        "delayed-turn": "turn",
        "inverted-turn": "turn",
        "up-bow": "up-bow",
        "down-bow": "down-bow",
        "harmonic": "harm.",
        "snap-pizzicato": "snap",
        "open-string": "open",
        "thumb-position": "thumb",
    }.get(normalized, name)


def _text_block_reading_order(candidate: tuple[int, TextBlock, int]) -> tuple[int, float, float, int]:
    index, block, _number = candidate
    if block.bbox is None:
        return (1, 0.0, 0.0, index)
    x1, y1, _x2, _y2 = block.bbox
    return (0, y1, x1, index)


def _first_ocr_measure_number(blocks: list[TextBlock]) -> int | None:
    candidates = [
        (index, block, int(block.text.strip()))
        for index, block in enumerate(blocks)
        if block.role == "measure_number" and block.text.strip().isdigit()
    ]
    if not candidates:
        return None
    candidates.sort(key=_text_block_reading_order)
    return candidates[0][2]
