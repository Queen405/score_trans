from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from score_trans.config.settings import OCR_MAX_TOKENS, OCR_TEMPERATURE

from ...models.common.errors import OCRError
from ...utils.media import image_to_data_url
from .protocols import OCRRequest
from .utils import is_deepseek_ocr_model


def build_request(
    image_path: str | Path,
    *,
    model: str,
    api_key: str | None,
    base_url: str,
    dry_run: bool = False,
) -> OCRRequest:
    path = Path(image_path)
    if not path.is_file():
        raise FileNotFoundError(path)

    if not api_key and not dry_run:
        raise OCRError("OCR API key not configured. Set it in Settings.")

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": ocr_prompt_for_model(model),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": image_to_data_url(path)},
                    },
                ],
            }
        ],
        "temperature": OCR_TEMPERATURE,
        "max_tokens": OCR_MAX_TOKENS,
    }
    if not is_deepseek_ocr_model(model):
        payload["response_format"] = {"type": "json_object"}

    return OCRRequest(
        endpoint=f"{base_url}/chat/completions",
        headers=headers,
        payload=payload,
    )


def send_request(request: OCRRequest, timeout: float) -> dict[str, Any]:
    data = json.dumps(request.payload).encode("utf-8")
    http_request = urllib.request.Request(
        request.endpoint,
        data=data,
        headers=request.headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(http_request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise OCRError(f"OCR provider returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise OCRError(f"OCR provider request failed: {exc.reason}") from exc

    return json.loads(body)


def ocr_prompt_for_model(model: str) -> str:
    if is_deepseek_ocr_model(model):
        return (
            "You are an OCR engine for sheet music pages. Extract every exact readable text item visible in the image, "
            "including title, lyrics, measure numbers, tempo marks, dynamics, fingering, and annotations. "
            "Do not translate, normalize, rewrite, merge, or correct the text. "
            "If only one measure number is readable, return that exact number and bbox; the renderer can number the rest. "
            "Preserve original wording exactly. Return JSON only as "
            '{"text_blocks":[{"text":"...","bbox":[x1,y1,x2,y2],'
            '"confidence":0.0,"role":"title|instrument|lyric|'
            'expression|footer|measure_number|other"}]}. '
            "Use pixel coordinates in the original image. If a coordinate is impossible to determine, use null for bbox. "
            "Do not describe the image. Do not explain."
        )
    return (
        "Extract all readable score text from this image. "
        "Preserve each text item exactly and include any readable measure number. "
        "Return JSON only as "
        '{"text_blocks":[{"text":"...","bbox":[x1,y1,x2,y2],'
        '"confidence":0.0,"role":"title|instrument|lyric|'
        'expression|footer|measure_number|other"}]}. '
    )
