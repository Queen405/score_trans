from pathlib import Path

from ..domain.models import JianpuScore
from .rendering import render_jianpu_file_to_svg, render_score_file_to_svg


class RenderService:
    def render_score_svg(self, score: JianpuScore, output_path: str | Path, title: str | None = None) -> Path:
        return render_score_file_to_svg(score, Path(output_path), title=title)

    def render_text_svg(self, input_path: str | Path, output_path: str | Path, title: str = "简谱") -> Path:
        return render_jianpu_file_to_svg(Path(input_path), Path(output_path), title=title)
