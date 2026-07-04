from __future__ import annotations

import json
from pathlib import Path

from score_trans.dao.history.history_dao import HistoryDao
from score_trans.models.history.entities import HistoryPage
from score_trans.services.storage.cache_service import CacheService


def test_clear_cache_preserves_every_history_file_reference(
    tmp_path: Path, monkeypatch
) -> None:
    cache_dir = tmp_path / "cache"
    for name in ("audiveris", "pipeline", "ai_transcribe"):
        scratch_file = cache_dir / name / "scratch.txt"
        scratch_file.parent.mkdir(parents=True, exist_ok=True)
        scratch_file.write_text("scratch", encoding="utf-8")

    referenced_ids = {
        "input-file",
        "musicxml-file",
        "svg-file",
        "overlay-svg-file",
        "overlay-file",
        "source-map-file",
        "render-page-1",
        "render-page-2",
    }
    kept_files: list[Path] = []
    index: dict[str, str] = {}
    for file_id in sorted(referenced_ids):
        kept_file = cache_dir / "uploads" / file_id / "artifact.bin"
        kept_file.parent.mkdir(parents=True, exist_ok=True)
        kept_file.write_text(file_id, encoding="utf-8")
        kept_files.append(kept_file)
        index[file_id] = str(kept_file.resolve())

    removed_file = cache_dir / "uploads" / "drop456" / "score.svg"
    removed_file.parent.mkdir(parents=True, exist_ok=True)
    removed_file.write_text("removed", encoding="utf-8")
    index["drop456"] = str(removed_file.resolve())
    (cache_dir / "uploads" / "index.json").write_text(
        json.dumps(index), encoding="utf-8"
    )

    history = HistoryDao(tmp_path / "history.db")
    history.create_batch(
        [
            HistoryPage(
                input_file_name="score.png",
                input_file_id="input-file",
                musicxml_file_id="musicxml-file",
                jianpu_text="1 2 3 |",
                ocr_text="",
                svg_file_id="svg-file",
                overlay_svg_file_id="overlay-svg-file",
                overlay_file_id="overlay-file",
                source_map_file_id="source-map-file",
            )
        ],
        render_page_file_ids=["render-page-1", "render-page-2"],
    )

    def fail_if_full_batches_are_loaded():
        raise AssertionError(
            "cache cleanup must not load full batches with N+1 page queries"
        )

    monkeypatch.setattr(history, "list_batches", fail_if_full_batches_are_loaded)

    result = CacheService(cache_dir=cache_dir, history=history).clear()

    assert all(path.exists() for path in kept_files)
    assert not removed_file.exists()
    assert not (cache_dir / "audiveris").exists()
    assert not (cache_dir / "pipeline").exists()
    assert not (cache_dir / "ai_transcribe").exists()
    persisted_index = json.loads(
        (cache_dir / "uploads" / "index.json").read_text(encoding="utf-8")
    )
    assert set(persisted_index) == referenced_ids
    assert result.preserved_uploads == len(referenced_ids)
    assert result.removed_items >= 4
    assert result.freed_bytes > 0


def test_history_dao_collects_all_referenced_file_ids(tmp_path: Path) -> None:
    history = HistoryDao(tmp_path / "history.db")
    history.create_batch(
        [
            HistoryPage(
                input_file_id="input-file",
                musicxml_file_id="musicxml-file",
                svg_file_id="svg-file",
                overlay_svg_file_id="overlay-svg-file",
                overlay_file_id="overlay-file",
                source_map_file_id="source-map-file",
            )
        ],
        render_page_file_ids=["render-page-1", "", "render-page-2"],
    )

    assert history.referenced_file_ids() == {
        "input-file",
        "musicxml-file",
        "svg-file",
        "overlay-svg-file",
        "overlay-file",
        "source-map-file",
        "render-page-1",
        "render-page-2",
    }
