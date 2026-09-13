export const PUBLICATION_ENGINE_VERSION = 'publication-15'

export function jianpuLayoutKey(
  contentScalePercent: number,
  systemGapPercent: number,
  shortNoteGapPercent: number,
  beatGapPercent: number,
): string {
  return `${contentScalePercent}:${systemGapPercent}:${shortNoteGapPercent}:${beatGapPercent}`
}

export function isRenderLayoutStale(renderLayoutKey: string, currentLayoutKey: string): boolean {
  return renderLayoutKey !== currentLayoutKey
}
