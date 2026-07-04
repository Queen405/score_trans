from __future__ import annotations

from collections.abc import Iterable
from fractions import Fraction
from math import gcd, lcm


_FINE_DURATION_PREFIXES = {
    "d" * count: Fraction(1, 2 ** (count + 2)) for count in range(1, 6)
}
DURATION_PREFIXES = {
    "w": Fraction(4, 1),
    "h": Fraction(2, 1),
    "q": Fraction(1, 2),
    "s": Fraction(1, 4),
    **_FINE_DURATION_PREFIXES,
}

PREFIX_SLASHES = {
    "": 0,
    "w": 0,
    "h": 0,
    "q": 1,
    "s": 2,
    **{"d" * count: count + 2 for count in range(1, 6)},
}

_DURATION_BASES = (
    (Fraction(4, 1), "w"),
    (Fraction(2, 1), "h"),
    (Fraction(1, 1), ""),
    (Fraction(1, 2), "q"),
    (Fraction(1, 4), "s"),
    *((duration, prefix) for prefix, duration in _FINE_DURATION_PREFIXES.items()),
)
_EXACT_DURATION_AFFIXES = {
    duration: (prefix, "") for duration, prefix in _DURATION_BASES
}
_DURATION_PREFIXES_LONGEST_FIRST = tuple(
    sorted(DURATION_PREFIXES, key=len, reverse=True)
)
_MAX_GENERATED_DOTS = 3
_ACCIDENTAL_PREFIXES_STARTING_WITH_DURATION = ("qf", "qs")


def duration_prefix(token: str) -> str:
    if token.startswith(_ACCIDENTAL_PREFIXES_STARTING_WITH_DURATION):
        return ""
    for prefix in _DURATION_PREFIXES_LONGEST_FIRST:
        if token.startswith(prefix):
            return prefix
    return ""


def consume_duration_prefix(token: str) -> tuple[Fraction, str]:
    prefix = duration_prefix(token)
    if prefix:
        return DURATION_PREFIXES[prefix], token[len(prefix) :]
    return Fraction(1, 1), token


def duration_affixes(duration: Fraction) -> tuple[str, str]:
    if duration <= 0:
        raise ValueError(f"无法用简谱时值语法表示非正时值：{duration}")
    if duration in _EXACT_DURATION_AFFIXES:
        return _EXACT_DURATION_AFFIXES[duration]
    for base, prefix in _DURATION_BASES:
        for dot_count in range(1, _MAX_GENERATED_DOTS + 1):
            if duration == dotted_duration(base, dot_count):
                return prefix, "." * dot_count
    if duration >= 1:
        whole = int(duration)
        remain = duration - whole
        prefix, suffix = duration_affixes(remain) if remain else ("", "")
        extension_count = whole if remain else max(0, whole - 1)
        return prefix, suffix + "-" * extension_count
    raise ValueError(f"无法用简谱时值语法表示时值：{duration}")


def dotted_duration(base_duration: Fraction, dot_count: int) -> Fraction:
    if dot_count < 0:
        raise ValueError("附点数量不能为负数")
    return base_duration * (2 - Fraction(1, 2**dot_count))


def consume_duration_suffix(
    base_duration: Fraction, token: str
) -> tuple[Fraction, str, int]:
    work = token
    extension_count = 0
    while work.endswith("-"):
        extension_count += 1
        work = work[:-1]

    dot_count = 0
    while work.endswith("."):
        dot_count += 1
        work = work[:-1]

    duration = dotted_duration(base_duration, dot_count)
    duration += Fraction(extension_count, 1)
    return duration, work, dot_count


def token_duration(token: str) -> Fraction:
    token = token.strip().strip("()~")
    if token.startswith("[") and token.endswith("]"):
        parts = [part.strip() for part in token[1:-1].split("+") if part.strip()]
        return min((token_duration(part) for part in parts), default=Fraction(1, 1))
    base_duration, work = consume_duration_prefix(token)
    duration, _work, _dot_count = consume_duration_suffix(base_duration, work)
    return duration


def tuplet_duration_unit_count(durations: Iterable[Fraction]) -> int:
    values = [Fraction(duration) for duration in durations]
    if not values or any(duration <= 0 for duration in values):
        raise ValueError("连音组时值必须全部大于零")
    common_denominator = 1
    for duration in values:
        common_denominator = lcm(common_denominator, duration.denominator)
    scaled = [
        duration.numerator * (common_denominator // duration.denominator)
        for duration in values
    ]
    unit = 0
    for value in scaled:
        unit = gcd(unit, value)
    return sum(value // unit for value in scaled)
