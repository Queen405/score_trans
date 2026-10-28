from __future__ import annotations

import logging
from pathlib import Path

from score_trans.config.settings import UPLOAD_PDF_DPI

from ...models.common.protocols import UploadFileLike
from ...models.files.schemas import FilesExistResponse, UploadPage, UploadResponse
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

logger = logging.getLogger(__name__)


class FileActions:
    def __init__(self, uploads: UploadService | None = None) -> None:
        self.uploads = uploads or UploadService()

    def upload_file(self, file: UploadFileLike) -> UploadResponse:
        if not file.filename:
            raise ValueError("文件名不能为空")

        file_id = self.uploads.save(file)
        path = self.uploads.get_path(file_id)
        size = path.stat().st_size if path and path.exists() else 0

        pages: list[UploadPage] | None = None
        if path and path.suffix.lower() == ".pdf":
            pages = self._pdf_to_images(path)

        return UploadResponse(
            file_id=file_id, filename=file.filename, size=size, pages=pages
        )

    def _pdf_to_images(self, pdf_path: Path) -> list[UploadPage] | None:
        try:
            import fitz
        except ImportError as exc:
            raise RuntimeError("PDF 页面转换依赖不可用") from exc

        try:
            doc = fitz.open(str(pdf_path))
            pages: list[UploadPage] = []
            stem = pdf_path.stem
            for i in range(len(doc)):
                page = doc.load_page(i)
                pix = page.get_pixmap(dpi=UPLOAD_PDF_DPI)
                img_filename = f"{stem}_page_{i + 1:03d}.png"
                img_path = pdf_path.parent / img_filename
                pix.save(str(img_path))
                img_file_id = self.uploads.register(img_path)
                pages.append(
                    UploadPage(file_id=img_file_id, filename=img_filename, page_index=i)
                )
            doc.close()
            return pages if pages else None
        except Exception as exc:
            logger.exception("PDF 页面转换失败: %s", pdf_path)
            raise ValueError("PDF 页面转换失败，请检查文件是否损坏") from exc

    def rotate_file(self, file_id: str, direction: str) -> UploadResponse:
        rotated_id, path = self.uploads.rotate_image(file_id, direction)
        return UploadResponse(
            file_id=rotated_id,
            filename=path.name,
            size=path.stat().st_size,
        )

    def download_file(self, file_id: str) -> tuple[Path, str]:
        path = self.uploads.get_path(file_id)
        if not path or not path.exists():
            raise FileNotFoundError(f"文件不存在：{file_id}")
        media_type = MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")
        return path, media_type

    def files_exist(self, file_ids: list[str]) -> FilesExistResponse:
        unique_ids = list(dict.fromkeys(file_id for file_id in file_ids if file_id))
        exists = self.uploads.exists_many(unique_ids)
        return FilesExistResponse(
            files={file_id: exists.get(file_id, False) for file_id in file_ids}
        )

    def delete_file(self, file_id: str) -> dict[str, str]:
        self.uploads.cleanup(file_id)
        return {"status": "deleted"}
