import { app, ipcMain } from 'electron'
import fs from 'fs'
import path from 'path'

export type LocaleCode = 'zh-CN' | 'en-US'

const LOCALE_FILE = 'ui-locale.json'

const MAIN_MESSAGES: Record<LocaleCode, Record<string, string>> = {
  'zh-CN': {
    'backend.startFailedTitle': '后端启动失败',
    'backend.startFailedBody': 'Score Trans 后端无法启动，应用即将退出。\n\n{detail}',
    'close.unavailableTitle': '无法检查未保存的更改',
    'close.unavailableMessage': '界面进程当前不可用，未保存的更改可能丢失。',
    'close.unavailableDetail': '是否仍要直接退出？',
    'close.cancel': '取消',
    'close.quit': '直接退出',
    'files.windowUnavailable': '主窗口不可用',
    'files.invalidExportDir': '导出目录无效',
    'files.invalidFilename': '文件名无效',
    'files.invalidDir': '目录无效',
    'files.dirMustBeAbsolute': '目录必须是绝对路径',
    'files.openFolderFailed': '打开文件夹失败: {error}',
    'export.symlinkNotAllowed': '导出目录不能包含符号链接或重解析点',
    'export.uniqueNameFailed': '无法生成唯一的导出文件名',
    'export.invalidDir': '导出目录无效',
    'export.nulChar': '导出目录包含非法空字符',
    'export.mustBeAbsolute': '导出目录必须是绝对路径',
    'export.traversal': '导出目录不能包含路径遍历片段',
    'export.notDirectory': '导出路径中的已有项目不是目录',
    'export.escapesDir': '导出目标路径越出所选目录',
    'export.sourceArrayBuffer': '导出来源必须包含 ArrayBuffer',
    'update.connectFailed': '无法连接更新服务器：{error}',
    'update.badStatus': '更新服务器返回 {status}',
    'update.badFormat': '更新信息格式错误：{error}',
    'update.missingFields': '更新信息缺少必要字段',
  },
  'en-US': {
    'backend.startFailedTitle': 'Backend failed to start',
    'backend.startFailedBody':
      'The Score Trans backend could not start. The app will now quit.\n\n{detail}',
    'close.unavailableTitle': 'Cannot check for unsaved changes',
    'close.unavailableMessage':
      'The UI process is currently unavailable, so unsaved changes may be lost.',
    'close.unavailableDetail': 'Do you still want to quit directly?',
    'close.cancel': 'Cancel',
    'close.quit': 'Quit',
    'files.windowUnavailable': 'Main window unavailable',
    'files.invalidExportDir': 'Invalid export directory',
    'files.invalidFilename': 'Invalid file name',
    'files.invalidDir': 'Invalid directory',
    'files.dirMustBeAbsolute': 'Directory must be an absolute path',
    'files.openFolderFailed': 'Failed to open folder: {error}',
    'export.symlinkNotAllowed':
      'Export directory must not contain symbolic links or reparse points',
    'export.uniqueNameFailed': 'Could not generate a unique export file name',
    'export.invalidDir': 'Invalid export directory',
    'export.nulChar': 'Export directory contains an illegal null character',
    'export.mustBeAbsolute': 'Export directory must be an absolute path',
    'export.traversal': 'Export directory must not contain path traversal segments',
    'export.notDirectory': 'An existing item in the export path is not a directory',
    'export.escapesDir': 'Export target path escapes the selected directory',
    'export.sourceArrayBuffer': 'Export source must contain an ArrayBuffer',
    'update.connectFailed': 'Could not reach the update server: {error}',
    'update.badStatus': 'Update server returned {status}',
    'update.badFormat': 'Malformed update information: {error}',
    'update.missingFields': 'Update information is missing required fields',
  },
}

let cachedLocale: LocaleCode | null = null

export function isLocaleCode(value: unknown): value is LocaleCode {
  return value === 'zh-CN' || value === 'en-US'
}

function localeFilePath(): string {
  return path.join(app.getPath('userData'), LOCALE_FILE)
}

function systemLocale(): LocaleCode {
  const tag = app.getLocale() || ''
  return tag.toLowerCase().startsWith('zh') ? 'zh-CN' : 'en-US'
}

export function getLocale(): LocaleCode {
  if (cachedLocale) return cachedLocale
  try {
    const raw = fs.readFileSync(localeFilePath(), 'utf-8')
    const parsed = JSON.parse(raw) as { locale?: unknown }
    if (isLocaleCode(parsed?.locale)) {
      cachedLocale = parsed.locale
      return cachedLocale
    }
  } catch {
    // Fall through to the system default when no preference has been stored yet.
  }
  cachedLocale = systemLocale()
  return cachedLocale
}

export function setLocale(next: LocaleCode): LocaleCode {
  cachedLocale = next
  try {
    fs.mkdirSync(path.dirname(localeFilePath()), { recursive: true })
    fs.writeFileSync(localeFilePath(), `${JSON.stringify({ locale: next }, null, 2)}\n`, 'utf-8')
  } catch {
    // The in-memory value stays effective even when the file cannot be written.
  }
  return cachedLocale
}

export function registerLocaleIpc(): void {
  ipcMain.handle('locale:get', () => getLocale())
  ipcMain.handle('locale:set', (_event, next: unknown) => {
    return isLocaleCode(next) ? setLocale(next) : getLocale()
  })
}

export function t(key: string, vars?: Record<string, string | number>): string {
  const raw = MAIN_MESSAGES[getLocale()][key]
  if (raw === undefined) return key
  if (!vars) return raw
  return raw.replace(/\{(\w+)\}/g, (match, name: string) =>
    name in vars ? String(vars[name]) : match,
  )
}
