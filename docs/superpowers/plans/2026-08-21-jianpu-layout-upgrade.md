# Jianpu Layout Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve the current `publication-2` Jianpu renderer's deterministic spacing and collision behavior while preserving its public APIs, source provenance, and musical semantics.

**Architecture:** Keep `PublicationRenderer` as the only engraving engine. Introduce a shared visual-geometry calculation used by intrinsic measure sizing, event placement, and drawing; then add protected measure gutters, dynamic vertical extents, and bounded notation primitives. Defer data-model-dependent features such as multi-verse lyrics and mid-measure breaks until their contracts are specified.

**Tech Stack:** Python 3.13, dataclasses, `fontTools`, deterministic SVG scene graph, pytest, Ruff.

**Spec:** `docs/jianpu-layout-research-and-upgrade-plan.md` plus the approved scope revision in the conversation.

## Global Constraints

- Preserve `publication-2`, public render function signatures, existing CSS classes, `data-*` attributes, source IDs, and render-map version compatibility.
- Do not silently split or mutate invalid overfull musical events.
- Use bundled fonts and deterministic `fontTools` measurements; do not depend on browser metrics.
- Keep multi-verse lyrics, phrase breaking, themes, and mid-measure breaks out of the first geometry delivery.
- Run `tests/test_render.py`, the full pytest suite, Ruff checks, and `git diff --check` at each delivery checkpoint.

### Task 1: Establish deterministic layout fixtures and geometry assertions

**Files:**
- Create: `tests/fixtures/render_cases.py`
- Modify: `tests/test_render.py`

**Interfaces:**
- Produce fixture builders returning `JianpuScore` instances for accidental clearance, dense chords, low-octave dots, staccato, long durations, measure attributes, and tie/slur cases.
- Produce XML helper assertions that inspect scene groups, primitive nodes, and `data-bbox` values instead of brittle full-SVG strings.

