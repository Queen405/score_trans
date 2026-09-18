from __future__ import annotations
import json
from functools import cache
from importlib.resources import files


@cache
def glyph_assets() -> dict:
    return json.loads(
        files("trans_jp").joinpath("assets/glyphs.json").read_text(encoding="utf-8")
    )["glyphs"]
