import assert from 'node:assert/strict'
import { EventEmitter } from 'node:events'
import fs from 'node:fs'
import path from 'node:path'
import vm from 'node:vm'
import test from 'node:test'
import { setImmediate as nextTurn } from 'node:timers/promises'
import ts from 'typescript'

function compile(name) {
  return ts.transpileModule(fs.readFileSync(new URL(`../src/main/${name}.ts`, import.meta.url), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText
}
const mainSource = compile('index')
const coordinatorSource = compile('closeCoordinator')

// Execute the real entrypoint and IPC handlers; only Electron and the backend are substitutes.
async function launch(platform = 'darwin', { deferStop = false } = {}) {
  const handlers = new Map()
  const requests = []
  const windows = []
  let stops = 0
  let relaunches = 0
  let exited = false
  let closingForQuit = false
  let nativeDecision = 0
  let finishStop
  const stopping = deferStop ? new Promise((resolve) => { finishStop = resolve }) : Promise.resolve()
  const app = new EventEmitter()
  app.commandLine = { appendSwitch() {} }
  app.whenReady = () => Promise.resolve()
  app.relaunch = () => { relaunches++ }
  app.quit = () => {
    const event = closeEvent()
    app.emit('before-quit', event)
    if (event.prevented) return
    closingForQuit = true
    for (const window of [...windows]) window.close()
    closingForQuit = false
    if (windows.length) return
    app.emit('will-quit')
    exited = true
  }
  const ipcMain = new EventEmitter()
  ipcMain.handle = (name, callback) => handlers.set(name, callback)
  ipcMain.removeHandler = (name) => handlers.delete(name)
  function closeEvent() {
    return { prevented: false, preventDefault() { this.prevented = true } }
  }
  class Window extends EventEmitter {
    static getAllWindows() { return windows }
    constructor() {
      super()
      windows.push(this)
      this.webContents = new EventEmitter()
      Object.assign(this.webContents, {
        setWindowOpenHandler() {},
        isDestroyed: () => false,
        send(name, request) { if (name === 'app:close-requested') requests.push(request) },
      })
    }
    removeMenu() {}
    loadFile() {}
    close() {
      const event = closeEvent()
      this.emit('close', event)
      if (event.prevented) return
      const index = windows.indexOf(this)
      if (index < 0) return
      windows.splice(index, 1)
      this.emit('closed')
      if (!windows.length && !closingForQuit) app.emit('window-all-closed')
    }
  }
  class Backend {
    async start() {}
    async stop() { stops++; await stopping }
    getBaseURL() { return 'http://127.0.0.1:19200' }
    getApiToken() { return 'test-token' }
  }
  const coordinator = { exports: {} }
  vm.runInNewContext(coordinatorSource, coordinator)
  const imports = {
    electron: {
      app, BrowserWindow: Window, ipcMain, session: {},
      dialog: { showMessageBoxSync: () => nativeDecision },
    },
    path,
    fs: { existsSync: () => false },
    '@electron-toolkit/utils': {
      electronApp: { setAppUserModelId() {} }, optimizer: { watchWindowShortcuts() {} }, is: { dev: false },
    },
    './backend': { BackendProcess: Backend },
    './files': { registerFileHandlers() {} },
    './closeCoordinator': coordinator.exports,
    './storage': { configureElectronStoragePaths() {}, loadStoragePaths() {}, saveStoragePaths() {} },
    './updater': { checkForUpdate() {} },
    './locale': { t: (s) => s, registerLocaleIpc() {} },
  }
  vm.runInNewContext(mainSource, {
    exports: {}, __dirname: 'test-app', process: { platform, env: {} },
    console: { log() {}, error() {} },
    require(name) {
      assert.ok(Object.hasOwn(imports, name), `Unexpected dependency: ${name}`)
      return imports[name]
    },
  })
  await nextTurn()
  const ready = () => handlers.get('app:close-listener-ready')()
  ready()
  return {
    app, windows, requests, ready,
    get stops() { return stops },
    get exited() { return exited },
    get relaunches() { return relaunches },
    finishStop: () => finishStop?.(),
    nativeDecision: (value) => { nativeDecision = value },
    request: (intent) => handlers.get('app:request-close')({}, intent),
    resolve: (decision, id = requests.at(-1).requestId) => ipcMain.emit('app:resolve-close', {}, id, decision),
  }
}

for (const platform of ['darwin', 'win32']) {
  test(`${platform}: confirmed app quit stops the backend and exits`, async () => {
    const run = await launch(platform)
    run.app.quit()
    assert.equal(run.requests.length, 1)
    assert.equal(run.stops, 0)
    run.resolve('proceed')
    await nextTurn()
    assert.equal(run.stops, 1)
    assert.equal(run.exited, true)
    assert.equal(run.windows.length, 0)
  })
}

test('macOS: cancelling quit restores ordinary close and Dock activation', async () => {
  const run = await launch()
  run.app.quit()
  run.resolve('cancel')
  run.windows[0].close()
  run.resolve('proceed')
  await nextTurn()
  assert.equal(run.windows.length, 0)
  assert.equal(run.stops, 0)
  assert.equal(run.exited, false)
  run.app.emit('activate')
  assert.equal(run.windows.length, 1)
  run.ready()
  run.app.quit()
  run.resolve('proceed')
  await nextTurn()
  assert.equal(run.exited, true)
})

test('macOS: repeated quit waits for one backend cleanup before exiting', async () => {
  const run = await launch('darwin', { deferStop: true })
  run.app.quit()
  run.app.quit()
  assert.equal(run.requests.length, 1)
  run.resolve('proceed')
  run.app.quit()
  run.app.quit()
  assert.equal(run.stops, 1)
  assert.equal(run.exited, false)
  run.app.emit('activate')
  assert.equal(run.windows.length, 1)
  run.finishStop()
  await nextTurn()
  assert.equal(run.exited, true)
  assert.equal(run.stops, 1)
})

test('macOS: approved relaunch exits, but cancelled relaunch does not schedule a restart', async () => {
  const run = await launch()
  run.request('relaunch')
  run.resolve('cancel')
  assert.equal(run.relaunches, 0)
  run.request('relaunch')
  run.resolve('proceed')
  await nextTurn()
  assert.equal(run.relaunches, 1)
  assert.equal(run.stops, 1)
  assert.equal(run.exited, true)
})

test('macOS: stale approval after cancellation cannot approve a newer quit', async () => {
  const run = await launch()
  run.app.quit()
  const oldId = run.requests[0].requestId
  run.resolve('cancel')
  run.app.quit()
  run.resolve('proceed', oldId)
  await nextTurn()
  assert.equal(run.exited, false)
  assert.equal(run.stops, 0)
  run.resolve('proceed')
  await nextTurn()
  assert.equal(run.exited, true)
})

test('macOS: native cancellation clears quit intent when the renderer is unavailable', async () => {
  const run = await launch()
  run.windows[0].webContents.emit('render-process-gone')
  run.app.quit()
  assert.equal(run.exited, false)
  run.nativeDecision(1)
  run.windows[0].close()
  await nextTurn()
  assert.equal(run.windows.length, 0)
  assert.equal(run.stops, 0)
  assert.equal(run.exited, false)
})

test('macOS: explicit quit after ordinary window close still stops the backend', async () => {
  const run = await launch('darwin', { deferStop: true })
  run.windows[0].close()
  run.resolve('proceed')
  assert.equal(run.windows.length, 0)
  run.app.quit()
  run.app.emit('activate')
  assert.equal(run.windows.length, 0)
  assert.equal(run.exited, false)
  run.finishStop()
  await nextTurn()
  assert.equal(run.stops, 1)
  assert.equal(run.exited, true)
})
