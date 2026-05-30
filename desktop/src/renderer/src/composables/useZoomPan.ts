import { ref, type Ref } from 'vue'

export function useZoomPan(container: Ref<HTMLElement | undefined>) {
  const scale = ref(1)
  const tx = ref(0)
  const ty = ref(0)
  const MIN_SCALE = 0.05
  const MAX_SCALE = 10
  const ZOOM_STEP = 0.08

  let isPanning = false
  let startX = 0
  let startY = 0
  let startTx = 0
  let startTy = 0
  let resizeObserver: ResizeObserver | null = null
  let autoFit = true

  function applyTransform() {
    const el = container.value
    if (!el) return
    const target = el.querySelector('.zp-content') as HTMLElement
    if (!target) return
    target.style.transform = `translate(${tx.value}px, ${ty.value}px) scale(${scale.value})`
    target.style.transformOrigin = '0 0'
    target.style.willChange = 'transform'
  }

  function getContentSize(): { w: number; h: number } | null {
    const el = container.value
    if (!el) return null
    const img = el.querySelector('.zp-content img') as HTMLImageElement | null
    if (img && img.naturalWidth && img.naturalHeight) {
      return { w: img.naturalWidth, h: img.naturalHeight }
    }
    const iframe = el.querySelector('.zp-content iframe') as HTMLIFrameElement | null
    if (iframe) {
      return { w: iframe.clientWidth || 800, h: iframe.clientHeight || 600 }
    }
    return null
  }

  function fitToView(): void {
    const el = container.value
    if (!el) return
    const size = getContentSize()
    if (!size) return

    const cw = el.clientWidth
    const ch = el.clientHeight
    if (!cw || !ch) return

    const sx = cw / size.w
    const sy = ch / size.h
    const s = Math.min(sx, sy)

    scale.value = s
    tx.value = (cw - size.w * s) / 2
    ty.value = (ch - size.h * s) / 2
    autoFit = true
    applyTransform()
  }

  function reset(): void {
    fitToView()
  }

  function onWheel(e: WheelEvent) {
    e.preventDefault()

    if (e.ctrlKey || e.metaKey) {
      const delta = e.deltaY > 0 ? -ZOOM_STEP : ZOOM_STEP
      const newScale = Math.max(MIN_SCALE, Math.min(MAX_SCALE, scale.value * (1 + delta)))
      const rect = container.value!.getBoundingClientRect()
      const mx = e.clientX - rect.left
      const my = e.clientY - rect.top
      const ratio = newScale / scale.value
      tx.value = mx - ratio * (mx - tx.value)
      ty.value = my - ratio * (my - ty.value)
      scale.value = newScale
      autoFit = false
    } else if (e.shiftKey) {
      tx.value -= e.deltaY
      autoFit = false
    } else {
      ty.value -= e.deltaY
      tx.value -= e.deltaX
      autoFit = false
    }

    applyTransform()
  }

  function onMouseDown(e: MouseEvent) {
    if (e.button !== 1) return
    e.preventDefault()
    isPanning = true
    startX = e.clientX
    startY = e.clientY
    startTx = tx.value
    startTy = ty.value
    document.body.style.cursor = 'grabbing'
    document.body.style.userSelect = 'none'
  }

  function onMouseMove(e: MouseEvent) {
    if (!isPanning) return
    tx.value = startTx + (e.clientX - startX)
    ty.value = startTy + (e.clientY - startY)
    autoFit = false
    applyTransform()
  }

  function onMouseUp() {
    if (!isPanning) return
    isPanning = false
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
  }

  function onResize() {
    if (autoFit) fitToView()
  }

  function bind() {
    const el = container.value
    if (!el) return
    el.addEventListener('wheel', onWheel, { passive: false })
    el.addEventListener('mousedown', onMouseDown)
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
    resizeObserver = new ResizeObserver(onResize)
    resizeObserver.observe(el)
  }

  function unbind() {
    const el = container.value
    if (el) {
      el.removeEventListener('wheel', onWheel)
      el.removeEventListener('mousedown', onMouseDown)
    }
    window.removeEventListener('mousemove', onMouseMove)
    window.removeEventListener('mouseup', onMouseUp)
    if (resizeObserver) {
      resizeObserver.disconnect()
      resizeObserver = null
    }
  }

  return { scale, tx, ty, reset, fitToView, bind, unbind, applyTransform }
}
