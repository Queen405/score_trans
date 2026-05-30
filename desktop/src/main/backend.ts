import { spawn, execSync, ChildProcess } from 'child_process'
import { app } from 'electron'
import path from 'path'
import http from 'http'
import net from 'net'
import { existsSync } from 'fs'

const DEFAULT_PORT = 19200
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
    this.port = await findAvailablePort(this.port)
    this.baseURL = `http://127.0.0.1:${this.port}`

    if (isDev) {
      const projectRoot = resolveProjectRoot()
      const localPython = path.join(projectRoot, '.venv', 'Scripts', 'python.exe')
      const pythonExe = existsSync(localPython) ? localPython : 'python'
      const srcPath = path.join(projectRoot, 'src')
      const pythonPath = [srcPath, process.env.PYTHONPATH].filter(Boolean).join(path.delimiter)

      this.process = spawn(pythonExe, [
        '-m', 'uvicorn',
        'score_trans.api.app:create_app',
        '--factory',
        '--host', '127.0.0.1',
        '--port', String(this.port),
        '--reload',
      ], {
        stdio: 'pipe',
        cwd: projectRoot,
        env: { ...process.env, PYTHONPATH: pythonPath },
        windowsHide: true,
      })
    } else {
      const exePath = path.join(process.resourcesPath, 'backend', 'backend.exe')
      this.process = spawn(exePath, [
        '--host', '127.0.0.1',
        '--port', String(this.port),
      ], { stdio: 'pipe', windowsHide: true })
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

    const pid = this.process.pid
    if (!pid) { this.process = null; return }

    if (process.platform === 'win32') {
      this.killTree(pid)
    } else {
      this.process.kill('SIGTERM')
      await new Promise<void>((resolve) => {
        const timeout = setTimeout(() => {
          try { this.process?.kill('SIGKILL') } catch {}
          resolve()
        }, SHUTDOWN_TIMEOUT)
        this.process?.on('exit', () => { clearTimeout(timeout); resolve() })
      })
    }

    this.process = null
  }

  private killTree(pid: number): void {
    try {
      execSync(`taskkill /T /F /PID ${pid}`, { stdio: 'ignore' })
    } catch {
      // process may already be dead
    }
  }

  getBaseURL(): string {
    return this.baseURL
  }
}

function resolveProjectRoot(): string {
  const candidates = [
    path.resolve(__dirname, '..', '..', '..'),
    path.resolve(__dirname, '..', '..'),
    process.cwd(),
    path.resolve(process.cwd(), '..'),
  ]
  const found = candidates.find((candidate) => existsSync(path.join(candidate, 'src', 'score_trans')))
  return found ?? process.cwd()
}

async function findAvailablePort(startPort: number): Promise<number> {
  for (let port = startPort; port < startPort + 20; port += 1) {
    if (await isPortAvailable(port)) {
      return port
    }
  }
  throw new Error(`No available backend port found from ${startPort}`)
}

function isPortAvailable(port: number): Promise<boolean> {
  return new Promise((resolve) => {
    const server = net.createServer()
    server.once('error', () => resolve(false))
    server.once('listening', () => {
      server.close(() => resolve(true))
    })
    server.listen(port, '127.0.0.1')
  })
}
