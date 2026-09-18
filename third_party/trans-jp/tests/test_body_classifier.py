from __future__ import annotations

from pathlib import Path
import json
from trans_jp.models.candidates import CandidateRegistry, LocatedCandidate
from trans_jp.models.geometry import Box
from trans_jp.models.classification import CandidateBatchRequest
from trans_jp.recognition.candidate_classifier import (
    parse_candidate_response,
    classify_batches,
)
from trans_jp.structure.body_assembler import assemble_body_tokens, partition_candidates
from trans_jp.models.contracts import RowSegment, CompletionResult


def registry(count=25):
    return CandidateRegistry(
        0,
        1000,
        100,
        tuple(
            LocatedCandidate(
                f"r0000:c{i:04}", "digit", Box(i * 30 + 5, 30, 15, 25), (0,), ()
            )
            for i in range(count)
        ),
    )


def request(reg=None):
    reg = reg or registry(3)
    return CandidateBatchRequest(
        "r0000:b0000",
        Path("row.png"),
        Path("atlas.png"),
        reg,
        tuple(c.candidate_id for c in reg.candidates),
    )


def response(req, label="3"):
    return json.dumps(
        {
            "schema_version": 3,
            "items": [
                {
                    "candidate_id": cid,
                    "label": label,
                    "kind": "digit",
                    "confidence": 0.9,
                    "status": "recognized",
                }
                for cid in req.candidate_ids
            ],
            "unresolved": [],
        }
    )


def test_partition_covers_every_eligible_candidate_once():
    batches = partition_candidates(registry())
    assert list(map(len, batches)) == [12, 12, 1]
    assert len(set(c.candidate_id for batch in batches for c in batch)) == 25


def test_duplicate_missing_foreign_and_invalid_label_are_rejected():
    req = request()
    data = json.loads(response(req))
    data["items"].append(data["items"][0])
    data["items"][1]["label"] = "8"
    data["items"][2]["candidate_id"] = "r9999:c0000"
    parsed = parse_candidate_response(json.dumps(data), req)
    assert len(parsed.items) == 3
    assert all(item.status != "recognized" for item in parsed.items)
    assert parsed.warnings


def test_one_failed_batch_does_not_discard_successes():
    req = request()
    other = CandidateBatchRequest(
        "r0000:b0001",
        req.image_path,
        req.atlas_path,
        req.registry,
        (req.candidate_ids[2],),
    )
    first = CandidateBatchRequest(
        req.batch_id,
        req.image_path,
        req.atlas_path,
        req.registry,
        req.candidate_ids[:2],
    )

    class Client:
        def classify(self, batch):
            if batch.batch_id.endswith("1"):
                raise RuntimeError("offline")
            return CompletionResult(response(batch), "stop")

    results = classify_batches([first, other], Client(), concurrency=2)
    assert results[0].status == "classified"
    assert results[1].status == "batch_request_failed"
    row = RowSegment(0, 0, 100, Path("row.png"), 1000, 100)
    result = assemble_body_tokens(req.registry, results, row)
    assert len(result.tokens) == 2
    assert not result.complete and result.unresolved_candidates


def test_omission_does_not_shift_ids_or_invent_rests():
    req = request()
    data = json.loads(response(req))
    data["items"].pop(0)
    parsed = parse_candidate_response(json.dumps(data), req)
    row = RowSegment(0, 0, 100, Path("row.png"), 1000, 100)
    result = assemble_body_tokens(req.registry, [parsed], row)
    assert [t.candidate_ids for t in result.tokens] == [
        (req.candidate_ids[1],),
        (req.candidate_ids[2],),
    ]
    assert all(t.text == "3" for t in result.tokens)


