import asyncio
from pathlib import Path
import time

from fastapi.testclient import TestClient

from score_trans.api.dependencies import get_file_actions
from score_trans.api.dependencies import get_history_actions
from score_trans.api.dependencies import get_settings_actions
from score_trans.api.app import create_app
from score_trans.api.export.routes import export_midi
from score_trans.api.render.routes import render_jianpu_svg
from score_trans.api.settings.routes import clear_cache
from score_trans.exec.export.actions import ExportActions
from score_trans.exec.files.actions import FileActions
from score_trans.exec.history.actions import HistoryActions
from score_trans.exec.settings.actions import SettingsActions
from score_trans.dao.settings.settings_dao import SettingsDao
from score_trans.models.render.schemas import (
    RenderJianpuSvgRequest,
    RenderJianpuSvgResponse,
)
from score_trans.models.common.errors import RenderError
from score_trans.models.export.schemas import ExportMidiRequest, ExportResponse
from score_trans.models.settings.schemas import CacheCleanupResponse
from score_trans.models.settings.config import ToolConfig
from score_trans.services.files.upload_service import UploadService
from score_trans.services.history.history_service import HistoryService
from score_trans.services.settings.settings_service import SettingsService


def test_render_routes_are_registered() -> None:
    paths = set(create_app().openapi()["paths"])

    assert "/render/final-output" in paths
    assert "/render/preserving-layout" in paths
    assert "/export/pdf" in paths
    assert "/export/midi" in paths
    assert "/history/pages/{page_id}" in paths
    assert "/history/{batch_id}/render-page-ocr-texts" in paths
    assert "/tasks/{task_id}" in paths
    assert "/tasks/{task_id}/stream" in paths


def test_render_error_uses_structured_api_response() -> None:
    app = create_app()

    @app.get("/_test/render-error")
    def raise_render_error() -> None:
        raise RenderError("渲染器未生成任何简谱 SVG 页面")

    response = TestClient(app).get("/_test/render-error")

    assert response.status_code == 500
    assert response.json() == {
        "error": "渲染器未生成任何简谱 SVG 页面",
        "stage": "render",
    }


def test_exec_errors_are_mapped_at_the_api_boundary() -> None:
    client = TestClient(create_app())

    missing_file = client.get("/files/definitely-missing")
    missing_export = client.post(
        "/export/midi",
        json={"musicxml_file_id": "definitely-missing"},
    )
    invalid_render = client.post("/render/batch-a4", json={"pages": []})

    assert missing_file.status_code == 404
    assert missing_file.json() == {
        "error": "文件不存在：definitely-missing",
        "stage": "files",
    }
    assert missing_export.status_code == 404
    assert missing_export.json() == {
        "error": "MusicXML 文件不存在：definitely-missing",
        "stage": "files",
    }
    assert invalid_render.status_code == 400
    assert invalid_render.json() == {
        "error": "至少需要一个待渲染页面",
        "stage": "validation",
    }


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


class SlowExportActions:
    def export_midi(
        self,
        musicxml_file_id: str,
        filename: str | None = None,
    ) -> ExportResponse:
        time.sleep(0.2)
        return ExportResponse(
            file_id=f"exported-{musicxml_file_id}",
            filename=filename or "score.mid",
        )


def test_export_route_offloads_blocking_export_work() -> None:
    async def scenario() -> tuple[float, bool, str]:
        start = time.perf_counter()
        task = asyncio.create_task(export_midi("score", actions=SlowExportActions()))
        await asyncio.sleep(0.01)
        elapsed = time.perf_counter() - start
        still_running = not task.done()
        result = await task
        return elapsed, still_running, result.file_id

    elapsed, still_running, file_id = asyncio.run(scenario())

    assert elapsed < 0.1
    assert still_running
    assert file_id == "exported-score"


class SlowSettingsActions:
    def clear_cache(self) -> CacheCleanupResponse:
        time.sleep(0.2)
        return CacheCleanupResponse(
            cache_dir="cache",
            before_bytes=1,
            after_bytes=0,
            freed_bytes=1,
            removed_items=1,
            preserved_uploads=0,
        )


