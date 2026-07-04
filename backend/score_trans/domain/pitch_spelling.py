from __future__ import annotations

from fractions import Fraction

from .constants import KEY_TO_FIFTHS

DIATONIC_STEPS = ("C", "D", "E", "F", "G", "A", "B")
SHARP_ORDER = ("F", "C", "G", "D", "A", "E", "B")
FLAT_ORDER = ("B", "E", "A", "D", "G", "C", "F")


def written_pitch_to_jianpu(
    step: str,
    alter: Fraction,
    octave: int,
    target_key: str,
) -> tuple[int, Fraction, int]:
    scale = _key_scale(target_key)
    normalized_step = step.strip().upper()
    for degree, (scale_step, key_alter, scale_octave) in enumerate(scale, start=1):
        if scale_step == normalized_step:
            return degree, alter - key_alter, octave - scale_octave
    raise ValueError(f"无效的 MusicXML 音名字母：{step}")


def jianpu_pitch_to_written(
    degree: int,
    accidental: Fraction,
    octave: int,
    target_key: str,
) -> tuple[str, Fraction, int]:
    if not 1 <= degree <= 7:
        raise ValueError(f"无效的简谱音级：{degree}")
    step, key_alter, scale_octave = _key_scale(target_key)[degree - 1]
    return step, key_alter + accidental, scale_octave + octave


def _key_scale(target_key: str) -> list[tuple[str, int, int]]:
    if target_key not in KEY_TO_FIFTHS:
        raise ValueError(f"不支持的简谱调：{target_key}")
    tonic_step = target_key[0].upper()
    tonic_index = DIATONIC_STEPS.index(tonic_step)
    alterations = _key_signature_alterations(KEY_TO_FIFTHS[target_key])
    return [
        (
            DIATONIC_STEPS[(tonic_index + offset) % len(DIATONIC_STEPS)],
            alterations[
                DIATONIC_STEPS[(tonic_index + offset) % len(DIATONIC_STEPS)]
            ],
            4 + (tonic_index + offset) // len(DIATONIC_STEPS),
        )
        for offset in range(7)
    ]


def _key_signature_alterations(fifths: int) -> dict[str, int]:
    alterations = {step: 0 for step in DIATONIC_STEPS}
    if fifths > 0:
        for step in SHARP_ORDER[:fifths]:
            alterations[step] = 1
    elif fifths < 0:
        for step in FLAT_ORDER[: -fifths]:
            alterations[step] = -1
    return alterations
