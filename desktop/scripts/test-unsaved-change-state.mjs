import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import ts from 'typescript'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const sourcePath = path.resolve(
  here,
  '../src/renderer/src/utils/unsavedChangeState.ts',
)

async function loadModule() {
  const source = fs.readFileSync(sourcePath, 'utf8')
  const compiled = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ES2022,
      target: ts.ScriptTarget.ES2022,
    },
    fileName: sourcePath,
  }).outputText
  return import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`)
}

test('each user-edit category independently makes a batch unsaved', async () => {
  const { createRevisionState, markEdited, hasUnsavedChanges } = await loadModule()

  for (const kind of ['jianpu', 'ocr', 'attachments']) {
    const state = markEdited(createRevisionState(), kind)
    assert.equal(hasUnsavedChanges(state), true)
  }
})

test('acknowledging a captured revision preserves edits made while saving', async () => {
  const {
    acknowledgeRevision,
    captureEditedRevision,
    createRevisionState,
    hasUnsavedChanges,
    markEdited,
  } = await loadModule()
  const beforeSave = markEdited(createRevisionState(), 'jianpu')
  const captured = captureEditedRevision(beforeSave)
  const editedDuringSave = markEdited(beforeSave, 'jianpu')

  const acknowledged = acknowledgeRevision(editedDuringSave, captured)

  assert.equal(acknowledged.saved.jianpu, 1)
  assert.equal(acknowledged.edited.jianpu, 2)
  assert.equal(hasUnsavedChanges(acknowledged), true)
})

test('render persistence can acknowledge OCR without clearing attachments', async () => {
  const {
    acknowledgeRevision,
    captureEditedRevision,
    createRevisionState,
    hasUnsavedChanges,
    markEdited,
  } = await loadModule()
  let state = markEdited(createRevisionState(), 'ocr')
  state = markEdited(state, 'attachments')

  const acknowledged = acknowledgeRevision(
    state,
    captureEditedRevision(state),
    ['ocr'],
  )

  assert.equal(acknowledged.saved.ocr, acknowledged.edited.ocr)
  assert.equal(acknowledged.saved.attachments, 0)
  assert.equal(hasUnsavedChanges(acknowledged), true)
})

test('acknowledging every captured category makes an unchanged batch clean', async () => {
  const {
    acknowledgeRevision,
    captureEditedRevision,
    createRevisionState,
    hasUnsavedChanges,
    markEdited,
  } = await loadModule()
  let state = markEdited(createRevisionState(), 'jianpu')
  state = markEdited(state, 'ocr')
  state = markEdited(state, 'attachments')

  state = acknowledgeRevision(state, captureEditedRevision(state))

  assert.equal(hasUnsavedChanges(state), false)
})
