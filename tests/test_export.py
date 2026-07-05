from __future__ import annotations

import xml.etree.ElementTree as ET

import mido
import pytest

from score_trans.domain.jianpu import jianpu_to_musicxml, parse_jianpu_score
from score_trans.exec.export.actions import ExportActions
from score_trans.models.export.schemas import (
    ExportMidiTextRequest,
    ExportMusicXmlRequest,
    ExportMusicXmlTextRequest,
    ExportResponse,
)
from score_trans.services.export.export_service import ExportService
from score_trans.services.files.upload_service import UploadService


def test_export_service_writes_musicxml(tmp_path) -> None:
    xml_text = jianpu_to_musicxml("1=C\n4/4\n1 2 3 4 |")
    output_path = tmp_path / "out.musicxml"

    from score_trans.domain.musicxml import musicxml_to_score

    score = musicxml_to_score(xml_text)
    ExportService().export_musicxml(score, output_path, title="Test Score")

    assert output_path.exists()
    written = output_path.read_text(encoding="utf-8")
    assert '<?xml version="1.0"' in written
    assert "<score-partwise" in written
    assert "<work-title>Test Score</work-title>" in written


def test_export_musicxml_text_from_jianpu() -> None:
    actions = ExportActions(uploads=UploadService())
    req = ExportMusicXmlTextRequest(
        jianpu_text="title=测试\n1=G\n3/4\n1 2 3 |",
        filename="test.musicxml",
    )

    resp = actions.export_musicxml_text(req)

    assert isinstance(resp, ExportResponse)
    assert resp.filename == "test.musicxml"
    path = actions.uploads.get_path(resp.file_id)
    assert path is not None and path.exists()
    written = path.read_text(encoding="utf-8")
    assert "<work-title>测试</work-title>" in written
    assert "<fifths>1</fifths>" in written


def test_export_musicxml_from_file_id(tmp_path) -> None:
    uploads = UploadService()
    original = tmp_path / "original.musicxml"
    original.write_text(jianpu_to_musicxml("1=C\n4/4\n1 2 3 4 |"), encoding="utf-8")
    file_id = uploads.register(original)

    actions = ExportActions(uploads=uploads)
    req = ExportMusicXmlRequest(
        musicxml_file_id=file_id,
        target_key="D",
        filename="transposed.musicxml",
    )

    resp = actions.export_musicxml(req)

    assert resp.filename == "transposed.musicxml"
    path = uploads.get_path(resp.file_id)
    assert path is not None and path.exists()
    written = path.read_text(encoding="utf-8")
    assert "<fifths>2</fifths>" in written


def test_text_exports_preserve_multi_part_structure() -> None:
    uploads = UploadService()
    actions = ExportActions(uploads=uploads)
    text = (
        '// @part 1 name="高音"\n1=C\n4/4\n1 2 3 4 |\n'
        '// @part 2 name="低音"\n1=C\n4/4\n5 6 7 1\' |'
    )

    xml_response = actions.export_musicxml_text(
        ExportMusicXmlTextRequest(jianpu_text=text, title="双声部")
    )
    xml_path = uploads.get_path(xml_response.file_id)
    assert xml_path is not None
    root = ET.fromstring(xml_path.read_text(encoding="utf-8"))
    assert len(root.findall("./part-list/score-part")) == 2
    assert len(root.findall("./part")) == 2

    midi_response = actions.export_midi_text(
        ExportMidiTextRequest(jianpu_text=text, title="双声部")
    )
    midi_path = uploads.get_path(midi_response.file_id)
    assert midi_path is not None
    midi = mido.MidiFile(midi_path)
    assert len(midi.tracks) == 2


def test_multi_page_midi_merges_parts_across_pages(tmp_path) -> None:
    uploads = UploadService()
    actions = ExportActions(uploads=uploads)
    text = (
        '// @page 1 start=auto name="p1.png"\n'
        '// @part 1 name="Voice"\n1=C\n4/4\n1 2 3 4 |\n'
        '// @part 2 name="Piano"\n1=C\n4/4\n5 6 7 1\' |\n'
        '// @page 2 start=auto name="p2.png"\n'
        '// @part 1 name="Voice"\n1=C\n4/4\n2 3 4 5 |\n'
        '// @part 2 name="Piano"\n1=C\n4/4\n6 7 1\' 2\' |'
    )

    midi_response = actions.export_midi_text(
        ExportMidiTextRequest(jianpu_text=text, title="多页多声部")
    )
    midi_path = uploads.get_path(midi_response.file_id)
    assert midi_path is not None
    midi = mido.MidiFile(midi_path)
    assert len(midi.tracks) == 2

    for track in midi.tracks:
        abs_time = 0
        note_times: list[int] = []
        for msg in track:
            abs_time += msg.time
            if msg.type == "note_on" and msg.velocity > 0:
                note_times.append(abs_time)
        assert len(note_times) == 8, f"Track {track.name}: expected 8 notes, got {len(note_times)}"
        assert note_times[3] < note_times[4], (
            f"Track {track.name}: page 2 notes must start after page 1 ends, "
            f"got {note_times[3]} -> {note_times[4]}"
        )


def test_midi_export_rejects_microtones_without_pitch_bend(tmp_path) -> None:
    score = parse_jianpu_score("1=C\n4/4\nqs1 2 3 4 |")
    output_path = tmp_path / "microtonal.mid"

    with pytest.raises(ValueError, match="pitch bend"):
        ExportService().export_midi(score, output_path)

    assert not output_path.exists()


