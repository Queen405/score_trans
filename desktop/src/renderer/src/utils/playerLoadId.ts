export interface PlayerLoadSource {
  midiFileId?: string
  musicxmlFileId?: string
  jianpuText?: string
}

/**
 * Build a stable cache key from every source field. Jianpu text must not be
 * truncated: edits beyond an arbitrary prefix still require a MIDI reload.
 */
export function buildPlayerLoadId(source: PlayerLoadSource): string {
  return JSON.stringify([
    source.midiFileId ?? '',
    source.musicxmlFileId ?? '',
    source.jianpuText ?? '',
  ])
}
