from __future__ import annotations

from pathlib import Path

from ....models.common.errors import AITranscriptionError
from ....models.tasks.entities import ProgressCallback, report_progress
from ..core.protocols import VisionJianpuProvider
from ..core.registry import create_provider
from ..core.schemas import AiTranscriptionResult, TranscribedScorePage
from .merging import first_present, merge_page_jianpu_texts
from .normalization import clean_jianpu_text, ensure_jianpu_header
from .preparation import prepare_score_pages
from .validation import validate_jianpu_text


class AiTranscriptionService:
    def __init__(
        self,
        provider: VisionJianpuProvider | str | None = None,
    ) -> None:
        if isinstance(provider, VisionJianpuProvider):
            self.provider = provider
        else:
            self.provider = create_provider(provider)

    def transcribe(
        self,
        input_path: str | Path,
        output_dir: str | Path,
        *,
        target_key: str = "C",
        title: str | None = None,
        render_dpi: int = 220,
        max_pages: int | None = None,
        extra_prompt: str | None = None,
        normalize: bool = True,
        progress_callback: ProgressCallback | None = None,
    ) -> AiTranscriptionResult:
        source = Path(input_path).resolve()
        out_dir = Path(output_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        report_progress(progress_callback, "ai_prepare", 10, "准备乐谱页面")
        prepared_pages = prepare_score_pages(
            source,
            out_dir / "pages",
            dpi=render_dpi,
            max_pages=max_pages,
        )
        if not prepared_pages:
            raise AITranscriptionError(f"No transcribable score pages found in {source}")

        report_progress(progress_callback, "ai_prepare", 20, f"已准备 {len(prepared_pages)} 页")
        pages: list[TranscribedScorePage] = []
        warnings: list[str] = []
        total_pages = len(prepared_pages)
        for index, prepared in enumerate(prepared_pages):
            start_percent = 20 + int(index / total_pages * 60)
            report_progress(
                progress_callback,
                "ai_transcribe",
                start_percent,
                f"AI 转写第 {prepared.page_index + 1} 页",
            )
            result = self.provider.transcribe_page(
                prepared.image_path,
                target_key=target_key,
                title=title,
                page_index=prepared.page_index,
                extra_prompt=extra_prompt,
            )
            page_text = ensure_jianpu_header(
                clean_jianpu_text(result.jianpu_text),
                target_key=result.key or target_key,
                meter=result.meter,
                title=result.title or title,
                tempo=result.tempo,
            )
            normalized_text, validation_errors = validate_jianpu_text(
                page_text,
                title=result.title or title,
                normalize=normalize,
            )
            if validation_errors:
                warnings.extend(
                    f"第 {prepared.page_index + 1} 页：{error}"
                    for error in validation_errors
                )
            pages.append(
                TranscribedScorePage(
                    prepared=prepared,
                    result=result,
                    jianpu_text=normalized_text,
                    validation_errors=validation_errors,
                )
            )
            end_percent = 20 + int((index + 1) / total_pages * 60)
            report_progress(
                progress_callback,
                "ai_transcribe",
                end_percent,
                f"第 {prepared.page_index + 1} 页转写完成",
            )

        report_progress(progress_callback, "ai_merge", 84, "合并 AI 转写结果")
        merged = merge_page_jianpu_texts(
            [page.jianpu_text for page in pages],
            target_key=target_key,
            title=title or first_present([page.result.title for page in pages]),
        )
        return AiTranscriptionResult(
            source_path=source,
            pages=pages,
            merged_jianpu_text=merged,
            warnings=warnings,
        )
