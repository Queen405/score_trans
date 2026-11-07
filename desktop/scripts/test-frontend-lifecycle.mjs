import assert from 'node:assert/strict'
import { Buffer } from 'node:buffer'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { compileTemplate, parse } from 'vue/compiler-sfc'

const here = path.dirname(fileURLToPath(import.meta.url))
const source = (relativePath) => fs.readFileSync(path.resolve(here, relativePath), 'utf8')

const logStoreSource = source('../src/renderer/src/stores/log.ts')
const appSource = source('../src/renderer/src/App.vue')
const logPanelSource = source('../src/renderer/src/components/LogPanel.vue')
const uploaderSource = source('../src/renderer/src/components/FileUploader.vue')
const recognizeSource = source('../src/renderer/src/views/RecognizeView.vue')
const assistantComponentSource = source('../src/renderer/src/components/AiAssistant.vue')
const assistantStoreSource = source('../src/renderer/src/stores/assistant.ts')
const editorSource = source('../src/renderer/src/components/JianpuEditor.vue')
const convertSource = source('../src/renderer/src/views/ConvertView.vue')
const historyRestoreSource = source('../src/renderer/src/composables/useHistoryRestore.ts')
const originalPreviewSource = source('../src/renderer/src/components/OriginalPreview.vue')
const toolPathsSource = source('../src/renderer/src/components/settings/ToolPathsPanel.vue')
const markerInspectorSource = source('../src/renderer/src/components/MarkerInspector.vue')
const shapeDescriptorSource = source('../src/renderer/src/utils/shapeDescriptor.ts')
const playerSource = source('../src/renderer/src/components/JianpuPlayer.vue')
const playerPreferencesPath = path.resolve(
  here,
  '../src/renderer/src/utils/playerPreferences.ts',
)
const playerLoadIdPath = path.resolve(
  here,
  '../src/renderer/src/utils/playerLoadId.ts',
)

