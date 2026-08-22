from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends

from ..dependencies import get_syntax_actions
from ...exec.syntax.actions import SyntaxActions
from ...models.syntax.schemas import SyntaxValidateRequest, SyntaxValidateResponse

router = APIRouter(prefix="/syntax", tags=["syntax"])


@router.post("/validate", response_model=SyntaxValidateResponse)
async def validate_syntax(
    req: SyntaxValidateRequest,
    actions: SyntaxActions = Depends(get_syntax_actions),
) -> SyntaxValidateResponse:
    return await asyncio.to_thread(actions.validate, req)
