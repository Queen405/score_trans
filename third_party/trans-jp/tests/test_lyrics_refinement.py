from __future__ import annotations

from dataclasses import asdict
import json
import httpx
import numpy as np
from PIL import Image
import pytest
from trans_jp.models.contracts import CompletionResult, RowSegment
from trans_jp.models.candidates import LocatedCandidate, CandidateRegistry
from trans_jp.models.geometry import Box, Transform
from trans_jp.models.lyrics import TextRegion, LyricsResult
from trans_jp.pipeline.lyrics_refinement import refine_regions
from trans_jp.pipeline.text_evidence import TextEvidenceSession
from trans_jp.matching.text_conflicts import (
    body_text_conflicts,
    finish_body_decisions,
    active_text_exclusions,
)
from trans_jp.io.lyrics_artifacts import (
    result_payload,
    write_lyrics_manifest,
    validate_lyrics_replay,
)
from trans_jp.recognition.lyrics import ConfiguredTextRecognizer
from trans_jp.rendering.lyrics import pending_overlay


def decision(identity, role="unknown", status="unresolved"):
    return {
        "id": identity,
        "role": role,
        "status": status,
        "text": None,
        "reason": "missing_or_duplicate",
    }


class RescueClient:
    def __init__(self, mode):
        self.mode = mode
        self.calls = []

    def recognize_text(self, request):
        raise AssertionError("rescue must never use the normal retry wrapper")

    def recognize_text_once(self, request):
        self.calls.append(request.request_id)
        if self.mode == "auth":
            resp = httpx.Response(
                401, request=httpx.Request("POST", "https://example.invalid")
            )
            raise httpx.HTTPStatusError(
                "unauthorized", request=resp.request, response=resp
            )
        if self.mode == "timeout":
            raise httpx.ReadTimeout("test timeout")
        if self.mode == "empty":
            return CompletionResult('{"schema_version":1,"items":[]}')
        return CompletionResult(
            json.dumps(
                {
                    "schema_version": 1,
                    "items": [
                        {"id": i["id"], "role": "notation", "text": None}
                        for i in request.items
                    ],
                }
            )
        )


@pytest.mark.parametrize(
    "mode,expected_calls", [("empty", 2), ("timeout", 2), ("auth", 1), ("ok", 1)]
)
def test_rescue_has_total_http_budget_and_no_nested_retry(
    tmp_path, mode, expected_calls
):
    c = RescueClient(mode)
    session = TextEvidenceSession(tmp_path, c, 4, None, False)
    region = TextRegion("t0", Box(0, 0, 80, 30), Box(0, 0, 80, 30))
    _, ds, history = refine_regions(
        Image.new("RGB", (100, 60), "white"),
        np.full((60, 100), 255, np.uint8),
        Transform(),
        [region],
        {"t0": decision("t0")},
        session,
        1,
        [],
        [],
    )
    assert len(c.calls) == expected_calls
    assert len([e for e in history if "attempt" in e]) == expected_calls
    if mode == "ok":
        assert ds["t0"]["role"] == "notation"
    else:
        assert ds["t0"]["role"] == "unknown"
    if mode == "auth":
        assert ds["t0"]["request_status"] == "auth_failed"


def test_initial_auth_failure_never_rescued(tmp_path):
    client = RescueClient("ok")
    session = TextEvidenceSession(tmp_path, client, 4, None, False)
    region = TextRegion("t0", Box(0, 0, 80, 30), Box(0, 0, 80, 30))
    refine_regions(
        Image.new("RGB", (100, 60), "white"),
        np.full((60, 100), 255, np.uint8),
        Transform(),
        [region],
        {"t0": {**decision("t0"), "request_status": "auth_failed"}},
        session,
        1,
        [],
        [],
    )
    assert not client.calls


