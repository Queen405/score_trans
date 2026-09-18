from __future__ import annotations

from pathlib import Path
from PIL import Image
from ..models.contracts import RowSegment
from ..models.errors import EngineError


def load_image(path: Path) -> Image.Image:
    try:
        with Image.open(path) as image:
            image.load()
            # Composite transparent scans on paper; preserve the source pixel frame.
            if image.mode in ("RGBA", "LA") or "transparency" in image.info:
                rgba = image.convert("RGBA")
                paper = Image.new("RGBA", rgba.size, "white")
                return Image.alpha_composite(paper, rgba).convert("RGB")
            return image.convert("RGB")
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise EngineError(f"图片无法解码: {path}: {exc}", 1) from exc


def save_rows(image: Image.Image, rows: list[RowSegment]) -> None:
    for row in rows:
        row.image_path.parent.mkdir(parents=True, exist_ok=True)
        image.crop((0, row.work_y_top, row.width, row.work_y_top + row.height)).save(
            row.image_path
        )
