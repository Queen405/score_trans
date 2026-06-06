from __future__ import annotations

import asyncio
import json

from pydantic import BaseModel

from score_trans.api.app import create_app
from score_trans.api.tasks.background import run_sync_task, schedule_background_task
from score_trans.exec.tasks.actions import TaskActions
from score_trans.models.tasks.entities import TaskStatus
from score_trans.services.tasks.task_service import TaskManager


class FakeResult(BaseModel):
    value: str


def _event_data(chunk: str) -> dict:
    assert chunk.startswith("data: ")
    return json.loads(chunk.removeprefix("data: ").strip())


def test_task_manager_streams_progress_and_result() -> None:
    async def scenario() -> list[dict]:
        manager = TaskManager()
        task_id = manager.create_task()

        async def finish_task() -> None:
            await manager.update(
                task_id,
                status=TaskStatus.RUNNING,
                stage="work",
                percent=42,
                message="working",
            )
            await manager.complete(task_id, {"ok": True})

        asyncio.create_task(finish_task())
        events: list[dict] = []
        async for chunk in manager.stream(task_id):
            if chunk.startswith(":"):
                continue
            events.append(_event_data(chunk))
            if events[-1]["status"] == "completed":
                break
        return events

    events = asyncio.run(scenario())

    assert events[0]["status"] == "pending"
    assert any(event["stage"] == "work" and event["percent"] == 42 for event in events)
    assert events[-1]["status"] == "completed"
    assert events[-1]["result"] == {"ok": True}


def test_run_sync_task_updates_task_to_completed() -> None:
    async def scenario() -> dict:
        actions = TaskActions()
        task_id = actions.create_task()

        def action(progress):
            progress("work", 33, "working")
            return FakeResult(value="done")

        await run_sync_task(task_id, actions, action)
        event = actions.get_event(task_id)
        assert event is not None
        return event.model_dump()

    event = asyncio.run(scenario())

    assert event["status"] == "completed"
    assert event["percent"] == 100
    assert event["result"] == {"value": "done"}


def test_task_manager_cleans_expired_terminal_tasks() -> None:
    clock = {"now": 100.0}
    manager = TaskManager(terminal_ttl_seconds=10, time_func=lambda: clock["now"])
    task_id = manager.create_task()

    asyncio.run(manager.complete(task_id, {"ok": True}))
    assert manager.get_progress(task_id) is not None

    clock["now"] = 111.0

    assert manager.cleanup_expired() == 1
    assert manager.get_progress(task_id) is None


def test_schedule_background_task_tracks_until_done() -> None:
    async def scenario() -> tuple[int, int]:
        app = create_app()

        async def work() -> None:
            await asyncio.sleep(0)

        task = schedule_background_task(app, "abc123", work())
        before = len(app.state.background_tasks)
        await task
        await asyncio.sleep(0)
        after = len(app.state.background_tasks)
        return before, after

    before, after = asyncio.run(scenario())

    assert before == 1
    assert after == 0
