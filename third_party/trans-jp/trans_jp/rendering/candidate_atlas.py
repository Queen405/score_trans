from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont
from ..models.candidates import CandidateRegistry


def render_atlases(
    image: Image.Image,
    registry: CandidateRegistry,
    *,
    candidate_ids: tuple[str, ...] | None = None,
) -> list[Image.Image]:
    pages = []
    shown = [
        c
        for c in registry.candidates
        if candidate_ids is None or c.candidate_id in candidate_ids
    ]
    font = ImageFont.load_default(size=17)
    for offset in range(0, len(shown), 24):
        page = Image.new("RGB", (1152, 640), "white")
        draw = ImageDraw.Draw(page)
        for index, c in enumerate(shown[offset : offset + 24]):
            x, y = (index % 6) * 192, (index // 6) * 160
            b = c.bounds
            h = max(8, min(b.height, 80))
            neighbors = [
                other.bounds
                for other in registry.candidates
                if other.candidate_id != c.candidate_id
                and set(other.band_ids).intersection(c.band_ids)
                and other.candidate_id not in c.conflicts
            ]
            left = max(
                ((other.right + b.x) / 2 for other in neighbors if other.right < b.x),
                default=0,
            )
            right = min(
                ((other.x + b.right) / 2 for other in neighbors if other.x > b.right),
                default=image.width,
            )
            crop_box = (
                max(0, int(max(left, b.x - h))),
                max(0, int(b.y - h * 1.5)),
                min(image.width, int(min(right, b.right + h) + 1)),
                min(image.height, int(b.bottom + h * 1.5)),
            )
            crop = image.crop(crop_box).convert("RGB")
            scale = min(180 / crop.width, 128 / crop.height)
            resized = crop.resize(
                (max(1, round(crop.width * scale)), max(1, round(crop.height * scale))),
                Image.Resampling.LANCZOS,
            )
            sx, sy = resized.width / crop.width, resized.height / crop.height
            px, py = x + (192 - resized.width) // 2, y + 27
            page.paste(resized, (px, py))
            # Put the rectangle outside the glyph, not through its strokes.
            draw.rectangle(
                (
                    px + (b.x - crop_box[0]) * sx - 2,
                    py + (b.y - crop_box[1]) * sy - 2,
                    px + (b.right - crop_box[0]) * sx + 2,
                    py + (b.bottom - crop_box[1]) * sy + 2,
                ),
                outline="#1976d2",
                width=1,
            )
            draw.rectangle((x, y, x + 191, y + 159), outline="#bbbbbb", width=1)
            draw.rectangle((x + 1, y + 1, x + 190, y + 24), fill="#e8efff")
            draw.text((x + 6, y + 3), c.candidate_id, font=font, fill="#15336a")
        pages.append(page)
    return pages
