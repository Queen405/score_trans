from __future__ import annotations

from fractions import Fraction

from .constants import KEY_TO_FIFTHS, STEP_TO_SEMITONE
from ..models.common.types import AccidentalMode

DIATONIC_STEPS = ("C", "D", "E", "F", "G", "A", "B")
SHARP_ORDER = ("F", "C", "G", "D", "A", "E", "B")
FLAT_ORDER = ("B", "E", "A", "D", "G", "C", "F")

# 等音重拼搜索的八度范围。简谱八度点最多表达几个八度，±4 已远超实际用量。
_RESPELL_OCTAVE_RANGE = range(-4, 6)
# 简谱只能表达到重升/重降；超过就无法记写。
_MAX_NOTATABLE_ALTER = Fraction(2, 1)


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


def written_pitch_to_jianpu_respelled(
    step: str,
    alter: Fraction,
    octave: int,
    target_key: str,
    *,
    accidental_mode: AccidentalMode = "auto",
) -> tuple[int, Fraction, int]:
    """保留音名优先；若所需变音超过 ±2，改按绝对音高等音重拼。

    written_pitch_to_jianpu 保留音名，跨远关系调时所需变音可达 ±3
    （例如 Cb 调的 b4 记到 G 调）。而 accidentals._accidental_text 的词表只到 ±2，
    ±3 会退化成单个升/降号，静默丢掉两个半音。这里在超界时改为按绝对音高
    搜索最小变音的记法，保证音高不变。
    """
    degree, accidental, octave_shift = written_pitch_to_jianpu(
        step, alter, octave, target_key
    )
    if abs(accidental) <= _MAX_NOTATABLE_ALTER:
        return degree, accidental, octave_shift
    normalized_step = step.strip().upper()
    if normalized_step not in STEP_TO_SEMITONE:
        raise ValueError(f"无效的 MusicXML 音名字母：{step}")
    total = octave * 12 + STEP_TO_SEMITONE[normalized_step] + alter
    best: tuple[int, Fraction, int] | None = None
    for candidate_degree, (_step, key_alter, scale_octave) in enumerate(
        _key_scale(target_key), start=1
    ):
        base = STEP_TO_SEMITONE[_step] + key_alter
        for candidate_octave in _RESPELL_OCTAVE_RANGE:
            needed = total - (candidate_octave + scale_octave) * 12 - base
            if abs(needed) > _MAX_NOTATABLE_ALTER:
                continue
            candidate = (candidate_degree, Fraction(needed), candidate_octave)
            if best is None or _respell_rank(
                candidate, accidental_mode
            ) < _respell_rank(best, accidental_mode):
                best = candidate
    if best is None:
        raise ValueError(f"无法在 {target_key} 调中记写绝对音高 {total}")
    return best


def _respell_rank(
    candidate: tuple[int, Fraction, int],
    accidental_mode: AccidentalMode,
) -> tuple[Fraction, int, int, int]:
    """等音候选的排序键：变音绝对值越小越好，其次按 accidental_mode 定向。

    同一最小变音下可能同时存在升号与降号写法（例如 Cb→Ab 的 bb4 可记作 4# 或 5b），
    必须显式定序，否则输出取决于迭代顺序且无视用户的变音偏好。
    """
    _degree, accidental, _octave = candidate
    if accidental_mode == "sharp":
        direction = 0 if accidental > 0 else 1
    elif accidental_mode == "flat":
        direction = 0 if accidental < 0 else 1
    else:
        direction = 0
    return (abs(accidental), direction, candidate[0], candidate[2])


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
            alterations[DIATONIC_STEPS[(tonic_index + offset) % len(DIATONIC_STEPS)]],
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
        for step in FLAT_ORDER[:-fifths]:
            alterations[step] = -1
    return alterations
