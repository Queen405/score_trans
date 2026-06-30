import { apiFetch, getFileURL, type ApiResult } from './client'
import type { ExportMidiTextRequest, ExportResponse } from '../models/types'

export const exportApi = {
  async exportMidi(musicxmlFileId: string, filename?: string): Promise<ApiResult<ExportResponse>> {
    const params = new URLSearchParams({ musicxml_file_id: musicxmlFileId })
    if (filename) params.set('filename', filename)
    return apiFetch(`/export/midi?${params.toString()}`, { method: 'POST' })
  },

  async exportMidiText(req: ExportMidiTextRequest): Promise<ApiResult<ExportResponse>> {
    return apiFetch('/export/midi-text', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    })
  },

  async exportPdf(imagePages: Blob[], filename = 'jianpu.pdf'): Promise<ApiResult<ExportResponse>> {
    const form = new FormData()
    form.append('filename', filename)
    for (let i = 0; i < imagePages.length; i++) {
      const blob = imagePages[i]
      const ext = blob.type === 'image/jpeg' ? 'jpg' : 'png'
      form.append('files', blob, `page_${i + 1}.${ext}`)
    }
    return apiFetch('/export/pdf', { method: 'POST', body: form })
  },

  getDownloadURL(fileId: string): string {
    return getFileURL(fileId)
  },
}

export async function svgToPngBlob(svgUrl: string, scale = 1): Promise<Blob> {
  const img = new Image()
  const loaded = new Promise<void>((resolve, reject) => {
    img.onload = () => resolve()
    img.onerror = () => reject(new Error('SVG 加载失败'))
    img.crossOrigin = 'anonymous'
  })
  img.src = svgUrl
  await loaded

  const canvas = document.createElement('canvas')
  canvas.width = img.naturalWidth * scale
  canvas.height = img.naturalHeight * scale
  const ctx = canvas.getContext('2d')!
  ctx.scale(scale, scale)
  ctx.drawImage(img, 0, 0)

  return new Promise<Blob>((resolve, reject) => {
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error('PNG 生成失败'))),
      'image/png',
    )
  })
}

export async function svgToJpegBlob(svgUrl: string, scale = 1, quality = 0.85): Promise<Blob> {
  const img = new Image()
  const loaded = new Promise<void>((resolve, reject) => {
    img.onload = () => resolve()
    img.onerror = () => reject(new Error('SVG 加载失败'))
    img.crossOrigin = 'anonymous'
  })
  img.src = svgUrl
  await loaded

  const canvas = document.createElement('canvas')
  canvas.width = img.naturalWidth * scale
  canvas.height = img.naturalHeight * scale
  const ctx = canvas.getContext('2d')!
  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, canvas.width, canvas.height)
  ctx.scale(scale, scale)
  ctx.drawImage(img, 0, 0)

  return new Promise<Blob>((resolve, reject) => {
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error('JPEG 生成失败'))),
      'image/jpeg',
      quality,
    )
  })
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
