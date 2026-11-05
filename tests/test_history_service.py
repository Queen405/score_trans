import sqlite3

import pytest
from score_trans.dao.history.history_dao import HistoryDao
from score_trans.exec.history.actions import HistoryActions
from score_trans.models.history.entities import HistoryPage, HistoryRenderPageOcrText
from score_trans.models.provenance.schemas import (
    SourceTextAttachment,
    TextAnchor,
    TextPlacementAnchor,
)
from score_trans.services.history.history_service import HistoryService


def _create_legacy_history_db(db_path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                input_file_name TEXT NOT NULL DEFAULT '',
                input_file_id TEXT NOT NULL DEFAULT '',
                musicxml_file_id TEXT NOT NULL DEFAULT '',
                jianpu_text TEXT NOT NULL DEFAULT '',
                svg_file_id TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'completed',
                error_message TEXT NOT NULL DEFAULT ''
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO history (
                id, created_at, input_file_name, input_file_id,
                musicxml_file_id, jianpu_text, svg_file_id, status, error_message
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    3,
                    "2025-01-02 03:04:05",
                    "first.png",
                    "input-3",
                    "xml-3",
                    "1=C\n4/4\n1 2 3 4 |",
                    "svg-3",
                    "completed",
                    "",
                ),
                (
                    8,
                    "2025-02-03 04:05:06",
                    "failed.png",
                    "input-8",
                    "",
                    "",
                    "",
                    "failed",
                    "识别失败",
                ),
            ],
        )


def test_list_batches_loads_pages_with_constant_query_count(tmp_path) -> None:
    class TracingHistoryDao(HistoryDao):
        def __init__(self, db_path) -> None:
            self.statements: list[str] = []
            super().__init__(db_path)

        def _connect(self) -> sqlite3.Connection:
            conn = super()._connect()
            conn.set_trace_callback(self.statements.append)
            return conn

    dao = TracingHistoryDao(tmp_path / "history.db")
    for index in range(3):
        dao.create_batch(
            [
                HistoryPage(input_file_name=f"{index}-a.png"),
                HistoryPage(input_file_name=f"{index}-b.png"),
            ]
        )

    dao.statements.clear()
    batches = dao.list_batches()
    select_statements = [
        statement
        for statement in dao.statements
        if statement.lstrip().upper().startswith("SELECT")
    ]

    assert len(batches) == 3
    assert all(len(batch.pages) == 2 for batch in batches)
    assert len(select_statements) == 2


def test_pdf_source_document_metadata_is_preserved(tmp_path) -> None:
    service = HistoryService(tmp_path / "history.db")
    batch = service.create_batch(
        [
            HistoryPage(
                input_file_name="score_page_002.png",
                input_file_id="page-png",
                source_document_file_id="source-pdf",
                source_document_name="score.pdf",
                source_page_index=1,
                source_rotation=90,
            )
        ]
    )

    restored = service.get_batch(batch.id).pages[0]
    assert restored.input_file_id == "page-png"
    assert restored.source_document_file_id == "source-pdf"
    assert restored.source_document_name == "score.pdf"
    assert restored.source_page_index == 1
    assert restored.source_rotation == 90


