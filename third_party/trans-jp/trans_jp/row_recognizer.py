"""Compatibility imports; implementation lives in the layered package."""

from __future__ import annotations

from .recognition.row_recognizer import (
    RowTranscriber as RowTranscriber,
    recognize_rows as recognize_rows,
)
