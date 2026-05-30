from __future__ import annotations

from ..services.settings import ToolConfig
from ..use_cases import (
    ConvertJianpuToMusicXmlUseCase,
    ConvertMusicXmlToJianpuUseCase,
    ExportScoreUseCase,
    FullPipelineUseCase,
    RecognizeScoreUseCase,
    RenderJianpuTextUseCase,
    RenderMusicXmlJianpuUseCase,
)
from .tasks import TaskManager
from .uploads import UploadManager


def get_config() -> ToolConfig:
    return ToolConfig.from_env()


_upload_manager: UploadManager | None = None
_task_manager: TaskManager | None = None


def get_upload_manager() -> UploadManager:
    global _upload_manager
    if _upload_manager is None:
        _upload_manager = UploadManager()
    return _upload_manager


def get_task_manager() -> TaskManager:
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager()
    return _task_manager


def get_convert_to_jianpu() -> ConvertMusicXmlToJianpuUseCase:
    return ConvertMusicXmlToJianpuUseCase()


def get_convert_to_musicxml() -> ConvertJianpuToMusicXmlUseCase:
    return ConvertJianpuToMusicXmlUseCase()


def get_recognize() -> RecognizeScoreUseCase:
    return RecognizeScoreUseCase()


def get_render_jianpu() -> RenderMusicXmlJianpuUseCase:
    return RenderMusicXmlJianpuUseCase()


def get_render_text() -> RenderJianpuTextUseCase:
    return RenderJianpuTextUseCase()


def get_pipeline() -> FullPipelineUseCase:
    return FullPipelineUseCase()


def get_export() -> ExportScoreUseCase:
    return ExportScoreUseCase()
