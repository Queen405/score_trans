from pathlib import Path

from ..domain.models import JianpuScore
from ..domain.musicxml import musicxml_path_to_score, score_to_jianpu_text
from ..services.ocr_provider import OCRProvider, OpenAICompatibleOCRProvider


class ConvertMusicXmlToJianpuUseCase:
    def execute(
        self,
        musicxml_path: str | Path,
        *,
        target_key: str = "C",
        start_measure_number: int | None = None,
    ) -> str:
        return score_to_jianpu_text(
            self.build_score(
                musicxml_path,
                target_key=target_key,
                start_measure_number=start_measure_number,
            )
        )

    def build_score(
        self,
        musicxml_path: str | Path,
        *,
        target_key: str = "C",
        start_measure_number: int | None = None,
        image_path: str | Path | None = None,
        ocr_provider: OCRProvider | None = None,
    ) -> JianpuScore:
        score = musicxml_path_to_score(
            Path(musicxml_path),
            target_key=target_key,
            start_measure_number=start_measure_number,
        )
        if image_path is not None:
            provider = ocr_provider or OpenAICompatibleOCRProvider()
            blocks = provider.recognize(Path(image_path))
            score.text_blocks.extend(blocks)
            _apply_measure_number_ocr(score, blocks)
        return score


def _apply_measure_number_ocr(score: JianpuScore, blocks) -> None:
    candidates = [
        (index, block, int(block.text.strip()))
        for index, block in enumerate(blocks)
        if block.role == "measure_number" and block.text.strip().isdigit()
    ]
    if not candidates:
        return
    candidates.sort(key=_measure_number_candidate_key)
    start = candidates[0][2]
    for index, measure in enumerate(score.measures):
        display_number = start + index
        measure.display_number = display_number
        for block in measure.text_blocks:
            if block.role == "measure_number":
                block.text = str(display_number)
                block.measure_number = display_number


def _measure_number_candidate_key(candidate) -> tuple[int, float, float, int]:
    index, block, _number = candidate
    if block.bbox is None:
        return (1, 0.0, 0.0, index)
    x1, y1, _x2, _y2 = block.bbox
    return (0, y1, x1, index)
