import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import ts from 'typescript'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))

function compileModule(sourcePath, replacements = []) {
  let compiled = ts.transpileModule(fs.readFileSync(sourcePath, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
    fileName: sourcePath,
  }).outputText
  for (const [from, to] of replacements) compiled = compiled.replaceAll(from, to)
  return `data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`
}

const sectionsUrl = compileModule(path.resolve(here, '../src/renderer/src/utils/jianpuPageSections.ts'))
const payloadUrl = compileModule(
  path.resolve(here, '../src/renderer/src/utils/historySavePayload.ts'),
  [["from './jianpuPageSections'", `from '${sectionsUrl}'`]],
)
const persistenceUrl = compileModule(
  path.resolve(here, '../src/renderer/src/utils/workspacePersistence.ts'),
  [["from './historySavePayload'", `from '${payloadUrl}'`]],
)
const { createWorkspacePersistence } = await import(persistenceUrl)

function page(index, historyBatchId = 10) {
  return {
    id: `local-${index}`,
    batchId: 'local-batch',
    historyPageId: historyBatchId ? 100 + index : null,
    historyBatchId,
    taskId: '',
    inputFileName: `page-${index}.png`,
    inputFileId: `input-${index}`,
    musicxmlFileId: '',
    jianpuText: `${index} |`,
    ocrText: '',
    textAttachments: [],
    svgFileId: '',
    overlayFileId: '',
    sourceMapFileId: '',
    textHash: '',
    textAnchors: [],
    textAnchorBaselineText: `baseline-${index}`,
    textAnchorBaselineAnchors: [{
      source_id: `source-${index}`,
      start_utf16: 0,
      end_utf16: 1,
      role: 'note',
      valid: true,
    }],
    status: 'completed',
    errorMessage: '',
    omrFileId: '',
    originalMusicxml: '',
    workingMusicxml: '',
    deletedSourceIds: [],
  }
}

function response(id, pages) {
  return {
    id,
    created_at: '',
    page_count: pages.length,
    status: 'completed',
    jianpu_text: 'batch-text',
    render_page_file_ids: [],
    render_page_ocr_texts: [],
    render_output_stale: true,
    render_layout_key: '',
    pages: pages.map((item, index) => ({
      id: 100 + index,
      batch_id: id,
      input_file_name: item.inputFileName,
      input_file_id: item.inputFileId,
      task_id: '',
      musicxml_file_id: '',
      jianpu_text: item.jianpuText,
      ocr_text: '',
      text_attachments: [],
      text_anchor_baseline_text: item.textAnchorBaselineText,
      text_anchor_baseline_anchors: item.textAnchorBaselineAnchors,
      svg_file_id: '',
      status: 'completed',
      error_message: '',
    })),
  }
}

function fakeStore(pages) {
  const acknowledgements = []
  const patches = []
  return {
    pages,
    currentBatchId: 'local-batch',
    batches: [{ id: 'local-batch', pages }],
    batchJianpuTextFor: () => 'batch-text',
    batchRenderPageOcrTextsFor: () => [],
    batchRenderPageFileIds: { 'local-batch': [] },
    batchRenderOutputStale: { 'local-batch': true },
    batchRenderLayoutKeys: { 'local-batch': '' },
    captureBatchChangeRevision: () => ({ jianpu: 1, ocr: 2, attachments: 3 }),
    acknowledgeBatchChanges: (...args) => acknowledgements.push(args),
    isBatchUnsaved: () => true,
    hasUnsavedChanges: false,
    patchPageById: (id, patch) => patches.push([id, patch]),
    setBatchRenderPageFileIds: () => {},
    setBatchRenderPageOcrTexts: () => {},
    acknowledgements,
    patches,
  }
}

