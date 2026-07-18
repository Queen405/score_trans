from __future__ import annotations

from pydantic import BaseModel

from ..common.types import AccidentalMode, InstrumentProfile, TargetKeyOrAuto
from ..provenance.schemas import TextAnchor


class MusicXmlToJianpuRequest(BaseModel):
    musicxml_file_id: str
    page_image_file_id: str | None = None
    target_key: TargetKeyOrAuto = "C"
    accidental_mode: AccidentalMode = "auto"
    instrument_profile: InstrumentProfile | None = None


class MusicXmlToJianpuResponse(BaseModel):
    jianpu_text: str
    text_anchors: list[TextAnchor] = []
    text_hash: str = ""


class JianpuToMusicXmlRequest(BaseModel):
    jianpu_text: str | None = None
    jianpu_file_id: str | None = None
    title: str | None = None


class JianpuToMusicXmlResponse(BaseModel):
    musicxml_text: str
    musicxml_file_id: str
