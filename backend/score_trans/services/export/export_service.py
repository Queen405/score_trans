from __future__ import annotations

import re
import json
from fractions import Fraction
from dataclasses import replace
from pathlib import Path
from typing import Literal

import fitz
import mido

from score_trans.config.settings import (
    MIDI_DEFAULT_VELOCITY,
    MIDI_TICKS_PER_BEAT,
)

from ...domain.playback_timeline import (
    score_parts,
    playback_visits,
    score_onset_groups,
    event_onsets,
    to_tick,
)
from ...domain.constants import KEY_TO_TONIC, MAJOR_SCALE
from ...domain.write.musicxml import scores_to_musicxml
from ...models.playback import PlaybackTextSource
from ...models.score import DEFAULT_TEMPO, JianpuPitch, JianpuScore

_TICKS_PER_BEAT = MIDI_TICKS_PER_BEAT


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
    return max(1, to_tick(duration, _TICKS_PER_BEAT))


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


_HIDDEN_TEXT_RE = re.compile(
    rb'<text\b[^>]*\bopacity="0+(?:\.0+)?"[^>]*(?:/>|>.*?</text>)',
    re.DOTALL,
)


def _strip_invisible_text(svg_data: bytes) -> bytes:
    """剔除 opacity=0 的辅助文本节点；MuPDF 忽略 opacity，会把它们画进 PDF/PNG。"""
    try:
        return _HIDDEN_TEXT_RE.sub(b"", svg_data)
    except Exception:
        return svg_data


