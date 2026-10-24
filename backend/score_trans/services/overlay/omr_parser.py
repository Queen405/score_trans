from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile

from ...utils.safe_xml import safe_xml_fromstring, safe_zip_member_bytes


@dataclass(slots=True)
class InterData:
    id: str
    tag: str
    shape: str
    grade: float
    bounds: tuple[int, int, int, int]
    median: tuple[float, float, float, float] | None = None
    width: float | None = None
    height: float | None = None
    thickness: float | None = None
    curve: tuple[float, float, float, float, float, float, float, float] | None = None
    pitch: float | None = None
    staff: str | None = None


@dataclass(slots=True)
class StaffData:
    id: str
    left: float
    right: float
    lines: tuple[tuple[float, float, float, float], ...]


@dataclass(slots=True)
class SheetModel:
    index: int
    width: int
    height: int
    inters: list[InterData]
    staves: list[StaffData]


_SKIP_TAGS: frozenset[str] = frozenset(
    {
        "head-chord",
        "rest-chord",
        "beam-group",
        "staff-barline",
    }
)

_SHEET_RE = re.compile(r"sheet#(\d+)/sheet#\d+\.xml$")


class OmrParser:
    """Parse an ``.omr`` book (ZIP) into :class:`SheetModel` instances."""

    def parse(self, omr_path: str | Path) -> list[SheetModel]:
        path = Path(omr_path)
        sheets: list[SheetModel] = []
        with ZipFile(path) as archive:
            sheet_entries = sorted(
                (
                    (int(match.group(1)), name)
                    for name in archive.namelist()
                    if (match := _SHEET_RE.search(name)) is not None
                ),
                key=lambda item: item[0],
            )
            for sheet_index, entry in sheet_entries:
                xml_bytes = safe_zip_member_bytes(
                    archive,
                    entry,
                    source=f"{path.name}:{entry}",
                )
                root = safe_xml_fromstring(
                    xml_bytes,
                    source=f"{path.name}:{entry}",
                )
                width, height = _read_picture_dimensions(root)
                inters = _read_inters(root)
                staves = _read_staves(root)
                sheets.append(
                    SheetModel(
                        index=sheet_index,
                        width=width,
                        height=height,
                        inters=inters,
                        staves=staves,
                    )
                )
        return sheets


def _read_picture_dimensions(root: ET.Element) -> tuple[int, int]:
    picture = root.find("picture")
    if picture is not None:
        w = picture.get("width")
        h = picture.get("height")
        if w and h:
            return int(w), int(h)
    return 0, 0


def _read_inters(root: ET.Element) -> list[InterData]:
    inters: list[InterData] = []
    for inters_container in root.iter("inters"):
        for child in inters_container:
            tag = child.tag
            if tag in _SKIP_TAGS:
                continue
            inter = _parse_inter(child)
            if inter is not None:
                inters.append(inter)
    return inters


def _parse_inter(element: ET.Element) -> InterData | None:
    tag = element.tag
    shape = element.get("shape", tag.upper())
    if tag == "time-pair":
        shape = _time_pair_shape(element.get("time-rational")) or "UNKNOWN_TIME"
    grade = _best_grade(element)
    bounds = _read_bounds(element)
    if bounds is None:
        return None

    median = _read_median(element)
    width = _read_float_attr(element, "width")
    height = _read_float_attr(element, "height")
    thickness = _read_float_attr(element, "thickness")
    curve = _read_curve(element)
    pitch = _read_float_attr(element, "pitch")

    return InterData(
        id=element.get("id", ""),
        tag=tag,
        shape=shape,
        grade=grade,
        bounds=bounds,
        median=median,
        width=width,
        height=height,
        thickness=thickness,
        curve=curve,
        pitch=pitch,
        staff=element.get("staff"),
    )


def _time_pair_shape(value: str | None) -> str | None:
    if not value:
        return None
    return {
        "4/4": "TIME_FOUR_FOUR",
        "2/2": "TIME_TWO_TWO",
        "2/4": "TIME_TWO_FOUR",
        "3/4": "TIME_THREE_FOUR",
        "5/4": "TIME_FIVE_FOUR",
        "6/4": "TIME_SIX_FOUR",
        "3/8": "TIME_THREE_EIGHT",
        "6/8": "TIME_SIX_EIGHT",
        "9/8": "TIME_NINE_EIGHT",
        "12/8": "TIME_TWELVE_EIGHT",
    }.get(value)


def _read_staves(root: ET.Element) -> list[StaffData]:
    staves: list[StaffData] = []
    for staff in root.iter("staff"):
        try:
            left = float(staff.get("left", "0"))
            right = float(staff.get("right", "0"))
            if right <= left:
                continue
            lines = tuple(
                (
                    float(points[0].get("x", "0")),
                    float(points[0].get("y", "0")),
                    float(points[-1].get("x", "0")),
                    float(points[-1].get("y", "0")),
                )
                for line in staff.findall("./lines/line")
                if (points := line.findall("point")) and len(points) >= 2
            )
            if len(lines) >= 5:
                staves.append(
                    StaffData(
                        id=staff.get("id", ""),
                        left=left,
                        right=right,
                        lines=lines,
                    )
                )
        except (TypeError, ValueError):
            continue
    return staves


def _best_grade(element: ET.Element) -> float:
    grade = _read_float_attr(element, "grade")
    ctx_grade = _read_float_attr(element, "ctx-grade")
    if ctx_grade is not None:
        return ctx_grade
    if grade is not None:
        return grade
    return 0.5


def _read_bounds(element: ET.Element) -> tuple[int, int, int, int] | None:
    bounds = element.find("bounds")
    if bounds is None:
        return None
    try:
        x = int(bounds.get("x", "0"))
        y = int(bounds.get("y", "0"))
        w = int(bounds.get("w", "0"))
        h = int(bounds.get("h", "0"))
    except (TypeError, ValueError):
        return None
    if w <= 0 or h <= 0:
        return None
    return x, y, w, h


def _read_median(element: ET.Element) -> tuple[float, float, float, float] | None:
    median = element.find("median")
    if median is None:
        return None
    p1 = median.find("p1")
    p2 = median.find("p2")
    if p1 is None or p2 is None:
        return None
    try:
        return (
            float(p1.get("x", "0")),
            float(p1.get("y", "0")),
            float(p2.get("x", "0")),
            float(p2.get("y", "0")),
        )
    except (TypeError, ValueError):
        return None


def _read_curve(
    element: ET.Element,
) -> tuple[float, float, float, float, float, float, float, float] | None:
    curve = element.find("curve")
    if curve is None:
        return None
    try:
        return (
            float(curve.get("x1", "0")),
            float(curve.get("y1", "0")),
            float(curve.get("ctrlx1", "0")),
            float(curve.get("ctrly1", "0")),
            float(curve.get("ctrlx2", "0")),
            float(curve.get("ctrly2", "0")),
            float(curve.get("x2", "0")),
            float(curve.get("y2", "0")),
        )
    except (TypeError, ValueError):
        return None


def _read_float_attr(element: ET.Element, name: str) -> float | None:
    value = element.get(name)
    if value is None or value.strip() == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None
