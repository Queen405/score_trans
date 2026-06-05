"""PDF rendering utilities."""

from __future__ import annotations

from pathlib import Path

from score_trans.config.settings import PDF_RENDER_DPI as _DEFAULT_PDF_DPI


def pdf_page_to_png(
    pdf_path: Path,
    output_path: Path,
    *,
    page_index: int = 0,
    dpi: int = _DEFAULT_PDF_DPI,
) -> Path:
    """Render a single PDF page to PNG."""
    try:
        import fitz
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Install pymupdf to render PDF pages.") from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with fitz.open(pdf_path) as doc:
        page = doc.load_page(page_index)
        pixmap = page.get_pixmap(dpi=dpi, alpha=False)
        pixmap.save(output_path)
    return output_path


def pdf_to_png_pages(
    pdf_path: Path,
    output_dir: Path,
    *,
    dpi: int = _DEFAULT_PDF_DPI,
    max_pages: int | None = None,
) -> list[Path]:
    """Render all (or limited) PDF pages to PNG files. Returns list of output paths."""
    try:
        import fitz
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Install pymupdf to render PDF pages.") from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    with fitz.open(pdf_path) as doc:
        limit = min(len(doc), max_pages) if max_pages else len(doc)
        for index in range(limit):
            page = doc.load_page(index)
            pixmap = page.get_pixmap(dpi=dpi, alpha=False)
            image_path = output_dir / f"{pdf_path.stem}_page_{index + 1:03d}.png"
            pixmap.save(image_path)
            paths.append(image_path)
    return paths
