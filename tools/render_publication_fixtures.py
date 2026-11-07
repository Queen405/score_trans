"""Render the publication review corpus to SVG and 300 DPI PNG."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from score_trans.domain.parse.jianpu_text import parse_jianpu_parts
from score_trans.services.export.export_service import svg_page_to_image
from score_trans.services.render.main import render_scores_a4_pages
from score_trans.services.render.options import A4LayoutOptions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    fixture_root = (
        Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "publication"
    )
    cases = json.loads((fixture_root / "cases.json").read_text(encoding="utf-8"))
    args.output.mkdir(parents=True, exist_ok=True)
    for case in cases:
        source = (fixture_root / case["path"]).resolve()
        parts = parse_jianpu_parts(source.read_text(encoding="utf-8"))
        pages = render_scores_a4_pages(
            [part.score for part in parts],
            layout=A4LayoutOptions(measures_per_system=case["measures_per_system"]),
        )
        for index, page in enumerate(pages, 1):
            stem = args.output / f"{case['name']}-page-{index:02d}"
            stem.with_suffix(".svg").write_text(page.svg, encoding="utf-8")
            svg_page_to_image(
                page.svg.encode("utf-8"), stem.with_suffix(".png"), dpi=300
            )
        print(f"{case['name']}: {len(pages)} page(s)")


if __name__ == "__main__":
    main()
