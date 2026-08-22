# Jianpu Geometry Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Each task must complete its own failing-test, implementation, and verification cycle.

**Goal:** Make Jianpu rendering geometry truthful and collision-aware for event-local marks, lyrics, dynamics, cross-event spans, system text, and render-map/QA diagnostics.

**Architecture:** Keep event-local geometry separate from cross-event span geometry and system-level text lanes. `EventLayout` remains the source of truth for one event; new span layout records describe beams, hooks, tuplets, ties, slurs, and slides; system layout consumes both before drawing. Render-map bboxes and geometry QA consume the same records instead of reconstructing geometry from unrelated constants.

**Tech Stack:** Python 3.13, dataclasses, `Fraction`, deterministic SVG scene graph, pytest, Vue 3/TypeScript for cache-version compatibility, Audiveris Java only when provenance interfaces are affected.

**Spec:** Current audit findings in this conversation and `docs/syntax-investigation-report.md`.

## Global Constraints

- Do not change Jianpu text syntax, MusicXML request schemas, or API route semantics.
- Preserve existing dirty-worktree changes; do not revert unrelated user changes.
- Keep `models/` independent of project modules and preserve the project import-layer rules.
- Use `PublicationStyle` for new tunable geometry values; do not add new magic numbers to renderer functions.
- Run Python tests with a writable workspace data/temp directory, for example `SCORE_TRANS_DATA_DIR=work/geometry-data` and `--basetemp=work/pytest-geometry`.
- Because SVG geometry changes, publish the next renderer version as `publication-4` and update all cache/history compatibility checks together.
- Keep diagnostics non-fatal for normal rendering; an intentional diagnostic must not make a valid score fail to render.

## Files and Responsibilities

- Modify `backend/score_trans/services/render/engraving/geometry.py`: event-local ink boxes, mark placement, adaptive lyric/dynamic lanes, and shared attachment helpers.
- Modify `backend/score_trans/services/render/engraving/renderer.py`: span layout, system occupancy, drawing metadata, text placement, and renderer-version use.
- Modify `backend/score_trans/services/render/engraving/scene.py` and `qa.py`: geometry records, recursive diagnostics, and render-map consistency.
- Modify `backend/score_trans/services/render/engraving/style.py`: geometry constants only.
- Modify `tests/test_render.py` and `tests/test_render_qa.py`: focused geometry regressions.
- Modify `tests/test_convert.py` and `tests/test_provenance.py`: nested/cross-measure tuplet and source-map regressions.
- Synchronize `svg_backend.py`, history/render models, history DAO, `ConvertView.vue`, `useHistoryRestore.ts`, and generated `desktop/src/renderer/src/models/openapi.ts` for `publication-4`.

### Task 1: Establish Geometry Contracts and P0 Regression Tests

**Files:**
- Modify: `tests/test_render.py`
- Modify: `tests/test_render_qa.py`
- Modify: `backend/score_trans/services/render/engraving/geometry.py`
- Modify: `backend/score_trans/services/render/engraving/style.py`

**Interfaces:**
- Add tests against the existing `measure_event_layout(event, style)` and `measure_event_ink(event, style)` interfaces.
- Define the invariant: every event-local primitive drawn by `_draw_event()` must be inside its measured `EventLayout.ink_box`, unless the test explicitly marks it as an intentional overflow diagnostic.

- [ ] Write failing tests for:
  - one event whose lyric width exceeds available measure width;
  - a four-row chord with low-octave dots and both lyric and dynamic;
  - `scoop` plus a long accidental;
  - multiple above/left/right marks on one chord;
  - duplicate event lyric plus `TextBlock(role="lyric")`.
