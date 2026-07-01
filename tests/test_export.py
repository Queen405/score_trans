from __future__ import annotations

from score_trans.domain.jianpu import jianpu_to_musicxml
from score_trans.exec.export.actions import ExportActions
from score_trans.models.export.schemas import (
    ExportMusicXmlRequest,
    ExportMusicXmlTextRequest,
    ExportResponse,
)
from score_trans.services.export.export_service import ExportService
from score_trans.services.files.upload_service import UploadService


def test_export_service_writes_musicxml(tmp_path) -> None:
    xml_text = jianpu_to_musicxml("1=C\n4/4\n1 2 3 4 |")
    output_path = tmp_path / "out.musicxml"

    from score_trans.domain.musicxml import musicxml_to_score

    score = musicxml_to_score(xml_text)
    ExportService().export_musicxml(score, output_path, title="Test Score")

    assert output_path.exists()
    written = output_path.read_text(encoding="utf-8")
    assert '<?xml version="1.0"' in written
    assert "<score-partwise" in written
    assert "<work-title>Test Score</work-title>" in written


def test_export_musicxml_text_from_jianpu() -> None:
    actions = ExportActions(uploads=UploadService())
    req = ExportMusicXmlTextRequest(
        jianpu_text="title=测试\n1=G\n3/4\n1 2 3 |",
        filename="test.musicxml",
    )

    resp = actions.export_musicxml_text(req)

    assert isinstance(resp, ExportResponse)
    assert resp.filename == "test.musicxml"
    path = actions.uploads.get_path(resp.file_id)
    assert path is not None and path.exists()
    written = path.read_text(encoding="utf-8")
    assert "<work-title>测试</work-title>" in written
    assert "<fifths>1</fifths>" in written


def test_export_musicxml_from_file_id(tmp_path) -> None:
    uploads = UploadService()
    original = tmp_path / "original.musicxml"
    original.write_text(jianpu_to_musicxml("1=C\n4/4\n1 2 3 4 |"), encoding="utf-8")
    file_id = uploads.register(original)

    actions = ExportActions(uploads=uploads)
    req = ExportMusicXmlRequest(
        musicxml_file_id=file_id,
        target_key="D",
        filename="transposed.musicxml",
    )

    resp = actions.export_musicxml(req)

    assert resp.filename == "transposed.musicxml"
    path = uploads.get_path(resp.file_id)
    assert path is not None and path.exists()
    written = path.read_text(encoding="utf-8")
    assert "<fifths>2</fifths>" in written
