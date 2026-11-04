import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import ts from 'typescript'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))

function compileModule(sourcePath, replacements = []) {
  let compiled = ts.transpileModule(fs.readFileSync(sourcePath, 'utf8'), {
    compilerOptions: {
      module: ts.ModuleKind.ES2022,
      target: ts.ScriptTarget.ES2022,
    },
    fileName: sourcePath,
  }).outputText
  for (const [from, to] of replacements) compiled = compiled.replaceAll(from, to)
  return `data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`
}

const syntaxUrl = compileModule(path.resolve(
  here,
  '../src/renderer/src/utils/jianpuSyntax.ts',
))
const sectionsUrl = compileModule(
  path.resolve(here, '../src/renderer/src/utils/jianpuPageSections.ts'),
  [["from './jianpuSyntax'", `from '${syntaxUrl}'`]],
)
const payloadUrl = compileModule(
  path.resolve(here, '../src/renderer/src/utils/historySavePayload.ts'),
  [["from './jianpuPageSections'", `from '${sectionsUrl}'`]],
)
const { buildBatchPersistenceSnapshot } = await import(payloadUrl)

function page(index, historyBatchId = 10) {
  return {
    id: `local-${index}`,
    batchId: 'local-batch',
    historyPageId: historyBatchId ? 100 + index : null,
    historyBatchId,
    taskId: `task-${index}`,
    inputFileName: `page-${index}.png`,
    inputFileId: `input-${index}`,
    sourceDocumentFileId: 'source-pdf',
    sourceDocumentName: 'score.pdf',
    sourcePageIndex: index,
    musicxmlFileId: `xml-${index}`,
    jianpuText: `old-${index}`,
    ocrText: `ocr-${index}`,
    textAttachments: [{ id: `attachment-${index}`, text: `text-${index}`, role: 'title', anchor: { kind: 'page', page_index: index } }],
    svgFileId: `svg-${index}`,
    overlayFileId: `overlay-${index}`,
    sourceMapFileId: `map-${index}`,
    textHash: `hash-${index}`,
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
    omrFileId: `omr-${index}`,
    originalMusicxml: `<original-${index}/>` ,
    workingMusicxml: `<working-${index}/>` ,
    deletedSourceIds: [`deleted-${index}`],
  }
}

const batchText = '// @page 1 name="page-0.png"\nnew-0\n// @page 2 name="page-1.png"\nnew-1'

test('existing batch payload saves every page including non-current attachments', () => {
  const snapshot = buildBatchPersistenceSnapshot({
    pages: [page(0), page(1)],
    jianpuText: batchText,
    renderPageFileIds: ['render-1'],
    renderPageOcrTexts: [{ page_index: 0, ocr_text: 'render-ocr' }],
    renderOutputStale: false,
    renderLayoutKey: 'layout',
    source: 'save',
  })

  assert.equal(snapshot.kind, 'update')
  assert.equal(snapshot.historyBatchId, 10)
  assert.equal(snapshot.request.pages[1].jianpu_text, 'new-1')
  assert.equal(snapshot.request.pages[1].text_attachments[0].id, 'attachment-1')
  assert.equal(snapshot.request.pages[1].text_anchor_baseline_text, 'baseline-1')
  assert.equal(
    snapshot.request.pages[1].text_anchor_baseline_anchors[0].source_id,
    'source-1',
  )
  assert.equal(snapshot.request.render_output_stale, false)
})

test('new batch payload creates all page and render state in one request', () => {
  const snapshot = buildBatchPersistenceSnapshot({
    pages: [page(0, null), page(1, null)],
    jianpuText: batchText,
    renderPageFileIds: [],
    renderPageOcrTexts: [],
    renderOutputStale: false,
    renderLayoutKey: '',
    source: 'save',
  })

  assert.equal(snapshot.kind, 'create')
  assert.equal(snapshot.request.pages.length, 2)
  assert.equal(snapshot.request.pages[0].jianpu_text, 'new-0')
  assert.equal(snapshot.request.pages[1].text_attachments[0].text, 'text-1')
  assert.equal(snapshot.request.pages[0].text_anchor_baseline_text, 'baseline-0')
  assert.equal(snapshot.request.pages[1].source_document_file_id, 'source-pdf')
  assert.equal(snapshot.request.pages[1].source_document_name, 'score.pdf')
  assert.equal(snapshot.request.pages[1].source_page_index, 1)
  assert.equal(snapshot.request.render_output_stale, true)
})

test('mixed or incomplete history identity is rejected before saving', () => {
  const mixed = [page(0), page(1)]
  mixed[1].historyPageId = null

  assert.throws(
    () => buildBatchPersistenceSnapshot({
      pages: mixed,
      jianpuText: batchText,
      renderPageFileIds: [],
      renderPageOcrTexts: [],
      renderOutputStale: true,
      renderLayoutKey: '',
      source: 'save',
    }),
    /history identity/,
  )
})
