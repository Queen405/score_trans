from __future__ import annotations

from fastapi import HTTPException

from ...domain.jianpu import normalize_jianpu_text
from ...models.history.entities import HistoryBatch, HistoryPage
from ...models.history.schemas import (
    BatchCreateRequest,
    BatchListItem,
    BatchResponse,
    DeleteAllResponse,
    PageResponse,
    PageUpdate,
)
from ...services.history.history_service import HistoryService


class HistoryActions:
    def __init__(self, service: HistoryService | None = None) -> None:
        self.service = service or HistoryService()

    def list_history(self) -> list[BatchListItem]:
        result = []
        for batch in self.service.list_batches():
            first_name = batch.pages[0].input_file_name if batch.pages else ""
            result.append(
                BatchListItem(
                    id=batch.id,
                    created_at=batch.created_at,
                    page_count=batch.page_count,
                    status=batch.status,
                    first_file_name=first_name,
                )
            )
        return result

    def create_batch(self, req: BatchCreateRequest) -> BatchResponse:
        pages = [
            HistoryPage(
                input_file_name=p.input_file_name,
                input_file_id=p.input_file_id,
                musicxml_file_id=p.musicxml_file_id,
                jianpu_text=_normalize_history_text(p.jianpu_text),
                ocr_text=p.ocr_text,
                svg_file_id=p.svg_file_id,
                start_measure_number=p.start_measure_number,
                status=p.status,
                error_message=p.error_message,
            )
            for p in req.pages
        ]
        return _batch_to_response(self.service.create_batch(pages))

    def get_history(self, batch_id: int) -> BatchResponse:
        batch = self.service.get_batch(batch_id)
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")
        self._migrate_batch_texts(batch)
        return _batch_to_response(batch)

    def update_history_page(self, page_id: int, req: PageUpdate) -> PageResponse:
        page = self.service.update_page(
            page_id,
            musicxml_file_id=req.musicxml_file_id,
            jianpu_text=_normalize_history_text(req.jianpu_text) if req.jianpu_text is not None else None,
            ocr_text=req.ocr_text,
            svg_file_id=req.svg_file_id,
            start_measure_number=req.start_measure_number,
            status=req.status,
            error_message=req.error_message,
        )
        if not page:
            raise HTTPException(status_code=404, detail="Page not found")
        return _page_to_response(page)

    def delete_history(self, batch_id: int) -> dict[str, bool]:
        if not self.service.delete_batch(batch_id):
            raise HTTPException(status_code=404, detail="Batch not found")
        return {"ok": True}

    def delete_all_history(self) -> DeleteAllResponse:
        return DeleteAllResponse(deleted_count=self.service.delete_all())

    def _migrate_batch_texts(self, batch: HistoryBatch) -> None:
        for page in batch.pages:
            normalized = _normalize_history_text(page.jianpu_text)
            if normalized != page.jianpu_text:
                updated = self.service.update_page(page.id, jianpu_text=normalized)
                if updated:
                    page.jianpu_text = updated.jianpu_text


def _page_to_response(page: HistoryPage) -> PageResponse:
    return PageResponse(
        id=page.id,
        input_file_name=page.input_file_name,
        input_file_id=page.input_file_id,
        musicxml_file_id=page.musicxml_file_id,
        jianpu_text=page.jianpu_text,
        ocr_text=page.ocr_text,
        svg_file_id=page.svg_file_id,
        start_measure_number=page.start_measure_number,
        status=page.status,
        error_message=page.error_message,
    )


def _batch_to_response(batch: HistoryBatch) -> BatchResponse:
    return BatchResponse(
        id=batch.id,
        created_at=batch.created_at,
        page_count=batch.page_count,
        status=batch.status,
        pages=[_page_to_response(p) for p in batch.pages],
    )


def _normalize_history_text(text: str) -> str:
    if not text.strip():
        return text
    try:
        return normalize_jianpu_text(text)
    except ValueError:
        return text

