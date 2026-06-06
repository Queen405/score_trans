import type { UploadResponse } from '../models/types'

function getBaseURL(): string {
  return (
    (window as any)?.api?.getBackendURL?.() ||
    import.meta.env.VITE_BACKEND_URL ||
    'http://127.0.0.1:19200'
  )
}

export class ApiError extends Error {
  stage?: string
  detail?: string

  constructor(message: string, stage?: string, detail?: string) {
    super(message)
    this.name = 'ApiError'
    this.stage = stage
    this.detail = detail
  }
}

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${getBaseURL()}${path}`, options)

  if (!response.ok) {
    const payload = await response.json().catch(() => ({} as Record<string, unknown>))
    const rawMessage = payload.error ?? payload.detail
    const message =
      typeof rawMessage === 'string'
        ? rawMessage
        : rawMessage
          ? JSON.stringify(rawMessage)
          : `HTTP ${response.status}`
    const stage = typeof payload.stage === 'string' ? payload.stage : undefined
    const detail =
      typeof payload.detail === 'string'
        ? payload.detail
        : payload.detail
          ? JSON.stringify(payload.detail)
          : undefined

    throw new ApiError(message, stage, detail)
  }

  return response.json()
}

export async function uploadFile(file: File): Promise<UploadResponse> {
  const formData = new FormData()
  formData.append('file', file)
  return apiFetch<UploadResponse>('/files/upload', {
    method: 'POST',
    body: formData,
  })
}

export function getFileURL(fileId: string): string {
  return `${getBaseURL()}/files/${fileId}`
}

async function probeFile(url: string, options: RequestInit): Promise<boolean | null> {
  try {
    const res = await fetch(url, { cache: 'no-store', ...options })
    if (res.ok || res.status === 206) return true
    if (res.status === 404 || res.status === 410) return false
    return null
  } catch {
    return null
  }
}

export async function fileExists(fileId: string): Promise<boolean> {
  if (!fileId) return false

  const url = getFileURL(fileId)
  const head = await probeFile(url, { method: 'HEAD' })
  if (head !== null) return head

  const ranged = await probeFile(url, { method: 'GET', headers: { Range: 'bytes=0-0' } })
  if (ranged !== null) return ranged

  return true
}

export { getBaseURL as BASE_URL }
