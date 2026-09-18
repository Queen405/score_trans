"""Legacy adapter; the renderer itself receives assets through dependency injection."""

from __future__ import annotations
from .models.contracts import RowResult
from .io.assets import glyph_assets
from .rendering.overlay_renderer import generate_overlay_svg as _render
from .rendering.overlay_renderer import ROLE_COLORS as ROLE_COLORS


def generate_overlay_svg(
    row_results: list[RowResult],
    image_width: int,
    image_height: int,
    *,
    debug: bool = False,
) -> str:
    return _render(row_results, image_width, image_height, glyph_assets(), debug=debug)