def test_update_page_replaces_jianpu_and_svg(tmp_path) -> None:
    service = HistoryService(tmp_path / "history.db")
    batch = service.create_batch(
        [
            HistoryPage(
                input_file_name="score.png",
                input_file_id="input-1",
                musicxml_file_id="xml-1",
                jianpu_text="1=C\n4/4\n1 2 |",
                svg_file_id="svg-old",
                omr_file_id="omr-1",
                original_musicxml="<score-partwise/>",
                working_musicxml="<score-partwise/>",
                deleted_source_ids=["s1:i9"],
            )
        ]
    )
    page_id = batch.pages[0].id

    updated = service.update_page(
        page_id,
        jianpu_text="1=C\n4/4\n3 4 |",
        ocr_text='[{"text":"词","bbox":[1,2,3,4],"role":"lyric"}]',
        text_attachments=[
            SourceTextAttachment(
                id="ocr-1",
                text="词",
                role="lyric",
                anchor=TextPlacementAnchor(
                    kind="source_element",
                    source_id="s1:i9",
                ),
            )
        ],
        svg_file_id="svg-new",
        working_musicxml="<score-partwise version='4.0'/>",
        deleted_source_ids=["s1:i9", "s1:i10"],
    )

    assert updated is not None
    assert updated.jianpu_text == "1=C\n4/4\n3 4 |"
    assert updated.ocr_text == '[{"text":"词","bbox":[1,2,3,4],"role":"lyric"}]'
    assert updated.text_attachments[0].anchor.source_id == "s1:i9"
    assert updated.svg_file_id == "svg-new"
    assert updated.omr_file_id == "omr-1"
    assert updated.original_musicxml == "<score-partwise/>"
    assert updated.working_musicxml == "<score-partwise version='4.0'/>"
    assert updated.deleted_source_ids == ["s1:i9", "s1:i10"]
    assert service.get_batch(batch.id).pages[0].jianpu_text == updated.jianpu_text
    assert service.get_batch(batch.id).pages[0].ocr_text == updated.ocr_text
    assert service.get_batch(batch.id).pages[0].text_attachments == (
        updated.text_attachments
    )
    assert service.get_batch(batch.id).pages[0].deleted_source_ids == (
        updated.deleted_source_ids
    )


def test_update_page_persists_empty_deleted_source_ids(tmp_path) -> None:
    """B 方案：恢复全部后 deleted_source_ids=[] 必须能持久化并往返还原。"""
    service = HistoryService(tmp_path / "history.db")
    batch = service.create_batch(
        [
            HistoryPage(
                input_file_name="score.png",
                input_file_id="input-1",
                musicxml_file_id="xml-1",
                jianpu_text="1=C\n4/4\n1 2 |",
                svg_file_id="svg-old",
                omr_file_id="omr-1",
                original_musicxml="<score-partwise/>",
                working_musicxml="<score-partwise/>",
                deleted_source_ids=["s1:i9"],
            )
        ]
    )
    page_id = batch.pages[0].id

    updated = service.update_page(page_id, deleted_source_ids=[])

    assert updated is not None
    assert updated.deleted_source_ids == []
    assert service.get_batch(batch.id).pages[0].deleted_source_ids == []


def test_text_anchor_baseline_roundtrips_and_survives_page_reorder(tmp_path) -> None:
    service = HistoryService(tmp_path / "history.db")
    baseline = [
        TextAnchor(
            source_id="s1:i1",
            start_utf16=0,
            end_utf16=1,
            role="note",
        )
    ]
    batch = service.create_batch(
        [
            HistoryPage(
                input_file_name="a.png",
                jianpu_text="edited-a",
                text_anchor_baseline_text="baseline-a",
                text_anchor_baseline_anchors=baseline,
            ),
            HistoryPage(
                input_file_name="b.png",
                jianpu_text="edited-b",
                text_anchor_baseline_text="baseline-b",
                text_anchor_baseline_anchors=baseline,
            ),
        ],
        jianpu_text="// @page 1\nedited-a\n// @page 2\nedited-b",
    )

    updated = service.update_page(
        batch.pages[0].id,
        text_anchor_baseline_text="new-baseline-a",
        text_anchor_baseline_anchors=baseline,
    )
    assert updated is not None
    assert updated.text_anchor_baseline_text == "new-baseline-a"

    reordered = service.reorder_pages(
        batch.id,
        "// @page 1\nreordered-b\n// @page 2\nreordered-a",
        [
            (batch.pages[1].id, "reordered-b"),
            (batch.pages[0].id, "reordered-a"),
        ],
    )

    assert reordered is not None
    assert [page.text_anchor_baseline_text for page in reordered.pages] == [
        "baseline-b",
        "new-baseline-a",
    ]
    assert [page.jianpu_text for page in reordered.pages] == [
        "reordered-b",
        "reordered-a",
    ]


def test_new_history_schema_omits_start_measure_number(tmp_path) -> None:
    db_path = tmp_path / "history.db"
    service = HistoryService(db_path)
    service.create_batch([HistoryPage(input_file_name="score.png")])

    with sqlite3.connect(db_path) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(history_page)")}
        version = conn.execute("PRAGMA user_version").fetchone()[0]

    assert "start_measure_number" not in columns
    assert version == 12


