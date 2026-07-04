export interface ExportBufferSource {
  buffer: ArrayBuffer
}

export function exportSourceBuffer(source: unknown): Buffer {
  if (
    !source
    || typeof source !== 'object'
    || !('buffer' in source)
    || !(source.buffer instanceof ArrayBuffer)
  ) {
    throw new Error('导出来源必须包含 ArrayBuffer')
  }
  return Buffer.from(source.buffer)
}
