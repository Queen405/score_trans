from __future__ import annotations

import os
from pathlib import Path

from fastapi import HTTPException, UploadFile

from ...models.files.schemas import UploadPage, UploadResponse
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

        pages: list[UploadPage] | None = None
        if path and path.suffix.lower() == ".pdf":
            pages = self._pdf_to_images(path)

        return UploadResponse(file_id=file_id, filename=file.filename, size=size, pages=pages)

    def _pdf_to_images(self, pdf_path: Path) -> list[UploadPage] | None:
        try:
            import fitz
        except ImportError:
            return None

        try:
            doc = fitz.open(str(pdf_path))
            pages: list[UploadPage] = []
            stem = pdf_path.stem
            for i in range(len(doc)):
                page = doc.load_page(i)
                pix = page.get_pixmap(dpi=int(os.getenv("SCORE_TRANS_UPLOAD_PDF_DPI", "200")))
                img_filename = f"{stem}_page_{i + 1:03d}.png"
                img_path = pdf_path.parent / img_filename
                pix.save(str(img_path))
                img_file_id = self.uploads.register(img_path)
                pages.append(
                    UploadPage(file_id=img_file_id, filename=img_filename, page_index=i)
                )
            doc.close()
            return pages if pages else None
        except Exception:
            return None

    def download_file(self, file_id: str) -> tuple[Path, str]:
        path = self.uploads.get_path(file_id)
        if not path or not path.exists():
            raise HTTPException(404, f"文件不存在：{file_id}")
        media_type = MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")
        return path, media_type

    def delete_file(self, file_id: str) -> dict[str, str]:
        self.uploads.cleanup(file_id)
        return {"status": "deleted"}