- [ ] Run only those tests and record the expected failures.
- [ ] Add a single shared helper for event attachment top/bottom and rhythm-line offset. The helper must include pitch rows, accidentals, octave dots, rhythm lines, dynamic, and lyric lanes in the same coordinate system.
- [ ] Make lyric placement use the measured event bottom plus `style.lyric_clearance`; make dynamic placement use the measured attachment bottom plus `style.dynamic_clearance`.
- [ ] Make the event-position fallback keep an overwide event anchor within the available content center instead of moving the note itself outside the page. Its bbox must remain truthful even when the content cannot fit.
- [ ] Make `_draw_measure_text()` skip a lyric block when the same text is already attached to an event in that measure, preventing MusicXML/Jianpu lyric duplication.
- [ ] Run the focused tests and confirm they pass.

### Task 2: Replace Fixed Mark Placement with Collision-Aware Event Layout

**Files:**
- Modify: `backend/score_trans/services/render/engraving/geometry.py`
- Modify: `backend/score_trans/services/render/engraving/style.py`
- Modify: `backend/score_trans/services/render/engraving/renderer.py`
- Test: `tests/test_render.py`

**Interfaces:**
- Keep `mark_layouts(event, style) -> tuple[MarkLayout, ...]` as the public internal boundary.
- `MarkLayout.ink_box` must be the final position, not an estimate based on a fixed `-24/+24` offset.

- [ ] Write failing tests asserting that every mark box is disjoint from the event note/accidental boxes and from other marks, except explicitly allowed stacked marks.
- [ ] For left marks, place the mark using the measured left edge of the widest accidental/note group plus the mark width and `style.mark_clearance`; for right marks, place it after the widest duration-dot/extension geometry.
- [ ] For above marks, stack from the actual attachment top and use each mark's measured ink height plus `style.mark_stack_gap`, not label-length heuristics.
- [ ] Preserve the distinct staccato triangle geometry and give its `MarkLayout.ink_box` the exact triangle bounds.
- [ ] Add tests for `scoop`, `plop`, long accidental text, fermata, accent, staccato, and two simultaneous above marks.
- [ ] Run all mark/chord/octave render tests.

### Task 3: Introduce First-Class Span Geometry

**Files:**
- Modify: `backend/score_trans/services/render/engraving/scene.py`
- Modify: `backend/score_trans/services/render/engraving/geometry.py`
- Modify: `backend/score_trans/services/render/engraving/renderer.py`
- Test: `tests/test_render.py`

**Interfaces:**
- Add an internal immutable `SpanLayout` record containing `kind`, `bbox`, `source_ids`, and `continuation` metadata.
- Define `SpanLayout` as `kind: str`, `bbox: BBox`, `source_ids: tuple[str, ...]`, `continuation: Literal["none", "start", "end"]`, and `allow_overlap: bool = False`.
- Add deterministic helpers:
  - `_rhythm_run_layout(anchors, level, baseline, style) -> SpanLayout`
  - `_beam_hook_layout(anchor, level, direction, baseline, style) -> SpanLayout`
  - `_spanner_layout(kind, start, end, style) -> SpanLayout`
  - `_tuplet_layout(group, span_id, style) -> SpanLayout`
- Drawing helpers must consume the layout record and attach `data-bbox` and source metadata to the emitted SVG node.

- [ ] Write failing tests for beam hooks extending into a neighboring compressed event, slur/tuplet vertical intersection, tie/mark intersection, and slide endpoint bounds.
- [ ] Move all hook extents, spanner heights, slide terminal offsets, and span clearance values into `PublicationStyle`.
- [ ] Calculate conservative cubic-path bboxes from the same control points used to build SVG `d` attributes.
- [ ] Register span bboxes in `PublicationScene.source_boxes` for every source ID represented by the span.
- [ ] Keep event bboxes event-local; do not inflate every participating event by the full span rectangle.
- [ ] Add tests that verify `data-bbox` matches the generated line/path geometry and that hooks are clipped only at measure limits, not silently at event limits.
- [ ] Run all beam, tie, slur, slide, tuplet, and render-map tests.

### Task 4: Correct Tuplet Span Semantics

