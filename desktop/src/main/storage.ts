import { app } from 'electron'
import fs from 'fs'
import path from 'path'

const USER_DATA_DIR_NAME = '.sorce_trans'
const STORAGE_CONFIG_FILE = 'storage-paths.json'
const CACHE_DIR_NAME = 'cache'
const ELECTRON_SESSION_DIR_NAME = 'electron-session'
const DB_FILE_NAMES = ['settings.db', 'history.db', 'ai_chat.db', 'tasks.db']

export interface StoragePaths {
  dataDir: string
  cacheDir: string
  configPath: string
}

export interface StoragePathUpdate {
  dataDir?: string
  cacheDir?: string
}

export function loadStoragePaths(): StoragePaths {
  const defaults = defaultStoragePaths()
  const config = readStorageConfig(defaults.configPath)
  const dataDir = normalizeDir(config.dataDir, defaults.dataDir)
  const cacheDir = normalizeDir(config.cacheDir, path.join(dataDir, CACHE_DIR_NAME))
  return { dataDir, cacheDir, configPath: defaults.configPath }
}

export function configureElectronStoragePaths(): StoragePaths {
  const paths = loadStoragePaths()
  const sessionDir = path.join(paths.cacheDir, ELECTRON_SESSION_DIR_NAME)
  fs.mkdirSync(sessionDir, { recursive: true })
  app.setPath('sessionData', sessionDir)
  return paths
}

export function saveStoragePaths(update: StoragePathUpdate): StoragePaths {
  const previous = loadStoragePaths()
  const dataDir = normalizeDir(update.dataDir, previous.dataDir)
  const cacheDir = normalizeDir(update.cacheDir, previous.cacheDir)
  const next = { dataDir, cacheDir, configPath: previous.configPath }

  if (dataDir !== previous.dataDir) {
    migrateDataFiles(previous.dataDir, dataDir)
  }
  if (cacheDir !== previous.cacheDir) {
    copyDirectoryContents(previous.cacheDir, cacheDir)
  }

  fs.mkdirSync(path.dirname(previous.configPath), { recursive: true })
  fs.writeFileSync(
    previous.configPath,
    `${JSON.stringify({ dataDir, cacheDir }, null, 2)}\n`,
    'utf-8',
  )
  fs.mkdirSync(dataDir, { recursive: true })
  fs.mkdirSync(cacheDir, { recursive: true })
  return next
}

function defaultStoragePaths(): StoragePaths {
  const dataDir = path.join(app.getPath('home'), USER_DATA_DIR_NAME)
  return {
    dataDir,
    cacheDir: path.join(dataDir, CACHE_DIR_NAME),
    configPath: path.join(dataDir, STORAGE_CONFIG_FILE),
  }
}

function normalizeDir(value: unknown, fallback: string): string {
  if (typeof value !== 'string' || !value.trim()) {
    return path.resolve(fallback)
  }
  return path.resolve(value.trim())
}

function readStorageConfig(configPath: string): StoragePathUpdate {
  try {
    const raw = fs.readFileSync(configPath, 'utf-8')
    const parsed = JSON.parse(raw) as StoragePathUpdate
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return {}
  }
}

function migrateDataFiles(sourceDataDir: string, targetDataDir: string): void {
  for (const name of DB_FILE_NAMES) {
    for (const suffix of ['', '-wal', '-shm']) {
      copyFileIfMissing(
        path.join(sourceDataDir, 'work', `${name}${suffix}`),
        path.join(targetDataDir, 'work', `${name}${suffix}`),
      )
    }
  }
}

function copyDirectoryContents(source: string, target: string): void {
  if (!fs.existsSync(source) || path.resolve(source) === path.resolve(target)) {
    return
  }
  for (const child of fs.readdirSync(source)) {
    copyPathIfMissing(path.join(source, child), path.join(target, child))
  }
}

function copyPathIfMissing(source: string, target: string): void {
  if (fs.existsSync(target)) {
    return
  }
  try {
    const stat = fs.statSync(source)
    if (stat.isDirectory()) {
      fs.mkdirSync(target, { recursive: true })
      copyDirectoryContents(source, target)
      return
    }
    if (stat.isFile()) {
      copyFileIfMissing(source, target)
    }
  } catch {
    return
  }
}

function copyFileIfMissing(source: string, target: string): void {
  if (!fs.existsSync(source) || fs.existsSync(target)) {
    return
  }
  try {
    fs.mkdirSync(path.dirname(target), { recursive: true })
    fs.copyFileSync(source, target)
  } catch {
    return
  }
}
