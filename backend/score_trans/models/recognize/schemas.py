from __future__ import annotations

from pydantic import BaseModel


class RecognizeResponse(BaseModel):
    musicxml_file_id: str
    musicxml_filename: str
    musicxml_text: str = ""
    omr_file_id: str | None = None
    overlay_file_id: str | None = None
    source_map_file_id: str | None = None
    overlay_svg_file_id: str | None = None
