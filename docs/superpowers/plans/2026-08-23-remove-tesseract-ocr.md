# Complete Tesseract OCR Removal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Completely remove the Java/Audiveris Tesseract OCR implementation and its native/runtime assets while retaining Audiveris OMR, Python OCR, dynamics recognition, and existing OCR text contracts.

**Architecture:** Audiveris remains responsible for musical-symbol OMR, including dynamics such as `f`, `mf`, `mp`, and `ff`; its Java `TEXTS` OCR execution is removed or made inert. The Python `services/ocr` provider remains the only text OCR path used by pipeline, conversion, and rendering flows. Packaging and generated artifacts are guarded so no stale Tesseract classes, native libraries, or tessdata are shipped.

**Tech Stack:** Java 25, Gradle/Audiveris, Python 3.13, repository `.venv/Scripts/python.exe`, pytest, FastAPI, Vue 3, pnpm.

**Spec:** User requirement: completely delete Tesseract OCR, keep Python backend OCR, and keep non-OCR Audiveris OMR behavior.

## Global Constraints

- Use `D:/CODE/MyProjects/score_trans/.venv/Scripts/python.exe` for all Python tests, scripts, formatting, and linting.
- Use bash syntax for commands; set `JAVA_HOME` to JDK 25 before Gradle commands.
- Do not remove Audiveris OMR steps that recognize notes, rhythm, clefs, symbols, or dynamics.
- Do not remove `backend/score_trans/services/ocr/` or its provider/configuration contracts.
- Do not treat ordinary OCR text removal as proof that dynamics are lost; dynamics are Audiveris `DYNAMICS_*` symbols and must have a regression check.
- Do not preserve stale generated Tesseract classes or native resources in `app/build`, `app/bin`, package output, or Gradle runtime dependencies.

---

### Task 1: Freeze the Current Contracts and Add Regression Fixtures

**Files:**
- Reuse: `tests/test_pipeline.py:224` existing injected Python OCR contract
- Reuse: `tests/test_ocr.py:123` existing Python API-key error contract
- Modify: `tests/test_convert.py` only if extending the existing inline dynamics case to `mf`
- Modify: `tests/test_build_app.py`

**Interfaces:**
- Consumes: existing `OCRProvider` injection points and MusicXML parser behavior.
- Produces: tests proving Python OCR remains callable, MusicXML dynamics remain parseable, and package cleanup rejects stale Tesseract artifacts.

- [ ] **Step 1: Freeze the existing Python OCR contracts.**

  Reuse `tests/test_pipeline.py::test_full_pipeline_runs_ocr_for_image_and_outputs_a4_layout` and `tests/test_ocr.py::test_ocr_provider_requires_api_key` as the baseline. Do not add duplicate tests; only strengthen assertions if implementation exposes a regression.

- [ ] **Step 2: Extend the existing inline dynamics assertion if needed.**

  Reuse `tests/test_convert.py` inline MusicXML style. Add `mf` to an existing parametrized or compact test only if the current suite does not already exercise it; do not create a new fixtures directory.

- [ ] **Step 3: Add a packaging cleanup test for stale generated OCR output.**

  Create a temporary Audiveris tree containing `app/bin/main/org/audiveris/omr/text/tesseract/`, `app/build/classes/java/main/org/audiveris/omr/text/tesseract/`, and `app/dev/tessdata/eng.traineddata`; call the packaging cleanup helper and assert those paths are absent afterward.

- [ ] **Step 4: Run the new tests before implementation.**

  Run:

  ```bash
  SCORE_TRANS_DATA_DIR=work/pytest-tesseract-baseline \
  ./.venv/Scripts/python.exe -m pytest \
  tests/test_pipeline.py tests/test_convert.py tests/test_build_app.py -q \
  --basetemp=work/pytest-tesseract-baseline-temp
  ```

  Expected: existing contract tests pass; the new cleanup test fails until packaging cleanup is implemented.

---

### Task 2: Remove the Audiveris Tesseract Implementation and Dependencies

