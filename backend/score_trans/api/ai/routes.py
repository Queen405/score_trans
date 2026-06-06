from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends

from ..dependencies import get_ai_actions, get_task_actions
from ..tasks.background import ProgressCallback, run_sync_task
from ...exec.ai.actions import AiActions
from ...exec.tasks.actions import TaskActions
from ...models.ai.schemas import AiTranscribeRequest
from ...models.tasks.schemas import TaskSubmitResponse

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/transcribe", response_model=TaskSubmitResponse)
async def transcribe_score(
    req: AiTranscribeRequest,
    actions: AiActions = Depends(get_ai_actions),
    tasks: TaskActions = Depends(get_task_actions),
):
    task_id = tasks.create_task()

    def action(progress: ProgressCallback):
        return actions.transcribe_score(req, progress_callback=progress)

    asyncio.create_task(run_sync_task(task_id, tasks, action))
    return TaskSubmitResponse(task_id=task_id)
