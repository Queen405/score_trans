from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Protocol

from .response_parser import parse_row_response
from ..models.contracts import CompletionResult
from ..models.candidates import RowRecognitionRequest
from .prompt_builder import PromptBuilder
from ..models.contracts import RecognizedToken, RowResult, RowSegment

logger = logging.getLogger("trans_jp.recognize")


class CandidateRowTranscriber(Protocol):
    def transcribe_request_with_retry(
        self, request: RowRecognitionRequest, prompt: str, *, max_retries: int = 1
    ) -> CompletionResult: ...


class RowTranscriber(Protocol):
    def transcribe_row_with_retry(
        self, image_path: Path, prompt: str, *, max_retries: int = 1
    ) -> CompletionResult: ...


def recognize_rows(
    rows: list[RowSegment],
    llm_client: RowTranscriber | CandidateRowTranscriber,
    prompt_builder: PromptBuilder,
    *,
    target_key: str,
    title: str | None,
    extra_prompt: str | None = None,
    concurrency: int = 2,
    progress_callback: Callable[[int, int], None] | None = None,
    requests: dict[int, RowRecognitionRequest] | None = None,
) -> list[RowResult]:
    results: list[RowResult | None] = [None] * len(rows)
    total = len(rows)
    done = 0

    if concurrency <= 1:
        for row in rows:
            results[row.index] = _safe_recognize(
                row,
                llm_client,
                prompt_builder,
                request=(requests or {}).get(row.index),
                row_index=row.index,
                total_rows=total,
                target_key=target_key,
                title=title,
                extra_prompt=extra_prompt,
            )
            done += 1
            if progress_callback:
                progress_callback(done, total)
    else:
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            future_to_index = {
                executor.submit(
                    _safe_recognize,
                    row,
                    llm_client,
                    prompt_builder,
                    request=(requests or {}).get(row.index),
                    row_index=row.index,
                    total_rows=total,
                    target_key=target_key,
                    title=title,
                    extra_prompt=extra_prompt,
                ): row.index
                for row in rows
            }
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                results[index] = future.result()
                done += 1
                if progress_callback:
                    progress_callback(done, total)

    return [r for r in results if r is not None]


def _safe_recognize(
    row: RowSegment,
    llm_client: RowTranscriber | CandidateRowTranscriber,
    prompt_builder: PromptBuilder,
    *,
    request: RowRecognitionRequest | None = None,
    row_index: int,
    total_rows: int,
    target_key: str,
    title: str | None,
    extra_prompt: str | None,
) -> RowResult:
    try:
        return _recognize_single_row(
            row,
            llm_client,
            prompt_builder,
            request=request,
            row_index=row_index,
            total_rows=total_rows,
            target_key=target_key,
            title=title,
            extra_prompt=extra_prompt,
        )
    except Exception as exc:
        logger.error("行 %d 识别失败: %s", row_index, exc)
        return _error_row_result(row, str(exc))


def _recognize_single_row(
    row: RowSegment,
    llm_client: RowTranscriber | CandidateRowTranscriber,
    prompt_builder: PromptBuilder,
    *,
    request: RowRecognitionRequest | None = None,
    row_index: int,
    total_rows: int,
    target_key: str,
    title: str | None,
    extra_prompt: str | None,
) -> RowResult:
    prompt = prompt_builder.build_row_prompt(
        row_index=row_index,
        total_rows=total_rows,
        target_key=target_key,
        title=title,
        extra_prompt=extra_prompt,
    )
    if request is not None and hasattr(llm_client, "transcribe_request_with_retry"):
        prompt += prompt_builder.candidate_instructions(request.registry)
        result = llm_client.transcribe_request_with_retry(request, prompt)
    else:
        result = LegacyRowTranscriberAdapter(llm_client).transcribe(
            row.image_path, prompt
        )
    parsed = parse_row_response(result.content)
    if request is not None and request.expected_schema == 2:
        if parsed["schema_version"] != 2:
            parsed["warnings"].append("模型未返回 v2 协议，本行禁止坐标回退")
            parsed["schema_version"] = 2
            for token in parsed["tokens"]:
                token["candidate_ids"] = ()

    tokens = [
        RecognizedToken(
            index=i,
            text=t["text"],
            x=t["x"],
            w=t["w"],
            role=t["role"],
            y=t["y"],
            h=t["h"],
            candidate_ids=t["candidate_ids"],
        )
        for i, t in enumerate(parsed["tokens"])
    ]
    return RowResult(
        row=row,
        row_type=parsed["row_type"],
        jianpu_text=parsed["row_text"],
        tokens=tokens,
        key=parsed["key"],
        meter=parsed["meter"],
        tempo=parsed["tempo"],
        title=parsed["title"],
        warnings=parsed["warnings"],
        confidence=parsed["confidence"],
        schema_version=parsed["schema_version"],
        registry=request.registry if request else None,
        unresolved_candidates=parsed["unresolved_candidates"],
        raw_response=result.content,
        complete=not parsed["unresolved_candidates"]
        and not any(
            t.role in ("note", "rest", "chord") and not t.candidate_ids for t in tokens
        )
        if parsed["schema_version"] == 2
        else True,
    )


def _error_row_result(row: RowSegment, error_message: str) -> RowResult:
    return RowResult(
        row=row,
        row_type="other",
        jianpu_text="",
        tokens=[],
        warnings=[f"行 {row.index} 识别失败: {error_message}"],
        confidence=None,
        complete=False,
    )


class LegacyRowTranscriberAdapter:
    """Explicit adapter for older injected clients without multi-image requests."""

    def __init__(self, client: RowTranscriber):
        self.client = client

    def transcribe(self, image_path: Path, prompt: str) -> CompletionResult:
        return self.client.transcribe_row_with_retry(image_path, prompt)
