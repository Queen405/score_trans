import { ElectronAPI } from '@electron-toolkit/preload'

interface BackendAPI {
  getBackendURL(): string
  minimizeWindow(): Promise<void>
  toggleMaximizeWindow(): Promise<boolean>
  isMaximized(): Promise<boolean>
  closeWindow(): Promise<void>
  selectDirectory(): Promise<string | null>
  getStoragePaths(): Promise<{ dataDir: string; cacheDir: string; configPath: string }>
  setStoragePaths(paths: {
    dataDir?: string
    cacheDir?: string
  }): Promise<{ dataDir: string; cacheDir: string; configPath: string }>
  relaunchApp(): Promise<void>
  onMaximizedChanged(callback: (maximized: boolean) => void): () => void
}

declare global {
  interface Window {
    electron: ElectronAPI
    api: BackendAPI
    __BACKEND_URL__: string
  }
}
