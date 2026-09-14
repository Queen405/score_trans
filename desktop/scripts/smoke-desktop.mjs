/** Exercise the installed Electron application, including its own backend child. */
import assert from 'node:assert/strict'
import { mkdir, mkdtemp, readFile, writeFile } from 'node:fs/promises'
import { join, resolve } from 'node:path'
import { tmpdir } from 'node:os'
import { createConnection } from 'node:net'
import { writeFileSync } from 'node:fs'
import { spawnSync } from 'node:child_process'
import { setTimeout as delay } from 'node:timers/promises'
import { _electron as electron } from 'playwright-core'

const ENV = { ...process.env }
const argv = process.argv.slice(2)
const arg = (name) => argv[argv.indexOf('--' + name) + 1]
if (ENV.GITHUB_ACTIONS !== 'true' || ENV.RUNNER_ENVIRONMENT !== 'github-hosted') {
  throw new Error('Desktop smoke requires a disposable GitHub-hosted runner')
}
if (!argv.includes('--executable')) throw new Error('--executable is required')
const executable = resolve(arg('executable'))
const phase = argv.includes('--phase') ? arg('phase') : 'installed'
if (!/^[a-z-]+$/.test(phase)) throw new Error('Invalid phase')
const reports = resolve('smoke-reports', phase)
await mkdir(reports, { recursive: true })
const work = await mkdtemp(join(tmpdir(), 'score-trans-desktop-'))
const userData = join(work, 'electron')
await mkdir(userData)
await writeFile(join(userData, 'storage-paths.json'), JSON.stringify({
  dataDir: join(work, 'data'), cacheDir: join(work, 'cache'),
}))
const expectedVersion = JSON.parse(await readFile(new URL('../package.json', import.meta.url), 'utf8')).version
const errors = []
const logs = []
let application, page, child, backendPid, baseURL
let success = false
const env = Object.fromEntries(Object.entries(ENV).filter(([key]) => !key.startsWith('SCORE_TRANS_')))
env.SCORE_TRANS_ELECTRON_USER_DATA_DIR = userData
env.SCORE_TRANS_UPDATE_MANIFEST_URL = 'http://127.0.0.1:9/latest.json'
// No network trace: authentication tokens must never enter artifacts.
const redact = (text) => String(text)
  .replace(/Bearer\s+\S+/gi, 'Bearer [redacted]')
  .replace(/("?token"?\s*[:=]\s*"?)[^"\s,}]+/gi, '$1[redacted]')
const alive = (pid) => {
  if (!pid) return false
  try { process.kill(pid, 0); return true } catch (error) {
    if (error.code === 'ESRCH') return false
    throw error
  }
}
const portOpen = () => new Promise((resolvePort) => {
  if (!baseURL) return resolvePort(false)
  const socket = createConnection({ host: '127.0.0.1', port: Number(new URL(baseURL).port) })
  const done = (value) => { socket.destroy(); resolvePort(value) }
  socket.once('connect', () => done(true))
  socket.once('error', () => done(false))
  socket.setTimeout(500, () => done(false))
})
function killOwnedProcesses() {
  const killMacTree = (pid) => {
    if (!alive(pid)) return
    const children = spawnSync('pgrep', ['-P', String(pid)], { encoding: 'utf8', timeout: 3000 })
    for (const value of (children.stdout || '').trim().split(/\s+/)) {
      if (/^\d+$/.test(value)) killMacTree(Number(value))
    }
    try { process.kill(pid, 'SIGKILL') } catch (error) { if (error.code !== 'ESRCH') throw error }
  }
  for (const pid of [child?.pid, backendPid]) {
    if (!alive(pid)) continue
    if (process.platform === 'win32') {
      spawnSync('taskkill', ['/PID', String(pid), '/T', '/F'], { timeout: 10000, windowsHide: true })
    } else {
      killMacTree(pid)
    }
  }
}
// This watchdog also bounds debugger attach and shutdown when the app is broken.
const watchdog = setTimeout(() => {
  writeFileSync(join(reports, 'desktop.log'), logs.join('\n'))
  writeFileSync(join(reports, 'result.json'), JSON.stringify({ phase, success: false, errors: [...errors, 'Overall timeout'] }))
  killOwnedProcesses()
  console.error('Desktop smoke exceeded 120 seconds')
  process.exit(1)
}, 120000)
const startupWatchdog = setTimeout(() => {
  errors.push('Startup and core checks exceeded 90 seconds')
  killOwnedProcesses()
}, 90000)

