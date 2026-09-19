from __future__ import annotations

from collections import Counter, defaultdict
from ..models.candidates import CandidateRegistry, LocatedCandidate
from ..models.classification import BATCH_SIZE, CandidateBatchResult
from ..models.contracts import RowResult, RowSegment, RecognizedToken


def partition_candidates(
    registry: CandidateRegistry,
) -> list[tuple[LocatedCandidate, ...]]:
    candidates = sorted(
        (
            c
            for c in registry.candidates
            if c.kind in ("digit", "barline") and not c.ambiguous
        ),
        key=lambda c: (min(c.band_ids), c.bounds.cx, c.candidate_id),
    )
    return [
        tuple(candidates[i : i + BATCH_SIZE])
        for i in range(0, len(candidates), BATCH_SIZE)
    ]


def assemble_body_tokens(
    registry: CandidateRegistry,
    batches: list[CandidateBatchResult],
    row: RowSegment,
    *,
    blocked: dict[str, str] | None = None,
) -> RowResult:
    blocked = blocked or {}
    by_id = {c.candidate_id: c for c in registry.candidates}
    all_items = [item for batch in batches for item in batch.items]
    counts = Counter(item.candidate_id for item in all_items)
    accepted, unresolved, warnings = {}, [], []
    for batch in batches:
        warnings.extend(batch.warnings)
        if batch.registry_sha256 != registry.digest:
            raise ValueError("classification registry hash mismatch")
        for item in batch.items:
            c = by_id.get(item.candidate_id)
            if c is None or c.kind not in ("digit", "barline"):
                warnings.append("忽略注册表外的分类结果")
                continue
            if counts[item.candidate_id] != 1 or c.ambiguous:
                unresolved.append(
                    {
                        "candidate_id": item.candidate_id,
                        "reason": "重复分类或主体粘连",
                        "status": "candidate_invalid",
                    }
                )
            elif item.status != "recognized":
                unresolved.append(
                    {
                        "candidate_id": item.candidate_id,
                        "reason": item.reason,
                        "status": item.status,
                    }
                )
            elif (
                item.kind == c.kind == "digit" and item.label in tuple("01234567")
            ) or (item.kind == c.kind == "barline" and item.label == "barline"):
                accepted[item.candidate_id] = item
            else:
                unresolved.append(
                    {
                        "candidate_id": item.candidate_id,
                        "reason": "非法分类标签",
                        "status": "candidate_invalid",
                    }
                )
    for c in registry.candidates:
        if c.kind in ("digit", "barline") and c.candidate_id not in counts:
            unresolved.append(
                {
                    "candidate_id": c.candidate_id,
                    "reason": "主体粘连" if c.ambiguous else "没有分类结果",
                    "status": "candidate_unresolved",
                }
            )
    for cid, reason in blocked.items():
        accepted.pop(cid, None)
        unresolved = [item for item in unresolved if item["candidate_id"] != cid]
        if cid in by_id:
            unresolved.append(
                {
                    "candidate_id": cid,
                    "status": reason,
                    "reason": "文字区域排除或类型冲突",
                }
            )
    conflict_ids = {
        cid
        for cid in accepted
        if any(other in accepted for other in by_id[cid].conflicts)
    }
    for cid in sorted(conflict_ids):
        accepted.pop(cid)
        unresolved.append(
            {
                "candidate_id": cid,
                "reason": "互斥墨迹同时被确认",
                "status": "candidate_invalid",
            }
        )
    digits = [by_id[cid] for cid in accepted if by_id[cid].kind == "digit"]
    bars = sorted(
        (by_id[cid] for cid in accepted if by_id[cid].kind == "barline"),
        key=lambda c: c.bounds.cx,
    )
    tokens = []

    def append(text: str, role: str, candidates: tuple[str, ...] = ()) -> None:
        tokens.append(
            RecognizedToken(
                len(tokens), text, None, None, role, candidate_ids=candidates
            )
        )

    # Physical intervals, never VLM's declared measures. Boundary errors stay local.
    left = -1.0
    for boundary in [*bars, None]:
        right = boundary.bounds.cx if boundary else registry.width + 1
        interval = [c for c in digits if left < c.bounds.cx < right]
        groups = defaultdict(list)
        for c in interval:
            groups[min(c.band_ids)].append(c)
        for band in groups:
            groups[band].sort(key=lambda c: c.bounds.cx)
        # Only an isolated vertical column can form a visual chord. Parallel
        # melodic bands retain independent lanes; timing is intentionally unknown.
        visual_chord = (
            len(interval) > 1
            and all(len(group) == 1 for group in groups.values())
            and max(c.bounds.cx for c in interval) - min(c.bounds.cx for c in interval)
            < min(c.bounds.height for c in interval) * 0.45
            and all(accepted[c.candidate_id].label != "0" for c in interval)
        )
        if visual_chord:
            column = sorted(interval, key=lambda c: c.bounds.cy)
            append(
                "[" + "+".join(accepted[c.candidate_id].label for c in column) + "]",
                "chord",
                tuple(c.candidate_id for c in column),
            )
        else:
            ordered_bands = sorted(
                groups,
                key=lambda band: (
                    sum(c.bounds.cy for c in groups[band]) / len(groups[band])
                ),
            )
            for index, band in enumerate(ordered_bands):
                if index:
                    append("&", "other")
                for c in groups[band]:
                    item = accepted[c.candidate_id]
                    append(
                        item.label,
                        "rest" if item.label == "0" else "note",
                        (c.candidate_id,),
                    )
        if boundary:
            append(
                "||" if len(boundary.lines) > 1 else "|",
                "barline",
                (boundary.candidate_id,),
            )
            left = right
    # No synthesized key/meter/tempo: this text is not a playable score.
    text = (
        "// 主体预览：八度、时值及声部时间关系未确认\n"
        + " ".join(t.text for t in tokens)
        if tokens
        else ""
    )
    return RowResult(
        row,
        "notation" if digits else "other",
        text,
        tokens,
        warnings=warnings,
        schema_version=3,
        registry=registry,
        unresolved_candidates=unresolved,
        complete=not unresolved,
        recognition_scope="bodies_only",
        batch_diagnostics=[
            {
                "batch_id": b.batch_id,
                "status": b.status,
                "recognized": sum(i.status == "recognized" for i in b.items),
                "total": len(b.items),
            }
            for b in batches
        ],
    )
