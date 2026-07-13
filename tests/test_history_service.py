import sqlite3

import pytest

from score_trans.dao.history.history_dao import HistoryDao
from score_trans.exec.history.actions import HistoryActions
from score_trans.models.history.entities import HistoryPage, HistoryRenderPageOcrText
from score_trans.models.history.schemas import PageUpdate
from score_trans.models.provenance.schemas import (
    SourceTextAttachment,
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


def test_page_patch_distinguishes_omitted_and_explicit_null(tmp_path) -> None:
    service = HistoryService(tmp_path / "history.db")
    actions = HistoryActions(service)
    batch = service.create_batch(
        [HistoryPage(input_file_name="score.png", start_measure_number=9)]
    )
    page_id = batch.pages[0].id

    preserved = actions.update_history_page(
        page_id,
        PageUpdate(jianpu_text="1=C\n4/4\n1 2 |"),
    )
    cleared = actions.update_history_page(
        page_id,
        PageUpdate(start_measure_number=None),
    )

    assert preserved.start_measure_number == 9
    assert cleared.start_measure_number is None


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
            HistoryPage(input_file_name="first.png", status="waiting"),
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
                input_file_name="b.png", input_file_id="input-2", status="waiting"
            ),
        ]
    )

    assert batch.status == "waiting"

    first, second = batch.pages
    service.update_page(first.id, status="completed")
    assert service.get_batch(batch.id).status == "waiting"

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
        jianpu_text="\n".join(
            f"// @page {index + 1} start=auto" for index in range(10)
        ),
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


def test_history_batch_migration_adds_empty_batch_jianpu_text(tmp_path) -> None:
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

    service = HistoryService(db_path)
    loaded = service.get_batch(1)

    assert loaded is not None
    assert loaded.jianpu_text == ""
    # Rendered SVG IDs are derived output from the removed renderer and are
    # deliberately invalidated by the v2 publication-engine migration.
    assert loaded.render_page_file_ids == []
    assert loaded.engine_version == ""
    assert db_path.with_suffix(".v0.bak").exists()
    assert loaded.render_page_ocr_texts == []


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


def test_legacy_history_rows_are_migrated_without_data_loss(tmp_path) -> None:
    db_path = tmp_path / "history.db"
    _create_legacy_history_db(db_path)

    first_load = HistoryDao(db_path).list_batches()
    second_load = HistoryDao(db_path).list_batches()

    assert [batch.id for batch in first_load] == [8, 3]
    assert [batch.id for batch in second_load] == [8, 3]
    completed = first_load[1]
    assert completed.created_at == "2025-01-02 03:04:05"
    assert completed.jianpu_text == "1=C\n4/4\n1 2 3 4 |"
    assert completed.status == "completed"
    assert len(completed.pages) == 1
    assert completed.pages[0].input_file_name == "first.png"
    assert completed.pages[0].input_file_id == "input-3"
    assert completed.pages[0].musicxml_file_id == "xml-3"
    assert completed.pages[0].jianpu_text == "1=C\n4/4\n1 2 3 4 |"
    assert completed.pages[0].svg_file_id == "svg-3"
    assert completed.pages[0].completed_at == "2025-01-02 03:04:05"

    failed = first_load[0]
    assert failed.status == "failed"
    assert failed.pages[0].status == "failed"
    assert failed.pages[0].error_message == "识别失败"
    assert failed.pages[0].completed_at == "2025-02-03 04:05:06"

    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "history" not in tables
        assert "history_legacy_backup" in tables
        assert (
            conn.execute("SELECT COUNT(*) FROM history_legacy_backup").fetchone()[0]
            == 2
        )


def test_legacy_history_migration_rolls_back_as_one_transaction(
    tmp_path, monkeypatch
) -> None:
    db_path = tmp_path / "history.db"
    _create_legacy_history_db(db_path)

    def fail_after_partial_insert(conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            INSERT INTO history_batch (id, page_count, status)
            VALUES (99, 1, 'completed')
            """
        )
        raise RuntimeError("injected migration failure")

    monkeypatch.setattr(
        HistoryDao,
        "_migrate_legacy_history_rows",
        staticmethod(fail_after_partial_insert),
        raising=False,
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


def test_measure_selection_failure_update_does_not_leave_processing_status(
    tmp_path,
) -> None:
    service = HistoryService(tmp_path / "history.db")
    batch = service.create_batch(
        [
            HistoryPage(
                input_file_name="score.png",
                input_file_id="input-1",
                status="processing",
                error_message="正在重新渲染",
            )
        ]
    )
    page = batch.pages[0]

    updated = service.update_page(
        page.id,
        start_measure_number=5,
        status="waiting",
        error_message="选择小节号失败：bad token",
    )

    assert updated is not None
    assert updated.status == "waiting"
    assert updated.start_measure_number == 5
    assert "bad token" in updated.error_message
    assert service.get_batch(batch.id).status == "waiting"


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

    updated = service.update_page(batch.pages[0].id, status="waiting")
    assert updated is not None
    assert updated.status == "waiting"
    assert updated.completed_at == ""


def test_completed_at_column_migrated_for_legacy_db(tmp_path) -> None:
    db_path = tmp_path / "history.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE history_batch (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL DEFAULT '',
                page_count INTEGER NOT NULL DEFAULT 1,
                render_page_file_ids TEXT NOT NULL DEFAULT '[]',
                render_page_ocr_texts TEXT NOT NULL DEFAULT '[]',
                jianpu_text TEXT NOT NULL DEFAULT '',
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
                task_id TEXT NOT NULL DEFAULT '',
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

    service = HistoryService(db_path)
    loaded = service.get_page(1)

    assert loaded is not None
    assert loaded.completed_at == ""
