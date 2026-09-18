from __future__ import annotations

from collections import defaultdict
from ..models.candidates import CandidateRegistry
from ..models.melody import (
    AttachmentCandidate,
    AttachmentRelation,
    AttributeValue,
    NoteAttributes,
)


def resolve_attachment_relations(
    candidates: tuple[AttachmentCandidate, ...],
) -> list[AttachmentRelation]:
    relations = []
    for c in candidates:
        if len(c.kinds) == 1 and c.kinds[0] in (
            "octave_up",
            "octave_down",
            "augmentation",
            "underline",
            "extension",
        ):
            if len(c.owners) == 1 or c.kinds[0] == "underline":
                relations.append(
                    AttachmentRelation(c.candidate_id, c.owners, c.kinds[0])
                )
    return relations


def attributes_for_body(
    body_id: str,
    source_id: str,
    degree: str,
    registry: CandidateRegistry,
    candidates: tuple[AttachmentCandidate, ...],
    relations: list[AttachmentRelation],
    *,
    missing_evidence: bool = False,
) -> NoteAttributes:
    body = next(c for c in registry.candidates if c.candidate_id == body_id)
    b = body.bounds
    h = b.height
    relevant = [c for c in candidates if body_id in c.owners]
    by_id = {c.candidate_id: c for c in candidates}
    active = [r for r in relations if body_id in r.body_ids and r.status == "confirmed"]
    resolved = {r.candidate_id for r in relations if r.status == "confirmed"}
    residual = [c for c in relevant if c.candidate_id not in resolved]
    kinds = defaultdict(list)
    for r in active:
        kinds[r.kind].append(r.candidate_id)
    fields = {}

    def value(
        name: str,
        number: int | str,
        ids: list[str],
        unknown: bool = False,
        reason: str = "",
    ) -> None:
        fields[name] = AttributeValue(
            None if unknown else number,
            "unknown" if unknown else "confirmed",
            tuple(ids),
            source="review"
            if any(r.source == "vlm" and r.candidate_id in ids for r in active)
            else "cv",
            reason=reason if unknown else "",
        )

    # The row crop must include the actual search area; page whitespace alone
    # cannot prove that a neighboring cropped row contains no marks.
    up_cut = b.y - h * 1.8 < 0
    down_cut = b.bottom + h * 1.8 > registry.height
    horizontal_cut = b.x - h * 1.1 < 0 or b.right + h > registry.width
    up = kinds["octave_up"]
    down = kinds["octave_down"]

    def unclear(names: list[str]) -> bool:
        return any(
            set(c.kinds) & set(names) or "unclassified" in c.kinds for c in residual
        )

    value(
        "octave",
        len(up) - len(down),
        up + down,
        missing_evidence
        or (
            degree != "0"
            and (
                up_cut
                or down_cut
                or bool(up and down)
                or unclear(["octave_up", "octave_down"])
            )
        ),
        "八度搜索区被裁切或点归属不确定",
    )
    accidentals = [r for r in active if r.kind in ("sharp", "flat", "natural")]
    value(
        "accidental",
        accidentals[0].kind if len(accidentals) == 1 else "none",
        [r.candidate_id for r in accidentals],
        missing_evidence
        or horizontal_cut
        or len(accidentals) > 1
        or unclear(["sharp", "flat", "natural"]),
        "变音记号类别或归属未确认",
    )
    # Merge fragments at the same physical level, not just token counts.
    levels = []
    for cid in sorted(kinds["underline"], key=lambda cid: by_id[cid].bounds.cy):
        if not levels or by_id[cid].bounds.cy - levels[-1] > h * 0.12:
            levels.append(by_id[cid].bounds.cy)
    value(
        "underlines",
        len(levels),
        kinds["underline"],
        missing_evidence
        or b.bottom + h * 0.9 > registry.height
        or unclear(["underline"]),
        "减时线搜索区不完整或残留墨迹",
    )
    value(
        "dots",
        len(kinds["augmentation"]),
        kinds["augmentation"],
        missing_evidence or horizontal_cut or unclear(["augmentation"]),
        "附点归属未确认",
    )
    value(
        "extensions",
        len(kinds["extension"]),
        kinds["extension"],
        missing_evidence or unclear(["extension"]),
        "延长线归属未确认",
    )
    if degree == "0":
        if up or down or accidentals:
            fields["octave"] = AttributeValue(
                None, "unsupported", reason="休止符附近存在音高记号"
            )
        else:
            fields["octave"] = AttributeValue(0, "confirmed")
            fields["accidental"] = AttributeValue("none", "confirmed")
    if any(r.kind == "unsupported" for r in active):
        fields = {
            name: AttributeValue(None, "unsupported", reason="邻近不支持的音乐结构")
            for name in fields
        }
    return NoteAttributes(body_id, source_id, degree, fields)


def finalize_note_attributes(note: NoteAttributes) -> tuple[NoteAttributes, str | None]:
    from ..symbols.melody import derive_note_attributes, serialize_note

    derive_note_attributes(note)
    return note, serialize_note(note)
