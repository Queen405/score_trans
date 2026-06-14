import asyncio
from pathlib import Path
import time

from fastapi.testclient import TestClient

from score_trans.api.dependencies import get_file_actions
from score_trans.api.dependencies import get_settings_actions
from score_trans.api.app import create_app
from score_trans.api.export.routes import export_midi
from score_trans.api.render.routes import render_jianpu_svg
from score_trans.exec.export.actions import ExportActions
from score_trans.exec.files.actions import FileActions
from score_trans.exec.settings.actions import SettingsActions
from score_trans.dao.settings.settings_dao import SettingsDao
from score_trans.models.render.schemas import RenderJianpuSvgRequest, RenderJianpuSvgResponse
from score_trans.models.settings.config import ToolConfig
from score_trans.services.files.upload_service import UploadService
from score_trans.services.settings.settings_service import SettingsService


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
    assert "accidental_mode" in schema["properties"]


class SlowRenderActions:
    def render_jianpu_svg(
        self,
        req: RenderJianpuSvgRequest,
    ) -> RenderJianpuSvgResponse:
        time.sleep(0.2)
        return RenderJianpuSvgResponse(svg_file_id=f"rendered-{req.musicxml_file_id}")


def test_render_route_offloads_blocking_render_work() -> None:
    async def scenario() -> tuple[float, bool, str]:
        start = time.perf_counter()
        task = asyncio.create_task(
            render_jianpu_svg(
                RenderJianpuSvgRequest(musicxml_file_id="score"),
                actions=SlowRenderActions(),
            )
        )
        await asyncio.sleep(0.01)
        elapsed = time.perf_counter() - start
        still_running = not task.done()
        result = await task
        return elapsed, still_running, result.svg_file_id

    elapsed, still_running, svg_file_id = asyncio.run(scenario())

    assert elapsed < 0.1
    assert still_running
    assert svg_file_id == "rendered-score"


def test_musicxml_to_jianpu_request_accepts_page_image_for_ocr_text() -> None:
    schema = create_app().openapi()["components"]["schemas"]["MusicXmlToJianpuRequest"]

    assert "page_image_file_id" in schema["properties"]
    assert "accidental_mode" in schema["properties"]


def test_generation_requests_accept_accidental_mode() -> None:
    schemas = create_app().openapi()["components"]["schemas"]

    assert "accidental_mode" in schemas["SettingsResponse"]["properties"]
    assert "accidental_mode" in schemas["SettingsUpdateRequest"]["properties"]
    assert "accidental_mode" in schemas["PipelineByFileIdRequest"]["properties"]
    assert "accidental_mode" in schemas["FinalRenderRequest"]["properties"]
    assert "accidental_mode" in schemas["PreservingLayoutRequest"]["properties"]
    assert "accidental_mode" in schemas["AiTranscribeRequest"]["properties"]


def test_generation_requests_accept_show_measure_numbers() -> None:
    schemas = create_app().openapi()["components"]["schemas"]

    assert "show_measure_numbers" in schemas["SettingsResponse"]["properties"]
    assert "measure_number_mode" in schemas["SettingsResponse"]["properties"]
    assert "jianpu_syntax_highlight" in schemas["SettingsResponse"]["properties"]
    assert "show_measure_numbers" in schemas["SettingsUpdateRequest"]["properties"]
    assert "measure_number_mode" in schemas["SettingsUpdateRequest"]["properties"]
    assert "jianpu_syntax_highlight" in schemas["SettingsUpdateRequest"]["properties"]
    assert "show_measure_numbers" in schemas["PipelineByFileIdRequest"]["properties"]
    assert "measure_number_mode" in schemas["PipelineByFileIdRequest"]["properties"]
    assert "show_measure_numbers" in schemas["RenderJianpuSvgRequest"]["properties"]
    assert "measure_number_mode" in schemas["RenderJianpuSvgRequest"]["properties"]
    assert "show_measure_numbers" in schemas["RenderJianpuTextSvgRequest"]["properties"]
    assert "measure_number_mode" in schemas["RenderJianpuTextSvgRequest"]["properties"]
    assert "show_measure_numbers" in schemas["FinalRenderRequest"]["properties"]
    assert "measure_number_mode" in schemas["FinalRenderRequest"]["properties"]
    assert "show_measure_numbers" in schemas["PreservingLayoutRequest"]["properties"]
    assert "measure_number_mode" in schemas["PreservingLayoutRequest"]["properties"]


