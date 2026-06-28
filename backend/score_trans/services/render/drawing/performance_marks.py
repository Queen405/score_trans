from __future__ import annotations

from ....domain.performance_marks import get_performance_mark
from ..options import RenderOptions
from ..utils.articulations import _render_staccato
from ..utils.metrics import _token_metrics
from ..utils.positioning import _technique_mark_x, _technique_mark_y
from ..utils.text import _esc


def _render_performance_mark(
    mark_id: str,
    token: str,
    cx: float,
    y: int,
    layer: int,
    options: RenderOptions | None = None,
    *,
    anchor_y: float | None = None,
) -> list[str]:
    mark = get_performance_mark(mark_id)
    if mark is None:
        return []
    top = _token_metrics(token, y, options)["top"]
    py = anchor_y if anchor_y is not None else top - 13 - layer * 16
    px = cx
    if mark.placement == "left":
        px = cx - 18 - layer * 5
        py = y - 2
    elif mark.placement == "right":
        px = cx + 18 + layer * 5
        py = y - 2
    elif mark.placement == "below-right":
        px = _technique_mark_x(token, cx, options)
        py = _technique_mark_y(token, y, options)

    content = _mark_content(mark.renderer, mark_id, px, py)
    if not content:
        return []
    return [
        f'<g class="performance-mark" data-mark="{_esc(mark_id)}">',
        *content,
        "</g>",
    ]


