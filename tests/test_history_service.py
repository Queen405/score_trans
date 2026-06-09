import sqlite3

from score_trans.models.history.entities import HistoryPage
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


def test_update_page_missing_returns_none(tmp_path) -> None:
    service = HistoryService(tmp_path / "history.db")

    assert service.update_page(404, jianpu_text="1 2 |") is None


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
