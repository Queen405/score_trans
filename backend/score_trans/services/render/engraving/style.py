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
    margin_bottom: float = 48.0
    # Reserved footer band below the music systems (page number plus clearance).
    footer_reserved: float = 28.0
    # Small tolerance for rounding and dense-system packing at the page edge.
    pagination_bottom_allowance: float = 10.0
    title_size: float = 50.0
    meta_size: float = 20.0
    part_name_size: float = 18.0
    note_size: float = 30.0
    accidental_size: float = 20.0
    lyric_size: float = 18.0
    annotation_size: float = 15.0
    measure_number_size: float = 15.0
    ending_clearance: float = 6.0
    ending_label_gap: float = 3.0
    ending_hook_depth: float = 7.0
    base_staff_height: float = 92.0
    part_gap: float = 24.0
    # 声线最小基线距离及实际符号边界之间的最小留白。
    voice_row_gap: float = 32.0
    voice_clearance: float = 18.0
    system_gap: float = 12.0
    title_block_height: float = 96.0
    minimum_measure_width: float = 150.0
    minimum_event_gap: float = 28.0
    short_note_gap_scale: float = 1.0
    spacing_increment: float = 8.0
    tuplet_boundary_gap: float = 2.0
    # Optical beat separation is elastic; regular subdivisions stay uniform
    # and communicate grouping through rhythm-line breaks.
    beat_boundary_gap: float = 13.0
    beat_boundary_ratio: float = 0.28
    barline_gutter: float = 20.0
    event_clearance: float = 6.0
    accidental_clearance: float = 1.0
    mark_clearance: float = 6.0
    mark_stack_gap: float = 4.0
    chord_gap: float = 25.0
    # Independent engraving profile for stacked chord tones. Commercial
    # Jianpu editors use a compressed variant of the regular digit glyph.
    chord_scale_x: float = 0.90
    chord_scale_y: float = 0.68
    chord_layer_gap: float = 5.0
    chord_octave_dot_scale: float = 0.72
    chord_rhythm_scale: float = 0.82
    staccato_radius: float = 2.4
    octave_dot_radius: float = 2.25
    rhythm_dot_radius: float = 2.1
    rhythm_dot_step: float = 7.0
    duration_dot_clearance: float = 3.0
    dynamic_clearance: float = 6.0
    dynamic_baseline_floor: float = 30.0
    lyric_clearance: float = 6.0
    event_baseline: float = 43.0
    text_lane_clearance: float = 18.0
    text_lane_gap: float = 8.0
    text_lyric_clearance: float = 8.0
    continuation_header_height: float = 18.0
    system_top_reserve: float = 24.0
    header_system_gap: float = 36.0
    system_bottom_reserve: float = 18.0
    rhythm_line_side_extent: float = 12.0
    rhythm_line_gap: float = 12.5
    rhythm_line_stroke_width: float = 1.8
    duration_mark_offset: float = 17.0
    # Smaller overhang for per-beat segments when beams break at beat
    # boundaries, so adjacent beat groups keep a clearly visible gap.
    rhythm_line_break_segment_extent: float = 6.0
    rhythm_line_level_step: float = 6.0
    beam_hook_length: float = 18.0
    # When true, rhythm/beam lines break at beat boundaries so each beat keeps
    # its own continuous segment with a gap between beats (one line per beat).
    break_beams_at_beat: bool = True
    # 0 selects automatic breaking; 3/4/5 share aligned document columns.
    measures_per_system: int = 0
    spanner_endpoint_offset: float = 10.0
    slide_endpoint_offset: float = 13.0
    slur_height: float = 18.0
    tie_height: float = 9.0
    spanner_base_clearance: float = 5.0
    tie_below_clearance: float = 5.0
    tuplet_bracket_offset: float = 12.0
    tuplet_arc_height: float = 7.0
    tuplet_arc_extend: float = 4.0
    tuplet_number_gap: float = 4.0
    tuplet_stack_gap: float = 16.0
    extension_line_step: float = 18.0
    extension_line_length: float = 11.0
    last_line_fill_threshold: float = 0.72
    max_system_overflow_ratio: float = 1.08
    slur_break_penalty: float = 120.0
    tie_break_penalty: float = 100.0
    lyric_break_penalty: float = 90.0
    singleton_system_penalty: float = 160.0
    footer_clearance: float = 12.0
    stroke_width: float = 1.7
    font_family: str = "ScoreTransNotoSerif"
    music_font_family: str = "ScoreTransBravura"

    @property
    def first_system_header_height(self) -> float:
        return self.title_block_height + self.header_system_gap

    @property
    def continuation_system_header_height(self) -> float:
        return self.continuation_header_height + self.header_system_gap

    @property
    def content_width(self) -> float:
        return self.page_width - self.margin_left - self.margin_right

    @property
    def content_bottom(self) -> float:
        return self.page_height - self.margin_bottom
