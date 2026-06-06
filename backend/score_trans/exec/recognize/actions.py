from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from fastapi import UploadFile

from ...models.recognize.schemas import RecognizeResponse
from ...models.settings.config import ToolConfig
from ...services.files.upload_service import UploadService
from ...services.recognize.audiveris_service import AudiverisService
from ...services.settings.settings_service import SettingsService

ProgressCallback = Callable[[str, int, str], None]


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
        _report(progress_callback, "omr", 15, "启动 Audiveris")
        result = self.audiveris_service.recognize(input_file, output_dir, config)
        _report(progress_callback, "omr", 85, "Audiveris 输出 MusicXML")
        return result


class RecognizeActions:
    def __init__(
        self,
        uploads: UploadService | None = None,
        settings: SettingsService | None = None,
        recognizer: RecognizeScoreAction | None = None,
    ) -> None:
        self.uploads = uploads or UploadService()
        self.settings = settings or SettingsService()
        self.recognizer = recognizer or RecognizeScoreAction()

    def recognize(
        self,
        file: UploadFile,
        *,
        target_key: str = "C",
        start_measure_number: int | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> RecognizeResponse:
        input_path = self.save_upload(file)
        return self.recognize_from_path(
            input_path,
            target_key=target_key,
            start_measure_number=start_measure_number,
            progress_callback=progress_callback,
        )

    def save_upload(self, file: UploadFile) -> Path:
        file_id = self.uploads.save(file)
        input_path = self.uploads.get_path(file_id)
        if not input_path:
            raise FileNotFoundError("文件保存失败")
        return input_path

    def recognize_from_path(
        self,
        input_path: str | Path,
        *,
        target_key: str = "C",
        start_measure_number: int | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> RecognizeResponse:
        _ = (target_key, start_measure_number)
        config = self.settings.load()

        _report(progress_callback, "recognize", 5, "准备 OMR 识别")
        musicxml_path = self.recognizer.execute(
            input_path,
            config.work_dir / "audiveris",
            config,
            progress_callback=progress_callback,
        )
        _report(progress_callback, "recognize", 92, "注册 MusicXML 文件")
        musicxml_id = self.uploads.register(musicxml_path)
        return RecognizeResponse(
            musicxml_file_id=musicxml_id,
            musicxml_filename=musicxml_path.name,
        )


def _report(progress_callback: ProgressCallback | None, stage: str, percent: int, message: str) -> None:
    if progress_callback is not None:
        progress_callback(stage, percent, message)
