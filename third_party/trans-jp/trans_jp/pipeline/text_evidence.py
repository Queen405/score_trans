from __future__ import annotations

import json
import logging
from pathlib import Path
import httpx
from PIL import Image
from ..models.contracts import CompletionResult
from ..models.lyrics import TextRequest
from ..models.errors import EngineError
from ..recognition.lyrics import TextRecognizer, parse_text_response
from ..io.lyrics_artifacts import save_text_request, write_json

logger = logging.getLogger("trans_jp.lyrics")


class TextEvidenceSession:
    """Frozen requests are verified; refinement can only append new request IDs."""

    def __init__(
        self,
        output: Path,
        client: TextRecognizer | None,
        version: int,
        replay_root: Path | None,
        refine: bool,
    ) -> None:
        self.output, self.client, self.version = output, client, version
        self.replay_root, self.refine = replay_root, refine

    def request(
        self, identity: str, image: Image.Image, items: tuple[dict, ...], task: str
    ) -> TextRequest:
        version = self.version
        if self.replay_root is not None:
            previous = self.replay_root / "lyrics-evidence" / f"{identity}-request.json"
            if previous.exists():
                version = json.loads(previous.read_text(encoding="utf-8"))["version"]
        return save_text_request(
            self.output, identity, image, items, task, version=version
        )

    def evaluate(self, request: TextRequest, *, once: bool = False) -> list[dict]:
        saved = None
        if self.replay_root is not None:
            directory = self.replay_root / "lyrics-evidence"
            previous = directory / f"{request.request_id}-request.json"
            if previous.exists():
                data = json.loads(previous.read_text(encoding="utf-8"))
                if data["sha256"] != request.sha256:
                    raise EngineError("文字请求几何或图像已改变", 5)
                saved = json.loads(
                    (directory / f"{request.request_id}-response.json").read_text(
                        encoding="utf-8"
                    )
                )
            elif not self.refine:
                raise EngineError(f"冻结文字请求缺失: {request.request_id}", 5)
        if saved is None:
            if self.client is None:
                raise EngineError("缺少文字服务；冻结回放不会自动联网", 5)
            try:
                if once:
                    response = self.client.recognize_text_once(request)
                else:
                    response = self.client.recognize_text(request)
                saved = {
                    "content": response.content,
                    "finish_reason": response.finish_reason,
                    "failure": None,
                }
            except Exception as exc:
                status_code = (
                    exc.response.status_code
                    if isinstance(exc, httpx.HTTPStatusError)
                    else None
                )
                saved = {
                    "content": "",
                    "finish_reason": None,
                    "failure": type(exc).__name__,
                }
                if self.version >= 4:
                    saved.update(
                        http_status=status_code,
                        request_status="auth_failed"
                        if status_code in (401, 403)
                        else "request_failed",
                    )
        write_json(
            self.output / "lyrics-evidence" / f"{request.request_id}-response.json",
            saved,
        )
        parsed = parse_text_response(
            CompletionResult(saved["content"], saved["finish_reason"]), request
        )
        if saved["failure"]:
            for item in parsed:
                item.update(
                    role="unknown", text=None, status="failed", reason=saved["failure"]
                )
                if self.version >= 4:
                    item["request_status"] = saved.get(
                        "request_status", "request_failed"
                    )
        if self.version >= 4:
            try:
                entries = json.loads(saved["content"]).get("items")
            except (ValueError, AttributeError):
                entries = None
            for item in parsed:
                item["request_id"] = request.request_id
                status = "complete"
                if item["status"] == "observed" and item["role"] == "unknown":
                    status = "model_unknown"
                elif item["reason"] == "truncated":
                    status = "truncated"
                elif entries == []:
                    status = "empty_response"
                elif item["reason"] == "missing_or_duplicate":
                    count = sum(
                        isinstance(e, dict) and e.get("id") == item["id"]
                        for e in entries or []
                    )
                    status = "missing_id" if count == 0 else "duplicate_id"
                elif item["status"] != "observed":
                    status = "invalid_response"
                item.setdefault("request_status", status)
        logger.info(
            "文字识别 %s: %s",
            request.request_id,
            "failed" if saved["failure"] else "completed",
        )
        return parsed
