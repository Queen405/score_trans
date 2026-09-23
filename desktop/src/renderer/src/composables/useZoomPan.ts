import { computed, ref, type Ref } from 'vue'

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
  const autoFit = ref(true)
  const fitBase = ref(1)
  let contentW = 0
  let contentH = 0

  function applyTransform() {
    const el = container.value
    if (!el) return
    const inner = el.querySelector<HTMLElement>('.zp-inner')
    if (!inner) return
    inner.style.transform = `translate(${tx.value}px, ${ty.value}px) scale(${scale.value})`
    inner.style.transformOrigin = '0 0'
  }

  function measureContent(): boolean {
    const el = container.value
    if (!el) return false
    const img = el.querySelector<HTMLImageElement>('.zp-inner img')
    if (img && img.naturalWidth > 0 && img.naturalHeight > 0) {
      contentW = img.naturalWidth
      contentH = img.naturalHeight
      return true
    }
    const iframe = el.querySelector<HTMLIFrameElement>('.zp-inner iframe')
    if (iframe) {
      contentW = iframe.clientWidth || 800
      contentH = iframe.clientHeight || 600
      return true
    }
    const svg = el.querySelector<SVGSVGElement>('.zp-inner svg')
    if (svg) {
      const viewBox = svg.viewBox.baseVal
      contentW = svg.width.baseVal.value || viewBox.width || 800
      contentH = svg.height.baseVal.value || viewBox.height || 600
      return true
    }
    return false
  }

  function fitToView(): void {
    const el = container.value
    if (!el) return
    if (!measureContent()) return

    const cw = el.clientWidth
    const ch = el.clientHeight
    if (cw <= 0 || ch <= 0) return

    const sx = cw / contentW
    const sy = ch / contentH
    const s = Math.min(sx, sy, 1)

    const renderedW = contentW * s
    const renderedH = contentH * s
    scale.value = s
    fitBase.value = s
    tx.value = (cw - renderedW) / 2
    ty.value = (ch - renderedH) / 2
    autoFit.value = true
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
      autoFit.value = false
    } else if (e.shiftKey) {
      tx.value -= e.deltaY
      autoFit.value = false
    } else {
      ty.value -= e.deltaY
      tx.value -= e.deltaX
      autoFit.value = false
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
    autoFit.value = false
    applyTransform()
  }

  function onMouseUp() {
    if (!isPanning) return
    isPanning = false
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
  }

  function onResize() {
    fitToView()
  }

  function setAutoFit(value: boolean): void {
    autoFit.value = value
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

  const displayPercent = computed(() =>
    autoFit.value ? '100%' : `${Math.round(scale.value / (fitBase.value || 1) * 100)}%`,
  )

  return { scale, tx, ty, reset, fitToView, bind, unbind, applyTransform, setAutoFit, displayPercent }
}
