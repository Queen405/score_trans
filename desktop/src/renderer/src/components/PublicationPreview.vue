<template>
  <div
    v-if="svgUrl"
    class="svg-preview"
  >
    <div
      ref="containerRef"
      class="preview-viewport"
      @dblclick="addBlockAtCursor"
    >
      <div class="zp-inner">
        <div
          v-if="svgReady"
          :key="svgUrl"
          ref="svgHostRef"
          class="svg-inline"
        />
        <div
          v-else-if="svgError"
          class="svg-loading svg-error"
        >
          {{ svgError }}
        </div>
        <div
          v-else
          class="svg-loading"
        >
          加载中...
        </div>
        <template v-if="showOcrOverlay">
          <button
            v-for="block in ocrBlocks"
            :key="block.id"
            :class="['ocr-edit-block', { selected: selectedId === block.id }]"
            :style="ocrBlockStyle(block)"
            type="button"
            @mousedown.stop="startDrag(block, $event)"
            @dblclick.stop="startEditing(block)"
            @click.stop="selectBlock(block.id)"
          >
            <input
              v-if="editingId === block.id"
              v-model="editingText"
              class="ocr-edit-input"
              @mousedown.stop
              @click.stop
              @keydown.enter.prevent="commitEditing"
              @keydown.esc.prevent="cancelEditing"
              @blur="commitEditing"
            >
            <span v-else>{{ block.text }}</span>
            <span
              v-if="editableOcr && selectedId === block.id && editingId !== block.id"
              class="ocr-resize-handle"
              @mousedown.stop.prevent="startResize(block, $event)"
            />
          </button>
        </template>
      </div>
    </div>
    <div class="zoom-bar">
      <span class="zoom-label">{{ Math.round(zp.scale.value * 100) }}%</span>
      <button
        class="zoom-btn"
        title="适应窗口"
        @click="zp.reset()"
      >
        适应
      </button>
      <button
        :class="['zoom-btn', { active: showOcrOverlay }]"
        :title="showOcrOverlay ? '隐藏 OCR 文字叠加' : '显示 OCR 文字叠加'"
        @click="showOcrOverlay = !showOcrOverlay"
      >
        OCR叠加
      </button>
    </div>
  </div>
  <div
    v-else
    class="svg-empty"
  >
    <n-icon
      size="32"
      :depth="3"
    >
      <ImageOutline />
    </n-icon>
    <span>暂无 SVG</span>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch, nextTick } from 'vue'
import type { CSSProperties } from 'vue'
import { fetchFileBlob } from '../api/client'
import { ImageOutline } from '@vicons/ionicons5'
import { NIcon } from 'naive-ui'
import { useZoomPan } from '../composables/useZoomPan'
import { loadViewState, saveViewState } from '../composables/useViewPersistence'
import { useSettingsStore } from '../stores/settings'
import { parseOcrText, serializeOcrText, type OcrTextBlock } from '../utils/ocrText'
import { sanitizeSvg } from '../utils/svgSanitizer'
import { LatestAsyncGate } from '../utils/latestAsyncGate'

const props = withDefaults(defineProps<{
  svgFileId: string
  ocrText?: string
  editableOcr?: boolean
  currentNoteIndex?: number
  playbackGroupIndex?: number
}>(), {
  ocrText: '',
  editableOcr: false,
  currentNoteIndex: -1,
  playbackGroupIndex: -1,
})
interface TextAttachmentUpdate {
  sourcePageIndex: number
  sourceAttachmentId: string
  text?: string
  fontSize?: number
  offsetX?: number
  offsetY?: number
  deleted?: boolean
}
const emit = defineEmits<{
  'update:ocrText': [value: string]
  'update:textAttachment': [value: TextAttachmentUpdate]
}>()
const svgUrl = computed(() => props.svgFileId)

const containerRef = ref<HTMLElement>()
const svgHostRef = ref<HTMLElement>()
const zp = useZoomPan(containerRef)
const imgW = ref(0)
const imgH = ref(0)
const svgReady = ref(false)
const svgError = ref('')
const selectedId = ref('')
const editingId = ref('')
const editingText = ref('')
const ocrBlocks = ref<OcrTextBlock[]>([])
const settings = useSettingsStore()
const showOcrOverlay = ref(settings.showOcrOverlay)
let svgLoadGeneration = 0
const svgLoadGate = new LatestAsyncGate()
let svgLoadController: AbortController | null = null
let dragging: {
  id: string
  startClientX: number
  startClientY: number
  startBbox: number[]
  startOffsetX: number
  startOffsetY: number
} | null = null
let resizing: {
  id: string
  startClientX: number
  startClientY: number
  startBbox: number[]
} | null = null
function selectBlock(id: string): void {
  selectedId.value = id
}

