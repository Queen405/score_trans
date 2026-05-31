<template>
  <div class="svg-preview" v-if="svgUrl">
    <div ref="containerRef" class="preview-viewport" @dblclick="addBlockAtCursor">
      <div class="zp-inner">
        <img :key="svgUrl" :src="svgUrl" :style="imageStyle" @load="onImgLoad" />
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
          />
          <span v-else>{{ block.text }}</span>
          <span
            v-if="editableOcr && selectedId === block.id && editingId !== block.id"
            class="ocr-resize-handle"
            @mousedown.stop.prevent="startResize(block, $event)"
          />
        </button>
      </div>
    </div>
    <div class="zoom-bar">
      <span class="zoom-label">{{ Math.round(zp.scale.value * 100) }}%</span>
      <button class="zoom-btn" @click="zp.reset()" title="适应窗口">适应</button>
    </div>
  </div>
  <div v-else class="svg-empty">
    <n-icon size="32" :depth="3"><ImageOutline /></n-icon>
    <span>暂无 SVG</span>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch, nextTick } from 'vue'
import { getFileURL } from '../api/client'
import { ImageOutline } from '@vicons/ionicons5'
import { NIcon } from 'naive-ui'
import { useZoomPan } from '../composables/useZoomPan'
import { parseOcrText, serializeOcrText, type OcrTextBlock } from '../utils/ocrText'

const props = withDefaults(defineProps<{ svgFileId: string; ocrText?: string; editableOcr?: boolean }>(), {
  ocrText: '',
  editableOcr: false,
})
const emit = defineEmits<{ 'update:ocrText': [value: string] }>()
const svgUrl = computed(() => (props.svgFileId ? getFileURL(props.svgFileId) : ''))

const containerRef = ref<HTMLElement>()
const zp = useZoomPan(containerRef)
const imgW = ref(0)
const imgH = ref(0)
const selectedId = ref('')
const editingId = ref('')
const editingText = ref('')
const ocrBlocks = ref<OcrTextBlock[]>([])
let dragging: {
  id: string
  startClientX: number
  startClientY: number
  startBbox: number[]
} | null = null
let resizing: {
  id: string
  startClientX: number
  startClientY: number
  startBbox: number[]
} | null = null
const imageStyle = computed(() => ({
  width: imgW.value > 0 ? `${imgW.value}px` : 'auto',
  height: imgH.value > 0 ? `${imgH.value}px` : 'auto',
}))

function onImgLoad(e: Event) {
  const img = e.target as HTMLImageElement
  if (img.naturalWidth > 0 && img.naturalHeight > 0) {
    imgW.value = img.naturalWidth
    imgH.value = img.naturalHeight
  }
  requestAnimationFrame(() => zp.fitToView())
}

function selectBlock(id: string): void {
  selectedId.value = id
}

function ocrBlockStyle(block: OcrTextBlock) {
  const bbox = block.bbox ?? [12, 12, 120, 36]
  const [x1, y1, x2, y2] = scaleBBoxToImage(bbox)
  return {
    left: `${x1}px`,
    top: `${y1}px`,
    width: `${Math.max(24, x2 - x1)}px`,
    height: `${Math.max(18, y2 - y1)}px`,
    fontSize: `${Math.max(10, Math.min(34, (y2 - y1) * 0.78))}px`,
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
  ocrBlocks.value = ocrBlocks.value.filter((block) => block.id !== id)
  if (selectedId.value === id) selectedId.value = ''
  emitOcr()
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

watch(svgUrl, async (url) => {
  if (url) {
    imgW.value = 0
    imgH.value = 0
    await nextTick()
    zp.unbind()
    zp.bind()
  }
})

watch(() => props.ocrText, (value) => {
  ocrBlocks.value = parseOcrText(value || '')
}, { immediate: true })

onMounted(() => {
  if (svgUrl.value) zp.bind()
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

.zp-inner img {
  display: block;
  max-width: none;
  max-height: none;
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
</style>
