import { contextBridge, ipcRenderer } from 'electron'
import { electronAPI } from '@electron-toolkit/preload'

const api = {
  getBackendURL: (): string => {
    return ipcRenderer.sendSync('get-backend-url') || 'http://127.0.0.1:19200'
  },
  minimizeWindow: async (): Promise<void> => {
    await ipcRenderer.invoke('window:minimize')
  },
  toggleMaximizeWindow: async (): Promise<boolean> => {
    return ipcRenderer.invoke('window:toggle-maximize')
  },
  isMaximized: async (): Promise<boolean> => {
    return ipcRenderer.invoke('window:is-maximized')
  },
  closeWindow: async (): Promise<void> => {
    await ipcRenderer.invoke('window:close')
  },
  onMaximizedChanged: (callback: (maximized: boolean) => void): (() => void) => {
    const listener = (_event: unknown, maximized: boolean) => {
      callback(maximized)
    }
    ipcRenderer.on('window:maximized-changed', listener)
    return () => {
      ipcRenderer.removeListener('window:maximized-changed', listener)
    }
  },
  selectDirectory: async (): Promise<string | null> => {
    return ipcRenderer.invoke('dialog:select-directory')
  },
  getStoragePaths: async (): Promise<{ dataDir: string; cacheDir: string; configPath: string }> => {
    return ipcRenderer.invoke('storage:get')
  },
  setStoragePaths: async (paths: { dataDir?: string; cacheDir?: string }): Promise<{ dataDir: string; cacheDir: string; configPath: string }> => {
    return ipcRenderer.invoke('storage:set', paths)
  },
  relaunchApp: async (): Promise<void> => {
    await ipcRenderer.invoke('app:relaunch')
  },
}

if (process.contextIsolated) {
  try {
    contextBridge.exposeInMainWorld('electron', electronAPI)
    contextBridge.exposeInMainWorld('api', api)
  } catch (error) {
    console.error(error)
  }
} else {
  ;(window as any).electron = electronAPI
  ;(window as any).api = api
}
