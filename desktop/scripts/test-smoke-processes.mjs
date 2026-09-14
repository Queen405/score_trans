import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { once } from 'node:events'
import { copyFile, mkdtemp, readFile, realpath, rm, writeFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { tmpdir } from 'node:os'
import { fileURLToPath } from 'node:url'
import test from 'node:test'
import { createRequire } from 'node:module'
import { _electron as electron } from 'playwright-core'
import { inspectBackendProcess, runProcessQuery, selectBackendPid } from './smoke-processes.mjs'

async function temporary(t) {
  const root = await realpath(tmpdir())
  const directory = await mkdtemp(join(root, 'score-trans-process-query-'))
  t.after(async () => {
    assert.equal(dirname(directory), root)
    await rm(directory, { recursive: true, force: true })
  })
  return directory
}

test('Windows selects exactly one direct backend and excludes grandchildren', () => {
  const rows = [
    { pid: 10, parent_pid: 1, name: 'Score Trans.exe' },
    { pid: 20, parent_pid: 10, name: 'backend.exe' },
    { pid: 21, parent_pid: 20, name: 'backend.exe' },
    { pid: 30, parent_pid: 99, name: 'backend.exe' },
  ]
  assert.equal(selectBackendPid(JSON.stringify({ processes: rows }), 10, 'win32'), 20)
  assert.throws(() => selectBackendPid('{bad', 10, 'win32'), /Invalid process/)
  assert.throws(() => selectBackendPid('{"processes":null}', 10, 'win32'), /Invalid process/)
  assert.throws(() => selectBackendPid(JSON.stringify({ processes: [{ pid: '20', parent_pid: 10, name: 'backend.exe' }] }), 10, 'win32'), /Invalid process/)
  assert.throws(() => selectBackendPid('{"processes":[]}', 10, 'win32'), /Expected one.*got 0/)
  rows.push({ pid: 22, parent_pid: 10, name: 'backend.exe' })
  assert.throws(() => selectBackendPid(JSON.stringify({ processes: rows }), 10, 'win32'), /Expected one.*got 2/)
})

test('macOS supports application paths with spaces and filters by parent PID', () => {
  const output = '  20 10 /Installed App/Score Trans.app/Contents/Resources/backend/backend\n21 20 /other/backend\n22 99 /other/backend\n'
  assert.equal(selectBackendPid(output, 10, 'darwin'), 20)
  assert.throws(() => selectBackendPid('unexpected text', 10, 'darwin'), /Invalid process/)
})

test('query failure records exit code and stderr instead of discarding the cause', async (t) => {
  const reports = await temporary(t)
  await assert.rejects(
    runProcessQuery(process.execPath, ['-e', 'console.error("native snapshot denied"); process.exit(7)'], reports),
    /code=7.*native snapshot denied/s,
  )
  assert.match(await readFile(join(reports, 'process-query.stderr.log'), 'utf8'), /native snapshot denied/)
  const record = JSON.parse(await readFile(join(reports, 'process-query.json'), 'utf8'))
  assert.equal(record.code, 7)
})

test('missing query executable reports ENOENT', async (t) => {
  const reports = await temporary(t)
  await assert.rejects(runProcessQuery(join(reports, 'missing.exe'), [], reports), /ENOENT/)
})

test('query timeout remains bounded and preserves partial output', async (t) => {
  const reports = await temporary(t)
  await assert.rejects(
    runProcessQuery(process.execPath, ['-e', 'console.log("partial snapshot"); setInterval(() => {}, 1000)'], reports, 1000),
    /ETIMEDOUT/,
  )
  assert.match(await readFile(join(reports, 'process-query.stdout.log'), 'utf8'), /partial snapshot/)
  const record = JSON.parse(await readFile(join(reports, 'process-query.json'), 'utf8'))
  assert.throws(() => process.kill(record.pid, 0), { code: 'ESRCH' })
})

test('Windows native query finds a real backend.exe child using the project venv', { skip: process.platform !== 'win32' }, async (t) => {
  const reports = await temporary(t)
  const executable = join(reports, 'backend.exe')
  await copyFile(process.execPath, executable)
  const child = spawn(executable, ['-e', 'setInterval(() => {}, 1000)'], { stdio: 'ignore', windowsHide: true })
  await once(child, 'spawn')
  try {
    const python = fileURLToPath(new URL('../../.venv/Scripts/python.exe', import.meta.url))
    const application = { evaluate: async (callback) => callback(), process: () => process }
    const identity = await inspectBackendProcess(application, { reports, python })
    assert.equal(identity.backendPid, child.pid)
  } finally {
    const exited = once(child, 'exit')
    child.kill()
    await exited
  }
})

test('Playwright Windows launch locates the backend owned by Electron, including its shell wrapper', { skip: process.platform !== 'win32' }, async (t) => {
  const reports = await temporary(t)
  const executable = join(reports, 'backend.exe')
  await copyFile(process.execPath, executable)
  const entrypoint = join(reports, 'app.cjs')
  await writeFile(entrypoint, `
    const { app, BrowserWindow } = require('electron')
    const { spawn } = require('node:child_process')
    const { join } = require('node:path')
    app.setPath('userData', join(__dirname, 'electron-data'))
    app.disableHardwareAcceleration()
    let backend, quitting = false
    app.whenReady().then(async () => {
      backend = spawn(${JSON.stringify(executable)}, ['-e', 'setInterval(() => {}, 1000)'], {
        stdio: 'ignore', windowsHide: true,
      })
      globalThis.backendProbePid = backend.pid
      const window = new BrowserWindow({ show: false })
      await window.loadURL('data:text/html,<title>process ownership probe</title>')
    })
    app.on('before-quit', (event) => {
      if (quitting || !backend) return
      event.preventDefault()
      backend.once('exit', () => { quitting = true; app.quit() })
      backend.kill()
    })
  `)
  const env = { ...process.env }
  delete env.ELECTRON_RUN_AS_NODE
  const application = await electron.launch({
    executablePath: createRequire(import.meta.url)('electron'),
    args: [entrypoint], env, timeout: 15000,
  })
  let identity
  try {
    await application.firstWindow({ timeout: 5000 })
    const expected = await application.evaluate(() => ({ electronPid: process.pid, backendPid: globalThis.backendProbePid }))
    const python = fileURLToPath(new URL('../../.venv/Scripts/python.exe', import.meta.url))
    identity = await inspectBackendProcess(application, { reports, python })
    assert.equal(identity.launcherPid, application.process().pid)
    assert.equal(identity.electronPid, expected.electronPid)
    assert.equal(identity.backendPid, expected.backendPid)
    assert.notEqual(identity.launcherPid, identity.electronPid)
    assert.deepEqual(JSON.parse(await readFile(join(reports, 'application-processes.json'), 'utf8')), identity)
  } finally {
    await application.close()
  }
  for (const pid of [identity.launcherPid, identity.electronPid, identity.backendPid]) {
    assert.throws(() => process.kill(pid, 0), { code: 'ESRCH' })
  }
})
