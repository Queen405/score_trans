from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from ..dependencies import get_task_actions
from ...exec.tasks.actions import TaskActions
from ...models.tasks.schemas import SSEProgressEvent

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/events")
async def global_task_events(
    actions: TaskActions = Depends(get_task_actions),
):
    """Global SSE stream for ALL task state changes. Frontend connects once on app load."""
    return StreamingResponse(
        actions.global_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{task_id}", response_model=SSEProgressEvent)
async def get_task(
    task_id: str,
    actions: TaskActions = Depends(get_task_actions),
):
    event = actions.get_event(task_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return event


@router.get("/{task_id}/stream")
async def stream_task(
    task_id: str,
    actions: TaskActions = Depends(get_task_actions),
):
    return StreamingResponse(
        actions.stream(task_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
