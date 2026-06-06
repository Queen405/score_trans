from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from dataclasses import replace
import json
import time
import uuid
from typing import Any

from ...models.tasks.entities import TaskProgress, TaskStatus

DEFAULT_TASK_TTL_SECONDS = 3600.0


def _sse_event(progress: TaskProgress) -> str:
    data = {
        "task_id": progress.task_id,
        "status": progress.status.value,
        "stage": progress.stage,
        "percent": progress.percent,
        "message": progress.message,
    }
    if progress.error is not None:
        data["error"] = progress.error
    if progress.result is not None:
        data["result"] = progress.result
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


class TaskManager:
    """Manages background tasks with SSE progress streaming."""

    def __init__(
        self,
        *,
        terminal_ttl_seconds: float = DEFAULT_TASK_TTL_SECONDS,
        time_func=time.monotonic,
    ) -> None:
        self._tasks: dict[str, TaskProgress] = {}
        self._queues: dict[str, asyncio.Queue[TaskProgress]] = {}
        self._terminal_ttl_seconds = terminal_ttl_seconds
        self._time = time_func

    def create_task(self) -> str:
        self.cleanup_expired()
        task_id = uuid.uuid4().hex[:12]
        now = self._time()
        self._tasks[task_id] = TaskProgress(task_id=task_id, created_at=now, updated_at=now)
        self._queues[task_id] = asyncio.Queue()
        return task_id

    def get_progress(self, task_id: str) -> TaskProgress | None:
        self.cleanup_expired()
        return self._tasks.get(task_id)

    async def update(self, task_id: str, **kwargs: Any) -> None:
        self.cleanup_expired()
        progress = self._tasks.get(task_id)
        if progress is None:
            return
        for key, value in kwargs.items():
            if hasattr(progress, key):
                setattr(progress, key, value)
        now = self._time()
        progress.updated_at = now
        if progress.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            progress.expires_at = now + self._terminal_ttl_seconds
        queue = self._queues.get(task_id)
        if queue is not None:
            await queue.put(replace(progress))

    async def complete(self, task_id: str, result: dict[str, Any]) -> None:
        await self.update(
            task_id,
            status=TaskStatus.COMPLETED,
            percent=100,
            message="任务完成",
            result=result,
        )

    async def fail(self, task_id: str, error: str) -> None:
        await self.update(task_id, status=TaskStatus.FAILED, error=error, message=error)

    async def stream(self, task_id: str) -> AsyncGenerator[str, None]:
        """Yield Server-Sent Events for a task until it reaches a terminal state."""
        self.cleanup_expired()
        progress = self._tasks.get(task_id)
        if progress is None:
            yield _sse_event(TaskProgress(task_id=task_id, status=TaskStatus.FAILED, error="Task not found"))
            return

        progress = replace(progress)
        yield _sse_event(progress)

        queue = self._queues.get(task_id)
        if queue is None:
            return

        while progress.status not in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            try:
                progress = await asyncio.wait_for(queue.get(), timeout=15)
            except TimeoutError:
                yield ": keep-alive\n\n"
                continue
            yield _sse_event(progress)

    def cleanup_expired(self) -> int:
        now = self._time()
        expired = [
            task_id
            for task_id, progress in self._tasks.items()
            if progress.expires_at is not None and progress.expires_at <= now
        ]
        for task_id in expired:
            self._tasks.pop(task_id, None)
            self._queues.pop(task_id, None)
        return len(expired)
