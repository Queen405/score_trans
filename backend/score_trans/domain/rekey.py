from __future__ import annotations

import logging
import re
from fractions import Fraction

from .accidentals import pitch_to_token
from .parse.jianpu_text import parse_jianpu_score
from .pitch_spelling import jianpu_pitch_to_written, written_pitch_to_jianpu
from ..models.common.types import AccidentalMode
from ..models.score import JianpuPitch

logger = logging.getLogger(__name__)

# A "key" line: 1=C, 1=Bb, 1=F# ... (uppercase letter + optional accidental).
_KEY_LINE = re.compile(r"^1\s*=\s*([A-G][#b]*)")
# A single pitch: optional accidental prefix, degree 1-7, optional octave markers.
_PITCH = re.compile(r"(tqf|tqs|qf|qs|bb|x|n|\u266E|#|b)?([1-7])([',]*)")
# Tuplet body starts with an optional ratio like "3:2;".
_TUPLET_RATIO = re.compile(r"^\d+\s*:\s*\d+\s*;")
# Tokens: tuplet $...$, barlines, or a run of non-space non-pipe chars.
_TOKEN = re.compile(r"\$[^$]+\$|\|\||\|:|:\||\||[^\s|]+")

_BARLINES = {"|", "||", "|:", ":|"}

_ACCIDENTAL_MAP: dict[str, Fraction] = {
    "#": Fraction(1, 1),
    "x": Fraction(2, 1),
    "n": Fraction(0, 1),
    "\u266E": Fraction(0, 1),
    "b": Fraction(-1, 1),
    "bb": Fraction(-2, 1),
    "qs": Fraction(1, 2),
    "qf": Fraction(-1, 2),
    "tqs": Fraction(3, 2),
    "tqf": Fraction(-3, 2),
}


def rekey_text(
    text: str,
    previous_text: str,
    *,
    accidental_mode: AccidentalMode = "auto",
) -> str:
    """根据之前的简谱文本，将当前文本中的音符按新调号转调以保持音高不变。

    定位 old/new 文本中首个"取值不同的调号行"(1=X)，只转调其后到下一个调号行
    (或文末)之间的音符行；调号、拍号、歌词、注释、小节线、空白与排版原样保留。
    """
    try:
        parse_jianpu_score(previous_text)
        parse_jianpu_score(text)
    except Exception as exc:  # noqa: BLE001
        logger.warning("解析简谱失败：%s", exc)
        return text

    old_lines = previous_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    new_lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    # 定位首个取值不同的调号行(按行对齐，覆盖顶部换调与中途换调)。
    change_index = -1
    old_key = ""
    new_key = ""
    for index in range(min(len(old_lines), len(new_lines))):
        old_match = _KEY_LINE.match(old_lines[index].strip())
        new_match = _KEY_LINE.match(new_lines[index].strip())
        if old_match and new_match and old_match.group(1) != new_match.group(1):
            change_index = index
            old_key = old_match.group(1)
            new_key = new_match.group(1)
            break
    if change_index < 0 or not old_key or not new_key:
        return text

    result: list[str] = []
    in_segment = False
    for index, line in enumerate(new_lines):
        if index == change_index:
            in_segment = True
            result.append(line)
            continue
        if in_segment:
            # 遇到下一个调号行则停止(那是另一段调号)。
            if _KEY_LINE.match(line.strip()):
                in_segment = False
                result.append(line)
            elif _is_metadata_line(line):
                result.append(line)
            else:
                result.append(_rekey_note_line(line, old_key, new_key, accidental_mode))
        else:
            result.append(line)
    return "\n".join(result)


def _is_metadata_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped or stripped.startswith("//"):
        return True
    if stripped.startswith("L:") or stripped.startswith("@text "):
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


def _rekey_note_line(
    line: str,
    old_key: str,
    new_key: str,
    accidental_mode: AccidentalMode,
) -> str:
    """转调一行中的音符 token，保留小节线、空白、注释等。"""
    comment_start = line.find("//")
    if comment_start < 0:
        code = line
        comment = ""
    else:
        code = line[:comment_start]
        comment = line[comment_start:]

    def repl(match: re.Match[str]) -> str:
        token = match.group(0)
        if token.startswith("$") and token.endswith("$") and len(token) > 2:
            return "$" + _rekey_tuplet_body(token[1:-1], old_key, new_key, accidental_mode) + "$"
        if token in _BARLINES:
            return token
        transposed = _rekey_pitch_token(token, old_key, new_key, accidental_mode)
        return transposed if transposed is not None else token

    return _TOKEN.sub(repl, code) + comment


def _rekey_tuplet_body(
    body: str,
    old_key: str,
    new_key: str,
    accidental_mode: AccidentalMode,
) -> str:
    """转调连音组主体:跳过开头的比例(如 3:2;)，转调其后的音符。"""
    ratio_match = _TUPLET_RATIO.match(body)
    ratio = ratio_match.group(0) if ratio_match else ""
    rest = body[len(ratio):]
    return ratio + _rekey_pitches(rest, old_key, new_key, accidental_mode)


def _rekey_pitch_token(
    token: str,
    old_key: str,
    new_key: str,
    accidental_mode: AccidentalMode,
) -> str | None:
    """转调单个音符 token(可带装饰/附点);非单个音符返回 None。"""
    lead = ""
    work = token
    while work and work[0] in "~(":
        lead += work[0]
        work = work[1:]
    trail = ""
    while work and work[-1] in "~).":
        trail = work[-1] + trail
        work = work[:-1]
    if not work:
        return None
    match = _PITCH.fullmatch(work)
    if not match:
        return None
    acc_str, deg_str, oct_str = match.group(1), match.group(2), match.group(3)
    accidental = _ACCIDENTAL_MAP.get(acc_str, Fraction(0, 1)) if acc_str else Fraction(0, 1)
    degree = int(deg_str)
    octave = oct_str.count("'") - oct_str.count(",")
    new_degree, new_accidental, new_octave = _rekey_single_pitch(
        degree, accidental, octave, old_key, new_key
    )
    token_core = pitch_to_token(
        JianpuPitch(degree=new_degree, accidental=new_accidental, octave=new_octave),
        accidental_mode=accidental_mode,
    )
    return lead + token_core + trail


def _rekey_pitches(
    text: str,
    old_key: str,
    new_key: str,
    accidental_mode: AccidentalMode,
) -> str:
    """对一段文本中的每个音高([变音]音级[八度])做转调替换。"""

    def repl(match: re.Match[str]) -> str:
        acc_str, deg_str, oct_str = match.group(1), match.group(2), match.group(3)
        accidental = _ACCIDENTAL_MAP.get(acc_str, Fraction(0, 1)) if acc_str else Fraction(0, 1)
        degree = int(deg_str)
        octave = oct_str.count("'") - oct_str.count(",")
        new_degree, new_accidental, new_octave = _rekey_single_pitch(
            degree, accidental, octave, old_key, new_key
        )
        return pitch_to_token(
            JianpuPitch(degree=new_degree, accidental=new_accidental, octave=new_octave),
            accidental_mode=accidental_mode,
        )

    return _PITCH.sub(repl, text)


def _rekey_single_pitch(
    degree: int,
    accidental: Fraction,
    octave: int,
    old_key: str,
    new_key: str,
) -> tuple[int, Fraction, int]:
    """单个音高的转调计算:经绝对音高在两个调号间映射。"""
    step, alter, abs_octave = jianpu_pitch_to_written(degree, accidental, octave, old_key)
    return written_pitch_to_jianpu(step, alter, abs_octave, new_key)
