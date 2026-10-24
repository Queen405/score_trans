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
          v-if="overlayImgUrl && showOverlay && canShowOverlay && !correctedOverlayEntities.length"
          :src="overlayImgUrl"
          class="svg-overlay-img"
          alt=""
          draggable="false"
        >
        <svg
          v-else-if="overlayImgUrl && showOverlay && canShowOverlay && sourceSheet && correctedOverlayEntities.length"
          class="svg-overlay-img"
          :viewBox="`0 0 ${sourceSheet.width} ${sourceSheet.height}`"
          :width="imgW || sourceSheet.width"
          :height="imgH || sourceSheet.height"
          aria-hidden="true"
        >
          <defs>
            <mask
              :id="overlayMaskId"
              maskUnits="userSpaceOnUse"
              :width="sourceSheet.width"
              :height="sourceSheet.height"
            >
              <rect :width="sourceSheet.width" :height="sourceSheet.height" fill="white" />
              <path
                v-for="item in correctedOverlayEntities"
                :key="`mask-${item.key}`"
                :d="item.hitPath"
                fill="black"
              />
            </mask>
          </defs>
          <image
            x="0"
            y="0"
            :width="sourceSheet.width"
            :height="sourceSheet.height"
            :href="overlayImgUrl"
            :mask="`url(#${overlayMaskId})`"
          />
          <svg
            v-for="item in correctedOverlayEntities"
            :key="`corrected-${item.key}`"
            :x="item.x"
            :y="item.y"
            :width="item.width"
            :height="item.height"
            viewBox="0 0 32 24"
            aria-hidden="true"
          >
            <RecognitionSymbol
              :shape="item.shape"
              :background="false"
              :style="{ width: '100%', height: '100%', color: 'var(--success)', opacity: 1 }"
            />
          </svg>
        </svg>
        <svg
          v-if="sourceSheet && canShowOverlay && (showOverlay || editable)"
          class="source-hit-layer"
          :class="{ editing: editable }"
          :viewBox="`0 0 ${sourceSheet.width} ${sourceSheet.height}`"
          :width="imgW || sourceSheet.width"
          :height="imgH || sourceSheet.height"
          :aria-label="t('components.originalPreview.clickableElementLabel')"
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
            :data-source-id="element.source_id"
            tabindex="0"
            @click.stop="handleSourceClick(element.source_id, $event)"
            @contextmenu.stop.prevent="openMarkerEditor(element.source_id, $event)"
            @keydown.enter.prevent="selectSource(element.source_id, $event)"
          />
        </svg>
        <svg
          v-if="editable && suspiciousGlyphs?.length && isImage"
          class="source-hit-layer glyph-source-hit-layer"
          :viewBox="`0 0 ${entitySheetWidth} ${entitySheetHeight}`"
          :width="imgW || entitySheetWidth"
          :height="imgH || entitySheetHeight"
        >
          <path
            v-for="glyph in suspiciousGlyphs"
            :key="glyph.glyph_id"
            :d="glyph.hit_path"
            class="source-hit source-hit--glyph"
            :class="{ selected: glyph.glyph_id === selectedGlyphId }"
            :data-glyph-id="glyph.glyph_id"
            tabindex="0"
            @click.stop="selectGlyph(glyph.glyph_id, $event, false)"
            @contextmenu.stop.prevent="selectGlyph(glyph.glyph_id, $event, true)"
            @keydown.enter.prevent="selectGlyph(glyph.glyph_id, $event, true)"
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
      </div>
      <div
        v-if="editable && editorVisible"
        class="marker-editor-anchor"
        :style="editorPosition"
        @click.stop
      >
        <slot name="marker-editor" :close="closeMarkerEditor" />
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
      <span>{{ t('components.originalPreview.uploadHint') }}</span>
    </div>
    <div
      v-if="fileUrl"
      class="zoom-bar"
    >
      <span class="zoom-label">{{ zp.displayPercent }}</span>
      <button
        class="zoom-btn"
        :title="t('components.originalPreview.fitWindowTitle')"
        @click="zp.reset()"
      >
        {{ t('components.originalPreview.fit') }}
      </button>
      <button
        v-if="canShowOverlay"
        class="zoom-btn"
        :class="{ active: showOverlay }"
        :title="t('components.originalPreview.toggleOverlayTitle')"
        @click="showOverlay = !showOverlay"
      >
        {{ t('components.originalPreview.overlay') }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch, nextTick, useId } from 'vue'
