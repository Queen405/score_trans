import { apiFetch, fetchFileBlob, type ApiResult } from './client'
import type { ExportMidiRequest, ExportMidiTextRequest, ExportMusicXmlRequest, ExportMusicXmlTextRequest, ExportResponse } from '../models/types'

export const exportApi = {
  async exportMidi(req: ExportMidiRequest): Promise<ApiResult<ExportResponse>> {
    return apiFetch('/export/midi', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    })
  },

  async exportMidiText(req: ExportMidiTextRequest): Promise<ApiResult<ExportResponse>> {
    return apiFetch('/export/midi-text', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    })
  },

  async exportMusicXml(req: ExportMusicXmlRequest): Promise<ApiResult<ExportResponse>> {
    return apiFetch('/export/musicxml', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    })
  },

  async exportMusicXmlText(req: ExportMusicXmlTextRequest): Promise<ApiResult<ExportResponse>> {
    return apiFetch('/export/musicxml-text', {
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
}

export async function svgToPngBlob(svgFileId: string, scale = 1): Promise<Blob> {
  const { image, objectUrl } = await loadFileImage(svgFileId)

  try {
    const canvas = document.createElement('canvas')
    canvas.width = image.naturalWidth * scale
    canvas.height = image.naturalHeight * scale
    const ctx = canvas.getContext('2d')!
    ctx.scale(scale, scale)
    ctx.drawImage(image, 0, 0)

    return await new Promise<Blob>((resolve, reject) => {
      canvas.toBlob(
        (blob) => (blob ? resolve(blob) : reject(new Error('PNG 生成失败'))),
        'image/png',
      )
    })
  } finally {
    URL.revokeObjectURL(objectUrl)
  }
}

export async function svgToJpegBlob(svgFileId: string, scale = 1, quality = 0.85): Promise<Blob> {
  const { image, objectUrl } = await loadFileImage(svgFileId)

  try {
    const canvas = document.createElement('canvas')
    canvas.width = image.naturalWidth * scale
    canvas.height = image.naturalHeight * scale
    const ctx = canvas.getContext('2d')!
    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    ctx.scale(scale, scale)
    ctx.drawImage(image, 0, 0)

    return await new Promise<Blob>((resolve, reject) => {
      canvas.toBlob(
        (blob) => (blob ? resolve(blob) : reject(new Error('JPEG 生成失败'))),
        'image/jpeg',
        quality,
      )
    })
  } finally {
    URL.revokeObjectURL(objectUrl)
  }
}

async function loadFileImage(fileId: string): Promise<{
  image: HTMLImageElement
  objectUrl: string
}> {
  const result = await fetchFileBlob(fileId)
  if (result.error) throw result.error

  const objectUrl = URL.createObjectURL(result.data)
  const image = new Image()
  const loaded = new Promise<void>((resolve, reject) => {
    image.onload = () => resolve()
    image.onerror = () => reject(new Error('SVG 加载失败'))
  })
  image.src = objectUrl
  try {
    await loaded
    return { image, objectUrl }
  } catch (error) {
    URL.revokeObjectURL(objectUrl)
    throw error
  }
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
