from pathlib import Path

from ...models.score import JianpuScore
from .rendering import (
    render_jianpu_file_to_svg,
    render_jianpu_page_file_to_svg,
    render_score_file_to_svg,
    render_score_page_file_to_svg,
)


class RenderService:
    def render_score_svg(self, score: JianpuScore, output_path: str | Path, title: str | None = None) -> Path:
        return render_score_file_to_svg(score, Path(output_path), title=title)

    def render_score_page_svg(
        self,
        score: JianpuScore,
        output_path: str | Path,
        *,
        page_width: float,
        page_height: float,
        title: str | None = None,
    ) -> Path:
        return render_score_page_file_to_svg(
            score,
            Path(output_path),
            page_width=page_width,
            page_height=page_height,
            title=title,
        )

    def render_text_svg(self, input_path: str | Path, output_path: str | Path, title: str = "简谱") -> Path:
        return render_jianpu_file_to_svg(Path(input_path), Path(output_path), title=title)

    def render_text_page_svg(
        self,
        input_path: str | Path,
        output_path: str | Path,
        *,
        page_width: float,
        page_height: float,
        title: str = "简谱",
        text_blocks=None,
    ) -> Path:
        return render_jianpu_page_file_to_svg(
            Path(input_path),
            Path(output_path),
            page_width=page_width,
            page_height=page_height,
            title=title,
            text_blocks=text_blocks,
        )
