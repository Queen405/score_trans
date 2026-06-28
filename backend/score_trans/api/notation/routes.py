from __future__ import annotations

from fastapi import APIRouter, Depends

from ..dependencies import get_notation_actions
from ...exec.notation.actions import NotationActions
from ...models.notation.schemas import InstrumentProfileCatalog


router = APIRouter(prefix="/notation", tags=["notation"])


@router.get(
    "/instrument-profiles",
    response_model=list[InstrumentProfileCatalog],
)
async def list_instrument_profiles(
    actions: NotationActions = Depends(get_notation_actions),
):
    return actions.list_instrument_profiles()
