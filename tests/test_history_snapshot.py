from __future__ import annotations

import sqlite3

from score_trans.dao.history.history_dao import HistoryDao
from score_trans.exec.history.actions import HistoryActions
from score_trans.models.history.entities import HistoryPage
from score_trans.models.history.schemas import (
    BatchCreateRequest,
    BatchJianpuTextUpdate,
    PageCreate,
)
from score_trans.services.history.history_service import HistoryService


def _make_service(tmp_path) -> HistoryService:
    return HistoryService(tmp_path / "history.db")


def _make_batch(service: HistoryService, jianpu_text: str = "") -> int:
    batch = service.create_batch(
        [HistoryPage(input_file_name="a.png")],
        jianpu_text=jianpu_text,
    )
    return batch.id


def test_push_snapshot_keeps_only_newest_three(tmp_path) -> None:
    service = _make_service(tmp_path)
    batch_id = _make_batch(service)

    for text in ("1=C\n1", "1=C\n2", "1=C\n3", "1=C\n4"):
        service.push_snapshot(batch_id, text)

    snapshots = service.list_snapshots(batch_id)
    assert [s.jianpu_text for s in snapshots] == ["1=C\n4", "1=C\n3", "1=C\n2"]


def test_push_snapshot_deduplicates_same_text(tmp_path) -> None:
    service = _make_service(tmp_path)
    batch_id = _make_batch(service)

    service.push_snapshot(batch_id, "1=C\n1")
    service.push_snapshot(batch_id, "1=C\n1")
    service.push_snapshot(batch_id, "1=C\n1")

    snapshots = service.list_snapshots(batch_id)
    assert len(snapshots) == 1
    assert snapshots[0].jianpu_text == "1=C\n1"


def test_push_snapshot_records_empty_text(tmp_path) -> None:
    service = _make_service(tmp_path)
    batch_id = _make_batch(service)

    service.push_snapshot(batch_id, "")

    snapshots = service.list_snapshots(batch_id)
    assert len(snapshots) == 1
    assert snapshots[0].jianpu_text == ""


def test_push_snapshot_persists_source(tmp_path) -> None:
    service = _make_service(tmp_path)
    batch_id = _make_batch(service)

    service.push_snapshot(batch_id, "1=C\n1", "save")
    service.push_snapshot(batch_id, "1=C\n2", "reset")

    snapshots = service.list_snapshots(batch_id)
    assert snapshots[0].source == "reset"
    assert snapshots[1].source == "save"


def test_push_snapshot_ignores_missing_batch(tmp_path) -> None:
    service = _make_service(tmp_path)

    service.push_snapshot(9999, "1=C\n1")

    assert service.list_snapshots(9999) == []


def test_delete_batch_cascades_snapshots(tmp_path) -> None:
    service = _make_service(tmp_path)
    batch_id = _make_batch(service)
    service.push_snapshot(batch_id, "1=C\n1")

    service.delete_batch(batch_id)

    assert service.list_snapshots(batch_id) == []


def test_list_snapshots_orders_by_id_desc(tmp_path) -> None:
    service = _make_service(tmp_path)
    batch_id = _make_batch(service)

    service.push_snapshot(batch_id, "1=C\n1")
    service.push_snapshot(batch_id, "1=C\n2")
    service.push_snapshot(batch_id, "1=C\n3")

    snapshots = service.list_snapshots(batch_id)
    assert [s.id for s in snapshots] == sorted([s.id for s in snapshots], reverse=True)
    assert [s.jianpu_text for s in snapshots] == ["1=C\n3", "1=C\n2", "1=C\n1"]


