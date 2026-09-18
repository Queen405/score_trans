from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont
from ..models.geometry import Box


def render_metadata_atlas(
    work: Image.Image, regions: tuple[tuple[str, Box], ...]
) -> Image.Image:
    atlas = Image.new("RGB", (900, 180 * len(regions)), "white")
    draw = ImageDraw.Draw(atlas)
    font = ImageFont.load_default(size=18)
    for i, (rid, b) in enumerate(regions):
        crop = work.crop((int(b.x), int(b.y), int(b.right), int(b.bottom)))
        ratio = min(860 / max(crop.width, 1), 140 / max(crop.height, 1))
        crop = crop.resize(
            (max(1, round(crop.width * ratio)), max(1, round(crop.height * ratio))),
            Image.Resampling.LANCZOS,
        )
        atlas.paste(crop, (20, i * 180 + 35))
        draw.text((20, i * 180 + 5), rid, font=font, fill="blue")
    return atlas
