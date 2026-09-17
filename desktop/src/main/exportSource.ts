import { t } from './locale'

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
    throw new Error(t('export.sourceArrayBuffer'))
  }
  return Buffer.from(source.buffer)
}
