from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ..common.types import MidiTempo, TargetKeyOrAuto


class ExportResponse(BaseModel):
    file_id: str
    filename: str


class ExportFilesResponse(BaseModel):
    files: list[ExportResponse]


class ExportRenderedPdfRequest(BaseModel):
    svg_file_ids: list[str] = Field(min_length=1)
    filename: str = "jianpu.pdf"


class ExportRenderedImagesRequest(BaseModel):
    svg_file_ids: list[str] = Field(min_length=1)
    filename: str = "jianpu"
    format: Literal["png", "jpeg"] = "png"
    dpi: Literal[150, 300, 600] = 300


class ExportMidiRequest(BaseModel):
    musicxml_file_id: str
    filename: str | None = None
    title: str | None = None
    target_key: TargetKeyOrAuto = "auto"
    midi_tempo: MidiTempo = "auto"
    start_measure_number: int | None = None


class ExportMidiTextRequest(BaseModel):
    jianpu_text: str
    filename: str = "score.mid"
    title: str = "简谱"
    midi_tempo: MidiTempo = "auto"


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
