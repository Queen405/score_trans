from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, UploadFile

from ...models.files.schemas import UploadResponse
from ...services.files.upload_service import UploadService


MEDIA_TYPES: dict[str, str] = {
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
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".webp": "image/webp",
}


class FileActions:
    def __init__(self, uploads: UploadService | None = None) -> None:
        self.uploads = uploads or UploadService()

    def upload_file(self, file: UploadFile) -> UploadResponse:
        if not file.filename:
            raise HTTPException(400, "文件名不能为空")

        file_id = self.uploads.save(file)
        path = self.uploads.get_path(file_id)
        size = path.stat().st_size if path and path.exists() else 0
        return UploadResponse(file_id=file_id, filename=file.filename, size=size)

    def download_file(self, file_id: str) -> tuple[Path, str]:
        path = self.uploads.get_path(file_id)
        if not path or not path.exists():
            raise HTTPException(404, f"文件不存在：{file_id}")
        media_type = MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")
        return path, media_type

    def delete_file(self, file_id: str) -> dict[str, str]:
        self.uploads.cleanup(file_id)
        return {"status": "deleted"}

