from __future__ import annotations

from dataclasses import asdict
from io import BytesIO
import logging
import time
import numpy as np

from ..models.contracts import CliConfig, TransJpResult
from ..models.errors import EngineError
from ..matching.text_conflicts import (
    touches,
    finish_body_decisions,
    active_text_exclusions,
)
from ..io.images import load_image, save_rows
from ..io.assets import glyph_assets
from ..io.output_writer import write_row_responses
from ..io.candidate_requests import build_manifest, save_request, write_manifest
from ..io.replay_reader import ReplayClient
from ..structure.candidates import build_registry
from ..rendering.candidate_atlas import render_atlases
from ..preprocess.image import prepare_work_image, to_binary, otsu_binarize
from ..preprocess.deskew import normalize_skew
from ..structure.row_segmenter import segment
from ..structure.page_analyzer import analyze_row
from ..recognition.llm_client import LlmClient
from ..recognition.prompt_builder import PromptBuilder
from ..recognition.row_recognizer import RowTranscriber, recognize_rows
from ..matching.token_matcher import match_row
from ..validation.checks import validate_rows, reject_invalid_geometry
from ..provenance.text_anchors import merge_rows
from ..provenance.source_map import build_source_map
from ..rendering.overlay_renderer import generate_overlay_svg
from ..rendering.preview_renderer import composite_preview
from ..recognition.lyrics import ConfiguredTextRecognizer
from .lyrics_recognition import recognize_lyrics
from ..rendering.lyrics import lyric_overlay, lyrics_preview, pending_overlay
from ..io.lyrics_artifacts import lyrics_binding, write_lyrics_manifest, result_payload

from .body_recognition import recognize_bodies

logger = logging.getLogger("trans_jp.pipeline")


