from __future__ import annotations

import logging
import re
from fractions import Fraction

from .accidentals import pitch_to_token
from .jianpu_tokens import PITCH_CORE_PATTERN, pitch_core_spans
from .parse.jianpu_text import parse_jianpu_score
from .pitch_spelling import (
    jianpu_pitch_to_written,
    written_pitch_to_jianpu_respelled,
)
from ..models.common.types import AccidentalMode
from ..models.score import JianpuPitch

logger = logging.getLogger(__name__)

# 调号 token：1=X（X = [A-G] 后跟至多一个 # 或 b）。
# 词表与解析器 parse/jianpu_text.py 的 _is_key_name 保持一致；放宽会接受
# 1=Bbb 这类解析器拒绝的写法，收紧会漏掉合法的 1=Bb / 1=F#。
_KEY_TOKEN = re.compile(r"1\s*=\s*([A-G](?:#|b)?)")
# 独占一行的调号，用于 _is_metadata_line。
_KEY_LINE = re.compile(r"^1\s*=\s*([A-G](?:#|b)?)")
# 连音组主体开头的可选比例，如 "3:2;"。
_TUPLET_RATIO = re.compile(r"^\d+\s*:\s*\d+\s*;")
# token：连音组 $...$、小节线，或一段不含空白与竖线的字符。
_TOKEN = re.compile(r"\$[^$]+\$|\|\||\|:|:\||\||[^\s|]+")

_BARLINES = {"|", "||", "|:", ":|"}

_NATURAL_TEXTS = ("n", "\u266e")
# 前缀变音词表，最长优先（bb 必须先于 b，tqf/tqs 必须先于 qf/qs）。
_PREFIX_ACCIDENTALS: tuple[tuple[str, Fraction], ...] = (
    ("tqf", Fraction(-3, 2)),
    ("tqs", Fraction(3, 2)),
    ("qf", Fraction(-1, 2)),
    ("qs", Fraction(1, 2)),
    ("bb", Fraction(-2, 1)),
    ("x", Fraction(2, 1)),
    ("n", Fraction(0, 1)),
    ("\u266e", Fraction(0, 1)),
    ("#", Fraction(1, 1)),
    ("b", Fraction(-1, 1)),
)
# 后缀变音词表，最长优先。
_SUFFIX_ACCIDENTALS: tuple[tuple[str, Fraction], ...] = (
    ("bb", Fraction(-2, 1)),
    ("x", Fraction(2, 1)),
    ("#", Fraction(1, 1)),
    ("b", Fraction(-1, 1)),
)


class _KeyToken:
    """文本中一个调号 token 的位置与取值。"""

    __slots__ = ("line", "start", "end", "key")

    def __init__(self, line: int, start: int, end: int, key: str) -> None:
        self.line = line
        self.start = start
        self.end = end
        self.key = key


class _Segment:
    """一段需要转调的区间：[起点, 终点) 以及新旧调号。"""

    __slots__ = ("start_line", "start_col", "end_line", "end_col", "old_key", "new_key")

    def __init__(
        self,
        start_line: int,
        start_col: int,
        end_line: int,
        end_col: int,
        old_key: str,
        new_key: str,
    ) -> None:
        self.start_line = start_line
        self.start_col = start_col
        self.end_line = end_line
        self.end_col = end_col
        self.old_key = old_key
        self.new_key = new_key


def rekey_text(
    text: str,
    previous_text: str,
    *,
    accidental_mode: AccidentalMode = "auto",
) -> str:
    """根据之前的简谱文本，将当前文本中的音符按新调号转调以保持音高不变。

    以 token 级定位调号(1=X，可独占一行或紧跟在小节线 | 之后)，覆盖顶部换调、
    中途换调、行内换调与多字符调号(Bb/F#)。新旧调号序列按 LCS 对齐，一次调用可
    处理多处改动与中途插入调号。只转调「变化的调号之后、到下一个调号(或文末)」
    之间的音符；调号、拍号、歌词、注释、小节线、空白与排版原样保留。

    调号 token 被删除的情形不做转调：新文本中已无该调号，无法从调号序列恢复
    「哪些音符原属被删调号」的边界。
    """
    try:
        parse_jianpu_score(previous_text)
        parse_jianpu_score(text)
    except Exception as exc:  # noqa: BLE001
        logger.warning("解析简谱失败：%s", exc)
        return text

    newline = _detect_newline(text)
    normalized = _normalize_newlines(text)
    old_tokens = _find_key_tokens(_normalize_newlines(previous_text))
    new_tokens = _find_key_tokens(normalized)
    if not new_tokens:
        return text

    segments = _changed_segments(old_tokens, new_tokens, normalized)
    if not segments:
        return text

    lines = normalized.split("\n")
    # 区间互不重叠，倒序应用可让尚未处理的区间偏移保持有效。
    for segment in reversed(segments):
        _apply_segment(lines, segment, accidental_mode)
    return newline.join(lines)


