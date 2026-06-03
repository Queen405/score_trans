from __future__ import annotations

from fastapi import APIRouter, Depends

from ..dependencies import get_ai_actions
from ...exec.ai.actions import AiActions
from ...models.ai.schemas import AiTranscribeRequest, AiTranscribeResponse

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/transcribe", response_model=AiTranscribeResponse)
async def transcribe_score(
    req: AiTranscribeRequest,
    actions: AiActions = Depends(get_ai_actions),
):
    return actions.transcribe_score(req)
