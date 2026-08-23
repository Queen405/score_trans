<template>
  <div class="original-preview">
    <div
      ref="containerRef"
      class="preview-viewport"
    >
      <div class="zp-inner">
        <iframe
          v-if="fileUrl && isPdf"
          :src="pdfFitUrl"
          :title="fileName"
          class="scan-iframe"
        />
        <img
          v-else-if="fileUrl && isImage"
          :src="fileUrl"
          :alt="fileName"
          :width="imgW"
          :height="imgH"
          class="scan-img"
          :class="{ dimmed: showOverlay && canShowOverlay }"
          @load="onImgLoad"
        >
        <img
          v-if="overlayImgUrl && showOverlay && canShowOverlay"
          :src="overlayImgUrl"
          class="svg-overlay-img"
          alt=""
          draggable="false"
        >
        <svg
          v-if="sourceSheet && showOverlay && canShowOverlay"
          class="source-hit-layer"
          :class="{ disabled: editable }"
          :viewBox="`0 0 ${sourceSheet.width} ${sourceSheet.height}`"
          :width="imgW || sourceSheet.width"
          :height="imgH || sourceSheet.height"
          aria-label="可点击识别元素"
        >
          <path
            v-for="element in disabledElements"
            :key="`disabled-${element.source_id}`"
            :d="element.hit_path"
            class="source-hit source-hit--disabled"
            @click.stop="notifyUnmapped"
          />
          <path
            v-for="element in clickableElements"
            :key="element.source_id"
            :d="element.hit_path"
            class="source-hit"
            :class="{ selected: element.source_id === selectedSourceId }"
            tabindex="0"
            @click.stop="selectSource(element.source_id)"
            @keydown.enter.prevent="selectSource(element.source_id)"
          />
        </svg>
        <svg
          v-if="deletedMarkElements.length > 0 && isImage"
          class="deleted-mark-layer"
          :viewBox="`0 0 ${sourceSheet?.width ?? 0} ${sourceSheet?.height ?? 0}`"
          :width="imgW || sourceSheet?.width"
          :height="imgH || sourceSheet?.height"
          aria-hidden="true"
        >
          <path
            v-for="element in deletedMarkElements"
            :key="`deleted-mark-${element.source_id}`"
            :d="element.hit_path"
            class="deleted-mark"
          />
        </svg>
        <svg
          v-if="editable && entitySheetWidth > 0 && entitySheetHeight > 0"
          class="entity-edit-layer"
          :viewBox="`0 0 ${entitySheetWidth} ${entitySheetHeight}`"
          :width="imgW || entitySheetWidth"
          :height="imgH || entitySheetHeight"
          aria-label="可删除标记"
        >
          <rect
            v-for="entity in entities"
            :key="entity.source_id"
            :x="entity.bounds_x"
            :y="entity.bounds_y"
            :width="entity.bounds_w"
            :height="entity.bounds_h"
            class="entity-box"
            :class="[entity.tag, { deleted: isDeleted(entity.source_id) }]"
            tabindex="0"
            @click.stop="$emit('toggleDelete', entity.source_id)"
            @keydown.enter.prevent="$emit('toggleDelete', entity.source_id)"
          />
        </svg>
      </div>
    </div>
    <div
      v-if="!fileUrl"
      class="empty-overlay"
    >
      <n-icon
        size="32"
        :depth="3"
      >
        <ImageOutline />
      </n-icon>
      <span>上传图片或 PDF 后对照原始五线谱</span>
    </div>
    <div
      v-if="fileUrl"
      class="zoom-bar"
    >
      <span class="zoom-label">{{ Math.round(zp.scale.value * 100) }}%</span>
      <button
        class="zoom-btn"
        title="适应窗口"
        @click="zp.reset()"
      >
        适应
      </button>
      <button
        v-if="canShowOverlay"
        class="zoom-btn"
        :class="{ active: showOverlay }"
        title="切换识别结果叠加"
        @click="showOverlay = !showOverlay"
      >
        叠加
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch, nextTick } from 'vue'
import { fetchFileBlob } from '../api/client'
import { ImageOutline } from '@vicons/ionicons5'
import { NIcon, useMessage } from 'naive-ui'
import { useZoomPan } from '../composables/useZoomPan'
import { useSettingsStore } from '../stores/settings'
import type { CorrectableEntityDTO } from '../models/types'

const props = defineProps<{
  fileId: string
  fileName: string
  overlayFileId?: string
  sourceMapFileId?: string
  clickableSourceIds?: string[]
  selectedSourceId?: string
  editable?: boolean
  entities?: CorrectableEntityDTO[]
  deletedEntityIds?: Set<string>
  appliedDeletedSourceIds?: string[]
  entityWidth?: number
  entityHeight?: number
}>()
const emit = defineEmits<{
  selectSource: [sourceId: string]
  toggleDelete: [sourceId: string]
}>()

