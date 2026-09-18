from __future__ import annotations

import base64
from dataclasses import replace
from io import BytesIO
import json
from pathlib import Path
import pytest
from PIL import Image
from trans_jp.models.contracts import CliConfig, CompletionResult, LlmConfig
from trans_jp.models.errors import EngineError
from trans_jp.pipeline.runner import run
from trans_jp.io.output_writer import write_outputs
from trans_jp.io.replay_reader import ReplayClient
from trans_jp.recognition.llm_client import image_to_data_url
from trans_jp.recognition.response_parser import parse_row_response

SOURCE = Path(__file__).parents[1] / "examples/sample_jianpu.png"


class VerifiedSimpleClient:
    """Manually checked simple page: digit bodies ordered left to right."""

    def transcribe_request_with_retry(self, request, prompt, **kwargs):
        index = request.registry.row_index
        if index == 0:
            data = {
                "schema_version": 2,
                "row_type": "header",
                "row_text": "1=C\n4/4\ntempo=85",
                "tokens": [],
            }
        else:
            sequences = {
                1: ["1", "2", "3", "4", "5", "6", "7", "1'"],
                2: ["2", "3", "4", "5", "6", "7", "1'", "2'"],
                3: ["3", "4", "5", "6", "7", "1", "2", "3"],
            }
            # Main body band, excluding small apostrophes in this synthetic score.
            digits = [
                c
                for c in request.registry.candidates
                if c.kind == "digit" and c.bounds.height > 30 and c.bounds.width > 8
            ]
            bars = [
                c
                for c in request.registry.candidates
                if c.kind == "barline" and c.bounds.height > 30
            ]
            # Vertical strokes already identified as bars cannot also be digits.
            digits = [
                c
                for c in digits
                if not any(b.candidate_id in c.conflicts for b in bars)
            ]
            digits.sort(key=lambda c: c.bounds.x)
            assert len(digits) == 8
            tokens = [
                {"text": text, "role": "note", "candidate_ids": [c.candidate_id]}
                for text, c in zip(sequences[index], digits, strict=True)
            ]
            for bar in sorted(bars, key=lambda c: -c.bounds.x):
                before = sum(c.bounds.cx < bar.bounds.cx for c in digits)
                tokens.insert(
                    before,
                    {
                        "text": "||" if len(bar.lines) == 2 else "|",
                        "role": "barline",
                        "candidate_ids": [bar.candidate_id],
                    },
                )
            data = {
                "schema_version": 2,
                "row_type": "notation",
                "row_text": " ".join(t["text"] for t in tokens),
                "tokens": tokens,
            }
        return CompletionResult(json.dumps(data), "stop")


@pytest.fixture
def v2_run(tmp_path):
    config = CliConfig(
        SOURCE, tmp_path / "run", LlmConfig("", "", "fixture"), debug=True
    )
    result = run(config, VerifiedSimpleClient())
    write_outputs(result, config.output_dir)
    return config, result


def test_real_simple_page_v2_locates_every_body(v2_run):
    config, result = v2_run
    row = result.rows[1]
    assert len(row.tokens) == 10
    assert all(t.geometry.status in ("matched", "partial") for t in row.tokens)
    bodies = [t.geometry.bodies[0] for t in row.tokens if t.geometry.bodies]
    assert [b.cx for b in bodies] == sorted(b.cx for b in bodies)
    assert bodies[0].cx < 80  # 1 stays on the original 1, never shifts onto 3.
    assert len(result.source_map["sheets"][0]["elements"]) == 30
    assert (config.output_dir / "requests/row_1-response.txt").is_file()


def test_v2_replay_is_identical_and_offline(v2_run, tmp_path):
    config, first = v2_run
    second = run(
        replace(config, output_dir=tmp_path / "replay"),
        ReplayClient(config.output_dir / "rows"),
    )
    assert second.overlay_svg == first.overlay_svg
    assert second.source_map == first.source_map


@pytest.mark.parametrize("tamper", ["source", "registry", "manifest", "parameters"])
def test_v2_replay_rejects_mismatched_provenance(v2_run, tmp_path, tamper):
    config, _ = v2_run
    other = replace(config, output_dir=tmp_path / "replay")
    if tamper == "source":
        image = Image.open(SOURCE).convert("RGB")
        image.putpixel((0, 0), (0, 0, 0))
        path = tmp_path / "changed.png"
        image.save(path)
        other = replace(other, input_path=path)
    elif tamper == "registry":
        path = config.output_dir / "requests/row_1-candidates.json"
        data = json.loads(path.read_text())
        data["candidates"][0]["bounds"]["x"] += 1
        path.write_text(json.dumps(data))
    elif tamper == "manifest":
        (config.output_dir / "manifest.json").write_text("{}")
    else:
        other = replace(other, min_image_edge=2000)
    with pytest.raises(EngineError, match="回放校验失败"):
        run(other, ReplayClient(config.output_dir / "rows"))
    assert not other.output_dir.exists()


