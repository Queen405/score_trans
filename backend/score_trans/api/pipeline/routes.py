from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile

from ..dependencies import get_pipeline_actions, get_task_actions
from ...exec.pipeline.actions import PipelineActions
from ...exec.tasks.actions import TaskActions
from ...models.tasks.schemas import TaskSubmitResponse

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.post("", response_model=TaskSubmitResponse)
async def run_pipeline(
    request: Request,
    file: UploadFile = File(...),
    target_key: str = Form("C"),
    start_measure_number: int | None = Form(None),
    title: str | None = Form(None),
    actions: PipelineActions = Depends(get_pipeline_actions),
    tasks: TaskActions = Depends(get_task_actions),
):
    return await actions.submit_pipeline_task(
        request.app,
        file,
        tasks=tasks,
        target_key=target_key,
        start_measure_number=start_measure_number,
        title=title,
    )
