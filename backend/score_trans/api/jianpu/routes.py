from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.requests import Request as FastAPIRequest

from ..dependencies import get_jianpu_actions
from ...exec.jianpu.actions import JianpuActions


router = APIRouter(prefix="/jianpu", tags=["jianpu"])


async def _parse_request_body(request: FastAPIRequest) -> dict:
    """解析请求体为字典。"""
    return await request.json()


@router.post("/rekey")
async def rekey_text_route(
    request: Request,
    actions: Annotated[JianpuActions, Depends(get_jianpu_actions)],
) -> dict:
    """根据之前的简谱文本，将当前文本中的音符按新调号转调以保持音高不变。

    Args:
        text: 当前简谱文本（包含新调号）
        previous_text: 之前的简谱文本（包含旧调号）

    Returns:
        transposed_text: 转调后的文本

    Example:
        # C 调转 G 调
        POST /jianpu/rekey
        {
            "text": "1=G\\n4 5 6",
            "previous_text": "1=C\\n4 5 6"
        }
        → {"transposed_text": "1=G\\n1 2 3"}
    """
    from pydantic import BaseModel, Field

    class RekeyRequest(BaseModel):
        text: str = Field(..., description="当前简谱文本（可能包含新的调号）")
        previous_text: str = Field(
            ..., description="之前的简谱文本（用于获取旧调号信息）"
        )

    class RekeyResponse(BaseModel):
        transposed_text: str = Field(..., description="转调后的文本")

    try:
        body = await _parse_request_body(request)
        parsed = RekeyRequest(**body)
        result = await actions.rekey_text(parsed.text, parsed.previous_text)
        response = RekeyResponse(transposed_text=result)
        return response.model_dump(mode="json")
    except Exception as exc:
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=400, content={"error": str(exc)})