function ocrBlockStyle(block: OcrTextBlock): CSSProperties {
  const bbox = block.bbox ?? [12, 12, 120, 36]
  const [x1, y1, x2, y2] = scaleBBoxToImage(bbox)
  const fontSize = block.fontSize ?? Math.max(10, (y2 - y1) * 0.78)
  return {
    left: `${x1}px`,
    top: `${y1}px`,
    width: `${Math.max(24, x2 - x1)}px`,
    height: `${Math.max(18, y2 - y1)}px`,
    fontSize: `${fontSize}px`,
    cursor: props.editableOcr ? 'move' : 'default',
    pointerEvents: props.editableOcr ? 'auto' : 'none',
  }
}

function scaleBBoxToImage(bbox: number[]): number[] {
  if (Math.max(...bbox.map((value) => Math.abs(value))) <= 1.5) {
    return [bbox[0] * imgW.value, bbox[1] * imgH.value, bbox[2] * imgW.value, bbox[3] * imgH.value]
  }
  return bbox
}

function normalizeBBoxFromImage(bbox: number[]): number[] {
  return bbox.map((value) => Number(value.toFixed(3)))
}

function eventToImagePoint(event: MouseEvent): { x: number; y: number } | null {
  const el = containerRef.value
  if (!el) return null
  const rect = el.getBoundingClientRect()
  return {
    x: (event.clientX - rect.left - zp.tx.value) / zp.scale.value,
    y: (event.clientY - rect.top - zp.ty.value) / zp.scale.value,
  }
}

function addBlockAtCursor(event: MouseEvent): void {
  if (!props.editableOcr || editingId.value) return
  const point = eventToImagePoint(event)
  if (!point) return
  const width = 120
  const height = 28
  const id = `ocr-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`
  const block: OcrTextBlock = {
    id,
    text: '',
    bbox: normalizeBBoxFromImage([point.x, point.y, point.x + width, point.y + height]),
    role: 'other',
    fontSize: Number((height * 0.78).toFixed(1)),
  }
  ocrBlocks.value = [...ocrBlocks.value, block]
  selectedId.value = id
  editingId.value = id
  editingText.value = ''
  nextTick(() => {
    containerRef.value?.querySelector<HTMLInputElement>('.ocr-edit-input')?.focus()
  })
}

function startDrag(block: OcrTextBlock, event: MouseEvent): void {
  if (!props.editableOcr || editingId.value) return
  const bbox = scaleBBoxToImage(block.bbox ?? [12, 12, 120, 36])
  dragging = {
    id: block.id,
    startClientX: event.clientX,
    startClientY: event.clientY,
    startBbox: bbox,
    startOffsetX: block.anchor?.offset_x ?? 0,
    startOffsetY: block.anchor?.offset_y ?? 0,
  }
  selectedId.value = block.id
  document.body.style.userSelect = 'none'
}

function startResize(block: OcrTextBlock, event: MouseEvent): void {
  if (!props.editableOcr || editingId.value) return
  const bbox = scaleBBoxToImage(block.bbox ?? [12, 12, 120, 36])
  resizing = {
    id: block.id,
    startClientX: event.clientX,
    startClientY: event.clientY,
    startBbox: bbox,
  }
  selectedId.value = block.id
  document.body.style.userSelect = 'none'
}

function onDragMove(event: MouseEvent): void {
  if (resizing) {
    const dx = (event.clientX - resizing.startClientX) / zp.scale.value
    const dy = (event.clientY - resizing.startClientY) / zp.scale.value
    const minW = 24
    const minH = 18
    updateBlock(resizing.id, {
      bbox: normalizeBBoxFromImage([
        resizing.startBbox[0],
        resizing.startBbox[1],
        Math.max(resizing.startBbox[0] + minW, resizing.startBbox[2] + dx),
        Math.max(resizing.startBbox[1] + minH, resizing.startBbox[3] + dy),
      ]),
      fontSize: Number((Math.max(minH, resizing.startBbox[3] + dy - resizing.startBbox[1]) * 0.78).toFixed(1)),
    }, false)
    return
  }
  if (!dragging) return
  const dx = (event.clientX - dragging.startClientX) / zp.scale.value
  const dy = (event.clientY - dragging.startClientY) / zp.scale.value
  updateBlock(dragging.id, {
    bbox: normalizeBBoxFromImage([
      dragging.startBbox[0] + dx,
      dragging.startBbox[1] + dy,
      dragging.startBbox[2] + dx,
      dragging.startBbox[3] + dy,
    ]),
  }, false)
}

