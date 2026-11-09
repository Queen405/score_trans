import assert from 'node:assert/strict'
import test from 'node:test'
import fs from 'node:fs'
import path from 'node:path'
import ts from 'typescript'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { createRequire } from 'node:module'
import { i18nStubUrl } from './lib/i18n-stub.mjs'

const here = path.dirname(fileURLToPath(import.meta.url))

function typeScriptModuleUrl(relativePath, dependencies = {}) {
  const filePath = path.resolve(here, '../src/renderer/src', relativePath)
  let compiled = ts.transpileModule(fs.readFileSync(filePath, 'utf8'), {
    compilerOptions: {
      module: ts.ModuleKind.ES2022,
      target: ts.ScriptTarget.ES2022,
    },
    fileName: filePath,
  }).outputText.replace("from '../i18n'", `from '${i18nStubUrl}'`)
  for (const [name, url] of Object.entries(dependencies)) {
    compiled = compiled.replace(`from '${name}'`, `from '${url}'`)
  }
  return `data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`
}

async function loadTypeScript(relativePath) {
  return import(typeScriptModuleUrl(relativePath))
}

const { isRenderAborted } = await loadTypeScript('utils/renderAbort.ts')
const { RenderRequestGate } = await loadTypeScript('utils/renderRequestGate.ts')
const { apiFetch } = await loadTypeScript('api/client.ts')
const require = createRequire(import.meta.url)
const vueUrl = pathToFileURL(require.resolve('vue')).href
const { effectScope } = await import(vueUrl)
const { usePublicationRender } = await import(typeScriptModuleUrl('composables/usePublicationRender.ts', {
  vue: vueUrl,
  '../utils/renderRequestGate': typeScriptModuleUrl('utils/renderRequestGate.ts'),
  '../api/render': typeScriptModuleUrl('api/render.ts', {
    './client': typeScriptModuleUrl('api/client.ts'),
  }),
}))

test('publication composable sends titles unchanged through the real API serializer', async () => {
  const originalFetch = globalThis.fetch
  const requests = []
  globalThis.fetch = async (url, options) => {
    requests.push({ url, body: JSON.parse(options.body) })
    return new Response(JSON.stringify({ svg_file_id: 'rendered', pages: [] }), {
      headers: { 'Content-Type': 'application/json' },
    })
  }
  const scope = effectScope()
  const publication = scope.run(() => usePublicationRender())
  const text = '// @part 1 name="Voice"\ntitle=海阔天空\n1=G\n4/4\n1 2 3 4 |'
  const cases = {
    batchA4: { pages: [{ jianpu_text: text, title: '简谱' }] },
    jianpuTextSvg: { jianpu_text: text },
    jianpuSvg: { musicxml_file_id: 'xml' },
    finalOutput: { musicxml_file_id: 'xml' },
    normalizeJianpuText: { jianpu_text: text },
  }
  try {
    for (const [method, base] of Object.entries(cases)) {
      for (const titleFields of [{}, { title: null }, { title: '' }, { title: '自定标题' }]) {
        const request = { ...base, ...titleFields }
        const result = await publication[method](request)
        assert.equal(result.error, null)
        assert.deepEqual(requests.at(-1).body, request, `${method} must preserve title intent`)
      }
    }
  } finally {
    scope.stop()
    globalThis.fetch = originalFetch
  }
})

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

test('apiFetch preserves the HTTP status on ApiError', async () => {
  const originalFetch = globalThis.fetch
  globalThis.fetch = async () => new Response(
    JSON.stringify({ error: 'Batch not found' }),
    { status: 404, headers: { 'Content-Type': 'application/json' } },
  )

  try {
    const result = await apiFetch('/history/10/save-all')
    assert.equal(result.data, null)
    assert.equal(result.error?.message, 'Batch not found')
    assert.equal(result.error?.status, 404)
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
