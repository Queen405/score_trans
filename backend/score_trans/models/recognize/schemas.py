from __future__ import annotations

from pydantic import BaseModel


class RecognizeResponse(BaseModel):
    musicxml_file_id: str
    musicxml_filename: str