def test_pipeline_v3_and_replay_tamper(tmp_path):
    from trans_jp.models.contracts import CliConfig, LlmConfig
    from trans_jp.pipeline.runner import run
    from trans_jp.io.output_writer import write_outputs
    from trans_jp.io.replay_reader import ReplayClient
    from trans_jp.models.errors import EngineError
    from dataclasses import replace
    import pytest

    source = Path(__file__).parents[1] / "examples/sample_jianpu.png"

    class Client:
        def classify(self, req):
            values = []
            for cid in req.candidate_ids:
                c = next(c for c in req.registry.candidates if c.candidate_id == cid)
                values.append(
                    {
                        "candidate_id": cid,
                        "label": "barline" if c.kind == "barline" else "3",
                        "kind": c.kind,
                        "status": "recognized",
                        "confidence": 0.9,
                    }
                )
            return CompletionResult(
                json.dumps({"schema_version": 3, "items": values}), "stop"
            )

    config = CliConfig(
        source, tmp_path / "out", LlmConfig("", "", "fixture"), debug=True
    )
    result = run(config, Client())
    write_outputs(result, config.output_dir)
    assert all(row.schema_version == 3 for row in result.rows)
    assert result.source_map["sheets"][0]["elements"]
    replay = run(
        replace(config, output_dir=tmp_path / "replay"),
        ReplayClient(config.output_dir / "rows"),
    )
    assert replay.overlay_svg == result.overlay_svg
    assert replay.source_map == result.source_map
    manifest = json.loads((config.output_dir / "manifest.json").read_text())
    assert all(len(batch["candidate_ids"]) <= 12 for batch in manifest["batches"])
    raw = next((config.output_dir / "batches").glob("*-raw.txt"))
    raw.write_text("{}")
    with pytest.raises(EngineError, match="回放校验失败"):
        run(
            replace(config, output_dir=tmp_path / "invalid"),
            ReplayClient(config.output_dir / "rows"),
        )
    assert not (tmp_path / "invalid").exists()


def test_global_concurrency_bound_and_order():
    import threading
    import time
    from dataclasses import replace

    req = request()
    requests = [replace(req, batch_id=f"r0000:b{i:04}") for i in range(7)]

    class Client:
        active = 0
        peak = 0
        lock = threading.Lock()

        def classify(self, batch):
            with self.lock:
                self.active += 1
                self.peak = max(self.peak, self.active)
            time.sleep(0.01)
            with self.lock:
                self.active -= 1
            return CompletionResult(response(batch), "stop")

    client = Client()
    results = classify_batches(requests, client, concurrency=2)
    assert client.peak == 2
    assert [r.batch_id for r in results] == [r.batch_id for r in requests]


def test_transport_retries_are_bounded_and_auth_is_not_retried(monkeypatch):
    import httpx
    import pytest
    from trans_jp.recognition.llm_client import LlmClient
    from trans_jp.models.contracts import LlmConfig

    monkeypatch.setattr(
        "trans_jp.recognition.llm_client.image_to_data_url",
        lambda *args, **kwargs: "data:image/png;base64,AA==",
    )
    monkeypatch.setattr("trans_jp.recognition.llm_client.time.sleep", lambda _: None)
    client = LlmClient(LlmConfig("key", "http://test", "test"), "unused")
    calls = []

    def send(*args, **kwargs):
        calls.append(kwargs)
        raise httpx.ReadError("disconnected")

    monkeypatch.setattr(client, "_post", send)
    with pytest.raises(RuntimeError):
        client.classify(request())
    assert len(calls) == 3
    calls.clear()

    def unauthorized(*args, **kwargs):
        calls.append(kwargs)
        req = httpx.Request("POST", "http://test")
        raise httpx.HTTPStatusError(
            "unauthorized", request=req, response=httpx.Response(401, request=req)
        )

    monkeypatch.setattr(client, "_post", unauthorized)
    with pytest.raises(httpx.HTTPStatusError):
        client.classify(request())
    assert len(calls) == 1


def test_conflicting_ink_is_withheld_without_rejecting_other_notes():
    from dataclasses import replace

    req = request()
    candidates = list(req.registry.candidates)
    candidates[0] = replace(candidates[0], conflicts=(candidates[1].candidate_id,))
    candidates[1] = replace(candidates[1], conflicts=(candidates[0].candidate_id,))
    reg = replace(req.registry, candidates=tuple(candidates))
    req = replace(req, registry=reg)
    parsed = parse_candidate_response(response(req), req)
    row = RowSegment(0, 0, 100, Path("row.png"), 1000, 100)
    assembled = assemble_body_tokens(reg, [parsed], row)
    assert len(assembled.tokens) == 1
    assert assembled.tokens[0].candidate_ids == (candidates[2].candidate_id,)


