import { ref, onMounted, onUnmounted, type Ref } from 'vue'

export function useZoomPan(container: Ref<HTMLElement | undefined>) {
  const scale = ref(1)
  const tx = ref(0)
  const ty = ref(0)
  const MIN_SCALE = 0.1
  const MAX_SCALE = 10
  const ZOOM_STEP = 0.1

  let isPanning = false
  let startX = 0
  let startY = 0
  let startTx = 0
  let startTy = 0

  function applyTransform() {
    const el = container.value
    if (!el) return
    const target = el.querySelector('.zp-content') as HTMLElement
    if (!target) return
    target.style.transform = `translate(${tx.value}px, ${ty.value}px) scale(${scale.value})`
    target.style.transformOrigin = '0 0'
    target.style.willChange = 'transform'
  }

  function onWheel(e: WheelEvent) {
    e.preventDefault()

    if (e.ctrlKey || e.metaKey) {
      const delta = e.deltaY > 0 ? -ZOOM_STEP : ZOOM_STEP
      const newScale = Math.max(MIN_SCALE, Math.min(MAX_SCALE, scale.value + delta))
      const rect = container.value!.getBoundingClientRect()
      const mx = e.clientX - rect.left
      const my = e.clientY - rect.top
      const ratio = newScale / scale.value
      tx.value = mx - ratio * (mx - tx.value)
      ty.value = my - ratio * (my - ty.value)
      scale.value = newScale
    } else if (e.shiftKey) {
      tx.value -= e.deltaY
    } else {
      ty.value -= e.deltaY
      tx.value -= e.deltaX
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
    applyTransform()
  }

  function onMouseUp() {
    if (!isPanning) return
    isPanning = false
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
  }

  function reset() {
    scale.value = 1
    tx.value = 0
    ty.value = 0
    applyTransform()
  }

  function bind() {
    const el = container.value
    if (!el) return
    el.addEventListener('wheel', onWheel, { passive: false })
    el.addEventListener('mousedown', onMouseDown)
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
  }

  function unbind() {
    const el = container.value
    if (!el) return
    el.removeEventListener('wheel', onWheel)
    el.removeEventListener('mousedown', onMouseDown)
    window.removeEventListener('mousemove', onMouseMove)
    window.removeEventListener('mouseup', onMouseUp)
  }

  return { scale, tx, ty, reset, bind, unbind, applyTransform }
}
