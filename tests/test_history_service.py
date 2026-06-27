import sqlite3

from score_trans.models.history.entities import HistoryPage, HistoryRenderPageOcrText
from score_trans.services.history.history_service import HistoryService


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
            )
        ]
    )
    page_id = batch.pages[0].id

    updated = service.update_page(
        page_id,
        jianpu_text="1=C\n4/4\n3 4 |",
        ocr_text='[{"text":"词","bbox":[1,2,3,4],"role":"lyric"}]',
        svg_file_id="svg-new",
    )

    assert updated is not None
    assert updated.jianpu_text == "1=C\n4/4\n3 4 |"
    assert updated.ocr_text == '[{"text":"词","bbox":[1,2,3,4],"role":"lyric"}]'
    assert updated.svg_file_id == "svg-new"
    assert service.get_batch(batch.id).pages[0].jianpu_text == updated.jianpu_text
    assert service.get_batch(batch.id).pages[0].ocr_text == updated.ocr_text


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


def test_batch_jianpu_text_is_saved_and_updated_without_overwriting_pages(tmp_path) -> None:
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
    assert loaded.render_page_file_ids == ["a4-old"]
    assert loaded.render_page_ocr_texts == []


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


def test_measure_selection_failure_update_does_not_leave_processing_status(tmp_path) -> None:
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


def test_history_page_batch_index_is_created(tmp_path) -> None:
    db_path = tmp_path / "history.db"
    HistoryService(db_path)

    with sqlite3.connect(db_path) as conn:
        indexes = {
            row[1] for row in conn.execute("PRAGMA index_list(history_page)").fetchall()
        }

    assert "idx_history_page_batch_id_id" in indexes
