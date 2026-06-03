export interface OcrTextBlock {
  id: string
  text: string
  bbox: number[] | null
  role: string
  fontSize?: number
}

export function parseOcrText(payload: string): OcrTextBlock[] {
  if (!payload.trim()) return []
  try {
    const raw = JSON.parse(payload)
    if (!Array.isArray(raw)) return []
    return raw
      .map((item, index) => ({
        id: String(item?.id || `ocr-${index}`),
        text: String(item?.text || ''),
        bbox: Array.isArray(item?.bbox) && item.bbox.length === 4
          ? item.bbox.map((value: unknown) => Number(value))
          : null,
        role: String(item?.role || 'other'),
        fontSize: Number.isFinite(Number(item?.fontSize ?? item?.font_size))
          ? Number(item?.fontSize ?? item?.font_size)
          : undefined,
      }))
      .filter((block) => block.text.trim().length > 0)
  } catch {
    return []
  }
}

export function serializeOcrText(blocks: OcrTextBlock[]): string {
  const clean = blocks
    .map((block, index) => ({
      id: block.id || `ocr-${index}`,
      text: block.text,
      bbox: block.bbox,
      role: block.role || 'other',
      fontSize: block.fontSize,
    }))
    .filter((block) => block.text.trim().length > 0)
  return clean.length ? JSON.stringify(clean) : ''
}

export function splitJianpuAndOcr(text: string): { jianpuText: string; ocrText: string } {
  const jianpuLines: string[] = []
  const blocks: OcrTextBlock[] = []
  text.split(/\r?\n/).forEach((line, index) => {
    const trimmed = line.trim()
    if (!trimmed.startsWith('@text ')) {
      jianpuLines.push(line)
      return
    }
    const match = trimmed.match(/^@text\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(.+)$/)
    if (!match) return
    const [, x1, y1, x2, y2, role, content] = match
    const bbox = [x1, y1, x2, y2].every((value) => value !== '-' && Number.isFinite(Number(value)))
      ? [Number(x1), Number(y1), Number(x2), Number(y2)]
      : null
    blocks.push({
      id: `ocr-${index}-${blocks.length}`,
      text: content,
      bbox,
      role,
      fontSize: bbox ? Number(Math.max(8, (bbox[3] - bbox[1]) * 0.78).toFixed(1)) : undefined,
    })
  })
  return {
    jianpuText: jianpuLines.join('\n').trim(),
    ocrText: serializeOcrText(blocks),
    
  }
}
