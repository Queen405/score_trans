from __future__ import annotations
import json
from dataclasses import asdict
from pathlib import Path
from ..models.contracts import RowResult, TransJpResult
from ..models.errors import EngineError


def write_row_responses(rows: list[RowResult], directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for row in rows:
        data = {
            "schema_version": row.schema_version,
            "complete": row.complete,
            "recognition_scope": row.recognition_scope,
            "batch_diagnostics": row.batch_diagnostics,
            "unresolved_candidates": row.unresolved_candidates,
            "row_index": row.row.index,
            "row_type": row.row_type,
            "row_text": row.jianpu_text,
            "tokens": [
                {k: v for k, v in asdict(t).items() if k not in ("geometry", "index")}
                for t in row.tokens
            ],
            "key": row.key,
            "meter": row.meter,
            "tempo": row.tempo,
            "title": row.title,
            "warnings": row.warnings,
            "confidence": row.confidence,
        }
        if row.raw_response is not None:
            requests_dir = directory.parent / "requests"
            requests_dir.mkdir(parents=True, exist_ok=True)
            (requests_dir / f"row_{row.row.index}-response.txt").write_text(
                row.raw_response, encoding="utf-8"
            )
        (directory / f"row_{row.row.index}.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def write_outputs(result: TransJpResult, output_dir: Path) -> None:
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "jianpu.txt").write_text(result.jianpu_text, encoding="utf-8")
        (output_dir / "overlay.svg").write_text(result.overlay_svg, encoding="utf-8")
        for name, data in [
            ("score-link-map.json", result.source_map),
            ("text_anchors.json", result.text_anchors),
        ]:
            (output_dir / name).write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        if result.preview_png:
            (output_dir / "overlay-preview.png").write_bytes(result.preview_png)
        if result.debug:
            (output_dir / "overlay-debug.svg").write_text(
                result.debug_svg, encoding="utf-8"
            )
            (output_dir / "overlay-diagnostics.json").write_text(
                json.dumps(result.diagnostics, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
    except (OSError, ValueError) as exc:
        raise EngineError(f"输出写入失败: {exc}", 4) from exc
