import type { UploadResponse } from '../models/types'

type BackendConnection = Awaited<
  ReturnType<Window['api']['getBackendConnection']>
>

let backendConnection: BackendConnection | null = null

function fallbackBackendConnection(): BackendConnection {
  const viteEnv = import.meta.env ?? {}
  return {
    baseURL: viteEnv.VITE_BACKEND_URL || 'http://127.0.0.1:19200',
    token: viteEnv.VITE_BACKEND_TOKEN || '',
  }
}

export async function initializeBackendConnection(): Promise<void> {
  const fallback = fallbackBackendConnection()
  if (typeof window === 'undefined' || !window.api?.getBackendConnection) {
    backendConnection = fallback
    return
  }
  try {
    const connection = await window.api.getBackendConnection()
    backendConnection = connection.baseURL
      ? { baseURL: connection.baseURL, token: connection.token || '' }
      : fallback
  } catch (error) {
    console.warn('Failed to initialize backend connection:', error)
    backendConnection = fallback
  }
}

function getBackendConnection(): BackendConnection {
  return backendConnection ?? fallbackBackendConnection()
}

export function getBaseURL(): string {
  return getBackendConnection().baseURL
}

export function getApiToken(): string {
  return getBackendConnection().token
}

export function authenticatedFetch(
  input: RequestInfo | URL,
  options: RequestInit = {},
): Promise<Response> {
  const headers = new Headers(options.headers)
  const token = getApiToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  return fetch(input, { ...options, headers })
}

export class ApiError extends Error {
  stage?: string
  detail?: string
  code?: string

  constructor(message: string, stage?: string, detail?: string, code?: string) {
    super(message)
    this.name = 'ApiError'
    this.stage = stage
    this.detail = detail
    this.code = code
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
    const response = await authenticatedFetch(`${getBaseURL()}${path}`, options)
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
    const token = getApiToken()
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)
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
  const code = typeof payload.code === 'string' ? payload.code : undefined
  return new ApiError(message, stage, detail, code)
}

function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error
  if (
    typeof error === 'object'
    && error !== null
    && 'name' in error
    && (error as { name?: unknown }).name === 'AbortError'
  ) {
    return new ApiError('aborted', undefined, undefined, 'aborted')
  }
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
    const response = await authenticatedFetch(getFileURL(fileId), { signal })
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
    const res = await authenticatedFetch(url, { cache: 'no-store', ...options })
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