**Files:**
- Modify: `backend/score_trans/services/render/engraving/renderer.py`
- Modify: `backend/score_trans/domain/parse/musicxml.py` only if a parser invariant is required
- Test: `tests/test_convert.py`
- Test: `tests/test_render.py`

**Interfaces:**
- Add `_event_tuplet_spans(event) -> tuple[TupletSpan, ...]` as the single renderer-facing accessor.
- `_draw_tuplets()` must group each span ID independently, including nested spans; `tuplet_id` remains a compatibility shortcut for the primary span.

- [ ] Add a failing render test for nested same-number tuplets and a cross-measure tuplet.
- [ ] Preserve all parsed `TupletSpan` instances; never infer that `tuplet_id` represents the complete span set.
- [ ] Assign nested bracket lanes deterministically from outermost to innermost, with `style.tuplet_stack_gap` between brackets/numbers.
- [ ] Render partial continuation brackets at measure/system boundaries, with source metadata retained on each segment.
- [ ] Keep rhythm lines suppressed only for events belonging to a real tuplet span, and test that a manually constructed span-only event gets a bracket or a deterministic diagnostic rather than silently losing both representations.
- [ ] Run parser round-trip tests and all tuplet render tests.

### Task 5: Make Text and System Lanes Content-Aware

**Files:**
- Modify: `backend/score_trans/services/render/engraving/renderer.py`
- Modify: `backend/score_trans/services/render/engraving/geometry.py`
- Modify: `backend/score_trans/services/render/engraving/style.py`
- Test: `tests/test_render.py`

**Interfaces:**
- Add `_measure_text_layout(measure, x, width, y, style) -> list[TextLayout]` for unpositioned text blocks.
- Define `TextLayout` as `text: str`, `bbox: InkBox`, `role: str`, `lane_index: int`, `font_size: float`, and `source_ids: tuple[str, ...]`.

- [ ] Add failing tests for long unpositioned text, `TextBlock.start`, custom `font_size`, multiple text rows, and text adjacent to lyrics/dynamics.
- [ ] Position a block with `start` relative to the measure event timeline; center only blocks without a usable start.
- [ ] Measure actual font ink bounds and width; do not use `index * 19` as the height model.
- [ ] Allocate separate lanes for event lyric, event dynamic, and measure-level text. Preserve their existing semantic roles and source anchors.
- [ ] Add measured text bboxes to the scene and render map when source IDs are available.
- [ ] Update `_system_extra_height()` to consume text/span/event layout extents rather than independent booleans and fixed row counts.
- [ ] Run text, lyric, dynamic, pagination, and multi-part tests.

### Task 6: Expand Geometry QA and Render-Map Truthfulness

**Files:**
- Modify: `backend/score_trans/services/render/engraving/qa.py`
- Modify: `backend/score_trans/services/render/engraving/scene.py`
- Modify: `backend/score_trans/services/render/engraving/renderer.py`
- Test: `tests/test_render_qa.py`
- Test: `tests/test_provenance.py`

**Interfaces:**
- Define `GeometryRecord` in `scene.py` with `owner: str`, `kind: str`, `bbox: BBox`, `classes: tuple[str, ...]`, `source_ids: tuple[str, ...]`, and `allow_overlap: bool = False`.
- Extend `GeometryIssue` with `owner: str | None`, while keeping existing `kind/classes/bbox` fields compatible.
- Add `PublicationScene.geometry_records: list[GeometryRecord]` and `geometry_issues: list[GeometryIssue]`; include diagnostics in the internal render-map payload without changing API request/response schemas.

