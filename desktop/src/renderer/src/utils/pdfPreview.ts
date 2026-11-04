export function pdfPreviewTargetWidth(
  baseWidth: number,
  scale: number,
  devicePixelRatio: number,
): number {
  const dpr = Math.min(3, Math.max(1, devicePixelRatio || 1))
  const requestedWidth = baseWidth * scale * dpr
  return Math.min(16_384, Math.max(64, Math.ceil(requestedWidth / 32) * 32))
}
