import { app, BrowserWindow, shell, ipcMain, dialog, session } from 'electron'
import { join } from 'path'
import { existsSync } from 'fs'
import { electronApp, optimizer, is } from '@electron-toolkit/utils'
import { BackendProcess } from './backend'
import { registerFileHandlers } from './files'
import {
  CloseCoordinator,
  type CloseDecision,
  type CloseIntent,
} from './closeCoordinator'

// 本地后端(127.0.0.1)的请求绝不能走系统代理。
// 代理软件(Clash 等)会剥离响应里的 CORS 头, 浏览器随即以 CORS 错误拦截,
// 表现为页面图片"Failed to fetch"。用 commandLine 开关设置 bypass,
// 它在 Chromium 的任何代理模式(system/fixed/pac)下都强制生效,
// 比 session.setProxy 的 proxyBypassRules 可靠(后者在 system 模式下会被忽略)。
// 必须在 app ready 前调用。
app.commandLine.appendSwitch('proxy-bypass-list', '<local>,localhost,127.0.0.1,::1')
import {
  configureElectronStoragePaths,
  loadStoragePaths,
  saveStoragePaths,
  type StoragePathUpdate,
} from './storage'
import { checkForUpdate } from './updater'

let mainWindow: BrowserWindow | null = null
let backend: BackendProcess | null = null
let quitting = false
let quitRequested = false
let quitTask: Promise<void> | null = null
let allowWindowClose = false
let rendererCloseListenerReady = false
let rendererWasReady = false
let nextCloseIntent: CloseIntent = 'close'
const closeCoordinator = new CloseCoordinator()

configureElectronStoragePaths()

function createWindow(): void {
  allowWindowClose = false
  rendererCloseListenerReady = false
  rendererWasReady = false
  const iconPath = join(__dirname, '../../build/icon.ico')
  const iconPng = join(__dirname, '../../build/icon.png')
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    frame: false,
    autoHideMenuBar: true,
    show: false,
    ...(existsSync(iconPath) ? { icon: iconPath } : existsSync(iconPng) ? { icon: iconPng } : {}),
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      nodeIntegration: false,
      contextIsolation: true,
    },
  })

  mainWindow.on('ready-to-show', () => {
    mainWindow?.show()
  })

  mainWindow.removeMenu()

  mainWindow.webContents.setWindowOpenHandler((details) => {
    if (isAllowedExternalURL(details.url)) {
      void shell.openExternal(details.url)
    } else {
      console.warn(`[main] Blocked external URL: ${details.url}`)
    }
    return { action: 'deny' }
  })

  if (is.dev && process.env['ELECTRON_RENDERER_URL']) {
    mainWindow.loadURL(process.env['ELECTRON_RENDERER_URL'])
  } else {
    mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
  }

  const emitWindowMaximizedState = (): void => {
    const value = mainWindow?.isMaximized() ?? false
    mainWindow?.webContents.send('window:maximized-changed', value)
  }

  mainWindow.on('maximize', emitWindowMaximizedState)
  mainWindow.on('unmaximize', emitWindowMaximizedState)

  mainWindow.webContents.on('did-start-loading', () => {
    rendererCloseListenerReady = false
  })
  mainWindow.webContents.on('render-process-gone', () => {
    rendererCloseListenerReady = false
  })

  mainWindow.on('close', (event) => {
    if (allowWindowClose) return
    event.preventDefault()
    const intent = nextCloseIntent
    nextCloseIntent = 'close'
    if (!rendererCloseListenerReady || mainWindow?.webContents.isDestroyed()) {
      if (!rendererWasReady || confirmCloseWithoutRenderer()) {
        approveWindowClose(intent)
      } else {
        quitRequested = false
      }
      return
    }
    const pending = closeCoordinator.request(intent)
    if (pending.isNew) {
      mainWindow?.webContents.send('app:close-requested', pending.request)
    }
  })

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

async function cleanupBackend(): Promise<void> {
  if (!backend) return
  const ref = backend
  backend = null
  try {
    await ref.stop()
    console.log('[main] Backend stopped')
  } catch (err) {
    console.error('[main] Error stopping backend:', err)
  }
}

