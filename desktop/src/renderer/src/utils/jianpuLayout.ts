export const PUBLICATION_ENGINE_VERSION = 'publication-16'

export function jianpuLayoutKey(
  contentScalePercent: number,
  systemGapPercent: number,
  shortNoteGapPercent: number,
  beatGapPercent: number,
  breakBeamsAtBeat: boolean,
): string {
  return `${contentScalePercent}:${systemGapPercent}:${shortNoteGapPercent}:${beatGapPercent}:${breakBeamsAtBeat ? 1 : 0}`
}

export function isRenderLayoutStale(renderLayoutKey: string, currentLayoutKey: string): boolean {
  return renderLayoutKey !== currentLayoutKey
}