def run(config: CliConfig, llm_client: RowTranscriber | None = None) -> TransJpResult:
    if config.lyrics_refine and config.lyrics_mode != "recognize":
        raise EngineError("--lyrics-refine 需要 --lyrics recognize", 5)
    if config.lyrics_refine and (config.output_dir / "manifest.json").exists():
        raise EngineError("歌词补救必须写入新的输出目录", 5)
    if config.concurrency < 1 or config.min_image_edge < 0:
        raise EngineError("concurrency 必须大于 0，min-image-edge 不得为负数", 5)
    if config.body_responses_dir is not None:
        llm_client = ReplayClient(config.body_responses_dir)
    if isinstance(llm_client, ReplayClient):
        source = llm_client.directory.resolve()
        output = config.output_dir.resolve()
        if (
            source == (output / "rows").resolve()
            or output == source
            or output in source.parents
        ):
            raise EngineError("回放输出不能覆盖输入目录", 5)
    if config.recognition_mode not in ("bodies", "notation", "melody"):
        raise EngineError("recognition_mode 必须为 bodies 或 notation", 5)
    stages = []
    started = time.perf_counter()
    original = load_image(config.input_path)
    work, _ = prepare_work_image(original, config.min_image_edge)
    work, transform = normalize_skew(work, original.size)
    page_binary = to_binary(work)
    rows = segment(page_binary, work, config.output_dir / "rows", transform=transform)
    if not rows:
        raise EngineError("图像未找到有效谱行", 2)
    # All CV facts are computed before recognition. LLM cannot change them.
    analyses = []
    rasters = []
    crops = []
    registries = []
    for row in rows:
        crop = work.crop((0, row.work_y_top, row.width, row.work_y_top + row.height))
        binary = otsu_binarize(np.asarray(crop.convert("L"), dtype=np.uint8))
        crops.append(crop)
        rasters.append(binary)
        analyses.append(analyze_row(binary))
        registries.append(build_registry(binary, analyses[-1], row.index))
    stages.append(
        {"stage": "image_structure", "seconds": time.perf_counter() - started}
    )
    prompts = PromptBuilder(config.prompt_config)
    client = llm_client or LlmClient(config.llm, prompts.system_message)
    melody_replay_root = None
    melody_review_enabled = config.melody_review
    manifest = build_manifest(config, rows, crops, registries)
    if isinstance(client, ReplayClient):
        registries = client.validate_run(manifest, registries)
        if config.recognition_mode == "melody":
            if set(client.versions.values()) != {3}:
                raise EngineError("melody 只能复用 v3 主体响应", 5)
            root = client.directory.parent
            if (root / "melody-manifest.json").exists():
                from ..io.melody_artifacts import validate_melody_replay

                try:
                    validate_melody_replay(root)
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    raise EngineError(f"melody 回放校验失败: {exc}", 5) from exc
                melody_replay_root = root
                from ..io.melody_artifacts import read_melody_review_flag

                melody_review_enabled = read_melody_review_flag(root)
        manifest = build_manifest(config, rows, crops, registries)
    use_bodies = (
        any(v == 3 for v in client.versions.values())
        if isinstance(client, ReplayClient)
        else config.recognition_mode in ("bodies", "melody")
        and hasattr(client, "classify")
    )
    if config.recognition_mode == "melody" and not use_bodies:
        raise EngineError("melody 必须使用 v3 主体分类或 v3 回放", 5)
    lyrics_data = {}
    lyrics_svg = ""
    lyrics_result = None
    blocked_candidates: dict[str, str] = {}
    lyrics_replay_root = config.lyrics_responses_dir
    lyrics_replay_marker = None
    lyrics_enabled = config.lyrics_mode == "recognize"
    if config.lyrics_mode not in ("off", "recognize"):
        raise EngineError("lyrics_mode 必须为 off 或 recognize", 5)
    if isinstance(client, ReplayClient) and client.lyrics_marker:
        lyrics_enabled = True
        lyrics_replay_root = client.directory.parent
        lyrics_replay_marker = client.lyrics_marker
    if lyrics_enabled:
        if not use_bodies or config.recognition_mode not in ("bodies", "melody"):
            raise EngineError("歌词防误识别只能与 bodies 或 melody 主体模式一起使用", 5)
        if config.lyrics_refine and melody_replay_root is not None:
            raise EngineError("歌词补救不能复用旧melody属性；请从bodies运行开始", 5)
        if melody_replay_root is not None and not (
            isinstance(client, ReplayClient) and client.lyrics_marker
        ):
            raise EngineError(
                "旧 melody 证据不能在改变主体后继续复用；请使用 v3 bodies 响应", 5
            )
        if lyrics_replay_root is not None:
            source = lyrics_replay_root.resolve()
            output = config.output_dir.resolve()
            if output == source or output in source.parents:
                raise EngineError("歌词回放输出不能覆盖输入目录", 5)
        ocr = config.lyrics_ocr or config.llm
        if (lyrics_replay_root is None or config.lyrics_refine) and not (
            ocr.api_key and ocr.base_url and ocr.model
        ):
            raise EngineError("歌词识别需要文字模型配置或 --lyrics-responses-dir", 5)
        try:
            lyrics_result, blocked_candidates = recognize_lyrics(
                work,
                page_binary,
                transform,
                rows,
                registries,
                config.output_dir,
                ConfiguredTextRecognizer(ocr)
                if not lyrics_replay_root or config.lyrics_refine
                else None,
                lyrics_binding(manifest),
                concurrency=config.concurrency,
                replay_root=lyrics_replay_root,
                replay_marker=lyrics_replay_marker,
                refine=config.lyrics_refine,
            )
            lyrics_data = result_payload(lyrics_result)
            manifest["lyrics"] = write_lyrics_manifest(
                config.output_dir, lyrics_binding(manifest), lyrics_data
            )
            lyrics_svg = lyric_overlay(lyrics_result, original.width, original.height)
            # Old body replay keeps its frozen batches. Only newly sent batches
            # omit text candidates; both paths enforce the final assembly gate.
            manifest["lyrics_excluded_candidates"] = sorted(
                client.lyrics_excluded
                if isinstance(client, ReplayClient)
                else blocked_candidates
            )
        except (OSError, ValueError) as exc:
            raise EngineError(f"歌词识别产物失败: {exc}", 4) from exc
    requests = {}
    try:
        save_rows(work, rows)
        for row, crop, registry in zip(rows, crops, registries, strict=True):
            version = (
                client.versions.get(row.index, 1)
                if isinstance(client, ReplayClient)
                else 2
                if hasattr(client, "transcribe_request_with_retry")
                else 1
            )
            atlases = (
                render_atlases(crop, registry)
                if version == 2 and not use_bodies
                else []
            )
            requests[row.index] = save_request(
                row, registry, atlases, expected_schema=version
            )
        write_manifest(config.output_dir, manifest)
    except (OSError, ValueError) as exc:
        raise EngineError(f"识别输入写入失败: {exc}", 4) from exc
    started = time.perf_counter()
    body_observations = {}
    if use_bodies:
        recognized = recognize_bodies(
            rows,
            crops,
            registries,
            client,
            manifest,
            concurrency=config.concurrency,
            blocked=blocked_candidates,
            observations=body_observations,
            supplement_client=LlmClient(config.llm, prompts.system_message)
            if config.lyrics_refine and isinstance(client, ReplayClient)
            else None,
        )
    else:
        recognized = recognize_rows(
            rows,
            client,
            prompts,
            target_key=config.target_key,
            title=config.title,
            extra_prompt=config.extra_prompt,
            concurrency=config.concurrency,
            requests=requests,
            progress_callback=lambda done, total: logger.info(
                "识别进度 %d/%d", done, total
            ),
        )
    if lyrics_result and lyrics_result.version >= 4:
        finish_body_decisions(lyrics_result, recognized, body_observations)
        lyrics_data = result_payload(lyrics_result)
        manifest["lyrics"] = write_lyrics_manifest(
            config.output_dir, lyrics_binding(manifest), lyrics_data
        )
    try:
        write_row_responses(recognized, config.output_dir / "rows")
        if use_bodies:
            from ..io.classification_batches import sha256

            manifest["row_responses"] = {
                f"row_{r.row.index}.json": sha256(
                    config.output_dir / "rows" / f"row_{r.row.index}.json"
                )
                for r in recognized
            }
            write_manifest(config.output_dir, manifest)
    except OSError as exc:
        raise EngineError(f"行响应写入失败: {exc}", 4) from exc
    if use_bodies:
        batches = [b for r in recognized for b in r.batch_diagnostics]
        if batches and all(
            b["status"] in ("batch_request_failed", "batch_response_invalid")
            for b in batches
        ):
            raise EngineError("所有主体批次失败；原始响应和批次诊断已保存", 3)
    if all(not r.jianpu_text and not r.tokens for r in recognized) and not use_bodies:
        raise EngineError("所有谱行识别均失败", 3)
    stages.append({"stage": "recognition", "seconds": time.perf_counter() - started})
    started = time.perf_counter()
    matched = [
        match_row(row, binary, analysis)
        for row, binary, analysis in zip(recognized, rasters, analyses, strict=True)
    ]
    melody = {}
    if config.recognition_mode == "melody":
        from .melody_recognition import enrich_melody
        from ..io.melody_artifacts import finish_manifest

        reviewer = (
            client
            if hasattr(client, "review_attachments")
            else LlmClient(config.llm, "")
            if config.llm.api_key
            else None
        )
        try:
            melody = enrich_melody(
                matched,
                work,
                reviewer,
                config.output_dir,
                concurrency=config.concurrency,
                review_enabled=melody_review_enabled,
                replay_root=melody_replay_root,
                text_exclusions=active_text_exclusions(lyrics_result)
                if lyrics_result
                else (),
            )
            files = sorted((config.output_dir / "melody-evidence").glob("*")) + [
                config.output_dir / "melody.json"
            ]
            finish_manifest(config.output_dir, manifest, files)
        except OSError as exc:
            raise EngineError(f"melody 产物写入失败: {exc}", 4) from exc
    if lyrics_result:
        text_boxes = active_text_exclusions(lyrics_result)
        for row in matched:
            for token in row.tokens:
                if token.geometry:
                    token.geometry.primitives = [
                        p
                        for p in token.geometry.primitives
                        if not any(touches(p.bounds, b) for b in text_boxes)
                    ]
    reject_invalid_geometry(matched, *original.size)
    text, anchors = merge_rows(matched)
    source_map = build_source_map(matched, *original.size)
    glyphs = glyph_assets()
    svg = generate_overlay_svg(matched, *original.size, glyphs)
    warnings = [warning for row in matched for warning in row.warnings]
    warnings.extend(validate_rows(matched, *original.size))
    if lyrics_result:
        warnings.extend(lyrics_result.warnings)
    # A source target must also have a valid textual target to prevent a false
    # promise of click-to-text navigation for hallucinated extra tokens.
    valid_ids = {a["source_id"] for a in anchors if a["valid"]}
    for element in source_map["sheets"][0]["elements"]:
        if element["source_id"] not in valid_ids:
            warnings.append(f"{element['source_id']}: 无有效文本锚点")
    preview = BytesIO()
    composite_preview(original, svg).save(preview, format="PNG")
    stages.append(
        {"stage": "matching_render", "seconds": time.perf_counter() - started}
    )
    debug_svg = (
        generate_overlay_svg(matched, *original.size, glyphs, debug=True)
        if config.debug
        else ""
    )
    diagnostics = (
        {
            "source_size": original.size,
            "transform": asdict(transform),
            "stages": stages,
            "warnings": warnings,
            "rows": [
                {
                    "row_index": r.row.index,
                    "work_y_top": r.row.work_y_top,
                    "analysis": asdict(r.analysis),
                    "tokens": [asdict(t) for t in r.tokens],
                    "schema_version": r.schema_version,
                    "complete": r.complete,
                    "recognition_scope": r.recognition_scope,
                    "batch_diagnostics": r.batch_diagnostics,
                    "unresolved_candidates": r.unresolved_candidates,
                    "registry_sha256": r.registry.digest if r.registry else None,
                }
                for r in matched
            ],
        }
        if config.debug
        else {}
    )
    lyrics_html = ""
    if lyrics_result:
        import base64

        original_bytes = BytesIO()
        original.save(original_bytes, format="PNG")
        image_url = "data:image/png;base64," + base64.b64encode(
            original_bytes.getvalue()
        ).decode("ascii")
        lyrics_html = lyrics_preview(
            image_url, svg, lyrics_svg, lyrics_result, *original.size
        )
    return TransJpResult(
        jianpu_text=text,
        rows=matched,
        source_map=source_map,
        overlay_svg=svg,
        text_anchors=anchors,
        warnings=warnings,
        input_path=config.input_path,
        debug=config.debug,
        diagnostics=diagnostics,
        preview_png=preview.getvalue(),
        debug_svg=debug_svg,
        melody=melody,
        lyrics=lyrics_data,
        lyrics_svg=lyrics_svg,
        pending_svg=pending_overlay(lyrics_result, *original.size)
        if lyrics_result and lyrics_result.version >= 4
        else "",
        lyrics_preview_html=lyrics_html,
    )