def test_chord_projection_preserves_visual_vertical_order():
    from dataclasses import replace
    from trans_jp.matching.body_matcher import match_body_row
    from trans_jp.models.raster import RowAnalysis

    reg = registry(3)
    reg = replace(
        reg,
        candidates=tuple(
            replace(c, bounds=Box(50, 10 + i * 30, 15, 20), band_ids=(i,))
            for i, c in enumerate(reg.candidates)
        ),
    )
    req = request(reg)
    data = json.loads(response(req))
    for item, label in zip(data["items"], ["1", "5", "3"]):
        item["label"] = label
    parsed = parse_candidate_response(json.dumps(data), req)
    row = RowSegment(0, 0, 100, Path("row.png"), 1000, 100)
    assembled = assemble_body_tokens(reg, [parsed], row)
    assert assembled.tokens[0].text == "[1+5+3]"
    matched = match_body_row(assembled, RowAnalysis((), (), (), (), 1))
    assert [p.value for p in matched.tokens[0].geometry.primitives] == ["1", "5", "3"]


def test_all_batches_failed_preserves_diagnostics_before_exit(tmp_path):
    from trans_jp.pipeline.runner import run
    from trans_jp.models.contracts import CliConfig, LlmConfig
    from trans_jp.models.errors import EngineError
    import pytest

    class Failure:
        def classify(self, req):
            raise RuntimeError("offline")

    out = tmp_path / "fail"
    with pytest.raises(EngineError, match="所有主体批次失败"):
        run(
            CliConfig(
                Path(__file__).parents[1] / "examples/sample_jianpu.png",
                out,
                LlmConfig("", "", "test"),
            ),
            Failure(),
        )
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["batches"] and manifest["row_responses"]
    assert all(
        json.loads(
            (
                out
                / "batches"
                / next(name for name in b["files"] if name.endswith("-result.json"))
            ).read_text()
        )["status"]
        == "batch_request_failed"
        for b in manifest["batches"]
    )


def test_truncated_valid_json_is_not_accepted():
    class Truncated:
        def classify(self, req):
            return CompletionResult(response(req), "length")

    results = classify_batches([request()], Truncated())
    assert results[0].status == "batch_response_invalid"
    assert results[0].finish_reason == "length"
    assert all(i.status != "recognized" for i in results[0].items)


def test_replay_rejects_other_batch_artifact_tampering(tmp_path):
    from trans_jp.models.contracts import CliConfig, LlmConfig
    from trans_jp.pipeline.runner import run
    from trans_jp.io.output_writer import write_outputs
    from trans_jp.io.replay_reader import ReplayClient
    from trans_jp.models.errors import EngineError
    import pytest

    class Client:
        def classify(self, req):
            return CompletionResult(
                json.dumps(
                    {
                        "schema_version": 3,
                        "items": [],
                        "unresolved": [
                            {"candidate_id": cid, "reason": "unknown"}
                            for cid in req.candidate_ids
                        ],
                    }
                ),
                "stop",
            )

    source = Path(__file__).parents[1] / "examples/sample_jianpu.png"
    config = CliConfig(source, tmp_path / "original", LlmConfig("", "", "test"))
    result = run(config, Client())
    write_outputs(result, config.output_dir)
    files = [
        next((config.output_dir / "batches").glob("*-request.json")),
        next((config.output_dir / "batches").glob("*-result.json")),
        next((config.output_dir / "batches").glob("*-atlas.png")),
        next((config.output_dir / "rows").glob("*.json")),
    ]
    for i, path in enumerate(files):
        original = path.read_bytes()
        path.write_bytes(original + b"changed")
        with pytest.raises(EngineError, match="回放校验失败"):
            run(
                CliConfig(source, tmp_path / f"replay{i}", config.llm),
                ReplayClient(config.output_dir / "rows"),
            )
        assert not (tmp_path / f"replay{i}").exists()
        path.write_bytes(original)


def test_v3_manifest_cannot_be_bypassed_by_downgrading_every_row(tmp_path):
    from trans_jp.io.replay_reader import ReplayClient
    from trans_jp.models.errors import EngineError
    import pytest

    rows = tmp_path / "rows"
    rows.mkdir()
    (rows / "row_0.json").write_text(json.dumps({"schema_version": 1, "tokens": []}))
    (tmp_path / "manifest.json").write_text(json.dumps({"version": 3}))
    with pytest.raises(EngineError, match="降级"):
        ReplayClient(rows).validate_run({}, [registry()])
