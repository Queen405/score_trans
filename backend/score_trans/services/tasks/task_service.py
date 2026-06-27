from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from dataclasses import replace
import json
import logging
import time
import uuid
from typing import Any

from ...dao.tasks.task_dao import TaskDao
from ...models.tasks.entities import TaskProgress, TaskStatus

DEFAULT_TASK_TTL_SECONDS = 3600.0

_logger = logging.getLogger(__name__)


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
    """Manages background tasks with SSE progress streaming, SQLite persistence, and global event broadcasting."""

    def __init__(
        self,
        *,
        terminal_ttl_seconds: float = DEFAULT_TASK_TTL_SECONDS,
        time_func=time.time,
        dao: TaskDao | None = None,
    ) -> None:
        self._tasks: dict[str, TaskProgress] = {}
        self._queues: dict[str, asyncio.Queue[TaskProgress]] = {}
        self._terminal_ttl_seconds = terminal_ttl_seconds
        self._time = time_func
        self._dao = dao or TaskDao()
        # Global broadcast channel for all task state changes
        self._subscribers: list[asyncio.Queue[str]] = []
        self._recover_tasks()

    def _recover_tasks(self) -> None:
        """Recover non-expired tasks from SQLite on startup."""
        try:
            now = self._time()
            active = self._dao.load_active(now)
            for progress in active:
                if progress.status not in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                    message = "任务因后端服务重启而中断，请重新识别"
                    progress.status = TaskStatus.FAILED
                    progress.message = message
                    progress.error = message
                    progress.updated_at = now
                    progress.expires_at = now + self._terminal_ttl_seconds
                    self._persist(progress)
                self._tasks[progress.task_id] = progress
                self._queues[progress.task_id] = asyncio.Queue()
            if active:
                _logger.info("Recovered %d task(s) from SQLite", len(active))
        except Exception:
            _logger.warning("Failed to recover tasks from SQLite", exc_info=True)

    def create_task(self) -> str:
        self.cleanup_expired()
        task_id = uuid.uuid4().hex[:12]
        now = self._time()
        progress = TaskProgress(task_id=task_id, created_at=now, updated_at=now)
        self._tasks[task_id] = progress
        self._queues[task_id] = asyncio.Queue()
        self._persist(progress)
        return task_id

    def get_progress(self, task_id: str) -> TaskProgress | None:
        # Try memory first, fall back to SQLite (e.g. after page refresh)
        progress = self._tasks.get(task_id)
        if progress is not None:
            return progress
        progress = self._dao.load(task_id)
        if progress is not None:
            self._tasks[task_id] = progress
            self._queues[task_id] = asyncio.Queue()
        return progress

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
        self._persist(progress)
        # Per-task SSE queue
        queue = self._queues.get(task_id)
        if queue is not None:
            await queue.put(replace(progress))
        # Global broadcast
        await self._broadcast(progress)

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

        if progress.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            return

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

    async def global_events(self) -> AsyncGenerator[str, None]:
        """Yield SSE events for ALL task state changes. Used by the frontend for real-time updates."""
        sub: asyncio.Queue[str] = asyncio.Queue()
        self._subscribers.append(sub)
        try:
            # Send initial snapshot of all active tasks
            for progress in list(self._tasks.values()):
                yield _sse_event(progress)
            # Then stream live updates
            while True:
                try:
                    event = await asyncio.wait_for(sub.get(), timeout=30)
                    yield event
                except TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            self._subscribers.remove(sub)

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
            self._dao.delete(task_id)
        if expired:
            self._dao.delete_expired(now)
        return len(expired)

    def _persist(self, progress: TaskProgress) -> None:
        """Persist task state to SQLite (best-effort)."""
        try:
            self._dao.save(progress)
        except Exception:
            _logger.warning("Failed to persist task %s", progress.task_id, exc_info=True)

    async def _broadcast(self, progress: TaskProgress) -> None:
        """Push a task event to all global SSE subscribers."""
        event = _sse_event(progress)
        dead: list[asyncio.Queue[str]] = []
        for sub in self._subscribers:
            try:
                sub.put_nowait(event)
            except asyncio.QueueFull:
                dead.append(sub)
        for sub in dead:
            self._subscribers.remove(sub)
