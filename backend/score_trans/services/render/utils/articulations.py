from __future__ import annotations


def _render_staccato(cx: float, cy: float, size: float = 4.5) -> str:
    return (
        f'<path class="staccato" d="M {cx - size:.1f} {cy - size:.1f} '
        f'L {cx + size:.1f} {cy - size:.1f} L {cx:.1f} {cy + size:.1f} Z"/>'
    )
