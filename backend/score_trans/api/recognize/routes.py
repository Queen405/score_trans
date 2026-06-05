from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile

from ..dependencies import get_recognize_actions
from ...exec.recognize.actions import RecognizeActions
from ...models.recognize.schemas import RecognizeResponse

router = APIRouter(prefix="/recognize", tags=["recognize"])


@router.post("", response_model=RecognizeResponse)
async def recognize(
    file: UploadFile = File(...),
    target_key: str = Form("C"),
    start_measure_number: int | None = Form(None),
    actions: RecognizeActions = Depends(get_recognize_actions),
):
    return actions.recognize(
        file,
        target_key=target_key,
        start_measure_number=start_measure_number,
    )

