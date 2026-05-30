import { app, BrowserWindow, shell } from 'electron'
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

  mainWindow.webContents.setWindowOpenHandler((details) => {
    shell.openExternal(details.url)
    return { action: 'deny' }
  })

  if (is.dev && process.env['ELECTRON_RENDERER_URL']) {
    mainWindow.loadURL(process.env['ELECTRON_RENDERER_URL'])
  } else {
    mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
  }

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

  // Create the main window
  createWindow(backendURL)

  // Inject backend URL via preload
  // The preload script reads from window.__BACKEND_URL__
  if (mainWindow) {
    mainWindow.webContents.executeJavaScript(`window.__BACKEND_URL__ = '${backendURL}'`)
  }

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
