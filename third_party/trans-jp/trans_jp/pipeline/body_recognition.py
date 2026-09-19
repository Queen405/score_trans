from __future__ import annotations

import logging
from ..models.classification import (
    CLASSIFIER_VERSION,
    BATCH_SIZE,
    CandidateBatchRequest,
    CandidateBatchResult,
)
from ..models.candidates import CandidateRegistry
from ..models.contracts import RowSegment, RowResult, CompletionResult
from ..recognition.candidate_classifier import CandidateClassifier, classify_batches
from ..structure.body_assembler import partition_candidates, assemble_body_tokens
from ..rendering.candidate_atlas import render_atlases
from ..io.classification_batches import save_batch_request, write_batch_result
from ..io.candidate_requests import write_manifest
from ..models.errors import EngineError

logger = logging.getLogger("trans_jp.pipeline")


def recognize_bodies(
    rows: list[RowSegment],
    crops: list,
    registries: list[CandidateRegistry],
    client: CandidateClassifier,
    manifest: dict,
    *,
    concurrency: int,
    blocked: dict[str, str] | None = None,
    observations: dict | None = None,
    supplement_client: CandidateClassifier | None = None,
) -> list[RowResult]:
    blocked = blocked or {}
    requests = []
    supplemental_batches = set()
    supplemented_ids = set()
    output = rows[0].image_path.parent.parent
    manifest.update(
        version=3,
        recognition_scope="bodies_only",
        classifier_version=CLASSIFIER_VERSION,
        batches=[],
    )
    try:
        for row, crop, registry in zip(rows, crops, registries, strict=True):
            if hasattr(client, "groups_for_row"):
                groups = client.groups_for_row(row.index)
                covered = {cid for _, ids in groups for cid in ids}
                missing = [
                    c.candidate_id
                    for c in registry.candidates
                    if c.kind in ("digit", "barline")
                    and not c.ambiguous
                    and c.candidate_id not in covered
                    and c.candidate_id not in blocked
                ]
                if supplement_client is not None:
                    next_index = max((i for i, _ in groups), default=-1) + 1
                    for start in range(0, len(missing), BATCH_SIZE):
                        ids = tuple(missing[start : start + BATCH_SIZE])
                        index = next_index + start // BATCH_SIZE
                        groups.append((index, ids))
                        supplemental_batches.add(f"r{row.index:04d}:b{index:04d}")
                        supplemented_ids.update(ids)
            else:
                groups = [
                    (
                        index,
                        tuple(
                            c.candidate_id
                            for c in candidates
                            if c.candidate_id not in blocked
                        ),
                    )
                    for index, candidates in enumerate(partition_candidates(registry))
                ]
            for index, ids in groups:
                if not ids:
                    continue
                atlas = render_atlases(crop, registry, candidate_ids=ids)[0]
                requests.append(save_batch_request(row, registry, index, ids, atlas))
        if supplemented_ids:
            manifest["lyrics_excluded_candidates"] = sorted(
                set(manifest.get("lyrics_excluded_candidates", [])) - supplemented_ids
            )
        write_manifest(output, manifest)
    except (OSError, ValueError) as exc:
        raise EngineError(f"批次输入写入失败: {exc}", 4) from exc

    def save(request: CandidateBatchRequest, result: CandidateBatchResult) -> None:
        try:
            manifest["batches"].append(write_batch_result(request, result))
            manifest["batches"].sort(key=lambda b: b["batch_id"])
            write_manifest(output, manifest)
        except (OSError, ValueError) as exc:
            raise EngineError(f"批次结果写入失败: {exc}", 4) from exc
        logger.info(
            "候选识别进度 %d/%d (%s)",
            len(manifest["batches"]),
            len(requests),
            result.status,
        )

    class Router:
        def classify(self, request: CandidateBatchRequest) -> CompletionResult:
            if request.batch_id in supplemental_batches:
                return supplement_client.classify(request)
            return client.classify(request)

    results = classify_batches(
        requests, Router(), concurrency=concurrency, on_result=save
    )
    by_row = {registry.row_index: [] for registry in registries}
    for request, result in zip(requests, results, strict=True):
        by_row[request.registry.row_index].append(result)
    if observations is not None:
        for batch in results:
            for item in batch.items:
                observations[item.candidate_id] = {
                    "label": item.label,
                    "status": item.status,
                    "batch_id": batch.batch_id,
                }
    return [
        assemble_body_tokens(registry, by_row[row.index], row, blocked=blocked)
        for row, registry in zip(rows, registries, strict=True)
    ]
