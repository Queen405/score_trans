import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath, pathToFileURL } from 'node:url'
import ts from 'typescript'
import { createPinia, setActivePinia } from 'pinia'

const here = path.dirname(fileURLToPath(import.meta.url))

function compileModule(sourcePath, replacements = []) {
  let compiled = ts.transpileModule(fs.readFileSync(sourcePath, 'utf8'), {
    compilerOptions: {
      module: ts.ModuleKind.ES2022,
      target: ts.ScriptTarget.ES2022,
    },
    fileName: sourcePath,
  }).outputText
  for (const [from, to] of replacements) {
    compiled = compiled.replaceAll(from, to)
  }
  return `data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`
}

const jianpuSectionsPath = path.resolve(
  here,
  '../src/renderer/src/utils/jianpuPageSections.ts',
)
const jianpuSectionsUrl = compileModule(jianpuSectionsPath)
const unsavedChangeStatePath = path.resolve(
  here,
  '../src/renderer/src/utils/unsavedChangeState.ts',
)
const unsavedChangeStateUrl = compileModule(unsavedChangeStatePath)
const workspacePath = path.resolve(
  here,
  '../src/renderer/src/stores/workspace.ts',
)
const workspaceUrl = compileModule(workspacePath, [
  ["from 'pinia'", `from '${pathToFileURL(path.resolve(here, '../node_modules/pinia/dist/pinia.mjs')).href}'`],
  ["from 'vue'", `from '${pathToFileURL(path.resolve(here, '../node_modules/vue/dist/vue.runtime.esm-bundler.js')).href}'`],
  ["from '../utils/jianpuPageSections'", `from '${jianpuSectionsUrl}'`],
  ["from '../utils/unsavedChangeState'", `from '${unsavedChangeStateUrl}'`],
])
const { useWorkspaceStore } = await import(workspaceUrl)

function createLoadedBatch(pageCount = 3) {
  setActivePinia(createPinia())
  const store = useWorkspaceStore()
  const pages = Array.from({ length: pageCount }, (_, index) => ({
    inputFileName: `page-${index + 1}.png`,
    inputFileId: `input-${index + 1}`,
    jianpuText: `${index + 1} |`,
  }))
  store.loadBatch(
    pages,
    0,
    pages.map((_, index) => `svg-${index + 1}`),
    '',
    pages.map((_, index) => ({ page_index: index, ocr_text: `ocr-${index + 1}` })),
    false,
    '67:92:90',
  )
  for (let index = 0; index < pageCount; index += 1) {
    store.setBatchRenderPageOcrText(index, `dirty-${index + 1}`, index !== 1)
  }
  store.setBatchJianpuText(''.padEnd(0), true)
  return store
}

test('removing a middle page reindexes batch OCR state and removes only that page data', () => {
  const store = createLoadedBatch(3)
  const batchId = store.currentBatchId
  const removedId = store.pages[1].id
  store.markBatchJianpuPagePending(removedId)

  store.removePage(1)

  assert.deepEqual(store.currentBatchRenderPageFileIds, ['svg-1', 'svg-3'])
  assert.equal(store.currentBatchRenderLayoutKey, '67:92:90')
  assert.deepEqual(store.batchRenderPageOcrTextsFor(batchId), [
    { page_index: 0, ocr_text: 'dirty-1' },
    { page_index: 1, ocr_text: 'dirty-3' },
  ])
  assert.deepEqual(store.batchRenderPageOcrDirty[batchId], { 0: true, 1: true })
  assert.equal(store.currentBatchRenderPageOcrDirty, true)
  assert.deepEqual(store.currentBatchJianpuPendingPageIds, [])
  assert.equal(store.pages.length, 2)
})

