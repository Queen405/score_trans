from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from PIL import Image
from ..models.candidates import (
    CandidateRegistry,
    LocatedCandidate,
    RowRecognitionRequest,
)
from ..models.contracts import CliConfig, RowSegment
from ..models.geometry import Box
from ..models.raster import Filament


def image_hash(image: Image.Image) -> str:
    return hashlib.sha256(
        str(image.size).encode() + image.convert("RGB").tobytes()
    ).hexdigest()


def build_manifest(
    config: CliConfig,
    rows: list[RowSegment],
    crops: list[Image.Image],
    registries: list[CandidateRegistry],
) -> dict:
    return {
        "version": 2,
        "source_sha256": hashlib.sha256(config.input_path.read_bytes()).hexdigest(),
        "min_image_edge": config.min_image_edge,
        "model": config.llm.model,
        "request_parameters": {
            "temperature": config.llm.temperature,
            "max_tokens": config.llm.max_tokens,
            "target_key": config.target_key,
        },
        "rows": [
            {
                "row_index": r.index,
                "image_sha256": image_hash(crop),
                "work_y_top": r.work_y_top,
                "transform": asdict(r.transform),
                "registry_sha256": registry.digest,
            }
            for r, crop, registry in zip(rows, crops, registries, strict=True)
        ],
    }


def save_request(
    row: RowSegment,
    registry: CandidateRegistry,
    atlases: list[Image.Image],
    *,
    expected_schema: int,
) -> RowRecognitionRequest:
    directory = row.image_path.parent.parent / "requests"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"row_{row.index}-candidates.json").write_text(
        json.dumps(asdict(registry), ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    paths = []
    for index, image in enumerate(atlases):
        path = directory / f"row_{row.index}-atlas_{index}.png"
        image.save(path)
        paths.append(path)
    return RowRecognitionRequest(
        row.image_path, tuple(paths), registry, expected_schema
    )


def read_registry(path: Path) -> CandidateRegistry:
    data = json.loads(path.read_text(encoding="utf-8"))
    candidates = []
    for c in data["candidates"]:
        lines = tuple(
            Filament(
                line["orientation"],
                tuple(tuple(p) for p in line["points"]),
                line["thickness"],
                line["support"],
                Box(**line["bounds"]),
            )
            for line in c["lines"]
        )
        candidates.append(
            LocatedCandidate(
                c["candidate_id"],
                c["kind"],
                Box(**c["bounds"]),
                tuple(c["band_ids"]),
                tuple(c["component_ids"]),
                tuple(c["conflicts"]),
                c["ambiguous"],
                lines,
            )
        )
    return CandidateRegistry(
        data["row_index"],
        data["width"],
        data["height"],
        tuple(candidates),
        data["algorithm_version"],
    )


def write_manifest(directory: Path, manifest: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
