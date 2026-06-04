from __future__ import annotations

from .jianpu_tokens import DURATION_PREFIXES

STEP_TO_SEMITONE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
SEMITONE_TO_STEP = {
    0: ("C", 0),
    1: ("C", 1),
    2: ("D", 0),
    3: ("D", 1),
    4: ("E", 0),
    5: ("F", 0),
    6: ("F", 1),
    7: ("G", 0),
    8: ("G", 1),
    9: ("A", 0),
    10: ("A", 1),
    11: ("B", 0),
}
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
DEGREE_TO_MAJOR_OFFSET = {index + 1: offset for index, offset in enumerate(MAJOR_SCALE)}

DURATION_TO_PREFIX = {value: key for key, value in DURATION_PREFIXES.items()}
DYNAMICS = {"p", "pp", "ppp", "mp", "mf", "f", "ff", "fff", "sfz", "fp"}
