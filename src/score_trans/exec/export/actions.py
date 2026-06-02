from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

from ...domain.jianpu import parse_jianpu_score
from ...models.export.schemas import ExportMidiTextRequest, ExportResponse
from ...models.score import JianpuScore
from ...services.export.export_service import ExportService, png_pages_to_pdf
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
        return self.export_service.export(score, output_path, title=title)

    def execute_from_score(
        self,
        score: JianpuScore,
        output_file: str | Path,
        title: str | None = None,
    ) -> Path:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        return self.export_service.export(score, output_path, title=title)


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

    def export_midi(self, musicxml_file_id: str, filename: str | None = None) -> ExportResponse:
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

    async def export_pdf(self, files: list[UploadFile], filename: str = "jianpu.pdf") -> ExportResponse:
        if not files:
            raise HTTPException(400, "至少需要一个 PNG 图片")

        png_pages: list[bytes] = []
        for uploaded in files:
            data = await uploaded.read()
            if not data[:8].startswith(b"\x89PNG"):
                raise HTTPException(400, f"文件 {uploaded.filename} 不是有效的 PNG")
            png_pages.append(data)

        output_path = self.uploads.base_dir / f"{uuid.uuid4().hex[:12]}.pdf"
        png_pages_to_pdf(png_pages, output_path)
        file_id = self.uploads.register(output_path)
        return ExportResponse(file_id=file_id, filename=filename)

