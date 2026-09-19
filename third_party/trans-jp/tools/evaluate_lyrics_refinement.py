"""V4 recovery and controlled-holdout metrics; pending objects never count as accepted."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from trans_jp.models.geometry import Box
from evaluate_coordinates import iou, pair_boxes
from evaluate_lyrics import normalized, edit_distance, inside

ROOT = Path(__file__).parents[1]


def note_predictions(folder: Path) -> list[dict]:
    data = json.loads((folder / "overlay-diagnostics.json").read_text(encoding="utf-8"))
    return [
        {
            "candidate_ids": t["candidate_ids"],
            "label": p["value"],
            "box": Box(**p["bounds"]),
            "kind": "digit",
        }
        for r in data["rows"]
        for t in r["tokens"]
        for p in (t.get("geometry") or {}).get("primitives", [])
        if p["kind"] == "glyph" and p["value"] in "01234567"
    ]


def recovery(folder: Path) -> dict:
    truth = json.loads(
        (ROOT / "tests/fixtures/lyrics/recovery49.json").read_text(encoding="utf-8")
    )
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    if manifest["source_sha256"] != truth["source_sha256"]:
        raise ValueError("recovery source hash mismatch")
    actual = note_predictions(folder)
    result = json.loads((folder / "lyrics.json").read_text(encoding="utf-8"))
    decisions = {d["candidate_id"]: d for d in result["decisions"]}
    records = []
    for n in truth["notes"]:
        matches = [p for p in actual if n["candidate_id"] in p["candidate_ids"]]
        correct = any(
            p["label"] == n["label"] and iou(p["box"], Box(**n["bounds"])) >= 0.5
            for p in matches
        )
        records.append(
            {
                **n,
                "state": decisions[n["candidate_id"]]["state"],
                "correctly_restored": correct,
            }
        )
    return {
        "scope": truth["scope"],
        "expected": len(records),
        "correct": sum(r["correctly_restored"] for r in records),
        "pending": sum(r["state"] == "pending" for r in records),
        "records": records,
    }


def holdout(root: Path) -> dict:
    labels = json.loads(
        (ROOT / "tests/fixtures/lyrics/holdout-v4/labels.json").read_text(
            encoding="utf-8"
        )
    )
    records = []
    for page in labels["pages"]:
        name = Path(page["image"]).stem
        expected = [
            {"kind": "digit", "label": n["label"], "box": Box(*n["box"])}
            for n in page["notes"]
        ]
        base = note_predictions(root / "baseline" / name)
        actual = note_predictions(root / "filtered" / name)
        for mode in ["baseline", "filtered"]:
            manifest = json.loads(
                (root / mode / name / "manifest.json").read_text(encoding="utf-8")
            )
            if manifest["source_sha256"] != page["sha256"]:
                raise ValueError("holdout source mismatch")

        def correct(pred: list[dict]) -> int:
            return sum(
                expected[i]["label"] == pred[j]["label"]
                for i, j in pair_boxes(expected, pred)
            )

        lyric_data = json.loads(
            (root / "filtered" / name / "lyrics.json").read_text(encoding="utf-8")
        )
        errors = []
        for ref in page["lines"]:
            predicted = sorted(
                (
                    line
                    for line in lyric_data["lines"]
                    if inside(line["bounds"], ref["box"])
                ),
                key=lambda line: line["bounds"]["x"],
            )
            txt = normalized("".join(line["text"] for line in predicted))
            target = normalized(ref["text"])
            errors.append(
                {
                    "expected": ref["text"],
                    "actual": txt,
                    "characters": len(target),
                    "edits": edit_distance(target, txt),
                }
            )
        records.append(
            {
                "name": name,
                "expected_notes": len(expected),
                "baseline_correct": correct(base),
                "filtered_correct": correct(actual),
                "false_notes_in_lyric_bands": sum(
                    any(
                        inside(
                            {
                                "x": p["box"].x,
                                "y": p["box"].y,
                                "width": p["box"].width,
                                "height": p["box"].height,
                            },
                            r["box"],
                        )
                        for r in page["lines"]
                    )
                    for p in actual
                ),
                "pending": len(lyric_data["pending"]),
                "predicted_lyric_fragments": len(lyric_data["lines"]),
                "lyrics": errors,
            }
        )
    total = {
        k: sum(r[k] for r in records)
        for k in [
            "expected_notes",
            "baseline_correct",
            "filtered_correct",
            "false_notes_in_lyric_bands",
            "pending",
        ]
    }
    total["recall_drop_percentage_points"] = (
        100
        * (total["baseline_correct"] - total["filtered_correct"])
        / total["expected_notes"]
    )
    return {"scope": labels["policy"], "total": total, "pages": records}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recovery", type=Path)
    parser.add_argument("--holdout", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = {}
    if args.recovery:
        result["recovery49"] = recovery(args.recovery)
    if args.holdout:
        result["holdout"] = holdout(args.holdout)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                k: {a: b for a, b in v.items() if a not in ("pages", "records")}
                for k, v in result.items()
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
