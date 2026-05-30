from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from ..domain.models import OCRTextBlock, TextRole
from .env_file import DISABLE_DOTENV_ENV, load_project_env


OCR_API_KEY_ENV = "SCORE_TRANS_OCR_API_KEY"
OCR_BASE_URL_ENV = "SCORE_TRANS_OCR_BASE_URL"
OCR_MODEL_ENV = "SCORE_TRANS_OCR_MODEL"
DEFAULT_OCR_BASE_URL = "https://api.siliconflow.cn/v1"
DEFAULT_OCR_MODEL = "deepseek-ai/DeepSeek-OCR"


class OCRError(RuntimeError):
    """Raised when OCR request construction, transport, or parsing fails."""


class OCRProvider(Protocol):
    def recognize(self, image_path: str | Path) -> list[OCRTextBlock]:
        """Return OCR text blocks for an image file."""


@dataclass(slots=True)
class OCRRequest:
    endpoint: str
    headers: dict[str, str]
    payload: dict[str, Any]


class MockOCRProvider:
    def __init__(self, blocks: list[OCRTextBlock] | None = None) -> None:
        self.blocks = list(blocks or [])
        self.calls: list[Path] = []

    def recognize(self, image_path: str | Path) -> list[OCRTextBlock]:
        self.calls.append(Path(image_path))
        return list(self.blocks)


class OpenAICompatibleOCRProvider:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 60.0,
        dry_run: bool = False,
    ) -> None:
        explicit_api_key = os.environ.get(OCR_API_KEY_ENV)
        explicit_base_url = os.environ.get(OCR_BASE_URL_ENV)
        explicit_model = os.environ.get(OCR_MODEL_ENV)
        load_project_env()
        persisted = persisted_ocr_settings()
        self.base_url = (
            base_url
            or explicit_base_url
            or persisted.get("ocr_base_url")
            or os.environ.get(OCR_BASE_URL_ENV)
            or DEFAULT_OCR_BASE_URL
        ).rstrip("/")
        self.model = model or explicit_model or persisted.get("ocr_model") or os.environ.get(OCR_MODEL_ENV) or DEFAULT_OCR_MODEL
        self.api_key = explicit_api_key or persisted.get("ocr_api_key") or os.environ.get(OCR_API_KEY_ENV)
        self.timeout = timeout
        self.dry_run = dry_run

    def recognize(self, image_path: str | Path) -> list[OCRTextBlock]:
        request = self.build_request(image_path)
        if self.dry_run:
            return []

        data = json.dumps(request.payload).encode("utf-8")
        http_request = urllib.request.Request(
            request.endpoint,
            data=data,
            headers=request.headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(http_request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise OCRError(f"OCR provider returned HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise OCRError(f"OCR provider request failed: {exc.reason}") from exc

        return parse_openai_compatible_response(json.loads(body))

    def build_request(self, image_path: str | Path) -> OCRRequest:
        load_project_env()
        path = Path(image_path)
        if not path.is_file():
            raise FileNotFoundError(path)

        if not self.api_key and not self.dry_run:
            raise OCRError(f"Set {OCR_API_KEY_ENV} before calling the OCR provider.")

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": ocr_prompt_for_model(self.model),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": image_to_data_url(path)},
                        },
                    ],
                }
            ],
            "temperature": 0,
        }
        if not is_deepseek_ocr_model(self.model):
            payload["response_format"] = {"type": "json_object"}

        return OCRRequest(
            endpoint=f"{self.base_url}/chat/completions",
            headers=headers,
            payload=payload,
        )


def image_to_data_url(path: Path) -> str:
    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def is_deepseek_ocr_model(model: str) -> bool:
    return model.lower().endswith("/deepseek-ocr") or model.lower() == "deepseek-ocr"


def persisted_ocr_settings() -> dict[str, str]:
    if os.environ.get(DISABLE_DOTENV_ENV):
        return {}
    try:
        from .settings_db import SettingsDB

        return SettingsDB().get_all()
    except Exception:
        return {}


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
        'expression|footer|measure_number|other"}]}.'
    )


