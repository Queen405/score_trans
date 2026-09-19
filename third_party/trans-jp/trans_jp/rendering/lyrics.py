from __future__ import annotations

from xml.sax.saxutils import escape
from PIL import Image, ImageDraw
from ..models.geometry import Box
from ..models.lyrics import LyricsResult


def text_atlas(
    work: Image.Image, entries: list[tuple[str, Box]], *, context: bool
) -> Image.Image:
    panels = []
    for identity, b in entries:
        pad = max(12, int(b.height * 1.6)) if context else 3
        x = max(0, int(b.x) - pad)
        y = max(0, int(b.y) - pad)
        right, bottom = (
            min(work.width, int(b.right) + pad),
            min(work.height, int(b.bottom) + pad),
        )
        crop = work.crop((x, y, right, bottom)).convert("RGB")
        ratio = min(2, 1600 / max(1, crop.width))
        crop = crop.resize(
            (max(1, round(crop.width * ratio)), max(1, round(crop.height * ratio)))
        )
        panel = Image.new("RGB", (max(300, crop.width), crop.height + 24), "white")
        panel.paste(crop, (0, 24))
        d = ImageDraw.Draw(panel)
        d.text((3, 3), identity, fill="blue")
        if context:
            d.rectangle(
                (
                    (b.x - x) * ratio,
                    (b.y - y) * ratio + 24,
                    (b.right - x) * ratio,
                    (b.bottom - y) * ratio + 24,
                ),
                outline="blue",
                width=1,
            )
        panels.append(panel)
    result = Image.new(
        "RGB",
        (max(p.width for p in panels), sum(p.height + 8 for p in panels)),
        "#eeeeee",
    )
    top = 0
    for p in panels:
        result.paste(p, (0, top))
        top += p.height + 8
    return result


def lyric_overlay(result: LyricsResult, width: int, height: int) -> str:
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
    ]
    for line in result.lines:
        for identity, text, b, status in [
            (line.region_id, line.text, line.bounds, line.localization_status),
            *[
                (t.token_id, t.text, t.bounds, t.localization_status)
                for t in line.tokens
            ],
        ]:
            color = "#9a38c4" if identity == line.region_id else "#cf7400"
            parts.append(
                f'<g data-lyric-id="{escape(identity)}"><title>{escape(text)} | {escape(status)}</title><rect x="{b.x}" y="{b.y}" width="{b.width}" height="{b.height}" stroke="{color}" stroke-width="0.7" fill="none"/></g>'
            )
    parts.append("</svg>")
    return "\n".join(parts)


