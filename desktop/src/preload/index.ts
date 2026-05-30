import { contextBridge, ipcRenderer } from 'electron'
import { electronAPI } from '@electron-toolkit/preload'

const api = {
  getBackendURL: (): string => {
    return ipcRenderer.sendSync('get-backend-url') || 'http://127.0.0.1:18513'
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
