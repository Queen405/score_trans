from __future__ import annotations

from dataclasses import asdict, is_dataclass
from fractions import Fraction
import hashlib
import json
from pathlib import Path
from typing import Any
from PIL import Image
from ..models.melody import (
    AttachmentCandidate,
    AttachmentReviewRequest,
    AttachmentReviewResult,
    MELODY_VERSION,
    ATTACHMENT_VERSION,
)
from .classification_batches import sha256


def serializable(value: Any) -> Any:
    if isinstance(value, Fraction):
        return {"numerator": value.numerator, "denominator": value.denominator}
    if is_dataclass(value):
        return serializable(asdict(value))
    if isinstance(value, dict):
        return {k: serializable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serializable(v) for v in value]
    return value


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            serializable(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    ).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(serializable(value), ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )


def save_review(
    directory: Path, request: AttachmentReviewRequest, result: AttachmentReviewResult
) -> None:
    write_json(directory / f"{request.request_id}-result.json", result)
    (directory / f"{request.request_id}-raw.txt").write_text(
        result.raw_response, encoding="utf-8"
    )


def make_review(
    directory: Path,
    request_id: str,
    image: Image.Image,
    body_ids: tuple[str, ...],
    candidates: tuple[AttachmentCandidate, ...],
) -> AttachmentReviewRequest:
    directory.mkdir(parents=True, exist_ok=True)
    image_path = directory / f"{request_id}.png"
    image.save(image_path)
    payload = {
        "version": MELODY_VERSION,
        "attachment_version": ATTACHMENT_VERSION,
        "body_ids": body_ids,
        "candidates": candidates,
        "image_sha256": sha256(image_path),
    }
    digest = canonical_digest(payload)
    write_json(
        directory / f"{request_id}-request.json", {"payload": payload, "sha256": digest}
    )
    return AttachmentReviewRequest(request_id, image_path, body_ids, candidates, digest)


def finish_manifest(output: Path, body_manifest: dict, files: list[Path]) -> None:
    write_json(
        output / "melody-manifest.json",
        {
            "version": MELODY_VERSION,
            "attachment_version": ATTACHMENT_VERSION,
            "body_manifest_sha256": canonical_digest(body_manifest),
            "files": {p.relative_to(output).as_posix(): sha256(p) for p in files},
        },
    )


def validate_melody_replay(root: Path) -> dict:
    manifest = json.loads((root / "melody-manifest.json").read_text(encoding="utf-8"))
    if (
        manifest["version"] != MELODY_VERSION
        or manifest["attachment_version"] != ATTACHMENT_VERSION
    ):
        raise ValueError("melody 回放版本不一致")
    if (
        canonical_digest(
            json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        )
        != manifest["body_manifest_sha256"]
    ):
        raise ValueError("melody 主体 manifest 已改变")
    if not manifest.get("files") or "melody.json" not in manifest["files"]:
        raise ValueError("melody 文件集合不完整")
    metadata_files = {
        "melody-evidence/metadata-page.png",
        "melody-evidence/metadata-request.json",
        "melody-evidence/metadata-result.json",
    }
    if not metadata_files <= set(manifest["files"]):
        raise ValueError("melody 元数据证据不完整")
    for name in manifest["files"]:
        if name.startswith("melody-evidence/local-metadata-") and name.endswith(
            "-request.json"
        ):
            stem = name.removesuffix("-request.json")
            if not {stem + ".png", stem + "-result.json"} <= set(manifest["files"]):
                raise ValueError("局部元数据证据不完整")
        if (
            name.startswith("melody-evidence/")
            and name.endswith("-request.json")
            and "-review" in name
        ):
            stem = name.removesuffix("-request.json")
            if not {stem + ".png", stem + "-result.json", stem + "-raw.txt"} <= set(
                manifest["files"]
            ):
                raise ValueError("melody 局部复核证据不完整")
    for name, digest in manifest["files"].items():
        path = (root / name).resolve()
        if root.resolve() not in path.parents or sha256(path) != digest:
            raise ValueError("melody 文件哈希或路径不一致")
    return manifest


def read_melody_review_flag(root: Path) -> bool:
    return (
        json.loads((root / "melody.json").read_text(encoding="utf-8"))["review_enabled"]
        is True
    )
