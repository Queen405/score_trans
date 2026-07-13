from __future__ import annotations

from fastapi import APIRouter, Depends

from ...exec.correct.actions import CorrectActions
from ...models.correct.schemas import (
    CorrectionRequest,
    CorrectionResponse,
    EntitiesResponse,
)
from ..dependencies import get_correct_actions

router = APIRouter(prefix="/correct", tags=["correct"])


@router.get("/entities", response_model=EntitiesResponse)
async def get_entities(
    omr_file_id: str,
    source_map_file_id: str | None = None,
    actions: CorrectActions = Depends(get_correct_actions),
) -> EntitiesResponse:
    return actions.get_entities(omr_file_id, source_map_file_id)


@router.post("/apply", response_model=CorrectionResponse)
async def apply_corrections(
    req: CorrectionRequest,
    actions: CorrectActions = Depends(get_correct_actions),
) -> CorrectionResponse:
    return actions.apply_corrections(req)
