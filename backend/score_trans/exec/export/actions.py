from __future__ import annotations

import asyncio
import uuid
import hashlib
from pathlib import Path

from score_trans.config.settings import (
    MAX_UPLOAD_FILE_BYTES,
    MAX_UPLOAD_REQUEST_BYTES,
)

from ...domain.jianpu import parse_jianpu_scores
from ...domain.parse.jianpu_text import parse_jianpu_parts
from ...models.playback import PlaybackTextSource
from ...models.common.errors import UploadTooLargeError
from ...models.common.protocols import UploadFileLike
from ...models.export.schemas import (
    ExportMidiRequest,
    ExportMidiTextRequest,
    ExportFilesResponse,
    ExportMusicXmlRequest,
    ExportMusicXmlTextRequest,
    ExportRenderedImagesRequest,
    ExportRenderedPdfRequest,
    ExportResponse,
)
from ...models.score import JianpuScore
from ...services.export.export_service import (
    ExportService,
    images_to_pdf,
    svg_page_to_image,
    svg_pages_to_pdf,
)
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
        title: str | None = None,
    ) -> Path:
        musicxml_path = Path(musicxml_file)
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        scores = self.converter.build_scores(
            musicxml_path,
            target_key=target_key,
        )
        if title:
            for score in scores:
                score.title = title
        return self.export_service.export_midi_scores(scores, output_path)