app.whenReady().then(async () => {
  electronApp.setAppUserModelId('com.scoretrans.app')

  app.on('browser-window-created', (_, window) => {
    optimizer.watchWindowShortcuts(window)
  })

  // Start FastAPI backend
  backend = new BackendProcess()
  try {
    await backend.start()
  } catch (err) {
    console.error('[main] Failed to start backend:', err)
    dialog.showErrorBox(
      '后端启动失败',
      `Score Trans 后端无法启动，应用即将退出。\n\n${errorMessage(err)}`,
    )
    await cleanupBackend()
    app.quit()
    return
  }

  const backendURL = backend.getBaseURL()
  const backendToken = backend.getApiToken()

  // Expose this process-local backend connection atomically. The token is held only
  // in memory and is never placed in URLs, logs, settings, or renderer storage.
  ipcMain.handle('get-backend-connection', () => {
    return { baseURL: backendURL, token: backendToken }
  })

  ipcMain.handle('window:minimize', () => {
    mainWindow?.minimize()
  })

  ipcMain.handle('window:toggle-maximize', () => {
    if (!mainWindow) {
      return false
    }
    if (mainWindow.isMaximized()) {
      mainWindow.unmaximize()
      return false
    }
    mainWindow.maximize()
    return true
  })

  ipcMain.handle('window:is-maximized', () => {
    return mainWindow?.isMaximized() ?? false
  })

  ipcMain.handle('app:request-close', (_event, intent: CloseIntent = 'close') => {
    nextCloseIntent = intent === 'relaunch' ? 'relaunch' : 'close'
    mainWindow?.close()
  })

  ipcMain.handle('app:close-listener-ready', () => {
    rendererCloseListenerReady = true
    rendererWasReady = true
    const pending = closeCoordinator.pendingRequest
    if (pending) mainWindow?.webContents.send('app:close-requested', pending)
  })

  ipcMain.on(
    'app:resolve-close',
    (_event, requestId: number, decision: CloseDecision) => {
      const resolution = closeCoordinator.resolve(
        requestId,
        decision === 'proceed' ? 'proceed' : 'cancel',
      )
      if (resolution.kind === 'cancel') quitRequested = false
      if (resolution.kind === 'proceed') approveWindowClose(resolution.intent)
    },
  )

  ipcMain.handle('dialog:select-directory', async () => {
    if (!mainWindow) return null
    const result = await dialog.showOpenDialog(mainWindow, {
      properties: ['openDirectory'],
    })
    if (result.canceled || result.filePaths.length === 0) return null
    return result.filePaths[0]
  })

  ipcMain.handle('storage:get', () => {
    return loadStoragePaths()
  })

  ipcMain.handle('storage:set', (_event, paths: StoragePathUpdate) => {
    return saveStoragePaths(paths ?? {})
  })

  ipcMain.handle('cache:clear-electron', async () => {
    await session.defaultSession.clearCache()
    return { ok: true }
  })

  ipcMain.handle('app:check-update', () => checkForUpdate())

  ipcMain.handle('app:get-version', () => app.getVersion())

  ipcMain.handle('app:open-external', (_event, url: string) => {
    if (typeof url !== 'string' || !isAllowedExternalURL(url)) return
    void shell.openExternal(url)
  })

  registerFileHandlers(() => mainWindow)

  // Create the main window
  createWindow()

  app.on('activate', () => {
    if (!quitRequested && BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

app.on('before-quit', (e) => {
  if (quitting) return
  e.preventDefault()
  quitRequested = true
  if (mainWindow && !allowWindowClose) {
    mainWindow.close()
    return
  }
  // Repeated quit requests must wait even after cleanupBackend clears backend.
  if (quitTask) return
  quitTask = cleanupBackend().then(() => {
    quitting = true
    app.quit()
  })
})

app.on('will-quit', () => {
  ipcMain.removeHandler('get-backend-connection')
  ipcMain.removeHandler('window:minimize')
  ipcMain.removeHandler('window:toggle-maximize')
  ipcMain.removeHandler('window:is-maximized')
  ipcMain.removeHandler('app:request-close')
  ipcMain.removeHandler('app:close-listener-ready')
  ipcMain.removeAllListeners('app:resolve-close')
  ipcMain.removeHandler('dialog:select-directory')
  ipcMain.removeHandler('storage:get')
  ipcMain.removeHandler('storage:set')
  ipcMain.removeHandler('cache:clear-electron')
  ipcMain.removeHandler('app:check-update')
  ipcMain.removeHandler('app:open-external')
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

function isAllowedExternalURL(value: string): boolean {
  try {
    const protocol = new URL(value).protocol
    return protocol === 'http:' || protocol === 'https:'
  } catch {
    return false
  }
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

function confirmCloseWithoutRenderer(): boolean {
  if (!mainWindow) return true
  const choice = dialog.showMessageBoxSync(mainWindow, {
    type: 'warning',
    title: '无法检查未保存的更改',
    message: '界面进程当前不可用，未保存的更改可能丢失。',
    detail: '是否仍要直接退出？',
    buttons: ['取消', '直接退出'],
    defaultId: 0,
    cancelId: 0,
    noLink: true,
  })
  return choice === 1
}

function approveWindowClose(intent: CloseIntent): void {
  allowWindowClose = true
  if (intent === 'relaunch') {
    app.relaunch()
    quitRequested = true
  }
  // macOS stays resident after its last window closes; resume an explicit quit.
  if (quitRequested) app.quit()
  else mainWindow?.close()
}