def parse_openai_compatible_response(response: dict[str, Any]) -> list[OCRTextBlock]:
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise OCRError("OCR provider response did not contain message content.") from exc

    try:
        payload = parse_json_content(content)
    except (json.JSONDecodeError, OCRError):
        return plain_text_to_blocks(content_to_text(content))

    if isinstance(payload, list):
        return coerce_text_block_list(payload)
    if isinstance(payload, str):
        return plain_text_to_blocks(payload)
    if not isinstance(payload, dict):
        raise OCRError("OCR provider JSON response must be an object or list.")

    raw_blocks = payload.get("text_blocks", payload.get("blocks", []))
    if not isinstance(raw_blocks, list):
        raise OCRError("OCR provider JSON must contain a text_blocks list.")
    return coerce_text_block_list(raw_blocks)


def parse_json_content(content: Any) -> Any:
    if isinstance(content, dict):
        return content
    text = content_to_text(content)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise
        parsed = json.loads(match.group(0))

    return parsed


def content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(part.get("text", "") for part in content if isinstance(part, dict))
    if isinstance(content, dict):
        return json.dumps(content, ensure_ascii=False)
    raise OCRError("OCR provider message content is not text.")


def coerce_text_block_list(raw_blocks: list[Any]) -> list[OCRTextBlock]:
    blocks: list[OCRTextBlock] = []
    for raw in raw_blocks:
        if isinstance(raw, dict):
            blocks.append(coerce_text_block(raw))
        elif raw is not None and str(raw).strip():
            blocks.append(OCRTextBlock(text=str(raw).strip(), role=infer_text_role(str(raw))))
    return blocks


def plain_text_to_blocks(text: str) -> list[OCRTextBlock]:
    return [
        OCRTextBlock(text=line, role=infer_text_role(line))
        for line in cleaned_plain_text_lines(text)
    ]


def cleaned_plain_text_lines(text: str) -> list[str]:
    stripped = text.strip()
    if stripped.startswith('"""') and stripped.endswith('"""'):
        stripped = stripped[3:-3].strip()
    lines = []
    seen = set()
    for line in stripped.splitlines():
        line = clean_plain_text_line(line)
        key = line.casefold()
        if line and key not in seen:
            lines.append(line)
            seen.add(key)
    return lines


def clean_plain_text_line(line: str) -> str:
    line = line.strip().strip("`")
    for marker in (
        "The text in the image",
        "The image contains",
        "The text reads",
        "Text in the image",
        "Visible text",
    ):
        if marker in line:
            line = line.split(marker, 1)[0].strip()
    line = re.sub(r"^\d+\.\s+(?=[A-Za-z\u4e00-\u9fff])", "", line)
    line = line.strip(":： \t")
    line = collapse_exact_repetition(line)
    if not line:
        return ""
    lowered = line.lower()
    if lowered in {
        "the text reads",
        "the text in the image is",
        "the image contains the following text",
    }:
        return ""
    return line


def collapse_exact_repetition(text: str) -> str:
    value = text.strip()
    while value and len(value) % 2 == 0 and value[: len(value) // 2] == value[len(value) // 2 :]:
        value = value[: len(value) // 2].strip()
    return value


def infer_text_role(text: str) -> TextRole:
    lowered = text.lower()
    if re.search(r"\b(allegro|andante|moderato|largo|adagio|presto|rit\.?|accel\.?)\b", lowered):
        return "expression"
    if re.search(r"\b\d+\s*=\s*[A-Ga-g]", text):
        return "expression"
    if re.fullmatch(r"\d+", text.strip()):
        return "measure_number"
    return "other"


def coerce_text_block(raw: Any) -> OCRTextBlock:
    if not isinstance(raw, dict):
        raise OCRError("Each OCR text block must be an object.")

    text = str(raw.get("text", ""))
    bbox = coerce_bbox(raw.get("bbox"))
    confidence = raw.get("confidence")
    if confidence is not None:
        confidence = float(confidence)

    role = raw.get("role") or infer_text_role(text)
    if role not in TextRole.__args__:
        role = infer_text_role(text)

    return OCRTextBlock(
        text=text,
        bbox=bbox,
        confidence=confidence,
        role=role,
        measure_number=raw.get("measure_number"),
    )


def coerce_bbox(raw: Any) -> tuple[float, float, float, float] | None:
    if raw is None:
        return None
    if not isinstance(raw, (list, tuple)) or len(raw) != 4:
        raise OCRError("OCR bbox must contain four numbers.")
    return tuple(float(value) for value in raw)
