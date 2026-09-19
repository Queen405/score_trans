from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from PIL import Image
from ..models.candidates import CandidateRegistry
from ..models.classification import CandidateBatchRequest, CandidateBatchResult
from ..models.contracts import RowSegment


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_batch_request(
    row: RowSegment,
    registry: CandidateRegistry,
    index: int,
    candidate_ids: tuple[str, ...],
    atlas: Image.Image,
) -> CandidateBatchRequest:
    directory = row.image_path.parent.parent / "batches"
    directory.mkdir(parents=True, exist_ok=True)
    batch_id = f"r{row.index:04d}:b{index:04d}"
    stem = batch_id.replace(":", "-")
    atlas_path = directory / f"{stem}-atlas.png"
    atlas.save(atlas_path)
    request = CandidateBatchRequest(
        batch_id, row.image_path, atlas_path, registry, candidate_ids
    )
    payload = {
        "schema_version": 3,
        "batch_id": batch_id,
        "registry_sha256": registry.digest,
        "candidate_ids": candidate_ids,
        "row_image_sha256": sha256(row.image_path),
        "atlas_sha256": sha256(atlas_path),
    }
    (directory / f"{stem}-request.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return request


def write_batch_result(
    request: CandidateBatchRequest, result: CandidateBatchResult
) -> dict:
    directory = request.atlas_path.parent
    stem = request.batch_id.replace(":", "-")
    raw = directory / f"{stem}-raw.txt"
    normalized = directory / f"{stem}-result.json"
    raw.write_text(result.raw_response, encoding="utf-8")
    normalized.write_text(
        json.dumps(asdict(result), ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    return {
        "batch_id": request.batch_id,
        "row_index": request.registry.row_index,
        "candidate_ids": request.candidate_ids,
        "files": {
            p.name: sha256(p)
            for p in [
                request.atlas_path,
                directory / f"{stem}-request.json",
                raw,
                normalized,
            ]
        },
    }


def validate_batch_files(
    root: Path,
    entries: list[dict],
    registries: dict[int, CandidateRegistry],
    excluded: set[str] | None = None,
) -> dict[str, dict]:
    results = {}
    used = set()
    for entry in entries:
        batch_id = entry["batch_id"]
        row_index = entry["row_index"]
        registry = registries[row_index]
        prefix = f"r{row_index:04d}:b"
        if (
            not isinstance(batch_id, str)
            or not batch_id.startswith(prefix)
            or len(batch_id) != len(prefix) + 4
            or not batch_id[len(prefix) :].isdigit()
            or batch_id in results
        ):
            raise ValueError("批次编号错误或重复")
        stem = batch_id.replace(":", "-")
        names = {
            f"{stem}-atlas.png",
            f"{stem}-request.json",
            f"{stem}-raw.txt",
            f"{stem}-result.json",
        }
        if set(entry["files"]) != names:
            raise ValueError("批次文件集合不一致")
        for filename, digest in entry["files"].items():
            if sha256(root / "batches" / filename) != digest:
                raise ValueError("批次文件哈希不一致")
        request = json.loads(
            (root / "batches" / f"{stem}-request.json").read_text(encoding="utf-8")
        )
        result = json.loads(
            (root / "batches" / f"{stem}-result.json").read_text(encoding="utf-8")
        )
        ids = entry["candidate_ids"]
        valid = {
            c.candidate_id
            for c in registry.candidates
            if c.kind in ("digit", "barline") and not c.ambiguous
        }
        if (
            not 1 <= len(ids) <= 12
            or len(set(ids)) != len(ids)
            or set(ids) - valid
            or set(ids) & used
        ):
            raise ValueError("批次候选非法或重复")
        used.update(ids)
        if (
            request["candidate_ids"] != ids
            or request["batch_id"] != batch_id
            or result["batch_id"] != batch_id
            or request["registry_sha256"] != registry.digest
            or result["registry_sha256"] != registry.digest
        ):
            raise ValueError("批次绑定不一致")
        if request["atlas_sha256"] != entry["files"][f"{stem}-atlas.png"] or request[
            "row_image_sha256"
        ] != sha256(root / "rows" / f"row_{row_index}.png"):
            raise ValueError("批次图像不一致")
        if result["raw_response"] != (root / "batches" / f"{stem}-raw.txt").read_text(
            encoding="utf-8"
        ):
            raise ValueError("原始响应与批次结果不一致")
        if [i["candidate_id"] for i in result["items"]] != ids:
            raise ValueError("规范化分类列表与批次不一致")
        results[batch_id] = result
    expected = {
        c.candidate_id
        for registry in registries.values()
        for c in registry.candidates
        if c.kind in ("digit", "barline") and not c.ambiguous
    }
    expected -= excluded or set()
    if used != expected:
        raise ValueError("批次没有覆盖全部可识别候选")
    return results
