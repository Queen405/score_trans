from dataclasses import dataclass
from pathlib import Path

from ...models.score import OCRTextBlock
from .provider import OCRProvider, OpenAICompatibleOCRProvider


@dataclass(slots=True)
class OCRTextLayer:
    image_path: Path
    blocks: list[OCRTextBlock]

    @property
    def plain_text(self) -> str:
        return "\n".join(block.text for block in self.blocks if block.text)


class OCRService:
    def __init__(self, provider: OCRProvider | None = None) -> None:
        self.provider = provider or OpenAICompatibleOCRProvider()

    def recognize_text_blocks(self, image_path: str | Path) -> list[OCRTextBlock]:
        return self.provider.recognize(Path(image_path))

    def extract_text_layer(self, image_path: str | Path) -> OCRTextLayer:
        path = Path(image_path)
        return OCRTextLayer(image_path=path, blocks=self.recognize_text_blocks(path))
