from __future__ import annotations


def _bar_bounds(y: int, top: float | None, bottom: float | None) -> tuple[float, float]:
    return (
        float(y - 50) if top is None else top,
        float(y + 58) if bottom is None else bottom,
    )


def _bar_line(
    x: float,
    y: int,
    *,
    top: float | None = None,
    bottom: float | None = None,
) -> str:
    y1, y2 = _bar_bounds(y, top, bottom)
    return f'<line class="bar" x1="{x:.1f}" y1="{y1:g}" x2="{x:.1f}" y2="{y2:g}"/>'


def _repeat_start_bar(
    x: float,
    y: int,
    *,
    top: float | None = None,
    bottom: float | None = None,
) -> list[str]:
    y1, y2 = _bar_bounds(y, top, bottom)
    return [
        f'<line class="bar" x1="{x:.1f}" y1="{y1:g}" x2="{x:.1f}" y2="{y2:g}" stroke-width="3.0"/>',
        f'<line class="bar" x1="{x + 6:.1f}" y1="{y1:g}" x2="{x + 6:.1f}" y2="{y2:g}"/>',
        f'<circle class="octave-dot" cx="{x + 14:.1f}" cy="{y - 12}" r="2.8"/>',
        f'<circle class="octave-dot" cx="{x + 14:.1f}" cy="{y + 20}" r="2.8"/>',
    ]


def _repeat_end_bar(
    x: float,
    y: int,
    *,
    top: float | None = None,
    bottom: float | None = None,
) -> list[str]:
    y1, y2 = _bar_bounds(y, top, bottom)
    return [
        f'<circle class="octave-dot" cx="{x - 14:.1f}" cy="{y - 12}" r="2.8"/>',
        f'<circle class="octave-dot" cx="{x - 14:.1f}" cy="{y + 20}" r="2.8"/>',
        f'<line class="bar" x1="{x - 6:.1f}" y1="{y1:g}" x2="{x - 6:.1f}" y2="{y2:g}"/>',
        f'<line class="bar" x1="{x:.1f}" y1="{y1:g}" x2="{x:.1f}" y2="{y2:g}" stroke-width="3.0"/>',
    ]
