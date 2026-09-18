from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont
from ..models.candidates import CandidateRegistry
from ..models.melody import AttachmentCandidate


def render_attachment_atlas(
    image: Image.Image,
    registry: CandidateRegistry,
    body_ids: tuple[str, ...],
    attachments: tuple[AttachmentCandidate, ...],
) -> Image.Image:
    page = Image.new("RGB", (1200, ((len(body_ids) + 2) // 3) * 340), "white")
    font = ImageFont.load_default(size=13)
    lookup = {c.candidate_id: c for c in registry.candidates}
    for i, cid in enumerate(body_ids):
        body = lookup[cid].bounds
        h = body.height
        marks = [a for a in attachments if cid in a.owners]
        left = max(0, int(min([body.x - h * 1.3] + [a.bounds.x - 3 for a in marks])))
        right = min(
            image.width,
            int(max([body.right + h * 1.3] + [a.bounds.right + 3 for a in marks])),
        )
        top = max(0, int(body.y - h * 1.9))
        bottom = min(image.height, int(body.bottom + h * 1.9))
        crop = image.crop((left, top, right, bottom))
        crop.thumbnail((380, 285), Image.Resampling.LANCZOS)
        ox = (i % 3) * 400 + 10
        oy = (i // 3) * 340 + 35
        page.paste(crop, (ox, oy))
        draw = ImageDraw.Draw(page)
        sx = crop.width / (right - left)
        sy = crop.height / (bottom - top)
        for label, box, color in [(cid, body, "blue")] + [
            (a.candidate_id, a.bounds, "red") for a in marks
        ]:
            coords = (
                ox + (box.x - left) * sx,
                oy + (box.y - top) * sy,
                ox + (box.right - left) * sx,
                oy + (box.bottom - top) * sy,
            )
            draw.rectangle(coords, outline=color, width=1)
            draw.text(
                (coords[0], max(oy, coords[1] - 14)), label, font=font, fill=color
            )
        draw.text((ox, oy - 25), "BODY " + cid, font=font, fill="blue")
    return page
