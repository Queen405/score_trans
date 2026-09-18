from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile

from ...exec.pipeline.actions import PipelineActions
from ...exec.tasks.actions import TaskActions
from ...models.common.types import (
    AccidentalMode,
    InstrumentProfile,
    MeasureNumberMode,
    PolyphonyMode,
    TargetKeyOrAuto,
)
from ...models.pipeline.schemas import PipelineByFileIdRequest
from ...models.render.layout import (
    DEFAULT_BEAT_GAP_PERCENT,
    DEFAULT_CONTENT_SCALE_PERCENT,
    DEFAULT_SHORT_NOTE_GAP_PERCENT,
    DEFAULT_SYSTEM_GAP_PERCENT,
    MAX_BEAT_GAP_PERCENT,
    MAX_CONTENT_SCALE_PERCENT,
    MAX_SHORT_NOTE_GAP_PERCENT,
    MAX_SYSTEM_GAP_PERCENT,
    MIN_BEAT_GAP_PERCENT,
    MIN_CONTENT_SCALE_PERCENT,
    MIN_SHORT_NOTE_GAP_PERCENT,
    MIN_SYSTEM_GAP_PERCENT,
)
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
        polyphony_mode=req.polyphony_mode,
        show_measure_numbers=_request_show_measure_numbers(req),
        measure_number_mode=_request_measure_number_mode(req),
        content_scale_percent=req.jianpu_content_scale_percent,
        system_gap_percent=req.jianpu_system_gap_percent,
        short_note_gap_percent=req.jianpu_short_note_gap_percent,
        beat_gap_percent=req.jianpu_beat_gap_percent,
        break_beams_at_beat=req.jianpu_break_beams_at_beat,
        title=req.title,
    )


@router.post("", response_model=TaskSubmitResponse)
async def run_pipeline(
    request: Request,
    file: UploadFile = File(...),
    target_key: TargetKeyOrAuto = Form("C"),
    accidental_mode: AccidentalMode = Form("auto"),
    instrument_profile: InstrumentProfile = Form("general"),
    polyphony_mode: PolyphonyMode = Form("auto"),
    show_measure_numbers: bool = Form(True),
    measure_number_mode: MeasureNumberMode = Form("all"),
    jianpu_content_scale_percent: int = Form(
        DEFAULT_CONTENT_SCALE_PERCENT,
        ge=MIN_CONTENT_SCALE_PERCENT,
        le=MAX_CONTENT_SCALE_PERCENT,
    ),
    jianpu_system_gap_percent: int = Form(
        DEFAULT_SYSTEM_GAP_PERCENT,
        ge=MIN_SYSTEM_GAP_PERCENT,
        le=MAX_SYSTEM_GAP_PERCENT,
    ),
    jianpu_short_note_gap_percent: int = Form(
        DEFAULT_SHORT_NOTE_GAP_PERCENT,
        ge=MIN_SHORT_NOTE_GAP_PERCENT,
        le=MAX_SHORT_NOTE_GAP_PERCENT,
    ),
    jianpu_beat_gap_percent: int = Form(
        DEFAULT_BEAT_GAP_PERCENT,
        ge=MIN_BEAT_GAP_PERCENT,
        le=MAX_BEAT_GAP_PERCENT,
    ),
    jianpu_break_beams_at_beat: bool = Form(False),
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
        polyphony_mode=polyphony_mode,
        show_measure_numbers=measure_number_mode != "none" and show_measure_numbers,
        measure_number_mode="none" if not show_measure_numbers else measure_number_mode,
        content_scale_percent=jianpu_content_scale_percent,
        system_gap_percent=jianpu_system_gap_percent,
        short_note_gap_percent=jianpu_short_note_gap_percent,
        beat_gap_percent=jianpu_beat_gap_percent,
        break_beams_at_beat=jianpu_break_beams_at_beat,
        title=title,
    )


def _request_measure_number_mode(req: PipelineByFileIdRequest) -> MeasureNumberMode:
    if req.show_measure_numbers is False:
        return "none"
    return req.measure_number_mode


def _request_show_measure_numbers(req: PipelineByFileIdRequest) -> bool:
    return _request_measure_number_mode(req) != "none"
