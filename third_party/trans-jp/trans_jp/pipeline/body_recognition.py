from __future__ import annotations

import logging
from ..models.classification import (
    CLASSIFIER_VERSION,
    CandidateBatchRequest,
    CandidateBatchResult,
)
from ..models.candidates import CandidateRegistry
from ..models.contracts import RowSegment, RowResult
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
) -> list[RowResult]:
    requests = []
    output = rows[0].image_path.parent.parent
    manifest.update(
        version=3,
        recognition_scope="bodies_only",
        classifier_version=CLASSIFIER_VERSION,
        batches=[],
    )
    try:
        for row, crop, registry in zip(rows, crops, registries, strict=True):
            for index, candidates in enumerate(partition_candidates(registry)):
                ids = tuple(c.candidate_id for c in candidates)
                atlas = render_atlases(crop, registry, candidate_ids=ids)[0]
                requests.append(save_batch_request(row, registry, index, ids, atlas))
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

    results = classify_batches(
        requests, client, concurrency=concurrency, on_result=save
    )
    by_row = {registry.row_index: [] for registry in registries}
    for request, result in zip(requests, results, strict=True):
        by_row[request.registry.row_index].append(result)
    return [
        assemble_body_tokens(registry, by_row[row.index], row)
        for row, registry in zip(rows, registries, strict=True)
    ]
