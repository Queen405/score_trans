from __future__ import annotations

from ..models.layout import RenderItem
from ..options import RenderOptions
from ..parsing.tokens import _parse_chord_token, _parse_note
from ..utils.helpers import _split_accidental


def _beat_visual_width(
    items: list[RenderItem], options: RenderOptions | None = None
) -> float:
    gap = options.note_min_gap if options is not None else 9.0
    if not items:
        return 22.0
    return max(
        36.0,
        sum(_token_visual_width(item.token, options) for item in items)
        + max(0, len(items) - 1) * gap,
    )


def _token_visual_width(token: str, options: RenderOptions | None = None) -> float:
    duration_ratio = options.duration_spacing_ratio if options is not None else 1.0
    token = token.strip().strip("()~")
    if token == "-":
        return 30.0 * duration_ratio
    chord = _parse_chord_token(token)
    if chord is not None:
        _notes, _slashes, _dotted, extension = chord
        return 42 + extension * 16 * duration_ratio
    note = _parse_note(token)
    accidental_space = 12 if _split_accidental(note.display)[0] else 0
    return (
        30
        + accidental_space
        + note.extension * 16 * duration_ratio
        + (8 * duration_ratio if note.dotted else 0)
    )


def _item_slots(
    items: list[RenderItem],
    x: float,
    width: float,
    options: RenderOptions | None = None,
) -> list[tuple[RenderItem, float, float]]:
    if not items:
        return []
    gap = options.note_min_gap if options is not None else 9.0
    natural = sum(_token_visual_width(item.token, options) for item in items) + max(0, len(items) - 1) * gap
    scale = width / natural if natural > 0 else 1.0
    cursor = x
    slots: list[tuple[RenderItem, float, float]] = []
    for item in items:
        slot = _token_visual_width(item.token, options) * scale
        slots.append((item, cursor + slot / 2, slot))
        cursor += slot + gap * scale
    return slots
