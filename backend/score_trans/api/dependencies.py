from __future__ import annotations

from fastapi import Request

from ..exec.ai.actions import AiActions
from ..exec.convert.actions import ConvertActions
from ..exec.export.actions import ExportActions
from ..exec.files.actions import FileActions
from ..exec.history.actions import HistoryActions
from ..exec.pipeline.actions import PipelineActions
from ..exec.recognize.actions import RecognizeActions
from ..exec.render.actions import RenderActions
from ..exec.settings.actions import SettingsActions
from ..exec.tasks.actions import TaskActions


def get_ai_actions() -> AiActions:
    return AiActions()


def get_convert_actions() -> ConvertActions:
    return ConvertActions()


def get_export_actions() -> ExportActions:
    return ExportActions()


def get_file_actions() -> FileActions:
    return FileActions()


def get_history_actions() -> HistoryActions:
    return HistoryActions()


def get_pipeline_actions() -> PipelineActions:
    return PipelineActions()


def get_recognize_actions() -> RecognizeActions:
    return RecognizeActions()


def get_render_actions() -> RenderActions:
    return RenderActions()


def get_settings_actions() -> SettingsActions:
    return SettingsActions()


def get_task_actions(request: Request) -> TaskActions:
    actions = getattr(request.app.state, "task_actions", None)
    if actions is None:
        raise RuntimeError("TaskActions is not initialized")
    return actions
