/** Bounded OS process queries for the installed-application smoke test. */
import { spawn, spawnSync } from 'node:child_process'
import { open, readFile, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

export async function runProcessQuery(command, args, reports, timeout = 10000) {
  const stdoutPath = join(reports, 'process-query.stdout.log')
  const stderrPath = join(reports, 'process-query.stderr.log')
  const stdout = await open(stdoutPath, 'w')
  let stderr, result, child
  const started = Date.now()
  try {
    stderr = await open(stderrPath, 'w')
    // File descriptors avoid waiting on pipes inherited by a Windows venv launcher.
    child = spawn(command, args, {
      stdio: ['ignore', stdout.fd, stderr.fd], windowsHide: true,
    })
    result = await new Promise((resolve) => {
      let settled = false
      const finish = (value) => {
        if (settled) return
        settled = true
        clearTimeout(timer)
        resolve(value)
      }
      const timer = setTimeout(() => finish({ code: null, error: 'ETIMEDOUT' }), timeout)
      child.once('error', (error) => finish({ code: null, error: error.code || error.message }))
      child.once('exit', (code, signal) => finish({ code, signal }))
    })
    if (result.error === 'ETIMEDOUT' && child.pid) {
      const stopped = new Promise((resolve) => {
        const timer = setTimeout(resolve, 1000)
        child.once('exit', () => { clearTimeout(timer); resolve() })
      })
      if (process.platform === 'win32') {
        const killed = spawnSync('taskkill', ['/PID', String(child.pid), '/T', '/F'], {
          encoding: 'utf8', timeout: 5000, windowsHide: true,
        })
        if (killed.error || killed.status !== 0) {
          result.cleanupError = killed.error?.code || `taskkill exit ${killed.status}`
          child.kill()
        }
      } else {
        child.kill('SIGKILL')
      }
      await stopped
    }
  } finally {
    await stdout.close()
    await stderr?.close()
  }
  const record = { pid: child.pid, elapsedMs: Date.now() - started, ...result }
  await writeFile(join(reports, 'process-query.json'), JSON.stringify(record, null, 2))
  const [output, errorOutput] = await Promise.all([
    readFile(stdoutPath, 'utf8'), readFile(stderrPath, 'utf8'),
  ])
  if (result.error || result.code !== 0) {
    throw new Error(
      `Cannot inspect application child processes: code=${result.code}, `
      + `signal=${result.signal ?? 'none'}, error=${result.error ?? 'none'}; `
      + errorOutput.trim().slice(-4000),
    )
  }
  return output
}

export function selectBackendPid(output, parentPid, platform) {
  let rows
  if (platform === 'win32') {
    try { rows = JSON.parse(output).processes } catch {
      throw new Error('Invalid process query JSON; see process-query.stdout.log')
    }
  } else {
    rows = output.split('\n').filter((line) => line.trim()).map((line) => {
      const match = line.trim().match(/^(\d+)\s+(\d+)\s+(.+)$/)
      if (!match) throw new Error('Invalid process query ps output; see process-query.stdout.log')
      return { pid: Number(match[1]), parent_pid: Number(match[2]), name: match[3] }
    })
  }
  if (!Array.isArray(rows) || rows.some((row) => !row
    || !Number.isSafeInteger(row.pid) || row.pid <= 0
    || !Number.isSafeInteger(row.parent_pid) || row.parent_pid < 0
    || typeof row.name !== 'string')) {
    throw new Error('Invalid process query records; see process-query.stdout.log')
  }
  const candidates = rows.filter((row) => row.parent_pid === parentPid && (platform === 'win32'
    ? row.name.toLowerCase() === 'backend.exe'
    : row.name.endsWith('/backend')))
  if (candidates.length !== 1) {
    throw new Error(`Expected one packaged backend child of PID ${parentPid}, got ${candidates.length}; see process-query.stdout.log`)
  }
  return candidates[0].pid
}

export async function inspectBackendProcess(application, { python, reports }) {
  // Playwright launches through cmd.exe on Windows; process().pid is the launcher.
  const parentPid = await application.evaluate(() => process.pid)
  if (!Number.isSafeInteger(parentPid) || parentPid <= 0) throw new Error('Invalid application PID')
  const identity = { launcherPid: application.process().pid, electronPid: parentPid }
  const identityFile = join(reports, 'application-processes.json')
  await writeFile(identityFile, JSON.stringify(identity, null, 2))
  console.log(`[desktop] launcher PID=${identity.launcherPid}, Electron PID=${parentPid}`)
  const windows = process.platform === 'win32'
  if (windows && !python) throw new Error('--python is required for Windows process inspection')
  const command = windows ? python : 'ps'
  const args = windows
    ? [fileURLToPath(new URL('../../tools/installer_diagnostics.py', import.meta.url)), '--pid', String(parentPid), '--processes-only']
    : ['-axo', 'pid=,ppid=,comm=']
  const output = await runProcessQuery(command, args, reports)
  identity.backendPid = selectBackendPid(output, parentPid, process.platform)
  await writeFile(identityFile, JSON.stringify(identity, null, 2))
  return identity
}
