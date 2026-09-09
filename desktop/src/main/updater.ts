import { app } from 'electron'

export interface UpdateCheckResult {
  hasUpdate: boolean
  currentVersion: string
  latestVersion: string | null
  downloadUrl: string | null
  notes: string | null
  error: string | null
}

interface Manifest {
  version: string
  url: string
  notes?: string
}

const UPDATE_MANIFEST_URL =
  process.env.SCORE_TRANS_UPDATE_MANIFEST_URL ??
  'https://cdn.jsdelivr.net/gh/Queen405/score_trans/desktop/latest.json'

const FETCH_TIMEOUT_MS = 5000

export async function checkForUpdate(): Promise<UpdateCheckResult> {
  const currentVersion = app.getVersion()
  const base: UpdateCheckResult = {
    hasUpdate: false,
    currentVersion,
    latestVersion: null,
    downloadUrl: null,
    notes: null,
    error: null,
  }

  let response: Response
  try {
    response = await fetch(`${UPDATE_MANIFEST_URL}?t=${Date.now()}`, {
      headers: { 'Cache-Control': 'no-cache' },
      signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
    })
  } catch (err) {
    return { ...base, error: `无法连接更新服务器：${errorMessage(err)}` }
  }

  if (!response.ok) {
    return { ...base, error: `更新服务器返回 ${response.status}` }
  }

  let manifest: Manifest
  try {
    manifest = (await response.json()) as Manifest
  } catch (err) {
    return { ...base, error: `更新信息格式错误：${errorMessage(err)}` }
  }

  if (typeof manifest.version !== 'string' || typeof manifest.url !== 'string') {
    return { ...base, error: '更新信息缺少必要字段' }
  }

  return {
    hasUpdate: isNewer(manifest.version, currentVersion),
    currentVersion,
    latestVersion: manifest.version,
    downloadUrl: manifest.url,
    notes: manifest.notes ?? null,
    error: null,
  }
}

function isNewer(remote: string, local: string): boolean {
  const remoteParts = remote.split('.').map((n) => Number.parseInt(n, 10))
  const localParts = local.split('.').map((n) => Number.parseInt(n, 10))
  if (remoteParts.length !== 3 || localParts.length !== 3) {
    return remote !== local
  }
  if (remoteParts.some(Number.isNaN) || localParts.some(Number.isNaN)) {
    return remote !== local
  }
  for (let i = 0; i < 3; i++) {
    const r = remoteParts[i]!
    const l = localParts[i]!
    if (r > l) return true
    if (r < l) return false
  }
  return false
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}