def test_history_render_pages_use_current_publication_engine_version(tmp_path) -> None:
    service = HistoryService(tmp_path / "history.db")
    batch = service.create_batch(
        [HistoryPage(input_file_name="score.png", svg_file_id="svg-1")],
        render_page_file_ids=["svg-1"],
        render_output_stale=True,
    )

    assert batch.engine_version == "publication-29"
    assert batch.pages[0].engine_version == "publication-29"
    assert batch.render_output_stale is True


def test_history_render_pages_persist_layout_key(tmp_path) -> None:
    service = HistoryService(tmp_path / "history.db")
    batch = service.create_batch(
        [HistoryPage(input_file_name="score.png", svg_file_id="svg-1")],
        render_page_file_ids=["svg-1"],
        render_layout_key="67:92:90",
    )

    assert batch.render_layout_key == "67:92:90"

    updated = service.update_batch_render_pages(
        batch.id,
        ["svg-2"],
        render_layout_key="75:88:85",
    )
    assert updated is not None
    assert updated.render_layout_key == "75:88:85"


def test_history_render_pages_clear_ocr_stale_only_after_new_svg_ids(tmp_path) -> None:
    service = HistoryService(tmp_path / "history.db")
    batch = service.create_batch(
        [HistoryPage(input_file_name="score.png", svg_file_id="svg-old")],
        render_page_file_ids=["svg-old"],
        render_output_stale=True,
    )

    saved = service.update_batch_render_page_ocr_texts(
        batch.id,
        [HistoryRenderPageOcrText(page_index=0, ocr_text="updated")],
    )
    assert saved is not None
    assert saved.render_output_stale is True

    rendered = service.update_batch_render_pages(batch.id, ["svg-new"])
    assert rendered is not None
    assert rendered.render_output_stale is False


