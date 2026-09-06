import { spawn, type ChildProcess } from 'node:child_process'
import { app } from 'electron'
import path from 'path'
import http from 'http'
import net from 'net'
import { existsSync } from 'fs'
import { randomBytes } from 'crypto'
import { loadStoragePaths } from './storage'
import { terminateChildProcess } from './backendLifecycle'

const DEFAULT_PORT = 19200
const HEALTH_CHECK_INTERVAL = 1000
const HEALTH_CHECK_TIMEOUT = 15000
const SHUTDOWN_TIMEOUT = 5000

export class BackendProcess {
  private process: ChildProcess | null = null
  private port: number
  private baseURL: string
  private readonly apiToken: string

  constructor(port: number = DEFAULT_PORT) {
    this.port = port
    this.baseURL = `http://127.0.0.1:${port}`
    this.apiToken = randomBytes(32).toString('base64url')
  }

  async start(): Promise<void> {
    if (this.process) await this.stop()
    const isDev = !app.isPackaged
    this.port = await findAvailablePort(this.port)
    this.baseURL = `http://127.0.0.1:${this.port}`
    const storagePaths = loadStoragePaths()
    const backendEnv = {
      ...process.env,
      SCORE_TRANS_DATA_DIR: storagePaths.dataDir,
      SCORE_TRANS_CACHE_DIR: storagePaths.cacheDir,
      SCORE_TRANS_API_TOKEN: this.apiToken,
      SCORE_TRANS_API_AUTH_DISABLED: '0',
      // 显式注入 CORS 允许源, 防止用户 shell 里残留的脏 SCORE_TRANS_CORS_ORIGINS
      // (load_project_env 不会覆盖已存在的环境变量) 导致后端 CORS 配置错误,
      // 进而让渲染进程的文件请求全部被浏览器以 CORS 错误拦截。
      SCORE_TRANS_CORS_ORIGINS:
        'http://localhost:5173,http://127.0.0.1:5173,null',
    }

    let child: ChildProcess
    if (isDev) {
      const projectRoot = resolveProjectRoot()
      const localPython = path.join(projectRoot, '.venv', 'Scripts', 'python.exe')
      const pythonExe = existsSync(localPython) ? localPython : 'python'
      const backendPath = path.join(projectRoot, 'backend')
      const pythonPath = [backendPath, process.env.PYTHONPATH].filter(Boolean).join(path.delimiter)

      child = spawn(pythonExe, [
        '-m', 'uvicorn',
        'score_trans.api.app:create_app',
        '--factory',
        '--host', '127.0.0.1',
        '--port', String(this.port),
      ], {
        stdio: 'pipe',
        cwd: projectRoot,
        env: { ...backendEnv, PYTHONPATH: pythonPath },
        windowsHide: true,
      })
    } else {
      const resourcesPath = process.resourcesPath
      const exePath = path.join(resourcesPath, 'backend', 'backend.exe')
      const backendCwd = path.join(resourcesPath, 'backend')
      child = spawn(exePath, [
        '--host', '127.0.0.1',
        '--port', String(this.port),
      ], { stdio: 'pipe', windowsHide: true, cwd: backendCwd, env: backendEnv })
    }
    this.process = child

    child.stdout?.on('data', (data: Buffer) => {
      console.log(`[backend] ${data.toString().trim()}`)
    })

    child.stderr?.on('data', (data: Buffer) => {
      console.error(`[backend] ${data.toString().trim()}`)
    })

    child.on('exit', (code) => {
      console.log(`[backend] Process exited with code=${code}`)
      if (this.process === child) this.process = null
    })

    child.on('error', (err) => {
      console.error(`[backend] Process error: ${err.message}`)
    })

    try {
      await this.waitForHealthy()
    } catch (error) {
      if (this.process === child) this.process = null
      await terminateChildProcess(child, SHUTDOWN_TIMEOUT)
      throw error
    }
  }

  async waitForHealthy(maxWait: number = HEALTH_CHECK_TIMEOUT): Promise<void> {
    const start = Date.now()
    while (Date.now() - start < maxWait) {
      try {
        await this.healthCheck()
        console.log(`[backend] Health check passed on port ${this.port}`)
        return
      } catch {
        if (!this.process) {
          throw new Error('Backend process exited before becoming healthy')
        }
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
    const child = this.process
    if (!child) return
    this.process = null
    await terminateChildProcess(child, SHUTDOWN_TIMEOUT)
  }

  getBaseURL(): string {
    return this.baseURL
  }

  getApiToken(): string {
    return this.apiToken
  }
}

function resolveProjectRoot(): string {
  const candidates = [
    path.resolve(__dirname, '..', '..', '..'),
    path.resolve(__dirname, '..', '..'),
    process.cwd(),
    path.resolve(process.cwd(), '..'),
  ]
  const found = candidates.find((candidate) => existsSync(path.join(candidate, 'backend', 'score_trans')))
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
