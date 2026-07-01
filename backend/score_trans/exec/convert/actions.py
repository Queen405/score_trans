from __future__ import annotations

import uuid
from pathlib import Path


from ...domain.jianpu import jianpu_file_to_musicxml, jianpu_to_musicxml
from ...domain.musicxml import (
    musicxml_path_to_score,
    score_to_jianpu_document,
    score_to_jianpu_text,
)
from ...models.common.types import AccidentalMode, InstrumentProfile
from ...models.convert.schemas import (
    JianpuToMusicXmlRequest,
    JianpuToMusicXmlResponse,
    MusicXmlToJianpuRequest,
    MusicXmlToJianpuResponse,
)
from ...models.score import JianpuScore
from ...models.provenance.entities import JianpuDocument
from ...services.files.file_service import FileService
from ...services.files.upload_service import UploadService
from ...services.ocr.core import OCRProvider
from ...services.ocr.providers import create_configured_ocr_provider


class MusicXmlToJianpuAction:
    def execute(
        self,
        musicxml_path: str | Path,
        *,
        target_key: str = "C",
        accidental_mode: AccidentalMode = "auto",
        instrument_profile: InstrumentProfile | None = None,
        start_measure_number: int | None = None,
        image_path: str | Path | None = None,
        ocr_provider: OCRProvider | None = None,
    ) -> str:
        return score_to_jianpu_text(
            self.build_score(
                musicxml_path,
                target_key=target_key,
                instrument_profile=instrument_profile,
                start_measure_number=start_measure_number,
                image_path=image_path,
                ocr_provider=ocr_provider,
            ),
            accidental_mode=accidental_mode,
        )

    def build_score(
        self,
        musicxml_path: str | Path,
        *,
        target_key: str = "C",
        instrument_profile: InstrumentProfile | None = None,
        start_measure_number: int | None = None,
        image_path: str | Path | None = None,
        ocr_provider: OCRProvider | None = None,
    ) -> JianpuScore:
        score = musicxml_path_to_score(
            Path(musicxml_path),
            target_key=target_key,
            start_measure_number=start_measure_number,
            instrument_profile=instrument_profile,
        )
        if image_path is not None:
            provider = ocr_provider or create_configured_ocr_provider()
            blocks = provider.recognize(Path(image_path))
            score.text_blocks.extend(blocks)
            _apply_measure_number_ocr(
                score, blocks, start_measure_number=start_measure_number
            )
        return score

    def execute_document(
        self,
        musicxml_path: str | Path,
        *,
        target_key: str = "C",
        accidental_mode: AccidentalMode = "auto",
        instrument_profile: InstrumentProfile | None = None,
        start_measure_number: int | None = None,
        image_path: str | Path | None = None,
        ocr_provider: OCRProvider | None = None,
    ) -> JianpuDocument:
        return score_to_jianpu_document(
            self.build_score(
                musicxml_path,
                target_key=target_key,
                instrument_profile=instrument_profile,
                start_measure_number=start_measure_number,
                image_path=image_path,
                ocr_provider=ocr_provider,
            ),
            accidental_mode=accidental_mode,
        )


class JianpuToMusicXmlAction:
    def execute_text(self, jianpu_text: str, *, title: str = "Jianpu Import") -> str:
        return jianpu_to_musicxml(jianpu_text, title=title)

    def execute_file(
        self, input_path: str | Path, *, title: str = "Jianpu Import"
    ) -> str:
        return jianpu_file_to_musicxml(Path(input_path), title=title)


class ConvertActions:
    def __init__(
        self,
        uploads: UploadService | None = None,
        file_service: FileService | None = None,
        musicxml_to_jianpu: MusicXmlToJianpuAction | None = None,
        jianpu_to_musicxml: JianpuToMusicXmlAction | None = None,
    ) -> None:
        self.uploads = uploads or UploadService()
        self.file_service = file_service or FileService()
        self.musicxml_to_jianpu = musicxml_to_jianpu or MusicXmlToJianpuAction()
        self.jianpu_to_musicxml = jianpu_to_musicxml or JianpuToMusicXmlAction()

    def musicxml_to_jianpu_response(
        self, req: MusicXmlToJianpuRequest
    ) -> MusicXmlToJianpuResponse:
        path = self.uploads.get_path(req.musicxml_file_id)
        if not path or not path.exists():
            raise FileNotFoundError(f"文件不存在：{req.musicxml_file_id}")

        image_path = None
        if req.page_image_file_id:
            image_path = self.uploads.get_path(req.page_image_file_id)
            if not image_path or not image_path.exists():
                raise FileNotFoundError(f"页面图片不存在：{req.page_image_file_id}")

        document = self.musicxml_to_jianpu.execute_document(
            path,
            target_key=req.target_key,
            accidental_mode=req.accidental_mode,
            instrument_profile=req.instrument_profile,
            start_measure_number=req.start_measure_number,
            image_path=image_path,
        )
        return MusicXmlToJianpuResponse(
            jianpu_text=document.text,
            text_anchors=document.anchors,
            text_hash=document.text_hash,
        )

    def jianpu_to_musicxml_response(
        self, req: JianpuToMusicXmlRequest
    ) -> JianpuToMusicXmlResponse:
        if req.jianpu_text:
            xml_text = self.jianpu_to_musicxml.execute_text(
                req.jianpu_text, title=req.title
            )
        elif req.jianpu_file_id:
            path = self.uploads.get_path(req.jianpu_file_id)
            if not path or not path.exists():
                raise FileNotFoundError(f"文件不存在：{req.jianpu_file_id}")
            xml_text = self.jianpu_to_musicxml.execute_file(path, title=req.title)
        else:
            raise ValueError("必须提供 jianpu_text 或 jianpu_file_id")

        out_path = self.uploads.base_dir / f"{uuid.uuid4().hex[:12]}.musicxml"
        self.file_service.write_text(out_path, xml_text)
        musicxml_id = self.uploads.register(out_path)
        return JianpuToMusicXmlResponse(
            musicxml_text=xml_text, musicxml_file_id=musicxml_id
        )


def _apply_measure_number_ocr(
    score: JianpuScore, blocks, *, start_measure_number: int | None = None
) -> None:
    candidates = [
        (index, block, int(block.text.strip()))
        for index, block in enumerate(blocks)
        if block.role == "measure_number" and block.text.strip().isdigit()
    ]
    if not candidates and start_measure_number is None:
        return
    if start_measure_number is not None:
        start = start_measure_number
    else:
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
