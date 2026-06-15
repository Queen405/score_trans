from __future__ import annotations

from pathlib import Path

from ....models.common.errors import AITranscriptionError
from ....models.common.types import IMAGE_SUFFIXES
from ....utils.pdf import pdf_to_png_pages
from ..core.schemas import PreparedScorePage


def prepare_score_pages(
    input_path: Path,
    output_dir: Path,
    *,
    dpi: int = 220,
    max_pages: int | None = None,
) -> list[PreparedScorePage]:
    suffix = input_path.suffix.lower()
    if suffix == ".pdf":
        return _render_pdf_pages(input_path, output_dir, dpi=dpi, max_pages=max_pages)
    if suffix in IMAGE_SUFFIXES:
        return [PreparedScorePage(page_index=0, image_path=input_path, generated=False)]
    raise AITranscriptionError(f"Unsupported AI transcription input type: {suffix or input_path.name}")


def _render_pdf_pages(
    pdf_path: Path,
    output_dir: Path,
    *,
    dpi: int = 220,
    max_pages: int | None = None,
) -> list[PreparedScorePage]:
    try:
        paths = pdf_to_png_pages(pdf_path, output_dir, dpi=dpi, max_pages=max_pages)
    except RuntimeError as exc:
        raise AITranscriptionError(str(exc)) from exc

    return [
        PreparedScorePage(page_index=index, image_path=path, generated=True)
        for index, path in enumerate(paths)
    ]
