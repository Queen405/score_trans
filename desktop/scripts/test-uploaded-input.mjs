import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import ts from 'typescript'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const sourcePath = path.resolve(here, '../src/renderer/src/utils/uploadedInput.ts')
const compiled = ts.transpileModule(fs.readFileSync(sourcePath, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
}).outputText
const moduleUrl = `data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`
const { uploadedInputPages } = await import(moduleUrl)

test('PDF upload keeps its document identity and page indexes', () => {
  const pages = uploadedInputPages({
    file_id: 'pdf-source',
    filename: 'Doc1.pdf',
    size: 100,
    pages: [
      { file_id: 'page-1', filename: 'Doc1_page_001.png', page_index: 0 },
      { file_id: 'page-2', filename: 'Doc1_page_002.png', page_index: 1 },
    ],
  })

  assert.deepEqual(pages.map((page) => page.inputFileId), ['page-1', 'page-2'])
  assert.deepEqual(pages.map((page) => page.sourcePageIndex), [0, 1])
  assert.ok(pages.every((page) => page.sourceDocumentFileId === 'pdf-source'))
  assert.ok(pages.every((page) => page.sourceDocumentName === 'Doc1.pdf'))
})

test('ordinary image upload does not pretend to have a PDF source', () => {
  assert.deepEqual(uploadedInputPages({
    file_id: 'image', filename: 'scan.png', size: 100, pages: null,
  }), [{
    inputFileId: 'image',
    inputFileName: 'scan.png',
    sourceDocumentFileId: '',
    sourceDocumentName: '',
    sourcePageIndex: -1,
  }])
})
