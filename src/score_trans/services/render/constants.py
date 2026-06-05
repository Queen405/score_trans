from __future__ import annotations

import os

CHORD_GAP = int(os.getenv("SCORE_TRANS_RENDER_CHORD_GAP", "38"))
LOW_OCTAVE_DOT_OFFSET = int(os.getenv("SCORE_TRANS_RENDER_OCTAVE_DOT_OFFSET", "18"))
OCTAVE_DOT_GAP = int(os.getenv("SCORE_TRANS_RENDER_OCTAVE_DOT_GAP", "8"))