def _detect_newline(text: str) -> str:
    """探测原文行尾，输出时原样还原，避免把 CRLF 文档静默改成 LF。"""
    if "\r\n" in text:
        return "\r\n"
    if "\r" in text:
        return "\r"
    return "\n"


def _normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _find_key_tokens(text: str) -> list[_KeyToken]:
    """返回所有调号 token（已归一化行尾的文本）。

    调号须是独立 token（前后为行首/空白/小节线），因此能识别独占一行的 1=G
    与紧跟 | 之后的 1=G。行内注释与歌词/文本行中的 1=X 字样不算调号。
    """
    tokens: list[_KeyToken] = []
    for line_index, raw_line in enumerate(text.split("\n")):
        line = _strip_inline_comment(raw_line)
        if _is_lyric_or_text_line(line):
            continue
        for match in _KEY_TOKEN.finditer(line):
            start, end = match.start(), match.end()
            prev_ok = start == 0 or line[start - 1] in " \t|"
            next_ok = end == len(line) or line[end] in " \t|"
            if prev_ok and next_ok:
                tokens.append(_KeyToken(line_index, start, end, match.group(1)))
    return tokens


def _changed_segments(
    old_tokens: list[_KeyToken],
    new_tokens: list[_KeyToken],
    text: str,
) -> list[_Segment]:
    """比对新旧调号序列，返回所有需要转调的区间（按出现顺序）。

    按 LCS 对齐而非下标配对：在中途插入调号时，下标配对会把「插入位置之后的
    段落」误判为原属后一个调号，用错旧调。
    """
    line_lengths = [len(line) for line in text.split("\n")]
    segments: list[_Segment] = []
    # 走查对齐结果时记录「旧文本中此刻生效的调号」，用于新增调号的旧调来源。
    effective_old_key = ""
    for operation, old_index, new_index in _align_keys(
        [token.key for token in old_tokens], [token.key for token in new_tokens]
    ):
        if operation == "equal":
            effective_old_key = old_tokens[old_index].key
            continue
        if operation == "delete":
            effective_old_key = old_tokens[old_index].key
            continue
        old_key = (
            old_tokens[old_index].key if operation == "replace" else effective_old_key
        )
        new_key = new_tokens[new_index].key
        if operation == "replace":
            effective_old_key = old_tokens[old_index].key
        if old_key and old_key != new_key:
            segments.append(
                _segment_for(new_tokens, new_index, old_key, new_key, line_lengths)
            )
    return segments


def _segment_for(
    new_tokens: list[_KeyToken],
    index: int,
    old_key: str,
    new_key: str,
    line_lengths: list[int],
) -> _Segment:
    token = new_tokens[index]
    if index + 1 < len(new_tokens):
        following = new_tokens[index + 1]
        return _Segment(
            token.line, token.end, following.line, following.start, old_key, new_key
        )
    last_line = len(line_lengths) - 1
    return _Segment(
        token.line, token.end, last_line, line_lengths[last_line], old_key, new_key
    )


