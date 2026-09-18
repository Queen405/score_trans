from __future__ import annotations

import math
import re
from fractions import Fraction
from ..models.contracts import RowResult
from ..symbols.notation_parser import parse_notation


def validate_rows(rows: list[RowResult], width: int, height: int) -> list[str]:
    """Diagnostics only: never repair musical content to force a full measure."""
    warnings = []
    meter: Fraction | None = None
    for row in rows:
        if row.recognition_scope in ("bodies_only", "melody_experimental"):
            continue
        if row.meter:
            match = re.fullmatch(r"(\d+)/(\d+)", str(row.meter))
            if match and int(match[2]) > 0:
                meter = Fraction(int(match[1]) * 4, int(match[2]))
        durations = [Fraction(0)]
        known = True
        has_notes = False
        for token in row.tokens:
            if token.text == "&":
                durations.append(Fraction(0))
                continue
            if token.role.startswith("header_") or token.role == "lyrics":
                continue
            note = parse_notation(token.text)
            if note is None:
                known = False
            elif note.kind in ("note", "extension"):
                has_notes = True
                durations[-1] += note.duration
            elif note.kind == "barline":
                if has_notes and known and meter is not None:
                    for voice, duration in enumerate(durations):
                        if duration != meter:
                            warnings.append(
                                f"行 {row.row.index} 声部 {voice}: 小节时值 {duration} 与拍号 {meter} 不符（弱起/不完整小节也可能触发）"
                            )
                durations = [Fraction(0)]
                known = True
                has_notes = False
            geometry = token.geometry
            if not geometry:
                continue
            for primitive in geometry.primitives:
                b = primitive.bounds
                if (
                    not all(math.isfinite(v) for v in (b.x, b.y, b.width, b.height))
                    or b.width <= 0
                    or b.height <= 0
                ):
                    warnings.append(f"行 {row.row.index} token {token.index}: 无效几何")
                elif b.x < 0 or b.y < 0 or b.right > width or b.bottom > height:
                    warnings.append(
                        f"行 {row.row.index} token {token.index}: 几何超出原图边界"
                    )
    return warnings


def reject_invalid_geometry(rows: list[RowResult], width: int, height: int) -> None:
    """Drop a token consistently before SVG and SourceMap project its geometry."""
    for row in rows:
        for token in row.tokens:
            geometry = token.geometry
            if geometry is None:
                continue
            boxes = [
                *geometry.bodies,
                *[p.bounds for p in geometry.primitives],
                *[
                    p.hit_bounds
                    for p in geometry.primitives
                    if p.hit_bounds is not None
                ],
            ]
            invalid = any(
                not all(math.isfinite(v) for v in (b.x, b.y, b.width, b.height))
                or b.width <= 0
                or b.height <= 0
                or b.x < -1e-6
                or b.y < -1e-6
                or b.right > width + 1e-6
                or b.bottom > height + 1e-6
                for b in boxes
            )
            invalid = invalid or any(
                not math.isfinite(p.thickness)
                or p.thickness <= 0
                or any(
                    not math.isfinite(x)
                    or not math.isfinite(y)
                    or x < -1e-6
                    or y < -1e-6
                    or x > width + 1e-6
                    or y > height + 1e-6
                    for x, y in p.points
                )
                for p in geometry.primitives
            )
            if invalid:
                geometry.bodies.clear()
                geometry.primitives.clear()
                geometry.status = "unmatched"
                message = "坐标变换后几何无效或越界，禁止绘制"
                geometry.warnings.append(message)
                row.warnings.append(
                    f"行 {row.row.index} token {token.index}: {message}"
                )
