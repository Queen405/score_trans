from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import pytest
from trans_jp.models.contracts import CliConfig, LlmConfig, CompletionResult
from trans_jp.models.errors import EngineError
from trans_jp.pipeline.runner import run
from trans_jp.io.output_writer import write_outputs
from trans_jp.io.replay_reader import ReplayClient
from trans_jp.io.melody_artifacts import validate_melody_replay

SOURCE = Path(__file__).parents[1] / "examples/sample_jianpu.png"


class BodyAndReviewClient:
    def classify(self, request):
        items = []
        for cid in request.candidate_ids:
            candidate = next(
                c for c in request.registry.candidates if c.candidate_id == cid
            )
            items.append(
                {
                    "candidate_id": cid,
                    "kind": candidate.kind,
                    "label": "barline" if candidate.kind == "barline" else "3",
                    "status": "recognized",
                }
            )
        return CompletionResult(
            json.dumps({"schema_version": 3, "items": items}), "stop"
        )

    def review_attachments(self, request):
        return CompletionResult(
            json.dumps(
                {
                    "schema_version": 1,
                    "relations": [],
                    "unknown_ids": [c.candidate_id for c in request.candidates],
                }
            ),
            "stop",
        )

    def recognize_melody_metadata(self, image_path, region_ids):
        return CompletionResult(
            json.dumps(
                {
                    "schema_version": 1,
                    "key": {"value": "C", "status": "confirmed", "region_id": "page"},
                    "meter": {
                        "value": "4/4",
                        "status": "confirmed",
                        "region_id": "page",
                    },
                }
            ),
            "stop",
        )


def test_melody_pipeline_reuses_bodies_and_replays_all_evidence(tmp_path):
    config = CliConfig(
        SOURCE,
        tmp_path / "melody",
        LlmConfig("", "", "fixture"),
        debug=True,
        recognition_mode="melody",
    )
    result = run(config, BodyAndReviewClient())
    write_outputs(result, config.output_dir)
    assert result.melody["metadata"]["key"]["value"] == "C"
    assert not result.melody["melody_complete"]
    assert (config.output_dir / "melody.json").is_file()
    validate_melody_replay(config.output_dir)
    replay = run(
        replace(config, output_dir=tmp_path / "replay"),
        ReplayClient(config.output_dir / "rows"),
    )
    assert replay.melody == result.melody
    assert replay.overlay_svg == result.overlay_svg
    assert replay.source_map == result.source_map
    assert replay.text_anchors == result.text_anchors
    (config.output_dir / "melody-evidence/metadata-result.json").write_text("{}")
    with pytest.raises(EngineError, match="melody 回放校验失败"):
        run(
            replace(config, output_dir=tmp_path / "tampered"),
            ReplayClient(config.output_dir / "rows"),
        )
    assert not (tmp_path / "tampered").exists()


def test_v3_body_ids_stable_and_local_enrichment_requires_no_api(tmp_path):
    client = BodyAndReviewClient()
    config = CliConfig(
        SOURCE, tmp_path / "bodies", LlmConfig("", "", "fixture"), debug=True
    )
    body = run(config, client)
    result = run(
        replace(
            config,
            output_dir=tmp_path / "local",
            recognition_mode="melody",
            body_responses_dir=config.output_dir / "rows",
            melody_review=False,
        )
    )
    assert [(t.index, t.candidate_ids) for r in result.rows for t in r.tokens] == [
        (t.index, t.candidate_ids) for r in body.rows for t in r.tokens
    ]
    assert result.melody["metadata"]["key"]["status"] == "unknown"
    assert result.melody["review_requests"] == 0
    assert result.melody["melody_complete"] is False
    assert {e["source_id"] for e in result.source_map["sheets"][0]["elements"]} <= {
        a["source_id"] for a in result.text_anchors if a["valid"]
    }


def test_review_failure_does_not_drop_bodies(tmp_path):
    class Failed(BodyAndReviewClient):
        def review_attachments(self, request):
            raise RuntimeError("network")

        def recognize_melody_metadata(self, *args):
            raise RuntimeError("network")

    result = run(
        CliConfig(
            SOURCE,
            tmp_path / "out",
            LlmConfig("", "", "fixture"),
            recognition_mode="melody",
        ),
        Failed(),
    )
    assert result.source_map["sheets"][0]["elements"]
    assert result.melody["metadata"]["key"]["status"] == "unknown"
    assert not result.melody["melody_complete"]


def test_local_melody_replay_preserves_disabled_review_mode(tmp_path):
    config = CliConfig(
        SOURCE,
        tmp_path / "local",
        LlmConfig("", "", "fixture"),
        recognition_mode="melody",
        melody_review=False,
    )
    result = run(config, BodyAndReviewClient())
    replay = run(
        replace(config, output_dir=tmp_path / "replay", melody_review=True),
        ReplayClient(config.output_dir / "rows"),
    )
    assert replay.melody == result.melody
    assert replay.overlay_svg == result.overlay_svg


def test_transformed_melody_json_uses_rational_numbers(tmp_path):
    config = CliConfig(
        SOURCE,
        tmp_path / "out",
        LlmConfig("", "", "fixture"),
        recognition_mode="melody",
        melody_review=False,
    )
    result = run(config, BodyAndReviewClient())
    value = json.loads((config.output_dir / "melody.json").read_text(encoding="utf-8"))
    assert value == result.melody
    for region in value["regions"]:
        for note in region["notes"]:
            assert note["duration"] is None or set(note["duration"]) == {
                "numerator",
                "denominator",
            }


def test_melody_rejects_legacy_recognizer_before_writing(tmp_path):
    class Legacy:
        def transcribe_row_with_retry(self, *args, **kwargs):
            raise AssertionError("must not call legacy recognition")

    config = CliConfig(
        SOURCE,
        tmp_path / "legacy",
        LlmConfig("", "", "fixture"),
        recognition_mode="melody",
    )
    with pytest.raises(EngineError, match="v3 主体"):
        run(config, Legacy())
    assert not config.output_dir.exists()


def test_local_metadata_replay_with_crops(tmp_path):
    from PIL import Image, ImageDraw
    from trans_jp.pipeline.local_metadata import recognize_local_declarations
    from trans_jp.io.melody_artifacts import serializable

    work = Image.new("RGB", (300, 120), "white")
    draw = ImageDraw.Draw(work)
    draw.rectangle((100, 50, 111, 51), fill="black")
    draw.rectangle((100, 58, 111, 59), fill="black")

    class Local:
        def recognize_local_metadata(self, path, ids):
            return CompletionResult(
                json.dumps(
                    {
                        "schema_version": 1,
                        "declarations": [
                            {
                                "region_id": ids[0],
                                "key_text": "1=#C",
                                "meter_text": "4/4",
                            }
                        ],
                    }
                ),
                "stop",
            )

    output = tmp_path / "out"
    (output / "melody-evidence").mkdir(parents=True)
    first = recognize_local_declarations(
        work, [], Local(), output, enabled=True, replay_root=None
    )
    assert first["declarations"][0]["key"] == "C#"
    assert first["declarations"][0]["activation_status"] == "unknown"
    target = tmp_path / "replay"
    (target / "melody-evidence").mkdir(parents=True)
    second = recognize_local_declarations(
        work, [], None, target, enabled=True, replay_root=output
    )
    assert serializable(second) == serializable(first)
