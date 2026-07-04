import { ipcMain, shell } from 'electron'
import type { BrowserWindow } from 'electron'
import path from 'path'
import { writeUniqueExportFile } from './exportPath'
import { exportSourceBuffer } from './exportSource'

export function registerFileHandlers(getMainWindow: () => BrowserWindow | null): void {
  ipcMain.handle(
    'file:save-export',
    async (_event, source: unknown, dir: string, filename: string) => {
      const win = getMainWindow()
      if (!win) {
        throw new Error('主窗口不可用')
      }
      if (!dir || typeof dir !== 'string') {
        throw new Error('导出目录无效')
      }
      if (!filename || typeof filename !== 'string') {
        throw new Error('文件名无效')
      }

      return writeUniqueExportFile(dir, filename, exportSourceBuffer(source))
    },
  )

  ipcMain.handle('file:open-folder', async (_event, dir: string) => {
    if (!dir || typeof dir !== 'string') {
      throw new Error('目录无效')
    }
    if (!path.isAbsolute(dir)) {
      throw new Error('目录必须是绝对路径')
    }
    const error = await shell.openPath(dir)
    if (error) {
      throw new Error(`打开文件夹失败: ${error}`)
    }
  })
}
