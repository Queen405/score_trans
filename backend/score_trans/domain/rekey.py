from __future__ import annotations

import logging
import re
from typing import cast

from .accidentals import pitch_to_token
from .parse.jianpu_text import parse_jianpu_score
from .pitch_spelling import written_pitch_to_jianpu, jianpu_pitch_to_written
from .write.jianpu_text import _event_to_token, score_to_jianpu_document
from ..models.common.types import AccidentalMode
from ..models.score import Event, JianpuPitch, Measure

logger = logging.getLogger(__name__)


def rekey_text(
    text: str,
    previous_text: str,
    *,
    accidental_mode: AccidentalMode = "auto",
) -> str:
    """根据之前的简谱文本，将当前文本中的音符按新调号转调以保持音高不变。
    
    Args:
        text: 当前简谱文本（包含新调号）
        previous_text: 之前的简谱文本（包含旧调号）
        accidental_mode: 变音记号模式
    
    Returns:
        转调后的文本
    """
    try:
        old_score = parse_jianpu_score(previous_text)
        new_score = parse_jianpu_score(text)
    except Exception as exc:
        logger.warning("解析简谱失败：%s", exc)
        return text
    
    if not old_score.measures or not new_score.measures:
        return text
    
    # 找首个 target_key 不同的 measure（用户的调号改动点）
    key_change_point: int | None = None
    for i, (old_measure, new_measure) in enumerate(zip(old_score.measures, new_score.measures)):
        if old_measure.target_key != new_measure.target_key:
            key_change_point = i
            break
    
    if key_change_point is None:
        return text
    
    old_key = old_score.target_key
    new_key = new_score.target_key
    
    # 如果新旧调号相同，返回原文本
    if old_key == new_key:
        return text
    
    # 找到影响段的结束位置（下一个 key-change 或结尾）
    influence_end = _find_influence_end(new_score, key_change_point)
    
    # 解析文档以获取 anchors
    new_doc = score_to_jianpu_document(new_score, accidental_mode=accidental_mode)
    
    # 对指定段落进行外科式转调替换
    result_text = _transpose_segment(
        new_doc.text,
        new_doc.anchors,
        key_change_point,
        influence_end,
        old_key,
        new_key,
        accidental_mode,
    )
    
    return result_text


def _find_influence_end(score, start_index: int) -> int:
    """找到影响段的结束位置（下一个 key-change 或结尾）。"""
    current_key = score.measures[start_index].target_key
    
    for i in range(start_index + 1, len(score.measures)):
        if score.measures[i].target_key != current_key:
            return i
    
    return len(score.measures)


def _transpose_segment(
    text: str,
    anchors,
    start_measure: int,
    end_measure: int,
    old_key: str,
    new_key: str,
    accidental_mode: AccidentalMode,
) -> str:
    """对指定段落进行外科式转调替换。"""
    from dataclasses import fields
    
    # 收集所有需要转调的 note events（按 start_utf16 排序，从右到左替换避免偏移）
    notes_to_rekey: list[tuple[int, str]] = []
    
    for anchor in anchors:
        if hasattr(anchor, 'role') and anchor.role == "note":
            if hasattr(anchor, 'start_utf16') and anchor.start_utf16 is not None:
                if hasattr(anchor, 'end_utf16') and anchor.end_utf16 is not None:
                    if anchor.end_utf16 > anchor.start_utf16:
                        event_id = anchor.source_id
                        if event_id:
                            notes_to_rekey.append((anchor.start_utf16, event_id))
    
    # 按 start_utf16 降序排列（从右到左替换）
    notes_to_rekey.sort(key=lambda x: x[0], reverse=True)
    
    # 逐字符构建结果
    chars = list(text)
    
    for _, event_id in notes_to_rekey:
        # 简单跳过 anchor-based 替换，直接对整个文本区间操作
        
        # 在文本中定位事件 → 太复杂了，使用替代方案：
        # 对整个文本重新生成，但只在受影响段内改变调号
        
        pass
    
    # 更简单的方法：整个重新序列化，但只改受影响段内的目标调号
    return _rekey_by_reserialize(text, old_key, new_key, start_measure, end_measure, accidental_mode)


def _rekey_by_reserialize(
    text: str,
    old_key: str,
    new_key: str,
    start_measure: int,
    end_measure: int,
    accidental_mode: AccidentalMode,
) -> str:
    """通过重新序列化整个文本来转调，只在受影响段内应用新调号。"""
    lines = text.split('\n')
    result_lines: list[str] = []
    
    current_measure = 0
    in_affected_segment = False
    saw_initial_key = False
    
    for line_idx, line in enumerate(lines):
        stripped = line.strip()
        
        # 检查是否是 1=X 行
        key_match = re.match(r'^1\s*=[A-Gb#]$', stripped) if stripped else None
        
        if key_match:
            # 记录初始调号的位置
            if not saw_initial_key:
                saw_initial_key = True
                # 第一行调号也需转调吗？通常用户改的是第一行
                initial_key = stripped.split('=')[1].strip()
                if initial_key == old_key:
                    new_line = f"1={new_key}"
                    result_lines.append(new_line)
                    continue
            result_lines.append(line)
            continue
        
        # 检查小节线来追踪 measure 计数
        if stripped.startswith('|') or (stripped == '|' and current_measure < start_measure):
            current_measure += 1
            if current_measure >= start_measure and current_measure < end_measure:
                in_affected_segment = True
            elif current_measure >= end_measure:
                in_affected_segment = False
        
        if in_affected_segment and current_measure < end_measure:
            # 转调这行的音符
            result_lines.append(_transpose_line_according_to_key(line, old_key, new_key, accidental_mode))
        else:
            result_lines.append(line)
    
    return '\n'.join(result_lines)


