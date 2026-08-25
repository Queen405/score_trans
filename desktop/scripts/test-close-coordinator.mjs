import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import ts from 'typescript'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const sourcePath = path.resolve(here, '../src/main/closeCoordinator.ts')
const compiled = ts.transpileModule(fs.readFileSync(sourcePath, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
  fileName: sourcePath,
}).outputText
const { CloseCoordinator } = await import(
  `data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`
)

test('duplicate close attempts reuse one pending request', () => {
  const coordinator = new CloseCoordinator()

  const first = coordinator.request('close')
  const duplicate = coordinator.request('close')

  assert.equal(first.isNew, true)
  assert.equal(duplicate.isNew, false)
  assert.equal(duplicate.request.requestId, first.request.requestId)
})

test('stale renderer decisions cannot approve a newer close request', () => {
  const coordinator = new CloseCoordinator()
  const first = coordinator.request('close').request
  coordinator.resolve(first.requestId, 'cancel')
  const second = coordinator.request('close').request

  const stale = coordinator.resolve(first.requestId, 'proceed')

  assert.deepEqual(stale, { kind: 'stale' })
  assert.equal(coordinator.pendingRequest?.requestId, second.requestId)
})

test('cancel clears pending state and proceed preserves relaunch intent', () => {
  const coordinator = new CloseCoordinator()
  const cancelled = coordinator.request('close').request
  assert.deepEqual(coordinator.resolve(cancelled.requestId, 'cancel'), { kind: 'cancel' })
  assert.equal(coordinator.pendingRequest, null)

  const relaunch = coordinator.request('relaunch').request
  assert.deepEqual(coordinator.resolve(relaunch.requestId, 'proceed'), {
    kind: 'proceed',
    intent: 'relaunch',
  })
  assert.equal(coordinator.pendingRequest, null)
})
