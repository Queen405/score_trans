from __future__ import annotations

from fastapi import APIRouter, Depends, File, Request, UploadFile

from ..dependencies import get_recognize_actions, get_task_actions
from ...exec.recognize.actions import RecognizeActions
from ...exec.tasks.actions import TaskActions
from ...models.tasks.schemas import TaskSubmitResponse

router = APIRouter(prefix="/recognize", tags=["recognize"])


@router.post("", response_model=TaskSubmitResponse)
async def recognize(
    request: Request,
    file: UploadFile = File(...),
    actions: RecognizeActions = Depends(get_recognize_actions),
    tasks: TaskActions = Depends(get_task_actions),
):
    return await actions.submit_recognize_task(request.app, file, tasks=tasks)
