"""Evaluate manually read development lyric bands, keeping recognition and localization separate."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import unicodedata

ROOT = Path(__file__).parents[1]


def normalized(text: str) -> str:
    return "".join(unicodedata.normalize("NFKC", text).split()).replace("。", ".")


def edit_distance(a: str, b: str) -> int:
    previous = list(range(len(b) + 1))
    for i, aa in enumerate(a, 1):
        current = [i]
        for j, bb in enumerate(b, 1):
            current.append(
                min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (aa != bb))
            )
        previous = current
    return previous[-1]


def inside(box: dict, band: list[float]) -> bool:
    x, y, w, h = band
    return (
        x <= box["x"] + box["width"] / 2 < x + w
        and y <= box["y"] + box["height"] / 2 < y + h
    )


def primitives(root: Path) -> list[dict]:
    data = json.loads((root / "overlay-diagnostics.json").read_text(encoding="utf-8"))
    return [
        p
        for r in data["rows"]
        for t in r["tokens"]
        for p in (t.get("geometry") or {}).get("primitives", [])
        if p["kind"] == "glyph" or p.get("value") == "barline"
    ]


def evaluate(before: Path, after: Path, truth: dict) -> dict:
    for root in (before, after):
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        if manifest["source_sha256"] != truth["source_sha256"]:
            raise ValueError("source hash mismatch")
    data = json.loads((after / "lyrics.json").read_text(encoding="utf-8"))
    old, new = primitives(before), primitives(after)
    rows = []
    for ref in truth["lyrics"]:
        predicted = sorted(
            (line for line in data["lines"] if inside(line["bounds"], ref["box"])),
            key=lambda line: line["bounds"]["x"],
        )
        text = "".join(line["text"] for line in predicted)
        expected = normalized(ref["text"])
        actual = normalized(text)
        rows.append(
            {
                "expected": ref["text"],
                "actual": text,
                "edit_distance": edit_distance(expected, actual),
                "characters": len(expected),
                "located_tokens": sum(len(line["tokens"]) for line in predicted),
                "before_false_primitives": sum(
                    inside(p["bounds"], ref["box"]) for p in old
                ),
                "after_false_primitives": sum(
                    inside(p["bounds"], ref["box"]) for p in new
                ),
            }
        )

    def music_key(p: dict) -> str:
        return json.dumps([p["kind"], p["value"], p["bounds"]], sort_keys=True)

    old_music = {
        music_key(p)
        for p in old
        if p["kind"] == "glyph"
        and any(inside(p["bounds"], b) for b in truth["music_bands"])
    }
    new_music = {
        music_key(p)
        for p in new
        if p["kind"] == "glyph"
        and any(inside(p["bounds"], b) for b in truth["music_bands"])
    }
    return {
        "scope": truth["scope"],
        "normalization": "NFKC, remove whitespace, Chinese full stop normalized to period",
        "rows": rows,
        "total": {
            "lyric_false_primitives_before": sum(
                r["before_false_primitives"] for r in rows
            ),
            "lyric_false_primitives_after": sum(
                r["after_false_primitives"] for r in rows
            ),
            "characters": sum(r["characters"] for r in rows),
            "edits": sum(r["edit_distance"] for r in rows),
            "CER": sum(r["edit_distance"] for r in rows)
            / sum(r["characters"] for r in rows),
            "localized_tokens": sum(r["located_tokens"] for r in rows),
            "before_music_glyphs": len(old_music),
            "after_music_glyphs": len(new_music),
            "lost_previous_music_glyphs": len(old_music - new_music),
            "new_music_glyphs": len(new_music - old_music),
        },
        "limitations": [
            "No independent character-box IoU ground truth",
            "Development page only",
            "Retained baseline music glyphs are not independent note truth",
        ],
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--before", type=Path, required=True)
    p.add_argument("--after", type=Path, required=True)
    p.add_argument(
        "--truth", type=Path, default=ROOT / "tests/fixtures/lyrics/liangzhu.json"
    )
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    truth = json.loads(args.truth.read_text(encoding="utf-8"))
    if (
        hashlib.sha256((ROOT / "examples" / truth["image"]).read_bytes()).hexdigest()
        != truth["source_sha256"]
    ):
        raise ValueError("annotation image changed")
    result = evaluate(args.before, args.after, truth)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result["total"], ensure_ascii=False))


if __name__ == "__main__":
    main()