function endDrag(): void {
  if (!dragging && !resizing) return
  const activeDrag = dragging
  const activeResize = resizing
  if (activeDrag) {
    const block = ocrBlocks.value.find((item) => item.id === activeDrag.id)
    if (block?.bbox) {
      emitTextAttachmentUpdate(block, {
        offsetX: activeDrag.startOffsetX + block.bbox[0] - activeDrag.startBbox[0],
        offsetY: activeDrag.startOffsetY + block.bbox[1] - activeDrag.startBbox[1],
      })
    }
  } else if (activeResize) {
    const block = ocrBlocks.value.find((item) => item.id === activeResize.id)
    if (block?.fontSize !== undefined) {
      emitTextAttachmentUpdate(block, { fontSize: block.fontSize })
    }
  }
  dragging = null
  resizing = null
  document.body.style.userSelect = ''
  emitOcr()
}

function startEditing(block: OcrTextBlock): void {
  if (!props.editableOcr) return
  selectedId.value = block.id
  editingId.value = block.id
  editingText.value = block.text
  nextTick(() => {
    containerRef.value?.querySelector<HTMLInputElement>('.ocr-edit-input')?.focus()
  })
}

function commitEditing(): void {
  if (!editingId.value) return
  const text = editingText.value.trim()
  if (!text) {
    removeBlock(editingId.value)
  } else {
    updateBlock(editingId.value, { text }, true)
    const block = ocrBlocks.value.find((item) => item.id === editingId.value)
    if (block) emitTextAttachmentUpdate(block, { text })
  }
  editingId.value = ''
  editingText.value = ''
}

function cancelEditing(): void {
  editingId.value = ''
  editingText.value = ''
}

function updateBlock(id: string, patch: Partial<OcrTextBlock>, emitNow: boolean): void {
  ocrBlocks.value = ocrBlocks.value.map((block) => (block.id === id ? { ...block, ...patch } : block))
  if (emitNow) emitOcr()
}

function removeBlock(id: string): void {
  const removed = ocrBlocks.value.find((block) => block.id === id)
  ocrBlocks.value = ocrBlocks.value.filter((block) => block.id !== id)
  if (selectedId.value === id) selectedId.value = ''
  if (removed) emitTextAttachmentUpdate(removed, { deleted: true })
  emitOcr()
}

function emitTextAttachmentUpdate(
  block: OcrTextBlock,
  patch: Omit<TextAttachmentUpdate, 'sourcePageIndex' | 'sourceAttachmentId'>,
): void {
  if (block.sourcePageIndex === undefined || !block.sourceAttachmentId) return
  emit('update:textAttachment', {
    sourcePageIndex: block.sourcePageIndex,
    sourceAttachmentId: block.sourceAttachmentId,
    ...patch,
  })
}

function emitOcr(): void {
  emit('update:ocrText', serializeOcrText(ocrBlocks.value))
}

function onKeyDown(event: KeyboardEvent): void {
  if (!props.editableOcr || editingId.value || !selectedId.value) return
  if (event.key !== 'Delete' && event.key !== 'Backspace') return
  event.preventDefault()
  removeBlock(selectedId.value)
}

