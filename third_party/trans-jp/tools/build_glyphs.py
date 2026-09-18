"""Build a small SVG outline asset from the repository's licensed fonts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    fonts = root / "backend/score_trans/assets/fonts"
    output = Path(__file__).resolve().parents[1] / "trans_jp/assets"
    output.mkdir(parents=True, exist_ok=True)
    glyphs = {}
    sources = {}
    for name, mapping in [
        ("NotoSerifCJKsc-Regular.otf", {str(i): ord(str(i)) for i in range(8)}),
        (
            "Bravura.otf",
            {"♯": 0xE262, "♭": 0xE260, "♮": 0xE261, "𝄪": 0xE263, "𝄫": 0xE264},
        ),
    ]:
        file = fonts / name
        sources[name] = hashlib.sha256(file.read_bytes()).hexdigest()
        with TTFont(file) as font:
            glyph_set = font.getGlyphSet()
            cmap = font.getBestCmap()
            for label, code in mapping.items():
                glyph = glyph_set[cmap[code]]
                outline = SVGPathPen(glyph_set)
                bounds = BoundsPen(glyph_set)
                glyph.draw(outline)
                glyph.draw(bounds)
                glyphs[label] = {"path": outline.getCommands(), "bounds": bounds.bounds}
    (output / "glyphs.json").write_text(
        json.dumps({"sources": sources, "glyphs": glyphs}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    for name in ["OFL-NotoSerifCJK.txt", "OFL-Bravura.txt"]:
        (output / name).write_bytes((fonts / name).read_bytes())


if __name__ == "__main__":
    main()
