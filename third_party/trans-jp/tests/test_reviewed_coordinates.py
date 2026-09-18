from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import pytest
from trans_jp.models.contracts import CliConfig, LlmConfig
from trans_jp.pipeline.runner import run
from trans_jp.io.output_writer import write_outputs

ROOT = Path(__file__).parents[1]


def load_tool(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_reviewed_real_bodies_geometry_and_metrics(tmp_path):
    evaluator = load_tool("evaluate_coordinates")
    replay = load_tool("replay_reviewed_bodies")
    labels = json.loads(evaluator.DEFAULT_LABELS.read_text(encoding="utf-8"))
    assert sum(len(r["expected"]) for r in labels["rows"]) == 211
    for name in sorted({r["image"] for r in labels["rows"]}):
        reference = [r for r in labels["rows"] if r["image"] == name]
        source = ROOT / "examples" / name
        assert (
            hashlib.sha256(source.read_bytes()).hexdigest()
            == reference[0]["source_sha256"]
        )
        config = CliConfig(
            source,
            tmp_path / Path(name).stem,
            LlmConfig("", "", "reviewed-body-fixture"),
            debug=True,
        )
        result = run(config, replay.ReviewedBodyClient(reference))
        write_outputs(result, config.output_dir)
    result = evaluator.evaluate(tmp_path, labels)
    assert result["total"]["correct"] == result["total"]["emitted"] == 209
    assert result["total"]["candidate_recall"] == pytest.approx(209 / 211)
    assert result["total"]["body_label_precision"] == 1
    # The joined 0/5 in image copy 12 must remain unresolved rather than share a box.
    row = next(r for r in result["rows"] if r["image"] == "image copy 12.png")
    assert row["expected"] - row["correct"] == 2
