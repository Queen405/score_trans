from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import json
import logging
from pathlib import Path
import numpy as np
from PIL import Image
from ..models.contracts import CompletionResult
from ..models.errors import EngineError
from ..models.geometry import Transform
from ..models.lyrics import LyricsResult, LyricLine, LyricToken, TextRequest
from ..structure.lyric_regions import (
    find_text_regions,
    word_boxes,
    language,
    text_units,
)
from ..recognition.lyrics import TextRecognizer, parse_text_response
from ..rendering.lyrics import text_atlas
from ..io.lyrics_artifacts import save_text_request, write_json, validate_lyrics_replay
from ..matching.text_conflicts import (
    body_text_conflicts,
    attach_note_candidates,
    unique_word_alignment,
)

logger = logging.getLogger("trans_jp.lyrics")


def recognize_lyrics(
    work: Image.Image,
    binary: np.ndarray,
    transform: Transform,
    rows: list,
    registries: list,
    output: Path,
    client: TextRecognizer | None,
    binding: dict,
    *,
    concurrency: int = 2,
    replay_root: Path | None = None,
    replay_marker: dict | None = None,
) -> tuple[LyricsResult, dict[str, str]]:
    if replay_root is not None:
        try:
            validate_lyrics_replay(replay_root, binding, replay_marker)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise EngineError(f"歌词回放校验失败: {exc}", 5) from exc
    elif client is None:
        raise EngineError("歌词识别需要文字服务配置或 --lyrics-responses-dir", 5)
    regions = find_text_regions(binary, transform)
    write_json(output / "lyrics-evidence/regions.json", [asdict(r) for r in regions])

    def evaluate(request: TextRequest) -> list[dict]:
        saved = None
        if replay_root is not None:
            directory = replay_root / "lyrics-evidence"
            try:
                previous = json.loads(
                    (directory / f"{request.request_id}-request.json").read_text(
                        encoding="utf-8"
                    )
                )
                if previous["sha256"] != request.sha256:
                    raise ValueError("文字请求几何或图像已改变")
                saved = json.loads(
                    (directory / f"{request.request_id}-response.json").read_text(
                        encoding="utf-8"
                    )
                )
            except (OSError, ValueError, KeyError) as exc:
                raise EngineError(f"歌词回放请求校验失败: {exc}", 5) from exc
        else:
            try:
                response = client.recognize_text(request)
                saved = {
                    "content": response.content,
                    "finish_reason": response.finish_reason,
                    "failure": None,
                }
            except Exception as exc:
                saved = {
                    "content": "",
                    "finish_reason": None,
                    "failure": type(exc).__name__,
                }
        write_json(
            output / "lyrics-evidence" / f"{request.request_id}-response.json", saved
        )
        parsed = parse_text_response(
            CompletionResult(saved["content"], saved["finish_reason"]), request
        )
        if saved["failure"]:
            for item in parsed:
                item.update(
                    role="unknown", text=None, status="failed", reason=saved["failure"]
                )
        logger.info(
            "文字识别 %s: %s",
            request.request_id,
            "failed" if saved["failure"] else "completed",
        )
        return parsed

    requests = []
    for i in range(0, len(regions), 6):
        batch = regions[i : i + 6]
        entries = [(r.region_id, r.bounds_work) for r in batch]
        items = tuple(
            {"id": r.region_id, "bounds_work": asdict(r.bounds_work)} for r in batch
        )
        requests.append(
            save_text_request(
                output,
                f"regions-{i // 6:04d}",
                text_atlas(work, entries, context=False),
                items,
                "regions",
            )
        )
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        decisions = {
            v["id"]: v
            for response in executor.map(evaluate, requests)
            for v in response
        }
    result = LyricsResult()
    lines = {}
    token_boxes = {}
    word_requests = []
    for r in regions:
        d = decisions[r.region_id]
        result.regions.append(
            {**d, "bounds": asdict(r.bounds), "bounds_work": asdict(r.bounds_work)}
        )
        if d["status"] in ("failed", "unresolved"):
            result.warnings.append(f"{r.region_id}: {d['reason']}")
        if d["role"] != "lyrics" or not d["text"]:
            continue
        text = d["text"].strip()
        line = LyricLine(r.region_id, text, r.bounds, r.bounds_work, language(text))
        result.lines.append(line)
        lines[r.region_id] = line
        boxes = word_boxes(binary, r, text)
        token_boxes[r.region_id] = boxes
        # Fragmented radicals or ambiguous spacing remain at line precision.
        if len(boxes) != len(text_units(text)):
            result.warnings.append(f"{r.region_id}: 字框与行文字不能可靠对齐")
        for start in range(0, len(boxes), 12):
            entries = [
                (f"{r.region_id}:w{j:03d}", b)
                for j, b in enumerate(boxes)
                if start <= j < start + 12
            ]
            items = tuple(
                {"id": identity, "bounds_work": asdict(b)} for identity, b in entries
            )
            word_requests.append(
                save_text_request(
                    output,
                    f"words-{r.region_id.replace(':', '-')}-{start:03d}",
                    text_atlas(work, entries, context=False),
                    items,
                    "words",
                )
            )
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        words = {
            v["id"]: v
            for response in executor.map(evaluate, word_requests)
            for v in response
        }
    for identity, line in lines.items():
        boxes = token_boxes[identity]
        units = text_units(line.text)
        observed = [
            words.get(f"{identity}:w{i:03d}", {}).get("text") for i in range(len(boxes))
        ]
        alignment = unique_word_alignment(observed, units)
        for i, j in alignment.items():
            b = boxes[i]
            text = units[j]
            tid = f"{identity}:w{i:03d}"
            line.tokens.append(
                LyricToken(
                    tid,
                    text,
                    transform.box(b),
                    b,
                    "character" if language(text) == "zh" else "word",
                    localization_status="verified_crop",
                )
            )
        if len(line.tokens) == len(units):
            line.localization_status = "verified_crops"
        elif line.tokens:
            line.localization_status = "partial"
    blocked = body_text_conflicts(rows, registries, result)
    attach_note_candidates(result, rows, registries, blocked)
    result.warnings.append(
        "歌词为模型观测；字词仅在独立裁剪与整行转写一致时定位，音符对齐未确认"
    )
    return result, blocked