def test_target_key_schema_exposes_supported_keys() -> None:
    property_schema = create_app().openapi()["components"]["schemas"][
        "SettingsResponse"
    ]["properties"]["target_key"]

    assert property_schema["enum"] == [
        "Cb",
        "Gb",
        "Db",
        "Ab",
        "Eb",
        "Bb",
        "F",
        "C",
        "G",
        "D",
        "A",
        "E",
        "B",
        "F#",
        "C#",
    ]


def test_settings_persists_show_measure_numbers(tmp_path: Path) -> None:
    app = create_app()
    dao = SettingsDao(tmp_path / "settings.db")
    service = SettingsService(dao)
    service.set("work_dir", str(tmp_path / "work"))
    app.dependency_overrides[get_settings_actions] = lambda: SettingsActions(service)
    client = TestClient(app)

    response = client.get("/settings")
    assert response.status_code == 200
    assert response.json()["show_measure_numbers"] is True
    assert response.json()["measure_number_mode"] == "all"

    response = client.put(
        "/settings", json={"measure_number_mode": "row_start", "target_key": "F#"}
    )
    assert response.status_code == 200
    assert response.json()["show_measure_numbers"] is True
    assert response.json()["measure_number_mode"] == "row_start"
    assert response.json()["target_key"] == "F#"

    response = client.get("/settings")
    assert response.json()["measure_number_mode"] == "row_start"

    response = client.put("/settings", json={"show_measure_numbers": False})
    assert response.status_code == 200
    assert response.json()["show_measure_numbers"] is False
    assert response.json()["measure_number_mode"] == "none"


def test_settings_persists_jianpu_syntax_highlight(tmp_path: Path) -> None:
    app = create_app()
    dao = SettingsDao(tmp_path / "settings.db")
    service = SettingsService(dao)
    service.set("work_dir", str(tmp_path / "work"))
    app.dependency_overrides[get_settings_actions] = lambda: SettingsActions(service)
    client = TestClient(app)

    response = client.get("/settings")
    assert response.status_code == 200
    assert response.json()["jianpu_syntax_highlight"] is False

    response = client.put("/settings", json={"jianpu_syntax_highlight": True})
    assert response.status_code == 200
    assert response.json()["jianpu_syntax_highlight"] is True

    response = client.get("/settings")
    assert response.json()["jianpu_syntax_highlight"] is True


def test_settings_rejects_unsupported_target_key(tmp_path: Path) -> None:
    app = create_app()
    dao = SettingsDao(tmp_path / "settings.db")
    service = SettingsService(dao)
    service.set("work_dir", str(tmp_path / "work"))
    app.dependency_overrides[get_settings_actions] = lambda: SettingsActions(service)

    response = TestClient(app).put("/settings", json={"target_key": "D#"})

    assert response.status_code == 422


def test_jianpu_text_svg_request_accepts_page_image_for_ocr_overlay() -> None:
    schema = create_app().openapi()["components"]["schemas"][
        "RenderJianpuTextSvgRequest"
    ]

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


def test_file_download_allows_local_dev_origin_on_any_port(tmp_path: Path) -> None:
    app = create_app()
    config = ToolConfig(work_dir=tmp_path / "work")
    uploads = UploadService(config)
    source = tmp_path / "page.png"
    source.write_bytes(b"png")
    file_id = uploads.register(source)
    app.dependency_overrides[get_file_actions] = lambda: FileActions(uploads=uploads)

    response = TestClient(app).get(
        f"/files/{file_id}",
        headers={"Origin": "http://localhost:58123"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:58123"


def test_files_exist_route_returns_batch_existence(tmp_path: Path) -> None:
    app = create_app()
    config = ToolConfig(work_dir=tmp_path / "work")
    uploads = UploadService(config)
    source = tmp_path / "page.png"
    source.write_bytes(b"png")
    file_id = uploads.register(source)
    app.dependency_overrides[get_file_actions] = lambda: FileActions(uploads=uploads)

    response = TestClient(app).post(
        "/files/exists",
        json={"file_ids": [file_id, "missing", ""]},
    )

    assert response.status_code == 200
    assert response.json() == {
        "files": {
            file_id: True,
            "missing": False,
            "": False,
        }
    }


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
