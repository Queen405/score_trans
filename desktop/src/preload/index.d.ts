import type { ElectronAPI } from '@electron-toolkit/preload'
import type { BackendAPI } from './index'

declare global {
  interface Window {
    electron: ElectronAPI
    api: BackendAPI
  }
}
