from __future__ import annotations

from fractions import Fraction

MICROTONAL_TOKEN_TO_ALTER = {
    "qf": Fraction(-1, 2),
    "qs": Fraction(1, 2),
    "tqf": Fraction(-3, 2),
    "tqs": Fraction(3, 2),
}
MUSICXML_ACCIDENTAL_TO_TOKEN = {
    "flat": "b",
    "natural": "n",
    "sharp": "#",
    "double-flat": "bb",
    "flat-flat": "bb",
    "double-sharp": "x",
    "sharp-sharp": "x",
    "quarter-flat": "qf",
    "quarter-sharp": "qs",
    "three-quarters-flat": "tqf",
    "three-quarters-sharp": "tqs",
}
TOKEN_TO_MUSICXML_ACCIDENTAL = {
    token: name
    for name, token in MUSICXML_ACCIDENTAL_TO_TOKEN.items()
    if name
    in {
        "flat",
        "natural",
        "sharp",
        "double-flat",
        "double-sharp",
        "quarter-flat",
        "quarter-sharp",
        "three-quarters-flat",
        "three-quarters-sharp",
    }
}

STEP_TO_SEMITONE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
MAJOR_SCALE = [0, 2, 4, 5, 7, 9, 11]
FIFTHS_TO_KEY = {
    -7: "Cb",
    -6: "Gb",
    -5: "Db",
    -4: "Ab",
    -3: "Eb",
    -2: "Bb",
    -1: "F",
    0: "C",
    1: "G",
    2: "D",
    3: "A",
    4: "E",
    5: "B",
    6: "F#",
    7: "C#",
}
KEY_TO_FIFTHS = {value: key for key, value in FIFTHS_TO_KEY.items()}
KEY_TO_TONIC = {
    "C": 0,
    "G": 7,
    "D": 2,
    "A": 9,
    "E": 4,
    "B": 11,
    "F#": 6,
    "C#": 1,
    "F": 5,
    "Bb": 10,
    "Eb": 3,
    "Ab": 8,
    "Db": 1,
    "Gb": 6,
    "Cb": 11,
}
DYNAMICS = {
    "p",
    "pp",
    "ppp",
    "pppp",
    "mp",
    "mf",
    "f",
    "ff",
    "fff",
    "ffff",
    "sf",
    "sfz",
    "sfp",
    "fp",
    "fz",
    "rfz",
}

MUSICXML_METRONOME_UNIT_TO_SYMBOL = {
    "whole": "𝅝",
    "half": "𝅗𝅥",
    "quarter": "♩",
    "eighth": "♪",
    "16th": "𝅘𝅥𝅯",
    "32nd": "𝅘𝅥𝅰",
    "64th": "𝅘𝅥𝅱",
    "128th": "𝅘𝅥𝅲",
}
METRONOME_SYMBOL_TO_MUSICXML_UNIT = {
    symbol: unit for unit, symbol in MUSICXML_METRONOME_UNIT_TO_SYMBOL.items()
}
