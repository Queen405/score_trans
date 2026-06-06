from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, File, Request, UploadFile

from ..dependencies import get_recognize_actions, get_task_actions
from ..tasks.background import run_sync_task, schedule_background_task
from ...exec.recognize.actions import RecognizeActions
from ...exec.tasks.actions import TaskActions
from ...models.tasks.entities import ProgressCallback
from ...models.tasks.schemas import TaskSubmitResponse

router = APIRouter(prefix="/recognize", tags=["recognize"])


@router.post("", response_model=TaskSubmitResponse)
async def recognize(
    request: Request,
    file: UploadFile = File(...),
    actions: RecognizeActions = Depends(get_recognize_actions),
    tasks: TaskActions = Depends(get_task_actions),
):
    input_path = await asyncio.to_thread(actions.save_upload, file)
    task_id = tasks.create_task()

    def action(progress: ProgressCallback):
        return actions.recognize_from_path(
            input_path,
            progress_callback=progress,
        )

    schedule_background_task(request.app, task_id, run_sync_task(task_id, tasks, action))
    return TaskSubmitResponse(task_id=task_id)
