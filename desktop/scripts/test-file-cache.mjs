import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import fs from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import electron from 'electron'

test('file downloads recover from a cached response without CORS headers', { timeout: 30000 }, async () => {
  const userData = await fs.mkdtemp(path.join(os.tmpdir(), 'score-trans-cache-test-'))
  const fixture = fileURLToPath(new URL('./fixtures/file-cache-electron.cjs', import.meta.url))
  try {
    const env = { ...process.env, SCORE_TRANS_TEST_USER_DATA: userData }
    delete env.ELECTRON_RUN_AS_NODE
    const child = spawn(electron, [fixture], { env, windowsHide: true, stdio: 'pipe' })
    let output = ''
    child.stdout.on('data', (chunk) => { output += chunk })
    child.stderr.on('data', (chunk) => { output += chunk })
    const timer = setTimeout(() => child.kill(), 25000)
    try {
      const code = await new Promise((resolve, reject) => {
        child.once('error', reject)
        child.once('exit', resolve)
      })
      assert.equal(code, 0, output)
    } finally {
      clearTimeout(timer)
    }
  } finally {
    await fs.rm(userData, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 })
  }
})
