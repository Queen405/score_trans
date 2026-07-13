import { apiFetch, type ApiResult } from './client'
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

  async exportRenderedPdf(svgFileIds: string[], filename = 'jianpu.pdf'): Promise<ApiResult<ExportResponse>> {
    return apiFetch('/export/rendered-pdf', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ svg_file_ids: svgFileIds, filename }),
    })
  },

  async exportRenderedImages(
    svgFileIds: string[],
    filename = 'jianpu',
    dpi: 150 | 300 | 600 = 300,
    format: 'png' | 'jpeg' = 'png',
  ): Promise<ApiResult<{ files: ExportResponse[] }>> {
    return apiFetch('/export/rendered-images', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ svg_file_ids: svgFileIds, filename, dpi, format }),
    })
  },
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
