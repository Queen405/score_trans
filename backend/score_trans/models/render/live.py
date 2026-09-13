from __future__ import annotations

from dataclasses import dataclass, field

from ..score import JianpuScore
from ..syntax.schemas import SyntaxDiagnostic


@dataclass(slots=True)
class LiveMeasureSelection:
    score: JianpuScore
    initial_measure_number: int
    warnings: list[SyntaxDiagnostic] = field(default_factory=list)
