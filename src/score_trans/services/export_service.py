from __future__ import annotations

from fractions import Fraction
from io import BytesIO
from pathlib import Path

import fitz
import mido

from ..domain.jianpu import KEY_TO_TONIC, MAJOR_SCALE
from ..domain.models import JianpuPitch, JianpuScore
from .render_service import RenderService

_TICKS_PER_BEAT = 480


def _pitch_to_midi(pitch: JianpuPitch, key: str) -> int:
    if pitch.midi is not None:
        return pitch.midi
    tonic = KEY_TO_TONIC.get(key, 0)
    base_semitone = MAJOR_SCALE[pitch.degree - 1] if 1 <= pitch.degree <= 7 else 0
    midi = 60 + tonic + base_semitone + pitch.accidental + pitch.octave * 12
    return midi


def _duration_to_ticks(duration: Fraction, beat_type: int) -> int:
    quarter_note_fraction = Fraction(4, beat_type)
    quarters = duration / quarter_note_fraction
    return max(1, int(quarters * _TICKS_PER_BEAT))


def png_pages_to_pdf(png_pages: list[bytes], output_path: Path) -> Path:
    doc = fitz.open()
    for png_data in png_pages:
        src_doc = fitz.open("png", png_data)
        page_rect = src_doc[0].rect
        w, h = page_rect.width, page_rect.height
        page = doc.new_page(width=w, height=h)
        page.insert_image(fitz.Rect(0, 0, w, h), pixmap=src_doc[0].get_pixmap())
        src_doc.close()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    doc.close()
    return output_path


class ExportService:
    def __init__(self, render_service: RenderService | None = None) -> None:
        self.render_service = render_service or RenderService()

    def export_svg(self, score: JianpuScore, output_path: Path, title: str | None = None) -> Path:
        self.render_service.render_score_svg(score, output_path, title=title)
        return output_path

    def export_midi(self, score: JianpuScore, output_path: Path) -> Path:
        mid = mido.MidiFile(ticks_per_beat=_TICKS_PER_BEAT)
        track = mido.MidiTrack()
        mid.tracks.append(track)

        tempo = mido.bpm2tempo(120)
        track.append(mido.MetaMessage("set_tempo", tempo=tempo, time=0))

        key = score.target_key
        beat_type = score.beat_type

        for measure in score.measures:
            for event in measure.events:
                if event.kind == "rest":
                    ticks = _duration_to_ticks(event.duration, beat_type)
                    track.append(mido.Message("note_off", note=0, velocity=0, time=ticks))
                    continue
                if not event.pitches:
                    continue

                ticks = _duration_to_ticks(event.duration, beat_type)
                for i, pitch in enumerate(event.pitches):
                    midi_note = max(0, min(127, _pitch_to_midi(pitch, key)))
                    track.append(mido.Message("note_on", note=midi_note, velocity=80, time=0))
                for i, pitch in enumerate(event.pitches):
                    midi_note = max(0, min(127, _pitch_to_midi(pitch, key)))
                    track.append(mido.Message("note_off", note=midi_note, velocity=0, time=ticks if i == 0 else 0))

        output_path.parent.mkdir(parents=True, exist_ok=True)
        mid.save(str(output_path))
        return output_path

    def export(self, score: JianpuScore, output_path: Path, title: str | None = None) -> Path:
        fmt = output_path.suffix.lower()
        if fmt == ".svg":
            return self.export_svg(score, output_path, title=title)
        if fmt in (".mid", ".midi"):
            return self.export_midi(score, output_path)
        raise ValueError(f"导出为 {fmt} 需要前端提供 PNG 数据")
