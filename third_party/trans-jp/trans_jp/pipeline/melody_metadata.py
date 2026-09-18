from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from PIL import Image
from ..io.melody_artifacts import write_json
from ..io.classification_batches import sha256
from ..recognition.attachment_reviewer import parse_melody_metadata
from ..models.errors import EngineError


def recognize_metadata(
    work: Image.Image,
    client: Any,
    output: Path,
    *,
    enabled: bool,
    replay_root: Path | None,
) -> dict:
    directory = output / "melody-evidence"
    image_path = directory / "metadata-page.png"
    work.save(image_path)
    payload = {
        "region_ids": ["page"],
        "bounds_work": [0, 0, work.width, work.height],
        "image_sha256": sha256(image_path),
    }
    write_json(directory / "metadata-request.json", payload)
    content = ""
    status = "not_available"
    finish = None
    if replay_root:
        previous = replay_root / "melody-evidence"
        old = json.loads(
            (previous / "metadata-request.json").read_text(encoding="utf-8")
        )
        if old != payload:
            raise EngineError("metadata 回放图像不一致", 5)
        saved = json.loads(
            (previous / "metadata-result.json").read_text(encoding="utf-8")
        )
        content = saved["raw_response"]
        status = saved["status"]
        finish = saved.get("finish_reason")
    elif (
        enabled and client is not None and hasattr(client, "recognize_melody_metadata")
    ):
        try:
            response = client.recognize_melody_metadata(image_path, ("page",))
            content = response.content
            finish = response.finish_reason
            status = "reviewed" if finish in (None, "stop") else "invalid"
        except Exception as exc:
            status = "failed:" + type(exc).__name__
    result = parse_melody_metadata(content if status == "reviewed" else "", ("page",))
    result["source_regions"] = [
        {"region_id": "page", "bounds_work": payload["bounds_work"]}
    ]
    write_json(
        directory / "metadata-result.json",
        {
            "status": status,
            "raw_response": content,
            "finish_reason": finish,
            "parsed": result,
        },
    )
    return result
