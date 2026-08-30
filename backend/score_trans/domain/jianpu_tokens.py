from __future__ import annotations

import re
from fractions import Fraction

from .constants import DYNAMICS
from .performance_marks import PERFORMANCE_MARKS

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

# 演奏标记与力度记号的词表，最长优先匹配。
# `^tr`、`\pp` 这类多字符写法必须整段匹配，否则调用方会把 `^t` 之后的 `r` 当成正文。
_MARK_TOKENS_LONGEST_FIRST = tuple(
    sorted({mark.token for mark in PERFORMANCE_MARKS}, key=len, reverse=True)
)
_DYNAMICS_LONGEST_FIRST = tuple(sorted(DYNAMICS, key=len, reverse=True))
# 音高核心：[前缀变音]音级[八度点][后缀变音]。
# 前后缀变音都要纳入，否则 `5#` 这类后缀写法会被截断成 `5`，
# 替换时残留的 `#` 会与新的前缀变音叠加成 `b7,#` 这种语法损坏的 token。
PITCH_CORE_PATTERN = re.compile(
    r"(?:tqf|tqs|qf|qs|bb|x|n|\u266E|#|b)?[1-7][',]*(?:bb|x|#|b)?"
)
_PITCH_TRAILING_PATTERN = re.compile(r"[-.~)]*")


def mark_token_prefix(value: str) -> str:
    """返回 value 开头的演奏标记 token（不含 `^`）；无匹配返回空串。"""
    return next(
        (token for token in _MARK_TOKENS_LONGEST_FIRST if value.startswith(token)),
        "",
    )


def dynamic_token_prefix(value: str) -> str:
    """返回 value 开头的力度记号 token（不含 `\\`）；无匹配返回空串。"""
    return next(
        (token for token in _DYNAMICS_LONGEST_FIRST if value.startswith(token)),
        "",
    )


def leading_decoration_length(token: str) -> int:
    """返回 token 开头连续的非音高装饰长度（圆滑线、延音线、力度、演奏标记）。"""
    index = 0
    while index < len(token):
        char = token[index]
        if char in "(~":
            index += 1
            continue
        if char == "\\":
            dynamic = dynamic_token_prefix(token[index + 1 :])
            if not dynamic:
                break
            index += 1 + len(dynamic)
            continue
        if char == "^":
            mark = mark_token_prefix(token[index + 1 :])
            if not mark:
                break
            index += 1 + len(mark)
            continue
        break
    return index


def pitch_core_spans(token: str) -> list[tuple[int, int]]:
    """定位一个空白分隔 token 内所有音高核心的 (start, end)。

    覆盖时值前缀（q1/h5.）、和弦（[1+3+5]）、前后缀变音、力度与演奏标记附着
    （\\pp1、^tr1）、时值延长与附点（1-、1.）、圆滑线与延音线。
    休止符 0、小节线、重复次数 *2、小节标签 12: 等返回空列表。
    """
    if not token or token == "0":
        return []
    index = leading_decoration_length(token)
    index += len(duration_prefix(token[index:]))
    if index < len(token) and token[index] == "[":
        close = token.find("]", index)
        if close < 0:
            return []
        if _PITCH_TRAILING_PATTERN.fullmatch(token[close + 1 :]) is None:
            return []
        spans: list[tuple[int, int]] = []
        cursor = index + 1
        for match in PITCH_CORE_PATTERN.finditer(token, cursor, close):
            # 元素之间只允许 `+` 分隔，否则该 `[...]` 不是合法和弦。
            if token[cursor : match.start()].strip("+"):
                return []
            spans.append((match.start(), match.end()))
            cursor = match.end()
        return spans if not token[cursor:close].strip("+") else []
    match = PITCH_CORE_PATTERN.match(token, index)
    if match is None:
        return []
    if _PITCH_TRAILING_PATTERN.fullmatch(token[match.end() :]) is None:
        return []
    return [(match.start(), match.end())]


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


def safe_duration_affixes(duration: Fraction) -> tuple[str, str]:
    if duration <= 0:
        return "", ""
    try:
        return duration_affixes(duration)
    except ValueError:
        pass
    best_result: tuple[str, str] | None = None
    best_diff: Fraction | None = None
    for precision in range(8):
        unit = Fraction(1, 2**precision)
        lower = (duration // unit) * unit
        for candidate in (lower, lower + unit):
            if candidate <= 0:
                continue
            try:
                result = duration_affixes(candidate)
            except ValueError:
                continue
            diff = abs(candidate - duration)
            if best_diff is None or diff < best_diff:
                best_result = result
                best_diff = diff
                if diff == 0:
                    return best_result
    return best_result or ("", "")


def dotted_duration(base_duration: Fraction, dot_count: int) -> Fraction:
    if dot_count < 0:
        raise ValueError("附点数量不能为负数")
    return base_duration * (2 - Fraction(1, 2**dot_count))


def is_notatable_duration(duration: Fraction) -> bool:
    return duration > 0 and (duration.denominator & (duration.denominator - 1)) == 0


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


def tuplet_normal_notes(actual_notes: int) -> int:
    normal_notes = 1
    while normal_notes * 2 <= actual_notes:
        normal_notes *= 2
    return max(1, normal_notes)
