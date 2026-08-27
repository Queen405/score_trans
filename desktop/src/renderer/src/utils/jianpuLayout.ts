export const PUBLICATION_ENGINE_VERSION = 'publication-10'

export function jianpuLayoutKey(
  contentScalePercent: number,
  systemGapPercent: number,
  shortNoteGapPercent: number,
): string {
  return `${contentScalePercent}:${systemGapPercent}:${shortNoteGapPercent}`
}

export function isRenderLayoutStale(renderLayoutKey: string, currentLayoutKey: string): boolean {
  return renderLayoutKey !== currentLayoutKey
}
