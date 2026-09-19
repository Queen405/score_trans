from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from fractions import Fraction
import json
import logging
from pathlib import Path
from typing import Any
from collections.abc import Iterator
from PIL import Image
from ..models.candidates import CandidateRegistry
from ..models.geometry import Box
from ..matching.text_conflicts import touches
from ..models.contracts import RowSegment, RecognizedToken
from ..models.raster import RowAnalysis
from ..models.melody import AttachmentReviewRequest, NoteAttributes
import numpy as np
from ..models.contracts import RowResult, make_source_id
from ..models.melody import MelodyRegionResult, AttachmentReviewResult, AttributeValue
from ..models.errors import EngineError
from ..preprocess.image import otsu_binarize
from ..structure.page_analyzer import analyze_row
from ..structure.attachment_candidates import detect_attachment_candidates
from ..matching.attachment_relations import (
    resolve_attachment_relations,
    attributes_for_body,
    finalize_note_attributes,
)
from ..matching.geometry import add_shape, add_line, page_box
from ..rendering.attachment_atlas import render_attachment_atlas
from ..io.melody_artifacts import (
    write_json,
    make_review,
    save_review,
    serializable,
)
from ..recognition.attachment_reviewer import parse_attachment_review

logger = logging.getLogger("trans_jp.melody")


def _padded(
    row: RowResult, work: Image.Image
) -> tuple[RowSegment, CandidateRegistry, Image.Image, RowAnalysis]:
    registry = row.registry
    h = max(
        (
            c.bounds.height
            for c in registry.candidates
            if c.kind == "digit"
            and c.candidate_id in {cid for t in row.tokens for cid in t.candidate_ids}
        ),
        default=16,
    )
    top = max(0, row.row.work_y_top - int(h * 2))
    bottom = min(work.height, row.row.work_y_top + row.row.height + int(h * 2))
    offset = row.row.work_y_top - top
    shifted = replace(
        registry,
        height=bottom - top,
        candidates=tuple(
            replace(c, bounds=replace(c.bounds, y=c.bounds.y + offset))
            for c in registry.candidates
        ),
    )
    crop = work.crop((0, top, work.width, bottom))
    analysis = analyze_row(otsu_binarize(np.asarray(crop.convert("L"))))
    return (
        replace(row.row, work_y_top=top, height=bottom - top),
        shifted,
        crop,
        analysis,
    )


def _regions(
    row: RowResult,
) -> Iterator[tuple[int, float, float, list[RecognizedToken], bool]]:
    bars = [
        t
        for t in row.tokens
        if t.role == "barline" and t.geometry and t.geometry.primitives
    ]
    lookup = {c.candidate_id: c for c in row.registry.candidates}
    bars = sorted(bars, key=lambda t: lookup[t.candidate_ids[0]].bounds.cx)
    left = -1
    for number, end in enumerate([*bars, None]):
        right = lookup[end.candidate_ids[0]].bounds.cx if end else row.row.width + 1
        tokens = [
            t
            for t in row.tokens
            if t.role in ("note", "rest", "chord")
            and t.candidate_ids
            and left < lookup[t.candidate_ids[0]].bounds.cx < right
        ]
        if tokens:
            yield number, left, right, tokens, end is not None and left >= 0
        left = right


