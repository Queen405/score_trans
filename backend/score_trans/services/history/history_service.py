from __future__ import annotations

from pathlib import Path

from ...dao.history.history_dao import HistoryDao
from ...models.history.entities import HistoryBatch, HistoryPage


class HistoryService:
    def __init__(self, db_path: str | Path | None = None, dao: HistoryDao | None = None) -> None:
        self.dao = dao or HistoryDao(db_path)

    def list_batches(self) -> list[HistoryBatch]:
        return self.dao.list_batches()

    def get_batch(self, batch_id: int) -> HistoryBatch | None:
        return self.dao.get_batch(batch_id)

    def create_batch(self, pages: list[HistoryPage]) -> HistoryBatch:
        return self.dao.create_batch(pages)

    def update_page(
        self,
        page_id: int,
        *,
        jianpu_text: str | None = None,
        ocr_text: str | None = None,
        svg_file_id: str | None = None,
        musicxml_file_id: str | None = None,
        start_measure_number: int | None = None,
        status: str | None = None,
        error_message: str | None = None,
    ) -> HistoryPage | None:
        return self.dao.update_page(
            page_id,
            jianpu_text=jianpu_text,
            ocr_text=ocr_text,
            svg_file_id=svg_file_id,
            musicxml_file_id=musicxml_file_id,
            start_measure_number=start_measure_number,
            status=status,
            error_message=error_message,
        )

    def delete_batch(self, batch_id: int) -> bool:
        return self.dao.delete_batch(batch_id)

    def delete_all(self) -> int:
        return self.dao.delete_all()

