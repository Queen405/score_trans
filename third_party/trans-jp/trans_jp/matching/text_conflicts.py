from __future__ import annotations

from dataclasses import asdict, replace
from ..models.geometry import Box
from ..models.contracts import RowSegment
from ..models.candidates import CandidateRegistry, LocatedCandidate
from ..models.lyrics import LyricsResult


def touches(a: Box, b: Box) -> bool:
    return min(a.right, b.right) > max(a.x, b.x) and min(a.bottom, b.bottom) > max(
        a.y, b.y
    )


def body_text_conflicts(
    rows: list[RowSegment], registries: list[CandidateRegistry], result: LyricsResult
) -> dict[str, str]:
    if result.version >= 4:
        return body_decisions_v4(rows, registries, result)
    blocked = {}
    for row, registry in zip(rows, registries, strict=True):
        for c in registry.candidates:
            if c.kind not in ("digit", "barline"):
                continue
            b = replace(c.bounds, y=c.bounds.y + row.work_y_top)
            # A rectangle overlap alone is not ownership. Use the actual ink body
            # center inside the fine band. Unknown/mixed evidence quarantines it.
            owners = [
                r
                for r in result.regions
                if (rb := Box(**r["bounds_work"])).x <= b.cx < rb.right
                and rb.y <= b.cy < rb.bottom
            ]
            non_music = [r for r in owners if r["role"] != "notation"]
            if not non_music and owners:
                continue
            reason = "text_music_conflict"
            if non_music and all(
                r["role"] in ("lyrics", "other_text") for r in non_music
            ):
                reason = "text_excluded"
            blocked[c.candidate_id] = reason
            result.conflicts.append(
                {
                    "candidate_id": c.candidate_id,
                    "status": reason,
                    "region_ids": [r["id"] for r in non_music],
                    "bounds": asdict(row.transform.box(b)),
                    "bounds_work": asdict(b),
                    "reason": "文字区域或版面类型尚未确认",
                }
            )
    return blocked


def attach_note_candidates(
    result: LyricsResult,
    rows: list,
    registries: list[CandidateRegistry],
    blocked: dict[str, str],
) -> None:
    candidates = [
        (c.candidate_id, replace(c.bounds, y=c.bounds.y + row.work_y_top))
        for row, reg in zip(rows, registries, strict=True)
        for c in reg.candidates
        if c.kind == "digit" and c.candidate_id not in blocked
    ]
    notation = [r for r in result.regions if r["role"] == "notation"]
    for line in result.lines:
        b = line.bounds_work
        preceding = [
            r
            for r in notation
            if (rb := Box(**r["bounds_work"])).bottom <= b.y
            and b.y - rb.bottom < max(b.height * 8, 60)
            and min(b.right, rb.right) > max(b.x, rb.x)
        ]
        preceding.sort(key=lambda r: Box(**r["bounds_work"]).bottom, reverse=True)
        if preceding:
            line.associated_region_id = preceding[0]["id"]
        for token in line.tokens:
            t = token.bounds_work
            choices = [
                (t.y - c.bottom, abs(c.cx - t.cx), cid)
                for cid, c in candidates
                if c.bottom <= t.y
                and t.y - c.bottom < max(60, t.height * 8)
                and abs(c.cx - t.cx) < max(c.width, t.width) * 1.5
            ]
            token.candidate_note_ids = tuple(v[2] for v in sorted(choices)[:2])
    groups: dict[str, list] = {}
    for line in result.lines:
        if line.associated_region_id:
            groups.setdefault(line.associated_region_id, []).append(line)
    for lines in groups.values():
        baselines = []
        for line in sorted(
            lines, key=lambda line: (line.bounds_work.y, line.bounds_work.x)
        ):
            y = line.bounds_work.cy
            slot = next(
                (
                    i
                    for i, v in enumerate(baselines)
                    if abs(y - v) < line.bounds_work.height * 0.7
                ),
                None,
            )
            if slot is None:
                baselines.append(y)
                slot = len(baselines) - 1
            line.verse_index = slot + 1


def unique_word_alignment(
    observed: list[str | None], expected: list[str]
) -> dict[int, int]:
    """Accept only matches present in every maximum monotonic exact alignment."""
    n, m = len(observed), len(expected)
    forward = [[0] * (m + 1) for _ in range(n + 1)]
    backward = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n):
        for j in range(m):
            forward[i + 1][j + 1] = max(
                forward[i][j + 1],
                forward[i + 1][j],
                forward[i][j] + int(observed[i] == expected[j]),
            )
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            backward[i][j] = max(
                backward[i + 1][j],
                backward[i][j + 1],
                backward[i + 1][j + 1] + int(observed[i] == expected[j]),
            )
    best = forward[n][m]
    result = {}
    for i in range(n):
        # If an optimum can skip this crop, its identity is not established.
        if max(forward[i][j] + backward[i + 1][j] for j in range(m + 1)) == best:
            continue
        choices = [
            j
            for j in range(m)
            if observed[i] == expected[j]
            and forward[i][j] + 1 + backward[i + 1][j + 1] == best
        ]
        if len(choices) == 1:
            result[i] = choices[0]
    return result


def _contains_center(region: dict, b: Box) -> bool:
    box = Box(**region["bounds_work"])
    return box.x <= b.cx < box.right and box.y <= b.cy < box.bottom


