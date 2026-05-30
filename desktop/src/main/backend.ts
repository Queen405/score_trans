import { spawn, ChildProcess } from 'child_process'
import { app } from 'electron'
import path from 'path'
import http from 'http'

const DEFAULT_PORT = 18513
const HEALTH_CHECK_INTERVAL = 1000
const HEALTH_CHECK_TIMEOUT = 15000
const SHUTDOWN_TIMEOUT = 5000

export class BackendProcess {
  private process: ChildProcess | null = null
  private port: number
  private baseURL: string

  constructor(port: number = DEFAULT_PORT) {
    this.port = port
    this.baseURL = `http://127.0.0.1:${port}`
  }

  async start(): Promise<void> {
    const isDev = !app.isPackaged

    if (isDev) {
      this.process = spawn('python', [
        '-m', 'uvicorn',
        'score_trans.api.app:create_app',
        '--factory',
        '--host', '127.0.0.1',
        '--port', String(this.port),
        '--reload',
      ], { stdio: 'pipe' })
    } else {
      const exePath = path.join(process.resourcesPath, 'backend', 'backend.exe')
      this.process = spawn(exePath, [
        '--host', '127.0.0.1',
        '--port', String(this.port),
      ], { stdio: 'pipe' })
    }

    this.process.stdout?.on('data', (data: Buffer) => {
      console.log(`[backend] ${data.toString().trim()}`)
    })

    this.process.stderr?.on('data', (data: Buffer) => {
      console.error(`[backend] ${data.toString().trim()}`)
    })

    this.process.on('exit', (code) => {
      console.log(`[backend] Process exited with code=${code}`)
      this.process = null
    })

    this.process.on('error', (err) => {
      console.error(`[backend] Process error: ${err.message}`)
    })

    await this.waitForHealthy()
  }

  async waitForHealthy(maxWait: number = HEALTH_CHECK_TIMEOUT): Promise<void> {
    const start = Date.now()
    while (Date.now() - start < maxWait) {
      try {
        await this.healthCheck()
        console.log(`[backend] Health check passed on port ${this.port}`)
        return
      } catch {
        await new Promise(r => setTimeout(r, HEALTH_CHECK_INTERVAL))
      }
    }
    throw new Error(`Backend startup timed out after ${maxWait}ms`)
  }

  healthCheck(): Promise<void> {
    return new Promise((resolve, reject) => {
      const req = http.get(`${this.baseURL}/health`, (res) => {
        res.resume()
        if (res.statusCode === 200) {
          resolve()
        } else {
          reject(new Error(`Health check returned ${res.statusCode}`))
        }
      })
      req.on('error', reject)
      req.setTimeout(2000, () => {
        req.destroy()
        reject(new Error('Health check timeout'))
      })
    })
  }

  async stop(): Promise<void> {
    if (!this.process) return

    this.process.kill('SIGTERM')

    await new Promise<void>((resolve) => {
      const timeout = setTimeout(() => {
        console.log('[backend] Force killing backend process')
        this.process?.kill('SIGKILL')
        resolve()
      }, SHUTDOWN_TIMEOUT)

      this.process?.on('exit', () => {
        clearTimeout(timeout)
        resolve()
      })
    })

    this.process = null
  }

  getBaseURL(): string {
    return this.baseURL
  }
}