def test_no_schema_downgrade_for_online_clients(tmp_path):
    class BadClient:
        def transcribe_request_with_retry(self, request, prompt, **kwargs):
            return CompletionResult(
                json.dumps(
                    {
                        "row_text": "1",
                        "tokens": [{"text": "1", "role": "note", "x": 0.05, "w": 0.03}],
                    }
                ),
                "stop",
            )

    result = run(
        CliConfig(SOURCE, tmp_path / "out", LlmConfig("", "", "")), BadClient()
    )
    assert not result.source_map["sheets"][0]["elements"]
    assert all(r.schema_version == 2 for r in result.rows)


def test_png_wire_and_atlas_resolution(tmp_path):
    path = tmp_path / "wide.png"
    Image.new("RGB", (2500, 100), "white").save(path)
    for max_edge, expected in [(2000, (2000, 80)), (None, (2500, 100))]:
        url = image_to_data_url(path, max_edge=max_edge)
        assert url.startswith("data:image/png;base64,")
        with Image.open(BytesIO(base64.b64decode(url.split(",", 1)[1]))) as image:
            assert image.size == expected


def test_unresolved_is_not_silently_converted_to_rest():
    data = parse_row_response(
        json.dumps(
            {
                "schema_version": 2,
                "row_text": "",
                "tokens": [],
                "unresolved_candidates": [
                    {"candidate_id": "r0000:c0000", "reason": "blur"}
                ],
            }
        )
    )
    assert data["tokens"] == []
    assert data["unresolved_candidates"]


def test_multi_image_request_keeps_png_atlases_on_truncation_retry(
    tmp_path, monkeypatch
):
    from trans_jp.models.candidates import CandidateRegistry, RowRecognitionRequest
    from trans_jp.recognition.llm_client import LlmClient

    path = tmp_path / "row.png"
    atlas = tmp_path / "atlas.png"
    Image.new("RGB", (2500, 100), "white").save(path)
    Image.new("RGB", (1152, 640), "white").save(atlas)
    requests = []

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "choices": [
                    {
                        "finish_reason": "length" if len(requests) == 1 else "stop",
                        "message": {"content": "{}"},
                    }
                ]
            }

    def post(url, **kwargs):
        requests.append(kwargs["json"])
        return Response()

    monkeypatch.setattr("trans_jp.recognition.llm_client.httpx.post", post)
    client = LlmClient(LlmConfig("test", "http://test", "test"), "system")
    request = RowRecognitionRequest(path, (atlas,), CandidateRegistry(0, 2500, 100, ()))
    client.transcribe_request_with_retry(request, "prompt")
    assert len(requests) == 2
    images = [r["messages"][1]["content"][1:] for r in requests]
    assert images[0] == images[1] and len(images[0]) == 2
    with Image.open(
        BytesIO(base64.b64decode(images[0][1]["image_url"]["url"].split(",")[1]))
    ) as image:
        assert image.size == (1152, 640)
    assert "精简输出" in requests[1]["messages"][1]["content"][0]["text"]


def test_candidate_atlas_pagination_does_not_renumber():
    from trans_jp.models.candidates import CandidateRegistry, LocatedCandidate
    from trans_jp.models.geometry import Box
    from trans_jp.rendering.candidate_atlas import render_atlases

    candidates = tuple(
        LocatedCandidate(
            f"r0000:c{i:04d}", "digit", Box(i * 20 + 2, 25, 10, 20), (0,), ()
        )
        for i in range(25)
    )
    registry = CandidateRegistry(0, 600, 100, candidates)
    original = registry.digest
    pages = render_atlases(Image.new("RGB", (600, 100), "white"), registry)
    assert len(pages) == 2
    assert all(p.size == (1152, 640) for p in pages)
    assert registry.digest == original


def test_invalid_transformed_geometry_cannot_leak_to_svg_or_map():
    from trans_jp.models.contracts import RecognizedToken, RowResult, RowSegment
    from trans_jp.models.geometry import Box, Primitive, TokenGeometry
    from trans_jp.validation.checks import reject_invalid_geometry
    from trans_jp.provenance.source_map import build_source_map
    from trans_jp.overlay_generator import generate_overlay_svg

    token = RecognizedToken(
        0,
        "1",
        None,
        None,
        "note",
        geometry=TokenGeometry(
            "matched",
            bodies=[Box(90, 0, 30, 20)],
            primitives=[Primitive("glyph", Box(90, 0, 30, 20), "1")],
        ),
    )
    rows = [
        RowResult(
            RowSegment(0, 0, 100, Path("unused"), 100, 100),
            "notation",
            "1",
            [token],
            schema_version=2,
        )
    ]
    reject_invalid_geometry(rows, 100, 100)
    assert token.geometry.status == "unmatched"
    assert not build_source_map(rows, 100, 100)["sheets"][0]["elements"]
    assert "s0:r0:t0" not in generate_overlay_svg(rows, 100, 100)
