from __future__ import annotations

from pydantic import BaseModel, Field

from ..common.types import (
    AccidentalMode,
    InstrumentProfile,
    PolyphonyMode,
    TargetKeyOrAuto,
)
from ..provenance.schemas import TextAnchor


class MusicXmlToJianpuRequest(BaseModel):
    musicxml_file_id: str
    page_image_file_id: str | None = None
    target_key: TargetKeyOrAuto = "C"
    accidental_mode: AccidentalMode = "auto"
    instrument_profile: InstrumentProfile | None = None
    polyphony_mode: PolyphonyMode = "auto"


class MusicXmlToJianpuResponse(BaseModel):
    jianpu_text: str
    text_anchors: list[TextAnchor] = Field(default_factory=list)
    text_hash: str = ""
    warnings: list[str] = Field(default_factory=list)


class JianpuToMusicXmlRequest(BaseModel):
    jianpu_text: str | None = None
    jianpu_file_id: str | None = None
    title: str | None = None


class JianpuToMusicXmlResponse(BaseModel):
    musicxml_text: str
    musicxml_file_id: str
