from pathlib import Path

from ...models.common.types import MeasureNumberMode
from ...models.score import JianpuScore
from .main import (
    RenderedA4FilePage,
    RenderedA4Page,
    render_jianpu_file_to_svg,
    render_jianpu_page_file_to_svg,
    render_score_a4_pages_to_files,
    render_score_file_to_svg,
    render_score_page_file_to_svg,
    render_scores_a4_page_results_to_files,
    render_scores_a4_pages,
    render_scores_a4_pages_to_files,
)
from .options import A4LayoutOptions, RenderOptions


def _layout(
    content_scale_percent: int,
    system_gap_percent: int,
    short_note_gap_percent: int,
    beat_gap_percent: int,
) -> A4LayoutOptions:
    return A4LayoutOptions(
        content_scale_percent=content_scale_percent,
        system_gap_percent=system_gap_percent,
        short_note_gap_percent=short_note_gap_percent,
        beat_gap_percent=beat_gap_percent,
    )


class PublicationRenderService:
    def render_score_svg(
        self,
        score: JianpuScore,
        output_path: str | Path,
        title: str | None = None,
        show_measure_numbers: bool | None = None,
        measure_number_mode: MeasureNumberMode | None = None,
        initial_measure_number: int | None = 1,
    ) -> Path:
        return render_score_file_to_svg(
            score,
            Path(output_path),
            title=title,
            show_measure_numbers=show_measure_numbers,
            measure_number_mode=measure_number_mode,
            initial_measure_number=initial_measure_number,
        )

    def render_score_page_svg(
        self,
        score: JianpuScore,
        output_path: str | Path,
        *,
        page_width: float,
        page_height: float,
        title: str | None = None,
        show_measure_numbers: bool | None = None,
        measure_number_mode: MeasureNumberMode | None = None,
        initial_measure_number: int | None = 1,
    ) -> Path:
        return render_score_page_file_to_svg(
            score,
            Path(output_path),
            page_width=page_width,
            page_height=page_height,
            title=title,
            show_measure_numbers=show_measure_numbers,
            measure_number_mode=measure_number_mode,
            initial_measure_number=initial_measure_number,
        )

    def render_score_a4_svg_pages(
        self,
        score: JianpuScore,
        output_path: str | Path,
        title: str | None = None,
        show_measure_numbers: bool | None = None,
        measure_number_mode: MeasureNumberMode | None = None,
        initial_measure_number: int | None = 1,
        content_scale_percent: int = 67,
        system_gap_percent: int = 92,
        short_note_gap_percent: int = 90,
        beat_gap_percent: int = 100,
    ) -> list[RenderedA4FilePage]:
        return render_score_a4_pages_to_files(
            score,
            Path(output_path),
            title=title,
            show_measure_numbers=show_measure_numbers,
            measure_number_mode=measure_number_mode,
            initial_measure_number=initial_measure_number,
            layout=_layout(
                content_scale_percent,
                system_gap_percent,
                short_note_gap_percent,
                beat_gap_percent,
            ),
        )

    def render_scores_a4_svg_pages(
        self,
        scores: list[JianpuScore],
        output_path: str | Path,
        title: str | None = None,
        show_measure_numbers: bool | None = None,
        measure_number_mode: MeasureNumberMode | None = None,
        initial_measure_number: int | None = 1,
        content_scale_percent: int = 67,
        system_gap_percent: int = 92,
        short_note_gap_percent: int = 90,
        beat_gap_percent: int = 100,
    ) -> list[RenderedA4FilePage]:
        return render_scores_a4_pages_to_files(
            scores,
            Path(output_path),
            title=title,
            show_measure_numbers=show_measure_numbers,
            measure_number_mode=measure_number_mode,
            initial_measure_number=initial_measure_number,
            layout=_layout(
                content_scale_percent,
                system_gap_percent,
                short_note_gap_percent,
                beat_gap_percent,
            ),
        )

    def build_scores_a4_svg_pages(
        self,
        scores: list[JianpuScore],
        title: str | None = None,
        show_measure_numbers: bool | None = None,
        measure_number_mode: MeasureNumberMode | None = None,
        initial_measure_number: int | None = 1,
        content_scale_percent: int = 67,
        system_gap_percent: int = 92,
        short_note_gap_percent: int = 90,
        beat_gap_percent: int = 100,
    ) -> list[RenderedA4Page]:
        mode = measure_number_mode or (
            "none" if show_measure_numbers is False else "all"
        )
        return render_scores_a4_pages(
            scores,
            RenderOptions(
                title=title or (scores[0].title if scores else "简谱"),
                show_measure_numbers=mode != "none",
                measure_number_mode=mode,
                initial_measure_number=initial_measure_number,
            ),
            _layout(
                content_scale_percent,
                system_gap_percent,
                short_note_gap_percent,
                beat_gap_percent,
            ),
        )

    def render_scores_a4_svg_page_results(
        self,
        scores: list[JianpuScore],
        output_path: str | Path,
        title: str | None = None,
        show_measure_numbers: bool | None = None,
        measure_number_mode: MeasureNumberMode | None = None,
        initial_measure_number: int | None = 1,
        content_scale_percent: int = 67,
        system_gap_percent: int = 92,
        short_note_gap_percent: int = 90,
        beat_gap_percent: int = 100,
    ) -> list[RenderedA4FilePage]:
        return render_scores_a4_page_results_to_files(
            scores,
            Path(output_path),
            title=title,
            show_measure_numbers=show_measure_numbers,
            measure_number_mode=measure_number_mode,
            initial_measure_number=initial_measure_number,
            layout=_layout(
                content_scale_percent,
                system_gap_percent,
                short_note_gap_percent,
                beat_gap_percent,
            ),
        )

    def render_text_svg(
        self,
        input_path: str | Path,
        output_path: str | Path,
        title: str = "简谱",
        show_measure_numbers: bool | None = None,
        measure_number_mode: MeasureNumberMode | None = None,
        initial_measure_number: int | None = 1,
    ) -> Path:
        return render_jianpu_file_to_svg(
            Path(input_path),
            Path(output_path),
            title=title,
            show_measure_numbers=show_measure_numbers,
            measure_number_mode=measure_number_mode,
            initial_measure_number=initial_measure_number,
        )

    def render_text_page_svg(
        self,
        input_path: str | Path,
        output_path: str | Path,
        *,
        page_width: float,
        page_height: float,
        title: str = "简谱",
        show_measure_numbers: bool | None = None,
        measure_number_mode: MeasureNumberMode | None = None,
        initial_measure_number: int | None = 1,
    ) -> Path:
        return render_jianpu_page_file_to_svg(
            Path(input_path),
            Path(output_path),
            page_width=page_width,
            page_height=page_height,
            title=title,
            show_measure_numbers=show_measure_numbers,
            measure_number_mode=measure_number_mode,
            initial_measure_number=initial_measure_number,
        )