interface SourceElement {
  source_id: string
  hit_path: string
  shape?: string | null
}

interface SourceMapSheet {
  width: number
  height: number
  elements: SourceElement[]
}

interface SourceMap {
  version: number
  sheets: SourceMapSheet[]
}

const settings = useSettingsStore()
const message = useMessage()
const containerRef = ref<HTMLElement>()
const zp = useZoomPan(containerRef)
const imgW = ref(0)
const imgH = ref(0)
const fileUrl = ref('')
const overlayImgUrl = ref('')
const showOverlay = ref(settings.showRecognitionOverlay)
const sourceMap = ref<SourceMap | null>(null)

const pdfFitUrl = computed(() =>
  fileUrl.value ? `${fileUrl.value}#toolbar=0&navpanes=0&scrollbar=0&view=FitH` : '',
)
const extension = computed(() => props.fileName.split('.').pop()?.toLowerCase() ?? '')
const isPdf = computed(() => extension.value === 'pdf')
const isImage = computed(() => ['png', 'jpg', 'jpeg', 'tif', 'tiff', 'webp'].includes(extension.value))
const hasOverlay = computed(() => !!props.overlayFileId)
const canShowOverlay = computed(() => hasOverlay.value && isImage.value)
const sourceSheet = computed(() => sourceMap.value?.sheets?.[0] ?? null)
const clickableSourceIdSet = computed(() => new Set(props.clickableSourceIds ?? []))
const appliedDeletedSourceIdSet = computed(() => new Set(props.appliedDeletedSourceIds ?? []))
const deletedMarkElements = computed(() => (
  sourceSheet.value?.elements.filter((element) => (
    appliedDeletedSourceIdSet.value.has(element.source_id)
  )) ?? []
))
const clickableElements = computed(() => (
  sourceSheet.value?.elements.filter((element) => (
    clickableSourceIdSet.value.has(element.source_id)
    && !appliedDeletedSourceIdSet.value.has(element.source_id)
  )) ?? []
))
const disabledElements = computed(() => {
  if (!clickableSourceIdSet.value.size) return []
  return sourceSheet.value?.elements.filter(
    (element) => (
      !clickableSourceIdSet.value.has(element.source_id)
      && !appliedDeletedSourceIdSet.value.has(element.source_id)
      && !isUnanchoredByDesign(element)
    ),
  ) ?? []
})

// 与后端 domain/reconciliation.py 的 _UNANCHORED_BY_DESIGN_PREFIXES 对齐：
// 谱号/调号/拍号/连音数字等结构符号设计上就没有简谱锚点，
// 不应渲染为 disabled 命中区（避免点击时弹出误导性的"未识别"提示）。
const UNANCHORED_SHAPE_PREFIXES = ['KEY_', 'TIME_', 'TUPLET_'] as const

function isUnanchoredByDesign(element: SourceElement): boolean {
  const shape = element.shape
  if (!shape) return true
  if (shape.includes('CLEF')) return true
  return UNANCHORED_SHAPE_PREFIXES.some((prefix) => shape.startsWith(prefix))
}
const entitySheetWidth = computed(() => props.entityWidth || sourceSheet.value?.width || 0)
const entitySheetHeight = computed(() => props.entityHeight || sourceSheet.value?.height || 0)

function isDeleted(sourceId: string): boolean {
  return props.deletedEntityIds?.has(sourceId) ?? false
}

function selectSource(sourceId: string): void {
  emit('selectSource', sourceId)
}

function notifyUnmapped(): void {
  message.info('该音符未能进入识别结果，无法定位到简谱')
}

function onImgLoad(e: Event) {
  const img = e.target as HTMLImageElement
  if (img.naturalWidth > 0 && img.naturalHeight > 0) {
    imgW.value = img.naturalWidth
    imgH.value = img.naturalHeight
  }
  requestAnimationFrame(() => zp.fitToView())
}

watch(fileUrl, async (url) => {
  if (url) {
    await nextTick()
    zp.unbind()
    zp.bind()
  }
})

watch(
  () => props.fileId,
  async (fileId, _previous, onCleanup) => {
    showOverlay.value = settings.showRecognitionOverlay
    const controller = new AbortController()
    let active = true
    onCleanup(() => {
      active = false
      controller.abort()
    })

    if (fileUrl.value) {
      URL.revokeObjectURL(fileUrl.value)
      fileUrl.value = ''
    }
    if (!fileId) return

    const result = await fetchFileBlob(fileId, controller.signal)
    if (!active || result.error) return
    fileUrl.value = URL.createObjectURL(result.data)
  },
  { immediate: true },
)

