from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File

from ..dependencies import get_export, get_upload_manager
from ..schemas import ExportResponse
from ..uploads import UploadManager
from ...services.export_service import png_pages_to_pdf
from ...use_cases import ExportScoreUseCase

router = APIRouter(prefix="/export", tags=["export"])


@router.post("/midi", response_model=ExportResponse)
async def export_midi(
    musicxml_file_id: str,
    filename: str | None = None,
    uc: ExportScoreUseCase = Depends(get_export),
    uploads: UploadManager = Depends(get_upload_manager),
):
    musicxml_path = uploads.get_path(musicxml_file_id)
    if not musicxml_path or not musicxml_path.exists():
        raise HTTPException(404, f"MusicXML 文件不存在：{musicxml_file_id}")

    out_name = filename or f"{musicxml_path.stem}.mid"
    output_path = uploads.base_dir / f"{uuid.uuid4().hex[:12]}.mid"
    uc.execute(musicxml_path, output_path)
    file_id = uploads.register(output_path)
    return ExportResponse(file_id=file_id, filename=out_name)


@router.post("/pdf", response_model=ExportResponse)
async def export_pdf(
    files: list[UploadFile] = File(..., description="PNG images, one per page"),
    filename: str = "jianpu.pdf",
    uploads: UploadManager = Depends(get_upload_manager),
):
    if not files:
        raise HTTPException(400, "至少需要一个 PNG 图片")

    png_pages: list[bytes] = []
    for f in files:
        data = await f.read()
        if not data[:8].startswith(b"\x89PNG"):
            raise HTTPException(400, f"文件 {f.filename} 不是有效的 PNG")
        png_pages.append(data)

    output_path = uploads.base_dir / f"{uuid.uuid4().hex[:12]}.pdf"
    png_pages_to_pdf(png_pages, output_path)
    file_id = uploads.register(output_path)
    return ExportResponse(file_id=file_id, filename=filename)
