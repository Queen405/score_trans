from score_trans.services.history_service import HistoryPage, HistoryService


def test_update_page_replaces_jianpu_and_svg(tmp_path) -> None:
    service = HistoryService(tmp_path / "history.db")
    batch = service.create_batch([
        HistoryPage(
            input_file_name="score.png",
            input_file_id="input-1",
            musicxml_file_id="xml-1",
            jianpu_text="key=C\ntime=4/4\n1 2 |",
            svg_file_id="svg-old",
        )
    ])
    page_id = batch.pages[0].id

    updated = service.update_page(
        page_id,
        jianpu_text="key=C\ntime=4/4\n3 4 |",
        svg_file_id="svg-new",
    )

    assert updated is not None
    assert updated.jianpu_text == "key=C\ntime=4/4\n3 4 |"
    assert updated.svg_file_id == "svg-new"
    assert service.get_batch(batch.id).pages[0].jianpu_text == updated.jianpu_text


def test_update_page_missing_returns_none(tmp_path) -> None:
    service = HistoryService(tmp_path / "history.db")

    assert service.update_page(404, jianpu_text="1 2 |") is None