def _align_keys(old_keys: list[str], new_keys: list[str]) -> list[tuple[str, int, int]]:
    """按 LCS 对齐两个调号序列，返回 (操作, 旧下标, 新下标) 序列。

    操作为 equal / replace / insert / delete。连续的 delete+insert 块按位置配成
    replace，多出的部分保留为 insert 或 delete。
    """
    matched = _lcs_pairs(old_keys, new_keys)
    operations: list[tuple[str, int, int]] = []
    old_cursor = 0
    new_cursor = 0
    for old_index, new_index in [*matched, (len(old_keys), len(new_keys))]:
        deleted = list(range(old_cursor, old_index))
        inserted = list(range(new_cursor, new_index))
        paired = min(len(deleted), len(inserted))
        for offset in range(paired):
            operations.append(("replace", deleted[offset], inserted[offset]))
        for extra in deleted[paired:]:
            operations.append(("delete", extra, -1))
        for extra in inserted[paired:]:
            operations.append(("insert", -1, extra))
        if old_index < len(old_keys) and new_index < len(new_keys):
            operations.append(("equal", old_index, new_index))
        old_cursor = old_index + 1
        new_cursor = new_index + 1
    return operations


def _lcs_pairs(old_keys: list[str], new_keys: list[str]) -> list[tuple[int, int]]:
    """返回最长公共子序列的下标配对。"""
    rows, columns = len(old_keys), len(new_keys)
    table = [[0] * (columns + 1) for _ in range(rows + 1)]
    for row in range(rows - 1, -1, -1):
        for column in range(columns - 1, -1, -1):
            if old_keys[row] == new_keys[column]:
                table[row][column] = table[row + 1][column + 1] + 1
            else:
                table[row][column] = max(table[row + 1][column], table[row][column + 1])
    pairs: list[tuple[int, int]] = []
    row = column = 0
    while row < rows and column < columns:
        if old_keys[row] == new_keys[column]:
            pairs.append((row, column))
            row += 1
            column += 1
        elif table[row + 1][column] >= table[row][column + 1]:
            row += 1
        else:
            column += 1
    return pairs


def _apply_segment(
    lines: list[str],
    segment: _Segment,
    accidental_mode: AccidentalMode,
) -> None:
    """就地转调 lines 中 segment 覆盖的区间。"""
    for line_index in range(segment.start_line, segment.end_line + 1):
        if line_index >= len(lines):
            break
        line = lines[line_index]
        start = segment.start_col if line_index == segment.start_line else 0
        end = segment.end_col if line_index == segment.end_line else len(line)
        if start >= end:
            continue
        head, body, tail = line[:start], line[start:end], line[end:]
        # 边界行也要过 metadata 判定：歌词/文本/拍号行若正好落在区间首尾，
        # 直接按音符处理会把「L: 1 2」改写成「L: 4, 5,」。
        # 区间起点紧跟在调号 token 之后，因此 body 不会包含本段调号本身。
        if _is_metadata_line(body):
            continue
        lines[line_index] = (
            head
            + _rekey_note_line(body, segment.old_key, segment.new_key, accidental_mode)
            + tail
        )


def _is_metadata_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped or stripped.startswith("//"):
        return True
    if _is_lyric_or_text_line(stripped):
        return True
    if re.match(r"^(title|tempo)\s*=", stripped):
        return True
    if _KEY_LINE.match(stripped):
        return True
    if re.match(r"^(key|time)\s*=", stripped, re.IGNORECASE):
        return True
    if re.match(r"^\d+\s*/\s*\d+$", stripped):
        return True
    return False


def _is_lyric_or_text_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("L:") or stripped.startswith("@text ")


def _strip_inline_comment(line: str) -> str:
    comment_start = line.find("//")
    if comment_start < 0:
        return line
    return line[:comment_start]


def _rekey_note_line(
    line: str,
    old_key: str,
    new_key: str,
    accidental_mode: AccidentalMode,
) -> str:
    """转调一行中的音符 token，保留小节线、空白、注释等。"""
    comment_start = line.find("//")
    if comment_start < 0:
        code, comment = line, ""
    else:
        code, comment = line[:comment_start], line[comment_start:]

    def replace(match: re.Match[str]) -> str:
        token = match.group(0)
        if token.startswith("$") and token.endswith("$") and len(token) > 2:
            body = _rekey_tuplet_body(token[1:-1], old_key, new_key, accidental_mode)
            return f"${body}$"
        if token in _BARLINES:
            return token
        return _rekey_event_token(token, old_key, new_key, accidental_mode)

    return _TOKEN.sub(replace, code) + comment