async function loadSvg(url: string): Promise<void> {
  const generation = ++svgLoadGeneration
  svgLoadController?.abort()
  svgLoadController = null
  svgReady.value = false
  svgError.value = ''
  imgW.value = 0
  imgH.value = 0
  clearPlaybackHighlight()
  zp.unbind()

  if (!url) return

  const controller = new AbortController()
  svgLoadController = controller
  const timeout = window.setTimeout(() => controller.abort(), 15000)
  try {
    const result = await fetchFileBlob(url, controller.signal)
    if (result.error) throw result.error
    const text = await result.data.text()
    if (generation !== svgLoadGeneration) return
    const safeSvg = sanitizeSvg(text)

    const size = readSvgSize(safeSvg)
    imgW.value = size.width
    imgH.value = size.height
    svgReady.value = true

    await nextTick()
    const mountedSvg = document.importNode(safeSvg, true)
    svgHostRef.value?.replaceChildren(mountedSvg)
    zp.bind()
    const savedView = loadViewState(url)
    requestAnimationFrame(() => {
      if (savedView) {
        zp.scale.value = savedView.scale
        zp.tx.value = savedView.tx
        zp.ty.value = savedView.ty
        zp.applyTransform()
        zp.setAutoFit(false)
      } else {
        zp.fitToView()
      }
      applyPlaybackHighlight(false)
    })
  } catch {
    if (generation !== svgLoadGeneration) return
    svgReady.value = false
    svgError.value = 'SVG 加载失败'
  } finally {
    window.clearTimeout(timeout)
    if (svgLoadController === controller) svgLoadController = null
  }
}

function readSvgSize(svg: SVGSVGElement): { width: number; height: number } {
  const viewBox = (svg.getAttribute('viewBox') || '').split(/\s+/).map(Number)
  const viewBoxWidth = viewBox.length === 4 && Number.isFinite(viewBox[2]) ? viewBox[2] : 0
  const viewBoxHeight = viewBox.length === 4 && Number.isFinite(viewBox[3]) ? viewBox[3] : 0
  return {
    width: parseSvgLength(svg.getAttribute('width')) || viewBoxWidth || 800,
    height: parseSvgLength(svg.getAttribute('height')) || viewBoxHeight || 600,
  }
}

function parseSvgLength(value: string | null): number {
  if (!value) return 0
  const match = value.match(/^-?\d+(?:\.\d+)?/)
  return match ? Number(match[0]) : 0
}

function svgRoot(): SVGSVGElement | null {
  return containerRef.value?.querySelector<SVGSVGElement>('.zp-inner svg') ?? null
}

function clearPlaybackHighlight(): void {
  svgRoot()?.querySelectorAll('.playback-current, .playback-group-highlight').forEach((node) => {
    node.classList.remove('playback-current')
    if (node.classList.contains('playback-group-highlight')) node.remove()
  })
}

async function highlightSource(sourceId: string): Promise<boolean> {
  if (!(await svgLoadGate.waitForLatest())) return false
  await nextTick()
  if (!(await svgLoadGate.waitForLatest())) return false
  const svg = svgRoot()
  if (!svg || !sourceId) return false

  svg.querySelectorAll('.source-current').forEach((node) => {
    node.classList.remove('source-current')
  })

  const semanticTargets = Array.from(
    svg.querySelectorAll<SVGGraphicsElement>('[data-source-role]'),
  ).filter((element) => sourceIdsOf(element).includes(sourceId))
  const targets = semanticTargets.length
    ? semanticTargets
    : Array.from(svg.querySelectorAll<SVGGraphicsElement>('.source-anchor'))
      .filter((element) => sourceIdsOf(element).includes(sourceId))
  if (!targets.length) return false

  targets.forEach((target) => {
    target.classList.add('source-current')
  })
  keepTargetVisible(targets[0]!)
  flashTargets(targets)
  return true
}

function sourceIdsOf(element: SVGGraphicsElement): string[] {
  return (element.getAttribute('data-source-ids') ?? '').split(/\s+/).filter(Boolean)
}

function rootCoordinateBBox(
  target: SVGGraphicsElement,
  svg: SVGSVGElement,
): { x: number; y: number; width: number; height: number } | null {
  try {
    const box = target.getBBox()
    const targetMatrix = target.getScreenCTM()
    const svgMatrix = svg.getScreenCTM()
    if (!targetMatrix || !svgMatrix) return null
    const matrix = svgMatrix.inverse().multiply(targetMatrix)
    const points = [
      new globalThis.DOMPoint(box.x, box.y),
      new globalThis.DOMPoint(box.x + box.width, box.y),
      new globalThis.DOMPoint(box.x, box.y + box.height),
      new globalThis.DOMPoint(box.x + box.width, box.y + box.height),
    ].map((point) => point.matrixTransform(matrix))
    const xs = points.map((point) => point.x)
    const ys = points.map((point) => point.y)
    const x = Math.min(...xs)
    const y = Math.min(...ys)
    return {
      x,
      y,
      width: Math.max(...xs) - x,
      height: Math.max(...ys) - y,
    }
  } catch {
    return null
  }
}

defineExpose({ highlightSource })

