from score_trans.models.history.entities import HistoryPage
from score_trans.services.history.history_service import HistoryService


def test_update_page_replaces_jianpu_and_svg(tmp_path) -> None:
    service = HistoryService(tmp_path / "history.db")
    batch = service.create_batch([
        HistoryPage(
            input_file_name="score.png",
            input_file_id="input-1",
            musicxml_file_id="xml-1",
            jianpu_text="1=C\n4/4\n1 2 |",
            svg_file_id="svg-old",
        )
    ])
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
    batch = service.create_batch([
        HistoryPage(input_file_name="a.png", input_file_id="input-1", status="processing"),
        HistoryPage(input_file_name="b.png", input_file_id="input-2", status="waiting"),
    ])

    assert batch.status == "waiting"

    first, second = batch.pages
    service.update_page(first.id, status="completed")
    assert service.get_batch(batch.id).status == "waiting"

    service.update_page(second.id, status="completed")
    assert service.get_batch(batch.id).status == "completed"

    service.update_page(second.id, status="failed", error_message="bad input")
    assert service.get_batch(batch.id).status == "failed"
