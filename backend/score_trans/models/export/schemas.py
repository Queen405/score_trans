from __future__ import annotations

from pydantic import BaseModel

from ..common.types import TargetKeyOrAuto


class ExportResponse(BaseModel):
    file_id: str
    filename: str


class ExportMidiTextRequest(BaseModel):
    jianpu_text: str
    filename: str = "score.mid"
    title: str = "简谱"


class ExportMusicXmlRequest(BaseModel):
    musicxml_file_id: str
    filename: str | None = None
    title: str | None = None
    target_key: TargetKeyOrAuto = "C"
    start_measure_number: int | None = None


class ExportMusicXmlTextRequest(BaseModel):
    jianpu_text: str
    filename: str = "score.musicxml"
    title: str = "简谱"