function applyPlaybackHighlight(reveal: boolean): void {
  const svg = svgRoot()
  if (!svg) return
  svg.querySelectorAll('.playback-current, .playback-group-highlight').forEach((node) => {
    node.classList.remove('playback-current')
    if (node.classList.contains('playback-group-highlight')) node.remove()
  })
  const playbackIndex = props.playbackGroupIndex >= 0 ? props.playbackGroupIndex : props.currentNoteIndex
  if (playbackIndex < 0) return
  let targets = Array.from(svg.querySelectorAll<SVGGElement>(
    `.playback-note[data-note-group="${playbackIndex}"]`,
  ))
  if (!targets.length) {
    const fallback = svg.querySelector<SVGGElement>(
      `.playback-note[data-note-index="${props.currentNoteIndex}"]`,
    )
    targets = fallback ? [fallback] : []
  }
  if (!targets.length) return
  targets.forEach((target) => target.classList.add('playback-current'))
  const boxes = targets.map((target) => targetBBox(target, svg)).filter(
    (box): box is { x: number; y: number; width: number; height: number } => box !== null,
  )
  if (!boxes.length) return
  // Make one tight rectangle per staff row. Never union the vertical gap between parts.
  const rows: Array<{ boxes: typeof boxes }> = []
  for (const box of boxes) {
    const row = rows.find((candidate) => candidate.boxes.some((other) =>
      Math.min(box.y + box.height, other.y + other.height) - Math.max(box.y, other.y) > 0,
    ))
    if (row) row.boxes.push(box)
    else rows.push({ boxes: [box] })
  }
  for (const row of rows) {
    const left = Math.min(...row.boxes.map((box) => box.x)) - 3
    const top = Math.min(...row.boxes.map((box) => box.y)) - 3
    const right = Math.max(...row.boxes.map((box) => box.x + box.width)) + 3
    const bottom = Math.max(...row.boxes.map((box) => box.y + box.height)) + 3
    const frame = document.createElementNS('http://www.w3.org/2000/svg', 'rect')
    frame.setAttribute('class', 'playback-group-highlight')
    frame.setAttribute('x', String(left))
    frame.setAttribute('y', String(top))
    frame.setAttribute('width', String(Math.max(1, right - left)))
    frame.setAttribute('height', String(Math.max(1, bottom - top)))
    svg.appendChild(frame)
  }
  if (reveal) keepTargetVisible(targets[0]!)
}
function keepTargetVisible(target: SVGGraphicsElement): void {
  const viewport = containerRef.value
  const svg = svgRoot()
  if (!viewport || !svg) return
  const box = rootCoordinateBBox(target, svg)
  if (!box) return

  const margin = 32
  const scale = zp.scale.value
  const vw = viewport.clientWidth
  const vh = viewport.clientHeight
  const left = zp.tx.value + box.x * scale
  const right = zp.tx.value + (box.x + box.width) * scale
  const top = zp.ty.value + box.y * scale
  const bottom = zp.ty.value + (box.y + box.height) * scale
  const targetW = right - left
  const targetH = bottom - top
  const availW = vw - 2 * margin
  const availH = vh - 2 * margin

  if (targetW <= availW) {
    if (left < margin) {
      zp.tx.value += margin - left
    } else if (right > vw - margin) {
      zp.tx.value -= right - (vw - margin)
    }
  } else {
    zp.tx.value += (vw - targetW) / 2 - left
  }

  if (targetH <= availH) {
    if (top < margin) {
      zp.ty.value += margin - top
    } else if (bottom > vh - margin) {
      zp.ty.value -= bottom - (vh - margin)
    }
  } else {
    zp.ty.value += (vh - targetH) / 2 - top
  }

  zp.applyTransform()
}

function flashTargets(targets: SVGGraphicsElement[]): void {
  const svg = svgRoot()
  if (!svg || !targets.length) return
  const boxes = targets
    .map((target) => targetBBox(target, svg))
    .filter((box): box is { x: number; y: number; width: number; height: number } => !!box)
  if (!boxes.length) return
  const minX = Math.min(...boxes.map((box) => box.x))
  const minY = Math.min(...boxes.map((box) => box.y))
  const maxX = Math.max(...boxes.map((box) => box.x + box.width))
  const maxY = Math.max(...boxes.map((box) => box.y + box.height))
  const pad = 1
  svg.querySelectorAll('.source-flash-overlay').forEach((node) => node.remove())
  const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect')
  rect.setAttribute('class', 'source-flash-overlay')
  rect.setAttribute('x', String(minX - pad))
  rect.setAttribute('y', String(minY - pad))
  rect.setAttribute('width', String(maxX - minX + pad * 2))
  rect.setAttribute('height', String(maxY - minY + pad * 2))
  svg.appendChild(rect)
  const cleanup = () => rect.remove()
  rect.addEventListener('animationend', cleanup, { once: true })
  setTimeout(cleanup, 1300)
}

