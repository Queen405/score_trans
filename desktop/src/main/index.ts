import { app, BrowserWindow, shell, ipcMain, dialog, session } from 'electron'
import { join } from 'path'
import { existsSync } from 'fs'
import { electronApp, optimizer, is } from '@electron-toolkit/utils'
import { BackendProcess } from './backend'
import {
  configureElectronStoragePaths,
  loadStoragePaths,
  saveStoragePaths,
  type StoragePathUpdate,
} from './storage'

let mainWindow: BrowserWindow | null = null
let backend: BackendProcess | null = null
let quitting = false

configureElectronStoragePaths()

function createWindow(baseURL: string): void {
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
    shell.openExternal(details.url)
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
  }

  const backendURL = backend.getBaseURL()

  // Expose backend URL to renderer via IPC (synchronous, no race condition)
  ipcMain.on('get-backend-url', (event) => {
    event.returnValue = backendURL
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

  ipcMain.handle('window:close', () => {
    mainWindow?.close()
  })

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

  ipcMain.handle('app:relaunch', () => {
    app.relaunch()
    app.quit()
  })

  ipcMain.handle('cache:clear-electron', async () => {
    await session.defaultSession.clearCache()
    return { ok: true }
  })

  // Create the main window
  createWindow(backendURL)

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow(backendURL)
    }
  })
})

app.on('before-quit', async (e) => {
  if (quitting) return
  quitting = true
  if (backend) {
    e.preventDefault()
    await cleanupBackend()
    app.quit()
  }
})

app.on('will-quit', async () => {
  await cleanupBackend()
  ipcMain.removeHandler('window:minimize')
  ipcMain.removeHandler('window:toggle-maximize')
  ipcMain.removeHandler('window:is-maximized')
  ipcMain.removeHandler('window:close')
  ipcMain.removeHandler('dialog:select-directory')
  ipcMain.removeHandler('storage:get')
  ipcMain.removeHandler('storage:set')
  ipcMain.removeHandler('app:relaunch')
  ipcMain.removeHandler('cache:clear-electron')
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})
