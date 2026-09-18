from __future__ import annotations

from ..models.candidates import CandidateRegistry
from ..models.geometry import Box
from ..models.melody import AttachmentCandidate
from ..models.raster import RowAnalysis, Filament


def overlap(a: Box, b: Box) -> float:
    return max(0, min(a.right, b.right) - max(a.x, b.x)) * max(
        0, min(a.bottom, b.bottom) - max(a.y, b.y)
    )


def detect_attachment_candidates(
    analysis: RowAnalysis, registry: CandidateRegistry, body_ids: tuple[str, ...]
) -> tuple[AttachmentCandidate, ...]:
    bodies = [
        c
        for c in registry.candidates
        if c.candidate_id in body_ids and c.kind == "digit"
    ]
    output = []
    for component in analysis.components:
        b = component.bounds
        if any(
            overlap(b, c.bounds)
            > min(b.width * b.height, c.bounds.width * c.bounds.height) * 0.6
            for c in (*bodies, *(c for c in registry.candidates if c.kind == "barline"))
        ):
            continue
        owners = set()
        kinds = set()
        for c in bodies:
            a = c.bounds
            h = a.height
            if not (
                a.x - h * 1.2 < b.cx < a.right + h * 1.2
                and a.y - h * 1.8 < b.cy < a.bottom + h * 1.8
            ):
                continue
            if (
                max(b.width, b.height) < h * 0.38
                and 0.4 < b.width / max(b.height, 1) < 2
            ):
                if abs(b.cx - a.cx) < h * 0.4 and a.y - h * 1.8 < b.cy < a.y:
                    kinds.add("octave_up")
                    owners.add(c.candidate_id)
                if abs(b.cx - a.cx) < h * 0.4 and a.bottom < b.cy < a.bottom + h * 1.8:
                    kinds.add("octave_down")
                    owners.add(c.candidate_id)
                if a.right < b.cx < a.right + h * 0.9 and abs(b.cy - a.cy) < h * 0.4:
                    kinds.add("augmentation")
                    owners.add(c.candidate_id)
            elif (
                a.x - h * 1.1 < b.cx < a.x
                and a.y - h * 0.3 < b.cy < a.bottom
                and h * 0.35 < b.height < h * 1.4
            ):
                kinds.update(("sharp", "flat", "natural", "non_music"))
                owners.add(c.candidate_id)
            elif b.width > h * 0.5 and b.height < h * 0.25:
                # Horizontal ink is handled by fitted physical lines.
                continue
            else:
                kinds.add("unclassified")
                owners.add(c.candidate_id)
        if kinds:
            output.append(
                AttachmentCandidate(
                    "",
                    b,
                    tuple(sorted(kinds)),
                    (component.candidate_id,),
                    tuple(sorted(owners)),
                )
            )
    horizontal = list(analysis.horizontal)
    # Thin disconnected strokes remain valid evidence even when the row-wide
    # scale estimate (often dominated by octave dots) rejects their filaments.
    for comp in analysis.components:
        b = comp.bounds
        if any(
            b.width > c.bounds.height * 0.35 and b.height < c.bounds.height * 0.18
            for c in bodies
        ):
            if not any(
                overlap(b, line.bounds) > b.width * b.height * 0.5
                for line in horizontal
            ):
                horizontal.append(
                    Filament(
                        "horizontal", ((b.x, b.cy), (b.right, b.cy)), b.height, 1.0, b
                    )
                )
    for i, line in enumerate(horizontal):
        b = line.bounds
        owners = []
        kinds = set()
        for c in bodies:
            a = c.bounds
            h = a.height
            if b.x <= a.cx <= b.right and a.bottom - 1 <= b.cy < a.bottom + h * 0.9:
                kinds.add("underline")
                owners.append(c.candidate_id)
            elif (
                a.right < b.x
                and b.right < registry.width
                and abs(b.cy - a.cy) < h * 0.28
                and h * 0.25 < b.width < h * 1.8
            ):
                intervening = any(
                    other.bounds.cx > a.cx
                    and other.bounds.x < b.right
                    and set(other.band_ids) & set(c.band_ids)
                    for other in registry.candidates
                    if other.kind in ("digit", "barline")
                    and other.candidate_id != c.candidate_id
                )
                if not intervening:
                    kinds.add("extension")
                    owners.append(c.candidate_id)
        if kinds:
            output.append(
                AttachmentCandidate(
                    "",
                    b,
                    tuple(sorted(kinds)),
                    (f"h{i}",),
                    tuple(sorted(set(owners))),
                    line,
                )
            )
    output.sort(key=lambda c: (c.bounds.y, c.bounds.x, c.kinds, c.component_ids))
    return tuple(
        AttachmentCandidate(
            f"r{registry.row_index:04}:a{i:04}",
            c.bounds,
            c.kinds,
            c.component_ids,
            c.owners,
            c.line,
        )
        for i, c in enumerate(output)
    )