function targetBBox(
  target: SVGGraphicsElement,
  svg: SVGSVGElement,
): { x: number; y: number; width: number; height: number } | null {
  const raw = target.getAttribute('data-bbox')
  if (raw) {
    const parts = raw.split(/\s+/).map(Number)
    if (parts.length === 4 && parts.every((value) => Number.isFinite(value))) {
      return { x: parts[0]!, y: parts[1]!, width: parts[2]!, height: parts[3]! }
    }
  }
  return rootCoordinateBBox(target, svg)
}

watch(svgUrl, (url, prevUrl) => {
  if (prevUrl && svgReady.value) {
    saveViewState(prevUrl, {
      scale: zp.scale.value,
      tx: zp.tx.value,
      ty: zp.ty.value,
    })
  }
  showOcrOverlay.value = settings.showOcrOverlay
  svgLoadGate.track(loadSvg(url))
}, { immediate: true })

watch(() => props.currentNoteIndex, () => {
  nextTick(() => applyPlaybackHighlight(true))
})

// Page navigation can change the SVG while the playback group index stays the
// same. Re-apply the current group after the new SVG is mounted.
watch([svgUrl, svgReady], () => {
  if (!svgReady.value) return
  nextTick(() => applyPlaybackHighlight(false))
})

watch(() => props.ocrText, (value) => {
  ocrBlocks.value = parseOcrText(value || '')
}, { immediate: true })

onMounted(() => {
  if (svgReady.value) {
    zp.unbind()
    zp.bind()
    requestAnimationFrame(() => {
      zp.fitToView()
      applyPlaybackHighlight(false)
    })
  }
  window.addEventListener('mousemove', onDragMove)
  window.addEventListener('mouseup', endDrag)
  window.addEventListener('keydown', onKeyDown)
})
onUnmounted(() => {
  if (svgUrl.value && svgReady.value) {
    saveViewState(svgUrl.value, {
      scale: zp.scale.value,
      tx: zp.tx.value,
      ty: zp.ty.value,
    })
  }
  svgLoadGeneration += 1
  svgLoadController?.abort()
  svgLoadController = null
  svgLoadGate.dispose()
  zp.unbind()
  window.removeEventListener('mousemove', onDragMove)
  window.removeEventListener('mouseup', endDrag)
  window.removeEventListener('keydown', onKeyDown)
})
</script>

<style scoped>
.svg-preview {
  flex: 1;
  min-height: 0;
  display: flex;
  position: relative;
}

.preview-viewport {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  border-radius: var(--radius-sm);
  background: var(--bg-surface);
  cursor: default;
  position: relative;
}

.zp-inner {
  position: absolute;
  top: 0;
  left: 0;
  display: inline-block;
}

.svg-inline,
.svg-inline :deep(svg) {
  display: block;
}

.svg-inline :deep(svg) {
  max-width: none;
  max-height: none;
}

.svg-inline :deep(.playback-group-highlight) {
  fill: rgba(224, 82, 82, 0.08);
  stroke: #e05252;
  stroke-width: 2;
  rx: 3;
  pointer-events: none;
}

.svg-inline :deep(.playback-note.playback-current .note),
.svg-inline :deep(.source-anchor.source-current .note),
.svg-inline :deep(.playback-note.playback-current .accidental),
.svg-inline :deep(.source-anchor.source-current .accidental),
.svg-inline :deep(.playback-note.playback-current .dynamic),
.svg-inline :deep(.source-anchor.source-current .dynamic),
.svg-inline :deep(.playback-note.playback-current .ornament),
.svg-inline :deep(.source-anchor.source-current .ornament),
.svg-inline :deep(.playback-note.playback-current .technical),
.svg-inline :deep(.source-anchor.source-current .technical),
.svg-inline :deep(.playback-note.playback-current .technique-mark),
.svg-inline :deep(.source-anchor.source-current .technique-mark),
.svg-inline :deep(.playback-note.playback-current .performance-mark-fill),
.svg-inline :deep(.source-anchor.source-current .performance-mark-fill),
.svg-inline :deep(.playback-note.playback-current .lyric),
.svg-inline :deep(.source-anchor.source-current .lyric) {
  fill: #d97706;
}