async function importTranspiledTypeScript(filePath) {
  const sourceText = fs.readFileSync(filePath, 'utf8')
  const compiled = ts.transpileModule(sourceText, {
    compilerOptions: {
      module: ts.ModuleKind.ES2022,
      target: ts.ScriptTarget.ES2022,
    },
    fileName: filePath,
  }).outputText
  return import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`)
}

function isInsideScriptSetup(vueSource, token) {
  const setupStart = vueSource.indexOf('<script setup')
  const setupEnd = vueSource.indexOf('</script>', setupStart)
  const tokenIndex = vueSource.indexOf(token)
  return setupStart >= 0 && tokenIndex > setupStart && tokenIndex < setupEnd
}

function countTemplateRoots(vueSource) {
  const { descriptor } = parse(vueSource, { filename: 'ConvertView.vue' })
  assert.ok(descriptor.template)
  const result = compileTemplate({
    source: descriptor.template.content,
    filename: 'ConvertView.vue',
    id: 'workspace-root-check',
  })
  assert.deepEqual(result.errors, [])
  return result.ast.children.filter((child) => child.type === 1).length
}

test('log state is bounded and LogPanel uses its stable entry ids', () => {
  assert.match(logStoreSource, /MAX_LOG_ENTRIES\s*=\s*1000/)
  assert.match(logStoreSource, /id:\s*nextLogId/)
  assert.match(logStoreSource, /\.splice\(0,\s*overflow\)/)
  assert.match(logPanelSource, /ref="logContainer"/)
  assert.match(logPanelSource, /:key="entry\.id"/)
  assert.doesNotMatch(logPanelSource, /:key="i"/)
})

test('PDF preview re-renders without changing the OMR coordinate system', () => {
  assert.match(originalPreviewSource, /:src="displayFileUrl"/)
  assert.match(originalPreviewSource, /fetchPdfPageBlob/)
  assert.match(originalPreviewSource, /PDF_PREVIEW_DEBOUNCE_MS = 180/)
  assert.match(originalPreviewSource, /pdfPreviewTargetWidth/)
  assert.match(originalPreviewSource, /逻辑尺寸始终保持 OMR 坐标系/)
  assert.match(originalPreviewSource, /clearPdfPreviewCache\(\)/)
})

test('marker candidate maps preserve the native overlay and use contour hit paths', () => {
  assert.match(originalPreviewSource, /\[1, 2, 3\]\.includes\(parsed\.version\)/)
  assert.match(originalPreviewSource, /:class="\{ dimmed: showOverlay && canShowOverlay \}"/)
  assert.match(originalPreviewSource, /\.scan-img\.dimmed\s*\{[\s\S]*?grayscale\(0\.5\) brightness\(0\.95\)/)
  assert.doesNotMatch(originalPreviewSource, /\.scan-img\.dimmed\s*\{[^}]*blur/)
  assert.doesNotMatch(originalPreviewSource, /<rect[\s\S]*?entity-box/)
  assert.match(originalPreviewSource, /:d="element\.hit_path"/)
  assert.match(convertSource, /@select-source="handleOriginalSourceClick"/)
  // 删除/恢复由语义命中层单击驱动（仅 can_delete 实体），面板只做候选选择
  assert.match(convertSource, /@toggle-delete="toggleEntityDelete"/)
  assert.match(originalPreviewSource, /if \(entity\) \{[\s\S]*?emit\('toggleDelete', sourceId\)/)
})

test('partial candidate application stays pending instead of reporting false success', () => {
  assert.match(convertSource, /const unresolvedCandidateIds = Object\.keys/)
  assert.match(convertSource, /convert\.marker\.candidatesNotReady/)
  assert.match(convertSource, /const unappliedCandidateSelections = Object\.fromEntries/)
  assert.match(convertSource, /!\(sourceId in appliedCandidateSelections\)/)
  assert.match(convertSource, /recognitionCandidateSelections: savedCandidateSelections/)
  assert.match(convertSource, /\.\.\.unappliedCandidateSelections/)
  assert.match(convertSource, /message\.warning\(t\('convert\.marker\.applyPartial'/)
  assert.match(convertSource, /return false/)
})

test('applied deletions stay clickable in edit mode so they can be restored', () => {
  // 已应用的删除若从命中层剔除，用户就再也没法点回来，因此编辑态必须保留命中区
  assert.match(
    originalPreviewSource,
    /if \(appliedDeletedSourceIdSet\.value\.has\(element\.source_id\)\) return props\.editable/,
  )
  // 已删除记号悬停提示「恢复」，而不是再次预览删除
  assert.match(
    originalPreviewSource,
    /'source-hit--deleted': editable && isElementDeleted\(element\.source_id\)/,
  )
  assert.match(originalPreviewSource, /t\('convert\.marker\.restore'\)/)
  // 再次点击后虚线转绿，表示等待应用即可恢复
  assert.match(originalPreviewSource, /deleted-mark--restore/)
})

test('binarization offers explicit automatic and manual modes', () => {
  assert.match(toolPathsSource, /t\('settings\.tools\.binarizationMode'\)/)
  assert.match(toolPathsSource, /v-model:checked="binarizationAuto"/)
  assert.match(toolPathsSource, /v-model:value="manualBinarizationThreshold"/)
  assert.match(toolPathsSource, /:disabled="binarizationAuto"/)
  assert.match(toolPathsSource, /:min="1"/)
  assert.match(toolPathsSource, /automatic\s*\?\s*0/)
  assert.match(toolPathsSource, /lastManualBinarizationThreshold/)
})

test('uploader and recognition coordination state is instance scoped', () => {
  assert.ok(isInsideScriptSetup(uploaderSource, 'const uploadQueue'))
  assert.ok(isInsideScriptSetup(recognizeSource, 'const batchRenderInFlight'))
  assert.ok(isInsideScriptSetup(recognizeSource, 'const ownedTaskIds'))
  assert.ok(isInsideScriptSetup(recognizeSource, 'const resumingTaskIds'))
})

test('uploader reports individual upload failures while continuing the queue', () => {
  assert.match(uploaderSource, /const \{ upload, uploading, progress, phase, error \} = useFileUpload\(\)/)
  assert.match(uploaderSource, /const uploadErrors = ref<string\[\]>\(\[\]\)/)
  assert.match(uploaderSource, /v-if="uploadErrors\.length"/)
  assert.match(uploaderSource, /const detail = error\.value \|\| t\('components\.fileUploader\.uploadFailedRetry'\)/)
  assert.match(uploaderSource, /log\.addError\(t\('components\.fileUploader\.uploadFailedLog', \{ message \}\)\)/)
  assert.doesNotMatch(uploaderSource, /if \(!result\)\s*throw/)
})

test('renderer uses the typed preload API without global any escapes', () => {
  const rendererRoot = path.resolve(here, '../src/renderer/src')
  const guardedFiles = [
    'components/settings/ConversionSettingsPanel.vue',
    'components/settings/StorageSettingsPanel.vue',
    'stores/settings.ts',
    'views/ConvertView.vue',
  ]
  for (const relativePath of guardedFiles) {
    const sourceText = fs.readFileSync(path.join(rendererRoot, relativePath), 'utf8')
    assert.doesNotMatch(sourceText, /\(globalThis as any\)\.api/)
    assert.doesNotMatch(sourceText, /\(window as any\)\.api/)
  }
})

test('assistant animation timers are replaced and cleared on unmount', () => {
  assert.match(assistantComponentSource, /let animationTimer:/)
  assert.match(assistantComponentSource, /function scheduleAnimationFinish/)
  assert.match(
    assistantComponentSource,
    /onUnmounted\(\(\) => \{[\s\S]*clearTimeout\(animationTimer\)/,
  )
})

test('assistant stays mounted across tab switches so streams survive navigation', () => {
  assert.match(appSource, /<ai-assistant\s+v-show="activeTab === 'convert'"\s*\/>/)
  assert.doesNotMatch(appSource, /<ai-assistant\s+v-if=/)
  // Unmount abort only fires when the whole app is destroyed, not on tab switch.
  assert.match(
    assistantComponentSource,
    /onUnmounted\(\(\) => \{[\s\S]*assistant\.abortStream\(\)/,
  )
})

test('workspace view has one element root so App v-show can hide it', () => {
  assert.equal(countTemplateRoots(convertSource), 1)
})

test('all close paths share the guarded request protocol', () => {
  assert.match(appSource, /onCloseRequested\(handleCloseRequested\)/)
  assert.match(appSource, /settings\.draftDirty[\s\S]*processCloseRequest/)
  assert.match(appSource, /store\.hasUnsavedChanges/)
  assert.match(appSource, /store\.hasPersistableUnsavedChanges/)
  assert.match(
    appSource,
    /saveAllUnsavedBatches\(store,\s*\{[\s\S]*mode:\s*'discard'[\s\S]*\}\)/,
  )
  assert.match(appSource, /store\.isBusy \|\| store\.backgroundTaskCount > 0/)
  assert.match(appSource, /resolveCloseRequest\(request\.requestId, 'cancel'\)/)
  assert.match(appSource, /resolveCloseRequest\(request\.requestId, 'proceed'\)/)
})

test('history deletion marks matching workspace batches as unpersistable', () => {
  const deleteAllStart = convertSource.indexOf('async function handleDeleteAll')
  const deleteOneStart = convertSource.indexOf('async function handleDeleteBatch')
  const nextHandlerStart = convertSource.indexOf('async function toggleBatchExpand')
  const deleteAllHandler = convertSource.slice(deleteAllStart, deleteOneStart)
  const deleteOneHandler = convertSource.slice(deleteOneStart, nextHandlerStart)

  assert.match(deleteAllHandler, /store\.markAllHistoryBatchesDeleted\(\)/)
  assert.match(deleteOneHandler, /store\.markHistoryBatchDeleted\(batchId\)/)
})

test('convert guards destructive actions and shows the current unsaved state', () => {
  assert.match(convertSource, /store\.currentBatchHasUnsavedChanges/)
  assert.match(convertSource, /t\('convert\.panel\.unsavedHint'\)/)
  assert.match(convertSource, /await confirmDiscardUnsaved\('reset'\)/)
  assert.match(convertSource, /await confirmDiscardUnsaved\('restore'\)/)
  assert.match(convertSource, /:mask-closable="false"/)
})

test('final preview toggle reuses the cache-aware render path', () => {
  const toggleStart = convertSource.indexOf('async function toggleFinalView')
  const toggleEnd = convertSource.indexOf('async function loadJianpuSnapshots', toggleStart)
  assert.ok(toggleStart >= 0)
  assert.ok(toggleEnd > toggleStart)
  const toggleHandler = convertSource.slice(toggleStart, toggleEnd)

  assert.match(toggleHandler, /await renderExportSvgIds\(\)/)
  assert.doesNotMatch(toggleHandler, /await renderFinalBatch\(\)/)
})

test('assistant store cleans pending temp messages on abort and error paths', () => {
  // A shared cleanup helper must exist and be invoked on the aborted early returns.
  assert.match(assistantStoreSource, /const dropPendingMessages = \(\): void => \{/)
  const abortReturns = assistantStoreSource.match(/if \(controller\.signal\.aborted\) \{[\s\S]*?\n\s*return\n\s*\}/g) ?? []
  assert.ok(
    abortReturns.length >= 2,
    `expected both aborted early-return paths to clean up, found ${abortReturns.length}`,
  )
  for (const block of abortReturns) {
    assert.match(block, /dropPendingMessages\(\)/)
  }
  assert.match(
    assistantStoreSource,
    /if \(savedStreamMessages\) \{[\s\S]*savedStreamMessages = savedStreamMessages\.filter/,
  )
})

test('assistant streaming replaces the message object', () => {
  assert.doesNotMatch(assistantStoreSource, /target\.content\s*\+=/)
  assert.match(
    assistantStoreSource,
    /messages\.value\[targetIndex\]\s*=\s*\{[\s\S]*content:/,
  )
})

test('editor does not rewrite externally restored model text', () => {
  assert.doesNotMatch(editorSource, /function needsFormat/)
  assert.doesNotMatch(editorSource, /function formatMeasures/)
  assert.doesNotMatch(
    editorSource,
    /watch\(\s*\(\) => props\.modelValue[\s\S]*immediate:\s*true/,
  )
})

test('blank workspace treats structural marker comments as plain comments everywhere', () => {
  assert.match(editorSource, /structureMarkersEnabled/)
  assert.match(editorSource, /maskJianpuStructureMarkers\(props\.modelValue\)/)
  assert.match(
    convertSource,
    /:structure-markers-enabled="store\.currentBatchId !== null"/,
  )
  assert.match(convertSource, /const operationalJianpuText = computed/)
  assert.match(convertSource, /maskJianpuStructureMarkers\(jianpuText\.value\)/)
  assert.match(convertSource, /:jianpu-text="operationalJianpuText"/)
  assert.match(convertSource, /syntaxStore\.schedule\(operationalJianpuText\.value\)/)
  assert.match(convertSource, /jianpuText:\s*operationalJianpuText\.value/)
  assert.equal(
    convertSource.match(/jianpuText:\s*operationalJianpuText\.value/g)?.length,
    3,
    'export plus both render request builders must use plain-comment semantics',
  )
})

test('convert distinguishes one external editor sync without a nextTick timing flag', () => {
  assert.doesNotMatch(convertSource, /programmaticUpdate/)
  assert.match(convertSource, /let editorSyncGeneration = 0/)
  assert.match(convertSource, /pendingExternalEditorSync = \{ generation, text: v \}/)
  assert.match(convertSource, /const isExternalSync = pendingExternalEditorSync\?\.text === v/)
  assert.match(convertSource, /if \(isExternalSync\) pendingExternalEditorSync = null/)
})

test('recognition aligns and captures an immutable text-anchor baseline', () => {
  assert.match(recognizeSource, /ensureRecognizedPageTempoHeader\(\s*split\.jianpuText,\s*batchPageIndex/s)
  assert.match(recognizeSource, /reconcileTextAnchors\(\s*result\.jianpu_text,\s*recognizedJianpuText/s)
  assert.match(recognizeSource, /await hashJianpuText\(recognizedJianpuText\)/)
  assert.match(recognizeSource, /textAnchorBaselineText:\s*recognizedJianpuText/)
  assert.match(recognizeSource, /textAnchorBaselineAnchors[,}]/)
})

test('editor reconciles only changed page bodies from their baselines', () => {
  assert.match(convertSource, /previousSection\.body === currentSection\.body/)
  assert.match(
    convertSource,
    /reconcileTextAnchors\(\s*page\.textAnchorBaselineText,\s*currentSection\.body,\s*page\.textAnchorBaselineAnchors,\s*page\.textAnchors/s,
  )
  assert.match(convertSource, /textAnchorBaselineText:\s*resetJianpuText/)
  assert.match(convertSource, /textAnchorBaselineAnchors[:,]/)
  assert.match(convertSource, /await hashJianpuText\(resetJianpuText\)/)
  assert.match(convertSource, /await hashJianpuText\(corrected\.jianpuText\)/)
  assert.match(convertSource, /try \{[\s\S]*parseJianpuPageSections\(previous\)[\s\S]*catch/)
  assert.match(convertSource, /catch[\s\S]*valid:\s*false/)
  const handlerStart = convertSource.indexOf('function updateTextAnchorsAfterEdit')
  const handlerEnd = convertSource.indexOf('async function handleOriginalSourceClick', handlerStart)
  const handler = convertSource.slice(handlerStart, handlerEnd)
  assert.ok(
    handler.indexOf('if (!previousSection || !currentSection)')
      < handler.indexOf('if (!page.textAnchorBaselineAnchors.length)'),
    'missing sections must invalidate current anchors before empty baselines skip diffing',
  )
})

test('rekey responses use semantic anchor mappings and refresh baselines', () => {
  assert.match(editorSource, /rekey-applied/)
  assert.match(editorSource, /anchor_mapping/)
  assert.match(convertSource, /updateTextAnchorsAfterRekey/)
  assert.match(convertSource, /textAnchorBaselineText:\s*afterSection\.body/)
  assert.match(convertSource, /textAnchorBaselineAnchors:\s*localAnchors/)
})

test('rekey metadata is announced before the model update', () => {
  const rekeyEvent = editorSource.indexOf("emit('rekey-applied'")
  const modelUpdate = editorSource.indexOf('applyTransposed(pending.text, transposed)')
  assert.ok(rekeyEvent >= 0)
  assert.ok(modelUpdate >= 0)
  assert.ok(rekeyEvent < modelUpdate, 'rekey marker must be queued before v-model changes')
})

test('stale rekey metadata falls back to ordinary anchor reconciliation', () => {
  const watcherStart = convertSource.indexOf('watch(jianpuText')
  const watcherEnd = convertSource.indexOf("}, { immediate: true })", watcherStart)
  const watcher = convertSource.slice(watcherStart, watcherEnd)
  assert.match(watcher, /rekey\.before === previous/)
  assert.match(watcher, /rekey\.after === v/)
  assert.match(watcher, /else if \(isUserEdit\) \{[\s\S]*updateTextAnchorsAfterEdit\(/)
})

test('original preview separates valid, invalidated, and never-mapped sources', () => {
  assert.match(convertSource, /:mapped-source-ids="mappedSourceIds"/)
  assert.match(convertSource, /anchor\.valid !== false/)
  assert.match(convertSource, /textAnchorBaselineAnchors[\s\S]*\.map\(\(anchor\) => anchor\.source_id\)/)
  assert.match(originalPreviewSource, /mappedSourceIds\?: string\[\]/)
  assert.match(originalPreviewSource, /const mappedSourceIdSet = computed/)
  assert.match(originalPreviewSource, /!mappedSourceIdSet\.value\.has\(element\.source_id\)/)
  assert.doesNotMatch(originalPreviewSource, /if \(!mappedSourceIdSet\.value\.size/)
})

test('snapshot restore reconciles page anchors from their canonical baselines', () => {
  const start = convertSource.indexOf('async function restoreJianpuSnapshot')
  const end = convertSource.indexOf('function confirmDiscardUnsaved', start)
  const handler = convertSource.slice(start, end)

  assert.match(handler, /reconcileTextAnchors\(/)
  assert.match(handler, /page\.textAnchorBaselineText/)
  assert.match(handler, /page\.textAnchorBaselineAnchors/)
  assert.match(handler, /textAnchors:\s*update\.anchors/)
  assert.match(handler, /if \(!section\)[\s\S]*valid:\s*false/)
})

test('history restore treats persisted empty baseline anchors as authoritative', () => {
  assert.match(historyRestoreSource, /text_anchor_baseline_anchors !== undefined/)
  assert.doesNotMatch(historyRestoreSource, /text_anchor_baseline_anchors\?\.length/)
  assert.match(convertSource, /text_anchor_baseline_anchors !== undefined/)
})

test('player volume parsing clamps persistence to the supported range', async () => {
  assert.ok(fs.existsSync(playerPreferencesPath))
  const preferences = await importTranspiledTypeScript(playerPreferencesPath)

  assert.equal(preferences.parsePlayerVolume(null), 0.8)
  assert.equal(preferences.parsePlayerVolume('0'), 0)
  assert.equal(preferences.parsePlayerVolume('0.42'), 0.42)
  assert.equal(preferences.parsePlayerVolume('1'), 1)
  assert.equal(preferences.parsePlayerVolume('-0.1'), 0.8)
  assert.equal(preferences.parsePlayerVolume('1.1'), 0.8)
  assert.equal(preferences.parsePlayerVolume('broken'), 0.8)
  assert.match(playerSource, /loadPlayerVolume/)
  assert.match(playerSource, /savePlayerVolume/)
})

test('player load keys include the full Jianpu text instead of a shared prefix', async () => {
  assert.ok(fs.existsSync(playerLoadIdPath))
  const { buildPlayerLoadId } = await importTranspiledTypeScript(playerLoadIdPath)
  const commonPrefix = '1 2 3 4 5 6 7 | '.repeat(5)
  const firstText = `${commonPrefix}1 - 1`
  const changedText = `${commonPrefix}7 - 7`

  assert.notEqual(firstText.slice(0, 50), '')
  assert.equal(firstText.slice(0, 50), changedText.slice(0, 50))
  assert.notEqual(
    buildPlayerLoadId({ jianpuText: firstText }),
    buildPlayerLoadId({ jianpuText: changedText }),
  )
  assert.equal(
    buildPlayerLoadId({ jianpuText: firstText }),
    buildPlayerLoadId({ jianpuText: firstText }),
  )
})

test('player exposes fixed playback rates and resets them only for a new batch', () => {
  assert.match(playerSource, /PLAYBACK_RATES/)
  assert.match(playerSource, /player\.rate\.value/)
  assert.match(playerSource, /player\.setRate/)
  assert.doesNotMatch(playerSource, /n-input-number/)
  assert.doesNotMatch(playerSource, /resetBpm/)
  assert.match(convertSource, /:session-key="store\.currentBatchId"/)
})

test('MIDI generation failures unload stale audio and notify the user', () => {
  assert.match(playerSource, /useMessage\(\)/)
  assert.match(playerSource, /useLogStore\(\)/)
  assert.match(playerSource, /player\.unload\(\)/)
  assert.match(playerSource, /message\.error\(/)
})

test('syntax validation blocks output with a user-visible log and toast', () => {
  assert.match(
    playerSource,
    /if \(error instanceof ApiError && error\.code === 'jianpu_syntax'\) \{[\s\S]*logStore\.addError[\s\S]*message\.error/s,
  )
  assert.match(convertSource, /function handleJianpuOutputBlocked/)
  assert.match(convertSource, /syntaxBlockMsg/)
  assert.doesNotMatch(convertSource, /normalizeJianpuText\(\{ jianpu_text: savedJianpu/)
  assert.match(convertSource, /markBatchRenderPageOcrClean\(\)/)
})

test('delete-markers mode toggles label, cancels pending load, and gates apply on baseline diff', () => {
  // 入口/取消 二态标签
  assert.match(convertSource, /\{\{ editMode \? t\('common\.action\.cancel'\) : t\('convert\.marker\.deleteMark'\) \}\}/)
  // 应用按钮文案与加载态守卫
  assert.match(convertSource, /const loadingEntities = ref\(false\)/)
  assert.match(convertSource, /:disabled="loadingEntities \|\| !canEditMarkers"/)
  assert.match(
    convertSource,
    /@click="applyCorrections\(\)"[\s\S]*?>\s*\{\{ t\('convert\.marker\.apply'\) \}\}\s*<\/n-button>/,
  )
  // 拆分进入/取消；取消时终止未完成加载并恢复已应用基线
  assert.match(convertSource, /async function enterEditMode\(\)/)
  assert.match(convertSource, /function cancelEditMode\(\)/)
  assert.match(convertSource, /entityLoadController\?\.abort\(\)/)
  assert.match(
    convertSource,
    /new Set\(store\.currentPage\?\.deletedSourceIds \?\? \[\]\)/,
  )
  // apply 守卫基于"相对已应用基线的差异"，而非"删除数为 0"
  assert.match(convertSource, /const hasPendingChange =/)
  assert.doesNotMatch(convertSource, /未删除任何标记/)
  // 只有点「应用」才会提交并退出编辑模式
  assert.match(
    convertSource,
    /if \(!options\.silent\) message\.success\(t\('convert\.marker\.applied'\)\)\s*\n\s*if \(!options\.keepEditing\) editMode\.value = false/,
  )
  // 多页 OMR 提示文案与功能名一致
  assert.match(convertSource, /multiPageOmr/)
})

test('applied unrecognized glyphs behave like recognized marks', () => {
  // 非编辑模式下只渲染选过候选的 glyph，避免整页碎片抢点击
  assert.match(originalPreviewSource, /const visibleSuspiciousGlyphs = computed\(\(\) => \{/)
  assert.match(originalPreviewSource, /v-if="visibleSuspiciousGlyphs\.length && isImage"/)
  assert.match(originalPreviewSource, /glyph\.glyph_id in applied/)
  // 未识别 glyph 与已识别标记统一：左键删除/恢复，右键打开候选框。
  assert.match(originalPreviewSource, /@click\.stop="handleGlyphClick\(glyph\.glyph_id, \$event\)"/)
  assert.match(originalPreviewSource, /function handleGlyphClick\(glyphId: string, event: MouseEvent\): void \{[\s\S]*?emit\('toggleDelete', glyphId\)/)
  assert.match(originalPreviewSource, /@contextmenu\.stop\.prevent="selectGlyph\(glyph\.glyph_id, \$event, true\)"/)
  assert.match(originalPreviewSource, /'source-hit--deleted': editable && isElementDeleted\(glyph\.glyph_id\)/)
  assert.match(originalPreviewSource, /sourceSheet\.value\?\.glyphs \?\? \[\]/)
  // 点击已应用的 glyph 定位到简谱，并保留选中框
  assert.match(convertSource, /async function locateGlyphInJianpu\(glyphId: string\)/)
  assert.match(convertSource, /st__n-\$\{glyphId\.replace\(\/:\/g, '-'\)\}/)
  assert.match(convertSource, /if \(!editMode\.value\) \{\s*\n\s*void locateGlyphInJianpu\(glyphId\)/)
})

test('candidate selection only previews and commits on apply', () => {
  // 选候选是同步的本地暂存，不再触发后端修正
  assert.match(convertSource, /function selectCandidate\(sourceId: string, shape: string\): void \{/)
  assert.doesNotMatch(convertSource, /candidateOnly/)
  assert.match(
    convertSource,
    /candidateSelections\.value = \{ \.\.\.candidateSelections\.value, \[sourceId\]: shape \}/,
  )
  // 取消编辑回滚删除集合与候选选择
  assert.match(
    convertSource,
    /candidateSelections\.value = \{ \.\.\.\(store\.currentPage\?\.recognitionCandidateSelections \?\? \{\}\) \}/,
  )
  // 计数改为「已编辑」，覆盖删除与候选两种改动
  assert.match(convertSource, /const editedCount = computed\(/)
  assert.match(convertSource, /t\('convert\.marker\.editedCount', \{ count: editedCount \}\)/)
  // 删除优先于候选：删除时暂存候选，恢复后可以继续应用同一候选。
  assert.match(convertSource, /if \(deletedEntityIds\.value\.has\(sourceId\)\) continue/)
  assert.doesNotMatch(convertSource, /delete selections\[sourceId\]/)
  assert.match(convertSource, /const retainedDeletedCandidates = Object\.fromEntries\(/)
  assert.match(convertSource, /recognitionCandidateSelections: savedCandidateSelections/)
})

test('left click in edit mode toggles deletion without selecting the mark', () => {
  // 编辑态左键只切换删除：如果同时发 selectSource，蓝色选中轮廓会盖住红色删除虚线
  assert.match(
    originalPreviewSource,
    /if \(entity\) \{[\s\S]*?emit\('toggleDelete', sourceId\)/,
  )
  assert.doesNotMatch(
    originalPreviewSource,
    /if \(entity\?\.can_delete\) \{\s*emit\('selectSource'/,
  )
  // 删除虚线层必须在命中层之上
  assert.match(
    originalPreviewSource,
    /\.deleted-mark-layer \{[\s\S]*?z-index:\s*2;/,
  )
  // 已删除标记即使被选中也保持删除色
  assert.match(
    originalPreviewSource,
    /\.source-hit\.selected\.source-hit--deleted \+ \.source-hit-outline \{[\s\S]*?var\(--danger\)/,
  )
})

test('marker edit mode keeps the original overlay and clicks semantic hit paths without boxes', () => {
  assert.match(originalPreviewSource, /class="source-hit-layer"\s+:class="\{ editing: editable \}"/)
  assert.match(originalPreviewSource, /\.glyph-source-hit-layer\s*\{[\s\S]*?z-index:\s*0;/)
  assert.match(originalPreviewSource, /\.source-hit-layer\.editing \.source-hit--disabled\s*\{[\s\S]*?pointer-events:\s*none;/)
  // 命中层用宽描边扩大点击热区，视觉高亮由独立的细线层绘制，两者解耦
  assert.match(
    originalPreviewSource,
    /\.source-hit \{[\s\S]*?stroke-width:\s*6;[\s\S]*?pointer-events:\s*all;/,
  )
  assert.match(
    originalPreviewSource,
    /\.source-hit-outline \{[\s\S]*?stroke-width:\s*2;[\s\S]*?pointer-events:\s*none;/,
  )
  assert.match(originalPreviewSource, /@click\.stop="handleSourceClick\(element\.source_id, \$event\)"/)
  assert.match(originalPreviewSource, /@keydown\.enter\.prevent="selectSource\(element\.source_id, \$event\)"/)
  assert.match(originalPreviewSource, /class="marker-editor-anchor"/)
  assert.match(convertSource, /template #marker-editor/)
  assert.match(originalPreviewSource, /\.source-hit-layer\.editing \.source-hit\.source-hit--glyph:hover[\s\S]*?var\(--warning\)/)
  assert.match(originalPreviewSource, /\.source-hit-layer\.editing \.source-hit\.selected:not\(\.source-hit--deleted\)[\s\S]*?var\(--accent\)/)
  // 候选面板是独立组件：已识别标记与漏识别 glyph 共用同一套候选项渲染
  assert.match(convertSource, /<MarkerInspector[\s\S]*?:candidates="selectedEntityCandidates"/)
  assert.match(convertSource, /<MarkerInspector[\s\S]*?:candidates="selectedGlyphCandidates"/)
  assert.match(markerInspectorSource, /<RecognitionSymbol\s+:shape="candidate\.shape"/)
  // 简洁候选列表保留可读的无障碍名称、置信度与明确的选中状态
  assert.match(markerInspectorSource, /:aria-label="`\$\{index \+ 1\}\. \$\{labelFor\(candidate\.shape\)\}, \$\{formatScorePercent\(candidate\.score\)\}`"/)
  assert.match(markerInspectorSource, /class="candidate-row__score"/)
  assert.match(markerInspectorSource, /class="candidate-row__check"/)
  assert.match(shapeDescriptorSource, /export function shapeVariantKey/)
  assert.match(shapeDescriptorSource, /export function candidateMatchesTag/)
  assert.match(convertSource, /candidateMatchesTag\(candidate\.shape, entity\.tag, entity\.shape\)/)
  assert.match(convertSource, /candidateMatchesTag\(candidate\.shape, glyph\.tag, glyph\.shape\)/)
  assert.match(originalPreviewSource, /appliedCandidateSelections \?\? \{\}/)
  assert.match(originalPreviewSource, /:mask="`url\(#\$\{overlayMaskId\}\)`"/)
  assert.match(originalPreviewSource, /maskUnits="userSpaceOnUse"\s+x="0"\s+y="0"/)
  assert.match(originalPreviewSource, /maskContentUnits="userSpaceOnUse"\s+mask-type="luminance"/)
  assert.match(originalPreviewSource, /<RecognitionSymbol/)
  assert.match(convertSource, /selectedGlyphId\.value = ''/)
  assert.match(originalPreviewSource, /\.source-hit-layer\.editing \.source-hit:hover/)
  assert.doesNotMatch(originalPreviewSource, /<rect[\s\S]*?class="entity-box"/)
  assert.doesNotMatch(originalPreviewSource, /\.entity-box\s*\{/)
  assert.match(originalPreviewSource, /:class="\{ dimmed: showOverlay && canShowOverlay \}"/)
  assert.match(originalPreviewSource, /\.scan-img\.dimmed\s*\{[\s\S]*?grayscale\(0\.5\) brightness\(0\.95\)/)
  assert.doesNotMatch(originalPreviewSource, /\.scan-img\.dimmed\s*\{[^}]*blur/)
})

test('marker inspector has specific names for dynamics and accidentals', async () => {
  const descriptor = await importTranspiledTypeScript(path.resolve(
    here,
    '../src/renderer/src/utils/shapeDescriptor.ts',
  ))
  const expected = {
    DYNAMICS_F: 'dynamicF',
    DYNAMICS_SFZ: 'dynamicSFZ',
    FLAT: 'accidentalFlat',
    NATURAL: 'accidentalNatural',
    DOUBLE_SHARP: 'accidentalDoubleSharp',
    KEY_SHARP_2: 'keyD',
    KEY_FLAT_1: 'keyF',
    KEY_CANCEL: 'keyC',
    TENUTO: 'articulationTenuto',
    MARCATO_BELOW: 'articulationMarcato',
    STACCATO: 'articulationStaccato',
  }
  for (const [shape, key] of Object.entries(expected)) {
    assert.equal(descriptor.shapeVariantKey(shape), key)
  }
})

test('applied deleted source ids render in an independent persistent mark layer', () => {
  assert.match(convertSource, /:applied-deleted-source-ids="appliedDeletedSourceIds"/)
  assert.match(convertSource, /const appliedDeletedSourceIds = computed\(\(\) => store\.currentPage\?\.deletedSourceIds \?\? \[\]\)/)
  assert.match(originalPreviewSource, /appliedDeletedSourceIds\?: string\[\]/)
  assert.match(originalPreviewSource, /class="deleted-mark-layer"/)
  assert.match(originalPreviewSource, /v-if="deletedMarkElements\.length > 0 && isImage"/)
  // 待删除标记用主题危险色的虚线覆盖层，且不参与点击
  assert.match(originalPreviewSource, /\.deleted-mark \{[\s\S]*?var\(--danger\)[\s\S]*?stroke-dasharray: 5 3;/)
  assert.match(originalPreviewSource, /\.deleted-mark-layer \{[\s\S]*?pointer-events: none;/)
})
