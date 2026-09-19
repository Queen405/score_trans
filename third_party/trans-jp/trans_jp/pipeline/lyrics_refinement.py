from __future__ import annotations

from dataclasses import asdict, replace
from collections import defaultdict
import numpy as np
from PIL import Image
from ..models.contracts import RowSegment
from ..models.candidates import CandidateRegistry
from concurrent.futures import ThreadPoolExecutor
from ..models.lyrics import TextRegion
from ..models.geometry import Transform
from ..structure.text_refinement import split_mixed_region
from ..rendering.lyrics import text_atlas
from .text_evidence import TextEvidenceSession


def refine_regions(
    work: Image.Image,
    binary: np.ndarray,
    transform: Transform,
    regions: list[TextRegion],
    decisions: dict,
    session: TextEvidenceSession,
    concurrency: int,
    rows: list[RowSegment],
    registries: list[CandidateRegistry],
) -> tuple[list[TextRegion], dict, list[dict]]:
    targets = [
        r
        for r in regions
        if decisions[r.region_id]["role"] in ("mixed", "unknown")
        or decisions[r.region_id]["status"] != "observed"
    ]

    def refine(region: TextRegion):
        original = decisions[region.region_id]
        updates = {}
        events = []
        children = []
        if original.get("request_status") == "auth_failed":
            return (
                children,
                updates,
                [
                    {
                        "region_id": region.region_id,
                        "reason": "auth_failed",
                        "attempts": 0,
                    }
                ],
            )
        groups = [region]
        if original["role"] == "mixed":
            bands = defaultdict(list)
            parent = region.bounds_work
            for row, registry in zip(rows, registries, strict=True):
                for candidate in registry.candidates:
                    box = replace(
                        candidate.bounds, y=candidate.bounds.y + row.work_y_top
                    )
                    if (
                        candidate.kind == "digit"
                        and not candidate.ambiguous
                        and parent.x <= box.cx < parent.right
                        and parent.y <= box.cy < parent.bottom
                    ):
                        bands[(row.index, candidate.band_ids)].append(box)
            band_boxes = []
            for boxes in bands.values():
                if len(boxes) < 2:
                    continue
                union = boxes[0]
                for box in boxes[1:]:
                    union = union.union(box)
                band_boxes.append(union)
            children, erased = split_mixed_region(
                binary, region, transform, tuple(band_boxes)
            )
            events.append(
                {
                    "region_id": region.region_id,
                    "stage": "split",
                    "children": [asdict(c) for c in children],
                    "analysis_mask_erased_rules": erased,
                }
            )
            groups = children or [region]
        # Two HTTP requests TOTAL per original region, including split children.
        # At most 12 child crops per rescue; excess children stay pending.
        remaining = groups
        for attempt in range(2):
            if not remaining:
                break
            chosen = remaining[:12]
            request = session.request(
                f"rescue-{region.region_id.replace(':', '-')}-{attempt}",
                text_atlas(
                    work, [(r.region_id, r.bounds_work) for r in chosen], context=False
                ),
                tuple(
                    {"id": r.region_id, "bounds_work": asdict(r.bounds_work)}
                    for r in chosen
                ),
                "region_review",
            )
            results = session.evaluate(request, once=True)
            events.append(
                {
                    "region_id": region.region_id,
                    "request_id": request.request_id,
                    "attempt": attempt + 1,
                    "decisions": results,
                }
            )
            updates.update({d["id"]: d for d in results})
            if any(d.get("request_status") == "auth_failed" for d in results):
                break
            remaining = remaining[12:] + [
                r
                for r, d in zip(chosen, results, strict=True)
                if d["role"] in ("mixed", "unknown") or d["status"] != "observed"
            ]
        for child in children:
            updates.setdefault(
                child.region_id,
                {
                    "id": child.region_id,
                    "role": "unknown",
                    "text": None,
                    "status": "unresolved",
                    "reason": "rescue_budget_exhausted",
                },
            )
            updates[child.region_id]["parent_region_id"] = region.region_id
        return children, updates, events

    all_regions = list(regions)
    all_decisions = {k: dict(v) for k, v in decisions.items()}
    events = []
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        for children, updates, history in executor.map(refine, targets):
            all_regions.extend(children)
            all_decisions.update(updates)
            events.extend(history)
    return all_regions, all_decisions, events
