from __future__ import annotations

import base64
import io
import logging
import time
from pathlib import Path
from typing import Any
from collections.abc import Callable
from ..models.candidates import RowRecognitionRequest
from ..models.melody import AttachmentReviewRequest
from ..models.classification import CandidateBatchRequest
from .candidate_classifier import CLASSIFICATION_SYSTEM, classification_prompt

import httpx

from ..models.contracts import LlmConfig, CompletionResult

logger = logging.getLogger("trans_jp.llm")

_MAX_IMAGE_EDGE = 2000
_COMPACT_SUFFIX = "\n\n请精简输出：只保留 JSON 本体，不要输出任何解释文字。"
_RETRY_WAIT_SECONDS = 2.0


class LlmClient:
    def __init__(self, config: LlmConfig, system_message: str):
        self._config = config
        self._system_message = system_message

    def transcribe_row(self, image_path: Path, prompt: str) -> CompletionResult:
        return self._post([image_to_data_url(image_path)], prompt)

    def _post(
        self, image_urls: list[str], prompt: str, *, system_message: str | None = None
    ) -> CompletionResult:
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": system_message
                if system_message is not None
                else self._system_message,
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    *[
                        {"type": "image_url", "image_url": {"url": url}}
                        for url in image_urls
                    ],
                ],
            },
        ]
        body: dict[str, Any] = {
            "model": self._config.model,
            "messages": messages,
            "temperature": self._config.temperature,
            "max_tokens": self._config.max_tokens,
            "response_format": {"type": "json_object"},
        }
        resp = httpx.post(
            f"{self._config.base_url}/chat/completions",
            json=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._config.api_key}",
            },
            timeout=httpx.Timeout(
                connect=30,
                read=self._config.timeout,
                write=self._config.timeout,
                pool=30,
            ),
        )
        resp.raise_for_status()
        data = resp.json()
        return CompletionResult(
            content=_completion_content(data),
            finish_reason=_completion_finish_reason(data),
        )

    def recognize_local_metadata(
        self, image_path: Path, region_ids: tuple[str, ...]
    ) -> CompletionResult:
        import json

        prompt = (
            "逐个读取编号局部框中实际印刷的简谱调号/拍号，不推测，不读音符为拍号。"
            "返回 schema_version=1, declarations:[{region_id, key_text:可见原文如1=#C或null, meter_text:可见4/4等或null}]。"
            "如果是减时线/歌词/水印而非声明，两个字段均null。不得凭记忆补调号，必须分清F和C。编号："
            + json.dumps(region_ids)
        )
        return self._review_retry(
            lambda text: self._post(
                [image_to_data_url(image_path, max_edge=None)],
                text,
                system_message="Read only visible local key/meter declarations; JSON only.",
            ),
            prompt,
        )

    def recognize_melody_metadata(
        self, image_path: Path, region_ids: tuple[str, ...]
    ) -> CompletionResult:
        import json

        prompt = (
            "仅识别图片中明确印刷的简谱调号和拍号；禁止根据旋律猜测，缺失返回unknown。"
            "图片依次为编号区域。返回JSON: {schema_version:1,key:{value:音名如Bb,status:confirmed或unknown,region_id:区域编号},"
            "meter:{value:如4/4,status:confirmed或unknown,region_id:区域编号},changes_detected:页面是否有中途调号或拍号变化}。"
            "即使标题未知也不得补C调或4/4，不识别目标移调调号。区域："
            + json.dumps(region_ids)
        )
        return self._review_retry(
            lambda text: self._post(
                [image_to_data_url(image_path)],
                text,
                system_message="Extract only visible Jianpu key and meter metadata. Return JSON.",
            ),
            prompt,
        )

    def review_attachments(self, request: AttachmentReviewRequest) -> CompletionResult:
        from .attachment_reviewer import REVIEW_SYSTEM, review_prompt

        urls = [image_to_data_url(request.image_path, max_edge=None)]
        return self._review_retry(
            lambda prompt: self._post(urls, prompt, system_message=REVIEW_SYSTEM),
            review_prompt(request),
        )

    def _review_retry(
        self, send: Callable[[str], CompletionResult], prompt: str
    ) -> CompletionResult:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                result = send(prompt)
                if result.finish_reason != "length" or attempt == 2:
                    return result
                prompt += _COMPACT_SUFFIX
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                last_error = exc
                if (
                    isinstance(exc, httpx.HTTPStatusError)
                    and exc.response.status_code not in (408, 429)
                    and exc.response.status_code < 500
                ):
                    raise
            if attempt < 2:
                time.sleep(_RETRY_WAIT_SECONDS * (attempt + 1))
        raise RuntimeError("局部复核请求失败") from last_error

    def classify(self, request: CandidateBatchRequest) -> CompletionResult:
        urls = [
            image_to_data_url(request.image_path),
            image_to_data_url(request.atlas_path, max_edge=None),
        ]
        prompt = classification_prompt(request)
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                result = self._post(urls, prompt, system_message=CLASSIFICATION_SYSTEM)
                if result.finish_reason == "length":
                    prompt = classification_prompt(request) + _COMPACT_SUFFIX
                    if attempt == 2:
                        return result
                else:
                    return result
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                last_error = exc
                # Authentication and malformed request errors cannot be repaired by retry.
                if (
                    isinstance(exc, httpx.HTTPStatusError)
                    and exc.response.status_code not in (408, 429)
                    and exc.response.status_code < 500
                ):
                    raise
            if attempt < 2:
                time.sleep(_RETRY_WAIT_SECONDS * (attempt + 1))
        raise RuntimeError("候选批次请求失败") from last_error

    def transcribe_row_with_retry(
        self, image_path: Path, prompt: str, *, max_retries: int = 1
    ) -> CompletionResult:
        return self._retry(
            lambda text: self.transcribe_row(image_path, text), prompt, max_retries
        )

    def transcribe_request_with_retry(
        self, request: RowRecognitionRequest, prompt: str, *, max_retries: int = 1
    ) -> CompletionResult:
        urls = [
            image_to_data_url(request.image_path),
            *[image_to_data_url(path, max_edge=None) for path in request.atlas_paths],
        ]
        return self._retry(lambda text: self._post(urls, text), prompt, max_retries)

    def _retry(
        self, send: Callable[[str], CompletionResult], prompt: str, max_retries: int
    ) -> CompletionResult:
        result: CompletionResult | None = None
        last_error: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                result = send(prompt)
                break
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                last_error = exc
                if attempt < max_retries:
                    logger.warning(
                        "LLM 请求失败（第 %d 次），等待后重试: %s", attempt + 1, exc
                    )
                    time.sleep(_RETRY_WAIT_SECONDS)
        if result is None:
            raise RuntimeError(f"LLM 请求失败: {last_error}") from last_error

        if result.finish_reason != "length":
            return result

        logger.warning("LLM 输出因 max_tokens 截断，使用紧凑提示重试")
        retry_result = send(prompt + _COMPACT_SUFFIX)
        if retry_result.finish_reason == "length":
            raise RuntimeError(
                f"LLM 输出达到 max_tokens 上限（{self._config.max_tokens}）被截断，"
                "紧凑提示重试仍未完成。请调大 --max-tokens。"
            )
        return retry_result


def image_to_data_url(path: Path, *, max_edge: int | None = _MAX_IMAGE_EDGE) -> str:
    from PIL import Image

    with Image.open(path) as source:
        img = source.convert("RGB")
    if max_edge and max(img.size) > max_edge:
        ratio = max_edge / max(img.size)
        img = img.resize(
            (max(1, round(img.width * ratio)), max(1, round(img.height * ratio))),
            Image.Resampling.LANCZOS,
        )
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def _completion_content(data: dict[str, Any]) -> str:
    choices = data.get("choices")
    if not choices:
        raise ValueError("LLM 响应缺少 choices")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part.get("text", "") for part in content if isinstance(part, dict)
        )
    raise ValueError("LLM 响应缺少 content")


def _completion_finish_reason(data: dict[str, Any]) -> str | None:
    choices = data.get("choices")
    if not choices:
        return None
    reason = choices[0].get("finish_reason")
    return str(reason) if reason else None
