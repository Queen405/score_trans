from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import pytest
from trans_jp.models.contracts import CompletionResult

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests/fixtures/melody"


def tool():
    spec = importlib.util.spec_from_file_location(
        "evaluate_melody", ROOT / "tools/evaluate_melody.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("split", ["development", "holdout"])
def test_frozen_local_attribute_benchmark(split, tmp_path):
    module = tool()
    result = module.evaluate(split, tmp_path)
    key = (
        "benchmark-development-local-final"
        if split == "development"
        else "benchmark-holdout-local"
    )
    expected = json.loads((FIXTURE / "expected_metrics.json").read_text())[key]
    assert result["total"] == expected["total"]
    assert result["fields"] == expected["fields"]


def test_page_split_has_no_overlap_and_more_than_240_labels():
    split = json.loads((FIXTURE / "split.json").read_text())
    refs = json.loads((FIXTURE / "transcriptions.json").read_text())
    dev = {p["image"] for p in split["pages"]["development"]}
    holdout = {p["image"] for p in split["pages"]["holdout"]}
    assert len(dev) == 4 and len(holdout) == 2 and not dev & holdout
    assert sum(len(r["notes"]) for r in refs["rows"]) == 299
    assert sum(len(r["notes"]) for r in refs["rows"] if r["split"] == "holdout") == 118
    for r in refs["rows"]:
        assert r["image"] in (dev if r["split"] == "development" else holdout)


@pytest.mark.parametrize("split", ["development", "holdout"])
def test_frozen_review_benchmark_never_uses_network(split, tmp_path):
    module = tool()
    fixture = json.loads((FIXTURE / "frozen_reviews.json").read_text(encoding="utf-8"))

    class Frozen:
        def __init__(self):
            self.page = None

        def recognize_melody_metadata(self, image_path, region_ids):
            self.page = image_path.parent.parent.name + ".png"
            data = fixture["pages"][self.page]["metadata"]
            if data["status"] != "reviewed":
                raise RuntimeError("recorded metadata failure")
            return CompletionResult(data["raw_response"], data.get("finish_reason"))

        def review_attachments(self, request):
            data = fixture["pages"][self.page]["reviews"][request.request_id]
            assert data["sha256"] == request.payload_sha256
            result = data["result"]
            if result["status"] in ("failed", "not_available"):
                raise RuntimeError("recorded review failure")
            return CompletionResult(result["raw_response"], result.get("finish_reason"))

    result = module.evaluate(split, tmp_path, Frozen())
    expected = json.loads((FIXTURE / "expected_metrics.json").read_text())[
        f"benchmark-{split}-review"
    ]
    assert result["total"] == expected["total"]
    assert result["fields"] == expected["fields"]
