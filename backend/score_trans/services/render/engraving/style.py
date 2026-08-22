from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PublicationStyle:
    """Deterministic physical-page style expressed in A4 viewBox units."""

    page_width: float = 1240.0
    page_height: float = 1754.0
    margin_left: float = 82.0
    margin_right: float = 82.0
    margin_top: float = 72.0
    margin_bottom: float = 64.0
    title_size: float = 40.0
    meta_size: float = 20.0
    part_name_size: float = 18.0
    note_size: float = 30.0
    accidental_size: float = 18.0
    lyric_size: float = 18.0
    annotation_size: float = 15.0
    measure_number_size: float = 15.0
    base_staff_height: float = 92.0
    part_gap: float = 34.0
    system_gap: float = 32.0
    title_block_height: float = 132.0
    minimum_measure_width: float = 150.0
    ideal_event_gap: float = 42.0
    minimum_event_gap: float = 28.0
    spacing_increment: float = 8.0
    tuplet_boundary_gap: float = 2.0
    barline_gutter: float = 20.0
    event_clearance: float = 6.0
    accidental_clearance: float = 4.0
    chord_gap: float = 25.0
    staccato_radius: float = 2.4
    octave_dot_radius: float = 2.25
    rhythm_dot_radius: float = 2.1
    rhythm_dot_step: float = 7.0
    duration_dot_clearance: float = 3.0
    dynamic_clearance: float = 6.0
    extension_line_step: float = 18.0
    last_line_fill_threshold: float = 0.72
    stroke_width: float = 1.7
    font_family: str = "ScoreTransNotoSerif"
    music_font_family: str = "ScoreTransBravura"

    @property
    def content_width(self) -> float:
        return self.page_width - self.margin_left - self.margin_right

    @property
    def content_bottom(self) -> float:
        return self.page_height - self.margin_bottom
