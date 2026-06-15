from __future__ import annotations

from fastapi import HTTPException

from ...domain.jianpu import normalize_jianpu_text
from ...models.history.entities import (
    HistoryBatch,
    HistoryPage,
    HistoryRenderPageOcrText,
)
from ...models.history.schemas import (
    BatchCreateRequest,
    BatchJianpuTextUpdate,
    BatchListItem,
    BatchRenderPageOcrTextsUpdate,
    BatchRenderPagesUpdate,
    BatchResponse,
    DeleteAllResponse,
    PageResponse,
    PageUpdate,
    RenderPageOcrText,
)
from ...services.history.history_service import HistoryService


class HistoryActions:
    def __init__(self, service: HistoryService | None = None) -> None:
        self.service = service or HistoryService()

    def list_history(self) -> list[BatchListItem]:
        return [
            BatchListItem(
                id=batch.id,
                created_at=batch.created_at,
                page_count=batch.page_count,
                status=batch.status,
                first_file_name=batch.first_file_name,
            )
            for batch in self.service.list_batch_summaries()
        ]

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
        return _batch_to_response(
            self.service.create_batch(
                pages,
                req.render_page_file_ids,
                jianpu_text=_normalize_history_text(req.jianpu_text),
                render_page_ocr_texts=[
                    HistoryRenderPageOcrText(
                        page_index=item.page_index,
                        ocr_text=item.ocr_text,
                    )
                    for item in req.render_page_ocr_texts
                ],
            )
        )

    def get_history(self, batch_id: int) -> BatchResponse:
        batch = self.service.get_batch(batch_id)
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")
        return _batch_to_response(batch)

    def update_history_page(self, page_id: int, req: PageUpdate) -> PageResponse:
        page = self.service.update_page(
            page_id,
            musicxml_file_id=req.musicxml_file_id,
            jianpu_text=_normalize_history_text(req.jianpu_text)
            if req.jianpu_text is not None
            else None,
            ocr_text=req.ocr_text,
            svg_file_id=req.svg_file_id,
            start_measure_number=req.start_measure_number,
            status=req.status,
            error_message=req.error_message,
        )
        if not page:
            raise HTTPException(status_code=404, detail="Page not found")
        return _page_to_response(page)

    def update_batch_render_pages(
        self, batch_id: int, req: BatchRenderPagesUpdate
    ) -> BatchResponse:
        batch = self.service.update_batch_render_pages(
            batch_id, req.render_page_file_ids
        )
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")
        return _batch_to_response(batch)

    def update_batch_jianpu_text(
        self, batch_id: int, req: BatchJianpuTextUpdate
    ) -> BatchResponse:
        batch = self.service.update_batch_jianpu_text(
            batch_id, _normalize_history_text(req.jianpu_text)
        )
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")
        return _batch_to_response(batch)

    def update_batch_render_page_ocr_texts(
        self, batch_id: int, req: BatchRenderPageOcrTextsUpdate
    ) -> BatchResponse:
        batch = self.service.update_batch_render_page_ocr_texts(
            batch_id,
            [
                HistoryRenderPageOcrText(
                    page_index=item.page_index,
                    ocr_text=item.ocr_text,
                )
                for item in req.pages
            ],
        )
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")
        return _batch_to_response(batch)

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
        batch_id=page.batch_id,
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
        jianpu_text=batch.jianpu_text,
        render_page_file_ids=_batch_render_page_file_ids(batch),
        render_page_ocr_texts=[
            RenderPageOcrText(
                page_index=item.page_index,
                ocr_text=item.ocr_text,
            )
            for item in batch.render_page_ocr_texts
        ],
        pages=[_page_to_response(p) for p in batch.pages],
    )


def _batch_render_page_file_ids(batch: HistoryBatch) -> list[str]:
    if batch.render_page_file_ids:
        return batch.render_page_file_ids
    return [page.svg_file_id for page in batch.pages if page.svg_file_id]


def _normalize_history_text(text: str) -> str:
    if not text.strip():
        return text
    try:
        return normalize_jianpu_text(text)
    except ValueError:
        return text