- [ ] **Step 1: Write failing tests** for a protected barline gap, bounded staccato circle, chord row spacing, and duration-line clearance.
- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/test_render.py -q`; record the expected failures without changing existing tests yet.
- [ ] **Step 3: Add only fixture builders and assertion helpers**, keeping each case independent of historical `work/` files.
- [ ] **Step 4: Re-run** the focused tests and confirm only behavior assertions fail.
- [ ] **Step 5: Commit** with `test: 建立简谱布局几何基线`.

### Task 2: Add deterministic font ink bounds

**Files:**
- Modify: `backend/score_trans/services/render/engraving/fonts.py`
- Modify: `tests/test_render.py`

**Interfaces:**
- Add `FontRegistry.ink_bounds(text: str, font_size: float) -> tuple[float, float, float, float]`.
- Cache bounds by `(font_family, text, font_size)` and retain existing `measure()` behavior.

- [ ] **Step 1: Write a failing test** asserting non-zero bounds for `1`, `♯`, `●`, and a Chinese lyric string and stable repeated results.
- [ ] **Step 2: Run** the single font test and verify `AttributeError` or equivalent failure.
- [ ] **Step 3: Implement** outline measurement with `BoundsPen`, scaling font units to the requested size, returning `(left, top, right, bottom)` in the existing baseline coordinate convention.
- [ ] **Step 4: Run** the font test and `tests/test_render.py`.
- [ ] **Step 5: Commit** with `feat: 增加确定性字形墨迹边界测量`.

### Task 3: Introduce shared visual event geometry

**Files:**
- Create: `backend/score_trans/services/render/engraving/geometry.py`
- Modify: `backend/score_trans/services/render/engraving/renderer.py`
- Modify: `backend/score_trans/services/render/engraving/style.py`
- Modify: `tests/test_render.py`

**Interfaces:**
- Add frozen geometry DTOs `InkBox`, `VisualPart`, and `EventLayout`.
- Add `measure_event_layout(event, style) -> EventLayout` and `measure_event_ink(event, style) -> InkBox` as pure functions.
- Add style defaults for `barline_gutter`, `event_clearance`, `accidental_clearance`, `chord_gap`, `staccato_radius`, and `tie_clearance`.

- [ ] **Step 1: Write failing tests** for identical extents from intrinsic sizing and drawing, plus no adjacent event overlap under the existing synthetic cases.
- [ ] **Step 2: Run** the focused geometry tests and confirm current fixed formulas fail at least one case.
- [ ] **Step 3: Implement** geometry parts for note ink, accidentals, octave dots, duration tokens, rhythm lines, lyrics, dynamics, and marks; use `ink_bounds()` for text parts and keep conservative geometric bounds for paths/circles.
- [ ] **Step 4: Replace `_event_visual_extents()` and intrinsic-width approximations** with the shared result while preserving function-level compatibility where existing tests import helpers.
- [ ] **Step 5: Run** `tests/test_render.py` and inspect generated SVG for unchanged source attributes.
- [ ] **Step 6: Commit** with `refactor: 统一简谱事件视觉几何计算`.

### Task 4: Protect barlines and repair horizontal event placement

**Files:**
- Modify: `backend/score_trans/services/render/engraving/renderer.py`
- Modify: `backend/score_trans/services/render/engraving/style.py`
- Modify: `tests/test_render.py`

**Interfaces:**
- `_draw_measure()` computes `content_left` and `content_right` from style gutters and attribute width.
- `_event_positions()` returns positions satisfying each event's measured left/right ink bounds and minimum clearance, without global left-shifting that causes left overflow.

- [ ] **Step 1: Add failing tests** for dense accidentals at both measure edges and an attribute-bearing measure.
- [ ] **Step 2: Run** those tests and capture the offending bbox relationships.
- [ ] **Step 3: Implement** left-to-right constraint placement, bounded elastic gap distribution, and a diagnostic flag when content cannot fit; retain measure width/reflow as the next layer rather than clipping musical content.
- [ ] **Step 4: Run** all render tests and verify barline positions remain unchanged for ordinary measures.
- [ ] **Step 5: Commit** with `fix: 为简谱小节线增加事件保护区`.

### Task 5: Repair notation primitives and vertical occupancy

**Files:**
- Modify: `backend/score_trans/services/render/engraving/renderer.py`
- Modify: `backend/score_trans/services/render/engraving/geometry.py`
- Modify: `tests/test_render.py`

**Interfaces:**
- `_draw_duration()` uses a `duration_tokens(event, measure)` helper based on exact `Fraction` decomposition, not `ceil()` alone.
- Staccato is emitted as a bounded `circle` node with existing mark/source metadata.
- `_spanner()` gives ties a preferred upper route with collision-aware fallback; slurs retain their existing independent route.

- [ ] **Step 1: Add failing tests** for dotted/long durations, staccato radius, tie placement, and low-octave-dot-to-rhythm-line clearance.
- [ ] **Step 2: Run** the focused tests and confirm current text staccato/fixed extension behavior fails.
- [ ] **Step 3: Implement** exact duration tokenization for supported notation, preserving validation errors for unsupported or overfull events.
- [ ] **Step 4: Replace only the staccato renderer** with `_circle()` and preserve `data-mark="staccato"` and source roles.
- [ ] **Step 5: Use measured chord rows and vertical rungs** for marks, octave dots, rhythm lines, and ties.
- [ ] **Step 6: Run** focused and full render tests; update only assertions whose visual change is intentional.
- [ ] **Step 7: Commit** with `fix: 修复简谱记号和弦与连线占位`.

### Task 6: Make system height and pagination content-aware

**Files:**
- Modify: `backend/score_trans/services/render/engraving/renderer.py`
- Modify: `backend/score_trans/services/render/engraving/style.py`
- Modify: `tests/test_render.py`

**Interfaces:**
- `_system_extra_height()` derives top and bottom extents from measured event/layout parts and existing spanners.
- `_paginate()` consumes those heights without changing page-range or note-index semantics.

- [ ] **Step 1: Add failing tests** for dense marks, low octave dots, lyrics plus dynamics, and multi-page bottom bounds.
- [ ] **Step 2: Run** the tests and confirm fixed `base_staff_height` extras are insufficient.
- [ ] **Step 3: Implement** measured top/bottom extents and minimum system gap; keep ordinary simple-score output stable where no extra content exists.
- [ ] **Step 4: Run** render tests, full pytest, Ruff, and `git diff --check`.
- [ ] **Step 5: Commit** with `fix: 让简谱系统行高随内容计算`.

### Task 7: Add structural QA report without making it a hard gate

**Files:**
- Create: `backend/score_trans/services/render/engraving/qa.py`
- Create: `tests/test_render_qa.py`
- Modify: `docs/issues.md`

**Interfaces:**
- `check_scene_geometry(scene, style) -> list[dict[str, object]]` returns deterministic diagnostics for page overflow, protected-gutter violations, and non-whitelisted event overlap.
- QA excludes page background, container groups, and intentional spanner/anchor containment.

- [ ] **Step 1: Write failing tests** for one valid scene and one synthetic overlap.
- [ ] **Step 2: Implement** a simple deterministic pair scan first; optimize only if measured fixture size requires it.
- [ ] **Step 3: Keep the report diagnostic-only** and write JSON only from an explicit test/tool call, never during ordinary rendering.
- [ ] **Step 4: Run** the QA tests and document remaining intentional overlaps.
- [ ] **Step 5: Commit** with `test: 增加简谱场景几何诊断`.

### Task 8: Separate deferred data-contract work

**Files:**
- Future modify: `backend/score_trans/models/score.py`
- Future modify: parser/MusicXML normalization modules
- Future modify: `backend/score_trans/services/render/options.py`
- Future tests: dedicated lyric/title/line-breaking fixtures

**Interfaces:**
- Define explicit `Event.lyrics` verse-index semantics before adding the field.
- Define explicit title metadata precedence before adding subtitle/composer/lyricist options.
- Prototype mid-measure slices with multi-part and spanner preservation before enabling `allow_mid_measure_break`.

- [ ] **Step 1: Document input contracts and conversion ownership.**
- [ ] **Step 2: Add parser/domain round-trip tests before renderer support.**
- [ ] **Step 3: Implement renderer support behind default-off options.**
- [ ] **Step 4: Add visual fixtures and only then expose public options.**

---
