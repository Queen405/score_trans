from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import score_trans.services.files.upload_service as upload_service_module
from fastapi import UploadFile
from score_trans.config.settings import UPLOAD_PDF_DPI
from score_trans.exec.files.actions import FileActions
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


def test_explicit_work_dir_skips_global_legacy_migration(
    tmp_path: Path, monkeypatch
) -> None:
    def fail_migration(_target: Path) -> None:
        raise AssertionError("custom work directories must not import global legacy files")

    monkeypatch.setattr(
        upload_service_module,
        "_migrate_legacy_uploads_once",
        fail_migration,
    )

    UploadService(ToolConfig(work_dir=tmp_path / "work"))


def test_default_legacy_migration_runs_once_per_target(
    tmp_path: Path, monkeypatch
) -> None:
    target = (tmp_path / "uploads").resolve()
    migrated: list[Path] = []
    monkeypatch.setattr(
        upload_service_module,
        "_migrate_legacy_uploads",
        lambda path: migrated.append(path),
    )

    upload_service_module._migrate_legacy_uploads_once(target)
    upload_service_module._migrate_legacy_uploads_once(target)

    assert migrated == [target]


def test_upload_manager_restores_legacy_relative_index_paths(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(upload_service_module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(upload_service_module, "USER_CACHE_ROOT", tmp_path)
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


def test_upload_manager_merges_index_across_instances(tmp_path: Path) -> None:
    config = ToolConfig(work_dir=tmp_path)
    source_a = tmp_path / "a.musicxml"
    source_b = tmp_path / "b.musicxml"
    source_a.write_text("<a/>", encoding="utf-8")
    source_b.write_text("<b/>", encoding="utf-8")

    manager1 = UploadService(config)
    manager2 = UploadService(config)

    file_id_a = manager1.register(source_a)
    file_id_b = manager2.register(source_b)

    index = json.loads(
        (tmp_path / "uploads" / "index.json").read_text(encoding="utf-8")
    )
    assert file_id_a in index
    assert file_id_b in index


def test_upload_manager_cleanup_removes_mapping_when_index_is_merged(
    tmp_path: Path,
) -> None:
    config = ToolConfig(work_dir=tmp_path)
    source_a = tmp_path / "a.musicxml"
    source_b = tmp_path / "b.musicxml"
    source_a.write_text("<a/>", encoding="utf-8")
    source_b.write_text("<b/>", encoding="utf-8")
    manager1 = UploadService(config)
    manager2 = UploadService(config)
    file_id_a = manager1.register(source_a)
    file_id_b = manager2.register(source_b)

    manager1.cleanup(file_id_a)

    index = json.loads(
        (tmp_path / "uploads" / "index.json").read_text(encoding="utf-8")
    )
    assert file_id_a not in index
    assert file_id_b in index


def test_upload_manager_reuses_index_cache_when_index_is_unchanged(
    tmp_path: Path, monkeypatch
) -> None:
    config = ToolConfig(work_dir=tmp_path)
    source = tmp_path / "a.musicxml"
    source.write_text("<a/>", encoding="utf-8")
    manager = UploadService(config)
    file_id = manager.register(source)
    real_loads = upload_service_module.json.loads
    calls = {"count": 0}

    def counting_loads(raw: str):
        calls["count"] += 1
        return real_loads(raw)

    monkeypatch.setattr(upload_service_module.json, "loads", counting_loads)

    restored = UploadService(config)

    assert restored.get_path(file_id) is not None
    assert calls["count"] == 0


def test_upload_manager_exists_many(tmp_path: Path) -> None:
    config = ToolConfig(work_dir=tmp_path)
    source = tmp_path / "a.musicxml"
    source.write_text("<a/>", encoding="utf-8")
    manager = UploadService(config)
    file_id = manager.register(source)

    assert manager.exists_many([file_id, "missing"]) == {
        file_id: True,
        "missing": False,
    }


def test_upload_pdf_still_returns_page_pngs(monkeypatch, tmp_path: Path) -> None:
    seen_dpi: list[int] = []

    class FakePixmap:
        def __init__(self, page_index: int) -> None:
            self.page_index = page_index

        def save(self, path: str) -> None:
            Path(path).write_bytes(f"png-{self.page_index}".encode("ascii"))

    class FakePage:
        def __init__(self, page_index: int) -> None:
            self.page_index = page_index

        def get_pixmap(self, *, dpi: int) -> FakePixmap:
            seen_dpi.append(dpi)
            return FakePixmap(self.page_index)

    class FakeDocument:
        def __len__(self) -> int:
            return 2

        def load_page(self, page_index: int) -> FakePage:
            return FakePage(page_index)

        def close(self) -> None:
            return None

    monkeypatch.setitem(
        sys.modules,
        "fitz",
        SimpleNamespace(open=lambda _path: FakeDocument()),
    )

    uploads = UploadService(ToolConfig(work_dir=tmp_path))
    actions = FileActions(uploads)
    upload = UploadFile(file=BytesIO(b"%PDF-1.4"), filename="score.pdf")

    response = actions.upload_file(upload)

    assert response.pages is not None
    assert [page.page_index for page in response.pages] == [0, 1]
    assert [page.filename for page in response.pages] == [
        "score_page_001.png",
        "score_page_002.png",
    ]
    assert seen_dpi == [UPLOAD_PDF_DPI, UPLOAD_PDF_DPI]
    for page in response.pages:
        path = uploads.get_path(page.file_id)
        assert path is not None
        assert path.suffix == ".png"
        assert path.exists()
