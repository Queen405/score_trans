from __future__ import annotations

DIATONIC_STEPS = ("C", "D", "E", "F", "G", "A", "B")

_CLEF_REF_OCTAVE = {"G": 4, "F": 3, "C": 4}


def _diatonic_value(step: str, octave: int) -> int:
    return octave * 7 + DIATONIC_STEPS.index(step.upper())


def _from_diatonic(value: int) -> tuple[str, int]:
    return DIATONIC_STEPS[value % 7], value // 7


def compute_clef_bottom_diatonic(sign: str, line: int) -> int:
    if sign not in _CLEF_REF_OCTAVE:
        raise ValueError(f"Unsupported clef sign: {sign}")
    clef_octave = _CLEF_REF_OCTAVE[sign]
    clef_diatonic = _diatonic_value(sign, clef_octave)
    return clef_diatonic - 2 * (line - 1)


def transform_pitch(
    step: str,
    alter: float,
    octave: int,
    old_sign: str,
    old_line: int,
    new_sign: str = "G",
    new_line: int = 2,
) -> tuple[str, float, int]:
    old_bottom = compute_clef_bottom_diatonic(old_sign, old_line)
    new_bottom = compute_clef_bottom_diatonic(new_sign, new_line)
    note_diatonic = _diatonic_value(step, octave)
    staff_position = note_diatonic - old_bottom
    new_diatonic = new_bottom + staff_position
    new_step, new_octave = _from_diatonic(new_diatonic)
    return new_step, alter, new_octave
