"""Compatibility imports; implementation lives in the layered package."""

from __future__ import annotations

from .models.contracts import (
    CliConfig as CliConfig,
    LlmConfig as LlmConfig,
    RecognizedToken as RecognizedToken,
    RowResult as RowResult,
    RowSegment as RowSegment,
    TransJpResult as TransJpResult,
    DEFAULT_SHEET_INDEX as DEFAULT_SHEET_INDEX,
    make_source_id as make_source_id,
)
