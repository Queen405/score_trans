from pathlib import Path

from ..domain.models import JianpuScore
from ..services.ocr_provider import OCRProvider
from ..services.render_service import RenderService
from .convert_to_jianpu import ConvertMusicXmlToJianpuUseCase


class RenderMusicXmlJianpuUseCase:
    def __init__(
        self,
        converter: ConvertMusicXmlToJianpuUseCase | None = None,
        render_service: RenderService | None = None,
    ) -> None:
        self.converter = converter or ConvertMusicXmlToJianpuUseCase()
        self.render_service = render_service or RenderService()

    def execute(
        self,
        musicxml_path: str | Path,
        output_path: str | Path,
        *,
        target_key: str = "C",
        start_measure_number: int | None = None,
        title: str | None = None,
        image_path: str | Path | None = None,
        ocr_provider: OCRProvider | None = None,
    ) -> Path:
        score = self.build_score(
            musicxml_path,
            target_key=target_key,
            start_measure_number=start_measure_number,
            title=title,
            image_path=image_path,
            ocr_provider=ocr_provider,
        )
        return self.render_service.render_score_svg(score, output_path, title=title or score.title)

    def execute_page(
        self,
        musicxml_path: str | Path,
        output_path: str | Path,
        *,
        page_width: float,
        page_height: float,
        target_key: str = "C",
        start_measure_number: int | None = None,
        title: str | None = None,
        image_path: str | Path | None = None,
        ocr_provider: OCRProvider | None = None,
    ) -> Path:
        score = self.build_score(
            musicxml_path,
            target_key=target_key,
            start_measure_number=start_measure_number,
            title=title,
            image_path=image_path,
            ocr_provider=ocr_provider,
        )
        return self.render_service.render_score_page_svg(
            score,
            output_path,
            page_width=page_width,
            page_height=page_height,
            title=title or score.title,
        )

    def build_score(
        self,
        musicxml_path: str | Path,
        *,
        target_key: str = "C",
        start_measure_number: int | None = None,
        title: str | None = None,
        image_path: str | Path | None = None,
        ocr_provider: OCRProvider | None = None,
    ) -> JianpuScore:
        score = self.converter.build_score(
            musicxml_path,
            target_key=target_key,
            start_measure_number=start_measure_number,
            image_path=image_path,
            ocr_provider=ocr_provider,
        )
        if title:
            score.title = title
        return score


class RenderJianpuTextUseCase:
    def __init__(self, render_service: RenderService | None = None) -> None:
        self.render_service = render_service or RenderService()

    def execute(self, input_path: str | Path, output_path: str | Path, *, title: str = "简谱") -> Path:
        return self.render_service.render_text_svg(input_path, output_path, title=title)
