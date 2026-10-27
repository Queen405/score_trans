export interface ZoomFitBox {
  x: number
  y: number
  width: number
  height: number
}

export interface ZoomFitTransform {
  scale: number
  tx: number
  ty: number
}

export function calculateZoomFit(
  box: ZoomFitBox,
  viewportWidth: number,
  viewportHeight: number,
  padding = 0,
): ZoomFitTransform | null {
  if (
    ![box.x, box.y, box.width, box.height, viewportWidth, viewportHeight, padding]
      .every(Number.isFinite)
    || box.width <= 0
    || box.height <= 0
    || viewportWidth <= 0
    || viewportHeight <= 0
    || padding < 0
  ) return null
  const x = box.x - padding
  const y = box.y - padding
  const width = box.width + padding * 2
  const height = box.height + padding * 2
  const scale = Math.min(viewportWidth / width, viewportHeight / height, 1)
  return {
    scale,
    tx: (viewportWidth - width * scale) / 2 - x * scale,
    ty: (viewportHeight - height * scale) / 2 - y * scale,
  }
}