import { fetchFileBlob } from '../api/client'
import { t } from '../i18n'
import { ImageOutline } from '@vicons/ionicons5'
import { NIcon, useMessage } from 'naive-ui'
import { useZoomPan } from '../composables/useZoomPan'
import { useSettingsStore } from '../stores/settings'
import { useLogStore } from '../stores/log'
import type { CorrectableEntityDTO } from '../models/types'
import RecognitionSymbol from './RecognitionSymbol.vue'

const props = defineProps<{
  fileId: string
  fileName: string
  overlayFileId?: string
  sourceMapFileId?: string
  clickableSourceIds?: string[]
  mappedSourceIds?: string[]
  busy?: boolean
  selectedSourceId?: string
  editable?: boolean
  entities?: CorrectableEntityDTO[]
  appliedCandidateSelections?: Record<string, string>
  suspiciousGlyphs?: import('../models/types').SuspiciousGlyphDTO[]
  selectedGlyphId?: string
  deletedEntityIds?: Set<string>
  appliedDeletedSourceIds?: string[]
  entityWidth?: number
  entityHeight?: number
}>()
const emit = defineEmits<{
  selectSource: [sourceId: string]
  toggleDelete: [sourceId: string]
  selectGlyph: [glyphId: string]
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
const log = useLogStore()
const containerRef = ref<HTMLElement>()
const zp = useZoomPan(containerRef)
const imgW = ref(0)
const imgH = ref(0)
const fileUrl = ref('')
const overlayImgUrl = ref('')
const showOverlay = ref(settings.showRecognitionOverlay)
const sourceMap = ref<SourceMap | null>(null)
const editorVisible = ref(false)
const editorPosition = ref<Record<string, string>>({ left: '8px', top: '8px' })
let markerPositionObserver: InstanceType<typeof window.MutationObserver> | null = null
let markerResizeObserver: ResizeObserver | null = null
const overlayMaskId = `candidate-overlay-mask-${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`

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
const mappedSourceIdSet = computed(() => new Set(props.mappedSourceIds ?? []))
const appliedDeletedSourceIdSet = computed(() => new Set(props.appliedDeletedSourceIds ?? []))
const deletedMarkElements = computed(() => (
  sourceSheet.value?.elements.filter((element) => (
    appliedDeletedSourceIdSet.value.has(element.source_id)
      || props.deletedEntityIds?.has(element.source_id)
  )) ?? []
))
const clickableElements = computed(() => (
  sourceSheet.value?.elements.filter((element) => (
    (clickableSourceIdSet.value.has(element.source_id)
      || (props.editable && props.entities?.some((entity) => entity.source_id === element.source_id)))
    && !appliedDeletedSourceIdSet.value.has(element.source_id)
  )) ?? []
))
const disabledElements = computed(() => {
  return sourceSheet.value?.elements.filter(
    (element) => (
      !mappedSourceIdSet.value.has(element.source_id)
      && !clickableSourceIdSet.value.has(element.source_id)
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
const correctedOverlayEntities = computed(() => Object.entries(props.appliedCandidateSelections ?? {})
  .flatMap(([sourceId, shape]) => {
    const entity = props.entities?.find((item) => item.source_id === sourceId)
    if (entity && entity.bounds_w > 0 && entity.bounds_h > 0 && entity.hit_path) {
      return [{
        key: sourceId,
        shape,
        x: entity.bounds_x,
        y: entity.bounds_y,
        width: entity.bounds_w,
        height: entity.bounds_h,
        hitPath: entity.hit_path,
        grade: entity.grade,
      }]
    }
    const glyph = props.suspiciousGlyphs?.find((item) => item.glyph_id === sourceId)
    return glyph && glyph.bounds_w > 0 && glyph.bounds_h > 0 && glyph.hit_path
      ? [{
          key: sourceId,
          shape,
          x: glyph.bounds_x,
          y: glyph.bounds_y,
          width: glyph.bounds_w,
          height: glyph.bounds_h,
          hitPath: glyph.hit_path,
          grade: glyph.grade,
        }]
      : []
  }))

type MarkerTarget = { getBoundingClientRect: () => { left: number; right: number; top: number; bottom: number } }

function updateEditorPosition(target: MarkerTarget | null = null): void {
  if (!props.editable || !editorVisible.value) return
  const viewport = containerRef.value
  const inner = viewport?.querySelector<HTMLElement>('.zp-inner')
  const activeTarget = target ?? (props.selectedSourceId
    ? inner?.querySelector(`[data-source-id="${window.CSS.escape(props.selectedSourceId)}"]`)
    : props.selectedGlyphId
      ? inner?.querySelector(`[data-glyph-id="${window.CSS.escape(props.selectedGlyphId)}"]`)
      : null)
  if (!viewport || !activeTarget) return

  const viewportRect = viewport.getBoundingClientRect()
  const targetRect = activeTarget.getBoundingClientRect()
  const gap = 10
  const panelWidth = Math.min(318, Math.max(220, viewport.clientWidth - 16))
  const panelHeight = Math.min(470, Math.max(180, viewport.clientHeight - 16))
  const markerCenterX = (targetRect.left + targetRect.right) / 2 - viewportRect.left
  const markerCenterY = (targetRect.top + targetRect.bottom) / 2 - viewportRect.top
  const left = markerCenterX + panelWidth + gap <= viewport.clientWidth - 8
    ? markerCenterX + gap
    : markerCenterX - panelWidth - gap >= 8
      ? markerCenterX - panelWidth - gap
      : Math.max(8, Math.min(viewport.clientWidth - panelWidth - 8, markerCenterX - panelWidth / 2))
  const top = Math.max(8, Math.min(viewport.clientHeight - panelHeight - 8, markerCenterY - 40))
  editorPosition.value = { left: `${left}px`, top: `${top}px` }
}

function selectSource(sourceId: string, event: Event): void {
  if (props.busy) return
  if (props.editable) {
    editorVisible.value = true
    updateEditorPosition(event.currentTarget as unknown as MarkerTarget)
    requestAnimationFrame(() => updateEditorPosition())
  }
  emit('selectSource', sourceId)
}

function handleSourceClick(sourceId: string, event: Event): void {
  if (props.busy) return
  if (props.editable) {
    editorVisible.value = false
    const entity = props.entities?.find((item) => item.source_id === sourceId)
    if (entity?.can_delete) {
      emit('selectSource', sourceId)
      emit('toggleDelete', sourceId)
    }
    return
  }
  selectSource(sourceId, event)
}

function openMarkerEditor(sourceId: string, event: MouseEvent): void {
  if (!props.editable || props.busy) return
  editorVisible.value = true
  updateEditorPosition(event.currentTarget as unknown as MarkerTarget)
  emit('selectSource', sourceId)
  requestAnimationFrame(() => updateEditorPosition())
}

function closeMarkerEditor(): void {
  editorVisible.value = false
}

function selectGlyph(glyphId: string, event: Event, openEditor: boolean): void {
  if (props.busy) return
  editorVisible.value = openEditor
  if (openEditor) {
    updateEditorPosition(event.currentTarget as unknown as MarkerTarget)
    requestAnimationFrame(() => updateEditorPosition())
  }
  emit('selectGlyph', glyphId)
}

watch(() => props.editable, (editable) => {
  if (!editable) editorVisible.value = false
})

watch(() => [props.selectedSourceId, props.selectedGlyphId] as const, async () => {
  await nextTick()
  updateEditorPosition()
})

function notifyUnmapped(): void {
  message.info(t('components.originalPreview.noteNotMapped'))
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
    if (!active) return
    if (result.error) {
      // 切换页面/组件卸载触发的 abort 不算错误
      if (result.error.code === 'aborted') return
      const msg = result.error.message || t('components.originalPreview.unknownError')
      log.addError(t('components.originalPreview.sourceLoadFailedLog', { name: props.fileName, msg }))
      message.error(t('components.originalPreview.sourceLoadFailed', { msg }))
      return
    }
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
      if ([1, 2].includes(parsed.version) && Array.isArray(parsed.sheets)) sourceMap.value = parsed
    } catch {
      sourceMap.value = null
    }
  },
  { immediate: true },
)

onMounted(() => {
  zp.bind()
  const inner = containerRef.value?.querySelector<HTMLElement>('.zp-inner')
  if (inner) {
    markerPositionObserver = new window.MutationObserver(() => updateEditorPosition())
    markerPositionObserver.observe(inner, { attributes: true, attributeFilter: ['style'] })
  }
  if (containerRef.value) {
    markerResizeObserver = new ResizeObserver(() => updateEditorPosition())
    markerResizeObserver.observe(containerRef.value)
  }
})
onUnmounted(() => {
  zp.unbind()
  markerPositionObserver?.disconnect()
  markerResizeObserver?.disconnect()
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

.marker-editor-anchor {
  position: absolute;
  z-index: 30;
  width: min(318px, calc(100% - 16px));
  max-height: calc(100% - 20px);
  pointer-events: none;
}

.marker-editor-anchor :deep(.marker-inspector) {
  pointer-events: auto;
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
  z-index: 1;
  inset: 0;
  width: 100%;
  height: 100%;
  overflow: visible;
  pointer-events: none;
}

.glyph-source-hit-layer {
  z-index: 0;
}

.source-hit {
  fill: transparent;
  stroke: transparent;
  stroke-width: 5;
  vector-effect: non-scaling-stroke;
  pointer-events: visiblePainted;
  cursor: pointer;
  outline: none;
  transition: fill 0.14s ease, stroke 0.14s ease;
}

.source-hit:hover,
.source-hit:focus-visible {
  fill: color-mix(in srgb, var(--accent) 13%, transparent);
  stroke: color-mix(in srgb, var(--accent) 72%, transparent);
  stroke-width: 1.6;
}

/* 编辑模式下左键=删除，因此悬停预告的是删除结果 */
.source-hit-layer.editing .source-hit:hover,
.source-hit-layer.editing .source-hit:focus-visible {
  fill: color-mix(in srgb, var(--danger) 12%, transparent);
  stroke: color-mix(in srgb, var(--danger) 62%, transparent);
  stroke-width: 1.6;
  stroke-dasharray: 4 3;
}

.source-hit.selected {
  fill: color-mix(in srgb, var(--accent) 24%, transparent);
  stroke: var(--accent);
  stroke-width: 1.8;
  filter: drop-shadow(0 0 4px color-mix(in srgb, var(--accent) 55%, transparent));
}

.source-hit--glyph:hover,
.source-hit--glyph:focus-visible {
  fill: color-mix(in srgb, var(--warning) 16%, transparent);
  stroke: color-mix(in srgb, var(--warning) 80%, transparent);
  stroke-dasharray: 2 3;
}

.source-hit--glyph.selected {
  fill: color-mix(in srgb, var(--warning) 22%, transparent);
  stroke: var(--warning);
  stroke-width: 1.8;
  filter: drop-shadow(0 0 4px color-mix(in srgb, var(--warning) 55%, transparent));
}

.source-hit--disabled {
  fill: transparent;
  stroke: transparent;
  cursor: not-allowed;
}

.source-hit--disabled:hover,
.source-hit--disabled:focus-visible {
  fill: color-mix(in srgb, var(--text-tertiary) 10%, transparent);
  stroke: color-mix(in srgb, var(--text-tertiary) 60%, transparent);
  stroke-width: 1.6;
  stroke-dasharray: 4 3;
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
  fill: color-mix(in srgb, var(--danger) 9%, transparent);
  stroke: color-mix(in srgb, var(--danger) 82%, transparent);
  stroke-width: 2;
  stroke-dasharray: 5 3;
  stroke-linecap: round;
  stroke-linejoin: round;
  vector-effect: non-scaling-stroke;
  pointer-events: none;
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
