from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from collections import defaultdict
import numpy as np
from trans_jp.models.classification import CandidateBatchRequest
from trans_jp.recognition.candidate_classifier import parse_candidate_response
from trans_jp.structure.body_assembler import assemble_body_tokens
from trans_jp.io.images import load_image
from trans_jp.preprocess.image import prepare_work_image, to_binary, otsu_binarize
from trans_jp.preprocess.deskew import normalize_skew
from trans_jp.structure.row_segmenter import segment
from trans_jp.structure.page_analyzer import analyze_row
from trans_jp.structure.candidates import build_registry
from trans_jp.matching.token_matcher import match_row
from trans_jp.models.geometry import Box

ROOT = Path(__file__).parents[1]


def test_frozen_online_v3_body_quality():
    fixture = json.loads(
        (ROOT / "tests/fixtures/coordinates/v3_online_classifications.json").read_text(
            encoding="utf-8"
        )
    )
    truth = json.loads(
        (ROOT / "tests/fixtures/coordinates/reviewed_bodies.json").read_text(
            encoding="utf-8"
        )
    )
    spec = importlib.util.spec_from_file_location(
        "coordinate_eval", ROOT / "tools/evaluate_coordinates.py"
    )
    evaluator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evaluator)
    groups = defaultdict(list)
    for ref in fixture["rows"]:
        groups[ref["image"]].append(ref)
    totals = {"expected": 0, "emitted": 0, "correct": 0}
    oracle_correct = 0
    for image, refs in groups.items():
        original = load_image(ROOT / "examples" / image)
        work, _ = prepare_work_image(original, 2500)
        work, transform = normalize_skew(work, original.size)
        rows = segment(to_binary(work), work, Path("unused"), transform=transform)
        for ref in refs:
            row = rows[ref["row_index"]]
            crop = work.crop(
                (0, row.work_y_top, row.width, row.work_y_top + row.height)
            )
            binary = otsu_binarize(np.asarray(crop.convert("L")))
            analysis = analyze_row(binary)
            registry = build_registry(binary, analysis, row.index)
            assert registry.digest == ref["registry_sha256"]
            batches = []
            for batch in ref["batches"]:
                assert batch["status"] == "classified"
                req = CandidateBatchRequest(
                    batch["batch_id"],
                    row.image_path,
                    Path("unused"),
                    registry,
                    tuple(batch["candidate_ids"]),
                )
                batches.append(parse_candidate_response(batch["raw_response"], req))
            assembled = assemble_body_tokens(registry, batches, row)
            matched = match_row(assembled, binary, analysis)
            expected_ref = next(
                r
                for r in truth["rows"]
                if r["image"] == image and r["row_index"] == row.index
            )

            def source_box(values):
                x, y, w, h = values
                return transform.box(Box(x, y + row.work_y_top, w, h))

            expected = [
                {**e, "box": source_box(e["box"])} for e in expected_ref["expected"]
            ]
            actual = []
            for token in matched.tokens:
                lines = []
                for p in token.geometry.primitives:
                    if p.kind == "glyph" and p.value in tuple("01234567"):
                        actual.append(
                            {"kind": "digit", "label": p.value, "box": p.bounds}
                        )
                    if p.value == "barline":
                        lines.append(p.bounds)
                if lines and "barline" in expected_ref["score_kinds"]:
                    bounds = lines[0]
                    for b in lines[1:]:
                        bounds = bounds.union(b)
                    actual.append({"kind": "barline", "label": "|", "box": bounds})
            pairs = evaluator.pair_boxes(expected, actual)
            correct = sum(expected[i]["label"] == actual[j]["label"] for i, j in pairs)
            totals["expected"] += len(expected)
            totals["emitted"] += len(actual)
            totals["correct"] += correct
            # Independent geometry control: inject reviewed labels only at existing,
            # unambiguous candidates, never into the online classification above.
            candidates = [
                {
                    "kind": c.kind,
                    "box": source_box(
                        [c.bounds.x, c.bounds.y, c.bounds.width, c.bounds.height]
                    ),
                    "candidate": c,
                }
                for c in registry.candidates
                if not c.ambiguous and c.kind in expected_ref["score_kinds"]
            ]
            for _, j in evaluator.pair_boxes(expected, candidates):
                assert candidates[j]["candidate"].bounds.width > 0
                oracle_correct += 1
    assert totals == {"expected": 211, "emitted": 208, "correct": 206}
    assert oracle_correct == 209