def svg_pages_to_pdf(svg_pages: list[bytes], output_path: Path) -> Path:
    if not svg_pages:
        raise ValueError("至少需要一个 SVG 页面")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    target = fitz.open()
    try:
        for svg_data in svg_pages:
            source = fitz.open("svg", _strip_invisible_text(svg_data))
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
    source = fitz.open("svg", _strip_invisible_text(svg_data))
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
        return [
            replace(part[0], measures=[m for score in part for m in score.measures])
            for part in score_parts(scores)
        ]

    def export_midi_scores(
        self,
        scores: list[JianpuScore],
        output_path: Path,
        *,
        text_source: PlaybackTextSource | None = None,
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

        measure_count = max((len(s.measures) for s in rendered_scores), default=0)
        cells = [
            [s.measures[i] if i < len(s.measures) else None for s in rendered_scores]
            for i in range(measure_count)
        ]
        visits = playback_visits(cells)
        groups = score_onset_groups(cells)
        source_tempos: list[int] = []
        tempo = rendered_scores[0].tempo or DEFAULT_TEMPO
        for cell in cells:
            if cell[0] is not None:
                tempo = cell[0].tempo or tempo
            source_tempos.append(tempo)
        marker_events: list[tuple[int, dict[str, object]]] = [
            (
                0,
                {
                    "kind": "document",
                    "version": 1,
                    "source_kind": "text" if text_source is not None else "score",
                    "text_hash": text_source.text_hash
                    if text_source is not None
                    else None,
                },
            )
        ]
        for visit in visits:
            start_tick = to_tick(visit.performance_start, _TICKS_PER_BEAT)
            end_tick = to_tick(
                visit.performance_start + visit.duration, _TICKS_PER_BEAT
            )
            if end_tick <= start_tick:
                continue
            marker_events.append(
                (
                    start_tick,
                    {
                        "kind": "measure",
                        "score_tick": to_tick(visit.score_start, _TICKS_PER_BEAT),
                        "end_tick": end_tick,
                        "source_index": visit.source_index,
                    },
                )
            )
            ranges: dict[Fraction, set[tuple[int, int]]] = {}
            for measure in cells[visit.source_index]:
                if measure is None:
                    continue
                for onset, event in event_onsets(measure):
                    if event.kind != "note" or not event.pitches:
                        continue
                    bucket = ranges.setdefault(onset, set())
                    if (
                        text_source is not None
                        and id(event) in text_source.event_ranges
                    ):
                        bucket.add(text_source.event_ranges[id(event)])
            for onset, source_ranges in sorted(ranges.items()):
                marker_events.append(
                    (
                        to_tick(visit.performance_start + onset, _TICKS_PER_BEAT),
                        {
                            "kind": "onset",
                            "score_tick": to_tick(
                                visit.score_start + onset, _TICKS_PER_BEAT
                            ),
                            "score_group": groups[visit.score_start + onset],
                            "ranges": [
                                {"start": start, "end": end}
                                for start, end in sorted(source_ranges)
                            ],
                        },
                    )
                )
        mid = mido.MidiFile(ticks_per_beat=_TICKS_PER_BEAT)
        for part_index, score in enumerate(rendered_scores):
            track = mido.MidiTrack()
            mid.tracks.append(track)
            track_name = score.part_name or f"Part {part_index + 1}"
            try:
                track_name.encode("latin-1")
            except UnicodeEncodeError:
                track_name = f"Part {part_index + 1}"
            track.append(mido.MetaMessage("track_name", name=track_name, time=0))
            messages: list[tuple[int, int, mido.Message | mido.MetaMessage]] = []
            if part_index == 0:
                messages.extend(
                    (
                        tick,
                        0,
                        mido.MetaMessage(
                            "marker",
                            text="score-trans-playback:"
                            + json.dumps(
                                data, ensure_ascii=True, separators=(",", ":")
                            ),
                        ),
                    )
                    for tick, data in marker_events
                )
            current_bpm = score.tempo or DEFAULT_TEMPO
            if part_index == 0:
                messages.append(
                    (
                        0,
                        0,
                        mido.MetaMessage(
                            "set_tempo", tempo=mido.bpm2tempo(current_bpm)
                        ),
                    )
                )
                messages.append(
                    (
                        0,
                        0,
                        mido.MetaMessage(
                            "time_signature",
                            numerator=score.beats,
                            denominator=_midi_time_signature_denominator(
                                score.beat_type
                            ),
                            clocks_per_click=24,
                            notated_32nd_notes_per_beat=8,
                        ),
                    )
                )
            for visit in visits:
                measure = cells[visit.source_index][part_index]
                if measure is None:
                    continue
                bpm = source_tempos[visit.source_index]
                if part_index == 0 and bpm != current_bpm:
                    messages.append(
                        (
                            to_tick(visit.performance_start, _TICKS_PER_BEAT),
                            0,
                            mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm)),
                        )
                    )
                current_bpm = bpm
                for onset, event in event_onsets(measure):
                    if event.kind != "note" or not event.pitches:
                        continue
                    start = to_tick(visit.performance_start + onset, _TICKS_PER_BEAT)
                    end = max(
                        start + 1,
                        to_tick(
                            visit.performance_start + onset + event.duration,
                            _TICKS_PER_BEAT,
                        ),
                    )
                    for pitch in event.pitches:
                        note = max(
                            0, min(127, _pitch_to_midi(pitch, measure.target_key))
                        )
                        messages.append(
                            (
                                start,
                                2,
                                mido.Message(
                                    "note_on", note=note, velocity=MIDI_DEFAULT_VELOCITY
                                ),
                            )
                        )
                        messages.append(
                            (end, 1, mido.Message("note_off", note=note, velocity=0))
                        )
            cursor = 0
            for tick, _, message in sorted(
                messages, key=lambda item: (item[0], item[1])
            ):
                track.append(message.copy(time=tick - cursor))
                cursor = tick
            track.append(
                mido.MetaMessage(
                    "end_of_track",
                    time=max(
                        0,
                        (
                            to_tick(
                                visits[-1].performance_start + visits[-1].duration,
                                _TICKS_PER_BEAT,
                            )
                            if visits
                            else 0
                        )
                        - cursor,
                    ),
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
