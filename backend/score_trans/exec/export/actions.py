from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

from ...domain.jianpu import parse_jianpu_score
from ...models.export.schemas import (
    ExportMidiTextRequest,
    ExportMusicXmlRequest,
    ExportMusicXmlTextRequest,
    ExportResponse,
)
from ...services.export.export_service import ExportService, images_to_pdf
from ...services.files.upload_service import UploadService
from ..convert.actions import MusicXmlToJianpuAction


class ExportScoreAction:
    def __init__(
        self,
        converter: MusicXmlToJianpuAction | None = None,
        export_service: ExportService | None = None,
    ) -> None:
        self.converter = converter or MusicXmlToJianpuAction()
        self.export_service = export_service or ExportService()

    def execute(
        self,
        musicxml_file: str | Path,
        output_file: str | Path,
        *,
        target_key: str = "C",
        start_measure_number: int | None = None,
        title: str | None = None,
    ) -> Path:
        musicxml_path = Path(musicxml_file)
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        score = self.converter.build_score(
            musicxml_path,
            target_key=target_key,
            start_measure_number=start_measure_number,
        )
        if title:
            score.title = title
        return self.export_service.export_midi(score, output_path)


class ExportActions:
    def __init__(
        self,
        uploads: UploadService | None = None,
        exporter: ExportScoreAction | None = None,
        export_service: ExportService | None = None,
    ) -> None:
        self.uploads = uploads or UploadService()
        self.exporter = exporter or ExportScoreAction()
        self.export_service = export_service or ExportService()

    def export_midi(
        self, musicxml_file_id: str, filename: str | None = None
    ) -> ExportResponse:
        musicxml_path = self.uploads.get_path(musicxml_file_id)
        if not musicxml_path or not musicxml_path.exists():
            raise HTTPException(404, f"MusicXML 文件不存在：{musicxml_file_id}")

        out_name = filename or f"{musicxml_path.stem}.mid"
        output_path = self.uploads.base_dir / f"{uuid.uuid4().hex[:12]}.mid"
        self.exporter.execute(musicxml_path, output_path)
        file_id = self.uploads.register(output_path)
        return ExportResponse(file_id=file_id, filename=out_name)

    def export_midi_text(self, req: ExportMidiTextRequest) -> ExportResponse:
        score = parse_jianpu_score(req.jianpu_text, title=req.title)
        output_path = self.uploads.base_dir / f"{uuid.uuid4().hex[:12]}.mid"
        self.export_service.export_midi(score, output_path)
        file_id = self.uploads.register(output_path)
        return ExportResponse(file_id=file_id, filename=req.filename or "score.mid")

    def export_musicxml(self, req: ExportMusicXmlRequest) -> ExportResponse:
        musicxml_path = self.uploads.get_path(req.musicxml_file_id)
        if not musicxml_path or not musicxml_path.exists():
            raise HTTPException(404, f"MusicXML 文件不存在：{req.musicxml_file_id}")

        score = self.exporter.converter.build_score(
            musicxml_path,
            target_key=req.target_key,
            start_measure_number=req.start_measure_number,
        )
        if req.title:
            score.title = req.title

        out_name = req.filename or f"{musicxml_path.stem}.musicxml"
        output_path = self.uploads.base_dir / f"{uuid.uuid4().hex[:12]}.musicxml"
        self.export_service.export_musicxml(score, output_path, title=score.title)
        file_id = self.uploads.register(output_path)
        return ExportResponse(file_id=file_id, filename=out_name)

    def export_musicxml_text(self, req: ExportMusicXmlTextRequest) -> ExportResponse:
        score = parse_jianpu_score(req.jianpu_text, title=req.title)
        output_path = self.uploads.base_dir / f"{uuid.uuid4().hex[:12]}.musicxml"
        self.export_service.export_musicxml(score, output_path, title=score.title)
        file_id = self.uploads.register(output_path)
        return ExportResponse(
            file_id=file_id, filename=req.filename or "score.musicxml"
        )

    async def export_pdf(
        self, files: list[UploadFile], filename: str = "jianpu.pdf"
    ) -> ExportResponse:
        if not files:
            raise HTTPException(400, "至少需要一个图片文件")

        image_pages: list[bytes] = []
        for uploaded in files:
            data = await uploaded.read()
            if data[:8].startswith(b"\x89PNG"):
                image_pages.append(data)
            elif data[:3] == b"\xff\xd8\xff":
                image_pages.append(data)
            else:
                raise HTTPException(
                    400, f"文件 {uploaded.filename} 不是有效的 PNG 或 JPEG 图片"
                )

        output_path = self.uploads.base_dir / f"{uuid.uuid4().hex[:12]}.pdf"
        images_to_pdf(image_pages, output_path)
        file_id = self.uploads.register(output_path)
        return ExportResponse(file_id=file_id, filename=filename)
