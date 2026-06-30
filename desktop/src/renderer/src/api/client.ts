import type { UploadResponse } from '../models/types'

export function getBaseURL(): string {
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

export type ApiResult<T> =
  | { data: T; error: null }
  | { data: null; error: ApiError }

export async function apiFetch<T>(
  path: string,
  options?: RequestInit,
): Promise<ApiResult<T>> {
  try {
    const response = await fetch(`${getBaseURL()}${path}`, options)
    if (!response.ok) {
      const payload = await response.json().catch(() => ({} as Record<string, unknown>))
      return apiFailure(apiErrorFromResponse(response.status, payload))
    }
    return apiSuccess(await response.json() as T)
  } catch (error) {
    return apiFailure(toApiError(error))
  }
}

export function apiSuccess<T>(data: T): ApiResult<T> {
  return { data, error: null }
}

export function apiFailure<T = never>(error: unknown): ApiResult<T> {
  return { data: null, error: toApiError(error) }
}

export async function toApiResult<T>(promise: Promise<T>): Promise<ApiResult<T>> {
  try {
    return apiSuccess(await promise)
  } catch (error) {
    return apiFailure(error)
  }
}

export async function requireData<T>(
  resultPromise: Promise<ApiResult<T>>,
): Promise<T> {
  const result = await resultPromise
  if (result.error) throw result.error
  return result.data
}

export type UploadProgressCallback = (percent: number, phase: 'upload' | 'processing') => void

export async function uploadFile(
  file: File,
  onProgress?: UploadProgressCallback,
): Promise<ApiResult<UploadResponse>> {
  return toApiResult(uploadFileData(file, onProgress))
}

async function uploadFileData(
  file: File,
  onProgress?: UploadProgressCallback,
): Promise<UploadResponse> {
  if (!onProgress) {
    const formData = new FormData()
    formData.append('file', file)
    return requireData(apiFetch<UploadResponse>('/files/upload', {
      method: 'POST',
      body: formData,
    }))
  }
  return new Promise<UploadResponse>((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${getBaseURL()}/files/upload`)
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        // Cap upload phase at 85% — remaining 15% is server-side processing
        onProgress(Math.min(85, Math.round((e.loaded / e.total) * 85)), 'upload')
      }
    }
    xhr.upload.onload = () => {
      // All bytes sent, server is now processing (e.g. PDF → images)
      onProgress(85, 'processing')
    }
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        onProgress(100, 'processing')
        try { resolve(JSON.parse(xhr.responseText) as UploadResponse) }
        catch { reject(new ApiError('Invalid JSON response')) }
      } else {
        let msg = `HTTP ${xhr.status}`
        try { msg = JSON.parse(xhr.responseText).error ?? msg } catch { /* ignore */ }
        reject(new ApiError(msg))
      }
    }
    xhr.onerror = () => reject(new ApiError('网络错误'))
    const formData = new FormData()
    formData.append('file', file)
    xhr.send(formData)
  })
}

function apiErrorFromResponse(
  status: number,
  payload: Record<string, unknown>,
): ApiError {
  const rawMessage = payload.error ?? payload.detail
  const message =
    typeof rawMessage === 'string'
      ? rawMessage
      : rawMessage
        ? JSON.stringify(rawMessage)
        : `HTTP ${status}`
  const stage = typeof payload.stage === 'string' ? payload.stage : undefined
  const detail =
    typeof payload.detail === 'string'
      ? payload.detail
      : payload.detail
        ? JSON.stringify(payload.detail)
        : undefined
  return new ApiError(message, stage, detail)
}

function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error
  if (error instanceof Error) return new ApiError(error.message)
  return new ApiError(String(error))
}

export function getFileURL(fileId: string): string {
  return `${getBaseURL()}/files/${fileId}`
}

export async function fetchFileBlob(
  fileId: string,
  signal?: AbortSignal,
): Promise<ApiResult<Blob>> {
  try {
    const response = await fetch(getFileURL(fileId), { signal })
    if (!response.ok) {
      const payload = await response.json().catch(() => ({} as Record<string, unknown>))
      return apiFailure(apiErrorFromResponse(response.status, payload))
    }
    return apiSuccess(await response.blob())
  } catch (error) {
    return apiFailure(error)
  }
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
