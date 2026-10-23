from __future__ import annotations

import json
import logging
from pathlib import Path

from ...domain.reconciliation import (
    anchorable_source_ids,
    unanchored_source_ids_by_page,
)
from ...models.provenance.schemas import SourceMap
from ..files.image_info import image_dimensions
from .omr_parser import OmrParser, SheetModel
from .svg_generator import SvgGenerator

logger = logging.getLogger(__name__)


def find_unanchored_source_ids(
    source_map: SourceMap,
    anchored_ids: set[str],
) -> dict[int, list[str]]:
    """Diff anchorable link-map elements against text anchors, grouped by page."""
    return unanchored_source_ids_by_page(
        anchorable_source_ids(source_map),
        anchored_ids,
    )


class OverlayService:
    """Generate SVG overlay files from Audiveris ``.omr`` books."""

    def __init__(
        self,
        parser: OmrParser | None = None,
        generator: SvgGenerator | None = None,
    ) -> None:
        self.parser = parser or OmrParser()
        self.generator = generator or SvgGenerator()

    def generate_overlay_svgs(self, omr_output_dir: str | Path) -> list[Path]:
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
            logger.warning(
                "Failed to scan Audiveris output directory: %s",
                omr_output_dir,
                exc_info=True,
            )
            return []
        if not omr_files:
            return []

        for omr_file in omr_files:
            try:
                sheets = self.parser.parse(omr_file)
            except Exception:
                logger.warning(
                    "Failed to parse Audiveris book: %s",
                    omr_file,
                    exc_info=True,
                )
                continue
            if not sheets:
                continue

            svg_paths: list[Path] = []
            output_dir = Path(omr_output_dir)
            try:
                output_dir.mkdir(parents=True, exist_ok=True)
                for sheet in sheets:
                    if sheet.width <= 0 or sheet.height <= 0 or not sheet.inters:
                        logger.info(
                            "Skipping unusable Audiveris sheet %s in %s",
                            sheet.index,
                            omr_file,
                        )
                        continue
                    svg_text = self.generator.generate(sheet)
                    svg_path = output_dir / f"overlay_sheet{sheet.index}.svg"
                    svg_path.write_text(svg_text, encoding="utf-8")
                    svg_paths.append(svg_path)
            except Exception:
                logger.warning(
                    "Failed to generate overlay from Audiveris book: %s",
                    omr_file,
                    exc_info=True,
                )
                continue
            if svg_paths:
                return svg_paths
        return []

    def find_native_overlay(
        self, omr_output_dir: str | Path
    ) -> tuple[Path | None, Path | None]:
        """Return Audiveris-native overlay and sidecar after validating their contract."""
        output_dir = Path(omr_output_dir)
        source_map_path = output_dir / "score-link-map.json"
        if not source_map_path.exists():
            return None, None
        try:
            source_map = SourceMap.model_validate(
                json.loads(source_map_path.read_text(encoding="utf-8"))
            )
        except (OSError, ValueError, json.JSONDecodeError):
            logger.warning("Invalid Audiveris source map: %s", source_map_path)
            return None, None
        if source_map.version not in {1, 2} or not source_map.sheets:
            return None, None
        sheet = source_map.sheets[0]
        output_root = output_dir.resolve()
        overlay_path = (output_dir / sheet.overlay_file).resolve()
        if (
            not overlay_path.is_relative_to(output_root)
            or not overlay_path.is_file()
            or overlay_path.suffix.lower() != ".png"
        ):
            logger.warning("Audiveris overlay referenced by source map is missing")
            return None, None
        try:
            width, height = image_dimensions(overlay_path)
        except OSError:
            return None, None
        if (int(width), int(height)) != (sheet.width, sheet.height):
            logger.warning("Audiveris overlay dimensions do not match its source map")
            return None, None
        return overlay_path, source_map_path

    def parse_sheets(self, omr_path: str | Path) -> list[SheetModel]:
        """Parse an ``.omr`` file into sheet models (for testing)."""
        return self.parser.parse(omr_path)
