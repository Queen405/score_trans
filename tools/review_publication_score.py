"""Render a real multi-part score and build a browsable visual review gallery.

Run with the project venv and PYTHONPATH=backend. The gallery and raster pages
are review artifacts; the original score and application settings are untouched.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from html import escape
from pathlib import Path

from PIL import Image, ImageDraw

from score_trans.domain.parse.jianpu_text import parse_jianpu_parts
from score_trans.services.export.export_service import svg_page_to_image
from score_trans.services.render.main import _a4_renderer
from score_trans.services.render.options import A4LayoutOptions, RenderOptions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--title")
    parser.add_argument("--measures-per-system", type=int, choices=(3, 4, 5), default=5)
    parser.add_argument("--part-gap-percent", type=int, default=75)
    parser.add_argument("--system-gap-percent", type=int, default=40)
    parser.add_argument(
        "--break-beams-at-beat", action=argparse.BooleanOptionalAction, default=True
    )
    parser.add_argument("--dpi", type=int, default=150)
    args = parser.parse_args()
    scores = [
        part.score
        for part in parse_jianpu_parts(args.source.read_text(encoding="utf-8"))
    ]
    layout = A4LayoutOptions(
        measures_per_system=args.measures_per_system,
        part_gap_percent=args.part_gap_percent,
        system_gap_percent=args.system_gap_percent,
        break_beams_at_beat=args.break_beams_at_beat,
    )
    title = args.title or scores[0].title or args.source.stem
    renderer = _a4_renderer(RenderOptions(title=title), layout)
    pages = renderer.render_scores(scores, title=title, initial_measure_number=1)
    args.output.mkdir(parents=True, exist_ok=True)
    page_reports: list[dict[str, object]] = []
    report: dict[str, object] = {
        "title": title,
        "layout_key": layout.key,
        "pages": page_reports,
    }
    thumbnails: list[Image.Image] = []
    cards: list[str] = []
    for index, page in enumerate(pages, 1):
        name = f"page-{index:02d}"
        (args.output / f"{name}.svg").write_text(page.svg, encoding="utf-8")
        svg_page_to_image(
            page.svg.encode("utf-8"), args.output / f"{name}.png", dpi=args.dpi
        )
        counts = dict(Counter(issue["kind"] for issue in page.scene.geometry_issues))
        music_bottom = (
            max(
                (
                    record.bbox.y + record.bbox.height
                    for record in page.scene.geometry_records
                    if "page-background" not in record.classes
                    and "page-number" not in record.classes
                ),
                default=0.0,
            )
            * page.scene.coordinate_scale
        )
        barline_columns = sorted(
            {
                round(float(node.attrs["x1"]) * page.scene.coordinate_scale, 3)
                for node in page.scene.nodes
                if node.attrs.get("class") == "measure"
            }
        )
        page_reports.append(
            {
                "page": index,
                "diagnostics": counts,
                "barline_columns": barline_columns,
                "music_bottom": music_bottom,
                "bottom_blank_mm": (page.scene.height - music_bottom)
                * 210
                / page.scene.width,
            }
        )
        with Image.open(args.output / f"{name}.png") as raster:
            thumbnail = raster.convert("RGB")
            thumbnail.thumbnail((360, 510))
            tile = Image.new("RGB", (384, 548), "#e3e6e9")
            tile.paste(thumbnail, ((384 - thumbnail.width) // 2, 8))
            ImageDraw.Draw(tile).text((12, 526), f"Page {index}", fill="black")
            thumbnails.append(tile)
        cards.append(
            f'<figure><a href="{name}.svg"><img src="{name}.png" loading="lazy"></a>'
            f'<figcaption>第 {index} 页 · <a href="{name}.png">PNG</a> · '
            f'<a href="{name}.svg">SVG</a></figcaption></figure>'
        )
        print(f"{name}: {counts}", flush=True)
    columns = 4
    sheet = Image.new(
        "RGB",
        (columns * 384, ((len(thumbnails) + columns - 1) // columns) * 548),
        "white",
    )
    for index, tile in enumerate(thumbnails):
        sheet.paste(tile, ((index % columns) * 384, (index // columns) * 548))
    sheet.save(args.output / "contact.png")
    (args.output / "metrics.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    html = '<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
    html += f"<title>{escape(title)} · 出版渲染检查</title>"
    html += (
        "<style>body{background:#e9edf0;color:#17212b;font:16px system-ui;margin:32px}"
    )
    html += "main{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:24px}"
    html += "figure{margin:0}img{width:100%;background:white}figcaption{padding:12px 0}a{color:#1459a0}</style>"
    html += f"<h1>{escape(title)}</h1><p>每行 {args.measures_per_system} 小节 · {len(pages)} 页 · "
    html += (
        "点击页面查看可缩放的原始 SVG。</p><main>" + "".join(cards) + "</main></html>"
    )
    (args.output / "index.html").write_text(html, encoding="utf-8")
    print(args.output.resolve())


if __name__ == "__main__":
    main()
