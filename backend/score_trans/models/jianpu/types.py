from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# 未能转调的原因。前端据此决定是否提示用户，以及提示什么。
#   parse_error              当前文本本身解析失败（含解析器的调号位置约束）
#   no_key_token             当前文本里没有任何调号 token，无从下手
#   unresolvable_key_change  调号序列确实变了，但无法定出「旧调 → 新调」的区间
#                            （例如调号被整个删除，新文本里已无该调号可作边界）
RekeySkipReason = Literal["parse_error", "no_key_token", "unresolvable_key_change"]


@dataclass(slots=True, frozen=True)
class RekeyAnchorMapping:
    """A semantic span mapping from the rekey request text to its output text."""

    role: str
    old_start_utf16: int
    old_end_utf16: int
    new_start_utf16: int
    new_end_utf16: int


@dataclass(slots=True)
class RekeyResult:
    """转调结果。

    text 恒为可直接写回编辑器的文本：转调成功时是新文本，跳过时是原样输入。
    skip_reason 为 None 表示「正常」——既包括真的转调了，也包括调号序列没变、
    本来就无需转调。区分二者只需比较 text 与输入。
    """

    text: str
    skip_reason: RekeySkipReason | None = None
    detail: str = ""
    # Coordinates are mapped from the rekey request's ``text`` (new key with
    # old pitches) to ``text`` after the semantic rewrite, not from
    # ``previous_text``. The editor's existing anchors live on that request
    # text when the asynchronous response arrives.
    anchor_mapping: list[RekeyAnchorMapping] | None = None
