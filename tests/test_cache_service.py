from __future__ import annotations

from pathlib import Path

from score_trans.dao.history.history_dao import HistoryDao
from score_trans.models.history.entities import HistoryPage
from score_trans.services.storage.cache_service import CacheService


def test_clear_cache_preserves_history_uploads(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    for name in ("audiveris", "pipeline", "ai_transcribe"):
        scratch_file = cache_dir / name / "scratch.txt"
        scratch_file.parent.mkdir(parents=True, exist_ok=True)
        scratch_file.write_text("scratch", encoding="utf-8")

    kept_file = cache_dir / "uploads" / "keep123" / "score.svg"
    removed_file = cache_dir / "uploads" / "drop456" / "score.svg"
    kept_file.parent.mkdir(parents=True, exist_ok=True)
    removed_file.parent.mkdir(parents=True, exist_ok=True)
    kept_file.write_text("kept", encoding="utf-8")
    removed_file.write_text("removed", encoding="utf-8")
    (cache_dir / "uploads" / "index.json").write_text("{}", encoding="utf-8")

    history = HistoryDao(tmp_path / "history.db")
    history.create_batch(
        [
            HistoryPage(
                input_file_name="score.png",
                input_file_id="keep123",
                musicxml_file_id="",
                jianpu_text="1 2 3 |",
                ocr_text="",
                svg_file_id="",
            )
        ]
    )

    result = CacheService(cache_dir=cache_dir, history=history).clear()

    assert kept_file.exists()
    assert not removed_file.exists()
    assert not (cache_dir / "audiveris").exists()
    assert not (cache_dir / "pipeline").exists()
    assert not (cache_dir / "ai_transcribe").exists()
    assert not (cache_dir / "uploads" / "index.json").exists()
    assert result.preserved_uploads == 1
    assert result.removed_items >= 4
    assert result.freed_bytes > 0
