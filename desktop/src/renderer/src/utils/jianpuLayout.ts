export const PUBLICATION_ENGINE_VERSION = 'publication-22'

export function jianpuLayoutKey(
  contentScalePercent: number,
  systemGapPercent: number,
  shortNoteGapPercent: number,
  beatGapPercent: number,
  breakBeamsAtBeat: boolean,
  measuresPerSystem: 0 | 3 | 4 | 5,
): string {
  return `${contentScalePercent}:${systemGapPercent}:${shortNoteGapPercent}:${beatGapPercent}:${breakBeamsAtBeat ? 1 : 0}:${measuresPerSystem || 'a'}`
}

export function isRenderLayoutStale(renderLayoutKey: string, currentLayoutKey: string): boolean {
  return renderLayoutKey !== currentLayoutKey
}