**Files:**
- Delete: `third_party/audiveris/app/src/main/java/org/audiveris/omr/text/tesseract/`
- Delete: `third_party/audiveris/app/src/main/java/org/audiveris/omr/text/tesseract/resources/`
- Delete: `third_party/audiveris/app/dev/tessdata/eng.traineddata`
- Modify: `third_party/audiveris/app/build.gradle`
- Modify: `third_party/audiveris/gradle.properties`
- Modify: `third_party/audiveris/app/src/main/java/org/audiveris/omr/text/OcrUtil.java`
- Modify: `third_party/audiveris/app/src/main/java/org/audiveris/omr/text/TextsStep.java`
- Modify: direct callers found by static reference search, including `Main.java`, `AboutAction.java`, `MainGui.java`, `GuiActions.java`, `BookParameters.java`, `Language.java`, `TextLine.java`, `TextBuilder.java`, `SheetScanner.java`, `BlockScanner.java`, `InterController.java`, and `RehearsalsBuilder.java`

**Interfaces:**
- Consumes: Audiveris OMR step graph and existing MusicXML/overlay exporters.
- Produces: an Audiveris build with no Tesseract Java classes, no JavaCPP Tesseract bridge, no Leptonica runtime, and no tessdata.

- [ ] **Step 1: Capture the exact direct reference set.**

  Run:

  ```bash
  rg -n -i 'TesseractOCR|TesseractOrder|org\\.bytedeco\\.(tesseract|leptonica)|tessdata|traineddata|OcrUtil|TextsStep|SheetScanner|BlockScanner' \
  third_party/audiveris/app/src/main/java third_party/audiveris/app/build.gradle third_party/audiveris/gradle.properties
  ```

  Use this result as the deletion checklist. Do not remove unrelated `DynamicSection` classes; “dynamic” there is not musical dynamics or OCR.

- [ ] **Step 2: Remove the Tesseract/Leptonica/JavaCPP dependencies.**

  Delete the `org.bytedeco:leptonica`, `org.bytedeco:tesseract`, and any now-unused explicit `org.bytedeco:javacpp` declarations from `app/build.gradle`; remove both normal and platform-specific runtime declarations. Remove `theTessdataTag` and the `tessdata_tag` generated `ProgramId` field.

- [ ] **Step 3: Make the Java text step inert without deleting musical-symbol OMR.**

  Keep the `TEXTS` enum slot for serialized step ordering. Remove all OCR scanning from `TextsStep`; make `doProlog` return an empty context and make `doSystem` return before calling `TextBuilder.processSystem()` when that context has no lines. Do not pass a null/empty buffer into `TextBuilder`. Remove `OcrUtil` and scanner calls if no remaining caller needs them; otherwise leave only a non-OCR-compatible empty adapter with no Tesseract types. Remove Tesseract-specific confidence thresholds from `TextLine` and `TextBuilder` rather than replacing them with an engine call.

- [ ] **Step 4: Remove UI and metadata references.**

  Remove OCR engine/version display, language-download panes, and Tesseract availability checks from Audiveris UI classes. Keep generic text model and persisted `ocrLanguages` compatibility fields where old `.omr` deserialization or MusicXML/overlay serialization requires them; remove their active runtime/UI use only.

- [ ] **Step 5: Delete source and data assets.**

  Delete the complete `text/tesseract` package, its resource bundles, and `app/dev/tessdata/eng.traineddata`. Do not use a broad recursive delete; remove only the listed paths after confirming them with `find`.

- [ ] **Step 6: Compile Audiveris with a clean build.**

  Run:

  ```bash
  cd third_party/audiveris
  export JAVA_HOME="${SCORE_TRANS_JAVA_HOME:-E:/ENV/JAVA/JDK25}"
  ./gradlew clean :app:compileJava --no-daemon
  ```

  Expected: Java compilation succeeds without downloading or linking Tesseract/Leptonica artifacts.

---

### Task 3: Make Python the Sole OCR Producer

**Files:**
- Preserve: `backend/score_trans/services/ocr/`
- Modify: `backend/score_trans/exec/pipeline/actions.py`
- Modify: `backend/score_trans/exec/convert/actions.py`
- Modify: `backend/score_trans/exec/render/actions.py` only where comments or labels incorrectly describe Java/Audiveris OCR
- Modify: `backend/score_trans/services/settings/settings_service.py` and settings UI labels only if they still describe `enable_omr_ocr` as Java OCR
- Test: `tests/test_ocr.py`, `tests/test_pipeline.py`, `tests/test_convert.py`, `tests/test_api_routes.py`

**Interfaces:**
- Consumes: existing `OCRProvider`, `OCRService`, OCR parser, provider settings, and `TextBlock` contracts.
- Produces: one documented Python OCR path for image text, with no dependency on Audiveris-produced text items.

