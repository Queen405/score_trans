import assert from 'node:assert/strict'
import test from 'node:test'
import fs from 'node:fs'
import path from 'node:path'
import ts from 'typescript'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))

async function loadTypeScript(relativePath) {
  const filePath = path.resolve(here, '../src/renderer/src', relativePath)
  const compiled = ts.transpileModule(fs.readFileSync(filePath, 'utf8'), {
    compilerOptions: {
      module: ts.ModuleKind.ES2022,
      target: ts.ScriptTarget.ES2022,
    },
    fileName: filePath,
  }).outputText
  return import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`)
}

const { isRenderAborted } = await loadTypeScript('utils/renderAbort.ts')
const { RenderRequestGate } = await loadTypeScript('utils/renderRequestGate.ts')
const { apiFetch } = await loadTypeScript('api/client.ts')

function deferred() {
  let resolve
  let reject
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

test('render abort classifier handles DOMException and ApiError codes', () => {
  assert.equal(isRenderAborted(new DOMException('expired', 'AbortError')), true)
  assert.equal(isRenderAborted({ name: 'AbortError' }), true)
  assert.equal(isRenderAborted({ code: 'aborted' }), true)
  assert.equal(isRenderAborted(new Error('aborted')), false)
  assert.equal(isRenderAborted({ code: 'network' }), false)
})

test('apiFetch preserves AbortError as an aborted ApiError code', async () => {
  const originalFetch = globalThis.fetch
  globalThis.fetch = async () => {
    throw new DOMException('network abort', 'AbortError')
  }

  try {
    const result = await apiFetch('/render/test')
    assert.equal(result.data, null)
    assert.equal(result.error?.code, 'aborted')
    assert.equal(isRenderAborted(result.error), true)
  } finally {
    globalThis.fetch = originalFetch
  }
})

test('stale render result is rejected even when the request resolves successfully', async () => {
  const gate = new RenderRequestGate()
  const first = deferred()
  const second = deferred()

  const firstResult = gate.current(() => first.promise)
  const secondResult = gate.current(() => second.promise)
  first.resolve('old')

  await assert.rejects(firstResult, (error) => isRenderAborted(error))
  second.resolve('new')
  assert.equal(await secondResult, 'new')
})

test('stale render result is rejected after an abort-style request failure', async () => {
  const gate = new RenderRequestGate()
  const first = deferred()
  const second = deferred()

  const firstResult = gate.current(() => first.promise)
  const secondResult = gate.current(() => second.promise)
  first.resolve({ data: null, error: { code: 'aborted' } })

  await assert.rejects(firstResult, (error) => isRenderAborted(error))
  second.resolve('new')
  assert.equal(await secondResult, 'new')
})

test('disposing the gate aborts a pending current request', async () => {
  const gate = new RenderRequestGate()
  const pending = deferred()
  const result = gate.current(() => pending.promise)
  gate.dispose()
  pending.resolve('late')

  await assert.rejects(result, (error) => isRenderAborted(error))
})