def test_history_rejects_sqlite_older_than_335(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(sqlite3, "sqlite_version_info", (3, 34, 1))
    monkeypatch.setattr(sqlite3, "sqlite_version", "3.34.1")

    with pytest.raises(RuntimeError, match=r"SQLite 3\.35\.0 or newer"):
        HistoryDao(tmp_path / "history.db")


def test_history_page_update_preserves_unmodified_fields(tmp_path) -> None:
    service = HistoryService(tmp_path / "history.db")
    batch = service.create_batch([HistoryPage(input_file_name="score.png")])
    page_id = batch.pages[0].id

    updated = service.update_page(page_id, jianpu_text="1=C\n4/4\n1 2 |")

    assert updated is not None
    assert updated.input_file_name == "score.png"
    assert updated.jianpu_text == "1=C\n4/4\n1 2 |"


def test_history_page_persists_background_task_id(tmp_path) -> None:
    service = HistoryService(tmp_path / "history.db")
    batch = service.create_batch(
        [
            HistoryPage(
                input_file_name="score.png",
                input_file_id="input-1",
                task_id="task-running",
                status="processing",
            )
        ]
    )

    assert batch.pages[0].task_id == "task-running"

    updated = service.update_page(batch.pages[0].id, task_id="")

    assert updated is not None
    assert updated.task_id == ""


def test_update_page_missing_returns_none(tmp_path) -> None:
    service = HistoryService(tmp_path / "history.db")

    assert service.update_page(404, jianpu_text="1 2 |") is None


def test_get_history_page_returns_single_page(tmp_path) -> None:
    service = HistoryService(tmp_path / "history.db")
    batch = service.create_batch(
        [
            HistoryPage(input_file_name="first.png", status="processing"),
            HistoryPage(input_file_name="second.png", status="completed"),
        ]
    )

    page = service.get_page(batch.pages[1].id)

    assert page is not None
    assert page.input_file_name == "second.png"
    assert page.batch_id == batch.id
    assert service.get_page(404) is None


def test_batch_status_tracks_background_pages(tmp_path) -> None:
    service = HistoryService(tmp_path / "history.db")
    batch = service.create_batch(
        [
            HistoryPage(
                input_file_name="a.png", input_file_id="input-1", status="processing"
            ),
            HistoryPage(
                input_file_name="b.png", input_file_id="input-2", status="pending"
            ),
        ]
    )

    assert batch.status == "processing"

    first, second = batch.pages
    service.update_page(first.id, status="completed")
    assert service.get_batch(batch.id).status == "processing"

    service.update_page(second.id, status="completed")
    assert service.get_batch(batch.id).status == "completed"

    service.update_page(second.id, status="failed", error_message="bad input")
    assert service.get_batch(batch.id).status == "failed"


def test_partial_recognition_persists_all_pages_and_reuses_rows(tmp_path) -> None:
    service = HistoryService(tmp_path / "history.db")
    selected_indexes = {1, 6}
    batch = service.create_batch(
        [
            HistoryPage(
                input_file_name=f"page-{index + 1}.png",
                input_file_id=f"input-{index + 1}",
                status="processing" if index in selected_indexes else "unrecognized",
            )
            for index in range(10)
        ],
        jianpu_text="\n".join(f"// @page {index + 1}" for index in range(10)),
    )

    assert batch.page_count == 10
    assert batch.status == "processing"
    assert [page.input_file_id for page in batch.pages] == [
        f"input-{index + 1}" for index in range(10)
    ]
    assert [page.status for page in batch.pages] == [
        "processing" if index in selected_indexes else "unrecognized"
        for index in range(10)
    ]

    original_page_ids = [page.id for page in batch.pages]
    for index in selected_indexes:
        updated = service.update_page(batch.pages[index].id, status="completed")
        assert updated is not None

    completed_batch = service.get_batch(batch.id)
    assert completed_batch is not None
    assert completed_batch.status == "completed"
    assert completed_batch.page_count == 10

    fifth_page_id = completed_batch.pages[4].id
    processing = service.update_page(fifth_page_id, status="processing")
    assert processing is not None
    assert processing.id == fifth_page_id
    assert service.get_batch(batch.id).status == "processing"

    completed = service.update_page(fifth_page_id, status="completed")
    assert completed is not None
    reloaded = service.get_batch(batch.id)
    assert reloaded is not None
    assert reloaded.status == "completed"
    assert reloaded.page_count == 10
    assert [page.id for page in reloaded.pages] == original_page_ids


def test_batch_render_page_file_ids_are_saved_and_updated(tmp_path) -> None:
    service = HistoryService(tmp_path / "history.db")
    batch = service.create_batch(
        [HistoryPage(input_file_name="score.png", svg_file_id="legacy-svg")],
        render_page_file_ids=["a4-1", "a4-2"],
    )

    assert service.get_batch(batch.id).render_page_file_ids == ["a4-1", "a4-2"]

    updated = service.update_batch_render_pages(batch.id, ["a4-new"])

    assert updated is not None
    assert updated.render_page_file_ids == ["a4-new"]


def test_batch_render_page_ocr_texts_are_saved_and_updated(tmp_path) -> None:
    service = HistoryService(tmp_path / "history.db")
    batch = service.create_batch(
        [HistoryPage(input_file_name="score.png", svg_file_id="legacy-svg")],
        render_page_ocr_texts=[
            HistoryRenderPageOcrText(page_index=0, ocr_text='[{"text":"第一页"}]'),
        ],
    )

    loaded = service.get_batch(batch.id)
    assert loaded is not None
    assert loaded.render_page_ocr_texts[0].ocr_text == '[{"text":"第一页"}]'

    updated = service.update_batch_render_page_ocr_texts(
        batch.id,
        [
            HistoryRenderPageOcrText(page_index=0, ocr_text='[{"text":"改后"}]'),
            HistoryRenderPageOcrText(page_index=1, ocr_text='[{"text":"第二页"}]'),
        ],
    )

    assert updated is not None
    assert [item.page_index for item in updated.render_page_ocr_texts] == [0, 1]
    assert updated.render_page_ocr_texts[0].ocr_text == '[{"text":"改后"}]'


def test_batch_jianpu_text_is_saved_and_updated_without_overwriting_pages(
    tmp_path,
) -> None:
    service = HistoryService(tmp_path / "history.db")
    batch = service.create_batch(
        [
            HistoryPage(input_file_name="a.png", jianpu_text="1=C\n4/4\n1 2 |"),
            HistoryPage(input_file_name="b.png", jianpu_text="1=C\n4/4\n3 4 |"),
        ],
        jianpu_text="1=C\n4/4\n1 2 |\n\n3 4 |",
    )

    assert service.get_batch(batch.id).jianpu_text == "1=C\n4/4\n1 2 |\n\n3 4 |"

    updated = service.update_batch_jianpu_text(batch.id, "1=C\n4/4\n5 6 |")

    assert updated is not None
    assert updated.jianpu_text == "1=C\n4/4\n5 6 |"
    loaded = service.get_batch(batch.id)
    assert loaded is not None
    assert [page.jianpu_text for page in loaded.pages] == [
        "1=C\n4/4\n1 2 |",
        "1=C\n4/4\n3 4 |",
    ]


def test_old_history_batch_falls_back_to_page_svg_ids(tmp_path) -> None:
    service = HistoryService(tmp_path / "history.db")
    batch = service.create_batch(
        [
            HistoryPage(input_file_name="a.png", svg_file_id="svg-a"),
            HistoryPage(input_file_name="b.png", svg_file_id="svg-b"),
        ]
    )

    loaded = service.get_batch(batch.id)

    assert loaded is not None
    assert loaded.render_page_file_ids == []


def test_v4_migration_backs_up_and_clears_history(tmp_path) -> None:
    db_path = tmp_path / "history.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE history_batch (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL DEFAULT '',
                page_count INTEGER NOT NULL DEFAULT 1,
                render_page_file_ids TEXT NOT NULL DEFAULT '["a4-old"]',
                status TEXT NOT NULL DEFAULT 'completed'
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE history_page (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id INTEGER NOT NULL,
                input_file_name TEXT NOT NULL DEFAULT '',
                input_file_id TEXT NOT NULL DEFAULT '',
                musicxml_file_id TEXT NOT NULL DEFAULT '',
                jianpu_text TEXT NOT NULL DEFAULT '',
                ocr_text TEXT NOT NULL DEFAULT '',
                svg_file_id TEXT NOT NULL DEFAULT '',
                start_measure_number INTEGER,
                status TEXT NOT NULL DEFAULT 'completed',
                error_message TEXT NOT NULL DEFAULT ''
            )
            """
        )
        conn.execute("INSERT INTO history_batch DEFAULT VALUES")
        conn.execute(
            "INSERT INTO history_page (batch_id, input_file_name) VALUES (1, 'z.png')"
        )
        conn.execute("PRAGMA user_version = 4")

    service = HistoryService(db_path)
    assert service.list_batches() == []

    backup_path = db_path.with_suffix(".v4.bak")
    assert backup_path.exists()
    with sqlite3.connect(db_path) as conn:
        page_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(history_page)")
        }
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 12
        assert conn.execute("SELECT COUNT(*) FROM history_batch").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM history_page").fetchone()[0] == 0
        assert "start_measure_number" not in page_columns
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM sqlite_sequence "
                "WHERE name IN ('history_batch', 'history_page')"
            ).fetchone()[0]
            == 0
        )
    with sqlite3.connect(backup_path) as conn:
        backup_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(history_page)")
        }
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 4
        assert conn.execute("SELECT COUNT(*) FROM history_batch").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM history_page").fetchone()[0] == 1
        assert "start_measure_number" in backup_columns


def test_v5_migration_adds_ocr_stale_without_clearing_history(tmp_path) -> None:
    db_path = tmp_path / "history.db"
    initial = HistoryService(db_path)
    created = initial.create_batch(
        [HistoryPage(input_file_name="kept.png", svg_file_id="svg-kept")],
        render_page_file_ids=["svg-kept"],
    )
    with sqlite3.connect(db_path) as conn:
        conn.execute("ALTER TABLE history_batch DROP COLUMN render_output_stale")
        conn.execute("PRAGMA user_version = 5")

    migrated = HistoryService(db_path)
    loaded = migrated.get_batch(created.id)

    assert loaded is not None
    assert loaded.pages[0].input_file_name == "kept.png"
    assert loaded.render_page_file_ids == ["svg-kept"]
    assert loaded.render_output_stale is False
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 12


def test_schema_migration_rolls_back_all_alter_steps(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "history.db"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE history_batch (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL DEFAULT '',
                page_count INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'completed'
            );
            CREATE TABLE history_page (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id INTEGER NOT NULL,
                input_file_name TEXT NOT NULL DEFAULT '',
                input_file_id TEXT NOT NULL DEFAULT '',
                musicxml_file_id TEXT NOT NULL DEFAULT '',
                jianpu_text TEXT NOT NULL DEFAULT '',
                svg_file_id TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'completed',
                error_message TEXT NOT NULL DEFAULT ''
            );
            """
        )
        original_page_columns = [
            row[1] for row in conn.execute("PRAGMA table_info(history_page)")
        ]
        original_batch_columns = [
            row[1] for row in conn.execute("PRAGMA table_info(history_batch)")
        ]

    def fail_before_index_creation(conn: sqlite3.Connection) -> None:
        raise RuntimeError("injected schema migration failure")

    monkeypatch.setattr(
        HistoryDao,
        "_ensure_indexes",
        staticmethod(fail_before_index_creation),
    )

    with pytest.raises(RuntimeError, match="injected schema migration failure"):
        HistoryDao(db_path)

    with sqlite3.connect(db_path) as conn:
        assert [
            row[1] for row in conn.execute("PRAGMA table_info(history_page)")
        ] == original_page_columns
        assert [
            row[1] for row in conn.execute("PRAGMA table_info(history_batch)")
        ] == original_batch_columns
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 0