.svg-inline :deep([data-source-role].source-current path),
.svg-inline :deep([data-source-role].source-current text) {
  fill: #d97706;
}

.svg-inline :deep(line[data-source-role].source-current),
.svg-inline :deep(path[data-source-role].source-current) {
  stroke: #d97706;
}

.svg-inline :deep(.playback-note.playback-current .performance-mark-stroke),
.svg-inline :deep(.source-anchor.source-current .performance-mark-stroke) {
  stroke: #d97706;
}

.svg-inline :deep(.playback-note.playback-current .duration-line),
.svg-inline :deep(.source-anchor.source-current .duration-line),
.svg-inline :deep(.playback-note.playback-current .extension-line),
.svg-inline :deep(.source-anchor.source-current .extension-line),
.svg-inline :deep(.playback-note.playback-current .tie),
.svg-inline :deep(.source-anchor.source-current .tie),
.svg-inline :deep(.playback-note.playback-current .slur),
.svg-inline :deep(.source-anchor.source-current .slur),
.svg-inline :deep(.playback-note.playback-current .articulation),
.svg-inline :deep(.source-anchor.source-current .articulation) {
  stroke: #d97706;
}

.svg-inline :deep(.playback-note.playback-current .octave-dot),
.svg-inline :deep(.source-anchor.source-current .octave-dot),
.svg-inline :deep(.playback-note.playback-current .rhythm-dot),
.svg-inline :deep(.source-anchor.source-current .rhythm-dot),
.svg-inline :deep(.playback-note.playback-current .staccato),
.svg-inline :deep(.source-anchor.source-current .staccato) {
  fill: #d97706;
}

.svg-inline :deep(.source-flash-overlay) {
  fill: rgba(217, 119, 6, 0.22);
  stroke: #d97706;
  stroke-width: 1.5;
  vector-effect: non-scaling-stroke;
  pointer-events: none;
  animation: source-flash 1.2s ease-out forwards;
}

@keyframes source-flash {
  0% { opacity: 0; }
  10% { opacity: 1; }
  40% { opacity: 0; }
  55% { opacity: 1; }
  85% { opacity: 0; }
  100% { opacity: 0; }
}

.svg-loading {
  width: 160px;
  height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-tertiary);
  font-size: 12px;
}

.svg-error {
  color: var(--danger, #ef4444);
}

.ocr-edit-block {
  position: absolute;
  z-index: 3;
  border: 1px solid transparent;
  background: transparent;
  color: #111827;
  font-family: "Microsoft YaHei", SimSun, Arial, sans-serif;
  text-align: left;
  padding: 0 2px;
  line-height: 1;
  overflow: visible;
  white-space: nowrap;
}

.ocr-edit-block:hover,
.ocr-edit-block.selected {
  border-color: var(--accent);
  background: rgba(255, 255, 255, 0.68);
}

.ocr-edit-input {
  width: 100%;
  min-width: 80px;
  height: 100%;
  border: 0;
  outline: 1px solid var(--accent);
  background: #fff;
  color: #111827;
  font: inherit;
  padding: 0 2px;
}

.ocr-resize-handle {
  position: absolute;
  right: -5px;
  bottom: -5px;
  width: 10px;
  height: 10px;
  border-radius: 2px;
  border: 1px solid var(--accent);
  background: #fff;
  cursor: nwse-resize;
}

.svg-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--text-tertiary);
  font-size: 13px;
}

.zoom-bar {
  position: absolute;
  bottom: 8px;
  right: 8px;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 3px 6px;
  border-radius: 6px;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.08);
  z-index: 5;
}

.zoom-label {
  font-size: 11px;
  color: var(--text-tertiary);
  min-width: 32px;
  text-align: center;
  font-variant-numeric: tabular-nums;
}

.zoom-btn {
  border: 0;
  background: transparent;
  color: var(--text-secondary);
  font-size: 11px;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
}

.zoom-btn:hover {
  background: var(--accent-light);
  color: var(--accent);
}

.zoom-btn.active {
  background: var(--accent-light);
  color: var(--accent);
}
</style>
