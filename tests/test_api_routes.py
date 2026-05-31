import asyncio
from pathlib import Path

from score_trans.api.app import create_app
from score_trans.api.routers.export import export_score
from score_trans.api.schemas import ExportRequest
from score_trans.api.uploads import UploadManager
from score_trans.services.settings import ToolConfig


def test_render_routes_are_registered() -> None:
    paths = set(create_app().openapi()["paths"])

    assert "/render/final-output" in paths
    assert "/render/preserving-layout" in paths
    assert "/export" in paths
    assert "/history/pages/{page_id}" in paths


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


class FakeExportUseCase:
    def __init__(self) -> None:
        self.calls = []

    def execute(self, musicxml_file, output_file, **kwargs):
        self.calls.append((Path(musicxml_file), Path(output_file), kwargs))
        Path(output_file).write_bytes(b"exported")
        return Path(output_file)


def test_export_route_writes_and_registers_downloadable_file(tmp_path) -> None:
    config = ToolConfig(work_dir=tmp_path / "work")
    uploads = UploadManager(config)
    source = tmp_path / "score.musicxml"
    source.write_text("<score-partwise/>", encoding="utf-8")
    musicxml_id = uploads.register(source)
    fake_export = FakeExportUseCase()

    response = asyncio.run(
        export_score(
            ExportRequest(musicxml_file_id=musicxml_id, output_format="pdf"),
            uc=fake_export,
            uploads=uploads,
        )
    )

    assert response.filename == "score.pdf"
    assert uploads.get_path(response.file_id).read_bytes() == b"exported"