def _rekey_tuplet_body(
    body: str,
    old_key: str,
    new_key: str,
    accidental_mode: AccidentalMode,
) -> str:
    """转调连音组主体：跳过开头的比例(如 3:2;)，转调其后的音符。

    连音组主体既可空白分隔（$q1 q2 q3$），也可紧排（$123$）。紧排时无法按空白切
    token，改为直接扫描音高核心；这与解析器 _split_tuplet_body 的两种模式一致。
    """
    ratio_match = _TUPLET_RATIO.match(body)
    ratio = ratio_match.group(0) if ratio_match else ""
    rest = body[len(ratio) :]
    if rest.strip() and not re.search(r"\s", rest.strip()):
        return ratio + _rekey_pitch_cores(rest, old_key, new_key, accidental_mode)
    parts = re.split(r"(\s+)", rest)
    rekeyed = [
        part
        if not part or part.isspace()
        else _rekey_event_token(part, old_key, new_key, accidental_mode)
        for part in parts
    ]
    return ratio + "".join(rekeyed)


def _rekey_event_token(
    token: str,
    old_key: str,
    new_key: str,
    accidental_mode: AccidentalMode,
) -> str:
    """转调一个事件 token 内的所有音高核心，其余字符原样保留。

    只替换音高核心的字符区间，因此时值前缀、和弦括号、力度与演奏标记、
    时值延长与附点、圆滑线与延音线都不受影响。
    """
    spans = pitch_core_spans(token)
    if not spans:
        return token
    pieces: list[str] = []
    cursor = 0
    for start, end in spans:
        pieces.append(token[cursor:start])
        pieces.append(
            _rekey_pitch_core(token[start:end], old_key, new_key, accidental_mode)
        )
        cursor = end
    pieces.append(token[cursor:])
    return "".join(pieces)


def _rekey_pitch_cores(
    text: str,
    old_key: str,
    new_key: str,
    accidental_mode: AccidentalMode,
) -> str:
    """对一段紧排文本中的每个音高核心做转调替换。"""

    def replace(match: re.Match[str]) -> str:
        return _rekey_pitch_core(match.group(0), old_key, new_key, accidental_mode)

    return PITCH_CORE_PATTERN.sub(replace, text)


def _rekey_pitch_core(
    core: str,
    old_key: str,
    new_key: str,
    accidental_mode: AccidentalMode,
) -> str:
    degree, accidental, octave, is_natural = _parse_pitch_core(core)
    if degree is None:
        return core
    if is_natural:
        # 还原记号表示「取消调号对该音级的变音」，有效变音是 -key_alter，不是 0。
        # 与解析器 parse/jianpu_text.py 中 accidental_text in {"n","♮"} 的处理一致。
        _step, key_alter, _octave = jianpu_pitch_to_written(
            degree, Fraction(0, 1), octave, old_key
        )
        accidental = -key_alter
    step, alter, absolute_octave = jianpu_pitch_to_written(
        degree, accidental, octave, old_key
    )
    new_degree, new_accidental, new_octave = written_pitch_to_jianpu_respelled(
        step, alter, absolute_octave, new_key, accidental_mode=accidental_mode
    )
    return pitch_to_token(
        JianpuPitch(degree=new_degree, accidental=new_accidental, octave=new_octave),
        accidental_mode=accidental_mode,
    )


def _parse_pitch_core(core: str) -> tuple[int | None, Fraction, int, bool]:
    """解析音高核心为 (音级, 变音, 八度, 是否还原记号)。

    前后缀变音的取舍顺序与解析器 _parse_pitch 一致：后缀存在时覆盖前缀。
    """
    work = core
    accidental = Fraction(0, 1)
    is_natural = False
    for text, value in _PREFIX_ACCIDENTALS:
        if work.startswith(text):
            accidental = value
            is_natural = text in _NATURAL_TEXTS
            work = work[len(text) :]
            break
    for text, value in _SUFFIX_ACCIDENTALS:
        if work.endswith(text):
            accidental = value
            is_natural = False
            work = work[: -len(text)]
            break
    octave = work.count("'") - work.count(",")
    digits = work.replace("'", "").replace(",", "")
    if digits not in {"1", "2", "3", "4", "5", "6", "7"}:
        return None, accidental, octave, is_natural
    return int(digits), accidental, octave, is_natural