def _transpose_line_according_to_key(
    line: str,
    old_key: str,
    new_key: str,
    accidental_mode: AccidentalMode,
) -> str:
    """将单行中的所有音符从 old_key 转调到 new_key。"""
    import re
    
    # 保留前缀（速度标记等）、力度符号、注释
    parts = line.split(';')  # 分离注释
    code_part = parts[0]
    comment = ';'.join(parts[1:]) if len(parts) > 1 else ''
    
    def transpose_note(match: re.Match) -> str:
        token = match.group(0)
        parsed = _parse_pitch_token(token)
        if parsed is None:
            return token
        
        degree, accidental, octave, is_note = parsed
        if not is_note or degree == 0:  # 休止符不转
            return token
        
        # 转调计算
        new_degree, new_accidental, new_octave = _rekey_single_pitch(
            degree, accidental, octave, old_key, new_key
        )
        
        # 重新生成 token
        new_pitch = JianpuPitch(
            degree=new_degree,
            accidental=new_accidental,
            octave=new_octave,
        )
        return pitch_to_token(new_pitch, accidental_mode=accidental_mode)
    
    # 匹配 pitches 包括装饰符、八度标记
    pitch_pattern = r'(?:~)?[\(\)]?[whqs]?d*\d+(?:[\'#,]*)?(?:[#bxtqnqfqs|tqs|tqf|bb]*)?'
    
    transposed = re.sub(pitch_pattern, transpose_note, code_part)
    return transposed + comment


def _parse_pitch_token(token: str) -> tuple[int, Fraction, int, bool] | None:
    """解析 pitch token（如 \"#4\", \"5,\"）为 (degree, accidental, octave, is_note)。"""
    import re
    from fractions import Fraction
    
    work = token.strip()
    
    # 移除装饰符
    while work.startswith('~'):
        work = work[1:]
    while work.startswith('('):
        work = work[1:]
    while work.endswith(')'):
        work = work[:-1]
    while work.endswith('~'):
        work = work[:-1]
    
    # 去除时长前缀
    duration_match = re.match(r'^([whqs]|d\d+)', work, re.IGNORECASE)
    if duration_match:
        work = work[len(duration_match.group(1)):]
    
    # 去除附点
    while work.endswith('.'):
        work = work[:-1]
    
    if work in ('0', '-'):
        return (0, Fraction(0), 0, False)
    
    # 和弦暂不支持
    if work.startswith('[') and work.endswith(']'):
        return None
    
    # 匹配 [变音][数字][八度]
    match = re.match(r'^(?:tqf|tqs|qf|qs|bb|x|n|\u266E|#|b)([1-7])?([\'#,]*)$', work)
    if not match:
        match = re.match(r'^([1-7])([\'#,]*)$', work)
    
    if not match:
        return None
    
    accidental_part, octave_part = match.groups()
    
    # 解析变音
    accidental = Fraction(0, 1)
    if accidental_part and accidental_part != accidental_part:  # has accidental prefix
        accidental_map = {
            '#': Fraction(1, 1), 'x': Fraction(2, 1), 'n': Fraction(0, 1),
            'b': Fraction(-1, 1), 'bb': Fraction(-2, 1),
            'qs': Fraction(1, 2), 'qf': Fraction(-1, 2),
            'tqs': Fraction(3, 2), 'tqf': Fraction(-3, 2),
        }
        accidental = accidental_map.get(accidental_part, Fraction(0, 1))
    
    degree_str = accidental_part if accidental_part else match.group(1)
    if not degree_str or not re.match(r'^[1-7]$', degree_str):
        return None
    
    degree = int(degree_str)
    
    # 解析八度
    octave = 0
    if octave_part:
        up_count = octave_part.count("'")
        down_count = octave_part.count(",")
        octave = up_count - down_count
    
    return (degree, accidental, octave, True)


def _rekey_single_pitch(
    degree: int,
    accidental: Fraction,
    octave: int,
    old_key: str,
    new_key: str,
) -> tuple[int, Fraction, int]:
    """单个音符的转调计算。"""
    # old_key 下 pitch → absolute pitch
    step, alter, abs_octave = jianpu_pitch_to_written(degree, accidental, octave, old_key)
    
    # absolute pitch → new_key 下的 degree
    new_degree, new_accidental, new_octave = written_pitch_to_jianpu(step, alter, abs_octave, new_key)
    
    return (new_degree, new_accidental, new_octave)