test('removing the last page preserves earlier batch OCR state without stale numeric keys', () => {
  const store = createLoadedBatch(3)
  const batchId = store.currentBatchId

  store.removePage(2)

  assert.deepEqual(store.currentBatchRenderPageFileIds, ['svg-1', 'svg-2'])
  assert.deepEqual(store.batchRenderPageOcrTextsFor(batchId), [
    { page_index: 0, ocr_text: 'dirty-1' },
    { page_index: 1, ocr_text: 'dirty-2' },
  ])
  assert.deepEqual(
    Object.keys(store.batchRenderPageOcrTexts[batchId] ?? {}).map(Number),
    [0, 1],
  )
  assert.deepEqual(store.batchRenderPageOcrDirty[batchId], { 0: true, 1: false })
})

test('removing the final batch page deletes every per-batch record', () => {
  const store = createLoadedBatch(1)
  const batchId = store.currentBatchId
  store.markBatchJianpuPagePending(store.pages[0].id)

  store.removePage(0)

  assert.equal(store.pages.length, 0)
  assert.equal(store.currentBatchId, null)
  assert.equal(store.batchRenderPageFileIds[batchId], undefined)
  assert.equal(store.batchRenderPageOcrTexts[batchId], undefined)
  assert.equal(store.batchRenderPageOcrDirty[batchId], undefined)
  assert.equal(store.batchRenderLayoutKeys[batchId], undefined)
  assert.equal(store.batchJianpuTexts[batchId], undefined)
  assert.equal(store.batchJianpuDirty[batchId], undefined)
  assert.equal(store.batchJianpuPendingPageIds[batchId], undefined)
  assert.equal(store.batchUserChangeRevisions[batchId], undefined)
})

test('render stale state alone does not count as an unsaved user edit', () => {
  const store = createLoadedBatch(1)
  const batchId = store.currentBatchId
  const captured = store.captureBatchChangeRevision(batchId)
  store.acknowledgeBatchChanges(captured, undefined, batchId)

  store.setBatchRenderPageOcrTexts(
    [{ page_index: 0, ocr_text: 'persisted' }],
    true,
    batchId,
  )

  assert.equal(store.currentBatchRenderOutputStale, true)
  assert.equal(store.currentBatchHasUnsavedChanges, false)
  assert.equal(store.hasUnsavedChanges, false)
})

test('store acknowledges only captured edits and keeps a later edit dirty', () => {
  const store = createLoadedBatch(1)
  const batchId = store.currentBatchId
  store.acknowledgeBatchChanges(
    store.captureBatchChangeRevision(batchId),
    undefined,
    batchId,
  )
  store.markBatchAttachmentUserEdited(batchId)
  const captured = store.captureBatchChangeRevision(batchId)
  store.markBatchAttachmentUserEdited(batchId)

  store.acknowledgeBatchChanges(captured, undefined, batchId)

  assert.equal(store.currentBatchAttachmentUserEdited, true)
  assert.equal(store.hasUnsavedChanges, true)
})

test('workspace load and replacement preserve independent text-anchor baselines', () => {
  setActivePinia(createPinia())
  const store = useWorkspaceStore()
  const baselineAnchors = [{
    source_id: 's1:i1',
    start_utf16: 3,
    end_utf16: 4,
    role: 'note',
    valid: true,
  }]
  store.loadBatch([{
    inputFileName: 'page.png',
    inputFileId: 'input',
    jianpuText: '😀 1 |',
    textAnchorBaselineText: '😀 1 |',
    textAnchorBaselineAnchors: baselineAnchors,
  }], 0)

  baselineAnchors[0].start_utf16 = 99
  assert.equal(store.pages[0].textAnchorBaselineText, '😀 1 |')
  assert.equal(store.pages[0].textAnchorBaselineAnchors[0].start_utf16, 3)

  store.replacePage(0, [{
    inputFileName: 'replacement.png',
    inputFileId: 'replacement',
    jianpuText: '😀 2 |',
    textAnchorBaselineText: '😀 2 |',
    textAnchorBaselineAnchors: [{ ...baselineAnchors[0], start_utf16: 3 }],
  }])

  assert.equal(store.pages[0].textAnchorBaselineText, '😀 2 |')
  assert.equal(store.pages[0].textAnchorBaselineAnchors[0].start_utf16, 3)
})
