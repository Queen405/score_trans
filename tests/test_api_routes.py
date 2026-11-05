import asyncio
import time
from pathlib import Path

import pytest

from fastapi.testclient import TestClient
from score_trans.api.app import create_app
from score_trans.api.dependencies import (
    get_file_actions,
    get_history_actions,
    get_settings_actions,
    get_syntax_actions,
)
from score_trans.api.export.routes import export_midi
from score_trans.api.render.routes import render_jianpu_svg
from score_trans.api.settings.routes import clear_cache
from score_trans.dao.settings.settings_dao import SettingsDao
from score_trans.exec.export.actions import ExportActions
from score_trans.exec.files.actions import FileActions
from score_trans.exec.history.actions import HistoryActions
from score_trans.exec.settings.actions import SettingsActions
from score_trans.exec.syntax.actions import (
    MAX_DIAGNOSTICS,
    TRUNCATED_MARKER_ID,
    SyntaxActions,
)
from score_trans.models.common.errors import RenderError
from score_trans.models.history.entities import HistoryPage
from score_trans.models.history.schemas import PageUpdate
from score_trans.models.export.schemas import ExportMidiRequest, ExportResponse
from score_trans.models.render.schemas import (
    RenderJianpuSvgRequest,
    RenderJianpuSvgResponse,
)
from score_trans.models.settings.config import ToolConfig
from score_trans.models.settings.schemas import CacheCleanupResponse
from score_trans.services.files.upload_service import UploadService
from score_trans.services.history.history_service import HistoryService
from score_trans.services.settings.settings_service import SettingsService


def test_render_routes_are_registered() -> None:
    paths = set(create_app().openapi()["paths"])

    assert "/render/final-output" in paths
    assert "/render/preserving-layout" in paths
    assert "/export/pdf" in paths
    assert "/export/midi" in paths
    assert "/syntax/validate" in paths
    assert "/history/pages/{page_id}" in paths
    assert "/history/{batch_id}/render-page-ocr-texts" in paths
    assert "/files/{file_id}/rotate" in paths
    assert "/files/{file_id}/pdf-page" in paths
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


def test_jianpu_syntax_error_uses_coded_validation_response() -> None:
    response = TestClient(create_app()).post(
        "/export/musicxml-text",
        json={"jianpu_text": "1=C\n4/4\n45 |"},
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": "第 3 行第 1 列：不支持的简谱 token：45，"
        "请使用 1-7、0、#1、qs1、q1、[1+3+5] 等新语法",
        "stage": "validation",
        "code": "jianpu_syntax",
    }


def test_jianpu_parser_validation_errors_use_the_same_output_block_code() -> None:
    response = TestClient(create_app()).post(
        "/export/musicxml-text",
        json={
            "jianpu_text": "instrument=unknown\n1=C\n4/4\n1 2 3 4 |",
        },
    )

    assert response.status_code == 400
    assert response.json()["code"] == "jianpu_syntax"


