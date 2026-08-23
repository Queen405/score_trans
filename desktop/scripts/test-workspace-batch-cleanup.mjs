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
const workspacePath = path.resolve(
  here,
  '../src/renderer/src/stores/workspace.ts',
)
const workspaceUrl = compileModule(workspacePath, [
  ["from 'pinia'", `from '${pathToFileURL(path.resolve(here, '../node_modules/pinia/dist/pinia.mjs')).href}'`],
  ["from 'vue'", `from '${pathToFileURL(path.resolve(here, '../node_modules/vue/dist/vue.runtime.esm-bundler.js')).href}'`],
  ["from '../utils/jianpuPageSections'", `from '${jianpuSectionsUrl}'`],
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
})
