from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ...domain.jianpu import parse_jianpu_score
from ...domain.musicxml import score_to_jianpu_text
from ...models.common.errors import AITranscriptionError
from ..recognize.image_preprocessing import IMAGE_SUFFIXES
from .provider import LangChainVisionJianpuProvider, VisionJianpuProvider, VisionPageResult


@dataclass(slots=True)
class PreparedScorePage:
    page_index: int
    image_path: Path
    generated: bool = False


@dataclass(slots=True)
class TranscribedScorePage:
    prepared: PreparedScorePage
    result: VisionPageResult
    jianpu_text: str
    validation_errors: list[str]


@dataclass(slots=True)
class AiTranscriptionResult:
    source_path: Path
    pages: list[TranscribedScorePage]
    merged_jianpu_text: str
    warnings: list[str]


class AiTranscriptionService:
    def __init__(self, provider: VisionJianpuProvider | None = None) -> None:
        self.provider = provider or LangChainVisionJianpuProvider()

    def transcribe(
        self,
        input_path: str | Path,
        output_dir: str | Path,
        *,
        target_key: str = "C",
        title: str | None = None,
        render_dpi: int = 220,
        max_pages: int | None = None,
        extra_prompt: str | None = None,
        normalize: bool = True,
    ) -> AiTranscriptionResult:
        source = Path(input_path).resolve()
        out_dir = Path(output_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        prepared_pages = prepare_score_pages(
            source,
            out_dir / "pages",
            dpi=render_dpi,
            max_pages=max_pages,
        )
        if not prepared_pages:
            raise AITranscriptionError(f"No transcribable score pages found in {source}")

        pages: list[TranscribedScorePage] = []
        warnings: list[str] = []
        for prepared in prepared_pages:
            result = self.provider.transcribe_page(
                prepared.image_path,
                target_key=target_key,
                title=title,
                page_index=prepared.page_index,
                extra_prompt=extra_prompt,
            )
            page_text = ensure_jianpu_header(
                clean_jianpu_text(result.jianpu_text),
                target_key=result.key or target_key,
                meter=result.meter,
                title=result.title or title,
                tempo=result.tempo,
            )
            normalized_text, validation_errors = validate_jianpu_text(
                page_text,
                title=result.title or title,
                normalize=normalize,
            )
            if validation_errors:
                warnings.extend(
                    f"第 {prepared.page_index + 1} 页：{error}"
                    for error in validation_errors
                )
            pages.append(
                TranscribedScorePage(
                    prepared=prepared,
                    result=result,
                    jianpu_text=normalized_text,
                    validation_errors=validation_errors,
                )
            )

        merged = merge_page_jianpu_texts(
            [page.jianpu_text for page in pages],
            target_key=target_key,
            title=title or first_present([page.result.title for page in pages]),
        )
        return AiTranscriptionResult(
            source_path=source,
            pages=pages,
            merged_jianpu_text=merged,
            warnings=warnings,
        )


def prepare_score_pages(
    input_path: Path,
    output_dir: Path,
    *,
    dpi: int = 220,
    max_pages: int | None = None,
) -> list[PreparedScorePage]:
    suffix = input_path.suffix.lower()
    if suffix == ".pdf":
        return render_pdf_pages(input_path, output_dir, dpi=dpi, max_pages=max_pages)
    if suffix in IMAGE_SUFFIXES:
        return [PreparedScorePage(page_index=0, image_path=input_path, generated=False)]
    raise AITranscriptionError(f"Unsupported AI transcription input type: {suffix or input_path.name}")


def render_pdf_pages(
    pdf_path: Path,
    output_dir: Path,
    *,
    dpi: int = 220,
    max_pages: int | None = None,
) -> list[PreparedScorePage]:
    try:
        import fitz
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise AITranscriptionError("Install pymupdf to render PDF pages for AI transcription.") from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    pages: list[PreparedScorePage] = []
    with fitz.open(pdf_path) as doc:
        page_count = len(doc)
        limit = min(page_count, max_pages) if max_pages else page_count
        for index in range(limit):
            page = doc.load_page(index)
            pixmap = page.get_pixmap(dpi=dpi, alpha=False)
            image_path = output_dir / f"{pdf_path.stem}_page_{index + 1:03d}.png"
            pixmap.save(image_path)
            pages.append(
                PreparedScorePage(
                    page_index=index,
                    image_path=image_path,
                    generated=True,
                )
            )
    return pages


def clean_jianpu_text(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()

    migrated: list[str] = []
    for raw in stripped.splitlines():
        line = raw.strip()
        if re.match(r"(?i)^key\s*=", line):
            migrated.append(f"1={line.split('=', 1)[1].strip()}")
        elif re.match(r"(?i)^time\s*=", line):
            migrated.append(line.split("=", 1)[1].strip())
        else:
            migrated.append(raw)
    return "\n".join(migrated).strip()


def ensure_jianpu_header(
    text: str,
    *,
    target_key: str,
    meter: str | None = None,
    title: str | None = None,
    tempo: str | None = None,
) -> str:
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    resolved_key = normalize_key_value(target_key) or "C"
    resolved_meter = normalize_meter_value(meter) or "4/4"
    prefix: list[str] = []
    if title and not any(line.strip().startswith("title=") for line in lines):
        prefix.append(f"title={title}")
    if not any(re.fullmatch(r"\s*1\s*=\s*.+", line) for line in lines):
        prefix.append(f"1={resolved_key}")
    if not any(re.fullmatch(r"\s*\d+\s*/\s*\d+\s*", line) for line in lines):
        prefix.append(resolved_meter)
    if tempo and not any(line.strip().startswith("tempo=") for line in lines):
        tempo_value = tempo.split("=", 1)[-1].strip() if "=" in tempo else tempo.strip()
        if tempo_value:
            prefix.append(f"tempo={tempo_value}")
    return "\n".join(prefix + lines).strip()


def normalize_key_value(value: str | None) -> str | None:
    if not value:
        return None
    work = value.strip()
    if "=" in work:
        left, right = [part.strip() for part in work.split("=", 1)]
        if left.lower() in {"1", "key"}:
            work = right
    return work or None


def normalize_meter_value(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"\d+\s*/\s*\d+", value)
    if not match:
        return None
    return match.group(0).replace(" ", "")


def validate_jianpu_text(
    text: str,
    *,
    title: str | None = None,
    normalize: bool = True,
) -> tuple[str, list[str]]:
    try:
        score = parse_jianpu_score(text, title=title)
    except ValueError as exc:
        return text, [str(exc)]

    validation_errors = [
        f"第 {index} 小节：{error}"
        for index, measure in enumerate(score.measures, start=1)
        for error in measure.validation_errors
    ]
    if not normalize:
        return text, validation_errors
    return score_to_jianpu_text(score), validation_errors


def merge_page_jianpu_texts(
    page_texts: list[str],
    *,
    target_key: str = "C",
    title: str | None = None,
) -> str:
    non_empty = [text for text in page_texts if text.strip()]
    if not non_empty:
        return f"1={target_key}\n4/4\n"

    first_header = extract_header(non_empty[0])
    header: list[str] = []
    resolved_title = title or first_header.get("title")
    if resolved_title:
        header.append(f"title={resolved_title}")
    header.append(f"1={first_header.get('key') or target_key}")
    header.append(first_header.get("meter") or "4/4")
    if first_header.get("tempo"):
        header.append(f"tempo={first_header['tempo']}")

    body: list[str] = []
    for index, text in enumerate(non_empty, start=1):
        stripped = strip_header(text)
        if stripped:
            body.append(f"# Page {index}")
            body.append(stripped)
    return "\n".join(header + [""] + body).strip()


def extract_header(text: str) -> dict[str, str]:
    header: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("title="):
            header["title"] = line.split("=", 1)[1].strip()
        elif line.startswith("1="):
            header["key"] = line.split("=", 1)[1].strip()
        elif line.startswith("tempo="):
            header["tempo"] = line.split("=", 1)[1].strip()
        elif re.fullmatch(r"\d+\s*/\s*\d+", line) and "meter" not in header:
            header["meter"] = line.replace(" ", "")
    return header


def strip_header(text: str) -> str:
    body: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if (
            line.startswith("title=")
            or line.startswith("1=")
            or line.startswith("tempo=")
            or re.fullmatch(r"\d+\s*/\s*\d+", line)
        ):
            continue
        body.append(raw)
    return "\n".join(body).strip()


def first_present(values: list[str | None]) -> str | None:
    for value in values:
        if value:
            return value
    return None
