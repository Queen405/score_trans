import fs from 'fs'
import path from 'path'

export function migrateLegacyDataDirectory(source: string, target: string): boolean {
  if (!fs.existsSync(source)) {
    return true
  }
  if (path.resolve(source) === path.resolve(target)) {
    return true
  }

  try {
    const sourceStat = fs.lstatSync(source)
    if (sourceStat.isSymbolicLink() || !sourceStat.isDirectory()) {
      return false
    }
    fs.mkdirSync(target, { recursive: true })
    return copyMissingDirectoryContents(source, target)
  } catch {
    return false
  }
}

function copyMissingDirectoryContents(source: string, target: string): boolean {
  let succeeded = true
  for (const name of fs.readdirSync(source)) {
    const sourceChild = path.join(source, name)
    const targetChild = path.join(target, name)
    try {
      const stat = fs.lstatSync(sourceChild)
      if (stat.isSymbolicLink()) {
        succeeded = false
      } else if (stat.isDirectory()) {
        if (fs.existsSync(targetChild) && !fs.statSync(targetChild).isDirectory()) {
          continue
        }
        fs.mkdirSync(targetChild, { recursive: true })
        succeeded = copyMissingDirectoryContents(sourceChild, targetChild) && succeeded
      } else if (stat.isFile()) {
        succeeded = copyFileIfMissing(sourceChild, targetChild) && succeeded
      } else {
        succeeded = false
      }
    } catch {
      succeeded = false
    }
  }
  return succeeded
}

function copyFileIfMissing(source: string, target: string): boolean {
  if (fs.existsSync(target)) {
    return true
  }
  try {
    fs.mkdirSync(path.dirname(target), { recursive: true })
    fs.copyFileSync(source, target, fs.constants.COPYFILE_EXCL)
    return true
  } catch {
    return fs.existsSync(target)
  }
}
