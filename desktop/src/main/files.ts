import { ipcMain, shell } from 'electron'
import type { BrowserWindow } from 'electron'
import { promises as fs } from 'fs'
import path from 'path'

function sanitizeFilename(name: string): string {
  return name.replace(/[\\/:*?"<>|]/g, '_')
}

function isValidExportDir(dir: string): boolean {
  return path.isAbsolute(dir) && !dir.includes('\0')
}

async function uniqueFilePath(dir: string, filename: string): Promise<string> {
  const ext = path.extname(filename)
  const base = path.basename(filename, ext)
  let candidate = path.join(dir, filename)
  let counter = 1
  while (true) {
    try {
      await fs.access(candidate)
      candidate = path.join(dir, `${base}(${counter})${ext}`)
      counter++
    } catch {
      break
    }
  }
  return candidate
}

export function registerFileHandlers(getMainWindow: () => BrowserWindow | null): void {
  ipcMain.handle(
    'file:save-export',
    async (_event, source: { url: string } | { buffer: ArrayBuffer }, dir: string, filename: string) => {
      const win = getMainWindow()
      if (!win) {
        throw new Error('主窗口不可用')
      }
      if (!dir || typeof dir !== 'string') {
        throw new Error('导出目录无效')
      }
      if (!isValidExportDir(dir)) {
        throw new Error('导出目录必须是绝对路径')
      }
      if (!filename || typeof filename !== 'string') {
        throw new Error('文件名无效')
      }

      const safeName = sanitizeFilename(filename)
      await fs.mkdir(dir, { recursive: true })
      const targetPath = await uniqueFilePath(dir, safeName)

      if ('url' in source && typeof source.url === 'string') {
        const res = await fetch(source.url)
        if (!res.ok) {
          throw new Error(`下载失败: ${res.status}`)
        }
        const buffer = Buffer.from(await res.arrayBuffer())
        await fs.writeFile(targetPath, buffer)
      } else if ('buffer' in source && source.buffer instanceof ArrayBuffer) {
        await fs.writeFile(targetPath, Buffer.from(source.buffer))
      } else {
        throw new Error('不支持的文件来源')
      }

      return targetPath
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
