from __future__ import annotations

from fastapi import Request

from ..exec import composition
from ..exec.ai.actions import AiActions
from ..exec.convert.actions import ConvertActions
from ..exec.correct.actions import CorrectActions
from ..exec.export.actions import ExportActions
from ..exec.files.actions import FileActions
from ..exec.history.actions import HistoryActions
from ..exec.jianpu.actions import JianpuActions
from ..exec.notation.actions import NotationActions
from ..exec.pipeline.actions import PipelineActions
from ..exec.recognize.actions import RecognizeActions
from ..exec.render.actions import RenderActions
from ..exec.settings.actions import SettingsActions
from ..exec.syntax.actions import SyntaxActions
from ..exec.tasks.actions import TaskActions


def get_ai_actions() -> AiActions:
    return AiActions(
        uploads=composition.shared_uploads(),
        settings=composition.shared_settings_service(),
        file_service=composition.shared_file_service(),
    )


def get_convert_actions() -> ConvertActions:
    return ConvertActions(
        uploads=composition.shared_uploads(),
        file_service=composition.shared_file_service(),
        settings=composition.shared_settings_service(),
    )


def get_correct_actions() -> CorrectActions:
    return CorrectActions(
        uploads=composition.shared_uploads(),
    )


def get_export_actions() -> ExportActions:
    return ExportActions(uploads=composition.shared_uploads())


def get_file_actions() -> FileActions:
    return FileActions(uploads=composition.shared_uploads())


def get_history_actions() -> HistoryActions:
    return HistoryActions(service=composition.shared_history_service())


def get_notation_actions() -> NotationActions:
    return NotationActions()


def get_pipeline_actions() -> PipelineActions:
    return PipelineActions(
        uploads=composition.shared_uploads(),
        settings=composition.shared_settings_service(),
        file_service=composition.shared_file_service(),
    )


def get_recognize_actions() -> RecognizeActions:
    return RecognizeActions(
        uploads=composition.shared_uploads(),
        settings=composition.shared_settings_service(),
    )


def get_render_actions() -> RenderActions:
    return RenderActions(uploads=composition.shared_uploads())


def get_settings_actions() -> SettingsActions:
    return SettingsActions(service=composition.shared_settings_service())


def get_syntax_actions() -> SyntaxActions:
    return SyntaxActions(settings=composition.shared_settings_service())


def get_jianpu_actions() -> JianpuActions:
    """返回 JianpuActions 实例（单例）。"""
    return JianpuActions()


def get_task_actions(request: Request) -> TaskActions:
    actions = getattr(request.app.state, "task_actions", None)
    if actions is None:
        raise RuntimeError("TaskActions is not initialized")
    return actions
