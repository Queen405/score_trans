import { app, BrowserWindow, shell, ipcMain } from 'electron'
import { join } from 'path'
import { electronApp, optimizer, is } from '@electron-toolkit/utils'
import { BackendProcess } from './backend'

let mainWindow: BrowserWindow | null = null
let backend: BackendProcess | null = null

function createWindow(baseURL: string): void {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    frame: false,
    autoHideMenuBar: true,
    show: false,
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

  // Create the main window
  createWindow(backendURL)

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow(backendURL)
    }
  })
})

app.on('before-quit', async (e) => {
  if (backend) {
    e.preventDefault()
    try {
      await backend.stop()
    } catch (err) {
      console.error('[main] Error stopping backend:', err)
    }
    backend = null
    app.quit()
  }
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('will-quit', () => {
  ipcMain.removeHandler('window:minimize')
  ipcMain.removeHandler('window:toggle-maximize')
  ipcMain.removeHandler('window:is-maximized')
  ipcMain.removeHandler('window:close')
})
