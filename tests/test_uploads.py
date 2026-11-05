from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
import score_trans.services.files.upload_service as upload_service_module
from fastapi import UploadFile
from PIL import Image
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
        raise AssertionError(
            "custom work directories must not import global legacy files"
        )

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


def test_rotate_image_right_and_left_updates_pixels(tmp_path: Path) -> None:
    from PIL import Image

    config = ToolConfig(work_dir=tmp_path)
    source = tmp_path / "wide.png"
    image = Image.new("RGB", (4, 2), "white")
    image.putpixel((0, 0), (255, 0, 0))
    image.save(source)

    manager = UploadService(config)
    actions = FileActions(manager)
    file_id = manager.register(source)

    rotated_right = actions.rotate_file(file_id, "right")
    right_path = manager.get_path(rotated_right.file_id)
    assert right_path is not None
    with Image.open(right_path) as result:
        assert result.size == (2, 4)
        assert result.convert("RGB").getpixel((1, 0)) == (255, 0, 0)

    rotated_left = actions.rotate_file(file_id, "left")
    left_path = manager.get_path(rotated_left.file_id)
    assert left_path is not None
    with Image.open(left_path) as result:
        assert result.size == (2, 4)
        assert result.convert("RGB").getpixel((0, 3)) == (255, 0, 0)


def test_rotate_image_rejects_non_image_files(tmp_path: Path) -> None:
    config = ToolConfig(work_dir=tmp_path)
    source = tmp_path / "score.musicxml"
    source.write_text("<score-partwise/>", encoding="utf-8")

    manager = UploadService(config)
    actions = FileActions(manager)
    file_id = manager.register(source)

    with pytest.raises(ValueError, match="只有图片文件支持旋转"):
        actions.rotate_file(file_id, "right")


def test_pdf_page_preview_renders_requested_page_and_rotation(tmp_path: Path) -> None:
    fitz = pytest.importorskip("fitz")
    pdf_path = tmp_path / "score.pdf"
    with fitz.open() as doc:
        page = doc.new_page(width=200, height=400)
        page.draw_rect(fitz.Rect(20, 20, 180, 380))
        doc.save(pdf_path)
    uploads = UploadService(ToolConfig(work_dir=tmp_path / "work"))
    file_id = uploads.register(pdf_path)
    actions = FileActions(uploads)

    content, width, height = actions.render_pdf_page(
        file_id,
        page_index=0,
        target_width=600,
        rotation=90,
    )

    with Image.open(BytesIO(content)) as image:
        assert image.format == "PNG"
        assert (image.width, image.height) == (width, height)
    assert width == 600
    assert height == 300


def test_pdf_page_preview_enforces_pixel_budget_after_rounding(
    tmp_path: Path,
) -> None:
    fitz = pytest.importorskip("fitz")
    pdf_path = tmp_path / "score.pdf"
    with fitz.open() as doc:
        doc.new_page(width=595.32, height=841.92)
        doc.save(pdf_path)
    uploads = UploadService(ToolConfig(work_dir=tmp_path / "work"))
    file_id = uploads.register(pdf_path)

    _content, width, height = FileActions(uploads).render_pdf_page(
        file_id,
        page_index=0,
        target_width=16_000,
        rotation=90,
    )

    assert width * height <= 24_000_000


def test_pdf_page_preview_rejects_invalid_page_and_non_pdf(tmp_path: Path) -> None:
    fitz = pytest.importorskip("fitz")
    pdf_path = tmp_path / "score.pdf"
    with fitz.open() as doc:
        doc.new_page()
        doc.save(pdf_path)
    uploads = UploadService(ToolConfig(work_dir=tmp_path / "work"))
    pdf_id = uploads.register(pdf_path)
    png_path = tmp_path / "image.png"
    Image.new("RGB", (20, 20), "white").save(png_path)
    png_id = uploads.register(png_path)
    actions = FileActions(uploads)

    with pytest.raises(ValueError, match="页码超出范围"):
        actions.render_pdf_page(pdf_id, page_index=1, target_width=600, rotation=0)
    with pytest.raises(ValueError, match="仅 PDF"):
        actions.render_pdf_page(png_id, page_index=0, target_width=600, rotation=0)


@pytest.mark.parametrize(
    ("configured_dpi", "expected_dpi"),
    [(0, UPLOAD_PDF_DPI), (144, 144)],
)
def test_upload_pdf_uses_automatic_or_manual_dpi(
    monkeypatch, tmp_path: Path, configured_dpi: int, expected_dpi: int
) -> None:
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

    uploads = UploadService(
        ToolConfig(work_dir=tmp_path, pdf_upload_dpi=configured_dpi)
    )
    actions = FileActions(uploads)
    upload = UploadFile(file=BytesIO(b"%PDF-1.4"), filename="score.pdf")

    response = actions.upload_file(upload)

    assert response.pages is not None
    assert [page.page_index for page in response.pages] == [0, 1]
    assert [page.filename for page in response.pages] == [
        "score_page_001.png",
        "score_page_002.png",
    ]
    assert seen_dpi == [expected_dpi, expected_dpi]
    for page in response.pages:
        path = uploads.get_path(page.file_id)
        assert path is not None
        assert path.suffix == ".png"
        assert path.exists()


def test_upload_pdf_reports_a_user_facing_error_on_conversion_failure(
    monkeypatch, tmp_path: Path, caplog
) -> None:
    def fail_open(_path: str):
        raise RuntimeError("corrupt PDF")

    monkeypatch.setitem(sys.modules, "fitz", SimpleNamespace(open=fail_open))
    actions = FileActions(UploadService(ToolConfig(work_dir=tmp_path)))

    with pytest.raises(ValueError, match="PDF 页面转换失败"):
        actions._pdf_to_images(tmp_path / "broken.pdf")

    assert "PDF 页面转换失败" in caplog.text