def enrich_melody(
    rows: list[RowResult],
    work: Image.Image,
    client: Any,
    output: Path,
    *,
    concurrency: int = 2,
    review_enabled: bool = True,
    replay_root: Path | None = None,
    text_exclusions: tuple[Box, ...] = (),
) -> dict:
    directory = output / "melody-evidence"
    directory.mkdir(parents=True, exist_ok=True)
    from .melody_metadata import recognize_metadata

    metadata = recognize_metadata(
        work, client, output, enabled=review_enabled, replay_root=replay_root
    )
    from .local_metadata import recognize_local_declarations

    local_metadata = recognize_local_declarations(
        work, rows, client, output, enabled=review_enabled, replay_root=replay_root
    )
    if local_metadata["status"] not in ("legacy_not_available", "not_available"):
        metadata["local"] = local_metadata
    contexts = []
    requests = []
    for row in rows:
        if row.registry is None:
            continue
        padded, registry, crop, analysis = _padded(row, work)
        ids = tuple(
            cid
            for t in row.tokens
            if t.role in ("note", "rest")
            and len(t.candidate_ids) == 1
            and t.geometry
            and t.geometry.bodies
            for cid in t.candidate_ids
        )
        candidates = detect_attachment_candidates(analysis, registry, ids)
        text_marks = [
            c
            for c in candidates
            if any(touches(page_box(padded, c.bounds), b) for b in text_exclusions)
        ]
        missing_owners = {owner for c in text_marks for owner in c.owners}
        candidates = tuple(c for c in candidates if c not in text_marks)
        relations = resolve_attachment_relations(candidates)
        write_json(
            directory / f"row_{row.row.index}-candidates.json",
            {
                "version": 1,
                "work_y_top": padded.work_y_top,
                "transform": padded.transform,
                "registry_sha256": registry.digest,
                "candidates": candidates,
                "bounds_source": {
                    c.candidate_id: page_box(padded, c.bounds) for c in candidates
                },
            },
        )
        allowed = set()
        regions = []
        for number, left, right, tokens, bounded in _regions(row):
            region = MelodyRegionResult(f"r{row.row.index}:m{number}", "pending")
            regions.append((region, tokens, bounded))
            selected = [
                c
                for c in registry.candidates
                if c.candidate_id in {cid for t in tokens for cid in t.candidate_ids}
            ]
            bands = {band for c in selected for band in c.band_ids}
            if len(bands) != 1 or any(
                t.role == "chord" or not t.geometry.bodies for t in tokens
            ):
                region.status = "unsupported"
                region.reasons = ["多基线、和弦或主体定位不完整"]
                continue
            unclaimed = [
                c
                for c in registry.candidates
                if c.kind == "digit"
                and left < c.bounds.cx < right
                and set(c.band_ids) & bands
                and c.candidate_id not in ids
            ]
            if unclaimed:
                region.status = "unknown"
                region.reasons = ["小节存在粘连或未确认主体"]
            for t in tokens:
                if len(t.candidate_ids) == 1:
                    allowed.add(t.candidate_ids[0])
        resolved = {r.candidate_id for r in relations}
        uncertain = [
            c
            for c in candidates
            if c.candidate_id not in resolved and set(c.owners) & allowed
        ]
        # Keep a connected ownership group in a single request. Never split a
        # shared ambiguous mark across two independently accepted decisions.
        groups = []
        for c in uncertain:
            owners = set(c.owners) & allowed
            matches = [g for g in groups if g & owners]
            for g in matches:
                owners |= g
                groups.remove(g)
            groups.append(owners)
        context = {
            "row": row,
            "padded": padded,
            "registry": registry,
            "crop": crop,
            "analysis": analysis,
            "candidates": candidates,
            "relations": relations,
            "regions": regions,
            "missing": missing_owners,
            "reviews": [],
        }
        contexts.append(context)
        for i, owners in enumerate(groups):
            if len(owners) > 6 or not review_enabled:
                continue
            ids_group = tuple(sorted(owners))
            marks = tuple(c for c in uncertain if set(c.owners) & owners)
            image = render_attachment_atlas(crop, registry, ids_group, marks)
            request = make_review(
                directory,
                f"r{row.row.index:04d}-review{i:04d}",
                image,
                ids_group,
                marks,
            )
            requests.append((context, request))

    def review(request: AttachmentReviewRequest) -> AttachmentReviewResult:
        if replay_root is not None:
            previous = replay_root / "melody-evidence"
            payload = json.loads(
                (previous / f"{request.request_id}-request.json").read_text(
                    encoding="utf-8"
                )
            )
            if payload["sha256"] != request.payload_sha256:
                raise EngineError("局部复核请求与冻结输入不一致", 5)
            saved = json.loads(
                (previous / f"{request.request_id}-result.json").read_text(
                    encoding="utf-8"
                )
            )
            if saved["status"] in ("failed", "not_available"):
                return AttachmentReviewResult(
                    request.request_id,
                    unknown_ids=[c.candidate_id for c in request.candidates],
                    status=saved["status"],
                    reason=saved["reason"],
                )
            content = saved["raw_response"]
            finish = saved.get("finish_reason")
        elif client is None or not hasattr(client, "review_attachments"):
            return AttachmentReviewResult(
                request.request_id,
                unknown_ids=[c.candidate_id for c in request.candidates],
                status="not_available",
                reason="没有配置局部复核客户端",
            )
        else:
            try:
                completion = client.review_attachments(request)
                content = completion.content
                finish = completion.finish_reason
            except Exception as exc:
                return AttachmentReviewResult(
                    request.request_id,
                    unknown_ids=[c.candidate_id for c in request.candidates],
                    status="failed",
                    reason=type(exc).__name__,
                )
        result = parse_attachment_review(content, request)
        result.finish_reason = finish
        if finish not in (None, "stop"):
            result.relations = []
            result.unknown_ids = [c.candidate_id for c in request.candidates]
            result.status = "invalid"
            result.reason = "模型输出截断或未完成"
        return result

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {
            executor.submit(review, request): (context, request)
            for context, request in requests
        }
        for future in as_completed(futures):
            context, request = futures[future]
            result = future.result()
            save_review(directory, request, result)
            context["relations"].extend(result.relations)
            context["missing"].update(result.missing_evidence)
            context["reviews"].append(
                {"request_id": request.request_id, "status": result.status}
            )
            logger.info("属性复核完成 %s: %s", request.request_id, result.status)
    all_regions = []
    for ctx in contexts:
        row = ctx["row"]
        for region, tokens, bounded in ctx["regions"]:
            if region.status == "unsupported":
                all_regions.append(region)
                continue
            state = {}
            state_uncertain = not bounded or region.status == "unknown"
            note_texts = []
            for t in tokens:
                if len(t.candidate_ids) != 1:
                    continue
                body_id = t.candidate_ids[0]
                n = attributes_for_body(
                    body_id,
                    make_source_id(row.row.index, t.index),
                    t.text,
                    ctx["registry"],
                    ctx["candidates"],
                    ctx["relations"],
                    missing_evidence=body_id in ctx["missing"],
                )
                n, serialized = finalize_note_attributes(n)
                octave = n.fields["octave"]
                acc = n.fields["accidental"]
                state_key = (n.degree, octave.value)
                if octave.status == "confirmed" and acc.status == "confirmed":
                    if acc.value != "none":
                        state[state_key] = acc.value
                    if state_key in state:
                        n.effective_accidental = AttributeValue(
                            state[state_key], "confirmed", source="measure"
                        )
                    elif (
                        metadata["key"]["status"] == "confirmed"
                        and not metadata["changes"]
                        and not state_uncertain
                    ):
                        n.effective_accidental = AttributeValue(
                            "none", "confirmed", source="key_and_measure"
                        )
                    else:
                        n.effective_accidental = AttributeValue(
                            None, "unknown", reason="调号或小节起点未确认"
                        )
                else:
                    state.clear()
                    state_uncertain = True
                region.notes.append(n)
                if n.complete:
                    note_texts.append(serialized)
                _render_attributes(ctx, t, n)
            if region.status == "pending":
                region.status = (
                    "confirmed"
                    if region.notes and all(n.complete for n in region.notes)
                    else "unknown"
                )
            if region.status == "confirmed":
                region.text = " ".join(note_texts) + (" |" if bounded else "")
                region.measure_duration = sum(
                    (n.duration for n in region.notes), Fraction(0)
                )
                region.meter_status = "unknown" if bounded else "incomplete_measure"
                if (
                    bounded
                    and metadata["meter"]["status"] == "confirmed"
                    and not metadata["changes"]
                ):
                    num, den = map(int, metadata["meter"]["value"].split("/"))
                    region.meter_status = (
                        "consistent"
                        if region.measure_duration == Fraction(num * 4, den)
                        else "conflict"
                    )
                    if region.meter_status == "conflict":
                        region.reasons.append("小节时值冲突；未修改音符")
                for token, n in zip(tokens, region.notes, strict=True):
                    token.text = finalize_note_attributes(n)[1]
            all_regions.append(region)
        row.jianpu_text = (
            (
                "// 实验性单旋律属性；未知区域保留主体，不能直接播放"
                + chr(10)
                + " ".join(t.text for t in row.tokens)
            )
            if row.tokens
            else row.jianpu_text
        )
        row.recognition_scope = "melody_experimental"
        ctx["reviews"].sort(key=lambda item: item["request_id"])
        write_json(
            directory / f"row_{row.row.index}-relations.json",
            {
                "relations": ctx["relations"],
                "reviews": ctx["reviews"],
                "missing_evidence": sorted(ctx["missing"]),
            },
        )
    result = {
        "version": 1,
        "scope": "single_melody_experimental",
        "metadata": metadata,
        "regions": all_regions,
        "melody_complete": False,
        "attributes_complete": bool(all_regions)
        and all(r.status == "confirmed" for r in all_regions),
        "review_enabled": review_enabled,
        "review_requests": len(requests),
        "warnings": ["调号、拍号和跨区域连续性未确认；不提供默认可播放导出"],
    }
    write_json(output / "melody.json", result)
    return serializable(result)


