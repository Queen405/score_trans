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
              x="0"
              y="0"
              :width="sourceSheet.width"
              :height="sourceSheet.height"
              maskContentUnits="userSpaceOnUse"
              mask-type="luminance"
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
              fit
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
          <g
            v-for="element in clickableElements"
            :key="element.source_id"
          >
            <path
              :d="element.hit_path"
              class="source-hit"
              :class="{
                selected: element.source_id === selectedSourceId,
                'source-hit--deleted': editable && isElementDeleted(element.source_id),
              }"
              :data-source-id="element.source_id"
              tabindex="0"
              @click.stop="handleSourceClick(element.source_id, $event)"
              @contextmenu.stop.prevent="openMarkerEditor(element.source_id, $event)"
              @keydown.enter.prevent="selectSource(element.source_id, $event)"
            >
              <title v-if="editable && isElementDeleted(element.source_id)">
                {{ t('convert.marker.restore') }}
              </title>
            </path>
            <path
              :d="element.hit_path"
              class="source-hit-outline"
              aria-hidden="true"
            />
          </g>
        </svg>
        <svg
          v-if="visibleSuspiciousGlyphs.length && isImage"
          class="source-hit-layer glyph-source-hit-layer"
          :class="{ editing: editable }"
          :viewBox="`0 0 ${entitySheetWidth} ${entitySheetHeight}`"
          :width="imgW || entitySheetWidth"
          :height="imgH || entitySheetHeight"
        >
          <g
            v-for="glyph in visibleSuspiciousGlyphs"
            :key="glyph.glyph_id"
          >
            <path
              :d="glyph.hit_path"
              class="source-hit source-hit--glyph"
              :class="{
                selected: glyph.glyph_id === selectedGlyphId,
                'source-hit--deleted': editable && isElementDeleted(glyph.glyph_id),
              }"
              :data-glyph-id="glyph.glyph_id"
              tabindex="0"
              @click.stop="handleGlyphClick(glyph.glyph_id, $event)"
              @contextmenu.stop.prevent="selectGlyph(glyph.glyph_id, $event, true)"
              @keydown.enter.prevent="selectGlyph(glyph.glyph_id, $event, true)"
            >
              <title v-if="!editable">
                {{ t('convert.marker.locateGlyph') }}
              </title>
              <title v-else-if="isElementDeleted(glyph.glyph_id)">
                {{ t('convert.marker.restore') }}
              </title>
              <title v-else>
                {{ t('convert.marker.delete') }}
              </title>
            </path>
            <path
              :d="glyph.hit_path"
              class="source-hit-outline"
              aria-hidden="true"
            />
          </g>
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
            :class="{ 'deleted-mark--restore': isPendingRestore(element.source_id) }"
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
  selectGlyph: [glyphId: string, openEditor: boolean]
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
  glyphs?: { glyph_id: string; hit_path: string; suspicious?: boolean }[]
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
const deletedMarkElements = computed(() => {
  const deletedIds = new Set([
    ...appliedDeletedSourceIdSet.value,
    ...(props.deletedEntityIds ?? []),
  ])
  return [
    ...(sourceSheet.value?.elements ?? [])
      .filter((element) => deletedIds.has(element.source_id))
      .map((element) => ({ source_id: element.source_id, hit_path: element.hit_path })),
    ...(sourceSheet.value?.glyphs ?? [])
      .filter((glyph) => glyph.suspicious && deletedIds.has(glyph.glyph_id))
      .map((glyph) => ({ source_id: glyph.glyph_id, hit_path: glyph.hit_path })),
    ...(props.suspiciousGlyphs ?? [])
      .filter((glyph) => deletedIds.has(glyph.glyph_id))
      .map((glyph) => ({ source_id: glyph.glyph_id, hit_path: glyph.hit_path })),
  ].filter((item, index, items) => (
    items.findIndex((candidate) => candidate.source_id === item.source_id) === index
  ))
})
// 未识别字形：编辑模式下全部可见（可点选/撤销），
// 非编辑模式只保留选过候选的，避免整页碎片抢点击。
const visibleSuspiciousGlyphs = computed(() => {
  const glyphs = props.suspiciousGlyphs ?? []
  if (props.editable) return glyphs
  const applied = props.appliedCandidateSelections ?? {}
  return glyphs.filter((glyph) => glyph.glyph_id in applied)
})

