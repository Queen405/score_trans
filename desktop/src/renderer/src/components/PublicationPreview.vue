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
          :class="['svg-inline', { 'hide-static-ocr': shouldHideStaticOcr }]"
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
import { fetchFileBlob } from '../api/client'
import { ImageOutline } from '@vicons/ionicons5'
import { NIcon } from 'naive-ui'
import { useZoomPan } from '../composables/useZoomPan'
import { parseOcrText, serializeOcrText, type OcrTextBlock } from '../utils/ocrText'
import { sanitizeSvg } from '../utils/svgSanitizer'

const props = withDefaults(defineProps<{
  svgFileId: string
  ocrText?: string
  editableOcr?: boolean
  currentNoteIndex?: number
}>(), {
  ocrText: '',
  editableOcr: false,
  currentNoteIndex: -1,
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
const shouldHideStaticOcr = computed(() => props.editableOcr)
const showOcrOverlay = ref(true)
let svgLoadGeneration = 0
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

function ocrBlockStyle(block: OcrTextBlock) {
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
  svgReady.value = false
  svgError.value = ''
  imgW.value = 0
  imgH.value = 0
  clearPlaybackHighlight()
  zp.unbind()

  if (!url) return

  const controller = new AbortController()
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
    requestAnimationFrame(() => {
      zp.fitToView()
      applyPlaybackHighlight(false)
    })
  } catch {
    if (generation !== svgLoadGeneration) return
    svgReady.value = false
    svgError.value = 'SVG 加载失败'
  } finally {
    window.clearTimeout(timeout)
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
  svgRoot()?.querySelectorAll('.playback-current').forEach((node) => {
    node.classList.remove('playback-current')
  })
}

function highlightSource(sourceId: string): boolean {
  const svg = svgRoot()
  if (!svg || !sourceId) return false

  svg.querySelectorAll('.source-highlight-box').forEach((node) => node.remove())
  svg.querySelectorAll('.source-current').forEach((node) => {
    node.classList.remove('source-current')
  })

  const targets = Array.from(svg.querySelectorAll<SVGGElement>('.source-anchor'))
    .filter((element) => (element.dataset.sourceIds ?? '').split(/\s+/).includes(sourceId))
  if (!targets.length) return false

  targets.forEach((target) => {
    target.classList.add('source-current')
    addSourceHighlightBox(target)
  })
  keepTargetVisible(targets[0]!)
  return true
}

function addSourceHighlightBox(target: SVGGElement): void {
  let box: DOMRect
  try {
    box = target.getBBox()
  } catch {
    return
  }

  const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect')
  rect.setAttribute('x', String(box.x - 4))
  rect.setAttribute('y', String(box.y - 4))
  rect.setAttribute('width', String(box.width + 8))
  rect.setAttribute('height', String(box.height + 8))
  rect.setAttribute('rx', '4')
  rect.setAttribute('class', 'source-highlight-box')
  rect.setAttribute('pointer-events', 'none')
  target.appendChild(rect)
}

defineExpose({ highlightSource })

function applyPlaybackHighlight(reveal: boolean): void {
  const svg = svgRoot()
  if (!svg) return

  svg.querySelectorAll('.playback-current').forEach((node) => {
    node.classList.remove('playback-current')
  })

  if (props.currentNoteIndex < 0) return
  const targets = svg.querySelectorAll<SVGGElement>(
    `.playback-note[data-note-index="${props.currentNoteIndex}"]`
  )
  if (targets.length === 0) return

  targets.forEach((target) => target.classList.add('playback-current'))
  if (reveal) keepTargetVisible(targets[0])
}

function keepTargetVisible(target: SVGGraphicsElement): void {
  const viewport = containerRef.value
  if (!viewport) return

  let box: DOMRect
  try {
    box = target.getBBox()
  } catch {
    return
  }

  const margin = 32
  const scale = zp.scale.value
  const left = zp.tx.value + box.x * scale
  const right = zp.tx.value + (box.x + box.width) * scale
  const top = zp.ty.value + box.y * scale
  const bottom = zp.ty.value + (box.y + box.height) * scale

  if (left < margin) {
    zp.tx.value += margin - left
  } else if (right > viewport.clientWidth - margin) {
    zp.tx.value -= right - (viewport.clientWidth - margin)
  }

  if (top < margin) {
    zp.ty.value += margin - top
  } else if (bottom > viewport.clientHeight - margin) {
    zp.ty.value -= bottom - (viewport.clientHeight - margin)
  }

  zp.applyTransform()
}

watch(svgUrl, (url) => {
  void loadSvg(url)
}, { immediate: true })

watch(() => props.currentNoteIndex, () => {
  nextTick(() => applyPlaybackHighlight(true))
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

.svg-inline.hide-static-ocr :deep(.ocr-overlay) {
  display: none;
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
.svg-inline :deep(.playback-note.playback-current .lyric),
.svg-inline :deep(.source-anchor.source-current .lyric) {
  fill: #d97706;
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

.svg-inline :deep(.source-highlight-box) {
  fill: rgba(217, 119, 6, 0.12);
  stroke: #d97706;
  stroke-width: 2;
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
