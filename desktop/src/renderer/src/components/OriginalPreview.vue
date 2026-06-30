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
        />
        <img
          v-else-if="fileUrl && isImage"
          :src="fileUrl"
          :alt="fileName"
          :width="imgW"
          :height="imgH"
          @load="onImgLoad"
        >
        <div
          v-if="overlaySvgText && showOverlay"
          class="svg-overlay"
          v-html="overlaySvgText"
        />
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
        v-if="overlaySvgText"
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
import { getFileURL } from '../api/client'
import { ImageOutline } from '@vicons/ionicons5'
import { NIcon } from 'naive-ui'
import { useZoomPan } from '../composables/useZoomPan'

const props = defineProps<{
  fileId: string
  fileName: string
  overlayFileId?: string
}>()

const containerRef = ref<HTMLElement>()
const zp = useZoomPan(containerRef)
const imgW = ref(0)
const imgH = ref(0)
const overlaySvgText = ref('')
const showOverlay = ref(true)

const fileUrl = computed(() => (props.fileId ? getFileURL(props.fileId) : ''))
const overlayUrl = computed(() =>
  props.overlayFileId ? getFileURL(props.overlayFileId) : '',
)
const pdfFitUrl = computed(() =>
  fileUrl.value ? `${fileUrl.value}#toolbar=0&navpanes=0&scrollbar=0&view=FitH` : '',
)
const extension = computed(() => props.fileName.split('.').pop()?.toLowerCase() ?? '')
const isPdf = computed(() => extension.value === 'pdf')
const isImage = computed(() => ['png', 'jpg', 'jpeg', 'tif', 'tiff', 'webp'].includes(extension.value))

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

watch(overlayUrl, async (url) => {
  if (!url) {
    overlaySvgText.value = ''
    return
  }
  try {
    const resp = await fetch(url)
    if (resp.ok) {
      overlaySvgText.value = await resp.text()
    }
  } catch {
    overlaySvgText.value = ''
  }
}, { immediate: true })

onMounted(() => zp.bind())
onUnmounted(() => zp.unbind())
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
}

.zp-inner img {
  display: block;
  max-width: none;
  max-height: none;
}

.svg-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.svg-overlay :deep(svg) {
  display: block;
  width: 100%;
  height: 100%;
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
