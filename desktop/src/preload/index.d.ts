import { ElectronAPI } from '@electron-toolkit/preload'

interface BackendAPI {
  getBackendURL(): string
  minimizeWindow(): Promise<void>
  toggleMaximizeWindow(): Promise<boolean>
  isMaximized(): Promise<boolean>
  closeWindow(): Promise<void>
  onMaximizedChanged(callback: (maximized: boolean) => void): () => void
}

declare global {
  interface Window {
    electron: ElectronAPI
    api: BackendAPI
    __BACKEND_URL__: string
  }
}
