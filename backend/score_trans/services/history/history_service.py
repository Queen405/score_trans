from __future__ import annotations

from pathlib import Path

from ...dao.history.history_dao import HistoryDao
from ...models.history.entities import (
    HistoryBatch,
    HistoryBatchSummary,
    HistoryPage,
    HistoryRenderPageOcrText,
)
from ...models.provenance.schemas import TextAnchor


class HistoryService:
    def __init__(
        self, db_path: str | Path | None = None, dao: HistoryDao | None = None
    ) -> None:
        self.dao = dao or HistoryDao(db_path)

    def list_batches(self) -> list[HistoryBatch]:
        return self.dao.list_batches()

    def list_batch_summaries(self) -> list[HistoryBatchSummary]:
        return self.dao.list_batch_summaries()

    def get_batch(self, batch_id: int) -> HistoryBatch | None:
        return self.dao.get_batch(batch_id)

    def get_page(self, page_id: int) -> HistoryPage | None:
        return self.dao.get_page(page_id)

    def create_batch(
        self,
        pages: list[HistoryPage],
        render_page_file_ids: list[str] | None = None,
        jianpu_text: str = "",
        render_page_ocr_texts: list[HistoryRenderPageOcrText] | None = None,
    ) -> HistoryBatch:
        return self.dao.create_batch(
            pages,
            render_page_file_ids,
            jianpu_text=jianpu_text,
            render_page_ocr_texts=render_page_ocr_texts,
        )

    def update_batch_render_pages(
        self, batch_id: int, render_page_file_ids: list[str]
    ) -> HistoryBatch | None:
        return self.dao.update_batch_render_pages(batch_id, render_page_file_ids)

    def update_batch_jianpu_text(
        self, batch_id: int, jianpu_text: str
    ) -> HistoryBatch | None:
        return self.dao.update_batch_jianpu_text(batch_id, jianpu_text)

    def update_batch_render_page_ocr_texts(
        self,
        batch_id: int,
        render_page_ocr_texts: list[HistoryRenderPageOcrText],
    ) -> HistoryBatch | None:
        return self.dao.update_batch_render_page_ocr_texts(
            batch_id,
            render_page_ocr_texts,
        )

    def update_page(
        self,
        page_id: int,
        *,
        task_id: str | None = None,
        jianpu_text: str | None = None,
        ocr_text: str | None = None,
        svg_file_id: str | None = None,
        overlay_svg_file_id: str | None = None,
        overlay_file_id: str | None = None,
        source_map_file_id: str | None = None,
        text_hash: str | None = None,
        text_anchors: list[TextAnchor] | None = None,
        musicxml_file_id: str | None = None,
        start_measure_number: int | None = None,
        status: str | None = None,
        error_message: str | None = None,
    ) -> HistoryPage | None:
        return self.dao.update_page(
            page_id,
            task_id=task_id,
            jianpu_text=jianpu_text,
            ocr_text=ocr_text,
            svg_file_id=svg_file_id,
            overlay_svg_file_id=overlay_svg_file_id,
            overlay_file_id=overlay_file_id,
            source_map_file_id=source_map_file_id,
            text_hash=text_hash,
            text_anchors=text_anchors,
            musicxml_file_id=musicxml_file_id,
            start_measure_number=start_measure_number,
            status=status,
            error_message=error_message,
        )

    def delete_batch(self, batch_id: int) -> bool:
        return self.dao.delete_batch(batch_id)

    def delete_all(self) -> int:
        return self.dao.delete_all()
