from __future__ import annotations

import pytest

from score_trans.dao.history.history_dao import HistoryDao
from score_trans.exec.history.actions import HistoryActions
from score_trans.models.history.entities import HistoryPage
from score_trans.models.history.schemas import (
    BatchRenderStateUpdate,
    BatchSavePage,
    BatchSaveRequest,
    RenderPageOcrText,
)
from score_trans.models.provenance.schemas import TextAnchor
from score_trans.services.history.history_service import HistoryService


def _saved_page(page_id: int, text: str) -> BatchSavePage:
    return BatchSavePage(
        page_id=page_id,
        task_id="task-saved",
        musicxml_file_id="xml-saved",
        jianpu_text=text,
        ocr_text="ocr-saved",
        text_attachments=[],
        svg_file_id="svg-saved",
        overlay_file_id="overlay-saved",
        source_map_file_id="source-map-saved",
        text_hash="hash-saved",
        text_anchors=[],
        text_anchor_baseline_text=f"baseline-{text}",
        text_anchor_baseline_anchors=[
            TextAnchor(
                source_id="s1:i1",
                start_utf16=0,
                end_utf16=1,
                role="note",
            )
        ],
        status="completed",
        error_message="",
        omr_file_id="omr-saved",
        original_musicxml="<original/>",
        working_musicxml="<working/>",
        deleted_source_ids=["s1:i1"],
    )


def _save_request(batch, *, source: str = "save") -> BatchSaveRequest:
    return BatchSaveRequest(
        jianpu_text="batch-saved",
        source=source,
        pages=[
            _saved_page(page.id, f"page-{index}-saved")
            for index, page in enumerate(batch.pages)
        ],
        render_page_file_ids=["render-1"],
        render_page_ocr_texts=[RenderPageOcrText(page_index=0, ocr_text="render-ocr")],
        render_output_stale=False,
        render_layout_key="layout-saved",
    )


def test_save_batch_persists_complete_snapshot_and_snapshot_record(tmp_path) -> None:
    service = HistoryService(tmp_path / "history.db")
    batch = service.create_batch(
        [HistoryPage(input_file_name="a.png"), HistoryPage(input_file_name="b.png")],
        jianpu_text="batch-old",
    )
    actions = HistoryActions(service)

    saved = actions.save_batch(batch.id, _save_request(batch, source="reset"))

    assert saved.jianpu_text == "batch-saved"
    assert [page.jianpu_text for page in saved.pages] == [
        "page-0-saved",
        "page-1-saved",
    ]
    assert saved.pages[1].ocr_text == "ocr-saved"
    assert saved.pages[1].deleted_source_ids == ["s1:i1"]
    assert saved.pages[1].text_anchor_baseline_text == "baseline-page-1-saved"
    assert saved.pages[1].text_anchor_baseline_anchors[0].source_id == "s1:i1"
    assert saved.render_page_file_ids == ["render-1"]
    assert saved.render_page_ocr_texts[0].ocr_text == "render-ocr"
    assert saved.render_output_stale is False
    assert saved.render_layout_key == "layout-saved"
    snapshots = actions.list_jianpu_snapshots(batch.id)
    assert [(item.jianpu_text, item.source) for item in snapshots] == [
        ("batch-saved", "reset")
    ]


def test_save_batch_rejects_foreign_page_without_partial_write(tmp_path) -> None:
    service = HistoryService(tmp_path / "history.db")
    first = service.create_batch(
        [HistoryPage(input_file_name="a.png")], jianpu_text="first"
    )
    second = service.create_batch(
        [HistoryPage(input_file_name="b.png")], jianpu_text="second"
    )
    request = _save_request(first)
    request.pages = [_saved_page(second.pages[0].id, "foreign")]

    with pytest.raises(ValueError, match="pages.*batch"):
        HistoryActions(service).save_batch(first.id, request)

    unchanged = service.get_batch(first.id)
    assert unchanged is not None
    assert unchanged.jianpu_text == "first"
    assert unchanged.pages[0].jianpu_text == ""
    assert service.list_snapshots(first.id) == []


def test_save_batch_requires_each_batch_page_exactly_once(tmp_path) -> None:
    service = HistoryService(tmp_path / "history.db")
    batch = service.create_batch(
        [HistoryPage(input_file_name="a.png"), HistoryPage(input_file_name="b.png")]
    )
    actions = HistoryActions(service)

    missing = _save_request(batch)
    missing.pages = missing.pages[:1]
    with pytest.raises(ValueError, match="exactly"):
        actions.save_batch(batch.id, missing)

    duplicate = _save_request(batch)
    duplicate.pages[1] = duplicate.pages[0]
    with pytest.raises(ValueError, match="duplicate"):
        actions.save_batch(batch.id, duplicate)


def test_save_batch_rolls_back_page_batch_and_snapshot_on_write_failure(
    tmp_path,
) -> None:
    class FailingHistoryDao(HistoryDao):
        def _push_snapshot_locked(self, conn, batch_id, jianpu_text, source):
            super()._push_snapshot_locked(conn, batch_id, jianpu_text, source)
            raise RuntimeError("injected failure")

    dao = FailingHistoryDao(tmp_path / "history.db")
    service = HistoryService(dao=dao)
    batch = service.create_batch(
        [HistoryPage(input_file_name="a.png")], jianpu_text="old"
    )

    with pytest.raises(RuntimeError, match="injected failure"):
        HistoryActions(service).save_batch(batch.id, _save_request(batch))

    unchanged = service.get_batch(batch.id)
    assert unchanged is not None
    assert unchanged.jianpu_text == "old"
    assert unchanged.pages[0].jianpu_text == ""
    assert service.list_snapshots(batch.id) == []


def test_update_render_state_writes_files_ocr_layout_and_stale_together(
    tmp_path,
) -> None:
    service = HistoryService(tmp_path / "history.db")
    batch = service.create_batch([HistoryPage(input_file_name="a.png")])
    actions = HistoryActions(service)

    updated = actions.update_batch_render_state(
        batch.id,
        BatchRenderStateUpdate(
            render_page_file_ids=["render-1", "render-2"],
            render_page_ocr_texts=[
                RenderPageOcrText(page_index=0, ocr_text="first"),
                RenderPageOcrText(page_index=1, ocr_text="second"),
            ],
            render_output_stale=False,
            render_layout_key="layout-1",
        ),
    )

    assert updated.render_page_file_ids == ["render-1", "render-2"]
    assert [item.ocr_text for item in updated.render_page_ocr_texts] == [
        "first",
        "second",
    ]
    assert updated.render_output_stale is False
    assert updated.render_layout_key == "layout-1"
    assert "pages" not in updated.model_dump()


def test_fresh_render_state_requires_files_and_unique_ocr_indexes() -> None:
    with pytest.raises(ValueError, match="render_page_file_ids"):
        BatchRenderStateUpdate(
            render_page_file_ids=[],
            render_page_ocr_texts=[],
            render_output_stale=False,
            render_layout_key="",
        )

    with pytest.raises(ValueError, match="page_index"):
        BatchRenderStateUpdate(
            render_page_file_ids=["render-1"],
            render_page_ocr_texts=[
                RenderPageOcrText(page_index=0, ocr_text="first"),
                RenderPageOcrText(page_index=0, ocr_text="duplicate"),
            ],
            render_output_stale=True,
            render_layout_key="",
        )
