from __future__ import annotations

from copy import deepcopy
from typing import cast

from .constants import MAJOR_SCALE
from ..models.common.types import AccidentalMode
from ..models.score import JianpuPitch, JianpuScore


_ACCIDENTAL_MODES = {"auto", "sharp", "flat"}


def normalize_accidental_mode(value: str | None) -> AccidentalMode:
    if value in _ACCIDENTAL_MODES:
        return cast(AccidentalMode, value)
    return "auto"


def pitch_to_token(
    pitch: JianpuPitch,
    *,
    accidental_mode: AccidentalMode = "auto",
) -> str:
    accidental, degree, octave = pitch_spelling(
        pitch, accidental_mode=accidental_mode
    )
    octave_text = "'" * max(0, octave) + "," * max(0, -octave)
    return f"{accidental}{degree}{octave_text}"


def score_with_accidental_mode(
    score: JianpuScore,
    *,
    accidental_mode: AccidentalMode = "auto",
) -> JianpuScore:
    mode = normalize_accidental_mode(accidental_mode)
    if mode == "auto":
        return score

    adjusted = deepcopy(score)
    for measure in adjusted.measures:
        for event in measure.events:
            if event.kind == "note":
                event.source_token = None
            for pitch in event.pitches:
                accidental, degree, octave = pitch_spelling(
                    pitch, accidental_mode=mode
                )
                pitch.degree = degree
                pitch.octave = octave
                pitch.accidental = _accidental_value(accidental)
                pitch.accidental_text = None if abs(pitch.accidental) <= 1 else accidental
    return adjusted


def pitch_spelling(
    pitch: JianpuPitch,
    *,
    accidental_mode: AccidentalMode = "auto",
) -> tuple[str, int, int]:
    mode = normalize_accidental_mode(accidental_mode)
    if mode == "auto" or abs(pitch.accidental) > 1:
        return (
            pitch.accidental_text
            if pitch.accidental_text is not None
            else _accidental_text(pitch.accidental),
            pitch.degree,
            pitch.octave,
        )

    if pitch.accidental == 0:
        return "", pitch.degree, pitch.octave

    total = _pitch_total(pitch)
    preferred = _find_spelling(total, 1 if mode == "sharp" else -1)
    if preferred is not None:
        degree, octave = preferred
        return ("#" if mode == "sharp" else "b"), degree, octave

    natural = _find_spelling(total, 0)
    if natural is not None:
        degree, octave = natural
        return "", degree, octave

    return _accidental_text(pitch.accidental), pitch.degree, pitch.octave


def _pitch_total(pitch: JianpuPitch) -> int:
    degree_index = min(max(pitch.degree, 1), len(MAJOR_SCALE)) - 1
    return pitch.octave * 12 + MAJOR_SCALE[degree_index] + pitch.accidental


def _find_spelling(total: int, accidental: int) -> tuple[int, int] | None:
    for index, offset in enumerate(MAJOR_SCALE, start=1):
        remainder = total - offset - accidental
        if remainder % 12 == 0:
            return index, remainder // 12
    return None


def _accidental_text(accidental: int) -> str:
    return {2: "x", 1: "#", 0: "", -1: "b", -2: "bb"}.get(
        accidental,
        "#" if accidental > 0 else "b" if accidental < 0 else "",
    )


def _accidental_value(accidental: str) -> int:
    return {"x": 2, "#": 1, "": 0, "b": -1, "bb": -2}.get(accidental, 0)
