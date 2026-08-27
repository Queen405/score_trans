from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

logger = logging.getLogger(__name__)


_FONT_DIR = Path(__file__).resolve().parents[3] / "assets" / "fonts"
_FONT_FILES = {
    "text": (
        _FONT_DIR / "NotoSerifCJKsc-Regular.otf",
        "2a2eae2628df83556c54018c41e20fa532c1b862c5256ae8b3f23feb918d12ca",
    ),
    "music": (
        _FONT_DIR / "Bravura.otf",
        "dca2d90c88437a701b1c2e71fa54e76f9fa41d7deee935d74dc871ea66ecfdd2",
    ),
}


@dataclass(frozen=True, slots=True)
class GlyphPath:
    path: str
    cursor_em: float
    units_per_em: int


class FontRegistry:
    def __init__(self) -> None:
        self._fonts: dict[str, TTFont] = {}
        self._cmaps: dict[str, dict[int, str]] = {}
        for role, (path, expected_hash) in _FONT_FILES.items():
            if not path.is_file():
                raise RuntimeError(f"缺少出版字体资产：{path}")
            actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual_hash != expected_hash:
                raise RuntimeError(f"出版字体校验失败：{path.name}")
            font = TTFont(path, lazy=True)
            self._fonts[role] = font
            self._cmaps[role] = font.getBestCmap() or {}

    @property
    def manifest_hash(self) -> str:
        digest = hashlib.sha256()
        for role in sorted(_FONT_FILES):
            digest.update(_FONT_FILES[role][1].encode("ascii"))
        return digest.hexdigest()

    @lru_cache(maxsize=8192)
    def measure(self, text: str, font_size: float) -> float:
        return sum(self._advance_em(char) for char in text) * font_size

    @lru_cache(maxsize=8192)
    def ink_bounds(
        self, text: str, font_size: float
    ) -> tuple[float, float, float, float]:
        """Return text ink bounds relative to its start baseline.

        FontTools reports glyph coordinates with positive Y upwards.  SVG
        scene coordinates use positive Y downwards, so the vertical bounds are
        inverted here once and shared by all layout callers.
        """

        cursor_em = 0.0
        left_em: float | None = None
        top_em: float | None = None
        right_em: float | None = None
        bottom_em: float | None = None
        for char in text:
            try:
                role, glyph_name = self._glyph(char)
                font = self._fonts[role]
                glyph_set = font.getGlyphSet()
                pen = BoundsPen(glyph_set)
                glyph_set[glyph_name].draw(pen)
                if pen.bounds is not None:
                    x_min, y_min, x_max, y_max = pen.bounds
                    units_per_em = int(font["head"].unitsPerEm)
                    scale = 1.0 / units_per_em
                    glyph_left = cursor_em + x_min * scale
                    glyph_right = cursor_em + x_max * scale
                    glyph_top = -y_max * scale
                    glyph_bottom = -y_min * scale
                    left_em = (
                        glyph_left if left_em is None else min(left_em, glyph_left)
                    )
                    top_em = glyph_top if top_em is None else min(top_em, glyph_top)
                    right_em = (
                        glyph_right if right_em is None else max(right_em, glyph_right)
                    )
                    bottom_em = (
                        glyph_bottom
                        if bottom_em is None
                        else max(bottom_em, glyph_bottom)
                    )
            except AssertionError:
                logger.warning(
                    f"FontTools failed to draw glyph {char!r} (U+{ord(char):04X}), "
                    f"using fallback bounds (0, 0, 0, 0)"
                )
                cursor_em += self._advance_em(char)
        if left_em is None:
            return (0.0, 0.0, 0.0, 0.0)
        return (
            left_em * font_size,
            top_em * font_size,
            right_em * font_size,
            bottom_em * font_size,
        )

    @lru_cache(maxsize=8192)
    def paths(self, text: str) -> tuple[tuple[GlyphPath, ...], float]:
        cursor = 0.0
        result: list[GlyphPath] = []
        for char in text:
            try:
                role, glyph_name = self._glyph(char)
                font = self._fonts[role]
                units_per_em = int(font["head"].unitsPerEm)
                advance, _ = font["hmtx"][glyph_name]
                pen = SVGPathPen(font.getGlyphSet())
                font.getGlyphSet()[glyph_name].draw(pen)
                path = pen.getCommands()
                if path:
                    result.append(GlyphPath(path, cursor, units_per_em))
                cursor += advance / units_per_em
            except AssertionError:
                logger.warning(
                    f"FontTools failed to draw glyph {char!r} (U+{ord(char):04X}), "
                    f"skipping path generation"
                )
                continue
        return tuple(result), cursor

    def _advance_em(self, char: str) -> float:
        try:
            role, glyph_name = self._glyph(char)
            font = self._fonts[role]
            advance, _ = font["hmtx"][glyph_name]
            return advance / int(font["head"].unitsPerEm)
        except AssertionError:
            # Return a reasonable default advance when fontTools fails
            logger.warning(
                f"FontTools failed to get advance for {char!r}, using default 0.5em"
            )
            return 0.5

    def _glyph(self, char: str) -> tuple[str, str]:
        codepoint = ord(char)
        for role in ("text", "music"):
            glyph_name = self._cmaps[role].get(codepoint)
            if glyph_name:
                return role, glyph_name
        # Visible tofu is an intentional diagnostic fallback; layout never
        # delegates to a machine-dependent system font.
        replacement = self._cmaps["text"].get(ord("□"))
        if replacement:
            return "text", replacement
        raise ValueError(f"出版字体不包含字符 U+{codepoint:04X}：{char!r}")


@lru_cache(maxsize=1)
def font_registry() -> FontRegistry:
    return FontRegistry()


def reset_font_registry_cache() -> None:
    """Clear the font registry cache to force reinitialization.

    Used when font loading errors occur due to cached corrupted state.
    """
    font_registry.cache_clear()