def _mark_content(renderer: str, mark_id: str, x: float, y: float) -> list[str]:
    if renderer == "staccato":
        return [_render_staccato(x, y)]
    if renderer == "accent":
        return [
            f'<path class="articulation" d="M {x - 8:.1f} {y - 5:.1f} '
            f'L {x + 8:.1f} {y:.1f} L {x - 8:.1f} {y + 5:.1f}"/>'
        ]
    if renderer == "tenuto":
        return [
            f'<line class="articulation" x1="{x - 7:.1f}" y1="{y:.1f}" '
            f'x2="{x + 7:.1f}" y2="{y:.1f}"/>'
        ]
    if renderer == "fermata":
        return [
            f'<path class="articulation" d="M {x - 10:.1f} {y + 4:.1f} '
            f'Q {x:.1f} {y - 9:.1f}, {x + 10:.1f} {y + 4:.1f}"/>',
            f'<circle class="performance-symbol-fill" cx="{x:.1f}" cy="{y + 2:.1f}" r="2.2"/>',
        ]
    if renderer == "trill":
        return [
            f'<text class="ornament" x="{x:.1f}" y="{y + 4:.1f}" '
            'text-anchor="middle">tr</text>'
        ]
    if renderer == "three-slash":
        line_len = 10
        gap = 5
        rise = 4
        d = " ".join(
            f"M {x:.1f} {y + index * gap:.1f} "
            f"L {x + line_len:.1f} {y - rise + index * gap:.1f}"
            for index in range(3)
        )
        return [
            f'<path class="technique-mark" data-mark="{_esc(mark_id)}" '
            f'd="{d}" stroke="#171717" stroke-width="1.8" fill="none"/>'
        ]
    if renderer == "down-bow":
        return [
            f'<path class="performance-symbol" d="M {x - 7:.1f} {y + 6:.1f} '
            f'V {y - 5:.1f} H {x + 7:.1f} V {y + 6:.1f}"/>'
        ]
    if renderer == "up-bow":
        return [
            f'<path class="performance-symbol" d="M {x - 7:.1f} {y - 5:.1f} '
            f'L {x:.1f} {y + 6:.1f} L {x + 7:.1f} {y - 5:.1f}"/>'
        ]
    if renderer == "throw-bow":
        return [
            f'<path class="performance-symbol" d="M {x - 6:.1f} {y - 5:.1f} '
            f"Q {x + 1:.1f} {y - 7:.1f}, {x + 2:.1f} {y:.1f} "
            f"Q {x + 3:.1f} {y + 7:.1f}, {x - 4:.1f} {y + 6:.1f} "
            f'M {x + 2:.1f} {y + 1:.1f} L {x + 7:.1f} {y - 3:.1f}"/>'
        ]
    if renderer == "fingering":
        number = mark_id.rsplit("-", 1)[-1]
        return [
            f'<text class="technical fingering" x="{x:.1f}" y="{y + 4:.1f}" '
            f'text-anchor="middle">{number}</text>'
        ]
    if renderer == "natural-harmonic":
        return [
            f'<circle class="performance-symbol" cx="{x:.1f}" cy="{y:.1f}" r="4.5"/>'
        ]
    if renderer == "artificial-harmonic":
        return [
            f'<path class="performance-symbol" d="M {x:.1f} {y - 6:.1f} '
            f"L {x + 5:.1f} {y:.1f} L {x:.1f} {y + 6:.1f} "
            f'L {x - 5:.1f} {y:.1f} Z"/>'
        ]
    if renderer == "pluck":
        return [
            f'<path class="performance-symbol" d="M {x - 5:.1f} {y:.1f} '
            f'H {x + 5:.1f} M {x:.1f} {y - 5:.1f} V {y + 5:.1f}"/>'
        ]
    if renderer == "scoop":
        return [
            f'<path class="performance-symbol" d="M {x - 7:.1f} {y + 6:.1f} '
            f"Q {x - 1:.1f} {y + 6:.1f}, {x + 6:.1f} {y - 6:.1f} "
            f"M {x + 1:.1f} {y - 5:.1f} L {x + 6:.1f} {y - 6:.1f} "
            f'L {x + 5:.1f} {y - 1:.1f}"/>'
        ]
    if renderer == "plop":
        return [
            f'<path class="performance-symbol" d="M {x - 7:.1f} {y - 6:.1f} '
            f"Q {x - 1:.1f} {y - 6:.1f}, {x + 6:.1f} {y + 6:.1f} "
            f"M {x + 1:.1f} {y + 5:.1f} L {x + 6:.1f} {y + 6:.1f} "
            f'L {x + 5:.1f} {y + 1:.1f}"/>'
        ]
    if renderer == "finger-pad-slide":
        return [
            f'<path class="performance-symbol" d="M {x - 6:.1f} {y + 5:.1f} '
            f"Q {x - 1:.1f} {y - 6:.1f}, {x + 4:.1f} {y + 3:.1f} "
            f"M {x - 2:.1f} {y + 6:.1f} Q {x + 3:.1f} {y - 5:.1f}, "
            f'{x + 8:.1f} {y + 2:.1f}"/>'
        ]
    if renderer in {"doit", "falloff"}:
        end_y = y - 10 if renderer == "doit" else y + 10
        return [
            f'<path class="performance-symbol" d="M {x - 7:.1f} {y + (4 if renderer == "doit" else -4):.1f} '
            f'Q {x:.1f} {y:.1f}, {x + 10:.1f} {end_y:.1f}"/>'
        ]
    if renderer in {"lower-return-slide", "upper-return-slide"}:
        direction = 1 if renderer == "lower-return-slide" else -1
        return [
            f'<path class="performance-symbol" d="M {x - 7:.1f} {y:.1f} '
            f"Q {x + 2:.1f} {y + direction * 10:.1f}, {x + 8:.1f} {y + direction * 3:.1f} "
            f'Q {x + 4:.1f} {y + direction:.1f}, {x + 1:.1f} {y:.1f}"/>'
        ]
    if renderer in {"upper-trill", "lower-trill"}:
        notch = (
            f" M {x:.1f} {y + 2:.1f} L {x:.1f} {y + 8:.1f}"
            if renderer == "lower-trill"
            else ""
        )
        return [
            f'<path class="performance-symbol" d="M {x - 9:.1f} {y:.1f} '
            f'q 3 -4, 6 0 q 3 4, 6 0 q 3 -4, 6 0{notch}"/>'
        ]
    if renderer == "open-string":
        return [
            f'<text class="technical open-string" x="{x:.1f}" y="{y + 4:.1f}" '
            'text-anchor="middle">0</text>'
        ]
    if renderer in {"inner-string", "outer-string"}:
        text = "内" if renderer == "inner-string" else "外"
        return [
            f'<text class="technical string-name" x="{x:.1f}" y="{y + 4:.1f}" '
            f'text-anchor="middle">{text}</text>'
        ]
    if renderer == "breath-mark":
        return [
            f'<path class="performance-symbol-fill" d="M {x - 2:.1f} {y - 3:.1f} '
            f"Q {x + 4:.1f} {y - 2:.1f}, {x + 1:.1f} {y + 7:.1f} "
            f'Q {x - 1:.1f} {y + 4:.1f}, {x + 1:.1f} {y:.1f} Z"/>'
        ]
    if renderer == "hook-string":
        return [
            f'<path class="performance-symbol" d="M {x - 3:.1f} {y - 7:.1f} '
            f'V {y + 4:.1f} Q {x - 2:.1f} {y + 8:.1f}, {x + 5:.1f} {y + 4:.1f}"/>'
        ]
    if renderer == "guzheng-sweep-tremolo":
        return [
            f'<path class="performance-symbol" d="M {x - 11:.1f} {y - 4:.1f} '
            f"q 3 -5 6 0 h 3 q 3 5 6 0 "
            f"M {x - 11:.1f} {y + 5:.1f} q 3 -5 6 0 h 3 q 3 5 6 0 "
            f'M {x - 7:.1f} {y - 8:.1f} v 4 M {x + 7:.1f} {y + 1:.1f} v 4"/>'
        ]
    if renderer == "string-sweep":
        return [
            f'<path class="performance-symbol" d="M {x - 8:.1f} {y + 10:.1f} '
            f"L {x + 8:.1f} {y - 10:.1f} "
            f"M {x + 2:.1f} {y - 9:.1f} L {x + 8:.1f} {y - 10:.1f} "
            f"L {x + 7:.1f} {y - 4:.1f} "
            f"M {x - 7:.1f} {y + 4:.1f} L {x - 1:.1f} {y + 9:.1f} "
            f"M {x - 3:.1f} {y - 1:.1f} L {x + 3:.1f} {y + 4:.1f} "
            f'M {x + 1:.1f} {y - 6:.1f} L {x + 7:.1f} {y - 1:.1f}"/>'
        ]
    if renderer == "guzheng-double-tuo":
        return [
            f'<path class="performance-symbol" d="M {x - 10:.1f} {y + 6:.1f} '
            f"V {y - 4:.1f} H {x - 3:.1f} Q {x:.1f} {y - 4:.1f}, "
            f"{x:.1f} {y - 1:.1f} V {y + 2:.1f} "
            f"M {x - 1:.1f} {y + 6:.1f} V {y - 4:.1f} H {x + 6:.1f} "
            f'Q {x + 9:.1f} {y - 4:.1f}, {x + 9:.1f} {y - 1:.1f} V {y + 2:.1f}"/>'
        ]
    if renderer == "guzheng-double-mo":
        return [
            f'<path class="performance-symbol" d="M {x - 7:.1f} {y - 6:.1f} '
            f"L {x + 2:.1f} {y + 5:.1f} M {x - 1:.1f} {y - 7:.1f} "
            f'L {x + 8:.1f} {y + 4:.1f}"/>'
        ]
    if renderer == "arpeggio":
        return [
            f'<path class="performance-symbol" d="M {x:.1f} {y - 15:.1f} '
            f'q -5 3 0 6 q 5 3 0 6 q -5 3 0 6 q 5 3 0 6 q -5 3 0 6"/>'
        ]
    if renderer == "ornament-note":
        return [
            f'<ellipse class="performance-symbol" cx="{x - 2:.1f}" '
            f'cy="{y + 4:.1f}" rx="3.8" ry="2.8" '
            f'transform="rotate(-18 {x - 2:.1f} {y + 4:.1f})"/>',
            f'<path class="performance-symbol" d="M {x + 1:.1f} {y + 3:.1f} '
            f'V {y - 9:.1f} Q {x + 8:.1f} {y - 6:.1f}, '
            f'{x + 5:.1f} {y - 1:.1f}"/>',
        ]
    if renderer == "guzheng-board-front-flower":
        return [
            f'<path class="performance-symbol" d="M {x:.1f} {y - 10:.1f} '
            f"V {y + 2:.1f} M {x - 6:.1f} {y - 7:.1f} L {x + 6:.1f} {y - 1:.1f} "
            f"M {x + 6:.1f} {y - 7:.1f} L {x - 6:.1f} {y - 1:.1f} "
            f"M {x - 7:.1f} {y + 5:.1f} H {x + 7:.1f} "
            f'M {x - 5:.1f} {y + 9:.1f} H {x + 5:.1f}"/>'
        ]
    if renderer == "guzheng-on-beat-flower":
        return [
            f'<path class="performance-symbol" d="M {x:.1f} {y - 9:.1f} '
            f"V {y + 9:.1f} M {x - 9:.1f} {y:.1f} H {x + 9:.1f} "
            f"M {x - 6.5:.1f} {y - 6.5:.1f} L {x + 6.5:.1f} {y + 6.5:.1f} "
            f'M {x + 6.5:.1f} {y - 6.5:.1f} L {x - 6.5:.1f} {y + 6.5:.1f}"/>'
        ]
    if renderer in {"guzheng-ascending-scrape", "guzheng-descending-scrape"}:
        direction = -1 if renderer == "guzheng-ascending-scrape" else 1
        end_y = y + direction * 10
        start_y = y - direction * 8
        return [
            f'<path class="performance-symbol" d="M {x - 9:.1f} {start_y:.1f} '
            f"L {x + 9:.1f} {end_y:.1f} "
            f"M {x + 3:.1f} {end_y - direction * 1:.1f} L {x + 9:.1f} {end_y:.1f} "
            f'L {x + 8:.1f} {end_y - direction * 6:.1f}"/>'
        ]
    if renderer == "guzheng-vibrato":
        return [
            f'<path class="performance-symbol" d="M {x - 11:.1f} {y:.1f} '
            f'q 3 -4 6 0 q 3 4 6 0 q 3 -4 6 0 q 3 4 6 0"/>'
        ]
    if renderer in {
        "guzheng-ornament-up-slide",
        "guzheng-ornament-down-slide",
    }:
        direction = -1 if renderer == "guzheng-ornament-up-slide" else 1
        return [
            f'<path class="performance-symbol" d="M {x - 7:.1f} {y - direction * 6:.1f} '
            f"H {x - 1:.1f} V {y + direction * 1:.1f} "
            f"Q {x + 4:.1f} {y + direction * 8:.1f}, "
            f"{x + 8:.1f} {y + direction * 2:.1f} "
            f'M {x - 6:.1f} {y - direction * 2:.1f} H {x - 2:.1f}"/>'
        ]
    return []
