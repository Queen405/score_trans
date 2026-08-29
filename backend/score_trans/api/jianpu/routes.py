from __future__ import annotations

from fastapi import APIRouter, Depends

from ..dependencies import get_jianpu_actions
from ...exec.jianpu.actions import JianpuActions
from ...models.jianpu.schemas import JianpuRekeyRequest, JianpuRekeyResponse

router = APIRouter(prefix="/jianpu", tags=["jianpu"])


@router.post("/rekey", response_model=JianpuRekeyResponse)
async def rekey_text_route(
    req: JianpuRekeyRequest,
    actions: JianpuActions = Depends(get_jianpu_actions),
) -> JianpuRekeyResponse:
    """根据之前的简谱文本，将当前文本中的音符按新调号转调以保持音高不变。

    Example:
        POST /jianpu/rekey
        {"text": "1=G\\n4 5 6", "previous_text": "1=C\\n4 5 6"}
        → {"transposed_text": "1=G\\nb7, 1 2"}
    """
    transposed = await actions.rekey_text(req.text, req.previous_text)
    return JianpuRekeyResponse(transposed_text=transposed)
