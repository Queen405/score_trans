from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ..dependencies import get_upload_manager
from ..schemas import UploadResponse
from ..uploads import UploadManager

router = APIRouter(prefix="/files", tags=["files"])

_MEDIA_TYPES: dict[str, str] = {
    ".svg": "image/svg+xml",
    ".pdf": "application/pdf",
    ".musicxml": "application/xml",
    ".xml": "application/xml",
    ".mxl": "application/zip",
    ".mid": "audio/midi",
    ".midi": "audio/midi",
    ".txt": "text/plain; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = ...,
    uploads: UploadManager = Depends(get_upload_manager),
):
    """Upload a file and get a file_id for use in other API calls."""
    if not file.filename:
        raise HTTPException(400, "文件名不能为空")

    file_id = uploads.save(file)
    path = uploads.get_path(file_id)
    size = path.stat().st_size if path and path.exists() else 0

    return UploadResponse(file_id=file_id, filename=file.filename, size=size)


@router.get("/{file_id}")
async def download_file(
    file_id: str,
    uploads: UploadManager = Depends(get_upload_manager),
):
    """Download a file by its file_id."""
    path = uploads.get_path(file_id)
    if not path or not path.exists():
        raise HTTPException(404, f"文件不存在：{file_id}")

    media_type = _MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")
    return FileResponse(path, media_type=media_type, filename=path.name)


@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    uploads: UploadManager = Depends(get_upload_manager),
):
    """Delete a previously uploaded file."""
    uploads.cleanup(file_id)
    return {"status": "deleted"}
