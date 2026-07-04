import { promises as fs } from 'fs'
import path from 'path'

const WINDOWS_DEVICE_NAME = /^(con|prn|aux|nul|com[1-9]|lpt[1-9])$/i
const MAX_FILENAME_LENGTH = 240
const MAX_UNIQUE_ATTEMPTS = 10_000

export function sanitizeExportFilename(name: string): string {
  const withoutControls = Array.from(
    name,
    (character) => character.charCodeAt(0) <= 0x1f ? '_' : character,
  ).join('')
  let safe = withoutControls
    .replace(/[\\/:*?"<>|]/g, '_')
    .replace(/[.\s]+$/g, '')
    .replace(/^\.+/g, '')

  if (!safe) safe = 'export'

  const extension = path.extname(safe)
  const stem = path.basename(safe, extension)
  if (WINDOWS_DEVICE_NAME.test(stem)) {
    safe = `_${safe}`
  }

  if (safe.length > MAX_FILENAME_LENGTH) {
    const preservedExtension = path.extname(safe).slice(0, 32)
    safe = `${path.basename(safe, path.extname(safe)).slice(
      0,
      MAX_FILENAME_LENGTH - preservedExtension.length,
    )}${preservedExtension}`
  }
  return safe
}

export async function writeUniqueExportFile(
  directory: string,
  filename: string,
  data: Uint8Array,
): Promise<string> {
  validateExportDirectory(directory)
  const requestedDirectory = path.resolve(directory)
  await assertNoLinkedPathComponents(requestedDirectory)
  await fs.mkdir(requestedDirectory, { recursive: true })

  const canonicalDirectory = await fs.realpath(requestedDirectory)
  if (comparablePath(canonicalDirectory) !== comparablePath(requestedDirectory)) {
    throw new Error('导出目录不能包含符号链接或重解析点')
  }

  const safeName = sanitizeExportFilename(filename)
  const extension = path.extname(safeName)
  const stem = path.basename(safeName, extension)

  for (let counter = 0; counter < MAX_UNIQUE_ATTEMPTS; counter += 1) {
    const candidateName = counter === 0
      ? safeName
      : `${stem}(${counter})${extension}`
    const candidate = path.join(canonicalDirectory, candidateName)
    assertContainedPath(canonicalDirectory, candidate)

    let handle
    try {
      handle = await fs.open(candidate, 'wx')
    } catch (error) {
      if (isNodeError(error) && error.code === 'EEXIST') continue
      throw error
    }

    try {
      await handle.writeFile(data)
      return candidate
    } catch (error) {
      await handle.close()
      handle = undefined
      await fs.unlink(candidate).catch(() => undefined)
      throw error
    } finally {
      await handle?.close()
    }
  }

  throw new Error('无法生成唯一的导出文件名')
}

function validateExportDirectory(directory: string): void {
  if (!directory || typeof directory !== 'string') {
    throw new Error('导出目录无效')
  }
  if (directory.includes('\0')) {
    throw new Error('导出目录包含非法空字符')
  }
  if (!path.isAbsolute(directory)) {
    throw new Error('导出目录必须是绝对路径')
  }

  const root = path.parse(directory).root
  const segments = directory.slice(root.length).split(/[\\/]+/)
  if (segments.includes('..')) {
    throw new Error('导出目录不能包含路径遍历片段')
  }
}

async function assertNoLinkedPathComponents(directory: string): Promise<void> {
  const parsed = path.parse(directory)
  const segments = directory.slice(parsed.root.length).split(/[\\/]+/).filter(Boolean)
  let current = parsed.root
  let reachedMissingComponent = false

  for (const segment of segments) {
    current = path.join(current, segment)
    if (reachedMissingComponent) continue
    try {
      const stat = await fs.lstat(current)
      if (stat.isSymbolicLink()) {
        throw new Error('导出目录不能包含符号链接或重解析点')
      }
      if (!stat.isDirectory()) {
        throw new Error('导出路径中的已有项目不是目录')
      }
    } catch (error) {
      if (isNodeError(error) && error.code === 'ENOENT') {
        reachedMissingComponent = true
        continue
      }
      throw error
    }
  }
}

function assertContainedPath(directory: string, candidate: string): void {
  const relative = path.relative(directory, candidate)
  if (
    !relative
    || relative === '..'
    || relative.startsWith(`..${path.sep}`)
    || path.isAbsolute(relative)
  ) {
    throw new Error('导出目标路径越出所选目录')
  }
}

function comparablePath(value: string): string {
  const normalized = path.normalize(value).replace(/^\\\\\?\\/, '')
  return process.platform === 'win32' ? normalized.toLowerCase() : normalized
}

function isNodeError(error: unknown): error is NodeJS.ErrnoException {
  return error instanceof Error && 'code' in error
}
