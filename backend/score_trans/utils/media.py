"""Media helpers: image encoding, data URLs, etc."""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path


def image_to_data_url(path: Path) -> str:
    """Convert a local image file to a base64 data URL."""
    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"
