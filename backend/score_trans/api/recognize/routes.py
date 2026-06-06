from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, File, Form, UploadFile

from ..dependencies import get_recognize_actions, get_task_actions
from ..tasks.background import ProgressCallback, run_sync_task
from ...exec.recognize.actions import RecognizeActions
from ...exec.tasks.actions import TaskActions
from ...models.tasks.schemas import TaskSubmitResponse

router = APIRouter(prefix="/recognize", tags=["recognize"])


@router.post("", response_model=TaskSubmitResponse)
async def recognize(
    file: UploadFile = File(...),
    target_key: str = Form("C"),
    start_measure_number: int | None = Form(None),
    actions: RecognizeActions = Depends(get_recognize_actions),
    tasks: TaskActions = Depends(get_task_actions),
):
    input_path = await asyncio.to_thread(actions.save_upload, file)
    task_id = tasks.create_task()

    def action(progress: ProgressCallback):
        return actions.recognize_from_path(
            input_path,
            target_key=target_key,
            start_measure_number=start_measure_number,
            progress_callback=progress,
        )

    asyncio.create_task(run_sync_task(task_id, tasks, action))
    return TaskSubmitResponse(task_id=task_id)
