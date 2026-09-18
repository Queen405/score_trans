"""Geometry-only replay of visually reviewed bodies, NOT model recognition."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from trans_jp.models.contracts import CliConfig, CompletionResult, LlmConfig
from trans_jp.models.geometry import Box
from trans_jp.pipeline.runner import run
from trans_jp.io.output_writer import write_outputs
from evaluate_coordinates import DEFAULT_LABELS, iou


class ReviewedBodyClient:
    def __init__(self, rows: list[dict]):
        self.rows = {r["row_index"]: r for r in rows}

    def transcribe_request_with_retry(
        self, request, prompt, **kwargs
    ) -> CompletionResult:
        reference = self.rows.get(request.registry.row_index)
        if reference is None:
            return CompletionResult(
                json.dumps(
                    {
                        "schema_version": 2,
                        "row_type": "other",
                        "row_text": "",
                        "tokens": [],
                    }
                ),
                "stop",
            )
        entries = []
        for expected in reference["expected"]:
            box = Box(*expected["box"])
            options = sorted(
                [
                    (iou(box, c.bounds), c.candidate_id, c)
                    for c in request.registry.candidates
                    if c.kind == expected["kind"] and not c.ambiguous
                ],
                reverse=True,
            )
            c = options[0][2] if options and options[0][0] >= 0.5 else None
            band = min(c.band_ids) if c else 0
            entries.append(
                (
                    band,
                    box.cx,
                    {
                        "text": expected["label"],
                        "role": "barline"
                        if expected["kind"] == "barline"
                        else "rest"
                        if expected["label"] == "0"
                        else "note",
                        "candidate_ids": [c.candidate_id] if c else [],
                    },
                )
            )
        # Full-width single melody rows can have bars belonging to multiple bands.
        if "barline" in reference["score_kinds"]:
            entries.sort(key=lambda e: e[1])
            tokens = [e[2] for e in entries]
        else:
            entries.sort(key=lambda e: (e[0], e[1]))
            tokens, band = [], None
            for current, _, token in entries:
                if band is not None and band != current:
                    tokens.append({"text": "&", "role": "other", "candidate_ids": []})
                tokens.append(token)
                band = current
        data = {
            "schema_version": 2,
            "row_type": "notation",
            "row_text": " ".join(t["text"] for t in tokens),
            "tokens": tokens,
            "warnings": ["人工主体参考：不包含完整音高/时值语义，不是模型识别结果"],
        }
        return CompletionResult(json.dumps(data, ensure_ascii=False), "stop")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    labels = json.loads(DEFAULT_LABELS.read_text(encoding="utf-8"))
    examples = Path(__file__).parents[1] / "examples"
    for name in sorted({r["image"] for r in labels["rows"]}):
        rows = [r for r in labels["rows"] if r["image"] == name]
        config = CliConfig(
            examples / name,
            args.output_dir / Path(name).stem,
            LlmConfig("", "", "reviewed-bodies-fixture"),
            debug=True,
        )
        result = run(config, ReviewedBodyClient(rows))
        write_outputs(result, config.output_dir)
        print(name, len(result.source_map["sheets"][0]["elements"]))


if __name__ == "__main__":
    main()
