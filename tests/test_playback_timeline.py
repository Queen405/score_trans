from __future__ import annotations

from pathlib import Path
from fractions import Fraction
import xml.etree.ElementTree as ET

import mido

from score_trans.domain.parse.jianpu_text import parse_jianpu_scores
from score_trans.exec.render.actions import RenderActions
from score_trans.models.render.schemas import BatchRenderPageRequest, BatchRenderRequest
from score_trans.models.settings.config import ToolConfig
from score_trans.services.files.upload_service import UploadService
from score_trans.services.export.export_service import ExportService


def test_bach_batch_svg_onsets_match_midi_on_every_page(tmp_path: Path) -> None:
    text = (Path(__file__).parent / "fixtures/bach_playback_pages.jianpu").read_text(
        encoding="utf-8"
    )
    scores = parse_jianpu_scores(text)
    counts = [len(s.measures) for s in scores]
    uploads = UploadService(ToolConfig(work_dir=tmp_path))
    bodies = [
        "".join(body.splitlines(keepends=True)[1:])
        for body in text.split("// @page ")[1:]
    ]
    result = RenderActions(uploads=uploads).render_batch_a4(
        BatchRenderRequest(
            pages=[
                BatchRenderPageRequest(jianpu_text=body, source_page_index=i)
                for i, body in enumerate(bodies)
            ],
        )
    )
    midi_path = tmp_path / "bach.mid"
    ExportService().export_midi_scores(scores, midi_path)
    assert [len(s.measures) for s in scores] == counts, "MIDI export mutated the score"
    midi = mido.MidiFile(midi_path)
    track_starts = []
    for track in midi.tracks:
        tick = 0
        starts = []
        for message in track:
            tick += message.time
            if message.type == "note_on" and message.velocity:
                starts.append(tick)
        track_starts.append(starts)
    svg_starts = []
    page_ranges = []
    for page in result.pages:
        root = ET.parse(uploads.get_path(page.svg_file_id)).getroot()
        assert root.get("data-playback-version") == "1"
        start, end = page.playback_start_tick, page.playback_end_tick
        assert start is not None and end is not None and start < end
        page_ranges.append((start, end))
        for node in root.iter():
            if "playback-note" not in node.get("class", "").split():
                continue
            tick = int(node.attrib["data-playback-tick"])
            part = int(node.attrib["data-part-index"])
            assert start <= tick < end
            svg_starts.append((tick, part))
            assert tick in track_starts[part]
    assert {t for t, _ in svg_starts} == {t for track in track_starts for t in track}
    for previous, following in zip(page_ranges, page_ranges[1:]):
        assert previous[1] == following[0]
    # The user's m39 lower staff has two quarters in 3/8. Preserve it, and
    # delay BOTH parts of m41 to the shared boundary instead of drifting.
    boundary = round((40 * Fraction(3, 2) + Fraction(1, 2)) * midi.ticks_per_beat)
    assert boundary in track_starts[0] and boundary in track_starts[1]
    assert {(boundary, 0), (boundary, 1)} <= set(svg_starts)
    # Continuous batch reflow no longer requires a render-page break at a
    # source-page boundary; only playback continuity and note presence matter.