class ExportActions:
    def __init__(
        self,
        uploads: UploadService | None = None,
        exporter: ExportScoreAction | None = None,
        export_service: ExportService | None = None,
        *,
        max_upload_file_bytes: int = MAX_UPLOAD_FILE_BYTES,
        max_upload_request_bytes: int = MAX_UPLOAD_REQUEST_BYTES,
    ) -> None:
        if max_upload_file_bytes <= 0:
            raise ValueError("max_upload_file_bytes must be greater than zero")
        if max_upload_request_bytes <= 0:
            raise ValueError("max_upload_request_bytes must be greater than zero")
        self.uploads = uploads or UploadService()
        self.exporter = exporter or ExportScoreAction()
        self.export_service = export_service or ExportService()
        self.max_upload_file_bytes = max_upload_file_bytes
        self.max_upload_request_bytes = max_upload_request_bytes

    def export_midi(self, req: ExportMidiRequest) -> ExportResponse:
        file_ids = list(
            dict.fromkeys(
                req.musicxml_file_ids
                or ([req.musicxml_file_id] if req.musicxml_file_id else [])
            )
        )
        if not file_ids:
            raise ValueError("至少需要一个 MusicXML 文件")
        paths = [self.uploads.get_path(file_id) for file_id in file_ids]
        if any(not path or not path.exists() for path in paths):
            missing = next(
                file_id
                for file_id, path in zip(file_ids, paths)
                if not path or not path.exists()
            )
            raise FileNotFoundError(f"MusicXML 文件不存在：{missing}")
        scores = []
        for path in paths:
            scores.extend(
                self.exporter.converter.build_scores(path, target_key=req.target_key)
            )
        output_path = self.uploads.base_dir / f"{uuid.uuid4().hex[:12]}.mid"
        self.export_service.export_midi_scores(scores, output_path)
        source_stem = paths[0].stem
        out_name = req.filename or f"{source_stem}.mid"
        file_id = self.uploads.register(output_path)
        return ExportResponse(file_id=file_id, filename=out_name)

    def export_midi_text(self, req: ExportMidiTextRequest) -> ExportResponse:
        parts = parse_jianpu_parts(req.jianpu_text, title=req.title)
        source = PlaybackTextSource(
            hashlib.sha256(req.jianpu_text.encode("utf-8")).hexdigest()
        )
        bom_offset = len(req.jianpu_text) - len(req.jianpu_text.lstrip("﻿"))
        for part in parts:
            for measure in part.score.measures:
                for event in measure.events:
                    if (
                        event.source_start_utf16 is not None
                        and event.source_end_utf16 is not None
                    ):
                        base = part.body_start_utf16 + bom_offset
                        source.event_ranges[id(event)] = (
                            base + event.source_start_utf16,
                            base + event.source_end_utf16,
                        )
        output_path = self.uploads.base_dir / f"{uuid.uuid4().hex[:12]}.mid"
        self.export_service.export_midi_scores(
            [part.score for part in parts], output_path, text_source=source
        )
        file_id = self.uploads.register(output_path)
        return ExportResponse(file_id=file_id, filename=req.filename or "score.mid")

    def export_musicxml(self, req: ExportMusicXmlRequest) -> ExportResponse:
        file_ids = list(
            dict.fromkeys(
                req.musicxml_file_ids
                or ([req.musicxml_file_id] if req.musicxml_file_id else [])
            )
        )
        if not file_ids:
            raise ValueError("至少需要一个 MusicXML 文件")
        paths = [self.uploads.get_path(file_id) for file_id in file_ids]
        if any(not path or not path.exists() for path in paths):
            missing = next(
                file_id
                for file_id, path in zip(file_ids, paths)
                if not path or not path.exists()
            )
            raise FileNotFoundError(f"MusicXML 文件不存在：{missing}")
        scores = []
        for path in paths:
            scores.extend(
                self.exporter.converter.build_scores(path, target_key=req.target_key)
            )
        if req.title:
            for score in scores:
                score.title = req.title

        out_name = req.filename or f"{paths[0].stem}.musicxml"
        output_path = self.uploads.base_dir / f"{uuid.uuid4().hex[:12]}.musicxml"
        first_score = scores[0] if scores else JianpuScore()
        self.export_service.export_musicxml_scores(
            scores,
            output_path,
            title=first_score.title,
        )
        file_id = self.uploads.register(output_path)
        return ExportResponse(file_id=file_id, filename=out_name)

    def export_musicxml_text(self, req: ExportMusicXmlTextRequest) -> ExportResponse:
        scores = parse_jianpu_scores(req.jianpu_text, title=req.title)
        output_path = self.uploads.base_dir / f"{uuid.uuid4().hex[:12]}.musicxml"
        first_score = scores[0] if scores else JianpuScore()
        self.export_service.export_musicxml_scores(
            scores,
            output_path,
            title=first_score.title,
        )
        file_id = self.uploads.register(output_path)
        return ExportResponse(
            file_id=file_id, filename=req.filename or "score.musicxml"
        )

    def export_rendered_pdf(self, req: ExportRenderedPdfRequest) -> ExportResponse:
        pages = [self._read_svg_page(file_id) for file_id in req.svg_file_ids]
        output_path = self.uploads.base_dir / f"{uuid.uuid4().hex[:12]}.pdf"
        svg_pages_to_pdf(pages, output_path)
        return ExportResponse(
            file_id=self.uploads.register(output_path),
            filename=_filename_with_suffix(req.filename, ".pdf"),
        )

    def export_rendered_images(
        self, req: ExportRenderedImagesRequest
    ) -> ExportFilesResponse:
        suffix = ".jpg" if req.format == "jpeg" else ".png"
        stem = Path(req.filename).stem or "jianpu"
        files: list[ExportResponse] = []
        for index, file_id in enumerate(req.svg_file_ids):
            output_path = self.uploads.base_dir / f"{uuid.uuid4().hex[:12]}{suffix}"
            svg_page_to_image(
                self._read_svg_page(file_id),
                output_path,
                dpi=req.dpi,
                image_format=req.format,
            )
            filename = (
                f"{stem}{suffix}"
                if len(req.svg_file_ids) == 1
                else f"{stem}_p{index + 1}{suffix}"
            )
            files.append(
                ExportResponse(
                    file_id=self.uploads.register(output_path),
                    filename=filename,
                )
            )
        return ExportFilesResponse(files=files)

    def _read_svg_page(self, file_id: str) -> bytes:
        path = self.uploads.get_path(file_id)
        if not path or not path.exists():
            raise FileNotFoundError(f"SVG 页面不存在：{file_id}")
        data = path.read_bytes()
        if b"<svg" not in data[:4096]:
            raise ValueError(f"文件不是有效的 SVG 页面：{file_id}")
        return data

    async def export_pdf(
        self, files: list[UploadFileLike], filename: str = "jianpu.pdf"
    ) -> ExportResponse:
        if not files:
            raise ValueError("至少需要一个图片文件")

        image_pages: list[bytes] = []
        total_bytes = 0
        for uploaded in files:
            source_name = uploaded.filename or "upload"
            data = await _read_upload_bounded(
                uploaded,
                source_name=source_name,
                max_bytes=self.max_upload_file_bytes,
            )
            total_bytes += len(data)
            if total_bytes > self.max_upload_request_bytes:
                raise UploadTooLargeError(
                    f"请求体超过上传总大小上限 {self.max_upload_request_bytes} bytes"
                )
            if data[:8].startswith(b"\x89PNG"):
                image_pages.append(data)
            elif data[:3] == b"\xff\xd8\xff":
                image_pages.append(data)
            else:
                raise ValueError(
                    f"文件 {uploaded.filename} 不是有效的 PNG 或 JPEG 图片"
                )

        output_path = self.uploads.base_dir / f"{uuid.uuid4().hex[:12]}.pdf"
        return await asyncio.to_thread(
            self._write_pdf,
            image_pages,
            output_path,
            filename,
        )

    def _write_pdf(
        self,
        image_pages: list[bytes],
        output_path: Path,
        filename: str,
    ) -> ExportResponse:
        images_to_pdf(image_pages, output_path)
        file_id = self.uploads.register(output_path)
        return ExportResponse(file_id=file_id, filename=filename)


async def _read_upload_bounded(
    upload: UploadFileLike,
    *,
    source_name: str,
    max_bytes: int,
) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        remaining = max_bytes - total
        chunk = await upload.read(min(1024 * 1024, remaining + 1))
        if not chunk:
            return b"".join(chunks)
        total += len(chunk)
        if total > max_bytes:
            raise UploadTooLargeError(
                f"文件 {source_name} 超过上传大小上限 {max_bytes} bytes"
            )
        chunks.append(chunk)


def _filename_with_suffix(filename: str, suffix: str) -> str:
    path = Path(filename)
    return (
        path.name
        if path.suffix.lower() == suffix
        else f"{path.stem or 'jianpu'}{suffix}"
    )
