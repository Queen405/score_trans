import assert from 'node:assert/strict'
import test from 'node:test'
import ts from 'typescript'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const gatePath = path.resolve(here, '../src/renderer/src/utils/latestAsyncGate.ts')
const compiled = ts.transpileModule(fs.readFileSync(gatePath, 'utf8'), {
  compilerOptions: {
    module: ts.ModuleKind.ES2022,
    target: ts.ScriptTarget.ES2022,
  },
  fileName: gatePath,
}).outputText
const { LatestAsyncGate } = await import(
  `data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`
)

function deferred() {
  let resolve
  let reject
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

async function nextTurn() {
  await new Promise((resolve) => setImmediate(resolve))
}

test('waiter follows the latest generation during rapid A to B to C changes', async () => {
  const gate = new LatestAsyncGate()
  const a = deferred()
  const b = deferred()
  const c = deferred()
  gate.track(a.promise)

  let result
  const waiting = gate.waitForLatest().then((value) => {
    result = value
  })
  gate.track(b.promise)
  gate.track(c.promise)
  c.resolve()
  await nextTurn()

  assert.equal(result, true, 'the completed C generation should release the waiter')
  await waiting
})

test('latest generation failure is reported without throwing', async () => {
  const gate = new LatestAsyncGate()
  const failure = deferred()
  gate.track(failure.promise)
  const waiting = gate.waitForLatest()
  failure.reject(new Error('load failed'))

  assert.equal(await waiting, false)
})

test('dispose releases a waiter even when the current generation never settles', async () => {
  const gate = new LatestAsyncGate()
  const pending = deferred()
  gate.track(pending.promise)
  const waiting = gate.waitForLatest()
  gate.dispose()

  assert.equal(await waiting, false)
})