def test_children_override_only_covered_parent_ink_and_cannot_release_text(tmp_path):
    row = RowSegment(0, 0, 100, tmp_path / "row.png", 200, 100)
    cs = tuple(
        LocatedCandidate(f"c{i}", "digit", Box(10 + i * 35, 10, 12, 20), (0,), ())
        for i in range(3)
    )
    lyric = LocatedCandidate("lyric", "digit", Box(10, 65, 15, 20), (1,), ())
    uncovered = LocatedCandidate("uncovered", "digit", Box(170, 10, 12, 20), (0,), ())
    reg = CandidateRegistry(0, 200, 100, (*cs, lyric, uncovered))

    def region(identity, role, box, parent=None):
        return {
            **decision(identity, role, "observed"),
            "bounds": asdict(box),
            "bounds_work": asdict(box),
            "parent_region_id": parent,
            "request_id": "rescue-parent-0",
        }

    r = LyricsResult(
        regions=[
            region("parent", "mixed", Box(0, 0, 200, 100)),
            region("music", "notation", Box(5, 5, 100, 30), "parent"),
            region("text", "lyrics", Box(5, 60, 25, 30), "parent"),
        ]
    )
    blocked = body_text_conflicts([row], [reg], r)
    assert not set(blocked) & {"c0", "c1", "c2"}
    assert (
        blocked["lyric"] == "text_excluded"
        and blocked["uncovered"] == "text_music_conflict"
    )
    exclusions = active_text_exclusions(r)
    assert not any(b.x <= 16 < b.right and b.y <= 20 < b.bottom for b in exclusions)
    assert any(b.x <= 160 < b.right and b.y <= 50 < b.bottom for b in exclusions)
    observations = {
        "uncovered": {"label": "7", "status": "recognized", "batch_id": "b"}
    }
    finish_body_decisions(r, [], observations)
    pending = {p["candidate_id"]: p for p in r.pending}
    assert pending["uncovered"]["observed_label"] == "7"
    assert "lyric" not in pending
    svg = pending_overlay(r, 200, 100)
    assert "stroke-dasharray" in svg and "7?" in svg
    assert "None?" not in svg


def test_legacy_payload_and_version_binding(tmp_path):
    r = LyricsResult(version=3)
    payload = result_payload(r)
    assert "pending" not in payload and "decisions" not in payload
    marker = write_lyrics_manifest(tmp_path, {}, payload)
    assert marker["version"] == 3
    assert validate_lyrics_replay(tmp_path, {}, marker) == payload
    wrong = {**marker, "version": 4}
    with pytest.raises(ValueError):
        validate_lyrics_replay(tmp_path, {}, wrong)


def test_once_adapter_performs_exactly_one_post(monkeypatch, tmp_path):
    from trans_jp.models.contracts import LlmConfig
    from trans_jp.models.lyrics import TextRequest

    client = ConfiguredTextRecognizer(
        LlmConfig("fake", "https://example.invalid", "test")
    )
    image = tmp_path / "a.png"
    Image.new("RGB", (20, 20), "white").save(image)
    calls = []

    def post(*args, **kwargs):
        calls.append(1)
        raise httpx.ReadTimeout("timeout")

    monkeypatch.setattr(client.client, "_post", post)
    req = TextRequest("rescue", image, ({"id": "a"},), "region_review", "hash")
    with pytest.raises(httpx.ReadTimeout):
        client.recognize_text_once(req)
    assert len(calls) == 1


