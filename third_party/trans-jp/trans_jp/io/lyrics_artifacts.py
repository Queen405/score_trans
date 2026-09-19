from __future__ import annotations

import hashlib
import json
from pathlib import Path
from PIL import Image
from ..models.lyrics import (
    TextRequest,
    LYRICS_VERSION,
    SUPPORTED_LYRICS_VERSIONS,
    LyricsResult,
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, data: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )


def save_text_request(
    output: Path,
    identity: str,
    image: Image.Image,
    items: tuple[dict, ...],
    task: str,
    *,
    version: int = LYRICS_VERSION,
) -> TextRequest:
    directory = output / "lyrics-evidence"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{identity}.png"
    image.save(path)
    payload = {
        "version": version,
        "id": identity,
        "task": task,
        "items": items,
        "image_sha256": digest(path),
    }
    sha = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    write_json(directory / f"{identity}-request.json", {**payload, "sha256": sha})
    return TextRequest(identity, path, items, task, sha)


def write_lyrics_manifest(output: Path, binding: dict, result: dict) -> dict:
    write_json(output / "lyrics.json", result)
    files = [output / "lyrics.json", *sorted((output / "lyrics-evidence").glob("*"))]
    manifest = {
        "version": result["version"],
        "binding": binding,
        "files": {str(p.relative_to(output).as_posix()): digest(p) for p in files},
    }
    write_json(output / "lyrics-manifest.json", manifest)
    return {
        "version": result["version"],
        "manifest_sha256": digest(output / "lyrics-manifest.json"),
    }


def validate_lyrics_replay(
    root: Path, binding: dict, marker: dict | None = None
) -> dict:
    path = root / "lyrics-manifest.json"
    if marker is not None and (
        marker.get("version") not in SUPPORTED_LYRICS_VERSIONS
        or marker.get("manifest_sha256") != digest(path)
    ):
        raise ValueError("歌词manifest绑定错误")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") not in SUPPORTED_LYRICS_VERSIONS or data.get(
        "binding"
    ) != json.loads(json.dumps(binding)):
        raise ValueError("歌词源图/候选/变换版本不一致")
    if marker is not None and marker["version"] != data["version"]:
        raise ValueError("歌词标记与manifest版本不一致")
    expected = {
        "lyrics.json",
        *[
            str(p.relative_to(root).as_posix())
            for p in (root / "lyrics-evidence").glob("*")
            if p.is_file()
        ],
    }
    if set(data["files"]) != expected:
        raise ValueError("歌词证据集合不完整")
    for name, sha in data["files"].items():
        p = (root / name).resolve()
        if not p.is_relative_to(root.resolve()) or digest(p) != sha:
            raise ValueError("歌词证据路径或哈希错误")
    result = json.loads((root / "lyrics.json").read_text(encoding="utf-8"))
    if result.get("version") != data["version"]:
        raise ValueError("歌词结果版本与manifest不一致")
    return result


def lyrics_binding(manifest: dict) -> dict:
    return {
        "source_sha256": manifest["source_sha256"],
        "min_image_edge": manifest["min_image_edge"],
        "rows": manifest["rows"],
    }


def result_payload(result: LyricsResult) -> dict:
    from dataclasses import asdict

    data = asdict(result)
    if result.version == 3:
        for key in ("decisions", "pending", "refinement"):
            data.pop(key)
    return data
