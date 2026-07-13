from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from typing import Literal

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


def _resolve_bpm(score: JianpuScore, midi_tempo: int | Literal["auto"]) -> int:
    if midi_tempo != "auto":
        return midi_tempo
    if score.tempo and score.tempo > 0:
        return score.tempo
    return MIDI_DEFAULT_BPM


def _midi_time_signature_denominator(beat_type: int) -> int:
    """MIDI time_signature 的 denominator 必须是 2 的幂（1,2,4,8,16,32）。

    简谱的 beat_type 通常是 2/4/8/16，直接用；非标准值回退到最近的 2 的幂。
    """
    for power in (1, 2, 4, 8, 16, 32):
        if beat_type == power:
            return power
    for power in (1, 2, 4, 8, 16, 32):
        if beat_type <= power:
            return power
    return 32


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


def svg_pages_to_pdf(svg_pages: list[bytes], output_path: Path) -> Path:
    if not svg_pages:
        raise ValueError("至少需要一个 SVG 页面")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    target = fitz.open()
    try:
        for svg_data in svg_pages:
            source = fitz.open("svg", svg_data)
            try:
                pdf_data = source.convert_to_pdf()
            finally:
                source.close()
            page_doc = fitz.open("pdf", pdf_data)
            try:
                target.insert_pdf(page_doc)
            finally:
                page_doc.close()
        target.save(str(output_path))
    finally:
        target.close()
    return output_path


def svg_page_to_image(
    svg_data: bytes,
    output_path: Path,
    *,
    dpi: int = 300,
    image_format: Literal["png", "jpeg"] = "png",
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    source = fitz.open("svg", svg_data)
    try:
        page = source[0]
        pixmap = page.get_pixmap(
            matrix=fitz.Matrix(dpi / 96.0, dpi / 96.0), alpha=False
        )
        pixmap.save(str(output_path), output="jpg" if image_format == "jpeg" else "png")
    finally:
        source.close()
    return output_path


class ExportService:
    def export_midi(self, score: JianpuScore, output_path: Path) -> Path:
        return self.export_midi_scores([score], output_path)

    @staticmethod
    def _merge_scores_by_part(scores: list[JianpuScore]) -> list[JianpuScore]:
        """Merge parts that span multiple pages into one track per instrument.

        Within each page, parts are numbered 1, 2, 3, ... Parts with the same
        position across pages belong to the same instrument; their measures
        are concatenated to form a single continuous track.
        """
        grouped: dict[int, list[JianpuScore]] = {}
        current_page: int = -1
        part_in_page = 0
        for score in scores:
            if score.page_index != current_page:
                current_page = score.page_index
                part_in_page = 0
            grouped.setdefault(part_in_page, []).append(score)
            part_in_page += 1

        merged: list[JianpuScore] = []
        for part_pos in sorted(grouped.keys()):
            group = grouped[part_pos]
            base = group[0]
            for extra in group[1:]:
                base.measures.extend(extra.measures)
            merged.append(base)
        return merged

    def export_midi_scores(
        self,
        scores: list[JianpuScore],
        output_path: Path,
        *,
        midi_tempo: int | Literal["auto"] = "auto",
    ) -> Path:
        rendered_scores = (
            self._merge_scores_by_part(scores) if scores else [JianpuScore()]
        )
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
            # set_tempo 仅写在 track 0（MIDI 规范要求单一 tempo map）
            if index == 0:
                bpm = _resolve_bpm(score, midi_tempo)
                track.append(
                    mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm), time=0)
                )
                track.append(
                    mido.MetaMessage(
                        "time_signature",
                        numerator=score.beats,
                        denominator=_midi_time_signature_denominator(score.beat_type),
                        clocks_per_click=24,
                        notated_32nd_notes_per_beat=8,
                        time=0,
                    )
                )

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