def test_batch_jianpu_syntax_error_keeps_the_page_context_for_editor_jump() -> None:
    response = TestClient(create_app()).post(
        "/render/batch-a4",
        json={
            "pages": [
                {"jianpu_text": "1=C\n4/4\n1 2 3 4 |"},
                {"jianpu_text": "1=C\n4/4\n1 2 45 |"},
            ],
        },
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["code"] == "jianpu_syntax"
    assert payload["error"].startswith("第 2 页：第 3 行第 5 列")


def test_invalid_time_signature_is_a_coded_validation_error_not_500() -> None:
    response = TestClient(create_app()).post(
        "/export/musicxml-text",
        json={"jianpu_text": "1=C\n4/0\n1 2 3 4 |"},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["stage"] == "validation"
    assert payload["code"] == "jianpu_syntax"
    assert "拍号无效：4/0" in payload["error"]


def test_multi_part_measure_count_mismatch_is_a_coded_jianpu_validation_error() -> None:
    jianpu_text = (
        '// @part 1 name="a"\n1=C\n4/4\n1 2 3 4 | 5 6 7 1 |\n'
        '// @part 2 name="b"\n1=C\n4/4\n1 2 3 4 |'
    )
    response = TestClient(create_app()).post(
        "/render/batch-a4",
        json={"pages": [{"jianpu_text": jianpu_text}]},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["stage"] == "validation"
    assert payload["code"] == "jianpu_syntax"
    assert "各声部小节数量不一致" in payload["error"]


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
    assert "jianpu_syntax_highlight" in schemas["SettingsResponse"]["properties"]
    assert "jianpu_measure_duration_check" in schemas["SettingsResponse"]["properties"]
    assert "jianpu_auto_transpose" in schemas["SettingsResponse"]["properties"]
    assert "show_measure_numbers" in schemas["SettingsUpdateRequest"]["properties"]
    assert "measure_number_mode" in schemas["SettingsUpdateRequest"]["properties"]
    assert "jianpu_syntax_highlight" in schemas["SettingsUpdateRequest"]["properties"]
    assert (
        "jianpu_measure_duration_check"
        in schemas["SettingsUpdateRequest"]["properties"]
    )
    assert "jianpu_auto_transpose" in schemas["SettingsUpdateRequest"]["properties"]
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


def test_settings_response_schema_exposes_api_keys() -> None:
    properties = create_app().openapi()["components"]["schemas"]["SettingsResponse"][
        "properties"
    ]

    assert "ocr_api_key" in properties
    assert "ai_api_key" in properties
    assert "assistant_api_key" in properties
    assert "ocr_api_key_set" in properties
    assert "ai_api_key_set" in properties
    assert "assistant_api_key_set" in properties


def test_settings_schema_exposes_omr_ocr_toggle() -> None:
    schemas = create_app().openapi()["components"]["schemas"]

    assert "enable_omr_ocr" in schemas["SettingsResponse"]["properties"]
    assert "enable_omr_ocr" in schemas["SettingsUpdateRequest"]["properties"]


def test_jianpu_rekey_route_declares_its_request_and_response_schema() -> None:
    # The models used to be defined inside the route body, so they never reached
    # the OpenAPI document and the generated frontend types could not drift-check.
    document = create_app().openapi()
    schemas = document["components"]["schemas"]

    assert "/jianpu/rekey" in document["paths"]
    assert "text" in schemas["JianpuRekeyRequest"]["properties"]
    assert "previous_text" in schemas["JianpuRekeyRequest"]["properties"]
    assert "transposed_text" in schemas["JianpuRekeyResponse"]["properties"]
    # The editor needs the skip reason to tell "nothing to do" apart from a
    # silent failure, so it has to reach the generated frontend types.
    assert "skip_reason" in schemas["JianpuRekeyResponse"]["properties"]
    assert "skip_detail" in schemas["JianpuRekeyResponse"]["properties"]
    assert "anchor_mapping" in schemas["JianpuRekeyResponse"]["properties"]
    assert "诊断" in schemas["RekeyAnchorMapping"]["description"]
    body = document["paths"]["/jianpu/rekey"]["post"]["requestBody"]
    assert body["content"]["application/json"]["schema"]["$ref"].endswith(
        "JianpuRekeyRequest"
    )


def test_jianpu_rekey_transposes_the_segment_after_the_changed_key() -> None:
    client = TestClient(create_app(auth_disabled=True))

    response = client.post(
        "/jianpu/rekey",
        json={"text": "1=G\n4/4\n4 5 6", "previous_text": "1=C\n4/4\n4 5 6"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["transposed_text"] == "1=G\n4/4\nb7, 1 2"
    assert payload["skip_reason"] is None
    assert payload["anchor_mapping"]


def test_jianpu_rekey_reports_a_parse_error_instead_of_failing_silently() -> None:
    # The parser requires a key to open a measure; "1=E" on a line whose previous
    # line has no closing barline is rejected. The route still answers 200 with
    # the input text, but names the reason so the editor can surface it.
    client = TestClient(create_app(auth_disabled=True))
    text = "1=C\n4/4\n1 2 3 4\n1=E 5 6 7 1"

    response = client.post(
        "/jianpu/rekey",
        json={"text": text, "previous_text": "1=C\n4/4\n1 2 3 4\n5 6 7 1"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["transposed_text"] == text
    assert payload["skip_reason"] == "parse_error"
    assert payload["skip_detail"]


def test_jianpu_rekey_rejects_a_missing_field_with_a_validation_error() -> None:
    client = TestClient(create_app(auth_disabled=True))

    response = client.post("/jianpu/rekey", json={"text": "1=G\n1 2 3"})

    assert response.status_code == 422


def test_jianpu_rekey_maps_an_unsupported_key_to_a_validation_error() -> None:
    # 1=D# parses but has no scale table entry; the global ValueError handler
    # turns the domain error into the shared 400 validation envelope.
    client = TestClient(create_app(auth_disabled=True))

    response = client.post(
        "/jianpu/rekey",
        json={"text": "1=D#\n4/4\n1 2 3", "previous_text": "1=C\n4/4\n1 2 3"},
    )

    assert response.status_code == 400
    assert response.json()["stage"] == "validation"


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
    assert response.json()["measure_number_mode"] == "row_start"

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
    assert response.json()["jianpu_syntax_highlight"] is True
    assert response.json()["jianpu_measure_duration_check"] is True

    response = client.put("/settings", json={"jianpu_syntax_highlight": False})
    assert response.status_code == 200
    assert response.json()["jianpu_syntax_highlight"] is False

    response = client.get("/settings")
    assert response.json()["jianpu_syntax_highlight"] is False

    response = client.put("/settings", json={"jianpu_measure_duration_check": False})
    assert response.status_code == 200
    assert response.json()["jianpu_measure_duration_check"] is False

    response = client.get("/settings")
    assert response.json()["jianpu_measure_duration_check"] is False

    assert response.json()["jianpu_auto_transpose"] is True

    response = client.put("/settings", json={"jianpu_auto_transpose": False})
    assert response.status_code == 200
    assert response.json()["jianpu_auto_transpose"] is False

    response = client.get("/settings")
    assert response.json()["jianpu_auto_transpose"] is False


def test_syntax_measure_duration_warnings_follow_saved_setting(tmp_path: Path) -> None:
    app = create_app(auth_disabled=True)
    service = SettingsService(SettingsDao(tmp_path / "settings.db"))
    app.dependency_overrides[get_settings_actions] = lambda: SettingsActions(service)
    app.dependency_overrides[get_syntax_actions] = lambda: SyntaxActions(
        settings=service
    )
    client = TestClient(app)
    text = "1=C\n4/4\n1 2 3 |"

    diagnostics = client.post("/syntax/validate", json={"jianpu_text": text}).json()[
        "diagnostics"
    ]
    assert len(diagnostics) == 1
    assert diagnostics[0]["severity"] == "warning"
    assert "少拍" in diagnostics[0]["message"]

    response = client.put(
        "/settings",
        json={"jianpu_measure_duration_check": False},
    )

    assert response.status_code == 200
    assert response.json()["jianpu_measure_duration_check"] is False
    assert client.post("/syntax/validate", json={"jianpu_text": text}).json() == {
        "diagnostics": [],
        "lyrics": [],
    }

    diagnostics = client.post(
        "/syntax/validate",
        json={"jianpu_text": "1=C\n4/4\n45 1 2 | 1 2 3 4 5 |"},
    ).json()["diagnostics"]
    assert [item["severity"] for item in diagnostics] == ["error"]
    assert "不支持的简谱 token：45" in diagnostics[0]["message"]


def test_syntax_validate_truncates_diagnostics_above_limit(tmp_path: Path) -> None:
    app = create_app(auth_disabled=True)
    service = SettingsService(SettingsDao(tmp_path / "settings.db"))
    app.dependency_overrides[get_settings_actions] = lambda: SettingsActions(service)
    app.dependency_overrides[get_syntax_actions] = lambda: SyntaxActions(
        settings=service
    )
    client = TestClient(app)
    text = "1=C\n4/4\n" + "1 | " * 1100

    diagnostics = client.post("/syntax/validate", json={"jianpu_text": text}).json()[
        "diagnostics"
    ]

    assert len(diagnostics) == MAX_DIAGNOSTICS
    assert all(item["severity"] == "warning" for item in diagnostics)
    assert all(item["id"] != TRUNCATED_MARKER_ID for item in diagnostics[:-1])
    marker = diagnostics[-1]
    assert marker["id"] == TRUNCATED_MARKER_ID
    assert str(MAX_DIAGNOSTICS - 1) in marker["message"]


def test_settings_persists_a4_layout_percentages(tmp_path: Path) -> None:
    app = create_app()
    dao = SettingsDao(tmp_path / "settings.db")
    service = SettingsService(dao)
    service.set("work_dir", str(tmp_path / "work"))
    app.dependency_overrides[get_settings_actions] = lambda: SettingsActions(service)
    client = TestClient(app)

    initial = client.get("/settings")
    assert initial.status_code == 200
    assert initial.json()["jianpu_content_scale_percent"] == 80
    assert initial.json()["jianpu_system_gap_percent"] == 50
    assert initial.json()["jianpu_short_note_gap_percent"] == 20
    assert initial.json()["jianpu_beat_gap_percent"] == 100
    assert initial.json()["jianpu_break_beams_at_beat"] is False
    assert initial.json()["jianpu_measures_per_system"] == 0
    assert initial.json()["jianpu_margin_top_mm"] == 10
    assert initial.json()["jianpu_margin_bottom_mm"] == 7
    assert initial.json()["jianpu_margin_left_mm"] == 12
    assert initial.json()["jianpu_margin_right_mm"] == 12
    assert initial.json()["jianpu_header_gap_mm"] == 5
    assert initial.json()["jianpu_footer_protection_mm"] == 2
    assert initial.json()["jianpu_note_size_percent"] == 100
    assert initial.json()["jianpu_lyric_size_percent"] == 100
    assert initial.json()["jianpu_title_size_percent"] == 100
    assert initial.json()["jianpu_annotation_size_percent"] == 100
    assert initial.json()["jianpu_part_gap_percent"] == 100
    assert initial.json()["jianpu_voice_gap_percent"] == 100
    assert initial.json()["jianpu_lyric_line_gap_percent"] == 100
    assert initial.json()["jianpu_lyric_note_gap_percent"] == 100

    updated = client.put(
        "/settings",
        json={
            "jianpu_content_scale_percent": 75,
            "jianpu_system_gap_percent": 88,
            "jianpu_short_note_gap_percent": 85,
            "jianpu_beat_gap_percent": 140,
            "jianpu_break_beams_at_beat": True,
            "jianpu_measures_per_system": 4,
            "jianpu_margin_top_mm": 15.5,
            "jianpu_margin_bottom_mm": 9,
            "jianpu_margin_left_mm": 16,
            "jianpu_margin_right_mm": 17,
            "jianpu_header_gap_mm": 7.5,
            "jianpu_footer_protection_mm": 4,
            "jianpu_note_size_percent": 120,
            "jianpu_lyric_size_percent": 85,
            "jianpu_title_size_percent": 130,
            "jianpu_annotation_size_percent": 95,
            "jianpu_part_gap_percent": 120,
            "jianpu_voice_gap_percent": 130,
            "jianpu_lyric_line_gap_percent": 140,
            "jianpu_lyric_note_gap_percent": 150,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["jianpu_content_scale_percent"] == 75
    assert updated.json()["jianpu_system_gap_percent"] == 88
    assert updated.json()["jianpu_short_note_gap_percent"] == 85
    assert updated.json()["jianpu_beat_gap_percent"] == 140
    assert updated.json()["jianpu_break_beams_at_beat"] is True
    assert updated.json()["jianpu_measures_per_system"] == 4
    assert updated.json()["jianpu_margin_top_mm"] == 15.5
    assert updated.json()["jianpu_margin_bottom_mm"] == 9
    assert updated.json()["jianpu_margin_left_mm"] == 16
    assert updated.json()["jianpu_margin_right_mm"] == 17
    assert updated.json()["jianpu_header_gap_mm"] == 7.5
    assert updated.json()["jianpu_footer_protection_mm"] == 4
    assert updated.json()["jianpu_note_size_percent"] == 120
    assert updated.json()["jianpu_lyric_size_percent"] == 85
    assert updated.json()["jianpu_title_size_percent"] == 130
    assert updated.json()["jianpu_annotation_size_percent"] == 95
    assert updated.json()["jianpu_part_gap_percent"] == 120
    assert updated.json()["jianpu_voice_gap_percent"] == 130
    assert updated.json()["jianpu_lyric_line_gap_percent"] == 140
    assert updated.json()["jianpu_lyric_note_gap_percent"] == 150

    boundaries = client.put(
        "/settings",
        json={
            "jianpu_system_gap_percent": 20,
            "jianpu_short_note_gap_percent": 180,
            "jianpu_beat_gap_percent": 0,
            "jianpu_part_gap_percent": 0,
        },
    )
    assert boundaries.status_code == 200
    assert boundaries.json()["jianpu_system_gap_percent"] == 20
    assert boundaries.json()["jianpu_short_note_gap_percent"] == 180
    assert boundaries.json()["jianpu_beat_gap_percent"] == 0
    assert boundaries.json()["jianpu_part_gap_percent"] == 0

    for invalid in (1, 2, 6, "4", True):
        assert (
            client.put(
                "/settings", json={"jianpu_measures_per_system": invalid}
            ).status_code
            == 422
        )

    assert (
        client.put("/settings", json={"jianpu_content_scale_percent": 64}).status_code
        == 422
    )
    assert (
        client.put("/settings", json={"jianpu_system_gap_percent": 19}).status_code
        == 422
    )
    assert (
        client.put("/settings", json={"jianpu_short_note_gap_percent": 181}).status_code
        == 422
    )
    assert (
        client.put("/settings", json={"jianpu_beat_gap_percent": 201}).status_code
        == 422
    )


def test_all_a4_request_contracts_expose_layout_controls() -> None:
    schemas = create_app().openapi()["components"]["schemas"]
    request_names = (
        "RenderJianpuSvgRequest",
        "RenderJianpuTextSvgRequest",
        "FinalRenderRequest",
        "BatchRenderRequest",
        "PipelineByFileIdRequest",
        "ConversionOptionsDTO",
    )
    for request_name in request_names:
        properties = schemas[request_name]["properties"]
        assert properties["jianpu_content_scale_percent"]["default"] == 80
        assert properties["jianpu_system_gap_percent"]["default"] == 50
        assert properties["jianpu_short_note_gap_percent"]["default"] == 20
        assert properties["jianpu_beat_gap_percent"]["default"] == 100
        assert properties["jianpu_break_beams_at_beat"]["default"] is False
        assert properties["jianpu_measures_per_system"]["default"] == 0
        assert properties["jianpu_measures_per_system"]["enum"] == [0, 3, 4, 5]
        assert properties["jianpu_margin_top_mm"]["default"] == 10
        assert properties["jianpu_margin_bottom_mm"]["default"] == 7
        assert properties["jianpu_margin_left_mm"]["default"] == 12
        assert properties["jianpu_margin_right_mm"]["default"] == 12
        assert properties["jianpu_header_gap_mm"]["default"] == 5
        assert properties["jianpu_footer_protection_mm"]["default"] == 2
        assert properties["jianpu_note_size_percent"]["default"] == 100
        assert properties["jianpu_lyric_size_percent"]["default"] == 100
        assert properties["jianpu_title_size_percent"]["default"] == 100
        assert properties["jianpu_annotation_size_percent"]["default"] == 100
        assert properties["jianpu_part_gap_percent"]["default"] == 100
        assert properties["jianpu_part_gap_percent"]["minimum"] == 0
        assert properties["jianpu_voice_gap_percent"]["default"] == 100
        assert properties["jianpu_lyric_line_gap_percent"]["default"] == 100
        assert properties["jianpu_lyric_note_gap_percent"]["default"] == 100
        assert properties["jianpu_system_gap_percent"]["minimum"] == 20
        assert properties["jianpu_system_gap_percent"]["maximum"] == 180
        assert properties["jianpu_short_note_gap_percent"]["minimum"] == 20
        assert properties["jianpu_short_note_gap_percent"]["maximum"] == 180
        assert properties["jianpu_beat_gap_percent"]["minimum"] == 0
        assert properties["jianpu_beat_gap_percent"]["maximum"] == 200

    settings_properties = schemas["SettingsUpdateRequest"]["properties"]
    settings_system_gap = settings_properties["jianpu_system_gap_percent"]["anyOf"][0]
    settings_short_note_gap = settings_properties["jianpu_short_note_gap_percent"][
        "anyOf"
    ][0]
    settings_beat_gap = settings_properties["jianpu_beat_gap_percent"]["anyOf"][0]
    assert settings_system_gap["minimum"] == 20
    assert settings_system_gap["maximum"] == 180
    assert settings_short_note_gap["minimum"] == 20
    assert settings_short_note_gap["maximum"] == 180
    assert settings_beat_gap["minimum"] == 0
    assert settings_beat_gap["maximum"] == 200

    live_properties = schemas["LiveJianpuSvgRequest"]["properties"]
    assert live_properties["jianpu_break_beams_at_beat"]["default"] is False

    multipart_properties = schemas["Body_run_pipeline_pipeline_post"]["properties"]
    assert multipart_properties["jianpu_system_gap_percent"]["minimum"] == 20
    assert multipart_properties["jianpu_system_gap_percent"]["maximum"] == 180
    assert multipart_properties["jianpu_short_note_gap_percent"]["minimum"] == 20
    assert multipart_properties["jianpu_short_note_gap_percent"]["maximum"] == 180
    assert multipart_properties["jianpu_beat_gap_percent"]["minimum"] == 0
    assert multipart_properties["jianpu_beat_gap_percent"]["maximum"] == 200

    preserving = schemas["PreservingLayoutRequest"]["properties"]
    assert "jianpu_content_scale_percent" not in preserving


def test_settings_rejects_unsupported_target_key(tmp_path: Path) -> None:
    app = create_app()
    dao = SettingsDao(tmp_path / "settings.db")
    service = SettingsService(dao)
    service.set("work_dir", str(tmp_path / "work"))
    app.dependency_overrides[get_settings_actions] = lambda: SettingsActions(service)

    response = TestClient(app).put("/settings", json={"target_key": "D#"})

    assert response.status_code == 422


def test_settings_persist_audiveris_binarization_threshold(tmp_path: Path) -> None:
    app = create_app()
    service = SettingsService(SettingsDao(tmp_path / "settings.db"))
    app.dependency_overrides[get_settings_actions] = lambda: SettingsActions(service)
    client = TestClient(app)

    assert client.get("/settings").json()["audiveris_binarization_threshold"] == 0
    updated = client.put("/settings", json={"audiveris_binarization_threshold": 210})
    assert updated.status_code == 200
    assert updated.json()["audiveris_binarization_threshold"] == 210
    assert service.load().audiveris_binarization_threshold == 210
    assert (
        client.put(
            "/settings", json={"audiveris_binarization_threshold": 255}
        ).status_code
        == 422
    )


def test_settings_persist_pdf_upload_dpi(tmp_path: Path) -> None:
    app = create_app()
    service = SettingsService(SettingsDao(tmp_path / "settings.db"))
    app.dependency_overrides[get_settings_actions] = lambda: SettingsActions(service)
    client = TestClient(app)

    assert client.get("/settings").json()["pdf_upload_dpi"] == 0
    updated = client.put("/settings", json={"pdf_upload_dpi": 400})
    assert updated.status_code == 200
    assert updated.json()["pdf_upload_dpi"] == 400
    assert service.load().pdf_upload_dpi == 400
    assert (
        client.put("/settings", json={"pdf_upload_dpi": 0}).json()["pdf_upload_dpi"]
        == 0
    )
    assert client.put("/settings", json={"pdf_upload_dpi": 71}).status_code == 422
    assert client.put("/settings", json={"pdf_upload_dpi": 601}).status_code == 422


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


def test_history_page_schema_exposes_optional_anchor_baseline_requests() -> None:
    schemas = create_app().openapi()["components"]["schemas"]
    fields = {"text_anchor_baseline_text", "text_anchor_baseline_anchors"}

    for schema_name in ("PageCreate", "PageUpdate", "BatchSavePage"):
        schema = schemas[schema_name]
        assert fields <= schema["properties"].keys()
        assert fields.isdisjoint(schema.get("required", []))

    response = schemas["PageResponse"]
    assert fields <= response["properties"].keys()
    assert response["properties"]["text_anchor_baseline_text"].get("type") == "string"


def test_legacy_page_update_refreshes_anchor_baseline_from_current_fields(
    tmp_path: Path,
) -> None:
    service = HistoryService(tmp_path / "history.db")
    batch = service.create_batch([HistoryPage(input_file_name="score.png")])
    actions = HistoryActions(service)
    anchor = {
        "source_id": "s1:i1",
        "start_utf16": 0,
        "end_utf16": 1,
        "role": "note",
        "valid": True,
    }

    updated = actions.update_history_page(
        batch.pages[0].id,
        PageUpdate(jianpu_text="1 |", text_anchors=[anchor]),
    )

    assert updated.text_anchor_baseline_text == "1 |"
    assert updated.text_anchor_baseline_anchors[0].source_id == "s1:i1"


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
                    "status": "processing",
                    "error_message": "",
                }
            ]
        },
    ).json()
    page_id = created["pages"][0]["id"]
    client.patch(
        f"/history/pages/{page_id}",
        json={
            "status": "completed",
            "error_message": "",
        },
    )

    response = client.get(f"/history/pages/{page_id}")

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
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


def test_pdf_page_preview_route_returns_rotated_png(tmp_path: Path) -> None:
    fitz = pytest.importorskip("fitz")
    app = create_app()
    uploads = UploadService(ToolConfig(work_dir=tmp_path / "work"))
    source = tmp_path / "score.pdf"
    with fitz.open() as doc:
        doc.new_page(width=200, height=400)
        doc.save(source)
    file_id = uploads.register(source)
    app.dependency_overrides[get_file_actions] = lambda: FileActions(uploads=uploads)

    response = TestClient(app).get(
        f"/files/{file_id}/pdf-page",
        params={"page_index": 0, "target_width": 320, "rotation": 90},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["x-image-width"] == "320"
    assert response.headers["x-image-height"] == "160"
    assert response.content.startswith(b"\x89PNG")
    assert (
        TestClient(app)
        .get(
            f"/files/{file_id}/pdf-page",
            params={"page_index": 0, "rotation": 45},
        )
        .status_code
        == 400
    )


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


def test_file_rotate_route_returns_a_rotated_copy(tmp_path: Path) -> None:
    from PIL import Image

    app = create_app()
    uploads = UploadService(ToolConfig(work_dir=tmp_path / "work"))
    source = tmp_path / "page.png"
    Image.new("RGB", (4, 2), "white").save(source)
    file_id = uploads.register(source)
    app.dependency_overrides[get_file_actions] = lambda: FileActions(uploads=uploads)

    response = TestClient(app).post(
        f"/files/{file_id}/rotate",
        json={"direction": "right"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["filename"] == "page.png"
    rotated_path = uploads.get_path(payload["file_id"])
    assert rotated_path is not None
    with Image.open(rotated_path) as rotated:
        assert rotated.size == (2, 4)


def test_export_midi_route_writes_and_registers_downloadable_file(tmp_path) -> None:
    import mido

    config = ToolConfig(work_dir=tmp_path / "work")
    uploads = UploadService(config)
    source = tmp_path / "score.musicxml"
    source.write_text(
        '<score-partwise version="4.0"><part-list><score-part id="P1">'
        '<part-name>Music</part-name></score-part></part-list><part id="P1">'
        '<measure number="1"><attributes><divisions>1</divisions>'
        "<time><beats>4</beats><beat-type>4</beat-type></time></attributes>"
        "<note><pitch><step>C</step><octave>4</octave></pitch>"
        "<duration>4</duration><type>whole</type></note></measure></part></score-partwise>",
        encoding="utf-8",
    )
    musicxml_id = uploads.register(source)
    response = asyncio.run(
        export_midi(
            req=ExportMidiRequest(musicxml_file_id=musicxml_id),
            actions=ExportActions(uploads=uploads),
        )
    )
    assert response.filename == "score.mid"
    output = uploads.get_path(response.file_id)
    assert output is not None
    midi = mido.MidiFile(output)
    assert any(message.type == "note_on" and message.note == 60 for message in midi)


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