const clickableElements = computed(() => (
  sourceSheet.value?.elements.filter((element) => {
    const mapped = clickableSourceIdSet.value.has(element.source_id)
      || (props.editable
        && props.entities?.some((entity) => entity.source_id === element.source_id))
    if (!mapped) return false
    // 已应用的删除在编辑模式下必须保留命中区，否则无法再点回来恢复
    if (appliedDeletedSourceIdSet.value.has(element.source_id)) return props.editable
    return true
  }) ?? []
))
function isElementDeleted(sourceId: string): boolean {
  return appliedDeletedSourceIdSet.value.has(sourceId)
    || Boolean(props.deletedEntityIds?.has(sourceId))
}

/** 已写入 MusicXML 的删除，又被重新点亮：等待再次应用即可恢复。 */
function isPendingRestore(sourceId: string): boolean {
  return appliedDeletedSourceIdSet.value.has(sourceId)
    && !props.deletedEntityIds?.has(sourceId)
}

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
    // 与当前识别形状相同就没有预览的必要（例如把候选改回原形状）
    if (entity && entity.shape === shape) return []
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
    if (entity) {
      // 左键只切换删除状态：选中态是蓝色实线，会和「已删除」的红色虚线抢同一轮廓，
      // 导致用户点完看到的是蓝色而不是已删除。实体列表只包含后端支持精确 MusicXML
      // patch 的类型，因此不要再用可选 DTO 字段 can_delete 二次拦截左键。
      // 旧版/缓存 API 响应中的 can_delete=false 曾让很多合法标记看得到却点不掉。
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
  emit('selectGlyph', glyphId, openEditor)
}

function handleGlyphClick(glyphId: string, event: MouseEvent): void {
  if (props.busy) return
  if (props.editable) {
    editorVisible.value = false
    emit('toggleDelete', glyphId)
    return
  }
  // 普通预览模式下，已插入的 glyph 仍可定位到简谱对应位置。
  selectGlyph(glyphId, event, false)
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
      if ([1, 2, 3].includes(parsed.version) && Array.isArray(parsed.sheets)) sourceMap.value = parsed
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
  width: min(256px, calc(100% - 16px));
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
  /* 保留已识别标记在上层，避免重叠的碎片 Glyph 抢走其点击。 */
  z-index: 0;
}

.source-hit {
  /* 命中层：宽描边只用来扩大点击热区，颜色始终透明，不参与视觉。
     视觉高亮由后面的 .source-hit-outline 细线绘制，保证线宽不受热区影响。 */
  fill: transparent;
  stroke: transparent;
  stroke-width: 6;
  vector-effect: non-scaling-stroke;
  pointer-events: all;
  cursor: pointer;
  outline: none;
  transition: fill 0.14s ease;
}

/* 视觉轮廓层：细线、不参与命中，线宽不随缩放或状态变化 */
.source-hit-outline {
  fill: transparent;
  stroke: transparent;
  stroke-width: 2;
  stroke-linejoin: round;
  vector-effect: non-scaling-stroke;
  pointer-events: none;
  transition: stroke 0.14s ease;
}

.source-hit:hover,
.source-hit:focus-visible {
  fill: color-mix(in srgb, var(--accent) 13%, transparent);
}

.source-hit:hover + .source-hit-outline,
.source-hit:focus-visible + .source-hit-outline {
  stroke: color-mix(in srgb, var(--accent) 78%, transparent);
}

/* 编辑模式下左键=删除，悬停时预告删除结果 */
.source-hit-layer.editing .source-hit:hover,
.source-hit-layer.editing .source-hit:focus-visible {
  fill: color-mix(in srgb, var(--danger) 12%, transparent);
}

