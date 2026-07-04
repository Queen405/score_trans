"""PDF rendering utilities."""

from __future__ import annotations

from pathlib import Path

def pdf_to_png_pages(
    pdf_path: Path,
    output_dir: Path,
    *,
    dpi: int,
    max_pages: int | None = None,
) -> list[Path]:
    """Render all (or limited) PDF pages to PNG files. Returns list of output paths."""
    if max_pages is not None and max_pages < 0:
        raise ValueError("max_pages 必须是大于等于 0 的整数或 None")

    try:
        import fitz
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Install pymupdf to render PDF pages.") from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    with fitz.open(pdf_path) as doc:
        limit = min(len(doc), max_pages) if max_pages is not None else len(doc)
        for index in range(limit):
            page = doc.load_page(index)
            pixmap = page.get_pixmap(dpi=dpi, alpha=False)
            image_path = output_dir / f"{pdf_path.stem}_page_{index + 1:03d}.png"
            pixmap.save(image_path)
            paths.append(image_path)
    return paths
