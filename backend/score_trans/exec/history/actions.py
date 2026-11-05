from __future__ import annotations

from ...models.history.entities import (
    HistoryBatch,
    HistoryPage,
    HistoryRenderPageOcrText,
)
from ...models.history.schemas import (
    BatchCreateRequest,
    BatchJianpuTextUpdate,
    BatchListItem,
    BatchPageOrderRequest,
    BatchRenderPageOcrTextsUpdate,
    BatchRenderPagesUpdate,
    BatchResponse,
    BatchRenderStateResponse,
    BatchRenderStateUpdate,
    BatchSaveRequest,
    BatchSavePage,
    DeleteAllResponse,
    JianpuSnapshotItem,
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
                last_completed_at=batch.last_completed_at,
            )
            for batch in self.service.list_batch_summaries()
        ]

    def create_batch(self, req: BatchCreateRequest) -> BatchResponse:
        pages = [
            HistoryPage(
                input_file_name=p.input_file_name,
                input_file_id=p.input_file_id,
                source_document_file_id=p.source_document_file_id,
                source_document_name=p.source_document_name,
                source_page_index=p.source_page_index,
                source_rotation=p.source_rotation,
                task_id=p.task_id,
                musicxml_file_id=p.musicxml_file_id,
                jianpu_text=p.jianpu_text,
                ocr_text=p.ocr_text,
                text_attachments=p.text_attachments,
                svg_file_id=p.svg_file_id,
                engine_version=p.engine_version if p.svg_file_id else "",
                document_revision=p.document_revision or p.text_hash,
                overlay_svg_file_id=p.overlay_svg_file_id,
                overlay_file_id=p.overlay_file_id,
                source_map_file_id=p.source_map_file_id,
                text_hash=p.text_hash,
                text_anchors=p.text_anchors,
                text_anchor_baseline_text=(
                    p.text_anchor_baseline_text
                    if p.text_anchor_baseline_text is not None
                    else p.jianpu_text
                ),
                text_anchor_baseline_anchors=(
                    p.text_anchor_baseline_anchors
                    if p.text_anchor_baseline_anchors is not None
                    else p.text_anchors
                ),
                status=p.status,
                error_message=p.error_message,
                omr_file_id=p.omr_file_id,
                original_musicxml=p.original_musicxml,
                working_musicxml=p.working_musicxml,
                deleted_source_ids=p.deleted_source_ids,
                recognition_candidate_selections=p.recognition_candidate_selections,
            )
            for p in req.pages
        ]
        return _batch_to_response(
            self.service.create_batch(
                pages,
                req.render_page_file_ids,
                jianpu_text=req.jianpu_text,
                render_page_ocr_texts=[
                    HistoryRenderPageOcrText(
                        page_index=item.page_index,
                        ocr_text=item.ocr_text,
                    )
                    for item in req.render_page_ocr_texts
                ],
                render_output_stale=req.render_output_stale,
                render_layout_key=req.render_layout_key,
            )
        )

    def get_history(
        self, batch_id: int, *, include_musicxml: bool = True
    ) -> BatchResponse:
        batch = self.service.get_batch(batch_id, include_musicxml=include_musicxml)
        if not batch:
            raise FileNotFoundError("Batch not found")
        return _batch_to_response(batch, include_musicxml=include_musicxml)

    def get_history_page(self, page_id: int) -> PageResponse:
        page = self.service.get_page(page_id)
        if not page:
            raise FileNotFoundError("Page not found")
        return _page_to_response(page)

    def update_history_page(self, page_id: int, req: PageUpdate) -> PageResponse:
        baseline_text = req.text_anchor_baseline_text
        if baseline_text is None and req.jianpu_text is not None:
            baseline_text = req.jianpu_text
        baseline_anchors = req.text_anchor_baseline_anchors
        if baseline_anchors is None and req.text_anchors is not None:
            baseline_anchors = req.text_anchors
        page = self.service.update_page(
            page_id,
            input_file_name=req.input_file_name,
            input_file_id=req.input_file_id,
            source_rotation=req.source_rotation,
            task_id=req.task_id,
            musicxml_file_id=req.musicxml_file_id,
            jianpu_text=req.jianpu_text if req.jianpu_text is not None else None,
            ocr_text=req.ocr_text,
            text_attachments=req.text_attachments,
            svg_file_id=req.svg_file_id,
            engine_version=req.engine_version,
            document_revision=req.document_revision,
            overlay_svg_file_id=req.overlay_svg_file_id,
            overlay_file_id=req.overlay_file_id,
            source_map_file_id=req.source_map_file_id,
            text_hash=req.text_hash,
            text_anchors=req.text_anchors,
            text_anchor_baseline_text=baseline_text,
            text_anchor_baseline_anchors=baseline_anchors,
            status=req.status,
            error_message=req.error_message,
            omr_file_id=req.omr_file_id,
            original_musicxml=req.original_musicxml,
            working_musicxml=req.working_musicxml,
            deleted_source_ids=req.deleted_source_ids,
            recognition_candidate_selections=req.recognition_candidate_selections,
        )
        if not page:
            raise FileNotFoundError("Page not found")
        return _page_to_response(page)

    def update_batch_render_pages(
        self, batch_id: int, req: BatchRenderPagesUpdate
    ) -> BatchResponse:
        batch = self.service.update_batch_render_pages(
            batch_id,
            req.render_page_file_ids,
            render_output_stale=req.render_output_stale,
            render_layout_key=req.render_layout_key,
        )
        if not batch:
            raise FileNotFoundError("Batch not found")
        return _batch_to_response(batch)

    def update_batch_jianpu_text(
        self, batch_id: int, req: BatchJianpuTextUpdate
    ) -> BatchResponse:
        batch = self.service.update_batch_jianpu_text(batch_id, req.jianpu_text)
        if not batch:
            raise FileNotFoundError("Batch not found")
        if req.source != "auto":
            self.service.push_snapshot(batch_id, req.jianpu_text, req.source)
        return _batch_to_response(batch)

    def list_jianpu_snapshots(self, batch_id: int) -> list[JianpuSnapshotItem]:
        return [
            JianpuSnapshotItem(
                id=snapshot.id,
                batch_id=snapshot.batch_id,
                jianpu_text=snapshot.jianpu_text,
                source=snapshot.source,
                created_at=snapshot.created_at,
            )
            for snapshot in self.service.list_snapshots(batch_id)
        ]

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
            render_output_stale=req.render_output_stale,
        )
        if not batch:
            raise FileNotFoundError("Batch not found")
        return _batch_to_response(batch)

    def save_batch(self, batch_id: int, req: BatchSaveRequest) -> BatchResponse:
        existing = self.service.get_batch(batch_id)
        if not existing:
            raise FileNotFoundError("Batch not found")
        existing_pages = {page.id: page for page in existing.pages}

        def saved_page(page: BatchSavePage) -> HistoryPage:
            previous = existing_pages.get(page.page_id, HistoryPage())
            return HistoryPage(
                id=page.page_id,
                task_id=page.task_id,
                musicxml_file_id=page.musicxml_file_id,
                jianpu_text=page.jianpu_text,
                ocr_text=page.ocr_text,
                text_attachments=page.text_attachments,
                svg_file_id=page.svg_file_id,
                overlay_file_id=page.overlay_file_id,
                source_map_file_id=page.source_map_file_id,
                text_hash=page.text_hash,
                text_anchors=page.text_anchors,
                text_anchor_baseline_text=(
                    page.text_anchor_baseline_text
                    if page.text_anchor_baseline_text is not None
                    else previous.text_anchor_baseline_text or previous.jianpu_text
                ),
                text_anchor_baseline_anchors=(
                    page.text_anchor_baseline_anchors
                    if page.text_anchor_baseline_anchors is not None
                    else previous.text_anchor_baseline_anchors or previous.text_anchors
                ),
                status=page.status,
                error_message=page.error_message,
                omr_file_id=page.omr_file_id,
                original_musicxml=page.original_musicxml,
                working_musicxml=page.working_musicxml,
                deleted_source_ids=page.deleted_source_ids,
                recognition_candidate_selections=page.recognition_candidate_selections,
            )

        batch = self.service.save_batch(
            batch_id,
            [saved_page(page) for page in req.pages],
            jianpu_text=req.jianpu_text,
            source=req.source,
            render_page_file_ids=req.render_page_file_ids,
            render_page_ocr_texts=[
                HistoryRenderPageOcrText(
                    page_index=item.page_index,
                    ocr_text=item.ocr_text,
                )
                for item in req.render_page_ocr_texts
            ],
            render_output_stale=req.render_output_stale,
            render_layout_key=req.render_layout_key,
        )
        if not batch:
            raise FileNotFoundError("Batch not found")
        return _batch_to_response(batch)

    def update_batch_render_state(
        self, batch_id: int, req: BatchRenderStateUpdate
    ) -> BatchRenderStateResponse:
        batch = self.service.update_batch_render_state(
            batch_id,
            req.render_page_file_ids,
            [
                HistoryRenderPageOcrText(
                    page_index=item.page_index,
                    ocr_text=item.ocr_text,
                )
                for item in req.render_page_ocr_texts
            ],
            render_output_stale=req.render_output_stale,
            render_layout_key=req.render_layout_key,
            load_batch=False,
        )
        if not batch:
            raise FileNotFoundError("Batch not found")
        return BatchRenderStateResponse(
            id=batch.id,
            render_page_file_ids=batch.render_page_file_ids,
            engine_version=batch.engine_version,
            render_layout_key=batch.render_layout_key,
            render_page_ocr_texts=[
                RenderPageOcrText(page_index=item.page_index, ocr_text=item.ocr_text)
                for item in batch.render_page_ocr_texts
            ],
            render_output_stale=batch.render_output_stale,
        )

    def reorder_pages(self, batch_id: int, req: BatchPageOrderRequest) -> BatchResponse:
        page_orders = [(item.page_id, item.jianpu_text) for item in req.pages]
        batch = self.service.reorder_pages(batch_id, req.jianpu_text, page_orders)
        if not batch:
            raise FileNotFoundError("Batch not found")
        return _batch_to_response(batch)

    def delete_history(self, batch_id: int) -> dict[str, bool]:
        if not self.service.delete_batch(batch_id):
            raise FileNotFoundError("Batch not found")
        return {"ok": True}

    def delete_all_history(self) -> DeleteAllResponse:
        return DeleteAllResponse(deleted_count=self.service.delete_all())