def test_clear_cache_route_offloads_blocking_file_deletion() -> None:
    async def scenario() -> tuple[float, bool, int]:
        start = time.perf_counter()
        task = asyncio.create_task(clear_cache(actions=SlowSettingsActions()))
        await asyncio.sleep(0.01)
        elapsed = time.perf_counter() - start
        still_running = not task.done()
        result = await task
        return elapsed, still_running, result.removed_items

    elapsed, still_running, removed_items = asyncio.run(scenario())

    assert elapsed < 0.1
    assert still_running
    assert removed_items == 1


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
    assert "confirm_start_measure_number" in schemas["SettingsResponse"]["properties"]
    assert "jianpu_syntax_highlight" in schemas["SettingsResponse"]["properties"]
    assert "show_measure_numbers" in schemas["SettingsUpdateRequest"]["properties"]
    assert "measure_number_mode" in schemas["SettingsUpdateRequest"]["properties"]
    assert (
        "confirm_start_measure_number" in schemas["SettingsUpdateRequest"]["properties"]
    )
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


def test_settings_response_schema_does_not_expose_api_keys() -> None:
    properties = create_app().openapi()["components"]["schemas"]["SettingsResponse"][
        "properties"
    ]

    assert "ocr_api_key" not in properties
    assert "ai_api_key" not in properties
    assert "assistant_api_key" not in properties
    assert "ocr_api_key_set" in properties
    assert "ai_api_key_set" in properties
    assert "assistant_api_key_set" in properties


