from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, UploadFile

from ...models.recognize.schemas import RecognizeResponse
from ...models.settings.config import ToolConfig
from ...services.files.upload_service import UploadService
from ...services.recognize.audiveris_service import AudiverisService
from ...services.settings.settings_service import SettingsService


class RecognizeScoreAction:
    def __init__(self, audiveris_service: AudiverisService | None = None) -> None:
        self.audiveris_service = audiveris_service or AudiverisService()

    def execute(self, input_file: str | Path, output_dir: str | Path, config: ToolConfig) -> Path:
        return self.audiveris_service.recognize(input_file, output_dir, config)


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
    ) -> RecognizeResponse:
        _ = (target_key, start_measure_number)
        config = self.settings.load()
        file_id = self.uploads.save(file)
        input_path = self.uploads.get_path(file_id)
        if not input_path:
            raise HTTPException(500, "文件保存失败")

        musicxml_path = self.recognizer.execute(input_path, config.work_dir / "audiveris", config)
        musicxml_id = self.uploads.register(musicxml_path)
        return RecognizeResponse(
            musicxml_file_id=musicxml_id,
            musicxml_filename=musicxml_path.name,
        )