.source-hit-layer.editing .source-hit:hover + .source-hit-outline,
.source-hit-layer.editing .source-hit:focus-visible + .source-hit-outline {
  stroke: color-mix(in srgb, var(--danger) 68%, transparent);
}

.source-hit.selected {
  fill: color-mix(in srgb, var(--accent) 15%, transparent);
}

.source-hit.selected + .source-hit-outline {
  stroke: var(--accent);
  filter: drop-shadow(0 0 2px color-mix(in srgb, var(--accent) 40%, transparent));
}

/* 已经标记为删除的记号，再点一次是「恢复」，用绿色预告 */
.source-hit-layer.editing .source-hit--deleted:hover,
.source-hit-layer.editing .source-hit--deleted:focus-visible {
  fill: color-mix(in srgb, var(--danger) 10%, transparent);
}

.source-hit-layer.editing .source-hit--deleted:hover + .source-hit-outline,
.source-hit-layer.editing .source-hit--deleted:focus-visible + .source-hit-outline {
  stroke: color-mix(in srgb, var(--danger) 75%, transparent);
}

/* 已删除的记号即使同时处于选中态，也必须以删除色呈现 */
.source-hit.selected.source-hit--deleted + .source-hit-outline {
  stroke: color-mix(in srgb, var(--danger) 82%, transparent);
  filter: none;
}

.source-hit--glyph:hover,
.source-hit--glyph:focus-visible {
  fill: color-mix(in srgb, var(--warning) 15%, transparent);
}

.source-hit--glyph:hover + .source-hit-outline,
.source-hit--glyph:focus-visible + .source-hit-outline {
  stroke: color-mix(in srgb, var(--warning) 82%, transparent);
}

.source-hit--glyph.selected {
  fill: color-mix(in srgb, var(--accent) 15%, transparent);
}

.source-hit--glyph.selected + .source-hit-outline {
  stroke: var(--accent);
  filter: drop-shadow(0 0 2px color-mix(in srgb, var(--accent) 40%, transparent));
}

/* 漏识别 Glyph 用黄色提示可疑状态；右键选中后与已识别标记一致。 */
.source-hit-layer.editing .source-hit.source-hit--glyph:hover,
.source-hit-layer.editing .source-hit.source-hit--glyph:focus-visible {
  fill: color-mix(in srgb, var(--warning) 15%, transparent);
}

.source-hit-layer.editing .source-hit.source-hit--glyph:hover + .source-hit-outline,
.source-hit-layer.editing .source-hit.source-hit--glyph:focus-visible + .source-hit-outline {
  stroke: color-mix(in srgb, var(--warning) 82%, transparent);
}

/* 右键后的选中态优先于悬浮色，但已删除标记仍保持删除色。 */
.source-hit-layer.editing .source-hit.selected:not(.source-hit--deleted) {
  fill: color-mix(in srgb, var(--accent) 15%, transparent);
}

.source-hit-layer.editing .source-hit.selected:not(.source-hit--deleted) + .source-hit-outline {
  stroke: var(--accent);
  filter: drop-shadow(0 0 2px color-mix(in srgb, var(--accent) 40%, transparent));
}

.source-hit--disabled {
  fill: transparent;
  stroke: transparent;
  cursor: not-allowed;
}

/* 删除/候选编辑模式下，非可编辑结构标记不能遮挡漏检 Glyph 的命中区。 */
.source-hit-layer.editing .source-hit--disabled {
  pointer-events: none;
}

.source-hit--disabled:hover,
.source-hit--disabled:focus-visible {
  fill: color-mix(in srgb, var(--text-tertiary) 12%, transparent);
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
  z-index: 2;
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

.deleted-mark--restore {
  fill: color-mix(in srgb, var(--success) 8%, transparent);
  stroke: color-mix(in srgb, var(--success) 78%, transparent);
}

.scan-img {
  transition: filter 0.2s ease, opacity 0.2s ease;
}

.scan-img.dimmed {
  filter: grayscale(0.5) brightness(0.95);
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