def test_target_key_schema_exposes_supported_keys() -> None:
    property_schema = create_app().openapi()["components"]["schemas"][
        "SettingsResponse"
    ]["properties"]["target_key"]

    enum_values: list[str] = []
    for sub_schema in property_schema.get("anyOf", []):
        enum_values.extend(sub_schema.get("enum", []))
        if "const" in sub_schema:
            enum_values.append(sub_schema["const"])
    if "enum" in property_schema:
        enum_values = property_schema["enum"]

    expected_keys = [
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
    for key in expected_keys:
        assert key in enum_values, f"missing key {key}"
    assert "auto" in enum_values
    assert property_schema["default"] == "auto"


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


def test_settings_persists_confirm_start_measure_number(tmp_path: Path) -> None:
    app = create_app()
    dao = SettingsDao(tmp_path / "settings.db")
    service = SettingsService(dao)
    service.set("work_dir", str(tmp_path / "work"))
    app.dependency_overrides[get_settings_actions] = lambda: SettingsActions(service)
    client = TestClient(app)

    response = client.get("/settings")
    assert response.status_code == 200
    assert response.json()["confirm_start_measure_number"] is True

    response = client.put("/settings", json={"confirm_start_measure_number": False})
    assert response.status_code == 200
    assert response.json()["confirm_start_measure_number"] is False

    response = client.get("/settings")
    assert response.json()["confirm_start_measure_number"] is False


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
    assert "text_attachments" in schemas["PageCreate"]["properties"]
    assert "text_attachments" in schemas["PageUpdate"]["properties"]
    assert "text_attachments" in schemas["PageResponse"]["properties"]
    assert "task_id" in schemas["PageCreate"]["properties"]
    assert "task_id" in schemas["PageUpdate"]["properties"]
    assert "task_id" in schemas["PageResponse"]["properties"]


def test_history_batch_schema_persists_batch_jianpu_text() -> None:
    schemas = create_app().openapi()["components"]["schemas"]

    assert "jianpu_text" in schemas["BatchCreateRequest"]["properties"]
    assert "jianpu_text" in schemas["BatchResponse"]["properties"]
    assert "jianpu_text" in schemas["BatchJianpuTextUpdate"]["properties"]


def test_history_api_accepts_unrecognized_pages_as_completed_batch(
    tmp_path: Path,
) -> None:
    app = create_app()
    service = HistoryService(tmp_path / "history.db")
    app.dependency_overrides[get_history_actions] = lambda: HistoryActions(service)
    client = TestClient(app)

    response = client.post(
        "/history",
        json={
            "jianpu_text": "// @page 1 start=auto\n1 2 |\n// @page 2 start=auto",
            "pages": [
                {
                    "input_file_name": "recognized.png",
                    "input_file_id": "input-1",
                    "jianpu_text": "1 2 |",
                    "status": "completed",
                },
                {
                    "input_file_name": "unrecognized.png",
                    "input_file_id": "input-2",
                    "status": "unrecognized",
                },
            ],
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["page_count"] == 2
    assert [page["status"] for page in payload["pages"]] == [
        "completed",
        "unrecognized",
    ]


def test_history_list_returns_last_completed_at(tmp_path: Path) -> None:
    app = create_app()
    service = HistoryService(tmp_path / "history.db")
    app.dependency_overrides[get_history_actions] = lambda: HistoryActions(service)
    client = TestClient(app)

    created = client.post(
        "/history",
        json={
            "pages": [
                {
                    "input_file_name": "score.png",
                    "status": "processing",
                }
            ]
        },
    ).json()
    page_id = created["pages"][0]["id"]
    completed = client.patch(
        f"/history/pages/{page_id}",
        json={"status": "completed"},
    )

    assert completed.status_code == 200
    completed_page = service.get_page(page_id)
    assert completed_page is not None
    completed_at = completed_page.completed_at
    assert completed_at

    response = client.get("/history")

    assert response.status_code == 200
    assert response.json()[0]["last_completed_at"] == completed_at


def test_batch_a4_schema_exposes_page_ranges_and_page_ocr_texts() -> None:
    schemas = create_app().openapi()["components"]["schemas"]

    assert "source_pages" in schemas["BatchRenderRequest"]["properties"]
    assert "render_page_ocr_texts" in schemas["BatchRenderRequest"]["properties"]
    assert "measure_ranges" in schemas["RenderedSvgPage"]["properties"]
    assert "ocr_text" in schemas["RenderedSvgPage"]["properties"]
    assert "text_blocks" in schemas["RenderedSvgPage"]["properties"]
    assert "text_attachments" in schemas["BatchRenderPageRequest"]["properties"]
    assert "source_map_file_id" in schemas["BatchRenderPageRequest"]["properties"]
    assert "render_page_ocr_texts" in schemas["BatchCreateRequest"]["properties"]
    assert "render_page_ocr_texts" in schemas["BatchResponse"]["properties"]
    assert "pages" in schemas["BatchRenderPageOcrTextsUpdate"]["properties"]


def test_history_batch_jianpu_text_endpoint_updates_batch_only(tmp_path: Path) -> None:
    app = create_app()
    service = HistoryService(tmp_path / "history.db")
    app.dependency_overrides[get_history_actions] = lambda: HistoryActions(service)
    client = TestClient(app)

    response = client.post(
        "/history",
        json={
            "jianpu_text": "1=C\n4/4\n1 2 |",
            "pages": [
                {
                    "input_file_name": "a.png",
                    "jianpu_text": "1=C\n4/4\n1 2 |",
                }
            ],
        },
    )
    assert response.status_code == 201
    batch_id = response.json()["id"]

    response = client.patch(
        f"/history/{batch_id}/jianpu-text",
        json={"jianpu_text": "1=C\n4/4\n3 4 |"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["jianpu_text"] == "1=C\n4/4\n3 4 |"
    assert payload["pages"][0]["jianpu_text"] == "1=C\n4/4\n1 2 |"


def test_history_endpoints_preserve_editor_comments_and_blank_lines(
    tmp_path: Path,
) -> None:
    app = create_app()
    service = HistoryService(tmp_path / "history.db")
    app.dependency_overrides[get_history_actions] = lambda: HistoryActions(service)
    client = TestClient(app)
    raw_text = "1=C\n4/4\n// 用户注释\n\n1 2 3 4 | // 行尾注释"

    response = client.post(
        "/history",
        json={
            "jianpu_text": raw_text,
            "pages": [
                {
                    "input_file_name": "a.png",
                    "jianpu_text": raw_text,
                }
            ],
        },
    )

    assert response.status_code == 201
    payload = response.json()
    batch_id = payload["id"]
    page_id = payload["pages"][0]["id"]
    assert payload["jianpu_text"] == raw_text
    assert payload["pages"][0]["jianpu_text"] == raw_text

    updated_text = "1=C\n4/4\n1 2 3 4 |\n\n// 保存后的注释"
    response = client.patch(
        f"/history/{batch_id}/jianpu-text",
        json={"jianpu_text": updated_text},
    )
    assert response.status_code == 200
    assert response.json()["jianpu_text"] == updated_text

    response = client.patch(
        f"/history/pages/{page_id}",
        json={"jianpu_text": updated_text},
    )
    assert response.status_code == 200
    assert response.json()["jianpu_text"] == updated_text


def test_history_page_endpoint_returns_latest_page_and_404(tmp_path: Path) -> None:
    app = create_app()
    service = HistoryService(tmp_path / "history.db")
    app.dependency_overrides[get_history_actions] = lambda: HistoryActions(service)
    client = TestClient(app)
    created = client.post(
        "/history",
        json={
            "pages": [
                {
                    "input_file_name": "score.png",
                    "status": "waiting",
                    "error_message": "等待选择起始小节号：7、9",
                }
            ]
        },
    ).json()
    page_id = created["pages"][0]["id"]
    client.patch(
        f"/history/pages/{page_id}",
        json={
            "start_measure_number": 9,
            "status": "completed",
            "error_message": "",
        },
    )

    response = client.get(f"/history/pages/{page_id}")

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["start_measure_number"] == 9
    assert client.get("/history/pages/404").status_code == 404


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
            req=ExportMidiRequest(musicxml_file_id=musicxml_id),
            actions=ExportActions(uploads=uploads, exporter=fake_export),
        )
    )

    assert response.filename == "score.mid"
    assert uploads.get_path(response.file_id).read_bytes() == b"exported"


def test_instrument_profile_catalog_uses_contextual_tremolo_labels() -> None:
    response = TestClient(create_app()).get("/notation/instrument-profiles")

    assert response.status_code == 200
    profiles = {profile["id"]: profile for profile in response.json()}
    assert set(profiles) == {"general", "erhu", "ruan", "guzheng"}
    assert all(mark["id"] != "tremolo" for mark in profiles["general"]["marks"])
    erhu_tremolo = next(
        mark for mark in profiles["erhu"]["marks"] if mark["id"] == "tremolo"
    )
    ruan_tremolo = next(
        mark for mark in profiles["ruan"]["marks"] if mark["id"] == "tremolo"
    )
    guzheng_tremolo = next(
        mark for mark in profiles["guzheng"]["marks"] if mark["id"] == "tremolo"
    )
    assert erhu_tremolo["name"] == "颤弓（抖弓）"
    assert ruan_tremolo["name"] == "轮指"
    assert guzheng_tremolo["name"] == "摇指"
    assert profiles["erhu"]["range_examples"][0]["syntax"].startswith("(^l)")
    guzheng_ids = {
        mark["id"]
        for mark in profiles["guzheng"]["marks"]
        if mark["id"]
        in {
            "tremolo",
            "guzheng-sweep-tremolo",
            "string-sweep",
            "natural-harmonic",
            "guzheng-double-tuo",
            "guzheng-double-mo",
            "arpeggio",
            "guzheng-board-front-flower",
            "guzheng-on-beat-flower",
            "guzheng-ascending-scrape",
            "guzheng-descending-scrape",
            "guzheng-vibrato",
            "scoop",
            "plop",
            "guzheng-ornament-up-slide",
            "guzheng-ornament-down-slide",
            "continuous-slide",
        }
    }
    assert len(guzheng_ids) == 17
    ruan_marks = {
        mark["id"]: mark["name"]
        for mark in profiles["ruan"]["marks"]
        if mark["id"]
        in {
            "tremolo",
            "string-sweep",
            "natural-harmonic",
            "continuous-slide",
            "ornament-note",
            "arpeggio",
        }
    }
    assert ruan_marks == {
        "tremolo": "轮指",
        "string-sweep": "扫弦",
        "natural-harmonic": "泛音",
        "continuous-slide": "滑音",
        "ornament-note": "装饰音",
        "arpeggio": "琶音",
    }
    assert (
        next(
            mark
            for mark in profiles["guzheng"]["marks"]
            if mark["id"] == "natural-harmonic"
        )["syntax"]
        == "^zr"
    )
    excluded_names = {
        "大指摇",
        "食指摇",
        "柱音",
        "游摇",
        "逗号",
        "句号",
        "分号",
        "大撮",
        "小撮",
        "分指双托",
        "三指轮",
        "四指轮",
        "重颤音",
        "回滑音",
        "点音",
        "按音",
        "左手大拇指按滑符号",
    }
    assert excluded_names.isdisjoint(
        mark["name"] for mark in profiles["guzheng"]["marks"]
    )
