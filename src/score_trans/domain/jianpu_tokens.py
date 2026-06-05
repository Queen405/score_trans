from __future__ import annotations

from fractions import Fraction


DURATION_PREFIXES = {
    "q": Fraction(1, 2),
    "s": Fraction(1, 4),
    "d": Fraction(1, 8),
}

PREFIX_SLASHES = {"": 0, "q": 1, "s": 2, "d": 3}


def consume_duration_prefix(token: str) -> tuple[Fraction, str]:
    if token and token[0] in DURATION_PREFIXES:
        return DURATION_PREFIXES[token[0]], token[1:]
    return Fraction(1, 1), token

def duration_affixes(duration: Fraction) -> tuple[str, str]:
    dotted_base = None
    for base in (Fraction(4, 1), Fraction(2, 1), Fraction(1, 1), Fraction(1, 2), Fraction(1, 4), Fraction(1, 8)):
        if duration == base + base / 2:
            dotted_base = base
            break
    if dotted_base is not None:
        prefix, suffix = duration_affixes(dotted_base)
        return prefix, suffix + "."
    exact = {
        Fraction(1, 1): ("", ""),
        Fraction(1, 2): ("q", ""),
        Fraction(1, 4): ("s", ""),
        Fraction(1, 8): ("d", ""),
    }
    if duration in exact:
        return exact[duration]
    if duration >= 1:
        whole = int(duration)
        remain = duration - whole
        prefix, suffix = duration_affixes(remain) if remain else ("", "")
        return prefix, suffix + "-" * max(0, whole - 1)
    return "", ""


def token_duration(token: str) -> Fraction:
    token = token.strip().strip("()~")
    if token.startswith("[") and token.endswith("]"):
        parts = [part.strip() for part in token[1:-1].split("+") if part.strip()]
        return min((token_duration(part) for part in parts), default=Fraction(1, 1))
    duration, work = consume_duration_prefix(token)
    while work.endswith("-"):
        duration += Fraction(1, 1)
        work = work[:-1]
    if work.endswith("."):
        duration += duration / 2
    return duration