test('existing batch save uses one atomic request and acknowledges captured revisions', async () => {
  const pages = [page(0), page(1)]
  const store = fakeStore(pages)
  const calls = []
  const persistence = createWorkspacePersistence({
    saveBatch: async (id, request) => {
      calls.push([id, request])
      return { data: response(id, pages), error: null }
    },
    create: async () => assert.fail('create must not be called'),
    updateRenderState: async () => assert.fail('render-state must not be called'),
  })

  await persistence.saveBatch(store, 'local-batch')

  assert.equal(calls.length, 1)
  assert.equal(calls[0][0], 10)
  assert.equal(calls[0][1].pages[1].text_anchor_baseline_text, 'baseline-1')
  assert.deepEqual(store.acknowledgements[0], [
    { jianpu: 1, ocr: 2, attachments: 3 },
    undefined,
    'local-batch',
  ])
})

test('save-all refuses to finish when an edit remains after the batch pass', async () => {
  const pages = [page(0)]
  const store = fakeStore(pages)
  store.hasUnsavedChanges = true
  store.isBatchUnsaved = () => false
  const persistence = createWorkspacePersistence({
    saveBatch: async () => assert.fail('saveBatch must not be called'),
    create: async () => assert.fail('create must not be called'),
    updateRenderState: async () => assert.fail('render-state must not be called'),
  })

  await assert.rejects(
    persistence.saveAllUnsavedBatches(store),
    /New edits were made while saving/,
  )
})

test('new batch save creates once and binds returned history ids', async () => {
  const pages = [page(0, null), page(1, null)]
  const store = fakeStore(pages)
  let createCount = 0
  const persistence = createWorkspacePersistence({
    saveBatch: async () => assert.fail('saveBatch must not be called'),
    create: async () => {
      createCount += 1
      return { data: response(20, pages), error: null }
    },
    updateRenderState: async () => assert.fail('render-state must not be called'),
  })

  await persistence.saveBatch(store, 'local-batch')

  assert.equal(createCount, 1)
  assert.equal(store.patches.length, 2)
  assert.deepEqual(store.patches[1][1], {
    historyPageId: 101,
    historyBatchId: 20,
    jianpuText: '1 |',
    textAnchorBaselineText: 'baseline-1',
    textAnchorBaselineAnchors: pages[1].textAnchorBaselineAnchors,
  })
})

test('render-state persistence only acknowledges OCR changes', async () => {
  const pages = [page(0)]
  const store = fakeStore(pages)
  const persistence = createWorkspacePersistence({
    saveBatch: async () => assert.fail('saveBatch must not be called'),
    create: async () => assert.fail('create must not be called'),
    updateRenderState: async (id, request) => ({
      data: { ...response(id, pages), ...request },
      error: null,
    }),
  })

  await persistence.saveRenderState(store, 'local-batch', {
    renderPageFileIds: ['render-1'],
    renderPageOcrTexts: [{ page_index: 0, ocr_text: 'ocr' }],
    renderOutputStale: false,
    renderLayoutKey: 'layout',
  })

  assert.deepEqual(store.acknowledgements[0], [
    { jianpu: 1, ocr: 2, attachments: 3 },
    ['ocr'],
    'local-batch',
  ])
})

test('save response keeps an explicitly empty canonical anchor list', async () => {
  const pages = [page(0)]
  pages[0].textAnchorBaselineAnchors = [{
    source_id: 'stale-source',
    start_utf16: 0,
    end_utf16: 1,
    role: 'note',
    valid: true,
  }]
  const store = fakeStore(pages)
  const persistence = createWorkspacePersistence({
    saveBatch: async (id) => {
      const saved = response(id, pages)
      saved.pages[0].text_anchor_baseline_text = 'canonical-without-mappings'
      saved.pages[0].text_anchor_baseline_anchors = []
      return { data: saved, error: null }
    },
    create: async () => assert.fail('create must not be called'),
    updateRenderState: async () => assert.fail('render-state must not be called'),
  })

  await persistence.saveBatch(store, 'local-batch')

  assert.deepEqual(store.patches[0][1].textAnchorBaselineAnchors, [])
})
