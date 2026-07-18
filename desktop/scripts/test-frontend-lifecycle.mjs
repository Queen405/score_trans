import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'

const here = path.dirname(fileURLToPath(import.meta.url))
const source = (relativePath) => fs.readFileSync(path.resolve(here, relativePath), 'utf8')

const logStoreSource = source('../src/renderer/src/stores/log.ts')
const logPanelSource = source('../src/renderer/src/components/LogPanel.vue')
const uploaderSource = source('../src/renderer/src/components/FileUploader.vue')
const recognizeSource = source('../src/renderer/src/views/RecognizeView.vue')
const assistantComponentSource = source('../src/renderer/src/components/AiAssistant.vue')
const assistantStoreSource = source('../src/renderer/src/stores/assistant.ts')
const editorSource = source('../src/renderer/src/components/JianpuEditor.vue')
const convertSource = source('../src/renderer/src/views/ConvertView.vue')
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
  assert.match(uploaderSource, /const detail = error\.value \|\| '上传失败，请重试'/)
  assert.match(uploaderSource, /log\.addError\(`上传失败：\$\{message\}`\)/)
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

test('convert distinguishes one external editor sync without a nextTick timing flag', () => {
  assert.doesNotMatch(convertSource, /programmaticUpdate/)
  assert.match(convertSource, /let editorSyncGeneration = 0/)
  assert.match(convertSource, /pendingExternalEditorSync = \{ generation, text: v \}/)
  assert.match(convertSource, /const isExternalSync = pendingExternalEditorSync\?\.text === v/)
  assert.match(convertSource, /if \(isExternalSync\) pendingExternalEditorSync = null/)
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

test('MIDI generation failures unload stale audio and notify the user', () => {
  assert.match(playerSource, /useMessage\(\)/)
  assert.match(playerSource, /useLogStore\(\)/)
  assert.match(playerSource, /logStore\.addError\(/)
  assert.match(playerSource, /player\.unload\(\)/)
  assert.match(playerSource, /message\.error\(/)
})