def test_update_batch_jianpu_text_action_pushes_snapshot(tmp_path) -> None:
    actions = HistoryActions(HistoryService(tmp_path / "history.db"))
    created = actions.create_batch(
        BatchCreateRequest(pages=[PageCreate(input_file_name="a.png")])
    )
    batch_id = created.id

    actions.update_batch_jianpu_text(
        batch_id, BatchJianpuTextUpdate(jianpu_text="1=C\n1")
    )
    actions.update_batch_jianpu_text(
        batch_id,
        BatchJianpuTextUpdate(jianpu_text="1=C\n2", source="reset"),
    )

    snapshots = actions.list_jianpu_snapshots(batch_id)
    assert [s.jianpu_text for s in snapshots] == ["1=C\n2", "1=C\n1"]
    assert snapshots[0].source == "reset"
    assert snapshots[1].source == "save"


def test_update_batch_jianpu_text_auto_source_skips_snapshot(tmp_path) -> None:
    actions = HistoryActions(HistoryService(tmp_path / "history.db"))
    created = actions.create_batch(
        BatchCreateRequest(pages=[PageCreate(input_file_name="a.png")])
    )
    batch_id = created.id

    updated = actions.update_batch_jianpu_text(
        batch_id, BatchJianpuTextUpdate(jianpu_text="1=C\n1", source="auto")
    )

    assert updated.jianpu_text == "1=C\n1"
    assert actions.list_jianpu_snapshots(batch_id) == []


def test_v7_database_migrates_to_v8_with_snapshot_table(tmp_path) -> None:
    db_path = tmp_path / "history.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA user_version = 7")
        conn.execute(
            """
            CREATE TABLE history_batch (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                page_count INTEGER NOT NULL DEFAULT 0,
                jianpu_text TEXT NOT NULL DEFAULT '',
                render_page_file_ids TEXT NOT NULL DEFAULT '[]',
                render_page_ocr_texts TEXT NOT NULL DEFAULT '[]',
                render_output_stale INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'completed',
                engine_version TEXT NOT NULL DEFAULT '',
                document_revision TEXT NOT NULL DEFAULT '',
                render_layout_key TEXT NOT NULL DEFAULT ''
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE history_page (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id INTEGER NOT NULL REFERENCES history_batch(id) ON DELETE CASCADE,
                input_file_name TEXT NOT NULL DEFAULT '',
                input_file_id TEXT NOT NULL DEFAULT '',
                task_id TEXT NOT NULL DEFAULT '',
                musicxml_file_id TEXT NOT NULL DEFAULT '',
                jianpu_text TEXT NOT NULL DEFAULT '',
                ocr_text TEXT NOT NULL DEFAULT '',
                text_attachments TEXT NOT NULL DEFAULT '[]',
                svg_file_id TEXT NOT NULL DEFAULT '',
                overlay_svg_file_id TEXT NOT NULL DEFAULT '',
                overlay_file_id TEXT NOT NULL DEFAULT '',
                source_map_file_id TEXT NOT NULL DEFAULT '',
                text_hash TEXT NOT NULL DEFAULT '',
                text_anchors TEXT NOT NULL DEFAULT '[]',
                status TEXT NOT NULL DEFAULT 'completed',
                error_message TEXT NOT NULL DEFAULT '',
                completed_at TEXT NOT NULL DEFAULT '',
                position INTEGER NOT NULL DEFAULT 0,
                engine_version TEXT NOT NULL DEFAULT '',
                document_revision TEXT NOT NULL DEFAULT '',
                omr_file_id TEXT NOT NULL DEFAULT '',
                original_musicxml TEXT NOT NULL DEFAULT '',
                working_musicxml TEXT NOT NULL DEFAULT '',
                deleted_source_ids TEXT NOT NULL DEFAULT '[]'
            )
            """
        )
        conn.commit()

    dao = HistoryDao(db_path)

    with sqlite3.connect(db_path) as conn:
        version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        table_exists = bool(
            conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name = 'history_jianpu_snapshot'"
            ).fetchone()
        )

    assert version == 8
    assert table_exists

    batch = dao.create_batch([HistoryPage(input_file_name="a.png")])
    dao.push_snapshot(batch.id, "1=C\n1")
    assert len(dao.list_snapshots(batch.id)) == 1
