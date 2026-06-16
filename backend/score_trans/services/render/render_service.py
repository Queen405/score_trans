from pathlib import Path

from ...models.common.types import MeasureNumberMode
from ...models.score import JianpuScore, TextBlock
from . import (
    RenderedA4FilePage,
    RenderedA4Page,
    render_jianpu_a4_files_to_svgs,
    render_jianpu_file_to_svg,
    render_jianpu_page_file_to_svg,
    render_score_a4_pages_to_files,
    render_score_file_to_svg,
    render_score_page_file_to_svg,
    render_scores_a4_page_results_to_files,
    render_scores_a4_pages,
    render_scores_a4_pages_to_files,
)
from .options import RenderOptions


class RenderService:
    def render_score_svg(
        self,
        score: JianpuScore,
        output_path: str | Path,
        title: str | None = None,
        show_measure_numbers: bool | None = None,
        measure_number_mode: MeasureNumberMode | None = None,
    ) -> Path:
        return render_score_file_to_svg(
            score,
            Path(output_path),
            title=title,
            show_measure_numbers=show_measure_numbers,
            measure_number_mode=measure_number_mode,
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
    ) -> Path:
        return render_score_page_file_to_svg(
            score,
            Path(output_path),
            page_width=page_width,
            page_height=page_height,
            title=title,
            show_measure_numbers=show_measure_numbers,
            measure_number_mode=measure_number_mode,
        )

    def render_score_a4_svg_pages(
        self,
        score: JianpuScore,
        output_path: str | Path,
        title: str | None = None,
        show_measure_numbers: bool | None = None,
        measure_number_mode: MeasureNumberMode | None = None,
    ) -> list[Path]:
        return render_score_a4_pages_to_files(
            score,
            Path(output_path),
            title=title,
            show_measure_numbers=show_measure_numbers,
            measure_number_mode=measure_number_mode,
        )

    def render_scores_a4_svg_pages(
        self,
        scores: list[JianpuScore],
        output_path: str | Path,
        title: str | None = None,
        show_measure_numbers: bool | None = None,
        measure_number_mode: MeasureNumberMode | None = None,
    ) -> list[Path]:
        return render_scores_a4_pages_to_files(
            scores,
            Path(output_path),
            title=title,
            show_measure_numbers=show_measure_numbers,
            measure_number_mode=measure_number_mode,
        )

    def build_scores_a4_svg_pages(
        self,
        scores: list[JianpuScore],
        title: str | None = None,
        show_measure_numbers: bool | None = None,
        measure_number_mode: MeasureNumberMode | None = None,
        *,
        page_text_blocks: dict[int, list[TextBlock]] | None = None,
    ) -> list[RenderedA4Page]:
        mode = measure_number_mode or (
            "none" if show_measure_numbers is False else "all"
        )
        return render_scores_a4_pages(
            scores,
            RenderOptions(
                title=title or "简谱",
                show_measure_numbers=mode != "none",
                measure_number_mode=mode,
            ),
            page_text_blocks=page_text_blocks,
        )

    def render_scores_a4_svg_page_results(
        self,
        scores: list[JianpuScore],
        output_path: str | Path,
        title: str | None = None,
        show_measure_numbers: bool | None = None,
        measure_number_mode: MeasureNumberMode | None = None,
        *,
        page_text_blocks: dict[int, list[TextBlock]] | None = None,
    ) -> list[RenderedA4FilePage]:
        return render_scores_a4_page_results_to_files(
            scores,
            Path(output_path),
            title=title,
            show_measure_numbers=show_measure_numbers,
            measure_number_mode=measure_number_mode,
            page_text_blocks=page_text_blocks,
        )

    def render_text_svg(
        self,
        input_path: str | Path,
        output_path: str | Path,
        title: str = "简谱",
        show_measure_numbers: bool | None = None,
        measure_number_mode: MeasureNumberMode | None = None,
    ) -> Path:
        return render_jianpu_file_to_svg(
            Path(input_path),
            Path(output_path),
            title=title,
            show_measure_numbers=show_measure_numbers,
            measure_number_mode=measure_number_mode,
        )

    def render_text_page_svg(
        self,
        input_path: str | Path,
        output_path: str | Path,
        *,
        page_width: float,
        page_height: float,
        title: str = "简谱",
        text_blocks=None,
        start_measure_number: int | None = None,
        show_measure_numbers: bool | None = None,
        measure_number_mode: MeasureNumberMode | None = None,
    ) -> Path:
        return render_jianpu_page_file_to_svg(
            Path(input_path),
            Path(output_path),
            page_width=page_width,
            page_height=page_height,
            title=title,
            text_blocks=text_blocks,
            start_measure_number=start_measure_number,
            show_measure_numbers=show_measure_numbers,
            measure_number_mode=measure_number_mode,
        )

    def render_texts_a4_svg_pages(
        self,
        input_paths: list[str | Path],
        output_path: str | Path,
        title: str = "简谱",
        show_measure_numbers: bool | None = None,
        measure_number_mode: MeasureNumberMode | None = None,
    ) -> list[Path]:
        return render_jianpu_a4_files_to_svgs(
            [Path(path) for path in input_paths],
            Path(output_path),
            title=title,
            show_measure_numbers=show_measure_numbers,
            measure_number_mode=measure_number_mode,
        )