def _page_to_response(
    page: HistoryPage, *, include_musicxml: bool = True
) -> PageResponse:
    return PageResponse(
        id=page.id,
        batch_id=page.batch_id,
        input_file_name=page.input_file_name,
        input_file_id=page.input_file_id,
        source_document_file_id=page.source_document_file_id,
        source_document_name=page.source_document_name,
        source_page_index=page.source_page_index,
        source_rotation=page.source_rotation,
        task_id=page.task_id,
        musicxml_file_id=page.musicxml_file_id,
        jianpu_text=page.jianpu_text,
        ocr_text=page.ocr_text,
        text_attachments=page.text_attachments,
        svg_file_id=page.svg_file_id,
        engine_version=page.engine_version,
        document_revision=page.document_revision,
        overlay_svg_file_id=page.overlay_svg_file_id,
        overlay_file_id=page.overlay_file_id,
        source_map_file_id=page.source_map_file_id,
        text_hash=page.text_hash,
        text_anchors=page.text_anchors,
        text_anchor_baseline_text=page.text_anchor_baseline_text,
        text_anchor_baseline_anchors=page.text_anchor_baseline_anchors,
        status=page.status,
        error_message=page.error_message,
        omr_file_id=page.omr_file_id,
        original_musicxml=page.original_musicxml if include_musicxml else "",
        working_musicxml=page.working_musicxml if include_musicxml else "",
        deleted_source_ids=page.deleted_source_ids,
        recognition_candidate_selections=page.recognition_candidate_selections,
    )


def _batch_to_response(
    batch: HistoryBatch, *, include_musicxml: bool = True
) -> BatchResponse:
    return BatchResponse(
        id=batch.id,
        created_at=batch.created_at,
        page_count=batch.page_count,
        status=batch.status,
        jianpu_text=batch.jianpu_text,
        render_page_file_ids=_batch_render_page_file_ids(batch),
        engine_version=batch.engine_version,
        render_layout_key=batch.render_layout_key,
        document_revision=batch.document_revision,
        render_page_ocr_texts=[
            RenderPageOcrText(
                page_index=item.page_index,
                ocr_text=item.ocr_text,
            )
            for item in batch.render_page_ocr_texts
        ],
        render_output_stale=batch.render_output_stale,
        pages=[
            _page_to_response(p, include_musicxml=include_musicxml) for p in batch.pages
        ],
    )


def _batch_render_page_file_ids(batch: HistoryBatch) -> list[str]:
    if batch.render_page_file_ids:
        return batch.render_page_file_ids
    return [page.svg_file_id for page in batch.pages if page.svg_file_id]
