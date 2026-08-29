from __future__ import annotations

from pydantic import BaseModel, Field


class JianpuRekeyRequest(BaseModel):
    text: str = Field(..., description="当前简谱文本（包含新的调号）")
    previous_text: str = Field(..., description="之前的简谱文本（用于获取旧调号信息）")


class JianpuRekeyResponse(BaseModel):
    transposed_text: str = Field(..., description="转调后的文本")
