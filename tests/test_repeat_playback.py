from __future__ import annotations

import json
from pathlib import Path

import mido

from score_trans.domain.jianpu import parse_jianpu_score
from score_trans.services.export.export_service import ExportService

PREFIX = "score-trans-playback:"


def _markers(path: Path) -> list[tuple[int, dict]]:
    tick = 0
    result = []
    for message in mido.MidiFile(path).tracks[0]:
        tick += message.time
        if message.type == "marker" and message.text.startswith(PREFIX):
            result.append((tick, json.loads(message.text[len(PREFIX) :])))
    return result


def test_repeat_midi_maps_back_to_source_onsets(tmp_path: Path) -> None:
    score = parse_jianpu_score("1=C\n4/4\n|: 1 2 3 4 :| 5 6 7 1' |")
    path = ExportService().export_midi(score, tmp_path / "repeat.mid")
    markers = _markers(path)
    assert markers, "MIDI must carry its source-position mapping"
    onsets = [
        (tick, data["score_tick"], data["score_group"])
        for tick, data in markers
        if data["kind"] == "onset"
    ]
    assert onsets == [
        (i * 480, (i if i < 4 else i - 4) * 480, i if i < 4 else i - 4)
        for i in range(12)
    ]
    measures = [
        (tick, data["score_tick"])
        for tick, data in markers
        if data["kind"] == "measure"
    ]
    assert measures == [(0, 0), (1920, 0), (3840, 1920)]
    assert len(score.measures) == 2


def test_repeat_markers_on_one_part_repeat_all_tracks(tmp_path: Path) -> None:
    lead = parse_jianpu_score("1=C\n4/4\n|: w1 :| w2 |")
    bass = parse_jianpu_score("1=C\n4/4\nw6, | w7, |")
    for i, score in enumerate([lead, bass], 1):
        score.part_index, score.part_count = i, 2
    path = ExportService().export_midi_scores([lead, bass], tmp_path / "parts.mid")
    starts = []
    for track in mido.MidiFile(path).tracks:
        tick = 0
        notes = []
        for message in track:
            tick += message.time
            if message.type == "note_on" and message.velocity:
                notes.append(tick)
        starts.append(notes)
    assert starts == [[0, 1920, 3840], [0, 1920, 3840]]


def test_text_ranges_use_document_utf16_offsets(tmp_path: Path) -> None:
    import hashlib
    from score_trans.exec.export.actions import ExportActions
    from score_trans.models.export.schemas import ExportMidiTextRequest
    from score_trans.models.settings.config import ToolConfig
    from score_trans.services.files.upload_service import UploadService

    text = '\ufeff// 😀标题\r\n// @part 1 name="Piano"\r\n1=C\r\n4/4\r\n|: 1 2 3 4 :|\r\n// @part 2 name="低音"\r\n1=C\r\n4/4\r\n0 [3+#1] [3+#1] [3+#1] & w6, |\r\n'
    uploads = UploadService(ToolConfig(work_dir=tmp_path))
    result = ExportActions(uploads=uploads).export_midi_text(
        ExportMidiTextRequest(jianpu_text=text)
    )
    markers = _markers(uploads.get_path(result.file_id))
    assert markers[0][1]["text_hash"] == hashlib.sha256(text.encode()).hexdigest()
    raw = text.encode("utf-16-le")
    onsets = {tick: data for tick, data in markers if data["kind"] == "onset"}

    def tokens(tick: int) -> list[str]:
        return [
            raw[r["start"] * 2 : r["end"] * 2].decode("utf-16-le")
            for r in onsets[tick]["ranges"]
        ]

    assert tokens(0) == ["1", "w6,"]
    assert tokens(480) == ["2", "[3+#1]"]
    assert onsets[1920] == onsets[0]


def test_repeat_rest_and_tempo_mapping(tmp_path: Path) -> None:
    from fractions import Fraction
    from score_trans.models.score import Event, JianpuPitch, JianpuScore, Measure

    score = JianpuScore(
        tempo=120,
        measures=[
            Measure(
                "1",
                duration=Fraction(4),
                repeat_start=True,
                events=[Event(kind="rest", duration=Fraction(4))],
            ),
            Measure(
                "2",
                duration=Fraction(4),
                repeat_end=True,
                tempo=60,
                events=[
                    Event(kind="note", duration=Fraction(4), pitches=[JianpuPitch(1)])
                ],
            ),
        ],
    )
    path = ExportService().export_midi(score, tmp_path / "tempo.mid")
    visits = [
        (tick, d["score_tick"], d["end_tick"])
        for tick, d in _markers(path)
        if d["kind"] == "measure"
    ]
    assert visits == [
        (0, 0, 1920),
        (1920, 1920, 3840),
        (3840, 0, 5760),
        (5760, 1920, 7680),
    ]
    tick = 0
    tempos = []
    for m in mido.MidiFile(path).tracks[0]:
        tick += m.time
        if m.type == "set_tempo":
            tempos.append((tick, round(mido.tempo2bpm(m.tempo))))
    assert tempos == [(0, 120), (1920, 60), (3840, 120), (5760, 60)]


