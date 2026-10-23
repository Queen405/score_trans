"""反复跳跃房子（跳房子 / volta endings）的共享纯算法。

文本语法 ``{1.}`` / ``{1,2.}`` / ``{.}``、MusicXML ``<ending>`` 元素与
渲染器、播放展开等消费方共用这里的编号规范化与跨度扫描，避免各层重复实现。

模型约定（与 MusicXML 语义一致）：房子只在边界小节落标记——
``Measure.ending_start`` 开房子，``Measure.ending_stop`` / ``ending_discontinue``
闭房子，中间小节不带任何标记；跨度由 :func:`ending_spans` 扫描推导。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..models.score import Measure

_ENDING_NUMBER_PART = re.compile(r"\d+")


@dataclass(slots=True)
class EndingSpan:
    """一栋房子在小节序列上的跨度（下标闭区间）。"""

    number: str
    """规范化编号，如 ``"1"`` 或 ``"1,2"``。"""
    start: int
    """``ending_start`` 所在小节下标。"""
    stop: int
    """``ending_stop`` / ``ending_discontinue`` 所在小节下标。"""
    discontinue: bool = False
    """True = 开口结束（MusicXML discontinue，不画右竖钩）。"""


def normalize_ending_number(raw: str) -> str:
    """规范化房子编号为半角逗号无空格形式：``"1， 2."`` → ``"1,2"``。

    编号必须是正整数或逗号分隔的正整数组合；非法输入抛 ``ValueError``。
    """
    parts = _ENDING_NUMBER_PART.findall(raw.replace("，", ","))
    numbers = [int(part) for part in parts]
    if not numbers or any(number <= 0 for number in numbers):
        raise ValueError(f"房子编号无效：{raw!r}，应为正整数或逗号分隔的正整数组合")
    return ",".join(str(number) for number in numbers)


def ending_pass_numbers(number: str) -> set[int]:
    """规范化编号 → 该房子参与播放的遍数集合，如 ``"1,2"`` → ``{1, 2}``。"""
    return {int(part) for part in number.split(",")}


def ending_display_label(number: str) -> str:
    """谱面印刷样式的房子标签：``"1,2"`` → ``"1, 2."``。"""
    return ", ".join(part.strip() for part in number.split(",")) + "."


def ending_spans(measures: list[Measure | None]) -> list[EndingSpan]:
    """从边界标记扫描房子跨度，下标与输入列表（含 None 空洞）对齐。

    - ``ending_start`` 开一栋房子；若已有开着的房子，先在前一小节闭合它；
    - ``ending_stop`` / ``ending_discontinue`` 在当前小节闭房子；
    - 未闭合的房子延伸到最后一个小节（文本自动闭合规则之外的 MusicXML 数据）；
    - 没有开房子的孤立 stop/discontinue 标记被忽略。
    """
    spans: list[EndingSpan] = []
    open_number: str | None = None
    open_start = 0
    for index, measure in enumerate(measures):
        if measure is None:
            continue
        if measure.ending_start is not None:
            if open_number is not None and index > open_start:
                spans.append(EndingSpan(open_number, open_start, index - 1))
            open_number = measure.ending_start
            open_start = index
        if open_number is not None and (
            measure.ending_stop is not None or measure.ending_discontinue is not None
        ):
            spans.append(
                EndingSpan(
                    open_number,
                    open_start,
                    index,
                    discontinue=measure.ending_stop is None,
                )
            )
            open_number = None
    if open_number is not None and measures:
        spans.append(EndingSpan(open_number, open_start, len(measures) - 1))
    return spans
