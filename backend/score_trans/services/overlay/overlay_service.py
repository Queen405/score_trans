from __future__ import annotations

import logging
from pathlib import Path

from .omr_parser import OmrParser, SheetModel
from .svg_generator import SvgGenerator

logger = logging.getLogger(__name__)


class OverlayService:
    """Generate SVG overlay files from Audiveris ``.omr`` books."""

    def __init__(
        self,
        parser: OmrParser | None = None,
        generator: SvgGenerator | None = None,
    ) -> None:
        self.parser = parser or OmrParser()
        self.generator = generator or SvgGenerator()

    def generate_overlay_svgs(
        self, omr_output_dir: str | Path
    ) -> list[Path]:
        """Find ``.omr`` files, parse, and write overlay SVGs.

        Returns a list of generated SVG file paths.
        Never raises — overlay generation is non-fatal.
        """
        try:
            omr_files = sorted(
                Path(omr_output_dir).rglob("*.omr"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        except OSError:
            return []
        if not omr_files:
            return []

        for omr_file in omr_files:
            sheets = self.parser.parse(omr_file)
            if not sheets:
                continue

            svg_paths: list[Path] = []
            output_dir = Path(omr_output_dir)
            for sheet in sheets:
                svg_text = self.generator.generate(sheet)
                svg_path = output_dir / f"overlay_sheet{sheet.index}.svg"
                svg_path.write_text(svg_text, encoding="utf-8")
                svg_paths.append(svg_path)
            return svg_paths
        return []

    def parse_sheets(self, omr_path: str | Path) -> list[SheetModel]:
        """Parse an ``.omr`` file into sheet models (for testing)."""
        return self.parser.parse(omr_path)
