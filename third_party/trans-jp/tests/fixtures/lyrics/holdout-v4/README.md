# v4 controlled holdout

Four newly rendered pages were generated and labeled before the first model run:
English lyrics, two verses, closely spaced Chinese numeral-like lyrics, and an
instrumental negative. Each page has 16 known music digits; total 64 music digits
and 64 lyric words/characters. `labels.json` includes source SHA-256, known text,
Pillow text bounds, and line boxes. Rendering used the repository's OFL Noto Serif
CJK font, 1000x600 RGB images. All text is test content written for these fixtures.

These are controlled synthetic pages, not independent real scanned scores. No
classification thresholds were tuned on their evaluation results. Later fixes
were confined to replay completion and preserving unexplained mixed-region ink.
The first-evaluation code hashes, online body/text responses, failures, and counts
are under `screenshots/trans-jp-lyrics-v4/holdout/` in the local workspace.

Music retention and false-music counts are scored separately from lyric text.
A zero false-music count does not imply accurate lyric transcription or localization.
