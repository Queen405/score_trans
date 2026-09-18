"""Legacy I/O adapter. The structure module itself does no file I/O."""

from __future__ import annotations
from pathlib import Path
import numpy as np
from PIL import Image
from .structure.row_segmenter import segment as _segment
from .io.images import save_rows
from .models.contracts import RowSegment


def segment(
    binary: np.ndarray, original: Image.Image, rows_dir: Path, **kwargs
) -> list[RowSegment]:
    rows = _segment(binary, original, rows_dir, **kwargs)
    save_rows(original, rows)
    return rows
