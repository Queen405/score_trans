"""Media helpers: image encoding, data URLs, etc."""

from __future__ import annotations

import base64
import io
import mimetypes
from pathlib import Path

_MAX_IMAGE_EDGE = 2000
_JPEG_QUALITY = 85


def image_to_data_url(path: Path) -> str:
    """Convert a local image file to a base64 data URL.

    Large images are resized to a max edge of 2000px and re-encoded as JPEG
    to reduce upload size and API processing time for vision transcription.
    """
    raw = path.read_bytes()
    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"

    try:
        from PIL import Image
    except ImportError:
        encoded = base64.b64encode(raw).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"

    try:
        img = Image.open(path)
    except Exception:
        encoded = base64.b64encode(raw).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"

    longest_edge = max(img.size)
    if longest_edge <= _MAX_IMAGE_EDGE:
        encoded = base64.b64encode(raw).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"

    ratio = _MAX_IMAGE_EDGE / longest_edge
    new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
    img = img.convert("RGB").resize(new_size, Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=_JPEG_QUALITY)
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return "data:image/jpeg;base64," + encoded
