from __future__ import annotations

from collections import defaultdict
from ..models.contracts import RowResult
from ..models.candidates import LocatedCandidate
from ..models.notation import Notation


def bind_candidates(
    result: RowResult, notes: dict[int, Notation], contexts: dict[int, tuple[int, int]]
) -> tuple[dict[int, list[LocatedCandidate]], dict[int, list[str]]]:
    registry = result.registry
    candidates = {c.candidate_id: c for c in registry.candidates} if registry else {}
    bound, rejected = {}, {}
    users = defaultdict(set)

    def reject(index: int, reason: str) -> None:
        rejected.setdefault(index, []).append(reason)

    for t in result.tokens:
        note = notes.get(t.index)
        if note is None or note.kind == "relation":
            continue
        if registry is None or (
            registry.row_index,
            registry.width,
            registry.height,
        ) != (result.row.index, result.row.width, result.row.height):
            reject(t.index, "候选注册表缺失或行尺寸不一致")
            continue
        for cid in t.candidate_ids:
            if cid in candidates:
                users[cid].add(t.index)
        if not t.candidate_ids or any(cid not in candidates for cid in t.candidate_ids):
            reject(t.index, "缺少候选编号或编号不属于当前行")
            continue
        if len(set(t.candidate_ids)) != len(t.candidate_ids):
            reject(t.index, "重复引用候选编号")
            continue
        selected = [candidates[cid] for cid in t.candidate_ids]
        kind = {"note": "digit", "barline": "barline", "extension": "extension"}[
            note.kind
        ]
        count = (
            len(note.pitches)
            if note.kind == "note"
            else note.extensions
            if note.kind == "extension"
            else 1
        )
        if len(selected) != count or any(c.kind != kind for c in selected):
            reject(t.index, "候选类型或主体数量与记法不符")
            continue
        if any(
            c.ambiguous
            or c.bounds.width <= 0
            or c.bounds.height <= 0
            or c.bounds.x < 0
            or c.bounds.y < 0
            or c.bounds.right > registry.width
            or c.bounds.bottom > registry.height
            for c in selected
        ):
            reject(t.index, "候选粘连、几何无效或越界")
            continue
        if note.kind == "note" and len(selected) > 1:
            h = max(c.bounds.height for c in selected)
            if (
                any(a.bounds.cy >= b.bounds.cy for a, b in zip(selected, selected[1:]))
                or max(c.bounds.cx for c in selected)
                - min(c.bounds.cx for c in selected)
                > h * 0.45
            ):
                reject(t.index, "和弦候选必须从高到低且垂直对齐")
                continue
        bound[t.index] = selected

    for cid, indexes in users.items():
        affected = set(indexes)
        for other in candidates[cid].conflicts:
            affected.update(users.get(other, ()))
        if len(indexes) > 1 or any(
            other in users for other in candidates[cid].conflicts
        ):
            for index in affected:
                reject(index, "候选重复占用或墨迹互斥冲突")

    ordered = defaultdict(list)
    for index, selected in bound.items():
        if index not in rejected and notes[index].kind != "barline":
            ordered[contexts[index]].append((index, selected[-1]))
    for items in ordered.values():
        for i, (index, a) in enumerate(items):
            for other_index, b in items[i + 1 :]:
                if b.bounds.cx <= a.bounds.cx:
                    reject(index, "同小节同声部阅读顺序冲突")
                    reject(other_index, "同小节同声部阅读顺序冲突")
        digits = [(i, c) for i, c in items if notes[i].kind == "note"]
        if digits and not set.intersection(*(set(c.band_ids) for _, c in digits)):
            for index, _ in digits:
                reject(index, "同声部候选分属不同基线带")

    bars = [
        (i, cs[0])
        for i, cs in bound.items()
        if notes[i].kind == "barline" and i not in rejected
    ]
    boundary_conflicts = set()
    for index, c in bars:
        m, _ = contexts[index]
        for other, selected in bound.items():
            if other == index or other in rejected:
                continue
            other_m, _ = contexts[other]
            x = selected[-1].bounds.cx
            if (other_m == m and other < index and x >= c.bounds.cx) or (
                other_m == m + 1 and x <= c.bounds.cx
            ):
                boundary_conflicts.update((index, other))
    for index in sorted(boundary_conflicts):
        reject(index, "小节边界与候选位置冲突")
    return {i: cs for i, cs in bound.items() if i not in rejected}, rejected
