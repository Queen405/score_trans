import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import ts from 'typescript'

const filename = new URL('../src/renderer/src/utils/fileTextCache.ts', import.meta.url)
const source = fs.readFileSync(filename, 'utf8').replace("import { fetchFileBlob } from '../api/client'", '')
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
}).outputText
const { createFileTextCache } = await import(
  `data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`
)

test('20-page preview and playback loads share each SVG request', async () => {
  let calls = 0
  const cache = createFileTextCache(async (id) => {
    calls += 1
    await new Promise((resolve) => setTimeout(resolve, 5))
    return `text:${id}`
  })
  const ids = Array.from({ length: 20 }, (_, index) => `page-${index}`)
  const results = await Promise.all(ids.flatMap((id) => [cache(id), cache(id)]))
  assert.equal(calls, 20)
  assert.equal(results.length, 40)
  assert.equal(results[0], 'text:page-0')
  assert.equal(await cache('page-0'), 'text:page-0')
  assert.equal(calls, 20)
})

test('aborting one consumer does not cancel the shared request', async () => {
  let resolveRequest
  let calls = 0
  const cache = createFileTextCache(() => {
    calls += 1
    return new Promise((resolve) => { resolveRequest = resolve })
  })
  const first = cache('shared')
  const controller = new AbortController()
  const second = cache('shared', controller.signal)
  controller.abort()
  await assert.rejects(second, { name: 'AbortError' })
  resolveRequest('ok')
  assert.equal(await first, 'ok')
  assert.equal(calls, 1)
})

test('failed requests can retry and capacity evicts the oldest value', async () => {
  let attempts = 0
  const retry = createFileTextCache(async () => {
    attempts += 1
    if (attempts === 1) throw new Error('offline')
    return 'ok'
  })
  await assert.rejects(retry('retry'))
  assert.equal(await retry('retry'), 'ok')

  let calls = 0
  const cache = createFileTextCache(async (id) => {
    calls += 1
    return id
  }, 2)
  await cache('a')
  await cache('b')
  await cache('a')
  await cache('c')
  await cache('b')
  assert.equal(calls, 4)
})