def test_legacy_history_rows_are_discarded_after_backup(tmp_path) -> None:
    db_path = tmp_path / "history.db"
    _create_legacy_history_db(db_path)

    assert HistoryDao(db_path).list_batches() == []
    assert HistoryDao(db_path).list_batches() == []

    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "history" not in tables
        assert "history_legacy_backup" not in tables
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 12
    with sqlite3.connect(db_path.with_suffix(".v0.bak")) as conn:
        assert conn.execute("SELECT COUNT(*) FROM history").fetchone()[0] == 2


def test_legacy_history_cleanup_rolls_back_as_one_transaction(
    tmp_path, monkeypatch
) -> None:
    db_path = tmp_path / "history.db"
    _create_legacy_history_db(db_path)

    def fail_during_cleanup(conn: sqlite3.Connection) -> None:
        conn.execute("DROP TABLE history")
        raise RuntimeError("injected migration failure")

    monkeypatch.setattr(
        HistoryDao,
        "_drop_legacy_history_tables",
        staticmethod(fail_during_cleanup),
    )

    with pytest.raises(RuntimeError, match="injected migration failure"):
        HistoryDao(db_path)

    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "history" in tables
        assert "history_batch" not in tables
        assert conn.execute("SELECT COUNT(*) FROM history").fetchone()[0] == 2


