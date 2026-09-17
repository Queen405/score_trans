import assert from 'node:assert/strict'
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
  assert.match(convertSource, /:disabled="loadingEntities"/)
  assert.match(
    convertSource,
    /@click="applyCorrections"[\s\S]*?>\s*\{\{ t\('convert\.marker\.apply'\) \}\}\s*<\/n-button>/,
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
  // 应用成功后自动退出删除标记模式，无需再点"取消"
  assert.match(
    convertSource,
    /message\.success\(t\('convert\.marker\.applied'\)\)\s*\n\s*editMode\.value = false/,
  )
  // 多页 OMR 提示文案与功能名一致
  assert.match(convertSource, /multiPageOmr/)
})

test('deleted entity markers render as a faint red outline without fill', () => {
  // 不用红色填充覆盖 notehead，也不整体调 opacity 把轮廓弄没；
  // 删除标记只留淡红虚线轮廓（stroke-opacity 控制浓淡），填充不可见但保留可点击。
  assert.match(
    originalPreviewSource,
    /\.entity-box\.deleted \{[\s\S]*?stroke-opacity:\s*0\.3/,
  )
  assert.match(
    originalPreviewSource,
    /\.entity-box\.deleted:hover \{[\s\S]*?stroke-opacity:\s*0\.65/,
  )
  assert.match(originalPreviewSource, /aria-label="t\('components\.originalPreview\.deletableMarkLabel'\)"/)
  assert.match(originalPreviewSource, /transition: fill 0\.15s, stroke-opacity 0\.15s;/)
})

test('applied deleted source ids render in an independent persistent mark layer', () => {
  assert.match(convertSource, /:applied-deleted-source-ids="appliedDeletedSourceIds"/)
  assert.match(convertSource, /const appliedDeletedSourceIds = computed\(\(\) => store\.currentPage\?\.deletedSourceIds \?\? \[\]\)/)
  assert.match(originalPreviewSource, /appliedDeletedSourceIds\?: string\[\]/)
  assert.match(originalPreviewSource, /class="deleted-mark-layer"/)
  assert.match(originalPreviewSource, /v-if="deletedMarkElements\.length > 0 && isImage"/)
  assert.match(originalPreviewSource, /\.deleted-mark \{[\s\S]*?fill: none;[\s\S]*?stroke-dasharray: 6 4;/)
  assert.match(originalPreviewSource, /\.deleted-mark-layer \{[\s\S]*?pointer-events: none;/)
})
