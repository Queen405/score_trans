from __future__ import annotations
from io import BytesIO
import fitz
from PIL import Image


def composite_preview(background: Image.Image, svg: str) -> Image.Image:
    with fitz.open("svg", svg.encode("utf-8")) as document:
        page = document[0]
        pixmap = page.get_pixmap(
            matrix=fitz.Matrix(
                background.width / page.rect.width, background.height / page.rect.height
            ),
            alpha=True,
        )
        with Image.open(BytesIO(pixmap.tobytes("png"))) as overlay:
            if overlay.size != background.size:
                raise ValueError("SVG 与原图尺寸不一致")
            return Image.alpha_composite(
                background.convert("RGBA"), overlay.convert("RGBA")
            ).convert("RGB")
