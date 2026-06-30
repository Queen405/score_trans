from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any

from fastapi import UploadFile

from ...models.recognize.schemas import RecognizeResponse
from ...models.settings.config import ToolConfig
from ...models.tasks.entities import ProgressCallback, report_progress
from ...models.tasks.schemas import TaskSubmitResponse
from ...services.files.upload_service import UploadService
from ...services.overlay.overlay_service import OverlayService
from ...services.recognize.audiveris_service import AudiverisService
from ...services.settings.settings_service import SettingsService
from ..tasks.actions import TaskActions
from ..tasks.background import OMR_SEMAPHORE, run_sync_task, schedule_background_task


class RecognizeScoreAction:
    def __init__(self, audiveris_service: AudiverisService | None = None) -> None:
        self.audiveris_service = audiveris_service or AudiverisService()

    def execute(
        self,
        input_file: str | Path,
        output_dir: str | Path,
        config: ToolConfig,
        *,
        progress_callback: ProgressCallback | None = None,
    ) -> Path:
        report_progress(progress_callback, "omr", 15, "启动 Audiveris")
        result = self.audiveris_service.recognize(input_file, output_dir, config)
        report_progress(progress_callback, "omr", 85, "Audiveris 输出 MusicXML")
        return result


class RecognizeActions:
    def __init__(
        self,
        uploads: UploadService | None = None,
        settings: SettingsService | None = None,
        recognizer: RecognizeScoreAction | None = None,
        overlay_service: OverlayService | None = None,
    ) -> None:
        self.uploads = uploads or UploadService()
        self.settings = settings or SettingsService()
        self.recognizer = recognizer or RecognizeScoreAction()
        self.overlay_service = overlay_service or OverlayService()

    def recognize(
        self,
        file: UploadFile,
        *,
        progress_callback: ProgressCallback | None = None,
    ) -> RecognizeResponse:
        input_path = self.save_upload(file)
        return self.recognize_from_path(
            input_path,
            progress_callback=progress_callback,
        )

    def save_upload(self, file: UploadFile) -> Path:
        file_id = self.uploads.save(file)
        input_path = self.uploads.get_path(file_id)
        if not input_path:
            raise FileNotFoundError("文件保存失败")
        return input_path

    async def submit_recognize_task(
        self,
        app: Any,
        file: UploadFile,
        *,
        tasks: TaskActions,
    ) -> TaskSubmitResponse:
        input_path = await asyncio.to_thread(self.save_upload, file)
        task_id = tasks.create_task()

        def action(progress: ProgressCallback):
            return self.recognize_from_path(
                input_path,
                progress_callback=progress,
            )

        schedule_background_task(
            app, task_id, run_sync_task(task_id, tasks, action, semaphore=OMR_SEMAPHORE)
        )
        return TaskSubmitResponse(task_id=task_id)

    def recognize_from_path(
        self,
        input_path: str | Path,
        *,
        progress_callback: ProgressCallback | None = None,
    ) -> RecognizeResponse:
        config = self.settings.load()
        omr_dir = config.work_dir / "audiveris" / uuid.uuid4().hex

        report_progress(progress_callback, "recognize", 5, "准备 OMR 识别")
        musicxml_path = self.recognizer.execute(
            input_path,
            omr_dir,
            config,
            progress_callback=progress_callback,
        )
        report_progress(progress_callback, "recognize", 92, "注册 MusicXML 文件")
        musicxml_id = self.uploads.register(musicxml_path)
        overlay_svg_file_id = _generate_overlay_file_id(
            self.overlay_service, self.uploads, omr_dir
        )
        return RecognizeResponse(
            musicxml_file_id=musicxml_id,
            musicxml_filename=musicxml_path.name,
            overlay_svg_file_id=overlay_svg_file_id,
        )


def _generate_overlay_file_id(
    overlay_service: OverlayService,
    uploads: UploadService,
    omr_dir: Path,
) -> str | None:
    try:
        paths = overlay_service.generate_overlay_svgs(omr_dir)
    except Exception:
        return None
    if not paths:
        return None
    return uploads.register(paths[0])
