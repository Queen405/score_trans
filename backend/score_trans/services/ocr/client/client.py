from __future__ import annotations

from ..core.utils import is_deepseek_ocr_model


def ocr_prompt_for_model(model: str) -> str:
    if is_deepseek_ocr_model(model):
        return (
            "You are an OCR engine for sheet music pages. Extract every exact readable text item visible in the image, "
            "including title, lyrics, measure numbers, tempo marks, dynamics, fingering, and annotations. "
            "Do not translate, normalize, rewrite, merge, or correct the text. "
            "If only one measure number is readable, return that exact number and bbox; the renderer can number the rest. "
            "Preserve original wording exactly. Return JSON only as "
            '{"text_blocks":[{"text":"...","bbox":[x1,y1,x2,y2],'
            '"confidence":0.0,"role":"title|instrument|lyric|'
            'expression|footer|measure_number|other"}]}. '
            "Use pixel coordinates in the original image. If a coordinate is impossible to determine, use null for bbox. "
            "Do not describe the image. Do not explain."
        )
    return (
        "Extract all readable score text from this image. "
        "Preserve each text item exactly and include any readable measure number. "
        "Return JSON only as "
        '{"text_blocks":[{"text":"...","bbox":[x1,y1,x2,y2],'
        '"confidence":0.0,"role":"title|instrument|lyric|'
        'expression|footer|measure_number|other"}]}. '
    )