def lyrics_preview(
    image_url: str,
    music_svg: str,
    text_svg: str,
    result: LyricsResult,
    width: int,
    height: int,
) -> str:
    """Self-contained inspection page; image text is escaped before embedding."""
    import json

    conflicts = []
    for c in result.conflicts:
        b = Box(**c["bounds"])
        title = escape(c["candidate_id"] + " | " + c["status"] + " | " + c["reason"])
        conflicts.append(
            f'<g><title>{title}</title><rect x="{b.x}" y="{b.y}" width="{b.width}" height="{b.height}" fill="none" stroke="#e96d29" stroke-width="0.6"/></g>'
        )
    conflict_svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">{"".join(conflicts)}</svg>'
    payload = json.dumps(
        [
            {
                "text": line.text,
                "status": line.localization_status,
                "id": line.region_id,
            }
            for line in result.lines
        ],
        ensure_ascii=False,
    ).replace("<", chr(92) + "u003c")
    pending_svg = pending_overlay(result, width, height)
    pending_data = json.dumps(
        {d["candidate_id"]: d for d in result.pending}, ensure_ascii=False
    ).replace("<", chr(92) + "u003c")
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>歌词与音符核对</title>
<style>body{{font:16px/1.6 system-ui;margin:24px;background:#f6f7fa;color:#24303f}}header{{position:sticky;top:0;background:white;padding:12px;z-index:5}}label{{margin-right:16px}}main{{display:grid;grid-template-columns:minmax(400px,1fr) 320px;gap:20px}}.sheet{{position:relative}}.sheet img{{display:block;width:100%}}.layer{{position:absolute;inset:0;pointer-events:none}}.layer svg{{width:100%;height:100%}}.layer g{{pointer-events:all;cursor:pointer}}aside{{background:white;padding:16px}}button{{display:block;margin:8px 0;padding:8px;width:100%;text-align:left}}#details{{white-space:pre-wrap}}@media(max-width:850px){{main{{display:block}}}}</style>
<header><b>歌词与音符核对（实验）</b><br><label><input type="checkbox" checked data-layer="music">音符</label><label><input type="checkbox" checked data-layer="lyrics">歌词位置</label><label><input type="checkbox" checked data-layer="pending">待确认音符（不计入简谱）</label><label><input type="checkbox" data-layer="conflicts">文字冲突</label><p>歌词为模型观测；紫框为行/片段，橙框为裁剪复核字词。点击查看状态。音符对齐未确认。</p></header>
<main><div class="sheet"><img src="{image_url}" alt="原始谱面"><div class="layer" id="music">{music_svg}</div><div class="layer" id="lyrics">{text_svg}</div><div class="layer" id="pending">{pending_svg}</div><div class="layer" id="conflicts" hidden>{conflict_svg}</div></div><aside><div id="details">选择歌词框或冲突框查看详情</div><canvas id="pending-crop" hidden></canvas><div id="lines"></div></aside></main>
<script>const lines={payload};const pending={pending_data};document.querySelectorAll('input[data-layer]').forEach(c=>c.onchange=()=>document.getElementById(c.dataset.layer).hidden=!c.checked);document.querySelectorAll('.layer g').forEach(g=>g.onclick=()=>{{document.getElementById('details').textContent=g.querySelector('title')?.textContent||'音符主体，音乐属性未确认';const canvas=document.getElementById('pending-crop');const item=pending[g.dataset.pendingId];canvas.hidden=!item;if(item){{const image=document.querySelector('.sheet img');const b=item.bounds;const x=Math.max(0,b.x-6),y=Math.max(0,b.y-6),w=Math.min(image.naturalWidth-x,b.width+12),h=Math.min(image.naturalHeight-y,b.height+12);const scale=Math.min(4,300/w,160/h);canvas.width=Math.max(1,Math.round(w*scale));canvas.height=Math.max(1,Math.round(h*scale));canvas.getContext('2d').drawImage(image,x,y,w,h,0,0,canvas.width,canvas.height);}}}});for(const line of lines){{const b=document.createElement('button');b.textContent=line.text;b.onclick=()=>{{document.getElementById('details').textContent=line.id+' | '+line.status+String.fromCharCode(10)+line.text;}};document.getElementById('lines').appendChild(b);}}</script></html>'''


def pending_overlay(result: LyricsResult, width: int, height: int) -> str:
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
    ]
    for d in result.pending:
        b = Box(**d["bounds"])
        label = d.get("observed_label")
        title = escape(
            d["candidate_id"]
            + " | 待确认 | "
            + d["reason"]
            + " | 旧识别值: "
            + (label or "无")
            + " | 请求: "
            + ", ".join(d["request_ids"])
        )
        parts.append(
            f'<g data-pending-id="{escape(d["candidate_id"])}"><title>{title}</title><rect x="{b.x}" y="{b.y}" width="{b.width}" height="{b.height}" stroke="#777" stroke-width="0.8" stroke-dasharray="3 2" fill="none"/>'
        )
        if label:
            parts.append(
                f'<text x="{b.x}" y="{b.y - 2}" font-size="{max(6, min(12, b.height * 0.6))}" fill="#666">{escape(label)}?</text>'
            )
        parts.append("</g>")
    parts.append("</svg>")
    return "\n".join(parts)
