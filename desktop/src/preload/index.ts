import { contextBridge, ipcRenderer } from 'electron'
import { electronAPI } from '@electron-toolkit/preload'

export type CloseDecision = 'cancel' | 'proceed'
export interface CloseRequest {
  requestId: number
  intent: 'close' | 'relaunch'
}

export interface BackendConnection {
  baseURL: string
  token: string
}

export interface UpdateCheckResult {
  hasUpdate: boolean
  currentVersion: string
  latestVersion: string | null
  downloadUrl: string | null
  notes: string | null
  error: string | null
}

const api = {
  getBackendConnection: async (): Promise<BackendConnection> => {
    return await ipcRenderer.invoke('get-backend-connection') || {
      baseURL: 'http://127.0.0.1:19200',
      token: '',
    }
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
    await ipcRenderer.invoke('app:request-close', 'close')
  },
  onCloseRequested: (callback: (request: CloseRequest) => void): (() => void) => {
    const listener = (_event: unknown, request: CloseRequest) => callback(request)
    ipcRenderer.on('app:close-requested', listener)
    return () => ipcRenderer.removeListener('app:close-requested', listener)
  },
  notifyCloseListenerReady: async (): Promise<void> => {
    await ipcRenderer.invoke('app:close-listener-ready')
  },
  resolveCloseRequest: (
    requestId: number,
    decision: CloseDecision,
  ): void => {
    ipcRenderer.send('app:resolve-close', requestId, decision)
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
    await ipcRenderer.invoke('app:request-close', 'relaunch')
  },
  clearElectronCache: async (): Promise<void> => {
    await ipcRenderer.invoke('cache:clear-electron')
  },
  checkForUpdate: async (): Promise<UpdateCheckResult> => {
    return ipcRenderer.invoke('app:check-update')
  },
  getVersion: async (): Promise<string> => {
    return ipcRenderer.invoke('app:get-version')
  },
  openExternal: async (url: string): Promise<void> => {
    await ipcRenderer.invoke('app:open-external', url)
  },
  saveExportFile: async (
    source: { buffer: ArrayBuffer },
    dir: string,
    filename: string,
  ): Promise<string> => {
    return ipcRenderer.invoke('file:save-export', source, dir, filename)
  },
  openFolder: async (dir: string): Promise<void> => {
    await ipcRenderer.invoke('file:open-folder', dir)
  },
}

export type BackendAPI = typeof api

if (process.contextIsolated) {
  try {
    contextBridge.exposeInMainWorld('electron', electronAPI)
    contextBridge.exposeInMainWorld('api', api)
  } catch (error) {
    console.error(error)
  }
} else {
  window.electron = electronAPI
  window.api = api
}