try {
  const deadline = Date.now() + 90000
  application = await electron.launch({ executablePath: executable, env, timeout: 60000 })
  child = application.process()
  for (const stream of [child.stdout, child.stderr]) stream?.on('data', (data) => logs.push(redact(data)))
  application.on('window', (window) => {
    window.on('pageerror', (error) => errors.push(redact(error.message)))
    window.on('crash', () => errors.push('Renderer process crashed'))
  })
  page = await application.firstWindow({ timeout: Math.max(1, deadline - Date.now()) })
  page.setDefaultTimeout(Math.max(1, deadline - Date.now()))
  const state = await application.evaluate(({ app }) => ({ packaged: app.isPackaged, version: app.getVersion() }))
  assert.equal(state.packaged, true)
  assert.equal(state.version, expectedVersion)
  await page.locator('.app-shell').waitFor({ state: 'visible' })
  await page.getByRole('button', { name: '最小化', exact: true }).waitFor({ state: 'visible' })
  assert.equal(await page.evaluate(() => window.api.getVersion()), expectedVersion)
  const listing = process.platform === 'win32'
    ? spawnSync('powershell.exe', ['-NoProfile', '-NonInteractive', '-Command',
      `Get-CimInstance Win32_Process -Filter 'ParentProcessId = ${child.pid}' | Select-Object ProcessId,Name | ConvertTo-Json -Compress`],
    { encoding: 'utf8', timeout: 10000, windowsHide: true })
    : spawnSync('ps', ['-axo', 'pid=,ppid=,comm='], { encoding: 'utf8', timeout: 10000 })
  if (listing.error || listing.status !== 0) throw new Error('Cannot inspect application child processes')
  const candidates = process.platform === 'win32'
    ? [JSON.parse(listing.stdout)].flat().filter((p) => p.Name === 'backend.exe').map((p) => p.ProcessId)
    : listing.stdout.split('\n').map((line) => line.trim().match(/^(\d+)\s+(\d+)\s+(.+)$/))
      .filter((match) => match && Number(match[2]) === child.pid && match[3].endsWith('/backend'))
      .map((match) => Number(match[1]))
  assert.equal(candidates.length, 1, 'Expected one packaged backend child')
  backendPid = candidates[0]
  baseURL = await page.evaluate(async () => {
    const { baseURL: url, token } = await window.api.getBackendConnection()
    if (!url || !token) throw new Error('Backend IPC did not supply a connection')
    const response = await fetch(url + '/render/jianpu-text-svg', {
      method: 'POST', headers: { Authorization: 'Bearer ' + token, 'Content-Type': 'application/json' },
      body: JSON.stringify({ jianpu_text: '1=C\n4/4\n1 2 3 4 |' }),
    })
    if (!response.ok || !(await response.json()).svg_file_id) throw new Error('Renderer/backend round trip failed')
    return url
  })
  assert.equal(errors.length, 0, errors.join('\n'))
  await page.screenshot({ path: join(reports, 'window.png') })
  clearTimeout(startupWatchdog)
  // Normal app quit exercises before-quit, renderer close coordination and backend cleanup.
  await Promise.race([
    application.close(),
    delay(15000).then(() => { throw new Error('Application did not quit normally') }),
  ])
  assert.equal(alive(child.pid), false, 'Electron is still alive')
  assert.equal(alive(backendPid), false, 'Backend process is still alive')
  assert.equal(await portOpen(), false, 'Backend port is still listening after app exit')
  assert.equal(errors.length, 0, errors.join('\n'))
  success = true
} catch (error) {
  logs.push(redact(error.stack || error))
  if (page && !page.isClosed()) await page.screenshot({ path: join(reports, 'failure.png'), timeout: 3000 }).catch(() => {})
  throw error
} finally {
  clearTimeout(watchdog)
  clearTimeout(startupWatchdog)
  if (!success) killOwnedProcesses()
  await writeFile(join(reports, 'desktop.log'), logs.join('\n'))
  await writeFile(join(reports, 'result.json'), JSON.stringify({ phase, success, errors }, null, 2))
}
