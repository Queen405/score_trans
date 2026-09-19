from __future__ import annotations

import json
from pathlib import Path
from ..models.contracts import CompletionResult
from ..models.candidates import (
    CandidateRegistry,
    RowRecognitionRequest,
    CANDIDATE_VERSION,
)
from ..models.errors import EngineError
from .candidate_requests import read_registry
from .classification_batches import validate_batch_files, sha256
from ..models.classification import CandidateBatchRequest, CLASSIFIER_VERSION


class ReplayClient:
    """Replay frozen identities; validate the complete run before any recognition."""

    def __init__(self, directory: Path):
        self.directory = directory
        self.versions: dict[int, int] = {}
        self.batch_results: dict[str, dict] = {}
        self.lyrics_marker: dict | None = None
        self.saved_batch_groups: list[dict] = []
        self.lyrics_excluded: set[str] = set()

    def validate_run(
        self, manifest: dict, registries: list[CandidateRegistry]
    ) -> list[CandidateRegistry]:
        try:
            self.versions.clear()
            self.batch_results.clear()
            root = self.directory.parent
            manifest_path = root / "manifest.json"
            saved = (
                json.loads(manifest_path.read_text(encoding="utf-8"))
                if manifest_path.exists()
                else {}
            )
            for registry in registries:
                path = self.directory / f"row_{registry.row_index}.json"
                data = (
                    json.loads(path.read_text(encoding="utf-8"))
                    if path.exists()
                    else {}
                )
                self.versions[registry.row_index] = data.get("schema_version", 1)
            if saved.get("version") == 3 and set(self.versions.values()) != {3}:
                raise ValueError("v3 行响应缺失或被降级")
            if (
                not any(v in (2, 3) for v in self.versions.values())
                and saved.get("version") != 3
            ):
                return registries
            if saved.get("version") not in (2, 3) or any(
                saved.get(k) != manifest.get(k)
                for k in ("source_sha256", "min_image_edge")
            ):
                raise ValueError("源图、预处理参数或 manifest 版本不一致")
            if len(saved["rows"]) != len(manifest["rows"]):
                raise ValueError("回放谱行数量不一致")
            restored = []
            for current, previous, computed in zip(
                manifest["rows"], saved["rows"], registries, strict=True
            ):
                if any(
                    current[k] != previous[k]
                    for k in ("row_index", "image_sha256", "work_y_top", "transform")
                ):
                    raise ValueError("回放裁剪图或坐标变换不一致")
                registry = read_registry(
                    root / "requests" / f"row_{computed.row_index}-candidates.json"
                )
                if (
                    registry.digest != previous["registry_sha256"]
                    or registry.algorithm_version != CANDIDATE_VERSION
                ):
                    raise ValueError("候选注册表哈希或算法版本不一致")
                if (registry.row_index, registry.width, registry.height) != (
                    computed.row_index,
                    computed.width,
                    computed.height,
                ):
                    raise ValueError("候选注册表行尺寸不一致")
                restored.append(registry)
            if 3 in self.versions.values():
                if (
                    saved.get("version") != 3
                    or saved.get("classifier_version") != CLASSIFIER_VERSION
                    or set(self.versions.values()) != {3}
                ):
                    raise ValueError("v3 分类版本或行协议不一致")
                expected_names = {
                    f"row_{registry.row_index}.json" for registry in restored
                }
                if set(saved.get("row_responses", {})) != expected_names:
                    raise ValueError("v3 行响应集合不完整")
                for name, digest in saved["row_responses"].items():
                    if sha256(self.directory / name) != digest:
                        raise ValueError("v3 行响应哈希不一致")
                self.lyrics_marker = saved.get("lyrics")
                self.lyrics_excluded = set(saved.get("lyrics_excluded_candidates", []))
                if self.lyrics_marker:
                    from .lyrics_artifacts import validate_lyrics_replay, lyrics_binding

                    lyrics = validate_lyrics_replay(
                        root, lyrics_binding(saved), self.lyrics_marker
                    )
                    if not self.lyrics_excluded <= {
                        c["candidate_id"] for c in lyrics["conflicts"]
                    }:
                        raise ValueError("歌词排除集合与证据不一致")
                elif self.lyrics_excluded or (root / "lyrics-manifest.json").exists():
                    raise ValueError("歌词回放缺少manifest绑定")
                self.saved_batch_groups = saved["batches"]
                self.batch_results = validate_batch_files(
                    root,
                    saved["batches"],
                    {r.row_index: r for r in restored},
                    self.lyrics_excluded,
                )
            return restored
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise EngineError(f"v2/v3 回放校验失败: {exc}", 5) from exc

    def groups_for_row(self, row_index: int) -> list[tuple[int, tuple[str, ...]]]:
        return sorted(
            (int(b["batch_id"].split(":b")[1]), tuple(b["candidate_ids"]))
            for b in self.saved_batch_groups
            if b["row_index"] == row_index
        )

    def classify(self, request: CandidateBatchRequest) -> CompletionResult:
        data = self.batch_results[request.batch_id]
        if (
            tuple(i["candidate_id"] for i in data["items"]) != request.candidate_ids
            or data["registry_sha256"] != request.registry.digest
        ):
            raise ValueError("回放批次与请求不一致")
        if data["status"] == "batch_request_failed":
            raise RuntimeError("已记录的批次请求失败")
        return CompletionResult(
            data["raw_response"],
            data.get("finish_reason")
            or (
                "length"
                if data["status"] == "batch_response_invalid"
                and any("未完成" in w for w in data["warnings"])
                else "stop"
            ),
        )

    def transcribe_request_with_retry(
        self, request: RowRecognitionRequest, prompt: str, *, max_retries: int = 1
    ) -> CompletionResult:
        return self.transcribe_row_with_retry(
            request.image_path, prompt, max_retries=max_retries
        )

    def transcribe_row_with_retry(
        self, image_path: Path, prompt: str, *, max_retries: int = 1
    ) -> CompletionResult:
        data = json.loads(
            (self.directory / f"{image_path.stem}.json").read_text(encoding="utf-8")
        )
        if "jianpu_text" in data:
            data["row_text"] = data.pop("jianpu_text")
        return CompletionResult(json.dumps(data, ensure_ascii=False), "stop")
