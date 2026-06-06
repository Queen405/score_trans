import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

from score_trans.api.app import create_app
from score_trans.api.export.routes import export_midi
from score_trans.exec.export.actions import ExportActions
from score_trans.models.settings.config import ToolConfig
from score_trans.services.files.upload_service import UploadService


def test_render_routes_are_registered() -> None:
    paths = set(create_app().openapi()["paths"])

    assert "/render/final-output" in paths
    assert "/render/preserving-layout" in paths
    assert "/export/pdf" in paths
    assert "/export/midi" in paths
    assert "/history/pages/{page_id}" in paths
    assert "/tasks/{task_id}" in paths
    assert "/tasks/{task_id}/stream" in paths


def test_jianpu_svg_request_accepts_page_image_for_ocr_overlay() -> None:
    schema = create_app().openapi()["components"]["schemas"]["RenderJianpuSvgRequest"]

    assert "page_image_file_id" in schema["properties"]


def test_musicxml_to_jianpu_request_accepts_page_image_for_ocr_text() -> None:
    schema = create_app().openapi()["components"]["schemas"]["MusicXmlToJianpuRequest"]

    assert "page_image_file_id" in schema["properties"]


def test_jianpu_text_svg_request_accepts_page_image_for_ocr_overlay() -> None:
    schema = create_app().openapi()["components"]["schemas"]["RenderJianpuTextSvgRequest"]

    assert "page_image_file_id" in schema["properties"]
    assert "ocr_text" in schema["properties"]
    assert "include_ocr_text" in schema["properties"]


def test_history_page_schema_persists_ocr_text() -> None:
    schemas = create_app().openapi()["components"]["schemas"]

    assert "ocr_text" in schemas["PageCreate"]["properties"]
    assert "ocr_text" in schemas["PageUpdate"]["properties"]
    assert "ocr_text" in schemas["PageResponse"]["properties"]


def test_tasks_stream_allows_vite_dev_origin() -> None:
    response = TestClient(create_app()).get(
        "/tasks/missing/stream",
        headers={"Origin": "http://localhost:5173"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


class FakeExportUseCase:
    def __init__(self) -> None:
        self.calls = []

    def execute(self, musicxml_file, output_file, **kwargs):
        self.calls.append((Path(musicxml_file), Path(output_file), kwargs))
        Path(output_file).write_bytes(b"exported")
        return Path(output_file)


def test_export_midi_route_writes_and_registers_downloadable_file(tmp_path) -> None:
    config = ToolConfig(work_dir=tmp_path / "work")
    uploads = UploadService(config)
    source = tmp_path / "score.musicxml"
    source.write_text("<score-partwise/>", encoding="utf-8")
    musicxml_id = uploads.register(source)
    fake_export = FakeExportUseCase()

    response = asyncio.run(
        export_midi(
            musicxml_file_id=musicxml_id,
            actions=ExportActions(uploads=uploads, exporter=fake_export),
        )
    )

    assert response.filename == "score.mid"
    assert uploads.get_path(response.file_id).read_bytes() == b"exported"
