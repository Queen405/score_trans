from __future__ import annotations

from dataclasses import asdict, replace
from ..models.geometry import Box
from ..models.contracts import RowSegment
from ..models.candidates import CandidateRegistry
from ..models.lyrics import LyricsResult


def touches(a: Box, b: Box) -> bool:
    return min(a.right, b.right) > max(a.x, b.x) and min(a.bottom, b.bottom) > max(
        a.y, b.y
    )


def body_text_conflicts(
    rows: list[RowSegment], registries: list[CandidateRegistry], result: LyricsResult
) -> dict[str, str]:
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
