from __future__ import annotations

import argparse
import json
import statistics
import tempfile
import time
from pathlib import Path

from score_trans.exec.history.actions import HistoryActions
from score_trans.models.history.entities import HistoryPage, HistoryRenderPageOcrText
from score_trans.models.history.schemas import BatchRenderStateUpdate, RenderPageOcrText
from score_trans.models.settings.config import ToolConfig
from score_trans.services.files.upload_service import UploadService
from score_trans.services.history.history_service import HistoryService
from score_trans.services.render.main import render_scores_a4_pages
from score_trans.domain.jianpu import parse_jianpu_score


def _median(values: list[float]) -> float:
    return round(statistics.median(values) * 1000, 3)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages", type=int, default=20)
    parser.add_argument("--xml-kb", type=int, default=128)
    parser.add_argument("--repeat", type=int, default=5)
    parser.add_argument("--skip-render", action="store_true")
    parser.add_argument("--slim", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.pages < 1 or args.xml_kb < 0 or args.repeat < 1:
        raise ValueError("pages/repeat must be positive and xml-kb non-negative")

    with tempfile.TemporaryDirectory(
        prefix="score-trans-history-bench-", ignore_cleanup_errors=True
    ) as raw:
        root = Path(raw)
        xml = (
            "<score-partwise>"
            + ("<measure>" * 20)
            + ("x" * (args.xml_kb * 1024))
            + "</measure></score-partwise>"
        )
        pages = [
            HistoryPage(
                input_file_name=f"page-{index + 1:02d}.png",
                input_file_id=f"input-{index}",
                musicxml_file_id=f"musicxml-{index}",
                svg_file_id=f"svg-{index}",
                omr_file_id=f"omr-{index}",
                source_map_file_id=f"map-{index}",
                jianpu_text=f"// @page {index + 1}\n1=C\n4/4\n1 2 3 4 |",
                original_musicxml=xml,
                working_musicxml=xml,
                text_anchors=[],
                position=index,
            )
            for index in range(args.pages)
        ]
        actions = HistoryActions(HistoryService(root / "history.db"))
        batch = actions.service.create_batch(
            pages,
            render_page_file_ids=[f"render-{index}" for index in range(args.pages)],
            jianpu_text="\n".join(page.jianpu_text for page in pages),
            render_page_ocr_texts=[
                HistoryRenderPageOcrText(page_index=index, ocr_text="[]")
                for index in range(args.pages)
            ],
        )
        render_state = BatchRenderStateUpdate(
            render_page_file_ids=batch.render_page_file_ids,
            render_page_ocr_texts=[
                RenderPageOcrText(page_index=item.page_index, ocr_text=item.ocr_text)
                for item in batch.render_page_ocr_texts
            ],
            render_output_stale=False,
            render_layout_key="benchmark-layout",
        )

        get_times = []
        get_bytes = 0
        for _ in range(args.repeat):
            started = time.perf_counter()
            response = actions.get_history(batch.id, include_musicxml=not args.slim)
            get_bytes = len(response.model_dump_json().encode("utf-8"))
            get_times.append(time.perf_counter() - started)

        patch_times = []
        patch_bytes = 0
        for _ in range(args.repeat):
            started = time.perf_counter()
            response = actions.update_batch_render_state(batch.id, render_state)
            patch_bytes = len(response.model_dump_json().encode("utf-8"))
            patch_times.append(time.perf_counter() - started)

        file_ids = [
            file_id
            for page in pages
            for file_id in (
                page.input_file_id,
                page.musicxml_file_id,
                page.svg_file_id,
                page.omr_file_id,
                page.source_map_file_id,
            )
        ] + batch.render_page_file_ids
        uploads = UploadService(ToolConfig(work_dir=root / "work"))
        for file_id in file_ids:
            directory = uploads.base_dir / file_id
            directory.mkdir(parents=True)
            (directory / "payload.txt").write_text("x", encoding="utf-8")
        validation_times = []
        for _ in range(args.repeat):
            started = time.perf_counter()
            assert all(uploads.exists_many(file_ids).values())
            validation_times.append(time.perf_counter() - started)

        render_ms = None
        rendered_page_count = 0
        if not args.skip_render:
            score = parse_jianpu_score(
                "1=C\n4/4\n" + " | ".join(["1 2 3 4"] * (args.pages * 4)) + " |"
            )
            for index, measure in enumerate(score.measures):
                measure.new_page = index > 0 and index % 4 == 0
            started = time.perf_counter()
            rendered = render_scores_a4_pages([score])
            render_ms = round((time.perf_counter() - started) * 1000, 3)
            rendered_page_count = len(rendered)

        result = {
            "pages": args.pages,
            "include_musicxml": not args.slim,
            "xml_kb_per_copy": args.xml_kb,
            "repeat": args.repeat,
            "history_get_ms": _median(get_times),
            "history_get_bytes": get_bytes,
            "render_state_patch_ms": _median(patch_times),
            "render_state_patch_bytes": patch_bytes,
            "file_validation_ms": _median(validation_times),
            "file_validation_count": len(file_ids),
            "render_ms": render_ms,
            "rendered_page_count": rendered_page_count,
            "cached_restore_measured_ms": round(
                _median(get_times) + _median(validation_times), 3
            ),
            "stale_restore_measured_ms": (
                round(
                    _median(get_times)
                    + _median(validation_times)
                    + _median(patch_times)
                    + (render_ms or 0),
                    3,
                )
                if render_ms is not None
                else None
            ),
        }
        text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        print(text, end="")
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
