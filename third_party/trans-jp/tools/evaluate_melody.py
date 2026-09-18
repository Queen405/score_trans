"""Conditional attribute benchmark with manually transcribed bodies; not whole-score accuracy."""

from __future__ import annotations

import argparse
from collections import Counter
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import numpy as np
from trans_jp.models.contracts import RowResult, RecognizedToken
from trans_jp.models.geometry import Box
from trans_jp.io.images import load_image
from trans_jp.io.melody_artifacts import write_json
from trans_jp.preprocess.image import prepare_work_image, to_binary, otsu_binarize
from trans_jp.preprocess.deskew import normalize_skew
from trans_jp.structure.row_segmenter import segment
from trans_jp.structure.page_analyzer import analyze_row
from trans_jp.structure.candidates import build_registry
from trans_jp.matching.token_matcher import match_row
from trans_jp.pipeline.melody_recognition import enrich_melody
from trans_jp.symbols.notation_parser import parse_notation
from trans_jp.io.assets import glyph_assets
from trans_jp.rendering.overlay_renderer import generate_overlay_svg
from trans_jp.rendering.preview_renderer import composite_preview

ROOT = Path(__file__).parents[1]


def evaluate(split: str, output: Path, client=None):
    labels = json.loads(
        (ROOT / "tests/fixtures/melody/transcriptions.json").read_text(encoding="utf-8")
    )
    manifest = json.loads(
        (ROOT / "tests/fixtures/melody/split.json").read_text(encoding="utf-8")
    )
    rows_ref = [r for r in labels["rows"] if r["split"] == split]
    fields = {
        name: Counter()
        for name in (
            "octave",
            "accidental",
            "underlines",
            "dots",
            "extensions",
            "duration",
        )
    }
    total = Counter()
    records = []
    for name in sorted({r["image"] for r in rows_ref}):
        source = ROOT / "examples" / name
        expected_hash = next(
            p["sha256"] for p in manifest["pages"][split] if p["image"] == name
        )
        assert hashlib.sha256(source.read_bytes()).hexdigest() == expected_hash
        original = load_image(source)
        work, _ = prepare_work_image(original, 2500)
        work, tr = normalize_skew(work, original.size)
        page_rows = segment(to_binary(work), work, Path("unused"), transform=tr)
        selected = []
        truth = {}
        for ref in [r for r in rows_ref if r["image"] == name]:
            row = page_rows[ref["row"]]
            crop = work.crop(
                (0, row.work_y_top, row.width, row.work_y_top + row.height)
            )
            binary = otsu_binarize(np.asarray(crop.convert("L")))
            analysis = analyze_row(binary)
            registry = build_registry(binary, analysis, row.index)
            by_id = {c.candidate_id: c for c in registry.candidates}
            tokens = []
            for i, n in enumerate(ref["notes"]):
                c = by_id[n["body_id"]]
                assert c.bounds == Box(*n["bounds_work"])
                notation = parse_notation(n["text"])
                assert notation is not None, n["text"]
                degree = notation.pitches[0].degree
                tokens.append(
                    RecognizedToken(
                        i,
                        degree,
                        None,
                        None,
                        "rest" if degree == "0" else "note",
                        candidate_ids=(c.candidate_id,),
                    )
                )
                truth[c.candidate_id] = (n, notation)
            result = RowResult(
                row,
                "notation",
                " ".join(t.text for t in tokens),
                tokens,
                schema_version=3,
                registry=registry,
            )
            selected.append(match_row(result, binary, analysis))
        out = output / Path(name).stem
        result = enrich_melody(
            selected, work, client, out, review_enabled=client is not None
        )
        predictions = {n["body_id"]: n for r in result["regions"] for n in r["notes"]}
        for cid, (label, notation) in truth.items():
            total["expected"] += 1
            expected = {
                "octave": notation.pitches[0].octave,
                "accidental": {
                    "": "none",
                    "♯": "sharp",
                    "♭": "flat",
                    "♮": "natural",
                }.get(notation.pitches[0].accidental),
                "underlines": notation.underlines,
                "dots": notation.dots,
                "extensions": notation.extensions,
                "duration": notation.duration,
            }
            prediction = predictions.get(cid)
            correct = True
            confirmed = True
            errors = {}
            for field, want in expected.items():
                fields[field]["expected"] += 1
                attr = (
                    prediction["fields"][field]
                    if prediction and field != "duration"
                    else None
                )
                if field == "duration":
                    value = prediction.get("duration") if prediction else None
                    got = (
                        Fraction(value["numerator"], value["denominator"])
                        if value
                        else None
                    )
                    known = got is not None
                else:
                    known = bool(attr and attr["status"] == "confirmed")
                    got = attr["value"] if attr else None
                if known:
                    fields[field]["confirmed"] += 1
                    if got == want:
                        fields[field]["correct"] += 1
                    else:
                        correct = False
                        errors[field] = {"expected": str(want), "actual": str(got)}
                else:
                    correct = False
                    confirmed = False
            if confirmed:
                total["complete_emitted"] += 1
            if correct:
                total["complete_correct"] += 1
            records.append(
                {
                    "image": name,
                    "body_id": cid,
                    "truth": label["text"],
                    "complete_correct": correct,
                    "errors": errors,
                    "predicted": prediction,
                }
            )
        svg = generate_overlay_svg(selected, *original.size, glyph_assets())
        (out / "overlay.svg").write_text(svg, encoding="utf-8")
        composite_preview(original, svg).save(out / "overlay-preview.png")
    summary = {
        "split": split,
        "scope": "conditional on visually transcribed bodies; attachment identities not independently annotated",
        "review": client is not None,
        "total": dict(total),
        "fields": {k: dict(v) for k, v in fields.items()},
        "records": records,
    }
    write_json(output / "metrics.json", summary)
    print(
        json.dumps(
            {"total": dict(total), "fields": summary["fields"]}, ensure_ascii=False
        ),
        flush=True,
    )
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("development", "holdout"), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    evaluate(args.split, args.output_dir)


if __name__ == "__main__":
    main()