def _render_attributes(
    ctx: dict[str, Any], token: RecognizedToken, n: NoteAttributes
) -> None:
    # Append only relations backed by confirmed fields; body identity never changes.
    g = token.geometry
    row = ctx["padded"]
    marks = {c.candidate_id: c for c in ctx["candidates"]}
    g.primitives = [
        p
        for p in g.primitives
        if p.value not in ("underline", "extension", "octave", "augmentation")
    ]
    registry = ctx["registry"]
    body = next(c for c in registry.candidates if c.candidate_id == n.body_id)
    neighbors = [
        c.bounds
        for c in registry.candidates
        if c.kind in ("digit", "barline")
        and set(c.band_ids) & set(body.band_ids)
        and c.candidate_id != n.body_id
    ]
    left = max(
        ((b.cx + body.bounds.cx) / 2 for b in neighbors if b.cx < body.bounds.cx),
        default=0,
    )
    right = min(
        ((b.cx + body.bounds.cx) / 2 for b in neighbors if b.cx > body.bounds.cx),
        default=registry.width,
    )
    ids = {
        cid
        for f in n.fields.values()
        if f.status == "confirmed"
        for cid in f.evidence_ids
    }
    for relation in ctx["relations"]:
        if relation.candidate_id not in ids or n.body_id not in relation.body_ids:
            continue
        c = marks[relation.candidate_id]
        if relation.kind in ("octave_up", "octave_down", "augmentation"):
            add_shape(
                row,
                g,
                "dot",
                c.bounds,
                "octave" if relation.kind.startswith("octave") else "augmentation",
            )
        elif relation.kind in ("sharp", "flat", "natural"):
            add_shape(
                row,
                g,
                "glyph",
                c.bounds,
                {"sharp": "♯", "flat": "♭", "natural": "♮"}[relation.kind],
            )
        elif relation.kind == "extension" and c.line:
            add_line(row, g, c.line, "extension")
        elif relation.kind == "underline" and c.line:
            from ..models.geometry import Box

            start, end = max(left, c.bounds.x), min(right, c.bounds.right)
            if end > start:
                add_line(
                    row,
                    g,
                    c.line,
                    "underline",
                    Box(start, c.bounds.y, end - start, c.bounds.height),
                )
    g.status = "partial"
    g.warnings.append("局部属性已处理；区域音乐语义仍需核对")