def test_history_batch_pages_keep_source_order_by_id(tmp_path) -> None:
    service = HistoryService(tmp_path / "history.db")
    batch = service.create_batch(
        [
            HistoryPage(input_file_name="z-first.png", input_file_id="first"),
            HistoryPage(input_file_name="a-second.png", input_file_id="second"),
        ]
    )

    loaded = service.get_batch(batch.id)
    summaries = service.list_batch_summaries()

    assert loaded is not None
    assert [page.input_file_id for page in loaded.pages] == ["first", "second"]
    assert summaries[0].first_file_name == "z-first.png"


def test_unknown_page_status_marks_batch_failed(tmp_path) -> None:
    service = HistoryService(tmp_path / "history.db")
    batch = service.create_batch(
        [
            HistoryPage(
                input_file_name="score.png",
                input_file_id="input-1",
                status="stale-status",
            )
        ]
    )

    assert batch.status == "failed"


def test_list_batch_summaries_do_not_load_page_payloads(tmp_path) -> None:
    service = HistoryService(tmp_path / "history.db")
    large_text = "1=C\n4/4\n" + ("1 2 3 4 |\n" * 1000)
    batch = service.create_batch(
        [
            HistoryPage(
                input_file_name="first.png",
                input_file_id="input-1",
                jianpu_text=large_text,
                ocr_text="ocr" * 1000,
            ),
            HistoryPage(input_file_name="second.png", input_file_id="input-2"),
        ]
    )

    summaries = service.list_batch_summaries()

    assert summaries[0].id == batch.id
    assert summaries[0].first_file_name == "first.png"
    assert summaries[0].page_count == 2
    assert not hasattr(summaries[0], "pages")
    assert not hasattr(summaries[0], "jianpu_text")


