from __future__ import annotations

from pathlib import Path

from ...dao.history.history_dao import HistoryDao
from ...models.history.entities import (
    HistoryBatch,
    HistoryBatchSummary,
    HistoryPage,
    HistoryRenderPageOcrText,
    JianpuSnapshot,
)
from ...models.provenance.schemas import SourceTextAttachment, TextAnchor


class HistoryService:
    def __init__(
        self, db_path: str | Path | None = None, dao: HistoryDao | None = None
    ) -> None:
        self.dao = dao or HistoryDao(db_path)

    def list_batches(self) -> list[HistoryBatch]:
        return self.dao.list_batches()

    def list_batch_summaries(self) -> list[HistoryBatchSummary]:
        return self.dao.list_batch_summaries()

    def get_batch(
        self, batch_id: int, *, include_musicxml: bool = True
    ) -> HistoryBatch | None:
        return self.dao.get_batch(batch_id, include_musicxml=include_musicxml)

    def get_page(self, page_id: int) -> HistoryPage | None:
        return self.dao.get_page(page_id)

    def create_batch(
        self,
        pages: list[HistoryPage],
        render_page_file_ids: list[str] | None = None,
        jianpu_text: str = "",
        render_page_ocr_texts: list[HistoryRenderPageOcrText] | None = None,
        render_output_stale: bool = False,
        render_layout_key: str = "",
    ) -> HistoryBatch:
        return self.dao.create_batch(
            pages,
            render_page_file_ids,
            jianpu_text=jianpu_text,
            render_page_ocr_texts=render_page_ocr_texts,
            render_output_stale=render_output_stale,
            render_layout_key=render_layout_key,
        )

    def update_batch_render_pages(
        self,
        batch_id: int,
        render_page_file_ids: list[str],
        render_output_stale: bool = False,
        render_layout_key: str = "",
    ) -> HistoryBatch | None:
        return self.dao.update_batch_render_pages(
            batch_id,
            render_page_file_ids,
            render_output_stale=render_output_stale,
            render_layout_key=render_layout_key,
        )

    def update_batch_jianpu_text(
        self, batch_id: int, jianpu_text: str
    ) -> HistoryBatch | None:
        return self.dao.update_batch_jianpu_text(batch_id, jianpu_text)

    def push_snapshot(
        self, batch_id: int, jianpu_text: str, source: str = "save"
    ) -> None:
        self.dao.push_snapshot(batch_id, jianpu_text, source)

    def list_snapshots(self, batch_id: int) -> list[JianpuSnapshot]:
        return self.dao.list_snapshots(batch_id)

    def update_batch_render_page_ocr_texts(
        self,
        batch_id: int,
        render_page_ocr_texts: list[HistoryRenderPageOcrText],
        render_output_stale: bool = True,
    ) -> HistoryBatch | None:
        return self.dao.update_batch_render_page_ocr_texts(
            batch_id,
            render_page_ocr_texts,
            render_output_stale=render_output_stale,
        )

    def save_batch(
        self,
        batch_id: int,
        pages: list[HistoryPage],
        *,
        jianpu_text: str,
        source: str,
        render_page_file_ids: list[str],
        render_page_ocr_texts: list[HistoryRenderPageOcrText],
        render_output_stale: bool,
        render_layout_key: str,
        load_batch: bool = True,
    ) -> HistoryBatch | None:
        return self.dao.save_batch(
            batch_id,
            pages,
            jianpu_text=jianpu_text,
            source=source,
            render_page_file_ids=render_page_file_ids,
            render_page_ocr_texts=render_page_ocr_texts,
            render_output_stale=render_output_stale,
            render_layout_key=render_layout_key,
        )

    def update_batch_render_state(
        self,
        batch_id: int,
        render_page_file_ids: list[str],
        render_page_ocr_texts: list[HistoryRenderPageOcrText],
        *,
        render_output_stale: bool,
        render_layout_key: str,
        load_batch: bool = True,
    ) -> HistoryBatch | None:
        return self.dao.update_batch_render_state(
            batch_id,
            render_page_file_ids,
            render_page_ocr_texts,
            render_output_stale=render_output_stale,
            render_layout_key=render_layout_key,
            load_batch=load_batch,
        )

    def update_page(
        self,
        page_id: int,
        *,
        task_id: str | None = None,
        jianpu_text: str | None = None,
        ocr_text: str | None = None,
        text_attachments: list[SourceTextAttachment] | None = None,
        svg_file_id: str | None = None,
        engine_version: str | None = None,
        document_revision: str | None = None,
        overlay_svg_file_id: str | None = None,
        overlay_file_id: str | None = None,
        source_map_file_id: str | None = None,
        text_hash: str | None = None,
        text_anchors: list[TextAnchor] | None = None,
        text_anchor_baseline_text: str | None = None,
        text_anchor_baseline_anchors: list[TextAnchor] | None = None,
        musicxml_file_id: str | None = None,
        status: str | None = None,
        error_message: str | None = None,
        omr_file_id: str | None = None,
        original_musicxml: str | None = None,
        working_musicxml: str | None = None,
        deleted_source_ids: list[str] | None = None,
        recognition_candidate_selections: dict[str, str] | None = None,
    ) -> HistoryPage | None:
        return self.dao.update_page(
            page_id,
            task_id=task_id,
            jianpu_text=jianpu_text,
            ocr_text=ocr_text,
            text_attachments=text_attachments,
            svg_file_id=svg_file_id,
            engine_version=engine_version,
            document_revision=document_revision,
            overlay_svg_file_id=overlay_svg_file_id,
            overlay_file_id=overlay_file_id,
            source_map_file_id=source_map_file_id,
            text_hash=text_hash,
            text_anchors=text_anchors,
            text_anchor_baseline_text=text_anchor_baseline_text,
            text_anchor_baseline_anchors=text_anchor_baseline_anchors,
            musicxml_file_id=musicxml_file_id,
            status=status,
            error_message=error_message,
            omr_file_id=omr_file_id,
            original_musicxml=original_musicxml,
            working_musicxml=working_musicxml,
            deleted_source_ids=deleted_source_ids,
            recognition_candidate_selections=recognition_candidate_selections,
        )

    def reorder_pages(
        self,
        batch_id: int,
        jianpu_text: str,
        page_orders: list[tuple[int, str]],
    ) -> HistoryBatch | None:
        return self.dao.reorder_pages(batch_id, jianpu_text, page_orders)

    def delete_batch(self, batch_id: int) -> bool:
        return self.dao.delete_batch(batch_id)

    def delete_all(self) -> int:
        return self.dao.delete_all()
