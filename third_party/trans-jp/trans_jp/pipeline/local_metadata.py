from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import numpy as np
from PIL import Image
from ..models.contracts import RowResult
from ..models.errors import EngineError
from ..preprocess.image import otsu_binarize
from ..structure.metadata_regions import detect_metadata_regions
from ..rendering.metadata_atlas import render_metadata_atlas
from ..recognition.attachment_reviewer import parse_local_metadata
from ..io.melody_artifacts import write_json, canonical_digest
from ..io.classification_batches import sha256


def recognize_local_declarations(
    work: Image.Image,
    rows: list[RowResult],
    client: Any,
    output: Path,
    *,
    enabled: bool,
    replay_root: Path | None,
) -> dict:
    """Crop evidence and provisional reading order, without guessing activation."""
    directory = output / "melody-evidence"
    if (
        replay_root
        and not (replay_root / "melody-evidence/local-metadata.json").exists()
    ):
        return {
            "status": "legacy_not_available",
            "declarations": [],
            "source_regions": [],
        }
    if not replay_root and (
        not enabled or client is None or not hasattr(client, "recognize_local_metadata")
    ):
        return {"status": "not_available", "declarations": [], "source_regions": []}
    boxes = detect_metadata_regions(otsu_binarize(np.asarray(work.convert("L"))))
    regions = tuple((f"meta{i:04}", box) for i, box in enumerate(boxes))
    evidence = []
    declarations = []
    batches = []
    transform = rows[0].row.transform if rows else None
    for rid, b in regions:
        evidence.append(
            {
                "region_id": rid,
                "bounds_work": b,
                "bounds_source": transform.box(b) if transform else None,
            }
        )
    for start in range(0, len(regions), 6):
        chunk = regions[start : start + 6]
        ids = tuple(rid for rid, _ in chunk)
        stem = f"local-metadata-{start // 6:04}"
        image_path = directory / f"{stem}.png"
        render_metadata_atlas(work, chunk).save(image_path)
        payload = {"regions": chunk, "image_sha256": sha256(image_path)}
        digest = canonical_digest(payload)
        write_json(
            directory / f"{stem}-request.json", {"sha256": digest, "payload": payload}
        )
        raw = ""
        status = "not_available"
        finish = None
        if replay_root:
            previous = replay_root / "melody-evidence"
            old = json.loads(
                (previous / f"{stem}-request.json").read_text(encoding="utf-8")
            )
            if old["sha256"] != digest:
                raise EngineError("局部 metadata 裁剪图或编号不一致", 5)
            result = json.loads(
                (previous / f"{stem}-result.json").read_text(encoding="utf-8")
            )
            raw = result["raw_response"]
            status = result["status"]
            finish = result.get("finish_reason")
        else:
            try:
                response = client.recognize_local_metadata(image_path, ids)
                raw = response.content
                finish = response.finish_reason
                status = "reviewed" if finish in (None, "stop") else "invalid"
            except Exception as exc:
                status = "failed:" + type(exc).__name__
        parsed = parse_local_metadata(raw, ids) if status == "reviewed" else []
        write_json(
            directory / f"{stem}-result.json",
            {
                "raw_response": raw,
                "status": status,
                "finish_reason": finish,
                "parsed": parsed,
            },
        )
        batches.append({"id": stem, "status": status})
        declarations.extend(parsed)
    lookup = dict(regions)
    bodies = [
        (r.row.index, c.candidate_id, c.bounds, r.row.work_y_top)
        for r in rows
        if r.registry
        for c in r.registry.candidates
        if c.candidate_id
        in {
            cid
            for t in r.tokens
            if t.role in ("note", "rest")
            for cid in t.candidate_ids
        }
    ]
    for declaration in declarations:
        b = lookup[declaration["region_id"]]
        later = [
            (ri, cid, box, top)
            for ri, cid, box, top in bodies
            if box.y + top > b.bottom or (box.bottom + top > b.y and box.x > b.right)
        ]
        later.sort(key=lambda item: (item[0], item[2].cx))
        declaration["possible_following_body"] = later[0][1] if later else None
        declaration["activation_status"] = "unknown"
        declaration["reason"] = "局部可见文字候选；声明边界和跨行生效位置未独立验证"
    result = {
        "status": "observed_local" if declarations else "unknown",
        "declarations": declarations,
        "source_regions": evidence,
        "batches": batches,
    }
    write_json(directory / "local-metadata.json", result)
    return result
