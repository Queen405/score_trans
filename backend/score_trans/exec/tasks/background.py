from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable, Coroutine
from typing import Any

from ...models.tasks.entities import ProgressCallback, TaskStatus
from .actions import TaskActions

SyncTask = Callable[[ProgressCallback], Any]


def schedule_background_task(app: Any, task_id: str, coro: Coroutine[Any, Any, None]) -> asyncio.Task[None]:
    background_tasks = getattr(app.state, "background_tasks", None)
    if background_tasks is None:
        raise RuntimeError("Background task registry is not initialized")

    task = asyncio.create_task(coro, name=f"score-trans:{task_id}")
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)
    return task


async def run_sync_task(task_id: str, tasks: TaskActions, action: SyncTask) -> None:
    loop = asyncio.get_running_loop()
    cancelled = threading.Event()
    await tasks.start(task_id)

    def progress(stage: str, percent: int, message: str) -> None:
        if cancelled.is_set():
            return
        future = asyncio.run_coroutine_threadsafe(
            tasks.update(
                task_id,
                status=TaskStatus.RUNNING,
                stage=stage,
                percent=max(0, min(99, int(percent))),
                message=message,
            ),
            loop,
        )
        try:
            future.result(timeout=5)
        except Exception:
            return

    try:
        result = await asyncio.to_thread(action, progress)
    except asyncio.CancelledError:
        cancelled.set()
        await tasks.fail(task_id, "任务被服务关闭中断")
        raise
    except Exception as exc:
        await tasks.fail(task_id, _error_message(exc))
        return

    await tasks.complete(task_id, _result_to_dict(result))


def _result_to_dict(result: Any) -> dict[str, Any]:
    if hasattr(result, "model_dump"):
        return result.model_dump(exclude_none=True)
    if hasattr(result, "dict"):
        return result.dict(exclude_none=True)
    if isinstance(result, dict):
        return result
    return {"value": result}


def _error_message(exc: Exception) -> str:
    detail = getattr(exc, "detail", None)
    if isinstance(detail, str):
        return detail
    if detail is not None:
        return str(detail)
    return str(exc)
