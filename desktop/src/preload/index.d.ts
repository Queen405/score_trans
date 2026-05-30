import { ElectronAPI } from '@electron-toolkit/preload'

interface BackendAPI {
  getBackendURL(): string
}

declare global {
  interface Window {
    electron: ElectronAPI
    api: BackendAPI
    __BACKEND_URL__: string
  }
}
