from __future__ import annotations

import re
from collections.abc import Collection, Iterable

from ..models.provenance.schemas import SourceMap

# Shapes that ScoreTransOverlayExporter writes into score-link-map.json but
# that by design never receive jianpu text anchors (clefs, key/time
# signatures, tuplet digits). They must not be reported as unclickable.
_UNANCHORED_BY_DESIGN_PREFIXES: tuple[str, ...] = (
    "G_CLEF",
    "F_CLEF",
    "C_CLEF",
    "PERCUSSION_CLEF",
    "KEY_",
    "TIME_",
    "TUPLET_",
)

_SOURCE_ID_PAGE_RE = re.compile(r"^(?:p\d+\|)?s(\d+):i\d+$")


def anchorable_source_ids(source_map: SourceMap) -> list[str]:
    """Ids of link-map elements expected to receive jianpu text anchors."""
    ids: list[str] = []
    for sheet in source_map.sheets:
        for element in sheet.elements:
            if element.shape.startswith(_UNANCHORED_BY_DESIGN_PREFIXES):
                continue
            ids.append(element.source_id)
    return ids


def unanchored_source_ids_by_page(
    expected_ids: Iterable[str],
    anchored_ids: Collection[str],
) -> dict[int, list[str]]:
    """Group ``expected_ids - anchored_ids`` by the page encoded in the id.

    Provenance ids look like ``s{page}:i{inter}`` (optionally carrying a
    ``p{batch}|`` prefix); ids in any other format are grouped under page 0.
    """
    anchored = set(anchored_ids)
    missing: dict[int, set[str]] = {}
    for source_id in dict.fromkeys(expected_ids):
        if source_id in anchored:
            continue
        match = _SOURCE_ID_PAGE_RE.match(source_id)
        page = int(match.group(1)) if match else 0
        missing.setdefault(page, set()).add(source_id)
    return {page: sorted(ids) for page, ids in sorted(missing.items())}