def test_repeat_counts_conflict_is_reported(tmp_path: Path) -> None:
    import pytest

    scores = [parse_jianpu_score("1=C\n4/4\n|: w1 :|") for _ in range(2)]
    for i, score in enumerate(scores, 1):
        score.part_index, score.part_count = i, 2
        score.measures[0].repeat_count = i + 1
    with pytest.raises(ValueError, match="反复次数不一致"):
        ExportService().export_midi_scores(scores, tmp_path / "conflict.mid")


def test_full_fixture_repeat_groups_match_svg_and_source_ranges(tmp_path: Path) -> None:
    import xml.etree.ElementTree as ET
    from score_trans.domain.parse.jianpu_text import parse_jianpu_parts
    from score_trans.services.render.engraving.renderer import PublicationRenderer
    from score_trans.exec.export.actions import ExportActions
    from score_trans.models.export.schemas import ExportMidiTextRequest
    from score_trans.models.settings.config import ToolConfig
    from score_trans.services.files.upload_service import UploadService

    text = (Path(__file__).parent / "fixtures/piano_polyphonic.jianpu").read_text(
        encoding="utf-8"
    )
    scores = [p.score for p in parse_jianpu_parts(text)]
    svg_groups = {}
    for page in PublicationRenderer().render_scores(scores):
        for node in ET.fromstring(page.svg).iter():
            if "data-note-group" in node.attrib:
                svg_groups[int(node.attrib["data-playback-tick"])] = int(
                    node.attrib["data-note-group"]
                )
    uploads = UploadService(ToolConfig(work_dir=tmp_path))
    result = ExportActions(uploads=uploads).export_midi_text(
        ExportMidiTextRequest(jianpu_text=text)
    )
    midi = mido.MidiFile(uploads.get_path(result.file_id))
    actual = set()
    for track in midi.tracks:
        tick = 0
        for msg in track:
            tick += msg.time
            if msg.type == "note_on" and msg.velocity:
                actual.add(tick)
    markers = _markers(uploads.get_path(result.file_id))
    onsets = [(t, d) for t, d in markers if d["kind"] == "onset"]
    assert {t for t, _ in onsets} == actual
    assert len(onsets) == 2 * len(svg_groups)
    for _, data in onsets:
        assert svg_groups[data["score_tick"]] == data["score_group"]
        assert data["ranges"]
        for r in data["ranges"]:
            token = text.encode("utf-16-le")[r["start"] * 2 : r["end"] * 2].decode(
                "utf-16-le"
            )
            assert token.strip() and not token.startswith("//")


def test_repeat_counts_and_adjacent_sections_preserve_source_indices() -> None:
    from score_trans.domain.playback_timeline import playback_visits

    cases = [
        ("w1 :| w2 |", [0, 0, 1]),
        ("|: w1 :| *3 w2 |", [0, 0, 0, 1]),
        ("|: w1 :| |: w2 :| w3 |", [0, 0, 1, 1, 2]),
    ]
    for body, expected in cases:
        score = parse_jianpu_score("1=C\n4/4\n" + body)
        visits = playback_visits([[m] for m in score.measures])
        assert [v.source_index for v in visits] == expected


def test_repeat_can_return_across_source_pages(tmp_path: Path) -> None:
    from score_trans.domain.parse.jianpu_text import parse_jianpu_scores

    text = '// @page 1\n// @part 1 name="Piano"\n1=C\n4/4\n|: w1 |\n// @page 2\n// @part 1 name="Piano"\n1=C\n4/4\nw2 :| w3 |'
    scores = parse_jianpu_scores(text)
    path = ExportService().export_midi_scores(scores, tmp_path / "pages.mid")
    visits = [d["source_index"] for _, d in _markers(path) if d["kind"] == "measure"]
    assert visits == [0, 1, 0, 1, 2]
