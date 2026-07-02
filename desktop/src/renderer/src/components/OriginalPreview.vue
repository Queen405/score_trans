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
          :viewBox="`0 0 ${sourceSheet.width} ${sourceSheet.height}`"
          :width="imgW || sourceSheet.width"
          :height="imgH || sourceSheet.height"
          aria-label="可点击识别元素"
        >
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
import { fetchFileBlob, getFileURL } from '../api/client'
import { ImageOutline } from '@vicons/ionicons5'
import { NIcon } from 'naive-ui'
import { useZoomPan } from '../composables/useZoomPan'

const props = defineProps<{
  fileId: string
  fileName: string
  overlayFileId?: string
  sourceMapFileId?: string
  clickableSourceIds?: string[]
  selectedSourceId?: string
}>()
const emit = defineEmits<{ selectSource: [sourceId: string] }>()

interface SourceElement {
  source_id: string
  hit_path: string
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

const containerRef = ref<HTMLElement>()
const zp = useZoomPan(containerRef)
const imgW = ref(0)
const imgH = ref(0)
const overlayImgUrl = ref('')
const showOverlay = ref(true)
const sourceMap = ref<SourceMap | null>(null)

const fileUrl = computed(() => (props.fileId ? getFileURL(props.fileId) : ''))
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
const clickableElements = computed(() => (
  sourceSheet.value?.elements.filter((element) => clickableSourceIdSet.value.has(element.source_id)) ?? []
))

function selectSource(sourceId: string): void {
  emit('selectSource', sourceId)
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