def test_real_v3_replay_and_explicit_v4_recovery(tmp_path, monkeypatch):
    from pathlib import Path
    import trans_jp.pipeline.runner as runner
    from trans_jp.models.contracts import CliConfig, LlmConfig
    from trans_jp.io.output_writer import write_outputs

    root = Path(__file__).parents[1]
    old = json.loads(
        (root / "tests/fixtures/lyrics/frozen_development.json").read_text(
            encoding="utf-8"
        )
    )["pages"]["image copy 10"]
    added = json.loads(
        (root / "tests/fixtures/lyrics/frozen_refinement.json").read_text(
            encoding="utf-8"
        )
    )["pages"]["image copy 10"]

    class Frozen:
        calls = []

        def __init__(self, config):
            pass

        def recognize_text(self, request):
            record = old["text"].get(request.request_id) or added[request.request_id]
            assert request.sha256 == record["sha256"]
            r = record["response"]
            if r["failure"]:
                raise RuntimeError("frozen failure")
            return CompletionResult(r["content"], r["finish_reason"])

        def recognize_text_once(self, request):
            self.calls.append(request.request_id)
            return self.recognize_text(request)

    class Bodies:
        def classify(self, request):
            r = old["bodies"][request.batch_id]
            assert r["registry_sha256"] == request.registry.digest
            return CompletionResult(r["response"], r["finish_reason"])

    monkeypatch.setattr(runner, "ConfiguredTextRecognizer", Frozen)
    recognize = runner.recognize_lyrics

    def legacy(*args, **kwargs):
        return recognize(*args, **kwargs, version=3)

    monkeypatch.setattr(runner, "recognize_lyrics", legacy)
    source = root / "examples/image copy 10.png"
    cfg = CliConfig(
        source,
        tmp_path / "legacy",
        LlmConfig("fake", "fake", "fake"),
        lyrics_mode="recognize",
        debug=True,
    )
    before = runner.run(cfg, Bodies())
    write_outputs(before, cfg.output_dir)
    monkeypatch.setattr(runner, "recognize_lyrics", recognize)
    cfg = CliConfig(
        source,
        tmp_path / "legacy-replay",
        LlmConfig("", "", ""),
        body_responses_dir=tmp_path / "legacy/rows",
        melody_review=False,
        debug=True,
    )
    replay = runner.run(cfg)
    assert replay.lyrics == before.lyrics and replay.overlay_svg == before.overlay_svg
    assert not Frozen.calls
    items = {}
    for batch in old["bodies"].values():
        data = json.loads(batch["response"])
        for item in data.get("items", []):
            items[item["candidate_id"]] = item
    supplemental = []

    class Supplement:
        def __init__(self, *args):
            pass

        def classify(self, request):
            supplemental.extend(request.candidate_ids)
            return CompletionResult(
                json.dumps(
                    {
                        "schema_version": 3,
                        "items": [
                            items[cid] for cid in request.candidate_ids if cid in items
                        ],
                    }
                )
            )

    monkeypatch.setattr(runner, "LlmClient", Supplement)
    cfg = CliConfig(
        source,
        tmp_path / "refined",
        LlmConfig("fake", "fake", "fake"),
        body_responses_dir=tmp_path / "legacy/rows",
        lyrics_mode="recognize",
        lyrics_refine=True,
        melody_review=False,
        debug=True,
    )
    after = runner.run(cfg)
    write_outputs(after, cfg.output_dir)
    assert after.lyrics["version"] == 4 and Frozen.calls
    assert supplemental
    truth = json.loads(
        (root / "tests/fixtures/lyrics/recovery49.json").read_text(encoding="utf-8")
    )
    accepted = {
        cid: t.text for r in after.rows for t in r.tokens for cid in t.candidate_ids
    }
    assert all(accepted.get(n["candidate_id"]) == n["label"] for n in truth["notes"])
    decisions = {d["candidate_id"]: d for d in after.lyrics["decisions"]}
    assert all(
        decisions[n["candidate_id"]]["state"] == "accepted" for n in truth["notes"]
    )
    count = len(Frozen.calls)
    cfg = CliConfig(
        source,
        tmp_path / "v4-replay",
        LlmConfig("", "", ""),
        body_responses_dir=tmp_path / "refined/rows",
        melody_review=False,
        debug=True,
    )
    frozen = runner.run(cfg)
    assert len(Frozen.calls) == count
    assert frozen.lyrics == after.lyrics and frozen.overlay_svg == after.overlay_svg
    assert (tmp_path / "refined/pending-notes.json").exists()