- [ ] **Step 1: Preserve provider and parser contracts.**

  Keep `create_configured_ocr_provider()`, `OCRService`, `openai_compatible.py`, `dashscope.py`, `mock.py`, OCR prompts, and `parse_openai_compatible_response()`. No Python OCR file should be deleted as part of this task.

- [ ] **Step 2: Verify pipeline ownership.**

  Ensure `FullPipelineAction` passes the original raster image to the Python provider after OMR, and that `MusicXmlToJianpuAction` extends scores with returned `TextBlock` values. Keep explicit provider injection for tests.

- [ ] **Step 3: Clarify the setting name without breaking persisted data.**

  Keep the stored key `enable_omr_ocr` for backward compatibility in this removal task, but change UI/docs wording to “Python OCR text extraction”. A separate migration may rename the key to `enable_python_ocr`; do not combine that breaking API change with Tesseract deletion.

- [ ] **Step 4: Verify the no-Tesseract Python contract.**

  Reuse the existing injected-provider and missing-key tests. Verify that pipeline, conversion, and rendering call the Python provider and that `/recognize` remains OMR-only unless explicitly extended later; document this API boundary rather than adding a second OCR implementation.

- [ ] **Step 5: Run focused Python tests.**

  Run:

  ```bash
  SCORE_TRANS_DATA_DIR=work/pytest-tesseract-python \
  ./.venv/Scripts/python.exe -m pytest \
  tests/test_ocr.py tests/test_pipeline.py tests/test_convert.py \
  tests/test_api_routes.py -q \
  --basetemp=work/pytest-tesseract-python-temp
  ```

---

### Task 4: Remove Stale Build and Packaging Artifacts

**Files:**
- Modify: `build-app.py`
- Modify: `tests/test_build_app.py`
- Modify: `docs/packaging.md`
- Generated/ignored cleanup: `third_party/audiveris/app/bin/`, `third_party/audiveris/app/build/`, `build-resources/third_party/audiveris/`

**Interfaces:**
- Consumes: clean Audiveris source tree and existing packaging cleanup helpers.
- Produces: package output with no Tesseract classes, native libraries, tessdata, or OCR language resources.

- [ ] **Step 1: Harden package cleanup.**

  Before cleanup, validate the copied `app/build/generated-src/org/audiveris/omr/ProgramId.java` when present and fail if it contains `TESSDATA_TAG`, instructing the caller to run a clean `:app:compileJava`. Extend `_cleanup_audiveris()` so it removes stale generated Tesseract package directories under `app/build/classes`, `app/build/resources`, and any copied runtime tree while preserving the required non-OCR `app/build` artifacts such as generated `ProgramId.java` and commit metadata.

- [ ] **Step 2: Add package assertions.**

  After `setup_audiveris()` and cleanup, assert that no path matching `*tesseract*`, `*leptonica*`, `*tessdata*`, or `*.traineddata` exists below the packaged Audiveris directory. Keep Gradle wrapper cache validation unchanged.

- [ ] **Step 3: Rebuild a package smoke tree.**

  Run the build-app cleanup tests with the repository venv:

  ```bash
  SCORE_TRANS_DATA_DIR=work/pytest-build-tesseract \
  ./.venv/Scripts/python.exe -m pytest tests/test_build_app.py -q \
  --basetemp=work/pytest-build-tesseract-temp
  ```

- [ ] **Step 4: Verify the packaged runtime dependencies.**

  Inspect the generated Gradle dependency list or package contents and confirm there is no Tesseract/Leptonica native library or jar. Do not infer this only from source deletion because stale `app/build` output is currently preserved by the packaging flow.

---

### Task 5: Update Documentation and Remove Tesseract Claims

**Files:**
- Modify: `docs/architecture.md`
- Modify: `docs/audiveris-research.md`
- Modify: `docs/omr_parameters_manual.md`
- Modify: `backend/score_trans/config/env.example`
- Modify: `docs/environment.md` only if it contains an active obsolete claim
- Modify: `docs/packaging.md`
- Modify: `README.md` or `THIRD_PARTY_NOTICES.md` only if the final repository-wide search finds a Tesseract claim there

**Interfaces:**
- Consumes: final Java/Python architecture after Tasks 2–4.
- Produces: documentation that distinguishes Audiveris OMR symbol recognition from Python OCR text extraction.