def local_music_support(
    candidate: LocatedCandidate, registry: CandidateRegistry
) -> bool:
    b = candidate.bounds
    peers = [
        c
        for c in registry.candidates
        if c.kind == "digit"
        and not c.ambiguous
        and set(c.band_ids) & set(candidate.band_ids)
        and 0.55 * b.height <= c.bounds.height <= 1.8 * b.height
        and abs(c.bounds.cy - b.cy) < b.height * 0.6
    ]
    return (
        len(peers) >= 3
        and max(c.bounds.cx for c in peers) - min(c.bounds.cx for c in peers)
        > b.height * 2
    )


def body_decisions_v4(
    rows: list[RowSegment], registries: list[CandidateRegistry], result: LyricsResult
) -> dict[str, str]:
    blocked = {}
    result.decisions = []
    result.conflicts = []
    for row, registry in zip(rows, registries, strict=True):
        for c in registry.candidates:
            if c.kind not in ("digit", "barline"):
                continue
            b = replace(c.bounds, y=c.bounds.y + row.work_y_top)
            owners = [r for r in result.regions if _contains_center(r, b)]
            # Children supersede ONLY the portion actually covered by their ink.
            child_parents = {
                r["parent_region_id"] for r in owners if r.get("parent_region_id")
            }
            active = [r for r in owners if r["id"] not in child_parents]
            definite = [
                r
                for r in active
                if r["role"] in ("lyrics", "other_text") and r["status"] == "observed"
            ]
            notation = [
                r
                for r in active
                if r["role"] == "notation" and r["status"] == "observed"
            ]
            recovered = any(
                r.get("parent_region_id")
                or r.get("request_id", "").startswith("rescue-")
                for r in active
            )
            support = local_music_support(c, registry)
            if definite and not notation:
                state, reason = "excluded", "confirmed_text_region"
            elif (
                active
                and len(notation) == len(active)
                and not c.ambiguous
                and (not recovered or support)
            ):
                state, reason = (
                    "eligible",
                    "notation_region_and_structure" if recovered else "notation_region",
                )
            else:
                state, reason = (
                    "pending",
                    "text_music_conflict" if active else "region_missing",
                )
                if notation and recovered and not support:
                    reason = "insufficient_music_structure"
            decision = {
                "candidate_id": c.candidate_id,
                "state": state,
                "reason": reason,
                "region_ids": [r["id"] for r in active],
                "request_ids": sorted(
                    {r["request_id"] for r in active if r.get("request_id")}
                ),
                "bounds": asdict(row.transform.box(b)),
                "bounds_work": asdict(b),
                "music_structure_support": support,
                "observed_label": None,
                "row_index": row.index,
            }
            result.decisions.append(decision)
            if state != "eligible":
                status = (
                    "text_excluded" if state == "excluded" else "text_music_conflict"
                )
                blocked[c.candidate_id] = status
                result.conflicts.append({**decision, "status": status})
    return blocked


def finish_body_decisions(result: LyricsResult, rows: list, observations: dict) -> None:
    accepted = {cid for r in rows for t in r.tokens for cid in t.candidate_ids}
    for d in result.decisions:
        observed = observations.get(d["candidate_id"], {})
        if observed.get("status") == "recognized":
            d["observed_label"] = observed.get("label")
        d["body_observation"] = observed
        if d["state"] == "eligible":
            d["state"] = "accepted" if d["candidate_id"] in accepted else "pending"
            if d["state"] == "pending":
                d["reason"] = "body_classification_unresolved"
    result.pending = [dict(d) for d in result.decisions if d["state"] == "pending"]


def active_text_exclusions(result: LyricsResult) -> tuple[Box, ...]:
    if result.version == 3:
        return tuple(
            Box(**r["bounds"]) for r in result.regions if r["role"] != "notation"
        )
    parents = {
        r["parent_region_id"] for r in result.regions if r.get("parent_region_id")
    }
    exclusions = [
        Box(**r["bounds"])
        for r in result.regions
        if r["role"] != "notation" and r["id"] not in parents
    ]
    for parent in result.regions:
        if parent["id"] not in parents or parent["role"] == "notation":
            continue
        residual = [Box(**parent["bounds"])]
        for child in result.regions:
            if (
                child.get("parent_region_id") != parent["id"]
                or child["role"] != "notation"
                or child["status"] != "observed"
            ):
                continue
            cut = Box(**child["bounds"])
            residual = [piece for box in residual for piece in subtract_box(box, cut)]
        exclusions.extend(residual)
    exclusions.extend(
        Box(**d["bounds"])
        for d in result.decisions
        if d["state"] in ("pending", "excluded")
    )
    return tuple(exclusions)


def subtract_box(box: Box, cut: Box) -> list[Box]:
    if not touches(box, cut):
        return [box]
    left, top = max(box.x, cut.x), max(box.y, cut.y)
    right, bottom = min(box.right, cut.right), min(box.bottom, cut.bottom)
    return [
        b
        for b in [
            Box(box.x, box.y, box.width, top - box.y),
            Box(box.x, bottom, box.width, box.bottom - bottom),
            Box(box.x, top, left - box.x, bottom - top),
            Box(right, top, box.right - right, bottom - top),
        ]
        if b.width > 0 and b.height > 0
    ]
