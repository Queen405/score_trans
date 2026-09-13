from __future__ import annotations

import uuid
from pathlib import Path

from ...domain.jianpu import jianpu_file_to_musicxml, jianpu_to_musicxml
from ...domain.musicxml import (
    musicxml_path_to_scores,
)
from ...domain.write.jianpu_text import scores_to_jianpu_document
from ...models.common.types import (
    IMAGE_SUFFIXES,
    AccidentalMode,
    InstrumentProfile,
    PolyphonyMode,
)
from ...models.convert.schemas import (
    JianpuToMusicXmlRequest,
    JianpuToMusicXmlResponse,
    MusicXmlToJianpuRequest,
    MusicXmlToJianpuResponse,
)
from ...models.provenance.entities import JianpuDocument
from ...models.score import JianpuScore
from ...services.files.file_service import FileService
from ...services.files.upload_service import UploadService
from ...services.ocr.core import OCRProvider
from ...services.ocr.providers import create_configured_ocr_provider
from ...services.settings.settings_service import SettingsService


class MusicXmlToJianpuAction:
    def execute(
        self,
        musicxml_path: str | Path,
        *,
        target_key: str = "C",
        accidental_mode: AccidentalMode = "auto",
        polyphony_mode: PolyphonyMode = "auto",
        instrument_profile: InstrumentProfile | None = None,
        image_path: str | Path | None = None,
        ocr_provider: OCRProvider | None = None,
    ) -> str:
        return scores_to_jianpu_document(
            self.build_scores(
                musicxml_path,
                target_key=target_key,
                instrument_profile=instrument_profile,
                image_path=image_path,
                ocr_provider=ocr_provider,
            ),
            accidental_mode=accidental_mode,
            polyphony_mode=polyphony_mode,
        ).text

    def build_scores(
        self,
        musicxml_path: str | Path,
        *,
        target_key: str = "C",
        instrument_profile: InstrumentProfile | None = None,
        image_path: str | Path | None = None,
        ocr_provider: OCRProvider | None = None,
    ) -> list[JianpuScore]:
        scores = musicxml_path_to_scores(
            Path(musicxml_path),
            target_key=target_key,
            instrument_profile=instrument_profile,
        )
        if image_path is not None:
            # Text extraction is delegated to the configured Python OCR provider.
            provider = ocr_provider or create_configured_ocr_provider()
            blocks = provider.recognize(Path(image_path))
            for score in scores:
                score.text_blocks.extend(blocks)
        return scores

    def execute_document(
        self,
        musicxml_path: str | Path,
        *,
        target_key: str = "C",
        accidental_mode: AccidentalMode = "auto",
        polyphony_mode: PolyphonyMode = "auto",
        instrument_profile: InstrumentProfile | None = None,
        image_path: str | Path | None = None,
        ocr_provider: OCRProvider | None = None,
    ) -> JianpuDocument:
        return scores_to_jianpu_document(
            self.build_scores(
                musicxml_path,
                target_key=target_key,
                instrument_profile=instrument_profile,
                image_path=image_path,
                ocr_provider=ocr_provider,
            ),
            accidental_mode=accidental_mode,
            polyphony_mode=polyphony_mode,
        )


class JianpuToMusicXmlAction:
    def execute_text(self, jianpu_text: str, *, title: str | None = None) -> str:
        return jianpu_to_musicxml(jianpu_text, title=title)

    def execute_file(self, input_path: str | Path, *, title: str | None = None) -> str:
        return jianpu_file_to_musicxml(Path(input_path), title=title)


class ConvertActions:
    def __init__(
        self,
        uploads: UploadService | None = None,
        file_service: FileService | None = None,
        musicxml_to_jianpu: MusicXmlToJianpuAction | None = None,
        jianpu_to_musicxml: JianpuToMusicXmlAction | None = None,
        settings: SettingsService | None = None,
    ) -> None:
        self.uploads = uploads or UploadService()
        self.file_service = file_service or FileService()
        self.musicxml_to_jianpu = musicxml_to_jianpu or MusicXmlToJianpuAction()
        self.jianpu_to_musicxml = jianpu_to_musicxml or JianpuToMusicXmlAction()
        self.settings = settings or SettingsService()

    def musicxml_to_jianpu_response(
        self, req: MusicXmlToJianpuRequest
    ) -> MusicXmlToJianpuResponse:
        path = self.uploads.get_path(req.musicxml_file_id)
        if not path or not path.exists():
            raise FileNotFoundError(f"文件不存在：{req.musicxml_file_id}")

        image_path = None
        if req.page_image_file_id and self.settings.get_bool("enable_omr_ocr", False):
            image_path = self.uploads.get_path(req.page_image_file_id)
            if not image_path or not image_path.exists():
                raise FileNotFoundError(f"页面图片不存在：{req.page_image_file_id}")
            if image_path.suffix.lower() not in IMAGE_SUFFIXES:
                image_path = None

        document = self.musicxml_to_jianpu.execute_document(
            path,
            target_key=req.target_key,
            accidental_mode=req.accidental_mode,
            polyphony_mode=req.polyphony_mode,
            instrument_profile=req.instrument_profile,
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
