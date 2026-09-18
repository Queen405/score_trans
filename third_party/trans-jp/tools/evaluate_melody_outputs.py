"""Compare saved online-body melody outputs to reviewed attributes without inference."""

from __future__ import annotations

import argparse
from collections import Counter
from fractions import Fraction
import json
from pathlib import Path
from trans_jp.io.melody_artifacts import validate_melody_replay, write_json
from trans_jp.symbols.notation_parser import parse_notation

ROOT = Path(__file__).parents[1]


def evaluate_outputs(root: Path) -> dict:
    labels = json.loads(
        (ROOT / "tests/fixtures/melody/transcriptions.json").read_text(encoding="utf-8")
    )
    splits = json.loads(
        (ROOT / "tests/fixtures/melody/split.json").read_text(encoding="utf-8")
    )
    hashes = {
        p["image"]: p["sha256"] for pages in splits["pages"].values() for p in pages
    }
    totals = Counter()
    records = []
    excluded = []
    for image in sorted({row["image"] for row in labels["rows"]}):
        folder = root / Path(image).stem
        if not (folder / "melody.json").exists():
            excluded.append(image)
            continue
        validate_melody_replay(folder)
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        if manifest["source_sha256"] != hashes[image]:
            raise ValueError(f"Ground truth image mismatch: {image}")
        result = json.loads((folder / "melody.json").read_text(encoding="utf-8"))
        predictions = {n["body_id"]: n for r in result["regions"] for n in r["notes"]}
        for row in [r for r in labels["rows"] if r["image"] == image]:
            registry = json.loads(
                (folder / "requests" / f"row_{row['row']}-candidates.json").read_text(
                    encoding="utf-8"
                )
            )
            boxes = {
                c["candidate_id"]: [
                    c["bounds"][k] for k in ("x", "y", "width", "height")
                ]
                for c in registry["candidates"]
            }
            for reference in row["notes"]:
                if boxes.get(reference["body_id"]) != reference["bounds_work"]:
                    raise ValueError("Ground truth candidate identity changed")
                totals["expected"] += 1
                note = parse_notation(reference["text"])
                assert note is not None
                expected = {
                    "octave": note.pitches[0].octave,
                    "accidental": {
                        "": "none",
                        "♯": "sharp",
                        "♭": "flat",
                        "♮": "natural",
                    }[note.pitches[0].accidental],
                    "underlines": note.underlines,
                    "dots": note.dots,
                    "extensions": note.extensions,
                }
                prediction = predictions.get(reference["body_id"])
                emitted = bool(prediction and prediction["complete"])
                correct = emitted and prediction["degree"] == note.pitches[0].degree
                if correct:
                    correct = all(
                        prediction["fields"][k]["status"] == "confirmed"
                        and prediction["fields"][k]["value"] == v
                        for k, v in expected.items()
                    )
                    duration = prediction.get("duration")
                    correct = (
                        correct
                        and bool(duration)
                        and Fraction(duration["numerator"], duration["denominator"])
                        == note.duration
                    )
                totals["complete_emitted"] += emitted
                totals["complete_correct"] += bool(correct)
                records.append(
                    {
                        "image": image,
                        "body_id": reference["body_id"],
                        "truth": reference["text"],
                        "has_attributes": prediction is not None,
                        "complete_emitted": emitted,
                        "complete_correct": bool(correct),
                    }
                )
    return {
        "scope": "Online v3 bodies plus local attributes/review, on labeled subset only; excludes effective key, ties, voice timing and absolute pitch.",
        "totals": dict(totals),
        "excluded_pages_without_outputs": excluded,
        "records": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = evaluate_outputs(args.root)
    write_json(args.output, result)
    print(json.dumps(result["totals"]))


if __name__ == "__main__":
    main()
