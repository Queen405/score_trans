import { apiFetch, getFileURL, getBaseURL } from './client'
import type { ExportResponse } from '../models/types'

export const exportApi = {
  async exportMidi(musicxmlFileId: string, filename?: string): Promise<ExportResponse> {
    const params = new URLSearchParams({ musicxml_file_id: musicxmlFileId })
    if (filename) params.set('filename', filename)
    return apiFetch(`/export/midi?${params.toString()}`, { method: 'POST' })
  },

  async exportPdf(pngPages: Blob[], filename = 'jianpu.pdf'): Promise<ExportResponse> {
    const form = new FormData()
    form.append('filename', filename)
    for (let i = 0; i < pngPages.length; i++) {
      form.append('files', pngPages[i], `page_${i + 1}.png`)
    }
    return apiFetch('/export/pdf', { method: 'POST', body: form })
  },

  getDownloadURL(fileId: string): string {
    return getFileURL(fileId)
  },
}

export async function svgToPngBlob(svgUrl: string, scale = 2): Promise<Blob> {
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

export function downloadSvg(svgFileId: string, filename = 'jianpu.svg'): void {
  const url = getFileURL(svgFileId)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