def _midi_tempo_bpm(midi: mido.MidiFile) -> float:
    """从 track 0 的 set_tempo meta 解析 BPM（mido 转换有浮点误差，调用方用 approx 比较）。"""
    for msg in midi.tracks[0]:
        if msg.type == "set_tempo":
            return mido.tempo2bpm(msg.tempo)
    raise AssertionError("no set_tempo meta in track 0")


def test_midi_export_tempo_auto_uses_score_tempo(tmp_path) -> None:
    """midi_tempo='auto' 且简谱含 ♩=60 时，导出 BPM=60。"""
    score = parse_jianpu_score("1=C\ntempo=60\n4/4\n1 2 3 4 |")
    output_path = tmp_path / "auto_with_tempo.mid"
    ExportService().export_midi_scores([score], output_path, midi_tempo="auto")

    midi = mido.MidiFile(output_path)
    assert _midi_tempo_bpm(midi) == pytest.approx(60)


def test_midi_export_tempo_auto_falls_back_to_default(tmp_path) -> None:
    """midi_tempo='auto' 且简谱无 tempo 标记时，回退到 MIDI_DEFAULT_BPM。"""
    from score_trans.config.settings import MIDI_DEFAULT_BPM

    score = parse_jianpu_score("1=C\n4/4\n1 2 3 4 |")
    output_path = tmp_path / "auto_no_tempo.mid"
    ExportService().export_midi_scores([score], output_path, midi_tempo="auto")

    midi = mido.MidiFile(output_path)
    assert _midi_tempo_bpm(midi) == pytest.approx(MIDI_DEFAULT_BPM)


def test_midi_export_tempo_manual_overrides_score_tempo(tmp_path) -> None:
    """midi_tempo=144 时强制使用 144，忽略简谱中的 ♩=60。"""
    score = parse_jianpu_score("1=C\ntempo=60\n4/4\n1 2 3 4 |")
    output_path = tmp_path / "manual.mid"
    ExportService().export_midi_scores([score], output_path, midi_tempo=144)

    midi = mido.MidiFile(output_path)
    assert _midi_tempo_bpm(midi) == pytest.approx(144)


def test_midi_export_tempo_only_on_track0(tmp_path) -> None:
    """set_tempo 仅写在 track 0，非首 track 不写（符合 MIDI 规范）。"""
    text = (
        '// @part 1 name="高音"\n1=C\n4/4\n1 2 3 4 |\n'
        '// @part 2 name="低音"\n1=C\n4/4\n5 6 7 1\' |'
    )
    actions = ExportActions(uploads=UploadService())
    resp = actions.export_midi_text(
        ExportMidiTextRequest(jianpu_text=text, midi_tempo=90)
    )
    midi_path = actions.uploads.get_path(resp.file_id)
    assert midi_path is not None
    midi = mido.MidiFile(midi_path)

    assert len(midi.tracks) == 2
    tempo_msgs = [
        msg for track in midi.tracks for msg in track if msg.type == "set_tempo"
    ]
    assert len(tempo_msgs) == 1, "set_tempo 应仅出现一次（track 0）"
    assert _midi_tempo_bpm(midi) == pytest.approx(90)


def test_midi_export_writes_time_signature(tmp_path) -> None:
    """track 0 写入 time_signature meta，拍号从 score 读取。"""
    score_44 = parse_jianpu_score("1=C\n4/4\n1 2 3 4 |")
    output_44 = tmp_path / "ts_44.mid"
    ExportService().export_midi_scores([score_44], output_44)
    midi_44 = mido.MidiFile(output_44)
    ts_msgs = [m for m in midi_44.tracks[0] if m.type == "time_signature"]
    assert len(ts_msgs) == 1
    assert ts_msgs[0].numerator == 4
    assert ts_msgs[0].denominator == 4

    # 3/8 拍号
    score_38 = parse_jianpu_score("1=C\n3/8\n1 2 3 |")
    output_38 = tmp_path / "ts_38.mid"
    ExportService().export_midi_scores([score_38], output_38)
    midi_38 = mido.MidiFile(output_38)
    ts_38 = [m for m in midi_38.tracks[0] if m.type == "time_signature"]
    assert len(ts_38) == 1
    assert ts_38[0].numerator == 3
    assert ts_38[0].denominator == 8


def test_export_midi_route_accepts_target_key_and_tempo(tmp_path) -> None:
    """/export/midi 接受 ExportMidiRequest，传 target_key 和 midi_tempo。"""
    from score_trans.models.export.schemas import ExportMidiRequest

    uploads = UploadService()
    original = tmp_path / "original.musicxml"
    original.write_text(jianpu_to_musicxml("1=C\n4/4\n1 2 3 4 |"), encoding="utf-8")
    file_id = uploads.register(original)

    actions = ExportActions(uploads=uploads)
    req = ExportMidiRequest(
        musicxml_file_id=file_id,
        target_key="G",
        midi_tempo=100,
        filename="test.mid",
    )
    resp = actions.export_midi(req)

    assert resp.filename == "test.mid"
    midi_path = uploads.get_path(resp.file_id)
    assert midi_path is not None and midi_path.exists()
    midi = mido.MidiFile(midi_path)
    assert _midi_tempo_bpm(midi) == pytest.approx(100)