def test_list_batch_summaries_return_latest_page_completion_time(tmp_path) -> None:
    db_path = tmp_path / "history.db"
    service = HistoryService(db_path)
    batch = service.create_batch(
        [
            HistoryPage(input_file_name="first.png", status="processing"),
            HistoryPage(input_file_name="second.png", status="processing"),
        ]
    )
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE history_page SET completed_at = ? WHERE id = ?",
            ("2026-06-30 10:00:00", batch.pages[0].id),
        )
        conn.execute(
            "UPDATE history_page SET completed_at = ? WHERE id = ?",
            ("2026-06-30 10:05:00", batch.pages[1].id),
        )
        conn.commit()

    summaries = service.list_batch_summaries()

    assert summaries[0].last_completed_at == "2026-06-30 10:05:00"


def test_list_batch_summaries_leave_completion_time_empty_without_terminal_page(
    tmp_path,
) -> None:
    service = HistoryService(tmp_path / "history.db")
    service.create_batch(
        [HistoryPage(input_file_name="score.png", status="processing")]
    )

    summaries = service.list_batch_summaries()

    assert summaries[0].last_completed_at == ""


def test_history_page_batch_index_is_created(tmp_path) -> None:
    db_path = tmp_path / "history.db"
    HistoryService(db_path)

    with sqlite3.connect(db_path) as conn:
        indexes = {
            row[1] for row in conn.execute("PRAGMA index_list(history_page)").fetchall()
        }

    assert "idx_history_page_batch_id_id" in indexes


def test_update_page_records_completed_at_when_status_reaches_terminal(
    tmp_path,
) -> None:
    service = HistoryService(tmp_path / "history.db")
    batch = service.create_batch(
        [HistoryPage(input_file_name="score.png", status="processing")]
    )
    page = batch.pages[0]
    assert page.completed_at == ""

    updated = service.update_page(page.id, status="completed")
    assert updated is not None
    assert updated.completed_at != ""
    first_completed_at = updated.completed_at

    reloaded = service.get_page(page.id)
    assert reloaded is not None
    assert reloaded.completed_at == first_completed_at

    updated_again = service.update_page(page.id, jianpu_text="1=C\n")
    assert updated_again is not None
    assert updated_again.completed_at == first_completed_at


def test_update_page_records_completed_at_for_failed_status(tmp_path) -> None:
    service = HistoryService(tmp_path / "history.db")
    batch = service.create_batch(
        [HistoryPage(input_file_name="score.png", status="processing")]
    )

    updated = service.update_page(
        batch.pages[0].id, status="failed", error_message="bad"
    )
    assert updated is not None
    assert updated.completed_at != ""


def test_update_page_does_not_record_completed_at_for_non_terminal_status(
    tmp_path,
) -> None:
    service = HistoryService(tmp_path / "history.db")
    batch = service.create_batch(
        [HistoryPage(input_file_name="score.png", status="processing")]
    )

    updated = service.update_page(batch.pages[0].id, status="processing")
    assert updated is not None
    assert updated.status == "processing"
    assert updated.completed_at == ""


def test_history_detail_can_omit_musicxml_until_marker_editing(tmp_path) -> None:
    service = HistoryService(tmp_path / "history.db")
    batch = service.create_batch(
        [
            HistoryPage(
                input_file_name="page.png",
                original_musicxml="original-xml",
                working_musicxml="working-xml",
            )
        ]
    )
    actions = HistoryActions(service)

    slim = actions.get_history(batch.id, include_musicxml=False)
    full = actions.get_history(batch.id)

    assert slim.pages[0].original_musicxml == ""
    assert slim.pages[0].working_musicxml == ""
    assert full.pages[0].original_musicxml == "original-xml"
    assert full.pages[0].working_musicxml == "working-xml"
    assert actions.get_history_page(batch.pages[0].id).working_musicxml == "working-xml"
