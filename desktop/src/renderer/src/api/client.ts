import type { UploadResponse } from '../models/types'

const BASE_URL: string =
  (window as any)?.api?.getBackendURL?.() || 'http://127.0.0.1:18513'

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
  const response = await fetch(`${BASE_URL}${path}`, options)

  if (!response.ok) {
    const error = await response.json().catch(() => ({
      error: `HTTP ${response.status}`,
    }))
    throw new ApiError(error.error || `HTTP ${response.status}`, error.stage, error.detail)
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
  return `${BASE_URL}/files/${fileId}`
}

export { BASE_URL }
