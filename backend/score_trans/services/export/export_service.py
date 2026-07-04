from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import fitz
import mido

from score_trans.config.settings import (
    MIDI_DEFAULT_BPM,
    MIDI_DEFAULT_VELOCITY,
    MIDI_TICKS_PER_BEAT,
)

from ...domain.constants import KEY_TO_TONIC, MAJOR_SCALE
from ...domain.write.musicxml import scores_to_musicxml
from ...models.score import JianpuPitch, JianpuScore

_TICKS_PER_BEAT = MIDI_TICKS_PER_BEAT


def _pitch_to_midi(pitch: JianpuPitch, key: str) -> int:
    if pitch.midi is not None:
        midi = pitch.midi
    else:
        tonic = KEY_TO_TONIC.get(key, 0)
        base_semitone = MAJOR_SCALE[pitch.degree - 1] if 1 <= pitch.degree <= 7 else 0
        midi = 60 + tonic + base_semitone + pitch.accidental + pitch.octave * 12
    if midi.denominator != 1:
        raise ValueError("MIDI 导出暂不支持微音程：需要 pitch bend 通道分配")
    return int(midi)


def _duration_to_ticks(duration: Fraction, beat_type: int) -> int:
    quarter_note_fraction = Fraction(4, beat_type)
    quarters = duration / quarter_note_fraction
    return max(1, int(quarters * _TICKS_PER_BEAT))


def images_to_pdf(image_pages: list[bytes], output_path: Path) -> Path:
    a4_width = 595.0
    a4_height = 842.0
    doc = fitz.open()
    for img_data in image_pages:
        is_jpeg = img_data[:3] == b"\xff\xd8\xff"
        src_doc = fitz.open("png" if not is_jpeg else "jpg", img_data)
        page_rect = src_doc[0].rect
        w, h = page_rect.width, page_rect.height
        page = doc.new_page(width=a4_width, height=a4_height)
        scale = min(a4_width / w, a4_height / h)
        target_w = w * scale
        target_h = h * scale
        left = (a4_width - target_w) / 2
        top = (a4_height - target_h) / 2
        if is_jpeg:
            page.insert_image(
                fitz.Rect(left, top, left + target_w, top + target_h),
                stream=img_data,
            )
        else:
            page.insert_image(
                fitz.Rect(left, top, left + target_w, top + target_h),
                pixmap=src_doc[0].get_pixmap(),
            )
        src_doc.close()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    doc.close()
    return output_path


class ExportService:
    def export_midi(self, score: JianpuScore, output_path: Path) -> Path:
        return self.export_midi_scores([score], output_path)

    def export_midi_scores(
        self,
        scores: list[JianpuScore],
        output_path: Path,
    ) -> Path:
        rendered_scores = scores or [JianpuScore()]
        for score in rendered_scores:
            for measure in score.measures:
                for event in measure.events:
                    for pitch in event.pitches:
                        _pitch_to_midi(
                            pitch,
                            getattr(measure, "target_key", score.target_key),
                        )

        mid = mido.MidiFile(ticks_per_beat=_TICKS_PER_BEAT)
        for index, score in enumerate(rendered_scores):
            track = mido.MidiTrack()
            mid.tracks.append(track)
            track_name = score.part_name or f"Part {index + 1}"
            try:
                track_name.encode("latin-1")
            except UnicodeEncodeError:
                track_name = f"Part {index + 1}"
            track.append(
                mido.MetaMessage(
                    "track_name",
                    name=track_name,
                    time=0,
                )
            )
            tempo = mido.bpm2tempo(MIDI_DEFAULT_BPM)
            track.append(mido.MetaMessage("set_tempo", tempo=tempo, time=0))

            for measure in score.measures:
                key = getattr(measure, "target_key", score.target_key)
                beat_type = getattr(measure, "beat_type", score.beat_type)
                for event in measure.events:
                    if event.kind == "rest":
                        ticks = _duration_to_ticks(event.duration, beat_type)
                        track.append(
                            mido.Message("note_off", note=0, velocity=0, time=ticks)
                        )
                        continue
                    if not event.pitches:
                        continue

                    ticks = _duration_to_ticks(event.duration, beat_type)
                    for pitch in event.pitches:
                        midi_note = max(0, min(127, _pitch_to_midi(pitch, key)))
                        track.append(
                            mido.Message(
                                "note_on",
                                note=midi_note,
                                velocity=MIDI_DEFAULT_VELOCITY,
                                time=0,
                            )
                        )
                    for pitch_index, pitch in enumerate(event.pitches):
                        midi_note = max(0, min(127, _pitch_to_midi(pitch, key)))
                        track.append(
                            mido.Message(
                                "note_off",
                                note=midi_note,
                                velocity=0,
                                time=ticks if pitch_index == 0 else 0,
                            )
                        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        mid.save(str(output_path))
        return output_path

    def export_musicxml(
        self,
        score: JianpuScore,
        output_path: Path,
        *,
        title: str | None = None,
    ) -> Path:
        return self.export_musicxml_scores(
            [score],
            output_path,
            title=title or score.title,
        )

    def export_musicxml_scores(
        self,
        scores: list[JianpuScore],
        output_path: Path,
        *,
        title: str | None = None,
    ) -> Path:
        first_score = scores[0] if scores else JianpuScore()
        xml_text = scores_to_musicxml(
            scores,
            title=title or first_score.title,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(xml_text, encoding="utf-8")
        return output_path
