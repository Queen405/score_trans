from __future__ import annotations


def _bar_line(x: float, y: int) -> str:
    return f'<line class="bar" x1="{x:.1f}" y1="{y - 50}" x2="{x:.1f}" y2="{y + 58}"/>'


def _repeat_start_bar(x: float, y: int) -> list[str]:
    return [
        f'<line class="bar" x1="{x:.1f}" y1="{y - 50}" x2="{x:.1f}" y2="{y + 58}" stroke-width="3.0"/>',
        f'<line class="bar" x1="{x + 6:.1f}" y1="{y - 50}" x2="{x + 6:.1f}" y2="{y + 58}"/>',
        f'<circle class="octave-dot" cx="{x + 14:.1f}" cy="{y - 12}" r="2.8"/>',
        f'<circle class="octave-dot" cx="{x + 14:.1f}" cy="{y + 20}" r="2.8"/>',
    ]


def _repeat_end_bar(x: float, y: int) -> list[str]:
    return [
        f'<circle class="octave-dot" cx="{x - 14:.1f}" cy="{y - 12}" r="2.8"/>',
        f'<circle class="octave-dot" cx="{x - 14:.1f}" cy="{y + 20}" r="2.8"/>',
        f'<line class="bar" x1="{x - 6:.1f}" y1="{y - 50}" x2="{x - 6:.1f}" y2="{y + 58}"/>',
        f'<line class="bar" x1="{x:.1f}" y1="{y - 50}" x2="{x:.1f}" y2="{y + 58}" stroke-width="3.0"/>',
    ]
