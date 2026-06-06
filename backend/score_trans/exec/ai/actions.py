from __future__ import annotations

import uuid
from pathlib import Path

from ...models.ai.schemas import AiTranscribeRequest, AiTranscribeResponse, AiTranscribedPage
from ...models.settings.config import ToolConfig
from ...models.tasks.entities import ProgressCallback, report_progress
from ...services.ai.service import AiTranscriptionService
from ...services.files.file_service import FileService
from ...services.files.upload_service import UploadService
from ...services.settings.settings_service import SettingsService


class AiActions:
    def __init__(
        self,
        uploads: UploadService | None = None,
        settings: SettingsService | None = None,
        transcriber: AiTranscriptionService | None = None,
        file_service: FileService | None = None,
    ) -> None:
        self.uploads = uploads or UploadService()
        self.settings = settings or SettingsService()
        self.transcriber = transcriber or AiTranscriptionService()
        self.file_service = file_service or FileService()

    def transcribe_score(
        self,
        req: AiTranscribeRequest,
        *,
        progress_callback: ProgressCallback | None = None,
    ) -> AiTranscribeResponse:
        source = self.uploads.get_path(req.file_id)
        if not source or not source.exists():
            raise FileNotFoundError(f"文件不存在：{req.file_id}")

        config = self.settings.load()
        output_dir = config.work_dir / "ai_transcribe" / uuid.uuid4().hex[:12]
        report_progress(progress_callback, "ai", 5, "准备 AI 转写")
        result = self.transcriber.transcribe(
            source,
            output_dir,
            target_key=req.target_key,
            title=req.title,
            render_dpi=req.render_dpi,
            max_pages=req.max_pages,
            extra_prompt=req.prompt,
            normalize=req.normalize,
            progress_callback=progress_callback,
        )

        report_progress(progress_callback, "ai", 88, "写入 AI 草稿")
        jianpu_path = output_dir / f"{source.stem}_ai_jianpu.txt"
        self.file_service.write_text(jianpu_path, result.merged_jianpu_text)
        jianpu_file_id = self.uploads.register(jianpu_path)

        report_progress(progress_callback, "ai", 94, "注册 AI 页面")
        pages: list[AiTranscribedPage] = []
        for page in result.pages:
            image_file_id = self._register_page_image(
                req.file_id,
                source,
                page.prepared.image_path,
                page.prepared.generated,
            )
            pages.append(
                AiTranscribedPage(
                    page_index=page.prepared.page_index,
                    page_image_file_id=image_file_id,
                    page_image_filename=page.prepared.image_path.name,
                    title=page.result.title,
                    key=page.result.key,
                    meter=page.result.meter,
                    tempo=page.result.tempo,
                    jianpu_text=page.jianpu_text,
                    warnings=page.result.warnings,
                    validation_errors=page.validation_errors,
                    confidence=page.result.confidence,
                )
            )

        return AiTranscribeResponse(
            source_file_id=req.file_id,
            source_filename=source.name,
            target_key=req.target_key,
            title=req.title or _first_page_title(pages),
            merged_jianpu_text=result.merged_jianpu_text,
            jianpu_file_id=jianpu_file_id,
            pages=pages,
            warnings=result.warnings,
        )

    def _register_page_image(
        self,
        source_file_id: str,
        source_path: Path,
        image_path: Path,
        generated: bool,
    ) -> str:
        if not generated and image_path.resolve() == source_path.resolve():
            return source_file_id
        return self.uploads.register(image_path)

    def get_config(self) -> ToolConfig:
        return self.settings.load()


def _first_page_title(pages: list[AiTranscribedPage]) -> str | None:
    for page in pages:
        if page.title:
            return page.title
    return None
