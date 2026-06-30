from __future__ import annotations

import re
import struct
from pathlib import Path


def image_dimensions(path: str | Path) -> tuple[float, float]:
    file_path = Path(path)
    with file_path.open("rb") as handle:
        head = handle.read(32)

    if len(head) >= 24 and head.startswith(b"\x89PNG\r\n\x1a\n"):
        return float(struct.unpack(">I", head[16:20])[0]), float(
            struct.unpack(">I", head[20:24])[0]
        )

    if len(head) >= 2 and head[:2] == b"\xff\xd8":
        return _jpeg_dimensions(file_path)

    if len(head) >= 5 and head.startswith(b"%PDF"):
        return _pdf_page_dimensions(file_path)

    return 1600.0, 1200.0


def _jpeg_dimensions(path: Path) -> tuple[float, float]:
    with path.open("rb") as handle:
        handle.read(2)
        while True:
            marker_start = handle.read(1)
            if not marker_start:
                break
            if marker_start != b"\xff":
                continue
            marker = handle.read(1)
            while marker == b"\xff":
                marker = handle.read(1)
            if marker in {
                b"\xc0",
                b"\xc1",
                b"\xc2",
                b"\xc3",
                b"\xc5",
                b"\xc6",
                b"\xc7",
                b"\xc9",
                b"\xca",
                b"\xcb",
                b"\xcd",
                b"\xce",
                b"\xcf",
            }:
                length = struct.unpack(">H", handle.read(2))[0]
                data = handle.read(length - 2)
                if len(data) >= 5:
                    height = struct.unpack(">H", data[1:3])[0]
                    width = struct.unpack(">H", data[3:5])[0]
                    return float(width), float(height)
            else:
                length_raw = handle.read(2)
                if len(length_raw) != 2:
                    break
                length = struct.unpack(">H", length_raw)[0]
                handle.seek(max(0, length - 2), 1)
    return 1600.0, 1200.0


def _pdf_page_dimensions(path: Path) -> tuple[float, float]:
    data = path.read_bytes()[:1_000_000]
    match = re.search(
        rb"/(?:CropBox|MediaBox)\s*\[\s*([\d.+-]+)\s+([\d.+-]+)\s+([\d.+-]+)\s+([\d.+-]+)\s*\]",
        data,
    )
    if not match:
        return 1600.0, 1200.0
    x1, y1, x2, y2 = (float(value) for value in match.groups())
    return max(1.0, x2 - x1), max(1.0, y2 - y1)


_STRIP_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def strip_image_metadata(path: Path) -> bool:
    file_path = Path(path)
    if file_path.suffix.lower() not in _STRIP_SUFFIXES:
        return False

    tmp_path = file_path.with_name(file_path.name + ".strip.tmp")
    try:
        from PIL import Image

        with Image.open(file_path) as image:
            image.load()
            save_kwargs: dict[str, object] = {}
            if image.format == "JPEG":
                save_kwargs = {"quality": 95}
            elif image.format == "WEBP":
                save_kwargs = {"quality": 95}
            elif image.format == "PNG":
                save_kwargs = {"optimize": True}
            image.save(tmp_path, format=image.format, **save_kwargs)
        tmp_path.replace(file_path)
        return True
    except Exception:
        try:
            tmp_path.unlink()
        except OSError:
            pass
        return False