- [ ] **Step 1: Rewrite the architecture flow.**

  Document that `SYMBOLS`/OMR recognizes standard dynamics (`p`, `mp`, `mf`, `f`, `ff`), while Python OCR recognizes lyrics, titles, expression text, and other ordinary text.

- [ ] **Step 2: Remove obsolete Tesseract setup instructions.**

  Delete tessdata download instructions, Tesseract language configuration, Tesseract dependency versions, and statements that `TEXTS` calls Tesseract. Keep Audiveris Java 25 requirements because OMR still uses Java.

- [ ] **Step 3: Document Python OCR configuration.**

  Keep `SCORE_TRANS_OCR_*` variables and provider settings as the supported OCR configuration. State that an OCR API failure affects text extraction only; musical-symbol OMR remains a separate stage.

- [ ] **Step 4: Search documentation for stale claims.**

  Run:

  ```bash
  rg -n -i 'tesseract|leptonica|tessdata|traineddata|Java OCR' \
  README.md docs backend desktop third_party/audiveris \
  -g '!*.class' -g '!*.jar' -g '!*.png' -g '!*.bmp' -g '!*.jpg' -g '!*.gif' -g '!*.otf' -g '!*.ttf'
  ```

  Expected: no active source, packaging, or user documentation references remain. Historical audit records may retain historical mentions and must be checked separately rather than erased to make this grep empty.

---

### Task 6: Full Verification and Acceptance Gate

**Files:**
- Test: `tests/test_ocr.py`
- Test: `tests/test_pipeline.py`
- Test: `tests/test_convert.py`
- Test: `tests/test_render.py`
- Test: `tests/test_api_routes.py`
- Test: `tests/test_architecture.py`
- Test: `tests/test_build_app.py`
- Test: `desktop` lint/typecheck scripts

**Interfaces:**
- Consumes: all completed removal tasks.
- Produces: evidence that Tesseract is absent while Python OCR, OMR, dynamics, rendering, and packaging still work.

- [ ] **Step 1: Run the full backend suite with writable workspace paths.**

  ```bash
  SCORE_TRANS_DATA_DIR=work/pytest-tesseract-full \
  ./.venv/Scripts/python.exe -m pytest -q \
  --basetemp=work/pytest-tesseract-full-temp
  ```

- [ ] **Step 2: Run formatting, lint, and compile checks.**

  ```bash
  ./.venv/Scripts/python.exe -m ruff format --check backend/ tests/
  ./.venv/Scripts/python.exe -m ruff check backend/ tests/
  ./.venv/Scripts/python.exe -m compileall -q backend
  ```

- [ ] **Step 3: Compile Audiveris after a clean build.**

  ```bash
  cd third_party/audiveris
  export JAVA_HOME="${SCORE_TRANS_JAVA_HOME:-E:/ENV/JAVA/JDK25}"
  ./gradlew clean :app:compileJava --no-daemon
  ```

- [ ] **Step 4: Run frontend checks.**

  ```bash
  cd desktop
  pnpm lint
  pnpm exec vue-tsc --noEmit
  ```

- [ ] **Step 5: Run the final static deletion audit.**

  ```bash
  cd ..
  rg -n -i 'TesseractOCR|TesseractOrder|org\\.bytedeco\\.(tesseract|leptonica)|tessdata|traineddata|tesseract-ocr' \
  third_party/audiveris backend desktop build-app.py docs README.md THIRD_PARTY_NOTICES.md \
  -g '!*.class' -g '!*.jar'
  ```

  Expected: no active implementation, dependency, asset, package, or user-documentation hit. Historical audit records are checked separately. Python OCR references such as `services/ocr` and `OCRProvider` are expected and must remain.

- [ ] **Step 6: Perform one real OMR fixture smoke test.**

  Recognize a representative score containing `f`/`mf`, lyrics, and a title. Verify:

  1. MusicXML still contains dynamics for the standard dynamic glyphs.
  2. Python OCR output contains the expected ordinary text blocks.
  3. Jianpu rendering and source overlays still complete.
  4. No Audiveris output or logs mention Tesseract initialization or missing tessdata.

  Also record the accepted scope: Java OMR no longer emits OCR-derived lyrics, rehearsal numbers, chord names, or metronome text; Python OCR text blocks remain available through the existing pipeline/conversion/rendering paths.
