from __future__ import annotations

from pathlib import Path

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
