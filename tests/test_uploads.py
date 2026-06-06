from __future__ import annotations

import json
from pathlib import Path

import score_trans.services.files.upload_service as upload_service_module
from score_trans.models.settings.config import ToolConfig
from score_trans.services.files.upload_service import UploadService


def test_upload_manager_persists_registered_mapping(tmp_path: Path) -> None:
    config = ToolConfig(work_dir=tmp_path)
    source = tmp_path / "sample.musicxml"
    source.write_text("<score-partwise/>", encoding="utf-8")

    manager1 = UploadService(config)
    file_id = manager1.register(source)
    first_path = manager1.get_path(file_id)

    assert first_path is not None
    assert first_path.exists()

    manager2 = UploadService(config)
    restored_path = manager2.get_path(file_id)

    assert restored_path is not None
    assert restored_path.exists()
    assert restored_path.read_text(encoding="utf-8") == "<score-partwise/>"


def test_upload_manager_restores_legacy_relative_index_paths(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(upload_service_module, "PROJECT_ROOT", tmp_path)
    uploads_dir = tmp_path / "work" / "uploads"
    file_dir = uploads_dir / "legacy123"
    file_dir.mkdir(parents=True)
    page = file_dir / "page.png"
    page.write_bytes(b"png")
    (uploads_dir / "index.json").write_text(
        json.dumps({"legacy123": "work/uploads/legacy123/page.png"}),
        encoding="utf-8",
    )

    manager = UploadService(ToolConfig(work_dir=Path("work")))
    restored_path = manager.get_path("legacy123")

    assert restored_path == page.resolve()
    assert restored_path.read_bytes() == b"png"
