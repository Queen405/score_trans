from __future__ import annotations

from .text import _esc


def _render_staccato(cx: float, cy: float, size: float = 4.5) -> str:
    return (
        f'<path class="staccato" d="M {cx - size:.1f} {cy - size:.1f} '
        f'L {cx + size:.1f} {cy - size:.1f} L {cx:.1f} {cy + size:.1f} Z"/>'
    )


def _render_articulation(name: str, cx: float, y: int) -> list[str]:
    normalized = name.lower().replace("_", "-")
    if normalized == "fermata":
        return [
            f'<path class="articulation" d="M {cx - 10:.1f} {y - 42} Q {cx:.1f} {y - 54}, {cx + 10:.1f} {y - 42}"/>',
            f'<circle class="octave-dot" cx="{cx:.1f}" cy="{y - 43}" r="2.4"/>',
        ]
    if normalized in {"accent", "strong-accent"}:
        return [
            f'<path class="articulation" d="M {cx - 9:.1f} {y - 37} L {cx + 9:.1f} {y - 32} L {cx - 9:.1f} {y - 27}"/>'
        ]
    if normalized == "staccato":
        return [_render_staccato(cx, y - 37)]
    if normalized == "tenuto":
        return [
            f'<line class="articulation" x1="{cx - 8:.1f}" y1="{y - 36}" x2="{cx + 8:.1f}" y2="{y - 36}"/>'
        ]
    if normalized == "trill-mark":
        sx = cx - 6
        return [
            f'<path class="articulation" d="M {sx:.1f} {y - 38:.1f} '
            f'q 3 -4, 6 0 q 3 4, 6 0"/>'
        ]
    return [
        f'<text class="lyric" x="{cx:.1f}" y="{y - 38}" text-anchor="middle">{_esc(name)}</text>'
    ]
