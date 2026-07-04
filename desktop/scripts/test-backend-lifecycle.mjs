import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'

const here = path.dirname(fileURLToPath(import.meta.url))
const preloadSource = fs.readFileSync(
  path.resolve(here, '../src/preload/index.ts'),
  'utf8',
)
const preloadTypesSource = fs.readFileSync(
  path.resolve(here, '../src/preload/index.d.ts'),
  'utf8',
)
const backendSource = fs.readFileSync(
  path.resolve(here, '../src/main/backend.ts'),
  'utf8',
)
const mainSource = fs.readFileSync(
  path.resolve(here, '../src/main/index.ts'),
  'utf8',
)
const rendererMainSource = fs.readFileSync(
  path.resolve(here, '../src/renderer/src/main.ts'),
  'utf8',
)
const apiClientSource = fs.readFileSync(
  path.resolve(here, '../src/renderer/src/api/client.ts'),
  'utf8',
)
const lifecyclePath = path.resolve(
  here,
  '../src/main/backendLifecycle.ts',
)

test('preload global API type is derived from the runtime implementation', () => {
  assert.match(preloadSource, /export type BackendAPI\s*=\s*typeof api/)
  assert.match(preloadTypesSource, /import type \{ BackendAPI \} from '\.\/index'/)
  assert.doesNotMatch(preloadTypesSource, /interface BackendAPI/)
  assert.doesNotMatch(preloadTypesSource, /__BACKEND_URL__/)
})

test('backend connection IPC is asynchronous and initialized before mount', () => {
  assert.doesNotMatch(preloadSource, /sendSync/)
  assert.match(
    preloadSource,
    /getBackendConnection:\s*async[\s\S]*ipcRenderer\.invoke\('get-backend-connection'\)/,
  )
  assert.match(mainSource, /ipcMain\.handle\('get-backend-connection'/)
  assert.doesNotMatch(mainSource, /ipcMain\.on\('get-backend-connection'/)
  assert.match(apiClientSource, /export async function initializeBackendConnection/)
  assert.doesNotMatch(apiClientSource, /window as any/)
  assert.match(rendererMainSource, /await initializeBackendConnection\(\)/)
  assert.ok(
    rendererMainSource.indexOf('await initializeBackendConnection()')
      < rendererMainSource.indexOf(".mount('#app')"),
  )
})

test('backend launch avoids reloaders and delegates bounded process cleanup', () => {
  assert.doesNotMatch(backendSource, /['"]--reload['"]/)
  assert.match(backendSource, /terminateChildProcess/)
  assert.ok(fs.existsSync(lifecyclePath))
})

test('backend lifecycle helper terminates a real child process', async () => {
  assert.ok(fs.existsSync(lifecyclePath))
  const lifecycleSource = fs.readFileSync(lifecyclePath, 'utf8')
  const compiled = ts.transpileModule(lifecycleSource, {
    compilerOptions: {
      module: ts.ModuleKind.ES2022,
      target: ts.ScriptTarget.ES2022,
    },
    fileName: lifecyclePath,
  }).outputText
  const lifecycle = await import(
    `data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`
  )
  const child = spawn(
    process.execPath,
    ['-e', 'setInterval(() => {}, 1000)'],
    { stdio: 'ignore', windowsHide: true },
  )

  await lifecycle.terminateChildProcess(child, 1000)

  assert.ok(child.exitCode !== null || child.signalCode !== null)
})
