"""Score frozen, visually reviewed bodies; never treat matched as accuracy."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from trans_jp.models.geometry import Box, Transform

DEFAULT_LABELS = (
    Path(__file__).parents[1] / "tests/fixtures/coordinates/reviewed_bodies.json"
)


def iou(a: Box, b: Box) -> float:
    intersection = max(0, min(a.right, b.right) - max(a.x, b.x)) * max(
        0, min(a.bottom, b.bottom) - max(a.y, b.y)
    )
    return intersection / max(
        1e-9, a.width * a.height + b.width * b.height - intersection
    )


def pair_boxes(expected: list[dict], actual: list[dict]) -> list[tuple[int, int]]:
    edges = sorted(
        (
            (iou(e["box"], p["box"]), i, j)
            for i, e in enumerate(expected)
            for j, p in enumerate(actual)
            if e["kind"] == p["kind"]
        ),
        reverse=True,
    )
    seen_e, seen_p, pairs = set(), set(), []
    for score, i, j in edges:
        if score < 0.5 or i in seen_e or j in seen_p:
            continue
        seen_e.add(i)
        seen_p.add(j)
        pairs.append((i, j))
    return pairs


def evaluate(root: Path, labels: dict) -> dict:
    entries = []
    for reference in labels["rows"]:
        directory = root / Path(reference["image"]).stem
        diag_path = directory / "overlay-diagnostics.json"
        if not diag_path.exists():
            raise ValueError(f"Missing diagnostics: {diag_path}")
        diagnostics = json.loads(diag_path.read_text(encoding="utf-8"))
        manifest_path = directory / "manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            saved_row = manifest["rows"][reference["row_index"]]
            if (
                manifest["source_sha256"] != reference["source_sha256"]
                or saved_row["image_sha256"] != reference["crop_sha256"]
            ):
                raise ValueError(f"Reference image/crop mismatch: {directory}")
        transform = Transform(**diagnostics["transform"])
        row = next(
            r for r in diagnostics["rows"] if r["row_index"] == reference["row_index"]
        )
        if row["work_y_top"] != reference["work_y_top"]:
            raise ValueError(f"Row segmentation mismatch: {directory}")

        def page(values: list[float]) -> Box:
            x, y, w, h = values
            return transform.box(Box(x, y + reference["work_y_top"], w, h))

        expected = [{**e, "box": page(e["box"])} for e in reference["expected"]]
        actual = []
        for token in row["tokens"]:
            primitives = (token.get("geometry") or {}).get("primitives", [])
            lines = []
            for p in primitives:
                if p["kind"] == "glyph" and p["value"] in tuple("01234567"):
                    actual.append(
                        {
                            "kind": "digit",
                            "label": p["value"],
                            "box": Box(**p["bounds"]),
                        }
                    )
                if p["value"] == "barline":
                    lines.append(Box(**p["bounds"]))
            if lines and "barline" in reference["score_kinds"]:
                bounds = lines[0]
                for b in lines[1:]:
                    bounds = bounds.union(b)
                actual.append({"kind": "barline", "label": "|", "box": bounds})
        candidates_path = (
            directory / "requests" / f"row_{reference['row_index']}-candidates.json"
        )
        candidates = []
        if candidates_path.exists():
            registry = json.loads(candidates_path.read_text(encoding="utf-8"))
            candidates = [
                {
                    "kind": c["kind"],
                    "box": page(
                        [c["bounds"][k] for k in ("x", "y", "width", "height")]
                    ),
                }
                for c in registry["candidates"]
                if c["kind"] in reference["score_kinds"] and not c["ambiguous"]
            ]
        pairs = pair_boxes(expected, actual)
        correct = [
            (i, j) for i, j in pairs if expected[i]["label"] == actual[j]["label"]
        ]
        entries.append(
            {
                "image": reference["image"],
                "row_index": reference["row_index"],
                "expected": len(expected),
                "emitted": len(actual),
                "correct": len(correct),
                "candidate_hits": len(pair_boxes(expected, candidates))
                if candidates_path.exists()
                else None,
                "ious": [
                    round(iou(expected[i]["box"], actual[j]["box"]), 4)
                    for i, j in correct
                ],
                "center_errors_in_heights": [
                    round(
                        math.hypot(
                            expected[i]["box"].cx - actual[j]["box"].cx,
                            expected[i]["box"].cy - actual[j]["box"].cy,
                        )
                        / expected[i]["box"].height,
                        4,
                    )
                    for i, j in correct
                ],
                "wrong_labels": [
                    {"expected": expected[i]["label"], "actual": actual[j]["label"]}
                    for i, j in pairs
                    if expected[i]["label"] != actual[j]["label"]
                ],
            }
        )
    total = {
        key: sum(e[key] for e in entries) for key in ("expected", "emitted", "correct")
    }
    total["body_label_precision"] = (
        total["correct"] / total["emitted"] if total["emitted"] else None
    )
    total["body_label_coverage"] = total["correct"] / total["expected"]
    hits = [e["candidate_hits"] for e in entries]
    total["candidate_recall"] = (
        sum(hits) / total["expected"] if all(v is not None for v in hits) else None
    )
    return {"scope": labels["scope"], "total": total, "rows": entries}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        required=True,
        help="Parent of per-image output directories",
    )
    parser.add_argument("--labels", type=Path, default=DEFAULT_LABELS)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.root, json.loads(args.labels.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result["total"], ensure_ascii=False))


if __name__ == "__main__":
    main()
