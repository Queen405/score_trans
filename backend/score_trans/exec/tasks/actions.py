from __future__ import annotations

from collections.abc import AsyncGenerator

from ...models.tasks.entities import TaskProgress, TaskStatus
from ...models.tasks.schemas import SSEProgressEvent
from ...services.tasks.task_service import TaskManager


class TaskActions:
    def __init__(self, manager: TaskManager | None = None) -> None:
        self.manager = manager or TaskManager()

    def create_task(self) -> str:
        return self.manager.create_task()

    def get_progress(self, task_id: str) -> TaskProgress | None:
        return self.manager.get_progress(task_id)

    def get_event(self, task_id: str) -> SSEProgressEvent | None:
        progress = self.get_progress(task_id)
        if progress is None:
            return None
        return _progress_to_event(progress)

    async def update(self, task_id: str, **kwargs) -> None:
        await self.manager.update(task_id, **kwargs)

    async def start(
        self, task_id: str, *, stage: str = "start", message: str = "任务已开始"
    ) -> None:
        await self.update(
            task_id,
            status=TaskStatus.RUNNING,
            stage=stage,
            percent=0,
            message=message,
        )

    async def complete(self, task_id: str, result: dict) -> None:
        await self.manager.complete(task_id, result)

    async def fail(self, task_id: str, error: str) -> None:
        await self.manager.fail(task_id, error)

    def stream(self, task_id: str) -> AsyncGenerator[str, None]:
        return self.manager.stream(task_id)

    def global_events(self) -> AsyncGenerator[str, None]:
        return self.manager.global_events()


def _progress_to_event(progress: TaskProgress) -> SSEProgressEvent:
    return SSEProgressEvent(
        task_id=progress.task_id,
        status=progress.status.value,
        stage=progress.stage,
        percent=progress.percent,
        message=progress.message,
        error=progress.error,
        result=progress.result,
    )
