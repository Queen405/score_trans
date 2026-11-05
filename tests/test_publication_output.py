from __future__ import annotations

import fitz
import pytest
from score_trans.domain.jianpu import parse_jianpu_score
from score_trans.services.export.export_service import svg_page_to_image, svg_pages_to_pdf
from score_trans.services.render.main import render_scores_a4_pages


def test_a4_pdf_and_png_exports_share_vector_page_geometry(tmp_path) -> None:
    score = parse_jianpu_score("title=A4\n1=C\n4/4\n1 2 3 4 |")
    page = render_scores_a4_pages([score])[0]
    pdf_path = svg_pages_to_pdf([page.svg.encode("utf-8")], tmp_path / "score.pdf")
    png_path = svg_page_to_image(page.svg.encode("utf-8"), tmp_path / "score.png", dpi=300)

    pdf = fitz.open(pdf_path)
    try:
        assert pdf[0].rect.width == pytest.approx(210 / 25.4 * 72, abs=0.01)
        assert pdf[0].rect.height == pytest.approx(297 / 25.4 * 72, abs=0.01)
        assert not pdf[0].get_images()
        assert len(pdf[0].get_drawings()) > 0
    finally:
        pdf.close()
    pixmap = fitz.Pixmap(str(png_path))
    assert pixmap.width == pytest.approx(2480, abs=2)
    assert pixmap.height == pytest.approx(3508, abs=2)
