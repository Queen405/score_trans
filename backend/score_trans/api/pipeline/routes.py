from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile

from ..dependencies import get_pipeline_actions, get_task_actions
from ...exec.pipeline.actions import PipelineActions
from ...exec.tasks.actions import TaskActions
from ...models.pipeline.schemas import PipelineByFileIdRequest
from ...models.tasks.schemas import TaskSubmitResponse
from ...models.common.types import AccidentalMode

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.post("/by-file-id", response_model=TaskSubmitResponse)
async def run_pipeline_by_file_id(
    request: Request,
    req: PipelineByFileIdRequest,
    actions: PipelineActions = Depends(get_pipeline_actions),
    tasks: TaskActions = Depends(get_task_actions),
):
    return await actions.submit_pipeline_task_by_file_id(
        request.app,
        req.file_id,
        tasks=tasks,
        target_key=req.target_key,
        accidental_mode=req.accidental_mode,
        start_measure_number=req.start_measure_number,
        title=req.title,
    )


@router.post("", response_model=TaskSubmitResponse)
async def run_pipeline(
    request: Request,
    file: UploadFile = File(...),
    target_key: str = Form("C"),
    accidental_mode: AccidentalMode = Form("auto"),
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
        accidental_mode=accidental_mode,
        start_measure_number=start_measure_number,
        title=title,
    )
