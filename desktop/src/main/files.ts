import { ipcMain, shell } from 'electron'
import type { BrowserWindow } from 'electron'
import path from 'path'
import { writeUniqueExportFile } from './exportPath'
import { exportSourceBuffer } from './exportSource'
import { t } from './locale'

export function registerFileHandlers(getMainWindow: () => BrowserWindow | null): void {
  ipcMain.handle(
    'file:save-export',
    async (_event, source: unknown, dir: string, filename: string) => {
      const win = getMainWindow()
      if (!win) {
        throw new Error(t('files.windowUnavailable'))
      }
      if (!dir || typeof dir !== 'string') {
        throw new Error(t('files.invalidExportDir'))
      }
      if (!filename || typeof filename !== 'string') {
        throw new Error(t('files.invalidFilename'))
      }

      return writeUniqueExportFile(dir, filename, exportSourceBuffer(source))
    },
  )

  ipcMain.handle('file:open-folder', async (_event, dir: string) => {
    if (!dir || typeof dir !== 'string') {
      throw new Error(t('files.invalidDir'))
    }
    if (!path.isAbsolute(dir)) {
      throw new Error(t('files.dirMustBeAbsolute'))
    }
    const error = await shell.openPath(dir)
    if (error) {
      throw new Error(t('files.openFolderFailed', { error }))
    }
  })
}
