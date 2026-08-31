from __future__ import annotations

from pydantic import BaseModel, Field

from .types import RekeyAnchorMapping, RekeySkipReason


class JianpuRekeyRequest(BaseModel):
    text: str = Field(..., description="当前简谱文本（包含新的调号）")
    previous_text: str = Field(..., description="之前的简谱文本（用于获取旧调号信息）")


class JianpuRekeyResponse(BaseModel):
    transposed_text: str = Field(..., description="转调后的文本")
    skip_reason: RekeySkipReason | None = Field(
        default=None,
        description="未转调的原因；None 表示正常（已转调，或调号未变本就无需转调）",
    )
    skip_detail: str = Field(
        default="",
        description="跳过原因的补充说明，例如解析器的报错原文",
    )
    anchor_mapping: list[RekeyAnchorMapping] | None = Field(
        default=None,
        description=(
            "纯调号重写时从请求文本到转调文本的 token/角色 UTF-16 区间映射；"
            "token 区间供诊断和兼容扩展使用，无法一一对应时为 null"
        ),
    )