- [ ] Write failing QA tests for text/path/circle/line overflow, event-local mark collision, span/event collision, and render-map bbox mismatch.
- [ ] Make `_node_bbox()` handle all generated visible primitives through explicit geometry metadata; do not parse arbitrary SVG path strings at QA time.
- [ ] Recurse into nested scene nodes while excluding parent/child double counting.
- [ ] Compare only incompatible geometry kinds: note vs mark, mark vs mark, lyric/dynamic vs note, span vs tuplet/mark, and text vs neighboring measure content. Allow intentional note/own-attachment containment.
- [ ] Invoke QA once after each page is fully drawn. Log diagnostics non-fatally and expose them only in the internal render map.
- [ ] Verify `source_boxes` includes event-local and span-local source geometry without replacing the event anchor bbox with an unrelated full-span rectangle.
- [ ] Run render QA, provenance, and render-map tests.

### Task 7: Consolidate Style Constants and Version Compatibility

**Files:**
- Modify: `backend/score_trans/services/render/engraving/style.py`
- Modify: all renderer/geometry call sites that use the migrated constants
- Modify: `backend/score_trans/services/render/engraving/svg_backend.py`
- Modify: history/render schemas, entities, DAO, `desktop/src/renderer/src/views/ConvertView.vue`, `desktop/src/renderer/src/composables/useHistoryRestore.ts`, and generated `desktop/src/renderer/src/models/openapi.ts`
- Test: `tests/test_render.py`, `tests/test_history_service.py`, frontend type/API checks

**Interfaces:**
- Publish `PublicationRenderer.engine_version = "publication-4"`.
- Keep all existing request models and rendering entry points unchanged.

- [ ] Add style fields for event baseline, lyric/dynamic/text clearances, mark stacking, beam hook extent, span heights, tuplet stacking, and system text gap.
- [ ] Replace duplicated literals in `_draw_measure`, `_measure_bar_offsets`, `_system_extra_height`, `_draw_measure_text`, `_draw_explicit_beam_level`, `_spanner`, `_draw_tuplets`, and geometry helpers.
- [ ] Update SVG metadata, persistence defaults, DAO writes, history restore checks, and generated OpenAPI defaults atomically.
- [ ] Add a compatibility test proving `publication-3` history pages are rebuilt and `publication-4` pages are reused.
- [ ] Run `pnpm check:api-types` or regenerate/check the OpenAPI type output, then run `vue-tsc`.

### Task 8: Final Verification and Acceptance Gate

**Files:**
- No production files; verification only.

- [ ] Run focused geometry tests with a writable workspace temp directory.
- [ ] Run `python -m pytest --basetemp=work/pytest-geometry` with `SCORE_TRANS_DATA_DIR=work/geometry-data`.
- [ ] Run `python -m compileall -q backend tests`.
- [ ] Run `pnpm typecheck`, `pnpm lint`, `pnpm test:utils`, and `pnpm check:api-types` from `desktop/`.
- [ ] Run `JAVA_HOME=.../JDK25 ./gradlew :app:compileJava --no-daemon` from `third_party/audiveris` because provenance exporter code is touched.
- [ ] Run `git diff --check` and verify no generated/cache artifacts are tracked.

Acceptance requires:

- No event-local visible primitive lies outside its truthful event layout bbox.
- No long single event is silently moved off-page or represented by a clipped false bbox.
- Lyrics are rendered once and do not overlap chord rows, dynamics, or measure text.
- Left/right/above marks avoid note, accidental, duration, and other mark geometry.
- Beam hooks, tuplets, ties, slurs, and slides have explicit span geometry and diagnostics.
- Nested and cross-measure tuplet spans remain visible and source-addressable.
- Render-map bboxes match the geometry used to draw the SVG.
- Existing API behavior and Jianpu syntax remain compatible.

## Self-Review

- P0 user-visible defects are covered by Tasks 1, 2, and 5.
- Cross-event geometry is handled separately in Tasks 3 and 4 rather than inflated into event bboxes.
- QA and render-map consistency are explicitly covered by Task 6.
- Version/cache compatibility is isolated in Task 7.
- Every production task has focused tests before implementation and a full verification gate in Task 8.
