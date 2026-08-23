from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile

from ...exec.pipeline.actions import PipelineActions
from ...exec.tasks.actions import TaskActions
from ...models.common.types import (
    AccidentalMode,
    InstrumentProfile,
    MeasureNumberMode,
    TargetKeyOrAuto,
)
from ...models.pipeline.schemas import PipelineByFileIdRequest
from ...models.tasks.schemas import TaskSubmitResponse
from ..dependencies import get_pipeline_actions, get_task_actions

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
        instrument_profile=req.instrument_profile,
        show_measure_numbers=_request_show_measure_numbers(req),
        measure_number_mode=_request_measure_number_mode(req),
        content_scale_percent=req.jianpu_content_scale_percent,
        system_gap_percent=req.jianpu_system_gap_percent,
        short_note_gap_percent=req.jianpu_short_note_gap_percent,
        title=req.title,
    )


@router.post("", response_model=TaskSubmitResponse)
async def run_pipeline(
    request: Request,
    file: UploadFile = File(...),
    target_key: TargetKeyOrAuto = Form("C"),
    accidental_mode: AccidentalMode = Form("auto"),
    instrument_profile: InstrumentProfile = Form("general"),
    show_measure_numbers: bool = Form(True),
    measure_number_mode: MeasureNumberMode = Form("all"),
    jianpu_content_scale_percent: int = Form(67, ge=65, le=100),
    jianpu_system_gap_percent: int = Form(92, ge=60, le=140),
    jianpu_short_note_gap_percent: int = Form(90, ge=60, le=140),
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
        instrument_profile=instrument_profile,
        show_measure_numbers=measure_number_mode != "none" and show_measure_numbers,
        measure_number_mode="none" if not show_measure_numbers else measure_number_mode,
        content_scale_percent=jianpu_content_scale_percent,
        system_gap_percent=jianpu_system_gap_percent,
        short_note_gap_percent=jianpu_short_note_gap_percent,
        title=title,
    )


def _request_measure_number_mode(req: PipelineByFileIdRequest) -> MeasureNumberMode:
    if req.show_measure_numbers is False:
        return "none"
    return req.measure_number_mode


def _request_show_measure_numbers(req: PipelineByFileIdRequest) -> bool:
    return _request_measure_number_mode(req) != "none"
