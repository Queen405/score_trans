from __future__ import annotations

from ..models.layout import RenderItem
from ..options import RenderOptions
from ..parsing.tokens import _parse_chord_token, _parse_note, _token_slashes
from ..utils.helpers import _split_accidental


def _beat_visual_width(
    items: list[RenderItem], options: RenderOptions | None = None
) -> float:
    if not items:
        return 22.0
    return max(
        36.0,
        sum(_item_visual_width(item, options) for item in items)
        + sum(
            _inter_item_gap(left, right, options)
            for left, right in zip(items, items[1:])
        ),
    )


def _token_visual_width(token: str, options: RenderOptions | None = None) -> float:
    duration_ratio = options.duration_spacing_ratio if options is not None else 1.0
    note_width = options.note_font_size if options is not None else 30.0
    chord_width = options.chord_token_width if options is not None else 42.0
    token = token.strip().strip("()~")
    if token == "-":
        return note_width * duration_ratio
    chord = _parse_chord_token(token)
    if chord is not None:
        _notes, _slashes, _dotted, extension = chord
        return chord_width + extension * note_width * 0.52 * duration_ratio
    note = _parse_note(token)
    body_width = note_width * _short_note_width_ratio(note.slashes, options)
    accidental_space = (
        max(9.0, options.accidental_font_size * 0.65)
        if options is not None and _split_accidental(note.display)[0]
        else 12
        if _split_accidental(note.display)[0]
        else 0
    )
    return (
        body_width
        + accidental_space
        + note.extension * body_width * 0.52 * duration_ratio
        + (body_width * 0.27 * duration_ratio * min(3, note.dotted))
    )


def _item_visual_width(item: RenderItem, options: RenderOptions | None = None) -> float:
    width = _token_visual_width(item.token, options)
    if item.tuplet_id:
        ratio = options.tuplet_slot_width_ratio if options is not None else 0.54
        return width * ratio
    return width


def _inter_item_gap(
    left: RenderItem,
    right: RenderItem,
    options: RenderOptions | None = None,
) -> float:
    gap = options.note_min_gap if options is not None else 9.0
    if left.tuplet_id and left.tuplet_id == right.tuplet_id:
        ratio = options.tuplet_gap_ratio if options is not None else 0.55
        return gap * ratio
    if _token_slashes(left.token) >= 2 and _token_slashes(right.token) >= 2:
        ratio = options.short_note_gap_ratio if options is not None else 1.0
        return gap * ratio
    return gap


def _short_note_width_ratio(
    slashes: int,
    options: RenderOptions | None = None,
) -> float:
    if slashes < 2:
        return 1.0
    return options.short_note_slot_width_ratio if options is not None else 1.0


def _is_compact_gap(left: RenderItem, right: RenderItem) -> bool:
    if left.tuplet_id and left.tuplet_id == right.tuplet_id:
        return True
    return _token_slashes(left.token) >= 2 and _token_slashes(right.token) >= 2


def _item_slots(
    items: list[RenderItem],
    x: float,
    width: float,
    options: RenderOptions | None = None,
) -> list[tuple[RenderItem, float, float]]:
    if not items:
        return []
    gaps = [
        _inter_item_gap(left, right, options) for left, right in zip(items, items[1:])
    ]
    item_widths = [_item_visual_width(item, options) for item in items]
    natural = sum(item_widths) + sum(gaps)
    if natural > 0 and width < natural:
        scale = width / natural
        item_widths = [item_width * scale for item_width in item_widths]
        gaps = [gap * scale for gap in gaps]
        cursor = x
    else:
        extra = max(0.0, width - natural)
        stretchable = [
            index
            for index, (left, right) in enumerate(zip(items, items[1:]))
            if not _is_compact_gap(left, right)
        ]
        if stretchable:
            extra_gap = extra / len(stretchable)
            gaps = [
                gap + extra_gap if index in stretchable else gap
                for index, gap in enumerate(gaps)
            ]
            cursor = x
        else:
            cursor = x + extra / 2
    slots: list[tuple[RenderItem, float, float]] = []
    for index, item in enumerate(items):
        slot = item_widths[index]
        slots.append((item, cursor + slot / 2, slot))
        if index < len(gaps):
            cursor += slot + gaps[index]
    return slots