watch(
  () => [props.overlayFileId ?? '', canShowOverlay.value] as const,
  async ([fileId, enabled], _previous, onCleanup) => {
    const controller = new AbortController()
    let active = true
    onCleanup(() => {
      active = false
      controller.abort()
    })

    if (overlayImgUrl.value) {
      URL.revokeObjectURL(overlayImgUrl.value)
      overlayImgUrl.value = ''
    }
    if (!fileId || !enabled) return

    const result = await fetchFileBlob(fileId, controller.signal)
    if (!active || result.error) return
    overlayImgUrl.value = URL.createObjectURL(result.data)
  },
  { immediate: true },
)

watch(
  () => props.sourceMapFileId ?? '',
  async (fileId, _previous, onCleanup) => {
    const controller = new AbortController()
    let active = true
    onCleanup(() => {
      active = false
      controller.abort()
    })
    sourceMap.value = null
    if (!fileId) return
    const result = await fetchFileBlob(fileId, controller.signal)
    if (!active || result.error) return
    try {
      const parsed = JSON.parse(await result.data.text()) as SourceMap
      if (parsed.version === 1 && Array.isArray(parsed.sheets)) sourceMap.value = parsed
    } catch {
      sourceMap.value = null
    }
  },
  { immediate: true },
)

onMounted(() => zp.bind())
onUnmounted(() => {
  zp.unbind()
  if (fileUrl.value) URL.revokeObjectURL(fileUrl.value)
  if (overlayImgUrl.value) URL.revokeObjectURL(overlayImgUrl.value)
})
</script>

<style scoped>
.original-preview {
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
  will-change: transform;
}

.zp-inner img {
  display: block;
  max-width: none;
  max-height: none;
}

.svg-overlay-img {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  contain: layout style paint;
}

.source-hit-layer {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  overflow: visible;
  pointer-events: none;
}

.source-hit {
  fill: rgba(14, 165, 233, 0.001);
  stroke: rgba(14, 165, 233, 0.001);
  stroke-width: 4;
  vector-effect: non-scaling-stroke;
  pointer-events: visiblePainted;
  cursor: pointer;
  outline: none;
}

.source-hit:hover,
.source-hit:focus {
  fill: rgba(14, 165, 233, 0.16);
  stroke: rgba(2, 132, 199, 0.9);
  stroke-width: 2;
}

.source-hit.selected {
  fill: rgba(245, 158, 11, 0.22);
  stroke: rgba(217, 119, 6, 1);
  stroke-width: 4;
  animation: source-hit-pulse 1.2s ease-in-out infinite;
}

.source-hit--disabled {
  fill: rgba(100, 116, 139, 0.001);
  stroke: rgba(100, 116, 139, 0.001);
  cursor: not-allowed;
}

.source-hit--disabled:hover,
.source-hit--disabled:focus {
  fill: rgba(100, 116, 139, 0.1);
  stroke: rgba(100, 116, 139, 0.7);
  stroke-width: 2;
  stroke-dasharray: 4 3;
}

@keyframes source-hit-pulse {
  0%, 100% {
    stroke-opacity: 1;
    fill-opacity: 0.22;
  }
  50% {
    stroke-opacity: 0.6;
    fill-opacity: 0.35;
  }
}

.source-hit-layer.disabled {
  pointer-events: none;
}

.source-hit-layer.disabled .source-hit {
  pointer-events: none;
}

.deleted-mark-layer {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  overflow: visible;
  pointer-events: none;
}

.deleted-mark {
  fill: none;
  stroke: rgba(255, 51, 51, 0.84);
  stroke-width: 2.5;
  stroke-dasharray: 6 4;
  stroke-linecap: round;
  stroke-linejoin: round;
  vector-effect: non-scaling-stroke;
  pointer-events: none;
}

.entity-edit-layer {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  overflow: visible;
  pointer-events: none;
}

.entity-box {
  fill: rgba(0, 170, 68, 0.001);
  stroke-width: 2;
  stroke: #00aa44;
  vector-effect: non-scaling-stroke;
  pointer-events: visiblePainted;
  cursor: pointer;
  transition: fill 0.15s, stroke-opacity 0.15s;
}

.entity-box.clef,
.entity-box.time-whole,
.entity-box.time-custom,
.entity-box.key {
  stroke: #0066ff;
}

.entity-box.alter {
  stroke: #cc00cc;
}

.entity-box:hover {
  fill: rgba(0, 170, 68, 0.2);
}

.entity-box.deleted {
  stroke: #ff3333;
  stroke-width: 1.5;
  fill: rgba(255, 51, 51, 0.001);
  stroke-dasharray: 6 4;
  stroke-opacity: 0.3;
}

.entity-box.deleted:hover {
  stroke-opacity: 0.65;
}

.scan-img {
  transition: filter 0.2s ease, opacity 0.2s ease;
}

.scan-img.dimmed {
  filter: grayscale(0.5) brightness(0.95) blur(1px);
  opacity: 0.75;
}

.zp-inner iframe {
  display: block;
  width: 100%;
  height: 100%;
  border: 0;
  min-height: 500px;
}

.empty-overlay {
  position: absolute;
  inset: 0;
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
  font-weight: 600;
}
</style>
