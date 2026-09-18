from __future__ import annotations

from fractions import Fraction
from ..models.melody import AttributeValue, NoteAttributes

FIELDS = ("octave", "accidental", "underlines", "dots", "extensions")


def derive_note_attributes(note: NoteAttributes) -> NoteAttributes:
    note.duration = None
    note.complete = False
    if any(
        note.fields.get(name) is None or note.fields[name].status != "confirmed"
        for name in FIELDS
    ):
        return note
    octave, accidental, lines, dots, extensions = (
        note.fields[name].value for name in FIELDS
    )
    if not all(type(v) is int for v in (octave, lines, dots, extensions)):
        return note
    if (
        not -2 <= octave <= 2
        or not 0 <= lines <= 3
        or not 0 <= dots <= 2
        or not 0 <= extensions <= 8
    ):
        return note
    if accidental not in ("none", "sharp", "flat", "natural"):
        return note
    if note.degree == "0" and (octave or accidental != "none"):
        note.fields["octave"] = AttributeValue(
            None, "unsupported", reason="休止符不能有八度或变音记号"
        )
        return note
    if extensions and (dots or lines):
        note.fields["extensions"] = AttributeValue(
            None,
            "unknown",
            note.fields["extensions"].evidence_ids,
            reason="附点/减时线与延长线组合的作用域未确认",
        )
        return note
    note.duration = Fraction(1, 2**lines) * (2 - Fraction(1, 2**dots)) + extensions
    note.complete = note.degree in tuple("01234567")
    return note


def serialize_note(note: NoteAttributes) -> str | None:
    if not note.complete or note.duration is None:
        return None
    f = {key: attribute.value for key, attribute in note.fields.items()}
    prefix = ("", "q", "s", "d")[f["underlines"]]
    accidental = {"none": "", "sharp": "#", "flat": "b", "natural": "n"}[
        f["accidental"]
    ]
    octave = "'" * f["octave"] if f["octave"] > 0 else "," * (-f["octave"])
    return (
        prefix
        + accidental
        + note.degree
        + octave
        + "." * f["dots"]
        + "-" * f["extensions"]
    )
