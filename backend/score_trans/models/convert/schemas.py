from __future__ import annotations

from pydantic import BaseModel


class MusicXmlToJianpuRequest(BaseModel):
    musicxml_file_id: str
    page_image_file_id: str | None = None
    target_key: str = "C"
    start_measure_number: int | None = None


class MusicXmlToJianpuResponse(BaseModel):
    jianpu_text: str
    jianpu_file_id: str | None = None


class JianpuToMusicXmlRequest(BaseModel):
    jianpu_text: str | None = None
    jianpu_file_id: str | None = None
    title: str = "Jianpu Import"


class JianpuToMusicXmlResponse(BaseModel):
    musicxml_text: str
    musicxml_file_id: str

