import assert from 'node:assert/strict'
import test from 'node:test'
import fs from 'node:fs'
import ts from 'typescript'
import { fileURLToPath } from 'node:url'
import { i18nStubUrl } from './lib/i18n-stub.mjs'

function compile(relative) {
  const file = fileURLToPath(new URL(`../src/renderer/src/${relative}`, import.meta.url))
  return ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
    fileName: file,
  }).outputText
}
function moduleUrl(code) {
  return `data:text/javascript;base64,${Buffer.from(code).toString('base64')}`
}
const source = compile('composables/useLiveJianpuPreview.ts')
  .replace("from 'vue'", `from '${import.meta.resolve('vue')}'`)
  .replace("import { renderApi } from '../api/render';", 'const renderApi = {};')
  .replace("'../utils/asyncCoordination'", JSON.stringify(moduleUrl(compile('utils/asyncCoordination.ts'))))
  .replace("'../utils/renderAbort'", JSON.stringify(moduleUrl(compile('utils/renderAbort.ts'))))
  .replace("from '../i18n'", `from '${i18nStubUrl}'`)
const { useLiveJianpuPreview } = await import(moduleUrl(source))

function harness(t) {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const calls = []
  const preview = useLiveJianpuPreview((request, signal) => new Promise((resolve) => calls.push({ request, signal, resolve })))
  t.after(() => preview.dispose())
  function update(text, cursor = 0, documentId = 'a', enabled = true) {
    preview.update({ documentId, enabled, request: { jianpu_text: text, cursor_offset: cursor } })
  }
  async function respond(index, value) {
    calls[index].resolve(value)
    await Promise.resolve()
    await Promise.resolve()
  }
  return { preview, calls, update, respond, tick: () => t.mock.timers.tick(150) }
}
const success = (svg, warnings = []) => ({ data: { svg, warnings, jianpu_text: '' }, error: null })
const failure = (message = '第7小节错误') => ({ data: null, error: { message, code: 'jianpu_syntax' } })

test('keeps last SVG during loading/failure, then replaces it for a valid measure', async (t) => {
  const { preview, update, tick, respond } = harness(t)
  update('valid')
  tick()
  await respond(0, success('old'))
  update('bad7 | good9', 0)
  assert.equal(preview.loading.value, true)
  assert.equal(preview.svg.value, 'old')
  tick()
  await respond(1, failure())
  assert.equal(preview.svg.value, 'old')
  assert.equal(preview.error.value, '第7小节错误')
  update('bad7 | good9', 7)
  tick()
  await respond(2, success('measure9'))
  assert.equal(preview.svg.value, 'measure9')
  assert.equal(preview.error.value, '')
})

test('late error and finally cannot overwrite a newer success', async (t) => {
  const { preview, calls, update, tick, respond } = harness(t)
  update('bad7 | good9', 0)
  tick()
  update('bad7 | good9', 7)
  assert.equal(calls[0].signal.aborted, true)
  tick()
  await respond(1, success('measure9'))
  await respond(0, failure())
  assert.equal(preview.svg.value, 'measure9')
  assert.equal(preview.error.value, '')
  assert.equal(preview.loading.value, false)
})

test('invalidates immediately during debounce, and captures the text/cursor snapshot', async (t) => {
  const { preview, calls, update, tick, respond } = harness(t)
  update('first', 1)
  tick()
  update('second', 2)
  await respond(0, success('stale'))
  assert.equal(preview.svg.value, '')
  assert.equal(preview.loading.value, true)
  update('third', 3)
  tick()
  assert.equal(calls.length, 2)
  assert.deepEqual(calls[1].request, { jianpu_text: 'third', cursor_offset: 3 })
  await respond(1, success('third'))
  assert.equal(preview.svg.value, 'third')
})

for (const action of ['clear', 'disable', 'switch', 'dispose']) {
  test(`${action} clears the preview and prevents stale response resurrection`, async (t) => {
    const { preview, calls, update, tick, respond } = harness(t)
    update('first')
    tick()
    await respond(0, success('old'))
    update('pending')
    tick()
    if (action === 'clear') update('')
    if (action === 'disable') update('pending', 0, 'a', false)
    if (action === 'switch') update('different', 0, 'b')
    if (action === 'dispose') preview.dispose()
    assert.equal(preview.svg.value, '')
    assert.equal(calls[1].signal.aborted, true)
    await respond(1, success('stale'))
    assert.equal(preview.svg.value, '')
    assert.equal(preview.error.value, '')
  })
}

test('warnings belong to the current successful preview and aborts are silent', async (t) => {
  const { preview, update, tick, respond } = harness(t)
  const warnings = [{ id: 'context', message: '沿用最近有效设置', severity: 'warning' }]
  update('fallback')
  tick()
  await respond(0, success('fallback', warnings))
  assert.deepEqual(preview.warnings.value, warnings)
  update('fixed')
  tick()
  await respond(1, success('fixed'))
  assert.deepEqual(preview.warnings.value, [])
  update('aborted')
  tick()
  await respond(2, { data: null, error: { code: 'aborted', message: 'cancelled' } })
  assert.equal(preview.error.value, '')
  assert.equal(preview.svg.value, 'fixed')
})
