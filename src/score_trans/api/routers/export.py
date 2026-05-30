from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_config, get_export, get_upload_manager
from ..schemas import ExportRequest, ExportResponse
from ..uploads import UploadManager
from ...services.settings import ToolConfig
from ...use_cases import ExportScoreUseCase

router = APIRouter(prefix="/export", tags=["export"])


@router.post("", response_model=ExportResponse)
async def export_score(
    req: ExportRequest,
    uc: ExportScoreUseCase = Depends(get_export),
    config: ToolConfig = Depends(get_config),
    uploads: UploadManager = Depends(get_upload_manager),
):
    musicxml_path = uploads.get_path(req.musicxml_file_id)
    if not musicxml_path or not musicxml_path.exists():
        raise HTTPException(404, f"MusicXML 文件不存在：{req.musicxml_file_id}")

    filename = _export_filename(musicxml_path, req.output_format, req.filename)
    output_path = uploads.base_dir / f"{uuid.uuid4().hex[:12]}{Path(filename).suffix}"
    uc.execute(musicxml_path, output_path, config)
    file_id = uploads.register(output_path)
    return ExportResponse(file_id=file_id, filename=filename)


def _export_filename(source_path: Path, output_format: str, requested: str | None) -> str:
    fmt = "mid" if output_format == "midi" else output_format
    suffix = ".mid" if fmt == "mid" else f".{fmt}"
    raw_name = Path(requested).name if requested else f"{source_path.stem}{suffix}"
    safe_name = raw_name or f"{source_path.stem}{suffix}"
    return f"{Path(safe_name).stem}{suffix}"
