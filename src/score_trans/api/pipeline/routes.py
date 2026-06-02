from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile

from ..dependencies import get_pipeline_actions
from ...exec.pipeline.actions import PipelineActions
from ...models.pipeline.schemas import PipelineResponse

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.post("", response_model=PipelineResponse)
async def run_pipeline(
    file: UploadFile = File(...),
    target_key: str = Form("C"),
    start_measure_number: int | None = Form(None),
    title: str | None = Form(None),
    actions: PipelineActions = Depends(get_pipeline_actions),
):
    return actions.run_pipeline(
        file,
        target_key=target_key,
        start_measure_number=start_measure_number,
        title=title,
    )

